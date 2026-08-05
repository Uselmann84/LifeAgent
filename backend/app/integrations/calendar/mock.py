"""Calendar provider abstraction + mock.

On iOS the real integration uses EventKit. In Phase 1 the backend only prepares *drafts*; writes
are approval-gated and feature-flagged. This mock records draft events in memory for development.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass
class CalendarEventDraft:
    title: str
    start: datetime
    end: datetime
    notes: str | None = None
    case_id: str | None = None


@runtime_checkable
class CalendarProvider(Protocol):
    name: str

    def prepare_event(self, draft: CalendarEventDraft) -> CalendarEventDraft: ...

    def read_only(self) -> bool: ...


class MockCalendarProvider:
    name = "mock"

    def __init__(self) -> None:
        self.drafts: list[CalendarEventDraft] = []

    def read_only(self) -> bool:
        return True

    def prepare_event(self, draft: CalendarEventDraft) -> CalendarEventDraft:
        self.drafts.append(draft)
        return draft
