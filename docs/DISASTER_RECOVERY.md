# Disaster Recovery

Production data belongs to the **Backend Mac** and its configured backup destinations — not the
Development Mac. Source code and production personal data have **separate** backup strategies.

## What is backed up (encrypted)
Database, configuration (non-secret), workflow definitions, memories, case records, audit logs,
document metadata. Document *files* may be included or excluded per policy.

## Backup destinations
Encrypted external drive, another trusted local device, an encrypted network destination, or (later)
a user-approved encrypted cloud location. Backup encryption key lives in the Backend Mac Keychain.

## Backup jobs
- **Manual:** `scripts/backup_before_update.sh` (also used pre-deploy).
- **Scheduled:** launchd/cron on the Backend Mac.
- Every backup is **verified** by reading the archive back; a backup is never reported successful
  unless it can be read. A backup-health indicator is surfaced in the Mac Control Center.

## Restore
- `restore` verifies archive integrity and decryptability before applying.
- Restore into a scratch location first, validate schema + sentinel data, then promote.
- Restore reports whether it was complete (data + config) or partial.

## Recovery scenarios
| Scenario | Recovery |
|----------|----------|
| Bad deploy | `rollback_backend.sh` → previous release + verified pre-update backup. |
| DB corruption | Restore latest verified backup; replay nothing destructive. |
| Lost/stolen iPhone | Revoke device credential (`/pairing/revoke`); data stays on Backend Mac. |
| Development Mac lost/replaced | No runtime impact — Life Agent runs on Backend Mac + iPhone. Re-clone repo from Git; re-init dev env. |
| Backend Mac failure | Restore encrypted backup onto replacement Mac via `install_backend.sh` + `restore`; re-pair iPhone; re-authorize Gmail. |
| Secret compromise | Rotate affected key (`init_production_secrets.sh --rotate`); re-pair devices if signing key rotated; re-authorize OAuth. |

## Diagnostic support package (`scripts/collect_diagnostics.sh`)
Produces a **sanitized** bundle: system status, app version, migration version, service status,
recent redacted errors, model health, integration health, storage info. It **excludes** personal
email bodies, document contents, authentication tokens, and encryption keys.

## Production data during development
Never auto-synced to the Development Mac. Reproduce issues with structured error metadata and
sanitized fixtures. Any diagnostic export is an intentional action and is itself recorded.
