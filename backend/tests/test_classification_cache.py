"""Tests for the persistent per-UID email triage cache."""

from __future__ import annotations

from app.agent.importance import CalendarBlock, EmailTriage
from app.autonomy.classification_cache import ClassificationCache
from app.core.models import ImportanceCategory


def test_put_get_roundtrip(tmp_path):
    cache = ClassificationCache(tmp_path / "cache.json")
    triage = EmailTriage(ImportanceCategory.needs_action_today, "flight check-in opens soon")
    cache.put("uid-1", triage)
    got = cache.get("uid-1")
    assert got is not None
    assert got.importance is ImportanceCategory.needs_action_today
    assert got.why == "flight check-in opens soon"
    assert got.calendar is None


def test_roundtrip_with_calendar(tmp_path):
    cache = ClassificationCache(tmp_path / "cache.json")
    triage = EmailTriage(
        ImportanceCategory.needs_action_soon,
        "concert",
        CalendarBlock(title="Show", start="2026-08-22T14:00:00-07:00", end="2026-08-22T21:00:00-07:00"),
    )
    cache.put("uid-2", triage)
    got = cache.get("uid-2")
    assert got.calendar is not None
    assert got.calendar.title == "Show"
    assert got.calendar.end == "2026-08-22T21:00:00-07:00"


def test_persists_across_instances(tmp_path):
    path = tmp_path / "cache.json"
    ClassificationCache(path).put("uid-3", EmailTriage(ImportanceCategory.dangerous, "phishing"))
    reopened = ClassificationCache(path)
    assert reopened.get("uid-3").importance is ImportanceCategory.dangerous


def test_miss_returns_none(tmp_path):
    assert ClassificationCache(tmp_path / "cache.json").get("nope") is None


def test_corrupt_file_is_ignored(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text("{not valid json", "utf-8")
    cache = ClassificationCache(path)
    assert cache.get("uid-4") is None
    cache.put("uid-4", EmailTriage(ImportanceCategory.informational, ""))
    assert cache.get("uid-4") is not None
