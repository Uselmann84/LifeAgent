"""End-to-end calendar-write approval flow (propose → persist approval → execute).

Real CalDAV writes are refused by the execution boundary in the test/simulation environment, so
these verify the approval binding and the simulated (no-side-effect) execution path.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.agent import tools
from app.autonomy.decision import DecisionEngine, Disposition
from app.autonomy.events import Event, EventType
from app.autonomy.memory import EphemeralMemoryManager
from app.autonomy.notifications import NotificationDispatcher
from app.core.config import Settings
from app.core.db import engine
from app.core.models import ApprovalRequest, ApprovalStatus


def _sim() -> Settings:
    return Settings(env="testing", mode="demo", execution_mode="simulation")


def _engine(session: Session) -> DecisionEngine:
    settings = _sim()
    return DecisionEngine(session, EphemeralMemoryManager(), NotificationDispatcher(settings=settings), settings)


def test_request_calendar_save_approval_creates_pending():
    with Session(engine) as session:
        approval = tools.request_calendar_save_approval(
            session,
            title="Flight check-in",
            start="2026-08-10T09:00:00",
            end=None,
            reason="from email",
        )
        assert approval.action_type == "save_approved_calendar_event"
        assert approval.status == ApprovalStatus.pending
        assert approval.payload == {"title": "Flight check-in", "start": "2026-08-10T09:00:00", "end": None}
        assert approval.payload_hash  # bound to the exact payload


def test_save_approved_calendar_event_is_simulated_off_backend_mac():
    with Session(engine) as session:
        approval = tools.request_calendar_save_approval(
            session, title="Show", start="2026-08-22T14:00:00", end="2026-08-22T21:00:00", reason="x"
        )
        approval.status = ApprovalStatus.approved
        session.add(approval)
        session.commit()
        session.refresh(approval)
        result = tools.save_approved_calendar_event(
            session, approval=approval, submitted_payload_hash=approval.payload_hash
        )
    # Boundary blocks the real write in simulation; no external effect, recorded as not created.
    assert result["created"] is False
    assert result["reason"] == "simulated"


def test_save_approved_calendar_event_rejects_wrong_hash():
    with Session(engine) as session:
        approval = tools.request_calendar_save_approval(
            session, title="Show", start="2026-08-22T14:00:00", end=None, reason="x"
        )
        approval.status = ApprovalStatus.approved
        session.add(approval)
        session.commit()
        session.refresh(approval)
        try:
            tools.save_approved_calendar_event(session, approval=approval, submitted_payload_hash="tampered")
        except Exception as exc:  # payload-binding failure must refuse execution
            assert "hash" in str(exc).lower() or "approval" in str(exc).lower()
        else:
            raise AssertionError("expected wrong-hash approval to be rejected")


def test_decision_persists_calendar_approval():
    with Session(engine) as session:
        before = len(session.exec(select(ApprovalRequest)).all())
        decision = _engine(session).decide(
            Event(
                type=EventType.email_received,
                source="email:sim",
                summary="Check in for your flight",
                payload={
                    "importance": "needs_action_today",
                    "sender": "airline@example.com",
                    "calendar_suggestion": {"title": "Flight check-in", "start": "2026-08-10T09:00:00", "end": None},
                },
            )
        )
        after = session.exec(select(ApprovalRequest)).all()
    assert decision.disposition is Disposition.approval_requested
    assert len(after) == before + 1
    # The decision carries the persisted approval id + payload hash for the Approval Center.
    assert decision.proposed_action_payload["approval_id"]
    assert decision.proposed_action_payload["payload_hash"]
