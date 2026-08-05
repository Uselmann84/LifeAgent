"""Email provider abstraction.

Future providers (Gmail, Outlook, IMAP-read, SMTP) implement this Protocol. Read operations are
available in ``readonly_personal``; write/send operations are approval-gated and feature-flagged.
The mock provider backs Demo Mode entirely offline.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.core.models import EmailMessage


@runtime_checkable
class EmailProvider(Protocol):
    name: str

    def list_threads(self) -> list[str]: ...

    def get_thread(self, thread_id: str) -> list[EmailMessage]: ...

    def search(self, query: str) -> list[EmailMessage]: ...

    def read_only(self) -> bool: ...
