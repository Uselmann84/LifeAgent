"""Guardrail tests for real integrations (email/IMAP-SMTP, iCloud CalDAV, iMessage).

These verify the safety envelope, not real network I/O: in simulation every integration must refuse
to read (``*Disabled``) or to take an external effect (``SideEffectBlocked``).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.autonomy.execution import SideEffectBlocked
from app.integrations.calendar.icloud import (
    CalendarDisabled,
    ICloudCalendarClient,
    NewCalendarEvent,
)
from app.integrations.email.imap import EmailSyncDisabled, ImapEmailClient
from app.integrations.email.smtp import SmtpEmailSender
from app.integrations.imessage import IMessageDisabled, IMessageReader, IMessageSender


def test_imap_fetch_disabled_in_simulation():
    with pytest.raises(EmailSyncDisabled):
        ImapEmailClient().fetch_recent(limit=5)


def test_smtp_send_blocked_in_simulation():
    with pytest.raises(SideEffectBlocked):
        SmtpEmailSender().send(to=["a@example.com"], subject="hi", body="test")


def test_icloud_read_disabled_in_simulation():
    with pytest.raises(CalendarDisabled):
        ICloudCalendarClient().upcoming(days=3)


def test_icloud_create_event_blocked_in_simulation():
    now = datetime.now().astimezone()
    event = NewCalendarEvent(title="x", start=now, end=now + timedelta(hours=1))
    with pytest.raises(SideEffectBlocked):
        ICloudCalendarClient().create_event(event)


def test_imessage_read_disabled_in_simulation():
    with pytest.raises(IMessageDisabled):
        IMessageReader().recent(limit=5)


def test_imessage_send_blocked_in_simulation():
    with pytest.raises(SideEffectBlocked):
        IMessageSender().send(to="+15551234567", body="hi")
