"""Tests for the persistent cross-tick dedup store."""

from __future__ import annotations

from app.autonomy.seen_store import SeenStore


def test_add_and_seen(tmp_path):
    store = SeenStore(tmp_path / "seen.json")
    assert store.seen("email", "uid-1") is False
    store.add("email", "uid-1")
    assert store.seen("email", "uid-1") is True


def test_namespaces_are_isolated(tmp_path):
    store = SeenStore(tmp_path / "seen.json")
    store.add("email", "1")
    assert store.seen("tasks", "1") is False


def test_keys_are_stringified(tmp_path):
    store = SeenStore(tmp_path / "seen.json")
    store.add("imessage", 42)
    assert store.seen("imessage", 42) is True
    assert store.seen("imessage", "42") is True


def test_persists_across_instances(tmp_path):
    path = tmp_path / "seen.json"
    SeenStore(path).add("email", "uid-9")
    assert SeenStore(path).seen("email", "uid-9") is True


def test_in_memory_store_does_not_persist(tmp_path):
    SeenStore().add("email", "uid-1")  # path=None, no file written
    assert not (tmp_path / "seen.json").exists()


def test_corrupt_file_is_ignored(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text("{broken", "utf-8")
    store = SeenStore(path)
    assert store.seen("email", "uid-1") is False
    store.add("email", "uid-1")
    assert SeenStore(path).seen("email", "uid-1") is True
