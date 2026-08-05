"""Today briefing, waiting-for, activity log, and memory endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, desc, select

from app.api.deps import get_session, require
from app.api.schemas import MemoryCreate
from app.core import audit
from app.core.models import (
    ApprovalRequest,
    ApprovalStatus,
    Case,
    CaseStatus,
    EmailMessage,
    ImportanceCategory,
    MemoryItem,
    Priority,
    Task,
    TaskStatus,
)

router = APIRouter(prefix="/api/v1", tags=["today"])


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


@router.get("/today", dependencies=[Depends(require("view_personal_data"))])
def today(session: Session = Depends(get_session)) -> dict:
    now = datetime.now(UTC)

    open_tasks = session.exec(
        select(Task).where(Task.status.in_([TaskStatus.open, TaskStatus.in_progress]))
    ).all()
    priorities = [
        {"id": t.id, "title": t.title, "priority": t.priority.value, "due_at": _iso(t.due_at)}
        for t in open_tasks
        if t.priority in (Priority.high, Priority.urgent)
    ][:3]

    deadlines = sorted(
        [
            {"id": t.id, "title": t.title, "due_at": _iso(t.due_at)}
            for t in open_tasks
            if t.due_at is not None
        ],
        key=lambda d: d["due_at"] or "",
    )

    important = session.exec(
        select(EmailMessage).where(
            EmailMessage.importance.in_(
                [
                    ImportanceCategory.critical,
                    ImportanceCategory.needs_action_today,
                    ImportanceCategory.needs_action_soon,
                ]
            )
        )
    ).all()
    important_email = [
        {
            "id": m.id,
            "subject": m.subject,
            "sender": m.sender,
            "why_it_matters": m.why_it_matters,
            "requested_action": m.requested_action,
            "deadline_at": _iso(m.deadline_at),
            "importance": m.importance.value,
            "confidence": m.confidence,
        }
        for m in important
    ]

    waiting = session.exec(
        select(EmailMessage).where(
            EmailMessage.importance == ImportanceCategory.waiting_for_response
        )
    ).all()
    waiting_for = [
        {
            "id": m.id,
            "subject": m.subject,
            "awaiting_response_from": m.awaiting_response_from or m.sender,
        }
        for m in waiting
    ]

    pending = session.exec(
        select(ApprovalRequest).where(ApprovalRequest.status == ApprovalStatus.pending)
    ).all()
    pending_approvals = [
        {
            "id": a.id,
            "action_type": a.action_type,
            "reason": a.reason,
            "risk_level": a.risk_level.value,
            "expires_at": _iso(a.expires_at),
        }
        for a in pending
    ]

    at_risk = session.exec(select(Case).where(Case.status == CaseStatus.at_risk)).all()

    suggested = []
    if waiting_for:
        suggested.append("Send follow-ups for items awaiting a response.")
    if pending_approvals:
        suggested.append("Review pending approvals.")
    if not suggested:
        suggested.append("Ask the agent what needs attention today.")

    low_priority = [
        {"id": m.id, "subject": m.subject}
        for m in session.exec(
            select(EmailMessage).where(
                EmailMessage.importance.in_(
                    [
                        ImportanceCategory.newsletter,
                        ImportanceCategory.promotion,
                        ImportanceCategory.informational,
                    ]
                )
            )
        ).all()
    ]

    return {
        "generated_at": now.isoformat(),
        "top_priorities": priorities,
        "deadlines": deadlines,
        "important_email": important_email,
        "waiting_for": waiting_for,
        "appointments": [],
        "pending_approvals": pending_approvals,
        "cases_at_risk": [{"id": c.id, "title": c.title} for c in at_risk],
        "suggested_actions": suggested,
        "collapsed_low_priority": low_priority,
    }


@router.get("/waiting", dependencies=[Depends(require("view_personal_data"))])
def waiting(session: Session = Depends(get_session)) -> dict:
    rows = session.exec(
        select(EmailMessage).where(
            EmailMessage.importance == ImportanceCategory.waiting_for_response
        )
    ).all()
    return {
        "items": [
            {
                "id": m.id,
                "subject": m.subject,
                "awaiting_response_from": m.awaiting_response_from or m.sender,
                "since": _iso(m.received_at),
            }
            for m in rows
        ]
    }


@router.get("/activity", dependencies=[Depends(require("view_personal_data"))])
def activity(limit: int = 50, offset: int = 0, session: Session = Depends(get_session)) -> dict:
    entries = audit.recent_actions(session, limit=limit, offset=offset)
    return {
        "items": [
            {
                "id": e.id,
                "planned_action": e.planned_action,
                "tools_used": e.tools_used,
                "reasoning_summary": e.reasoning_summary,
                "success": e.success,
                "reversible": e.reversible,
                "data_changed": e.data_changed,
                "created_at": _iso(e.created_at),
            }
            for e in entries
        ]
    }


@router.get("/memory", dependencies=[Depends(require("view_personal_data"))])
def list_memory(session: Session = Depends(get_session)) -> dict:
    rows = session.exec(select(MemoryItem).order_by(desc(MemoryItem.learned_at))).all()
    return {
        "items": [
            {
                "id": m.id,
                "kind": m.kind,
                "content": m.content,
                "sensitivity": m.sensitivity,
                "inferred": m.inferred,
                "source": m.source,
                "learned_at": _iso(m.learned_at),
                "expires_at": _iso(m.expires_at),
            }
            for m in rows
        ]
    }


@router.post("/memory", dependencies=[Depends(require("change_user_rules"))])
def create_memory(body: MemoryCreate, session: Session = Depends(get_session)) -> dict:
    item = MemoryItem(
        kind=body.kind,
        content=body.content,
        sensitivity=body.sensitivity,
        inferred=body.inferred,
        expires_at=body.expires_at,
        source="user",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"id": item.id}


@router.delete("/memory/{item_id}", dependencies=[Depends(require("change_user_rules"))])
def delete_memory(item_id: str, session: Session = Depends(get_session)) -> dict:
    item = session.get(MemoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Memory item not found")
    session.delete(item)
    session.commit()
    return {"deleted": item_id}
