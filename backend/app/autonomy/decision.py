"""Autonomous decision engine (Section 31, bounded by Section 35.8).

Turns events into *proposed actions*. It never executes real-world side effects directly — it
classifies, consults the deterministic approval policy, updates memory, and emits notifications or
approval requests. Untrusted event content is never treated as an instruction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from sqlmodel import Session

from app.agent.content_trust import scan_untrusted
from app.autonomy.events import Event, EventType
from app.autonomy.memory import MemoryManager, MemoryRecord
from app.autonomy.notifications import Notification, NotificationDispatcher
from app.core.config import Settings, get_settings
from app.security import approval as policy


class Disposition(str, Enum):
    ignored = "ignored"
    remembered = "remembered"
    notified = "notified"
    approval_requested = "approval_requested"
    flagged_untrusted = "flagged_untrusted"


@dataclass
class Decision:
    event_type: EventType
    disposition: Disposition
    detail: str
    proposed_action: str | None = None
    requires_approval: bool = False
    security_warnings: list[str] = field(default_factory=list)


class DecisionEngine:
    def __init__(
        self,
        session: Session,
        memory: MemoryManager,
        notifier: NotificationDispatcher,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._memory = memory
        self._notifier = notifier
        self._settings = settings or get_settings()

    def decide(self, event: Event) -> Decision:
        # Any untrusted content is scanned before anything else; injection attempts are flagged
        # and never treated as authorization (Section 35 / content-trust).
        if event.untrusted:
            text = " ".join(str(v) for v in event.payload.values())
            scan = scan_untrusted(text)
            if scan.is_suspicious:
                self._memory.remember(
                    MemoryRecord(
                        kind="security",
                        content=f"Injection-like content from {event.source}: {scan.reason}",
                        source=event.source,
                        confidence=1.0,
                    )
                )
                return Decision(
                    event_type=event.type,
                    disposition=Disposition.flagged_untrusted,
                    detail="Untrusted content flagged; treated as data, not instructions.",
                    security_warnings=[scan.reason],
                )

        handler = {
            EventType.email_received: self._on_email,
            EventType.calendar_updated: self._on_calendar,
            EventType.task_changed: self._on_task,
            EventType.user_message: self._on_user_message,
            EventType.message_received: self._on_message,
            EventType.system: self._on_system,
        }.get(event.type)
        if handler is None:
            return Decision(event.type, Disposition.ignored, "No handler for event type.")
        return handler(event)

    # --- handlers ---------------------------------------------------------------
    def _on_email(self, event: Event) -> Decision:
        importance = event.payload.get("importance", "informational")
        why = (event.payload.get("why_it_matters") or "").strip()
        if importance in {"critical", "needs_action_today", "dangerous"}:
            self._notifier.dispatch(
                Notification(
                    title="Important email",
                    body=f"{event.summary} — {why}" if why else event.summary,
                    category="email",
                )
            )
            # Preparing a reply is an external effect → always via approval policy, never auto-sent.
            decision = policy.evaluate(
                "send_approved_email",
                autonomy_level=self._settings.default_autonomy_level,
                payload={"to": [event.payload.get("sender", "")]},
                recipient_trusted=False,
            )
            return Decision(
                event_type=event.type,
                disposition=Disposition.notified,
                detail=f"High-importance email surfaced ({importance}).",
                proposed_action="prepare_reply_draft",
                requires_approval=decision.requires_approval,
            )
        self._memory.remember(
            MemoryRecord(kind="email", content=event.summary, source=event.source, confidence=0.6)
        )
        return Decision(event.type, Disposition.remembered, "Low-importance email noted.")

    def _on_calendar(self, event: Event) -> Decision:
        self._notifier.dispatch(
            Notification(title="Upcoming", body=event.summary, category="calendar")
        )
        return Decision(event.type, Disposition.notified, "Upcoming calendar item surfaced.")

    def _on_task(self, event: Event) -> Decision:
        self._notifier.dispatch(
            Notification(title="Task due", body=event.summary, category="task")
        )
        return Decision(event.type, Disposition.notified, "Due task surfaced.")

    def _on_user_message(self, event: Event) -> Decision:
        self._memory.remember(
            MemoryRecord(kind="interaction", content=event.summary, source=event.source)
        )
        return Decision(event.type, Disposition.remembered, "User message recorded.")

    def _on_message(self, event: Event) -> Decision:
        # Inbound iMessage/SMS: surface it proactively and remember it. Any reply is an external
        # effect and only happens later through the approval-gated send_imessage tool.
        self._notifier.dispatch(
            Notification(title="New message", body=event.summary, category="imessage")
        )
        self._memory.remember(
            MemoryRecord(kind="message", content=event.summary, source=event.source, confidence=0.6)
        )
        return Decision(event.type, Disposition.notified, "Inbound message surfaced.")

    def _on_system(self, event: Event) -> Decision:
        return Decision(event.type, Disposition.ignored, "System heartbeat.")
