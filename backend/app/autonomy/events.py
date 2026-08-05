"""Unified event abstraction for autonomous triggers (Section 35.5).

All autonomous behavior is driven by :class:`Event` objects produced by :class:`EventSource`
implementations. Each source has a production variant (real API integration, Backend Mac only) and
a simulation variant (deterministic mock generator, safe on the Development Mac).

Content arriving from the outside world (email bodies, calendar invites) is *untrusted* and must be
marked as such so downstream code never treats it as instructions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from app.core.models import utcnow


class EventType(str, Enum):
    email_received = "email_received"
    email_classified = "email_classified"
    calendar_updated = "calendar_updated"
    task_changed = "task_changed"
    user_message = "user_message"
    system = "system"


@dataclass
class Event:
    """A normalized trigger flowing through the autonomous loop."""

    type: EventType
    source: str
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    # True when the payload contains content from outside the trust boundary.
    untrusted: bool = False
    occurred_at: datetime = field(default_factory=utcnow)


@runtime_checkable
class EventSource(Protocol):
    """Produces events. ``poll`` returns any events since the last call.

    Implementations are either production (real integrations, Backend Mac) or simulation
    (deterministic generators). A source declares which via :attr:`is_simulation`.
    """

    name: str
    is_simulation: bool

    def poll(self, limit: int) -> list[Event]: ...
