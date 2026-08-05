"""Concrete event sources with production and simulation variants (Section 35.5).

Production variants integrate real APIs and only function on the Backend Mac; until their phase
lands they raise clearly. Simulation variants generate deterministic, replayable events and never
touch real accounts, the production database, or external systems.
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.autonomy.events import Event, EventSource, EventType
from app.core.config import Settings
from app.core.models import EmailMessage, Task, TaskStatus, utcnow

# --------------------------------------------------------------------------- Gmail


class SimulatedGmailEventSource:
    """Replays seeded EmailMessage rows as inbound email events. Never touches real Gmail."""

    name = "gmail:sim"
    is_simulation = True

    def __init__(self, session: Session) -> None:
        self._session = session
        self._seen: set[str] = set()

    def poll(self, limit: int) -> list[Event]:
        rows = self._session.exec(select(EmailMessage)).all()
        events: list[Event] = []
        for m in rows:
            if m.id in self._seen:
                continue
            self._seen.add(m.id)
            events.append(
                Event(
                    type=EventType.email_received,
                    source=self.name,
                    summary=f"Email from {m.sender}: {m.subject}",
                    payload={
                        "email_id": m.id,
                        "sender": m.sender,
                        "subject": m.subject,
                        "importance": m.importance.value,
                        # Body is untrusted external content.
                        "body": m.body,
                    },
                    untrusted=True,
                )
            )
            if len(events) >= limit:
                break
        return events


class ProductionGmailEventSource:
    """Real Gmail integration (Backend Mac only). Implemented in Phase 2."""

    name = "gmail"
    is_simulation = False

    def __init__(self, session: Session) -> None:
        self._session = session

    def poll(self, limit: int) -> list[Event]:
        raise NotImplementedError(
            "Production Gmail integration lands in Phase 2 (OAuth on the Backend Mac)."
        )


# --------------------------------------------------------------------------- Calendar


class SimulatedCalendarEventSource:
    """Emits synthetic calendar-update events derived from upcoming case follow-ups."""

    name = "calendar:sim"
    is_simulation = True

    def __init__(self, session: Session) -> None:
        self._session = session
        self._emitted = False

    def poll(self, limit: int) -> list[Event]:
        if self._emitted:
            return []
        self._emitted = True
        soon = utcnow() + timedelta(days=1)
        return [
            Event(
                type=EventType.calendar_updated,
                source=self.name,
                summary="Upcoming: warranty follow-up reminder",
                payload={"title": "Warranty follow-up", "starts_at": soon.isoformat()},
            )
        ][:limit]


class ProductionCalendarEventSource:
    """Real EventKit/CalDAV integration (Backend Mac only). Implemented in Phase 3."""

    name = "calendar"
    is_simulation = False

    def __init__(self, session: Session) -> None:
        self._session = session

    def poll(self, limit: int) -> list[Event]:
        raise NotImplementedError("Production calendar integration lands in Phase 3.")


# --------------------------------------------------------------------------- Tasks


class TaskEventSource:
    """Emits task-changed events for tasks that became due. Same logic in both modes.

    Tasks are internal state (no external content), so this source is safe in simulation and
    production alike; ``is_simulation`` mirrors the host so logs are unambiguous.
    """

    name = "tasks"

    def __init__(self, session: Session, *, is_simulation: bool) -> None:
        self._session = session
        self.is_simulation = is_simulation
        self._seen: set[str] = set()

    def poll(self, limit: int) -> list[Event]:
        now = utcnow()
        stmt = select(Task).where(Task.status != TaskStatus.done)
        events: list[Event] = []
        for t in self._session.exec(stmt).all():
            if t.due_at is None or t.id in self._seen:
                continue
            due = t.due_at if t.due_at.tzinfo else t.due_at.replace(tzinfo=now.tzinfo)
            if due <= now:
                self._seen.add(t.id)
                events.append(
                    Event(
                        type=EventType.task_changed,
                        source=self.name,
                        summary=f"Task due: {t.title}",
                        payload={"task_id": t.id, "priority": t.priority.value},
                    )
                )
            if len(events) >= limit:
                break
        return events


# --------------------------------------------------------------------------- User messages


class SimulatedUserMessageEventSource:
    """Injectable queue of simulated user messages for testing proactive behavior."""

    name = "user:sim"
    is_simulation = True

    def __init__(self, session: Session) -> None:
        self._session = session
        self._queue: list[str] = []

    def enqueue(self, message: str) -> None:
        self._queue.append(message)

    def poll(self, limit: int) -> list[Event]:
        events = [
            Event(
                type=EventType.user_message,
                source=self.name,
                summary=f"User: {msg[:60]}",
                payload={"message": msg},
                untrusted=False,
            )
            for msg in self._queue[:limit]
        ]
        self._queue = self._queue[limit:]
        return events


class ProductionUserMessageEventSource:
    """Real user messages arrive via the API in production; this source stays empty.

    The continuous loop reacts to user messages through the request path, not by polling, so the
    production variant intentionally yields nothing.
    """

    name = "user"
    is_simulation = False

    def __init__(self, session: Session) -> None:
        self._session = session

    def poll(self, limit: int) -> list[Event]:
        return []


# --------------------------------------------------------------------------- System


class SystemEventSource:
    """Emits internal system heartbeats/health events. Safe in both modes."""

    name = "system"

    def __init__(self, *, is_simulation: bool) -> None:
        self.is_simulation = is_simulation
        self._ticks = 0

    def poll(self, limit: int) -> list[Event]:
        self._ticks += 1
        return [
            Event(
                type=EventType.system,
                source=self.name,
                summary=f"heartbeat #{self._ticks}",
                payload={"tick": self._ticks},
            )
        ][:limit]


def build_event_sources(session: Session, settings: Settings) -> list[EventSource]:
    """Assemble the event sources appropriate for the current execution mode."""
    sim = settings.is_simulation
    if sim:
        return [
            SimulatedGmailEventSource(session),
            SimulatedCalendarEventSource(session),
            TaskEventSource(session, is_simulation=True),
            SimulatedUserMessageEventSource(session),
            SystemEventSource(is_simulation=True),
        ]
    return [
        ProductionGmailEventSource(session),
        ProductionCalendarEventSource(session),
        TaskEventSource(session, is_simulation=False),
        ProductionUserMessageEventSource(session),
        SystemEventSource(is_simulation=False),
    ]
