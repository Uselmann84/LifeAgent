"""Persistent per-UID cache of email triage results.

Emails are immutable, so a message UID's triage (importance / why / calendar) never changes. Caching
it means a re-tick only sends *new* mail to the local model instead of re-classifying the whole inbox
every run. Stored as a small JSON file under the data directory (local-first; no DB migration).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.agent.importance import CalendarBlock, EmailTriage
from app.core.models import ImportanceCategory


class ClassificationCache:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._data: dict[str, dict] = {}
        try:
            self._data = json.loads(self._path.read_text("utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}

    def get(self, uid: str) -> EmailTriage | None:
        row = self._data.get(str(uid))
        if not isinstance(row, dict):
            return None
        try:
            importance = ImportanceCategory(row["importance"])
        except (KeyError, ValueError):
            return None
        cal = row.get("calendar")
        calendar = None
        if isinstance(cal, dict) and cal.get("title") and cal.get("start"):
            calendar = CalendarBlock(title=cal["title"], start=cal["start"], end=cal.get("end"))
        return EmailTriage(importance=importance, why=row.get("why", ""), calendar=calendar)

    def put(self, uid: str, triage: EmailTriage) -> None:
        calendar = None
        if triage.calendar is not None:
            calendar = {
                "title": triage.calendar.title,
                "start": triage.calendar.start,
                "end": triage.calendar.end,
            }
        self._data[str(uid)] = {
            "importance": triage.importance.value,
            "why": triage.why,
            "calendar": calendar,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, separators=(",", ":")), "utf-8")
        tmp.replace(self._path)  # atomic
