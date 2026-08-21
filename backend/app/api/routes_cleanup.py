"""Bulk inbox cleanup: scan senders and request permanent deletion (approval-gated).

Scanning is read-only IMAP (Backend Mac only). Deletion is permanent and irreversible, so it never
happens here — this endpoint only creates a payload-bound approval that the user must explicitly
confirm in the Approval Center, after which trusted code executes it behind the feature flag.
"""

from __future__ import annotations

from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.agent import cleanup, tools
from app.api.deps import get_session, require
from app.api.schemas import CleanupDeleteRequest, CleanupScanRequest
from app.integrations.email.imap import EmailSyncDisabled

router = APIRouter(prefix="/api/v1/email/cleanup", tags=["email-cleanup"])


def _to_dt(d) -> datetime:
    return datetime.combine(d, time.min)


@router.post("/scan", dependencies=[Depends(require("use_integrations"))])
def scan(body: CleanupScanRequest) -> dict:
    if body.before <= body.since:
        raise HTTPException(status_code=400, detail="'before' must be after 'since'")
    try:
        groups = cleanup.scan_senders(since=_to_dt(body.since), before=_to_dt(body.before))
    except EmailSyncDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {
        "items": [
            {
                "sender": g.sender,
                "sender_name": g.sender_name,
                "count": g.count,
                "sample_subjects": g.sample_subjects,
                "latest_at": g.latest_at.isoformat() if g.latest_at else None,
                "category": g.category,
                "reason": g.reason,
            }
            for g in groups
        ]
    }


@router.post("/request-delete", dependencies=[Depends(require("approve_actions"))])
def request_delete(body: CleanupDeleteRequest, session: Session = Depends(get_session)) -> dict:
    if not body.senders:
        raise HTTPException(status_code=400, detail="No senders selected")
    if body.before <= body.since:
        raise HTTPException(status_code=400, detail="'before' must be after 'since'")
    reason = body.reason or f"Permanently delete mail from {len(body.senders)} sender(s)."
    approval = tools.request_email_cleanup_approval(
        session,
        senders=body.senders,
        since=body.since.isoformat(),
        before=body.before.isoformat(),
        reason=reason,
    )
    return {
        "id": approval.id,
        "action_type": approval.action_type,
        "reason": approval.reason,
        "data_affected": approval.data_affected,
        "payload_hash": approval.payload_hash,
        "risk_level": approval.risk_level.value,
        "status": approval.status.value,
    }
