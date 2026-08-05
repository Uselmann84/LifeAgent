# Deployment Guide

Moving a backend release from the **Development Mac** to the **Backend Mac Pro M3**.

## Flow
```
Development MacBook
   ↓  git commit + tag (vX.Y.Z)
   ↓  scripts/validate_release.sh   (tests, lint, secret scan, schema check)
   ↓  scripts/build_backend_release.sh   → releases/lifeagent-vX.Y.Z.tar.gz + manifest
   ↓  scripts/deploy_to_backend.sh   (Tailscale, deploy_admin role)
Backend MacBook Pro M3
   ↓  backup_before_update → migrate → health check → activate (symlink current/)
   ↓  scripts/verify_deployment.sh
Live
```

## Release contents (only what production needs)
Backend source/package, dependency lockfile, migrations, workflow templates, prompt templates,
static assets, service config, version metadata, install/update scripts.
**Excluded:** dev DBs, test data, dev OAuth tokens, Xcode files, Claude Code session data,
uncommitted files, dev secrets, local caches, production personal data.

## Steps
1. On the Development Mac, ensure a clean working tree (no uncommitted changes) and tag the release.
2. `./scripts/validate_release.sh` — deployment **stops** if required checks fail. An emergency
   override exists only as `--emergency-override "<reason>"` and records the reason.
3. `./scripts/build_backend_release.sh vX.Y.Z` — builds the tarball + `manifest.json`
   (semver, git commit, build timestamp, required DB migration, min iOS version, api version,
   backup requirement, rollback notes, health-check criteria).
4. `./scripts/deploy_to_backend.sh vX.Y.Z <backend-tailscale-host>` — transfers the package over
   Tailscale using the deploy_admin credential and runs `update_backend.sh` remotely.
5. On the Backend Mac, `update_backend.sh`:
   verify current version + DB migration → `backup_before_update.sh` (verified) → check disk →
   drain workers → apply migrations → activate new release → start service → health checks →
   verify critical data → mark success. On failure it invokes `rollback_backend.sh`.
6. `./scripts/verify_deployment.sh` confirms service, health, model health, schema, backup, versions.

## Versioning
`Backend: 0.1.0 · iOS: 0.1.0 · API: v1 · DB schema: 001`. The Backend Mac records the active
version; `/api/v1/health` returns it; the iPhone shows its own + the backend version and detects
incompatible API versions. Production is **never** auto-updated from every commit — updates are
intentional and visible.

## Push notifications
Until APNs is fully configured, production uses local notifications + refresh-on-open. When
enabled, APNs credentials live in the Keychain on the Backend Mac (never in Git). Payloads avoid
sensitive content. See [APPLE_PLATFORM_LIMITATIONS.md](APPLE_PLATFORM_LIMITATIONS.md).

## First-deployment independence test (mandatory)
Build & deploy release → backend auto-starts → model health passes → prod DB initialized → build
iOS in Xcode → cable-install to iPhone → iPhone pairs directly with Backend Mac → **turn off the
Development Mac** → iPhone still talks to the Life Agent → scheduled jobs keep running → reboot the
Backend Mac and confirm the service auto-restores → backup+restore test passes → versions visible.
See [UPDATE_AND_ROLLBACK.md](UPDATE_AND_ROLLBACK.md) and [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md).
