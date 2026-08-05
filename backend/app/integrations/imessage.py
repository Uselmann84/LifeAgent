"""iMessage integration (Backend Mac only; unofficial, best-effort).

Apple provides no iMessage API. On a Mac that is signed into iMessage we can:

* **read** history from the local Messages SQLite store (``~/Library/Messages/chat.db``), which
  requires **Full Disk Access** for the process, and
* **send** by driving the Messages app via AppleScript (``osascript``).

Both paths are fragile across macOS versions and only work on the Backend Mac. Reading requires
``feature_real_imessage_read``; sending is a real-world side effect gated by the execution boundary
(:func:`guard_side_effect`) and ``feature_real_imessage_send``. Uses only the standard library.
"""

from __future__ import annotations

import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.autonomy.execution import SideEffect, guard_side_effect
from app.core.config import Settings, get_settings

# Apple Cocoa Core Data epoch: 2001-01-01 00:00:00 UTC, in Unix seconds.
_APPLE_EPOCH_OFFSET = 978307200


class IMessageDisabled(RuntimeError):
    """Raised when an iMessage operation is attempted outside the authorized Backend Mac."""


@dataclass
class IMessageRecord:
    rowid: int
    handle: str  # phone number or email of the other party
    text: str
    is_from_me: bool
    sent_at: datetime


def _apple_ns_to_datetime(value: int | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    # Newer macOS stores nanoseconds; older stored seconds. Normalize.
    seconds = value / 1_000_000_000 if value > 1_000_000_000_000 else value
    return datetime.fromtimestamp(seconds + _APPLE_EPOCH_OFFSET, tz=UTC)


class IMessageReader:
    name = "imessage"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def read_only(self) -> bool:
        return True

    def _ensure_permitted(self) -> None:
        s = self._settings
        if not s.is_production_execution:
            raise IMessageDisabled(
                "iMessage access is only allowed on the Backend Mac (execution_mode=production)."
            )
        if not s.feature_real_imessage_read:
            raise IMessageDisabled("feature_real_imessage_read is disabled.")

    def recent(self, limit: int = 25) -> list[IMessageRecord]:
        """Return the most recent messages (newest first). Read-only."""
        self._ensure_permitted()
        db_path = Path(self._settings.imessage_db_path).expanduser()
        if not db_path.exists():
            raise IMessageDisabled(
                f"Messages database not found at {db_path}. Is this the Backend Mac with "
                "Full Disk Access granted?"
            )
        # Read-only connection; never mutate the Messages store.
        uri = f"file:{db_path}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT m.ROWID AS rowid,
                       COALESCE(h.id, '') AS handle,
                       COALESCE(m.text, '') AS text,
                       m.is_from_me AS is_from_me,
                       m.date AS date
                FROM message m
                LEFT JOIN handle h ON m.handle_id = h.ROWID
                ORDER BY m.date DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        finally:
            conn.close()
        return [
            IMessageRecord(
                rowid=r["rowid"],
                handle=r["handle"],
                text=r["text"],
                is_from_me=bool(r["is_from_me"]),
                sent_at=_apple_ns_to_datetime(r["date"]),
            )
            for r in rows
        ]


class IMessageSender:
    name = "imessage"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def send(self, *, to: str, body: str) -> dict[str, str]:
        """Send an iMessage via AppleScript. Refused by the boundary unless fully authorized."""
        guard_side_effect(SideEffect.send_imessage, self._settings)
        script = (
            'on run {targetBuddy, targetMessage}\n'
            '    tell application "Messages"\n'
            '        set targetService to 1st account whose service type = iMessage\n'
            '        set targetParticipant to participant targetBuddy of targetService\n'
            '        send targetMessage to targetParticipant\n'
            '    end tell\n'
            'end run'
        )
        result = subprocess.run(
            ["osascript", "-e", script, to, body],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"osascript failed: {result.stderr.strip()}")
        return {"to": to, "status": "sent"}
