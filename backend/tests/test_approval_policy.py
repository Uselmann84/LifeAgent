"""Approval-policy and approval-invalidation tests (the security core)."""

from __future__ import annotations

import pytest

from app.core.models import ApprovalRequest, ApprovalStatus, RiskLevel
from app.security import approval as policy
from app.security.approval import AutonomyLevel


def test_consequential_action_always_requires_approval_even_at_max_autonomy():
    decision = policy.evaluate(
        "move_money", autonomy_level=AutonomyLevel.trusted_workflow, payload={"amount": 10}
    )
    assert decision.requires_approval is True
    assert decision.allowed_without_approval is False
    assert decision.risk_level == RiskLevel.critical


def test_internal_action_never_requires_approval():
    decision = policy.evaluate("create_task", autonomy_level=AutonomyLevel.observe)
    assert decision.requires_approval is False
    assert decision.allowed_without_approval is True


def test_send_email_requires_approval_at_default_level():
    decision = policy.evaluate(
        "send_approved_email",
        autonomy_level=AutonomyLevel.prepare,
        payload={"to": ["a@b.test"], "subject": "x", "body": "y"},
    )
    assert decision.requires_approval is True


def test_untrusted_only_value_blocks_autonomy():
    decision = policy.evaluate(
        "label_email",
        autonomy_level=AutonomyLevel.trusted_workflow,
        value_from_untrusted_only=True,
    )
    assert decision.requires_approval is True


def test_new_recipient_forces_approval():
    decision = policy.evaluate(
        "send_approved_email",
        autonomy_level=AutonomyLevel.trusted_workflow,
        payload={"to": ["stranger@x.test"], "subject": "s", "body": "b"},
        recipient_trusted=False,
    )
    assert decision.requires_approval is True


def test_payload_hash_is_stable_and_order_independent():
    p1 = {"to": ["a@b.test", "c@d.test"], "subject": "s", "body": "b"}
    p2 = {"body": "b", "subject": "s", "to": ["a@b.test", "c@d.test"]}
    assert policy.compute_payload_hash(p1) == policy.compute_payload_hash(p2)


def test_payload_change_changes_hash():
    base = {"to": ["a@b.test"], "subject": "s", "body": "b"}
    changed = {"to": ["a@b.test"], "subject": "s", "body": "b2"}
    assert policy.compute_payload_hash(base) != policy.compute_payload_hash(changed)


def _make_approval(payload: dict) -> ApprovalRequest:
    return ApprovalRequest(
        action_type="send_approved_email",
        reason="test",
        payload=payload,
        payload_hash=policy.compute_payload_hash(payload),
        status=ApprovalStatus.approved,
        expires_at=policy.new_approval_ttl(),
    )


def test_validate_approval_accepts_matching_hash():
    payload = {"to": ["a@b.test"], "subject": "s", "body": "b"}
    approval = _make_approval(payload)
    # Should not raise.
    policy.validate_approval(approval, policy.compute_payload_hash(payload))


def test_validate_approval_rejects_changed_payload():
    payload = {"to": ["a@b.test"], "subject": "s", "body": "b"}
    approval = _make_approval(payload)
    tampered = policy.compute_payload_hash({**payload, "body": "evil"})
    with pytest.raises(ValueError, match="payload changed"):
        policy.validate_approval(approval, tampered)


def test_validate_approval_rejects_non_approved_status():
    payload = {"to": ["a@b.test"], "subject": "s", "body": "b"}
    approval = _make_approval(payload)
    approval.status = ApprovalStatus.pending
    with pytest.raises(ValueError):
        policy.validate_approval(approval, approval.payload_hash)
