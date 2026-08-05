"""Autonomous memory manager with execution-mode separation (Section 35.7).

* **Production (Backend Mac)** — persistent long-term memory stored in the database
  (:class:`MemoryItem`), reflecting real user-specific state, task/email/decision history.
* **Simulation (Development Mac)** — ephemeral, resettable, in-process memory seeded with synthetic
  profiles and holding no real user data.

Both variants expose the same interface so the decision engine and loop are mode-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from sqlmodel import Session, desc, select

from app.core.config import Settings, get_settings
from app.core.models import MemoryItem, utcnow


@dataclass
class MemoryRecord:
    kind: str
    content: str
    source: str | None = None
    confidence: float = 1.0


@runtime_checkable
class MemoryManager(Protocol):
    persistent: bool

    def remember(self, record: MemoryRecord) -> None: ...

    def recall(self, limit: int = 50) -> list[MemoryRecord]: ...

    def reset(self) -> None: ...


class PersistentMemoryManager:
    """Backend Mac: durable memory backed by the production database."""

    persistent = True

    def __init__(self, session: Session) -> None:
        self._session = session

    def remember(self, record: MemoryRecord) -> None:
        item = MemoryItem(
            kind=record.kind,
            content=record.content,
            source=record.source,
            confidence=record.confidence,
            inferred=True,
        )
        self._session.add(item)
        self._session.commit()

    def recall(self, limit: int = 50) -> list[MemoryRecord]:
        stmt = select(MemoryItem).order_by(desc(MemoryItem.learned_at)).limit(limit)
        return [
            MemoryRecord(kind=m.kind, content=m.content, source=m.source, confidence=m.confidence)
            for m in self._session.exec(stmt).all()
        ]

    def reset(self) -> None:  # pragma: no cover - guarded against in production
        raise RuntimeError("Refusing to reset persistent production memory.")


@dataclass
class EphemeralMemoryManager:
    """Development Mac: in-process memory with synthetic seed data; safe to reset."""

    persistent = False
    _records: list[MemoryRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.reset()

    def remember(self, record: MemoryRecord) -> None:
        self._records.append(record)

    def recall(self, limit: int = 50) -> list[MemoryRecord]:
        return list(reversed(self._records))[:limit]

    def reset(self) -> None:
        self._records = [
            MemoryRecord("preference", "Synthetic user prefers a formal tone.", source="seed"),
            MemoryRecord("fact", f"Simulation memory initialized at {utcnow().isoformat()}.",
                         source="seed"),
        ]


def build_memory_manager(session: Session, settings: Settings | None = None) -> MemoryManager:
    settings = settings or get_settings()
    if settings.is_production_execution:
        return PersistentMemoryManager(session)
    return EphemeralMemoryManager()
