"""Database engine, sessions, and a lightweight versioned-migration runner.

Schema is created through numbered migrations recorded in ``schemamigration``. Migration 001
establishes the baseline via SQLModel metadata (portable across SQLite and PostgreSQL). Future
migrations are appended as numbered steps. ``current_schema_version`` powers the health endpoint
and the deploy-time compatibility gate (see docs/UPDATE_AND_ROLLBACK.md).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import get_settings
from app.core.models import SchemaMigration
from app.core.versions import DB_SCHEMA_VERSION

_settings = get_settings()

_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
engine = create_engine(_settings.database_url, echo=False, connect_args=_connect_args)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def current_schema_version() -> int:
    """Return the highest applied migration version (0 if none)."""
    with engine.connect() as conn:
        try:
            rows = conn.execute(text("SELECT MAX(version) FROM schemamigration")).scalar()
        except Exception:
            return 0
    return int(rows) if rows is not None else 0


def _record_migration(session: Session, version: int, name: str) -> None:
    session.add(SchemaMigration(version=version, name=name))
    session.commit()


def run_migrations() -> int:
    """Apply pending migrations. Idempotent and safe to run on every startup.

    Returns the resulting schema version.
    """
    # Ensure the migration bookkeeping table exists first.
    SchemaMigration.metadata.create_all(engine, tables=[SchemaMigration.__table__])

    applied = current_schema_version()

    # --- Migration 001: baseline schema -------------------------------------------------
    if applied < 1:
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            if not session.exec(select(SchemaMigration).where(SchemaMigration.version == 1)).first():
                _record_migration(session, 1, "initial")
        applied = 1

    # Future migrations (2, 3, ...) are appended here as backward-compatible steps.

    assert applied == DB_SCHEMA_VERSION, (
        f"Applied schema version {applied} != expected {DB_SCHEMA_VERSION}. "
        "Add a migration step for the new version."
    )
    return applied


def reset_database() -> None:
    """Drop and recreate all tables. TEST/DEMO ONLY — never call in production paths."""
    SQLModel.metadata.drop_all(engine)
    run_migrations()
