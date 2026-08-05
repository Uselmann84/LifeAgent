"""Mock email provider backed by seeded EmailMessage rows. Fully offline, read-only."""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.models import EmailMessage


class MockEmailProvider:
    name = "mock"

    def __init__(self, session: Session) -> None:
        self._session = session

    def read_only(self) -> bool:
        return True

    def list_threads(self) -> list[str]:
        rows = self._session.exec(select(EmailMessage)).all()
        return sorted({m.thread_id for m in rows})

    def get_thread(self, thread_id: str) -> list[EmailMessage]:
        stmt = (
            select(EmailMessage)
            .where(EmailMessage.thread_id == thread_id)
            .order_by(EmailMessage.received_at)
        )
        return list(self._session.exec(stmt).all())

    def search(self, query: str) -> list[EmailMessage]:
        q = (query or "").lower()
        rows = self._session.exec(select(EmailMessage)).all()
        return [m for m in rows if q in m.subject.lower() or q in m.body.lower()]
