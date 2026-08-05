# Project Status — Life Agent

_Last updated: Phase 0 + Phase 1 vertical slice._

## Legend
- ✅ done / working & tested
- 🟡 partial / stubbed
- ⬜ not started

## Phase 0 — Architecture & foundation
| Item | Status | Notes |
|------|--------|-------|
| Monorepo structure | ✅ | `apps/`, `backend/` (+ `backend/tests/`), `docs/`, `scripts/`, `infrastructure/` |
| `.env.example` (no real secrets) | ✅ | Feature flags default OFF |
| Config system w/ environment separation | ✅ | `demo`/`readonly_personal`/`controlled_action` modes |
| Domain model | ✅ | Person, Org, Task, Case, Communication, Document, ApprovalRequest, AgentAction, MemoryItem |
| Database migrations | ✅ | Versioned SQL migration `001_initial`, applied on startup |
| Mock providers (email, calendar, LLM) | ✅ | Fully offline development |
| Approval / autonomy policy engine | ✅ | Deterministic, with payload-binding + invalidation |
| Prompt-injection / content-trust module | ✅ | Trust levels + untrusted-content detection |
| Audit log | ✅ | Structured, redacted, user-readable |
| Architecture docs | ✅ | See `docs/` (19 documents) |
| CI / local validation script | ✅ | `scripts/validate_release.sh` (lint + tests + secret scan + schema check) |
| PROJECT_STATUS.md | ✅ | This file |

## Phase 1 — Working vertical slice
| Item | Status | Notes |
|------|--------|-------|
| Backend health endpoint | ✅ | `GET /api/v1/health` |
| Local-model health endpoint | ✅ | `GET /api/v1/health/model` |
| Chat endpoint (agent loop) | ✅ | Mock LLM; returns recommendation + rationale |
| Today briefing endpoint | ✅ | Priorities, deadlines, waiting-for, approvals |
| Task / case creation | ✅ | REST + agent-driven |
| Demo email inbox | ✅ | Mock provider seeded threads |
| Agent-generated recommendation | ✅ | Distinguishes found/recommend/prepared/approval-needed |
| Approval card + approve/reject | ✅ | Payload-bound approvals w/ invalidation |
| Audit log endpoint | ✅ | `GET /api/v1/activity` |
| iOS SwiftUI app shell | ✅ | Today / Agent / Cases / Inbox / More tabs; typechecks against iOS SDK |
| Backend version + API version surfaced | ✅ | `/api/v1/health` returns versions |
| Secure pairing scaffold | 🟡 | Pairing-code model + endpoints; crypto is placeholder |
| Push notifications | 🟡 | Local-notification fallback documented; APNs deferred |

## Two-Mac Development and Production Architecture
| Item | Status | Notes |
|------|--------|-------|
| Env separation (`development`/`testing`/`staging`/`production`) | ✅ | `LIFE_AGENT_ENV` + per-env settings |
| Configurable paths (no hard-coded Mac paths) | ✅ | All dirs via env |
| iPhone endpoints not hard-coded | ✅ | Backend connection profiles in app; `.xcconfig` mapping documented |
| Deployment package scripts | ✅ | `validate_release`, `build_backend_release`, `deploy_to_backend`, `install_backend`, `update_backend` (auto-rollback), `rollback_backend`, `backup_before_update`, `verify_deployment`, `uninstall_backend`, `init_production_secrets`, `collect_diagnostics` |
| launchd auto-start | ✅ | `infrastructure/launchd/com.lifeagent.backend.plist` template installed by `install_backend.sh` |
| Separate dev/deploy/owner roles | ✅ | Role model in security layer; enforced on admin routes |
| Production secrets on Backend Mac only | ✅ | Documented in `docs/SECRETS_MANAGEMENT.md`; Keychain approach |
| Dev-Mac cannot touch prod DB by default | ✅ | Guardrail in config (`production` DB URL rejected in `development`) |
| Deployment docs | ✅ | `DEPLOYMENT_GUIDE.md`, `UPDATE_AND_ROLLBACK.md`, `PRODUCTION_BACKEND_SETUP.md`, `DISASTER_RECOVERY.md` |

## Section 35 — Autonomous agent + two-Mac execution separation
| Item | Status | Notes |
|------|--------|-------|
| Execution reality boundary (`simulation`/`production`) | ✅ | `LIFE_AGENT_EXECUTION_MODE` + cross-guardrails; illegal combos rejected |
| Single side-effect chokepoint | ✅ | `app/autonomy/execution.py` (`guard_side_effect`/`simulate_or_block`); wired into agent tools |
| Event sources (sim + prod variants) | ✅ | email (mail.com/IMAP), calendar (iCloud/CalDAV), tasks, iMessage, user, system; prod sources fail soft when disabled |
| Real integrations (Backend Mac) | ✅ | IMAP read + SMTP send (mail.com), iCloud CalDAV read/write, iMessage read + send; all approval- and flag-gated |
| Document understanding | ✅ | Email attachments (PDF/Word/images) downloaded → text extracted → summarized/classified → stored as `Document` |
| Environment-aware LLM router | ✅ | `production-*` local profiles vs `development-*` in simulation |
| Memory manager (prod vs sim) | ✅ | Persistent SQLite on Backend Mac; ephemeral/resettable in simulation |
| Decision engine | ✅ | Event → proposed action; injection-flagging; approval-gated, never auto-executes |
| Notification dispatcher | ✅ | Real notifications gated by the execution boundary |
| Continuous loop runtime | ✅ | `AutonomousRuntime`: `tick()` + async `run()` with graceful SIGTERM; health snapshot |
| Service supervisor CLI | ✅ | `python -m app.autonomy.service` (run/tick/status/preflight/list) |
| Autonomy launchd service | ✅ | `com.lifeagent.autonomy.plist` (RunAtLoad, KeepAlive, throttle); installed by `install_backend.sh` |
| Autonomy API | ✅ | `GET /api/v1/autonomy/status`, `POST /api/v1/autonomy/tick` (simulation-only) |
| Independence verification | ✅ | `scripts/verify_autonomy.sh` (Section 35.10 checks) |
| Autonomous architecture docs | ✅ | `docs/AUTONOMOUS_ARCHITECTURE.md` (production diagram + service map) |

## Prioritized backlog (next)
1. Backend Mac credential setup (Keychain: mail.com app password, Apple ID app-specific password) + first live sync.
2. First-deployment independence test on the Backend Mac (install → run without Dev Mac).
3. Real secure pairing (X25519 device keys, QR flow, certificate pinning).
4. Phase 3 — EventKit, Share Extension, App Intents, Widgets in iOS app.
5. Multimodal/vision model for scanned PDFs and image attachments (local OCR).

## Known assumptions / limitations
- Single primary user, US jurisdiction, `America/Los_Angeles`, English UI (localization-ready).
- Local AI default; remote AI disabled by default.
- Approval Level 1 (prepare) default; Level 4 actions always require explicit approval.
- No real destructive action during development; all side effects feature-flagged.
- Direct-cable Xcode install is NOT App Store distribution; see `docs/APPLE_PLATFORM_LIMITATIONS.md`.
