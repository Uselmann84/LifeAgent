"""The single execution boundary for real-world side effects (Section 35.8).

Every action that touches the outside world — sending email, writing calendar events, creating
reminders, sending notifications, calling webhooks — MUST pass through :func:`guard_side_effect`
first. The Development Mac (``execution_mode=simulation``) can never satisfy the guard, so it is
structurally incapable of acting on the real world; it may only *simulate* effects.

This is defense in depth on top of the approval policy: even a bug that bypasses approval cannot
produce a real side effect on the Development Mac.
"""

from __future__ import annotations

from enum import Enum

from app.core.config import ExecutionMode, RuntimeMode, Settings, get_settings


class SideEffect(str, Enum):
    """Categories of real-world side effect, each gated by its own feature flag."""

    send_email = "send_email"
    modify_calendar = "modify_calendar"
    create_reminder = "create_reminder"
    send_notification = "send_notification"
    move_email = "move_email"
    call_webhook = "call_webhook"
    sync_email = "sync_email"
    send_imessage = "send_imessage"


class SideEffectBlocked(RuntimeError):
    """Raised when a real-world side effect is attempted outside the production boundary."""


# Maps each side effect to the feature flag that must be explicitly enabled for it to run.
_REQUIRED_FLAG: dict[SideEffect, str] = {
    SideEffect.send_email: "feature_real_email_send",
    SideEffect.sync_email: "feature_real_email_sync",
    SideEffect.modify_calendar: "feature_real_calendar_write",
    SideEffect.move_email: "feature_move_email_to_spam",
    SideEffect.create_reminder: "feature_real_calendar_write",
    SideEffect.send_notification: "notifications_enabled",
    SideEffect.call_webhook: "feature_real_calendar_write",
    SideEffect.send_imessage: "feature_real_imessage_send",
}


def side_effects_permitted(settings: Settings | None = None) -> bool:
    """True only on the Backend Mac in production execution + controlled-action mode."""
    settings = settings or get_settings()
    return (
        settings.execution_mode == ExecutionMode.production
        and settings.mode == RuntimeMode.controlled_action
    )


def guard_side_effect(effect: SideEffect, settings: Settings | None = None) -> None:
    """Authorize a real-world side effect or raise :class:`SideEffectBlocked`.

    Requires, in order:
      1. production execution mode (Backend Mac only),
      2. controlled-action runtime mode,
      3. the specific feature flag for this effect to be enabled.
    """
    settings = settings or get_settings()

    if settings.execution_mode != ExecutionMode.production:
        raise SideEffectBlocked(
            f"'{effect.value}' blocked: execution_mode={settings.execution_mode.value}. "
            "Real-world side effects run only on the Backend Mac (execution_mode=production). "
            "This environment may only simulate the effect."
        )
    if settings.mode != RuntimeMode.controlled_action:
        raise SideEffectBlocked(
            f"'{effect.value}' blocked: runtime mode={settings.mode.value}. "
            "Real actions require controlled_action mode."
        )
    flag = _REQUIRED_FLAG.get(effect)
    if flag is not None and not getattr(settings, flag, False):
        raise SideEffectBlocked(
            f"'{effect.value}' blocked: feature flag '{flag}' is disabled."
        )


def simulate_or_block(effect: SideEffect, settings: Settings | None = None) -> bool:
    """Return True if the caller should *simulate* the effect instead of executing it.

    Simulation is the correct behavior everywhere except a fully authorized Backend Mac. Callers
    use this to record a simulated outcome (audit + logs) without any external effect.
    """
    settings = settings or get_settings()
    try:
        guard_side_effect(effect, settings)
    except SideEffectBlocked:
        return True
    return False
