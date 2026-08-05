# Update & Rollback

All schema changes use **versioned migrations**. Prefer backward-compatible migrations that allow
safe rollback. Never run destructive migrations without an explicit, documented migration plan.

## Update procedure (`scripts/update_backend.sh`)
1. Verify current backend version + current DB migration version.
2. `scripts/backup_before_update.sh` — create a **verified** backup (archive is read back).
3. Check available disk space.
4. Stop/drain relevant workers safely (graceful).
5. Apply migrations.
6. Activate new release (`current/` symlink) and start the updated backend.
7. Run health checks (`/health`, model health).
8. Verify critical data (row counts / sentinel records).
9. Mark the release successful and record it in `releases/` metadata + logs.

## On verification failure (`scripts/rollback_backend.sh`)
1. Stop the new version.
2. Preserve diagnostic logs (sanitized).
3. Restore the previous known-good application version (symlink back).
4. Restore the database **only when required and safe** (from the verified pre-update backup).
5. Restart and health-check.
6. **Clearly report whether rollback was complete** (application-only vs application+data).

## Retention
The Backend Mac keeps at least: current release, previous known-good release, migration metadata,
and release logs.

## Migration authoring rules
- Additive first (new nullable columns / new tables), backfill, then tighten in a later release.
- Every migration has an `up` and a documented `down`/compat note.
- Migration tests (`backend/tests/test_migrations.py`) apply migrations to a fresh DB and assert the schema
  version and key invariants.

## Compatibility gate
`verify_deployment.sh` refuses to mark success if the running `db_schema_version` does not match
the release manifest's `required_migration`. The iPhone app surfaces API-version mismatches.
