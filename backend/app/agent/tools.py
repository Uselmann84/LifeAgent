"""Typed agent tools.

Every agent capability is a typed tool with declared permission/approval/reversibility metadata.
The agent never calls provider SDKs directly — it calls these controlled tools, which enforce the
approval policy and write audit entries. See docs/PERMISSION_MATRIX.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlmodel import Session

from app.autonomy.execution import SideEffect, guard_side_effect, simulate_or_block
from app.core import audit
from app.core.config import get_settings
from app.core.models import (
    ApprovalRequest,
    ApprovalStatus,
    Case,
    Communication,
    MemoryItem,
    Task,
)
from app.security import approval as policy


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    requires_approval: bool
    reversible: bool
    idempotent: bool
    # Minimum runtime mode required to actually take the external effect.
    min_mode: str


# Registry describing every tool's policy metadata (surfaced to docs/tests/UI).
TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search_email": ToolSpec("search_email", "Natural-language email search", False, True, True, "readonly_personal"),
    "get_email_thread": ToolSpec("get_email_thread", "Fetch an email thread", False, True, True, "readonly_personal"),
    "classify_email": ToolSpec("classify_email", "Classify importance", False, True, True, "readonly_personal"),
    "draft_email": ToolSpec("draft_email", "Prepare an email draft (no send)", False, True, False, "demo"),
    "draft_sms": ToolSpec("draft_sms", "Prepare an SMS draft (no send)", False, True, False, "demo"),
    "create_task": ToolSpec("create_task", "Create an internal task", False, True, False, "demo"),
    "update_task": ToolSpec("update_task", "Update an internal task", False, True, True, "demo"),
    "create_case": ToolSpec("create_case", "Create an internal case", False, True, False, "demo"),
    "link_document_to_case": ToolSpec("link_document_to_case", "Link doc to case", False, True, True, "demo"),
    "create_calendar_event_draft": ToolSpec("create_calendar_event_draft", "Prepare event", False, True, False, "demo"),
    "save_approved_calendar_event": ToolSpec(
        "save_approved_calendar_event", "Write event", True, False, True, "controlled_action"
    ),
    "create_reminder": ToolSpec("create_reminder", "Create a reminder", True, True, True, "controlled_action"),
    "schedule_follow_up": ToolSpec("schedule_follow_up", "Schedule follow-up", False, True, True, "demo"),
    "get_waiting_items": ToolSpec(
        "get_waiting_items", "List who owes a response", False, True, True, "readonly_personal"
    ),
    "store_memory": ToolSpec("store_memory", "Store a personal memory", False, True, False, "demo"),
    "delete_memory": ToolSpec("delete_memory", "Delete a personal memory", False, True, True, "demo"),
    "request_email_send_approval": ToolSpec(
        "request_email_send_approval", "Create send approval", False, True, True, "demo"
    ),
    "send_approved_email": ToolSpec(
        "send_approved_email", "Send an approved email", True, False, True, "controlled_action"
    ),
    "move_email_to_spam": ToolSpec("move_email_to_spam", "Move email to spam", True, True, True, "controlled_action"),
}


class ToolError(Exception):
    pass


# --------------------------------------------------------------------------- internal tools
def create_task(session: Session, *, title: str, **fields: Any) -> Task:
    task = Task(title=title, **fields)
    session.add(task)
    session.commit()
    session.refresh(task)
    audit.record_action(
        session,
        planned_action="create_task",
        tools_used=["create_task"],
        inputs={"title": title},
        outputs={"task_id": task.id},
        reasoning_summary="Created an internal task; no external effect.",
        success=True,
        data_changed=[f"task:{task.id}"],
    )
    session.refresh(task)  # audit commit expires the instance; reload before returning
    return task


def create_case(session: Session, *, case_type: str, title: str, **fields: Any) -> Case:
    case = Case(case_type=case_type, title=title, **fields)
    session.add(case)
    session.commit()
    session.refresh(case)
    audit.record_action(
        session,
        planned_action="create_case",
        tools_used=["create_case"],
        inputs={"case_type": case_type, "title": title},
        outputs={"case_id": case.id},
        reasoning_summary="Created an internal case; no external effect.",
        success=True,
        data_changed=[f"case:{case.id}"],
    )
    session.refresh(case)  # audit commit expires the instance; reload before returning
    return case


def store_memory(session: Session, *, kind: str, content: str, **fields: Any) -> MemoryItem:
    item = MemoryItem(kind=kind, content=content, **fields)
    session.add(item)
    session.commit()
    session.refresh(item)
    audit.record_action(
        session,
        planned_action="store_memory",
        tools_used=["store_memory"],
        inputs={"kind": kind},
        reasoning_summary="Stored a user-inspectable memory item.",
        success=True,
        data_changed=[f"memory:{item.id}"],
    )
    session.refresh(item)  # audit commit expires the instance; reload before returning
    return item


def draft_email(
    session: Session, *, to: list[str], subject: str, body: str, case_id: str | None = None
) -> dict[str, Any]:
    """Prepare a draft. Never sends. Returns the exact payload the user will review."""
    payload = {"to": to, "subject": subject, "body": body}
    audit.record_action(
        session,
        planned_action="draft_email",
        tools_used=["draft_email"],
        inputs={"to": to, "subject": subject},
        reasoning_summary="Prepared an email draft for user review; nothing sent.",
        success=True,
    )
    return {"draft": payload, "case_id": case_id, "sent": False}


# --------------------------------------------------------------------------- approval-bound tools
def request_email_send_approval(
    session: Session,
    *,
    to: list[str],
    subject: str,
    body: str,
    reason: str,
    recipient_trusted: bool = True,
    case_id: str | None = None,
    attachments: list[str] | None = None,
    autonomy_level: int | None = None,
) -> ApprovalRequest:
    """Create an approval request bound to the exact email payload."""
    settings = get_settings()
    level = autonomy_level if autonomy_level is not None else settings.default_autonomy_level
    payload = {
        "to": sorted(to),
        "subject": subject,
        "body": body,
        "attachments": sorted(attachments or []),
    }
    decision = policy.evaluate(
        "send_approved_email",
        autonomy_level=level,
        payload=payload,
        recipient_trusted=recipient_trusted,
    )
    payload_hash = policy.compute_payload_hash(payload)
    approval = ApprovalRequest(
        action_type="send_approved_email",
        reason=reason,
        data_affected=f"email to {', '.join(to)}",
        payload=payload,
        payload_hash=payload_hash,
        risk_level=decision.risk_level,
        status=ApprovalStatus.pending,
        expires_at=policy.new_approval_ttl(),
        case_id=case_id,
    )
    session.add(approval)
    session.commit()
    session.refresh(approval)
    audit.record_action(
        session,
        planned_action="request_email_send_approval",
        tools_used=["request_email_send_approval"],
        inputs={"to": to, "subject": subject},
        outputs={"approval_id": approval.id, "payload_hash": payload_hash},
        reasoning_summary="Prepared a send action; awaiting explicit user approval.",
        approval_id=approval.id,
        success=True,
    )
    session.refresh(approval)  # audit commit expires the instance; reload before returning
    return approval


def send_approved_email(
    session: Session, *, approval: ApprovalRequest, submitted_payload_hash: str
) -> dict[str, Any]:
    """Execute a send ONLY with a valid, unexpired, payload-matched approval.

    Real sending crosses the execution boundary (Section 35.8): it is refused entirely outside a
    fully authorized Backend Mac. In simulation the intent is recorded with no external effect.
    Never marks success before an external confirmation would be received.
    """
    # Trusted code re-validates the approval and payload binding.
    policy.validate_approval(approval, submitted_payload_hash)

    if simulate_or_block(SideEffect.send_email):
        audit.record_action(
            session,
            planned_action="send_approved_email",
            tools_used=["send_approved_email"],
            inputs={"to": approval.payload.get("to")},
            outputs={"dispatched": False, "reason": "simulated (execution boundary)"},
            reasoning_summary="Approval valid, but real sending is not permitted in this mode.",
            approval_id=approval.id,
            success=None,
            reversible=False,
        )
        return {"dispatched": False, "reason": "simulated", "approval_id": approval.id}

    # Backend Mac, production execution, controlled-action mode, flag enabled.
    guard_side_effect(SideEffect.send_email)
    # Phase 4 will call the email provider here with an idempotency key and record the provider
    # message id before marking success.
    raise ToolError("Real email sending is not implemented until Phase 4.")


def move_email_to_spam(session: Session, *, message_id: str) -> dict[str, Any]:
    """Conservative, recoverable spam move. Feature-flagged; never permanent auto-delete."""
    if simulate_or_block(SideEffect.move_email):
        return {"moved": False, "reason": "simulated (execution boundary)", "message_id": message_id}
    guard_side_effect(SideEffect.move_email)
    raise ToolError("Real spam move is not implemented until Phase 4.")


def schedule_follow_up(
    session: Session, *, summary: str, follow_up_at: datetime, case_id: str | None = None
) -> Communication:
    comm = Communication(
        channel="in_app",
        summary=summary,
        follow_up_required=True,
        follow_up_at=follow_up_at,
        case_id=case_id,
    )
    session.add(comm)
    session.commit()
    session.refresh(comm)
    return comm
