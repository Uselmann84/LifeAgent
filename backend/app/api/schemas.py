"""API request/response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    context: str | None = None  # treated as untrusted external content


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: str = "normal"
    due_at: datetime | None = None
    case_id: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_at: datetime | None = None


class CaseCreate(BaseModel):
    case_type: str
    title: str
    desired_outcome: str | None = None
    background: str | None = None


class CaseUpdate(BaseModel):
    status: str | None = None
    desired_outcome: str | None = None
    agent_next_action: str | None = None
    next_followup_at: datetime | None = None
    resolution_summary: str | None = None


class MemoryCreate(BaseModel):
    kind: str
    content: str
    sensitivity: str = "normal"
    inferred: bool = False
    expires_at: datetime | None = None


class EmailSearch(BaseModel):
    query: str


class EmailDraftRequest(BaseModel):
    to: list[str] = Field(default_factory=list)
    subject: str
    intent: str | None = None
    thread_id: str | None = None


class CleanupScanRequest(BaseModel):
    since: date
    before: date


class CleanupDeleteRequest(BaseModel):
    senders: list[str]
    since: date
    before: date
    reason: str | None = None


class ApproveRequest(BaseModel):
    payload_hash: str


class RejectRequest(BaseModel):
    reason: str | None = None


class ReviseRequest(BaseModel):
    instructions: str


class PairingStartResponse(BaseModel):
    code: str
    expires_at: datetime
    qr_payload: str


class PairingCompleteRequest(BaseModel):
    code: str
    device_name: str
    public_key: str
    role: str = "iphone_user"
