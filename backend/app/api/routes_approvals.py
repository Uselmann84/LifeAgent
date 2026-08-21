"""Approval Center endpoints.

Approvals are bound to an exact payload hash. Approving requires submitting the same hash; any
change to the payload invalidates the approval. Execution is performed by trusted code, never by
the model. See docs/PERMISSION_MATRIX.md.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, desc, select

from app.agent import tools
from app.api.deps import get_session, require
from app.api.schemas import ApproveRequest, RejectRequest, ReviseRequest
from app.core import audit
from app.core.models import ApprovalRequest, ApprovalStatus, utcnow
from app.security import approval as policy

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


def _approval_dict(a: ApprovalRequest) -> dict:
    return {
        "id": a.id,
        "action_type": a.action_type,
        "reason": a.reason,
        "data_affected": a.data_affected,
        "payload": a.payload,
        "payload_hash": a.payload_hash,
        "risk_level": a.risk_level.value,
        "status": a.status.value,
        "expires_at": a.expires_at.isoformat() if a.expires_at else None,
        "case_id": a.case_id,
        "created_at": a.created_at.isoformat(),
    }


@router.get("", dependencies=[Depends(require("view_personal_data"))])
def list_approvals(status: str | None = None, session: Session = Depends(get_session)) -> dict:
    stmt = select(ApprovalRequest).order_by(desc(ApprovalRequest.created_at))
    if status:
        stmt = stmt.where(ApprovalRequest.status == status)
    rows = session.exec(stmt).all()
    # Reflect expiry lazily for display.
    for a in rows:
        if a.status == ApprovalStatus.pending and policy.is_expired(a):
            a.status = ApprovalStatus.expired
            session.add(a)
    session.commit()
    return {"items": [_approval_dict(a) for a in rows]}


@router.get("/{approval_id}", dependencies=[Depends(require("view_personal_data"))])
def get_approval(approval_id: str, session: Session = Depends(get_session)) -> dict:
    a = session.get(ApprovalRequest, approval_id)
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found")
    return _approval_dict(a)


@router.post("/{approval_id}/approve", dependencies=[Depends(require("approve_actions"))])
def approve(
    approval_id: str, body: ApproveRequest, session: Session = Depends(get_session)
) -> dict:
    a = session.get(ApprovalRequest, approval_id)
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found")

    if a.status == ApprovalStatus.invalidated:
        raise HTTPException(status_code=400, detail="Approval was invalidated (payload changed)")
    if a.status != ApprovalStatus.pending:
        raise HTTPException(status_code=409, detail=f"Approval is {a.status.value}")
    if policy.is_expired(a):
        a.status = ApprovalStatus.expired
        session.add(a)
        session.commit()
        raise HTTPException(status_code=409, detail="Approval has expired")

    # Binding check: the submitted hash must match the exact bound payload.
    if body.payload_hash != a.payload_hash:
        a.status = ApprovalStatus.invalidated
        session.add(a)
        session.commit()
        raise HTTPException(
            status_code=400,
            detail="Payload hash mismatch; approval invalidated. Re-review the action.",
        )

    a.status = ApprovalStatus.approved
    a.approved_by = "user"
    a.approved_at = utcnow()
    session.add(a)
    session.commit()
    session.refresh(a)

    # Execute through trusted code. In demo/dev, external side effects are disabled by feature flags.
    result: dict = {"executed": False}
    if a.action_type == "send_approved_email":
        result = tools.send_approved_email(session, approval=a, submitted_payload_hash=body.payload_hash)
    elif a.action_type == "send_approved_imessage":
        result = tools.send_approved_imessage(session, approval=a, submitted_payload_hash=body.payload_hash)
    elif a.action_type == "save_approved_calendar_event":
        result = tools.save_approved_calendar_event(session, approval=a, submitted_payload_hash=body.payload_hash)
    a.execution_result = str(result)
    session.add(a)
    session.commit()

    audit.record_action(
        session,
        planned_action=f"approve:{a.action_type}",
        tools_used=[a.action_type],
        inputs={"approval_id": a.id},
        outputs=result,
        reasoning_summary="User approved the action; executed through trusted code.",
        approval_id=a.id,
        success=bool(result.get("dispatched") or result.get("created")) if isinstance(result, dict) else None,
        reversible=False,
    )
    return {"status": a.status.value, "result": result}


@router.post("/{approval_id}/reject", dependencies=[Depends(require("approve_actions"))])
def reject(approval_id: str, body: RejectRequest, session: Session = Depends(get_session)) -> dict:
    a = session.get(ApprovalRequest, approval_id)
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found")
    a.status = ApprovalStatus.rejected
    a.execution_result = f"rejected: {body.reason or 'no reason given'}"
    session.add(a)
    session.commit()
    return {"status": a.status.value}


@router.post("/{approval_id}/revise", dependencies=[Depends(require("approve_actions"))])
def revise(approval_id: str, body: ReviseRequest, session: Session = Depends(get_session)) -> dict:
    a = session.get(ApprovalRequest, approval_id)
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found")
    a.status = ApprovalStatus.revise
    a.execution_result = f"revision requested: {body.instructions}"
    session.add(a)
    session.commit()
    return {"status": a.status.value, "note": "Agent will prepare a revised action for re-approval."}
