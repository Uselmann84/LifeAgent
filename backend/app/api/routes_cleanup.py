"""Bulk inbox cleanup: scan senders and request permanent deletion (approval-gated).

Scanning is read-only IMAP (Backend Mac only). Deletion is permanent and irreversible, so it never
happens here — this endpoint only creates a payload-bound approval that the user must explicitly
confirm in the Approval Center, after which trusted code executes it behind the feature flag.
"""

from __future__ import annotations

from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.agent import cleanup_jobs, tools
from app.api.deps import get_session, require
from app.api.schemas import CleanupDeleteRequest, CleanupScanRequest

router = APIRouter(prefix="/api/v1/email/cleanup", tags=["email-cleanup"])


def _to_dt(d) -> datetime:
    return datetime.combine(d, time.min)


@router.post("/scan", dependencies=[Depends(require("use_integrations"))])
def scan(body: CleanupScanRequest) -> dict:
    """Start a background scan and return its job id. Poll GET /scan/{job_id} for progress.

    The scan keeps running on the backend even if the phone app is closed, so it never blocks on a
    mobile request timeout and streams partial results as senders are classified.
    """
    if body.before <= body.since:
        raise HTTPException(status_code=400, detail="'before' must be after 'since'")
    job_id = cleanup_jobs.start_scan(since=_to_dt(body.since), before=_to_dt(body.before))
    return {"job_id": job_id, "status": "running"}


@router.get("/scan/{job_id}", dependencies=[Depends(require("use_integrations"))])
def scan_status(job_id: str) -> dict:
    job = cleanup_jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown scan job")
    return {
        "job_id": job["id"],
        "status": job["status"],
        "phase": job["phase"],
        "processed": job["processed"],
        "total": job["total"],
        "error": job["error"],
        "items": job["items"],
    }


@router.post("/scan/{job_id}/cancel", dependencies=[Depends(require("use_integrations"))])
def cancel_scan(job_id: str) -> dict:
    if not cleanup_jobs.cancel_scan(job_id):
        raise HTTPException(status_code=404, detail="Unknown scan job")
    return {"job_id": job_id, "status": "cancelling"}


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
