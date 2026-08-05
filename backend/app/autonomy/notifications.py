"""Notification dispatcher (Section 35.9).

Delivers proactive nudges to the user. Real delivery (push/APNs) is a real-world side effect and
therefore passes through the execution boundary: on the Development Mac notifications are simulated
(recorded, not delivered); only a fully authorized Backend Mac delivers real notifications.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.autonomy.execution import SideEffect, simulate_or_block
from app.core.config import Settings, get_settings


@dataclass
class Notification:
    title: str
    body: str
    category: str = "info"


@dataclass
class NotificationDispatcher:
    settings: Settings = field(default_factory=get_settings)
    # Ring buffer of recently handled notifications for status/inspection.
    sent: list[Notification] = field(default_factory=list)
    simulated: list[Notification] = field(default_factory=list)

    def dispatch(self, notification: Notification) -> bool:
        """Deliver or simulate a notification. Returns True if really delivered."""
        if simulate_or_block(SideEffect.send_notification, self.settings):
            self.simulated.append(notification)
            return False
        # Backend Mac: real APNs delivery lands in a later phase.
        self.sent.append(notification)
        return True

    def recent(self, limit: int = 20) -> list[Notification]:
        return (self.sent + self.simulated)[-limit:]
