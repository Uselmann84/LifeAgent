"""Deterministic approval & autonomy policy engine.

This module is the trusted core that decides whether an action with an external effect may
execute. The language model may *recommend* actions, but only this code authorizes them. See
docs/PERMISSION_MATRIX.md and docs/THREAT_MODEL.md.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import IntEnum

from app.core.models import ApprovalRequest, ApprovalStatus, RiskLevel


class AutonomyLevel(IntEnum):
    observe = 0
    prepare = 1
    low_risk_automation = 2
    trusted_workflow = 3
    consequential = 4  # never fully autonomous


# Action types that are ALWAYS Level 4 (explicit approval required, never autonomous).
CONSEQUENTIAL_ACTIONS: frozenset[str] = frozenset(
    {
        "send_sensitive_email",
        "file_taxes",
        "submit_government_form",
        "accept_contract",
        "make_purchase",
        "move_money",
        "share_identity_document",
        "delete_important_data",
        "cancel_insurance",
        "admit_liability",
        "agree_settlement",
        "contact_authority",  # attorneys, government, insurers, employers on consequential matters
        "message_new_recipient",
    }
)

# Actions that produce external side effects but may be pre-authorized at higher autonomy levels.
EXTERNAL_ACTIONS: frozenset[str] = frozenset(
    {
        "send_approved_email",
        "save_approved_calendar_event",
        "create_reminder",
        "move_email_to_spam",
        "archive_email",
        "label_email",
    }
)

# Irreversible actions can never be executed without a valid explicit approval.
IRREVERSIBLE_ACTIONS: frozenset[str] = frozenset(
    {
        "send_approved_email",
        "send_sensitive_email",
        "file_taxes",
        "submit_government_form",
        "make_purchase",
        "move_money",
        "delete_important_data",
        "cancel_insurance",
    }
)

# Internal-only actions never require approval.
INTERNAL_ACTIONS: frozenset[str] = frozenset(
    {
        "create_task",
        "update_task",
        "create_case",
        "link_document_to_case",
        "schedule_follow_up",
        "store_memory",
        "draft_email",
        "draft_sms",
        "create_calendar_event_draft",
        "classify_email",
        "search_email",
        "get_email_thread",
        "get_waiting_items",
    }
)

DEFAULT_APPROVAL_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class PolicyDecision:
    allowed_without_approval: bool
    requires_approval: bool
    risk_level: RiskLevel
    reasons: list[str] = field(default_factory=list)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def compute_payload_hash(payload: dict) -> str:
    """Stable hash binding an approval to an exact action payload.

    Any change to recipients / subject / body / attachments / amount / target changes the hash and
    therefore invalidates a prior approval.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def classify_risk(action_type: str, payload: dict | None = None) -> RiskLevel:
    payload = payload or {}
    if action_type in CONSEQUENTIAL_ACTIONS:
        return RiskLevel.critical
    if action_type in IRREVERSIBLE_ACTIONS:
        return RiskLevel.high
    if action_type in EXTERNAL_ACTIONS:
        # A monetary amount raises risk.
        if float(payload.get("amount", 0) or 0) > 0:
            return RiskLevel.high
        return RiskLevel.medium
    return RiskLevel.low


def evaluate(
    action_type: str,
    *,
    autonomy_level: int,
    payload: dict | None = None,
    recipient_trusted: bool = True,
    value_from_untrusted_only: bool = False,
    pre_authorized_workflow: bool = False,
) -> PolicyDecision:
    """Decide whether ``action_type`` may run without an explicit approval.

    ``value_from_untrusted_only`` is True when a critical parameter (recipient, amount, target)
    originated *only* from untrusted external content and was never validated — such actions can
    never proceed autonomously (prompt-injection defense).
    """
    payload = payload or {}
    reasons: list[str] = []
    risk = classify_risk(action_type, payload)

    # 1) Internal, no-side-effect actions never need approval.
    if action_type in INTERNAL_ACTIONS and action_type not in CONSEQUENTIAL_ACTIONS:
        return PolicyDecision(True, False, risk, ["internal action; no external effect"])

    # 2) Consequential (Level 4) actions ALWAYS require explicit approval.
    if action_type in CONSEQUENTIAL_ACTIONS:
        reasons.append("consequential action always requires explicit approval")
        return PolicyDecision(False, True, risk, reasons)

    # 3) Irreversible actions require a valid explicit approval regardless of level.
    if action_type in IRREVERSIBLE_ACTIONS:
        reasons.append("irreversible action requires explicit approval")
        return PolicyDecision(False, True, risk, reasons)

    # 4) A critical value sourced only from untrusted content can never proceed autonomously.
    if value_from_untrusted_only:
        reasons.append("critical parameter came only from untrusted content; approval required")
        return PolicyDecision(False, True, risk, reasons)

    # 5) An untrusted / new recipient forces approval.
    if not recipient_trusted:
        reasons.append("new or uncertain recipient; approval required")
        return PolicyDecision(False, True, risk, reasons)

    # 6) External actions: depend on autonomy level.
    if action_type in EXTERNAL_ACTIONS:
        if autonomy_level >= AutonomyLevel.trusted_workflow and pre_authorized_workflow:
            reasons.append("pre-authorized trusted workflow within boundaries")
            return PolicyDecision(True, False, risk, reasons)
        if autonomy_level >= AutonomyLevel.low_risk_automation and risk == RiskLevel.low:
            reasons.append("low-risk automation permitted at this autonomy level")
            return PolicyDecision(True, False, risk, reasons)
        reasons.append("external effect requires approval at current autonomy level")
        return PolicyDecision(False, True, risk, reasons)

    # 7) Default deny-to-approval for anything unrecognized with potential side effects.
    reasons.append("unrecognized action; defaulting to approval")
    return PolicyDecision(False, True, risk, reasons)


def new_approval_ttl() -> datetime:
    return _utcnow() + DEFAULT_APPROVAL_TTL


def validate_approval(approval: ApprovalRequest, submitted_payload_hash: str) -> None:
    """Raise ValueError if the approval cannot authorize execution.

    Enforces: status is approved, not expired, and the submitted payload hash matches the bound
    hash (invalidation on any payload change).
    """
    if approval.status == ApprovalStatus.invalidated:
        raise ValueError("approval was invalidated because the action payload changed")
    if approval.status != ApprovalStatus.approved:
        raise ValueError(f"approval is not in an approved state (status={approval.status.value})")
    if approval.expires_at is not None:
        expires = approval.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if _utcnow() > expires:
            raise ValueError("approval has expired")
    if submitted_payload_hash != approval.payload_hash:
        raise ValueError("payload changed since approval; approval no longer valid")


def is_expired(approval: ApprovalRequest) -> bool:
    if approval.expires_at is None:
        return False
    expires = approval.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return _utcnow() > expires
