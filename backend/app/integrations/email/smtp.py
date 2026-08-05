"""Real SMTP email sender (Backend Mac only).

Sends mail through a standard SMTP server (mail.com by default). Sending is a real-world side
effect, so it must pass through the execution boundary (:func:`guard_side_effect`) — this module is
only ever invoked after an approval has been validated *and* the boundary authorizes it. Uses only
the Python standard library.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as MimeEmailMessage
from email.utils import make_msgid

from app.autonomy.execution import SideEffect, guard_side_effect
from app.core.config import Settings, get_settings


@dataclass
class SendResult:
    message_id: str
    accepted: list[str]


class SmtpEmailSender:
    name = "smtp"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def send(
        self,
        *,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
    ) -> SendResult:
        """Send an email. Refused by the execution boundary unless fully authorized."""
        # Defense in depth: even if a caller reaches here, the boundary must permit it.
        guard_side_effect(SideEffect.send_email, self._settings)
        s = self._settings
        if not (s.email_address and s.email_password and s.smtp_host):
            raise RuntimeError("SMTP credentials are not configured (Keychain not loaded?).")

        msg = MimeEmailMessage()
        msg["From"] = s.email_address
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg["Subject"] = subject
        message_id = make_msgid()
        msg["Message-ID"] = message_id
        msg.set_content(body)

        recipients = list(to) + list(cc or [])
        with smtplib.SMTP(s.smtp_host, s.smtp_port) as server:
            server.starttls()
            server.login(s.email_address, s.email_password)
            server.send_message(msg, to_addrs=recipients)
        return SendResult(message_id=message_id, accepted=recipients)
