"""Domain-first persistence models (SQLModel).

Storage is explicit entities, not chat blobs. JSON columns hold structured lists/dicts. IDs are
UUID strings; timestamps are timezone-aware UTC. See docs/DOMAIN_MODEL.md.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- enums
class TaskStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    waiting = "waiting"
    blocked = "blocked"
    done = "done"
    cancelled = "cancelled"


class Priority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class CaseStatus(str, Enum):
    open = "open"
    waiting = "waiting"
    at_risk = "at_risk"
    resolved = "resolved"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    revise = "revise"
    expired = "expired"
    invalidated = "invalidated"


class ImportanceCategory(str, Enum):
    critical = "critical"
    needs_action_today = "needs_action_today"
    needs_action_soon = "needs_action_soon"
    waiting_for_response = "waiting_for_response"
    informational = "informational"
    newsletter = "newsletter"
    promotion = "promotion"
    likely_spam = "likely_spam"
    dangerous = "dangerous"


class DeviceRole(str, Enum):
    iphone_user = "iphone_user"
    deploy_admin = "deploy_admin"
    owner = "owner"


# --------------------------------------------------------------------------- entities
class Person(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    relationship: str | None = None
    emails: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    phones: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    organization_id: str | None = Field(default=None, foreign_key="organization.id")
    preferred_channel: str | None = None
    notes: str | None = None
    trusted: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Organization(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    category: str | None = None
    website: str | None = None
    phones: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    account_identifiers: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    notes: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Case(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    case_type: str
    title: str
    status: CaseStatus = CaseStatus.open
    desired_outcome: str | None = None
    background: str | None = None
    timeline: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    parties: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    reference_numbers: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    important_dates: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    missing_information: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    risks: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    agent_next_action: str | None = None
    next_followup_at: datetime | None = None
    resolution_summary: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Task(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    title: str
    description: str | None = None
    status: TaskStatus = TaskStatus.open
    priority: Priority = Priority.normal
    due_at: datetime | None = None
    source: str | None = None
    related_email_id: str | None = None
    case_id: str | None = Field(default=None, foreign_key="case.id")
    related_person_id: str | None = Field(default=None, foreign_key="person.id")
    related_org_id: str | None = Field(default=None, foreign_key="organization.id")
    dependencies: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    checklist: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    agent_recommendation: str | None = None
    approval_status: str | None = None
    completion_evidence: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Communication(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    channel: str
    sender: str | None = None
    recipients: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    sent_at: datetime | None = None
    thread_id: str | None = None
    summary: str | None = None
    intent: str | None = None
    urgency: str | None = None
    task_id: str | None = Field(default=None, foreign_key="task.id")
    case_id: str | None = Field(default=None, foreign_key="case.id")
    attachments: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    follow_up_required: bool = False
    follow_up_at: datetime | None = None
    provider_message_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Document(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    filename: str
    file_hash: str
    source: str | None = None
    doc_type: str | None = None
    extracted_text: str | None = None
    summary: str | None = None
    important_dates: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    parties: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    reference_numbers: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    case_id: str | None = Field(default=None, foreign_key="case.id")
    sensitivity: str = "normal"
    retention_policy: str | None = None
    storage_ref: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class ApprovalRequest(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    action_type: str
    reason: str
    data_affected: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    payload_hash: str
    risk_level: RiskLevel = RiskLevel.medium
    status: ApprovalStatus = ApprovalStatus.pending
    expires_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    execution_result: str | None = None
    case_id: str | None = Field(default=None, foreign_key="case.id")
    created_at: datetime = Field(default_factory=utcnow)


class AgentAction(SQLModel, table=True):
    """Audit entry. Stores a concise decision summary, never private chain-of-thought."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    planned_action: str
    tools_used: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    inputs_redacted: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    outputs_redacted: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    reasoning_summary: str | None = None
    approval_id: str | None = Field(default=None, foreign_key="approvalrequest.id")
    success: bool | None = None
    reversible: bool = True
    rollback_info: str | None = None
    evidence: str | None = None
    account_affected: str | None = None
    data_read: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    data_changed: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    external_confirmation_id: str | None = None
    followup_scheduled_at: datetime | None = None
    correlation_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class MemoryItem(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    kind: str
    content: str
    source: str | None = None
    confidence: float = 1.0
    inferred: bool = False
    sensitivity: str = "normal"
    learned_at: datetime = Field(default_factory=utcnow)
    last_confirmed_at: datetime | None = None
    expires_at: datetime | None = None
    case_id: str | None = Field(default=None, foreign_key="case.id")


class EmailMessage(SQLModel, table=True):
    """Mock/provider-backed email message used for the inbox and importance features."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    thread_id: str
    sender: str
    recipients: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    subject: str
    body: str
    received_at: datetime = Field(default_factory=utcnow)
    importance: ImportanceCategory = ImportanceCategory.informational
    why_it_matters: str | None = None
    requested_action: str | None = None
    deadline_at: datetime | None = None
    confidence: float = 0.5
    case_id: str | None = Field(default=None, foreign_key="case.id")
    awaiting_response_from: str | None = None  # who owes the next reply


class PairedDevice(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    role: DeviceRole = DeviceRole.iphone_user
    public_key: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime | None = None
    revoked: bool = False


class PairingCode(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    code_hash: str
    role: DeviceRole = DeviceRole.iphone_user
    expires_at: datetime
    used: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class SchemaMigration(SQLModel, table=True):
    version: int = Field(primary_key=True)
    name: str
    applied_at: datetime = Field(default_factory=utcnow)
