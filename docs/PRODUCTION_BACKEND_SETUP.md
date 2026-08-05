# Production Backend Setup (Backend MacBook Pro M3)

The Backend Mac is the dedicated production host: FastAPI, local AI inference, email sync,
scheduled jobs, document processing, notifications, database, vector store, secrets, audit logs,
and backups. It runs near-continuously and **does not require Claude Code or Xcode**.

## Directory layout
```
~/LifeAgent/
├── app/            # deployed backend (symlinked from a release)
├── config/         # non-secret config; secrets live in Keychain
├── data/
│   ├── database/
│   ├── documents/
│   ├── vector_store/
│   └── cache/
├── models/         # local AI model files (downloaded ON this Mac)
├── logs/
├── backups/
├── releases/       # versioned releases (keep current + previous known-good)
└── current/        # symlink → releases/<active version>
```

## Idempotent setup
`scripts/install_backend.sh` is safe to run repeatedly. It:
1. Checks macOS version + Apple Silicon.
2. Verifies/install runtime deps (Python 3.12, optional Postgres, optional Ollama/MLX).
3. Creates the directory tree above (without overwriting existing data/secrets).
4. Creates an isolated venv and installs production deps.
5. Configures the production database + runs migrations.
6. Configures the local AI provider + model profiles.
7. Configures Tailscale + HTTPS on the private network.
8. Configures the production API + structured logs + rotation.
9. Installs the launchd service (auto-start).
10. Configures backup jobs + health monitoring.
11. Initializes/imports production secrets into the Keychain.
12. Runs production-readiness checks.

It **detects existing configuration and never overwrites production data or secrets.**

## Model routing / profiles
Model config must not assume dev==prod hardware. Profiles:
`production-fast` (spam/importance/extraction/routing), `production-reasoning` (case analysis,
planning, consequential drafting), `production-embedding`, `production-document` (OCR/interpretation).
Setup detects RAM/disk, verifies compatibility + checksums, runs inference + latency health checks,
selects safe defaults, and avoids loading more models than hardware supports. Model files are
downloaded **directly by the Backend Mac**, not copied through the Development Mac.

## Automatic startup (launchd)
Template: `infrastructure/launchd/com.lifeagent.backend.plist`. Install:
```bash
cp infrastructure/launchd/com.lifeagent.backend.plist ~/Library/LaunchAgents/
launchctl load  ~/Library/LaunchAgents/com.lifeagent.backend.plist
launchctl start com.lifeagent.backend
# status / stop / restart
launchctl list | grep lifeagent
launchctl stop  com.lifeagent.backend
launchctl kickstart -k gui/$(id -u)/com.lifeagent.backend
```
`KeepAlive` with a throttle prevents infinite crash loops; startup runs dependency + health checks.

## Secrets
Created/imported directly on this Mac into the macOS Keychain — never in Git, source, scripts, or
release archives. See [SECRETS_MANAGEMENT.md](SECRETS_MANAGEMENT.md).

## Pairing the iPhone
The Backend Mac generates a time-limited, single-use pairing code (QR) independent of the
Development Mac. See [NETWORK_AND_PAIRING.md](NETWORK_AND_PAIRING.md).

## Production-readiness checks
`scripts/verify_deployment.sh` verifies: service up, `/health` OK, model health OK, DB schema
version matches release, backup readable, and versions recorded.
