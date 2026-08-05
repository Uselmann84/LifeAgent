"""Database migration tests."""

from __future__ import annotations

from app.core.db import current_schema_version, reset_database, run_migrations
from app.core.versions import DB_SCHEMA_VERSION


def test_migrations_reach_expected_version():
    reset_database()
    assert current_schema_version() == DB_SCHEMA_VERSION


def test_migrations_are_idempotent():
    reset_database()
    v1 = run_migrations()
    v2 = run_migrations()
    assert v1 == v2 == DB_SCHEMA_VERSION
