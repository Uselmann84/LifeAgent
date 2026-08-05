# Life Agent

A private, local-first personal AI "Life Agent" that helps its single owner manage everyday
administrative work: email triage, deadlines, personal cases (warranty, insurance, vehicle
registration, taxes, subscriptions), documents, follow-ups, and calendar/reminders — while
keeping the user firmly in control through an explicit approval system.

> **Status:** Phase 0 + Phase 1 vertical slice. See [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Core principles

- **Privacy & local processing** — all inference and personal data stay on hardware you own.
- **Security & user control** — consequential actions always require explicit approval.
- **Traceability** — every material agent action is recorded in an audit log.
- **Reduced mental load** — the agent notices, organizes, remembers, prepares, warns, and follows up.

## Two-Mac architecture

This project is developed and operated across **three devices**:

```
┌─────────────────────────┐
│ Development MacBook      │
│ Claude Code + Xcode      │  ← source code, iOS builds, mock providers, tests
└────────────┬────────────┘
             │ Secure deployment / admin path (Tailscale + admin role)
             ▼
┌─────────────────────────┐
│ Backend MacBook Pro M3   │
│ AI + API + Data + Jobs   │  ← production inference, personal data, email sync
└────────────┬────────────┘
             │ Secure Life Agent API (Tailscale + iPhone user role)
             ▼
┌─────────────────────────┐
│ iPhone                   │
│ Native Life Agent App    │  ← native SwiftUI client
└─────────────────────────┘
```

Once deployed, the system operates **without** the Development MacBook. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/DEVELOPMENT_ENVIRONMENT.md](docs/DEVELOPMENT_ENVIRONMENT.md).

## Repository layout

```
life-agent/
├── apps/
│   ├── ios/                  # SwiftUI iPhone app (built on Development MacBook)
│   └── mac-control-center/   # (placeholder) macOS menu-bar control app
├── backend/
│   ├── api/                  # FastAPI routes
│   ├── agent/                # controlled agent loop, tools, content-trust
│   ├── integrations/         # email/calendar provider abstractions + mocks
│   ├── workflows/            # data-driven case workflow templates
│   ├── scheduler/            # follow-up / job orchestration (Phase 1: stubs)
│   ├── notifications/        # notification dispatch (Phase 1: stubs)
│   ├── document_processing/  # OCR / extraction (Phase 5: stubs)
│   ├── security/             # approval policy, autonomy levels, redaction
│   ├── core/                 # config, db, models, schemas
│   └── main.py               # app entrypoint
├── shared/                   # schemas / prompts / constants shared with docs
├── infrastructure/           # launchd plists, tailscale notes
├── scripts/                  # dev + deployment scripts
├── tests/                    # backend tests
├── docs/                     # architecture, threat model, deployment, etc.
├── .env.example
├── PROJECT_STATUS.md
└── README.md
```

## Quick start (Development MacBook, Demo Mode)

Requires Python 3.12+.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Copy env template and keep Demo Mode defaults
cp ../.env.example ../.env

# Seed fictional demo data and run the API
python -m app.seed
uvicorn app.main:app --reload --port 8787
```

Then open <http://127.0.0.1:8787/docs> for the interactive API, or
`GET http://127.0.0.1:8787/api/v1/health` for the health check.

Run the test suite:

```bash
cd backend
pytest -q
```

The iOS app lives in [apps/ios](apps/ios) and is built with Xcode on the Development MacBook.
See [docs/IOS_INSTALLATION.md](docs/IOS_INSTALLATION.md).

## Safety modes

The backend always boots in **Demo Mode** (`LIFE_AGENT_MODE=demo`) with fictional data and no real
integrations. Real integrations (`readonly_personal`, `controlled_action`) are feature-flagged and
must be enabled explicitly. See [docs/ENVIRONMENT_CONFIGURATION.md](docs/ENVIRONMENT_CONFIGURATION.md).
