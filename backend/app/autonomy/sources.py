"""Concrete event sources with production and simulation variants (Section 35.5).

Production variants integrate the user's real accounts and only function on the Backend Mac:

* email    → mail.com over IMAP (``app.integrations.email.imap``), with attachments downloaded and
  understood by the document pipeline (``app.documents.pipeline``),
* calendar → Apple Calendar / iCloud over CalDAV (``app.integrations.calendar.icloud``),
* messages → iMessage from the local Messages store (``app.integrations.imessage``).

Each production source is additionally gated by its feature flag and fails soft (returns no events)
when the integration is disabled or unavailable, so the loop never crashes. Simulation variants
generate deterministic, replayable events and never touch real accounts or external systems.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlmodel import Session, select

from app.autonomy.events import Event, EventSource, EventType
from app.core.config import Settings
from app.core.models import EmailMessage, ImportanceCategory, Task, TaskStatus, utcnow

logger = logging.getLogger("lifeagent.autonomy.sources")

# --------------------------------------------------------------------------- Email


class SimulatedEmailEventSource:
    """Replays seeded EmailMessage rows as inbound email events. Never touches a real mailbox."""

    name = "email:sim"
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
                        "attachments": [],
                    },
                    untrusted=True,
                )
            )
            if len(events) >= limit:
                break
        return events


class ProductionImapEmailEventSource:
    """Real mail.com/IMAP inbox (Backend Mac only), with attachment understanding."""

    name = "email"
    is_simulation = False

    def __init__(self, session: Session) -> None:
        self._session = session
        self._seen: set[str] = set()

    def poll(self, limit: int) -> list[Event]:
        # Lazy imports keep the base app free of integration internals.
        from app.agent.importance import classify_email_importance
        from app.autonomy.router import get_router
        from app.core.config import get_settings
        from app.documents.pipeline import DocumentProcessor
        from app.integrations.email.imap import EmailSyncDisabled, ImapEmailClient

        client = ImapEmailClient()
        try:
            fetched = client.fetch_recent(limit=limit)
        except EmailSyncDisabled as exc:
            logger.info("email source disabled: %s", exc)
            return []
        except Exception:  # pragma: no cover - provider/network errors must not crash the loop
            logger.exception("IMAP fetch failed")
            return []

        settings = get_settings()
        process_docs = settings.feature_process_documents
        processor = DocumentProcessor(self._session, settings)
        router = get_router(settings)
        events: list[Event] = []
        for msg in fetched:
            if msg.uid in self._seen:
                continue
            self._seen.add(msg.uid)
            attachments = []
            if process_docs:
                for att in msg.attachments:
                    try:
                        analysis = processor.analyze(
                            att.data, att.filename, att.content_type, source=f"email:{msg.uid}"
                        )
                        attachments.append(
                            {
                                "filename": analysis.filename,
                                "doc_type": analysis.doc_type,
                                "summary": analysis.summary,
                                "needs_vision": analysis.needs_vision,
                                "document_id": analysis.stored_document_id,
                            }
                        )
                    except Exception:  # pragma: no cover
                        logger.exception("attachment processing failed: %s", att.filename)

            attachment_note = "; ".join(
                f"{a['filename']}: {a['summary']}" for a in attachments if a.get("summary")
            )
            try:
                importance, why = classify_email_importance(
                    router,
                    sender=msg.sender,
                    subject=msg.subject,
                    body=msg.body,
                    attachment_note=attachment_note,
                )
            except Exception:  # pragma: no cover - classifier/model errors must not crash the loop
                logger.exception("importance classification failed: %s", msg.uid)
                importance, why = ImportanceCategory.informational, ""

            events.append(
                Event(
                    type=EventType.email_received,
                    source=self.name,
                    summary=f"Email from {msg.sender}: {msg.subject}",
                    payload={
                        "email_id": msg.uid,
                        "sender": msg.sender,
                        "subject": msg.subject,
                        "importance": importance.value,
                        "why_it_matters": why,
                        # Body and attachment text are untrusted external content.
                        "body": msg.body,
                        "attachments": attachments,
                    },
                    untrusted=True,
                )
            )
        return events


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


class ProductionICloudCalendarEventSource:
    """Real Apple Calendar (iCloud/CalDAV) upcoming events (Backend Mac only)."""

    name = "calendar"
    is_simulation = False

    def __init__(self, session: Session) -> None:
        self._session = session
        self._seen: set[str] = set()

    def poll(self, limit: int) -> list[Event]:
        from app.integrations.calendar.icloud import CalendarDisabled, ICloudCalendarClient

        client = ICloudCalendarClient()
        try:
            upcoming = client.upcoming(days=7)
        except CalendarDisabled as exc:
            logger.info("calendar source disabled: %s", exc)
            return []
        except Exception:  # pragma: no cover
            logger.exception("CalDAV fetch failed")
            return []

        events: list[Event] = []
        for ev in upcoming:
            if ev.uid in self._seen:
                continue
            self._seen.add(ev.uid)
            events.append(
                Event(
                    type=EventType.calendar_updated,
                    source=self.name,
                    summary=f"Upcoming: {ev.title}",
                    payload={
                        "uid": ev.uid,
                        "title": ev.title,
                        "starts_at": ev.start.isoformat(),
                        "location": ev.location,
                    },
                )
            )
            if len(events) >= limit:
                break
        return events


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


# --------------------------------------------------------------------------- iMessage


class SimulatedIMessageEventSource:
    """Injectable queue of simulated inbound iMessages for testing proactive behavior."""

    name = "imessage:sim"
    is_simulation = True

    def __init__(self, session: Session) -> None:
        self._session = session
        self._queue: list[tuple[str, str]] = []

    def enqueue(self, handle: str, text: str) -> None:
        self._queue.append((handle, text))

    def poll(self, limit: int) -> list[Event]:
        events = [
            Event(
                type=EventType.message_received,
                source=self.name,
                summary=f"iMessage from {handle}",
                payload={"handle": handle, "text": text},
                untrusted=True,
            )
            for handle, text in self._queue[:limit]
        ]
        self._queue = self._queue[limit:]
        return events


class ProductionIMessageEventSource:
    """Real inbound iMessages from the local Messages store (Backend Mac only)."""

    name = "imessage"
    is_simulation = False

    def __init__(self, session: Session) -> None:
        self._session = session
        self._seen: set[int] = set()

    def poll(self, limit: int) -> list[Event]:
        from app.integrations.imessage import IMessageDisabled, IMessageReader

        reader = IMessageReader()
        try:
            recent = reader.recent(limit=limit)
        except IMessageDisabled as exc:
            logger.info("imessage source disabled: %s", exc)
            return []
        except Exception:  # pragma: no cover
            logger.exception("iMessage read failed")
            return []

        events: list[Event] = []
        for rec in recent:
            if rec.rowid in self._seen or rec.is_from_me or not rec.text:
                continue
            self._seen.add(rec.rowid)
            events.append(
                Event(
                    type=EventType.message_received,
                    source=self.name,
                    summary=f"iMessage from {rec.handle}",
                    payload={"handle": rec.handle, "text": rec.text},
                    untrusted=True,
                )
            )
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
    if settings.is_simulation:
        return [
            SimulatedEmailEventSource(session),
            SimulatedCalendarEventSource(session),
            TaskEventSource(session, is_simulation=True),
            SimulatedIMessageEventSource(session),
            SimulatedUserMessageEventSource(session),
            SystemEventSource(is_simulation=True),
        ]
    return [
        ProductionImapEmailEventSource(session),
        ProductionICloudCalendarEventSource(session),
        TaskEventSource(session, is_simulation=False),
        ProductionIMessageEventSource(session),
        ProductionUserMessageEventSource(session),
        SystemEventSource(is_simulation=False),
    ]
