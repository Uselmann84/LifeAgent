"""In-memory background jobs for inbox cleanup scans.

A scan can take longer than a mobile request timeout, so it runs on a daemon thread on the Backend
Mac and keeps going even if the phone app is backgrounded or closed. The phone polls for status and
partial results and can resume polling on relaunch using the persisted job id. Jobs live in memory
for the life of the backend process (they do not survive a restart).
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from app.agent.cleanup import SenderGroup, scan_senders
from app.integrations.email.imap import EmailSyncDisabled

_CATEGORY_ORDER = {"spam": 0, "advertising": 1, "keep": 2}
_MAX_JOBS = 20
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


class _ScanCancelled(Exception):
    """Raised inside a job's callbacks when the user requests a stop."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _group_to_dict(g: SenderGroup) -> dict:
    return {
        "sender": g.sender,
        "sender_name": g.sender_name,
        "count": g.count,
        "sample_subjects": g.sample_subjects,
        "latest_at": g.latest_at.isoformat() if g.latest_at else None,
        "category": g.category,
        "reason": g.reason,
    }


def _sorted_items(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda d: (_CATEGORY_ORDER.get(d["category"], 3), -d["count"]))


def start_scan(*, since: datetime, before: datetime) -> str:
    job_id = uuid.uuid4().hex
    with _LOCK:
        _prune_locked()
        _JOBS[job_id] = {
            "id": job_id,
            "status": "running",
            "phase": "fetching",
            "processed": 0,
            "total": 0,
            "items": [],
            "error": None,
            "cancel": False,
            "since": since.date().isoformat(),
            "before": before.date().isoformat(),
            "started_at": _now(),
            "updated_at": _now(),
        }
    threading.Thread(target=_run, args=(job_id, since, before), daemon=True).start()
    return job_id


def _run(job_id: str, since: datetime, before: datetime) -> None:
    def _check_cancelled() -> None:
        with _LOCK:
            job = _JOBS.get(job_id)
            if job is not None and job.get("cancel"):
                raise _ScanCancelled

    def on_progress(done: int, total: int) -> None:
        _check_cancelled()
        with _LOCK:
            job = _JOBS.get(job_id)
            if job is None:
                return
            job["processed"] = done
            job["total"] = total
            job["phase"] = "classifying" if total else "fetching"
            job["updated_at"] = _now()

    def on_group(g: SenderGroup) -> None:
        _check_cancelled()
        with _LOCK:
            job = _JOBS.get(job_id)
            if job is None:
                return
            job["items"].append(_group_to_dict(g))
            job["updated_at"] = _now()

    try:
        scan_senders(since=since, before=before, on_group=on_group, on_progress=on_progress)
        _finish(job_id, status="done")
    except _ScanCancelled:
        _finish(job_id, status="cancelled")
    except EmailSyncDisabled as exc:
        _finish(job_id, status="error", error=str(exc))
    except Exception as exc:  # surface any failure to the phone rather than dying silently
        _finish(job_id, status="error", error=f"{type(exc).__name__}: {exc}")


def _finish(job_id: str, *, status: str, error: str | None = None) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return
        job["status"] = status
        job["error"] = error
        if status == "done":
            job["phase"] = "done"
            job["processed"] = job.get("total", 0)
        elif status == "cancelled":
            job["phase"] = "cancelled"
        job["items"] = _sorted_items(job["items"])
        job["updated_at"] = _now()


def get_job(job_id: str) -> dict | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        snapshot = dict(job)
        snapshot["items"] = _sorted_items(job["items"])
        return snapshot


def cancel_scan(job_id: str) -> bool:
    """Ask a running job to stop. Returns False if the job is unknown.

    Cancellation is cooperative: the worker stops at the next classified sender. A blocking IMAP
    fetch already in progress finishes first, then the job ends as 'cancelled' with partial results.
    """
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return False
        if job["status"] == "running":
            job["cancel"] = True
            job["updated_at"] = _now()
        return True


def _prune_locked() -> None:
    if len(_JOBS) <= _MAX_JOBS:
        return
    oldest = sorted(_JOBS, key=lambda k: _JOBS[k]["started_at"])[: len(_JOBS) - _MAX_JOBS]
    for jid in oldest:
        _JOBS.pop(jid, None)
