"""Real IMAP email reader (Backend Mac only).

Provider-agnostic IMAP client that works with mail.com (``anton.uselmann@mail.com``) and any other
standard IMAP account. Uses only the Python standard library. It is READ-ONLY: it fetches recent
messages and downloads their attachments so the document pipeline can understand them. Sending is a
separate, approval-gated concern (see :mod:`app.integrations.email.smtp`).

Network access to a real mailbox is refused unless we are on the Backend Mac in production execution
with ``feature_real_email_sync`` enabled — the Development Mac can never reach the real account.
"""

from __future__ import annotations

import email
import imaplib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime

from app.core.config import Settings, get_settings


class EmailSyncDisabled(RuntimeError):
    """Raised when a real mailbox fetch is attempted outside the authorized Backend Mac."""


@dataclass
class FetchedAttachment:
    filename: str
    content_type: str
    data: bytes

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass
class FetchedEmail:
    uid: str
    sender: str
    recipients: list[str]
    subject: str
    body: str
    received_at: datetime
    attachments: list[FetchedAttachment] = field(default_factory=list)


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _extract_body_and_attachments(msg: Message) -> tuple[str, list[FetchedAttachment]]:
    body_parts: list[str] = []
    attachments: list[FetchedAttachment] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            disposition = str(part.get("Content-Disposition") or "")
            content_type = part.get_content_type()
            filename = part.get_filename()
            if filename or "attachment" in disposition.lower():
                payload = part.get_payload(decode=True)
                if payload is not None:
                    attachments.append(
                        FetchedAttachment(
                            filename=_decode(filename) or "attachment.bin",
                            content_type=content_type,
                            data=payload,
                        )
                    )
            elif content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload is not None:
                    charset = part.get_content_charset() or "utf-8"
                    body_parts.append(payload.decode(charset, errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload is not None:
            charset = msg.get_content_charset() or "utf-8"
            body_parts.append(payload.decode(charset, errors="replace"))
    return ("\n".join(body_parts).strip(), attachments)


class ImapEmailClient:
    """Read-only IMAP client. Only usable on the Backend Mac in production execution."""

    name = "imap"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def read_only(self) -> bool:
        return True

    def _ensure_permitted(self) -> None:
        s = self._settings
        if not s.is_production_execution:
            raise EmailSyncDisabled(
                "Real IMAP fetch is only allowed on the Backend Mac (execution_mode=production). "
                "The Development Mac must use the simulated email source."
            )
        if not s.feature_real_email_sync:
            raise EmailSyncDisabled("feature_real_email_sync is disabled.")
        if not (s.email_address and s.email_password and s.imap_host):
            raise EmailSyncDisabled("IMAP credentials are not configured (Keychain not loaded?).")

    def fetch_recent(self, limit: int = 25) -> list[FetchedEmail]:
        """Fetch the most recent messages (newest first) with attachments downloaded."""
        self._ensure_permitted()
        s = self._settings
        results: list[FetchedEmail] = []
        conn = imaplib.IMAP4_SSL(s.imap_host, s.imap_port)
        try:
            conn.login(s.email_address, s.email_password)
            conn.select(s.email_mailbox, readonly=True)
            typ, data = conn.search(None, "ALL")
            if typ != "OK" or not data or not data[0]:
                return []
            uids = data[0].split()
            for uid in reversed(uids[-limit:]):
                typ, msg_data = conn.fetch(uid, "(RFC822)")
                if typ != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                body, attachments = _extract_body_and_attachments(msg)
                results.append(
                    FetchedEmail(
                        uid=uid.decode() if isinstance(uid, bytes) else str(uid),
                        sender=_parse_sender(msg),
                        recipients=_parse_recipients(msg),
                        subject=_decode(msg.get("Subject")),
                        body=body,
                        received_at=_parse_date(msg),
                        attachments=attachments,
                    )
                )
        finally:
            try:
                conn.close()
            except Exception:
                pass
            conn.logout()
        return results


def _parse_sender(msg: Message) -> str:
    addrs = getaddresses([msg.get("From", "")])
    return addrs[0][1] if addrs else ""


def _parse_recipients(msg: Message) -> list[str]:
    headers = [msg.get("To", ""), msg.get("Cc", "")]
    return [addr for _, addr in getaddresses(headers) if addr]


def _parse_date(msg: Message) -> datetime:
    raw = msg.get("Date")
    if not raw:
        return datetime.now(UTC)
    try:
        dt = parsedate_to_datetime(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except Exception:
        return datetime.now(UTC)
