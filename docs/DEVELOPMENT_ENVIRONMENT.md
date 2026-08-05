# Development Environment (Development MacBook)

The Development MacBook hosts Claude Code, source, Xcode, tests, and mock integrations. It builds
the iPhone app and prepares deployment packages. **It is never the permanent Life Agent backend.**

## Prerequisites
- macOS + Apple Silicon.
- Python 3.12+ (`brew install python@3.12` or from python.org).
- Xcode 15+ (for the iOS app).
- Git.
- (Optional) Ollama for local model testing: `brew install ollama`.
- (Optional) Tailscale for testing the private-network path.

## Backend (Demo Mode)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example ../.env          # keep Demo Mode defaults
python -m app.seed                  # seed fictional data
uvicorn app.main:app --reload --port 8787
```
- Health: <http://127.0.0.1:8787/api/v1/health>
- Docs: <http://127.0.0.1:8787/docs>

Run tests / validation:
```bash
pytest -q
../scripts/validate_release.sh      # runs lint + tests + secret scan + schema check
```

## Guardrails on the Development Mac
- Defaults to `LIFE_AGENT_MODE=demo`, `LIFE_AGENT_ENV=development`, `LLM_PROVIDER=mock`.
- The config layer **rejects a `production` DB URL when `LIFE_AGENT_ENV=development`** so the dev
  Mac cannot accidentally touch the production database.
- No production secrets ever live here — only public build config. See
  [SECRETS_MANAGEMENT.md](SECRETS_MANAGEMENT.md).
- Real integrations are feature-flagged off; enabling them for dev requires a dedicated test
  account, never production credentials.

## Fully developable without the Backend Mac
Mock LLM, mock Gmail, mock Calendar/Reminders, mock SMS composer state, seeded cases/tasks, mock
approvals, simulated push, and simulated backend states (offline / outdated / deploy-failure) let
you build and test nearly all behavior locally. See `backend/app/integrations/*/mock.py` and
`backend/tests/`.

## iOS
Open `apps/ios` in Xcode (see [IOS_INSTALLATION.md](IOS_INSTALLATION.md)). Debug builds may select
a Demo or Development backend; the app shows a clear environment banner for non-production
connections. Endpoints are **not** hard-coded — they come from connection profiles / `.xcconfig`
(see [ENVIRONMENT_CONFIGURATION.md](ENVIRONMENT_CONFIGURATION.md)).

## Deployment role
The Development Mac reaches the Backend Mac only over Tailscale using the **deploy_admin** role for
build/deploy/health/rollback — never with agent-approval or personal-data access. See
[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).
