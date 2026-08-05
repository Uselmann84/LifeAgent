"""Audit logging: append user-readable, redacted AgentAction entries.

Stores a concise decision summary and structured evidence — never private chain-of-thought.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, desc, select

from app.core.models import AgentAction
from app.security.redaction import redact_mapping


def record_action(
    session: Session,
    *,
    planned_action: str,
    tools_used: list[str] | None = None,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    reasoning_summary: str | None = None,
    approval_id: str | None = None,
    success: bool | None = None,
    reversible: bool = True,
    account_affected: str | None = None,
    data_read: list[str] | None = None,
    data_changed: list[str] | None = None,
    external_confirmation_id: str | None = None,
    correlation_id: str | None = None,
) -> AgentAction:
    entry = AgentAction(
        planned_action=planned_action,
        tools_used=tools_used or [],
        inputs_redacted=redact_mapping(inputs or {}),
        outputs_redacted=redact_mapping(outputs or {}),
        reasoning_summary=reasoning_summary,
        approval_id=approval_id,
        success=success,
        reversible=reversible,
        account_affected=account_affected,
        data_read=data_read or [],
        data_changed=data_changed or [],
        external_confirmation_id=external_confirmation_id,
        correlation_id=correlation_id,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def recent_actions(session: Session, limit: int = 50, offset: int = 0) -> list[AgentAction]:
    stmt = select(AgentAction).order_by(desc(AgentAction.created_at)).offset(offset).limit(limit)
    return list(session.exec(stmt).all())
