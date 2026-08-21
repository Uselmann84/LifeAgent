"""Apple Calendar (iCloud) integration over CalDAV (Backend Mac only).

Reading upcoming events is read-only. Creating events is a real-world side effect and must pass the
execution boundary (:func:`guard_side_effect`). Authentication uses your Apple ID plus an
**app-specific password** (from appleid.apple.com), injected from the Keychain on the Backend Mac.

The ``caldav``/``icalendar`` libraries are optional (install ``.[integrations]``) and imported
lazily so the base app and test suite do not require them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.autonomy.execution import SideEffect, guard_side_effect
from app.core.config import Settings, get_settings


class CalendarDisabled(RuntimeError):
    """Raised when a real calendar operation is attempted outside the authorized Backend Mac."""


@dataclass
class CalendarEvent:
    uid: str
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    notes: str | None = None


@dataclass
class NewCalendarEvent:
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    notes: str | None = None
    attendees: list[str] = field(default_factory=list)


class ICloudCalendarClient:
    name = "icloud_caldav"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def _ensure_readable(self) -> None:
        s = self._settings
        if not s.is_production_execution:
            raise CalendarDisabled(
                "Real calendar access is only allowed on the Backend Mac "
                "(execution_mode=production). The Development Mac uses the simulated source."
            )
        if not (s.apple_id and s.apple_app_password):
            raise CalendarDisabled("iCloud credentials are not configured (Keychain not loaded?).")

    def _principal(self):
        # Lazy import so the base install/tests do not require the caldav package.
        try:
            import caldav
        except ImportError as exc:  # pragma: no cover - only on Backend Mac without extras
            raise CalendarDisabled(
                "The 'caldav' package is not installed. Install with: pip install '.[integrations]'"
            ) from exc
        s = self._settings
        client = caldav.DAVClient(
            url=s.caldav_url, username=s.apple_id, password=s.apple_app_password
        )
        return client.principal()

    def _select_calendar(self, principal):
        s = self._settings
        calendars = principal.calendars()
        if not calendars:
            raise CalendarDisabled("No iCloud calendars found for this account.")
        if s.icloud_calendar_name:
            for cal in calendars:
                if (cal.name or "") == s.icloud_calendar_name:
                    return cal
        return calendars[0]

    def upcoming(self, days: int = 7) -> list[CalendarEvent]:
        """Return events between now and ``days`` ahead. Read-only."""
        self._ensure_readable()
        principal = self._principal()
        cal = self._select_calendar(principal)
        start = datetime.now().astimezone()
        end = start + timedelta(days=days)
        events: list[CalendarEvent] = []
        for ev in cal.search(start=start, end=end, event=True, expand=True):
            events.append(_to_event(ev))
        return events

    def create_event(self, new_event: NewCalendarEvent) -> CalendarEvent:
        """Create a real calendar event. Refused by the boundary unless fully authorized."""
        guard_side_effect(SideEffect.modify_calendar, self._settings)
        self._ensure_readable()
        try:
            from icalendar import Calendar as ICalendar
            from icalendar import Event as IEvent
        except ImportError as exc:  # pragma: no cover
            raise CalendarDisabled(
                "The 'icalendar' package is not installed. Install with: pip install '.[integrations]'"
            ) from exc
        principal = self._principal()
        cal = self._select_calendar(principal)

        vcal = ICalendar()
        vcal.add("prodid", "-//Life Agent//iCloud//EN")
        vcal.add("version", "2.0")
        vevent = IEvent()
        # iCloud rejects events without a UID/DTSTAMP; RFC 5545 requires both.
        vevent.add("uid", f"{uuid.uuid4()}@life-agent")
        vevent.add("dtstamp", datetime.now(tz=UTC))
        vevent.add("summary", new_event.title)
        vevent.add("dtstart", new_event.start)
        vevent.add("dtend", new_event.end)
        if new_event.location:
            vevent.add("location", new_event.location)
        if new_event.notes:
            vevent.add("description", new_event.notes)
        vcal.add_component(vevent)

        created = cal.save_event(vcal.to_ical().decode("utf-8"))
        return _to_event(created)


def _to_event(dav_event) -> CalendarEvent:
    """Best-effort mapping from a caldav event object to our dataclass."""
    comp = dav_event.icalendar_component
    start = comp.get("dtstart").dt if comp.get("dtstart") else datetime.now().astimezone()
    end = comp.get("dtend").dt if comp.get("dtend") else start
    return CalendarEvent(
        uid=str(comp.get("uid", "")),
        title=str(comp.get("summary", "")),
        start=start if isinstance(start, datetime) else datetime.now().astimezone(),
        end=end if isinstance(end, datetime) else start,
        location=str(comp.get("location")) if comp.get("location") else None,
        notes=str(comp.get("description")) if comp.get("description") else None,
    )
