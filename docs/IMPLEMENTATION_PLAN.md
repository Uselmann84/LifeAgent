# Implementation Plan

Deliver in controlled phases. Keep the app runnable after each milestone. Run tests after every
material change. Never reduce security to simplify implementation.

## Phase 0 — Architecture & foundation ✅
Docs (this set), monorepo structure, config + environment separation, domain model, versioned
migrations, mock providers, approval-policy engine, content-trust module, audit log, local
validation script, `PROJECT_STATUS.md`.

## Phase 1 — Working vertical slice ✅ (this deliverable)
Backend: health + model-health endpoints, controlled agent loop (mock LLM), Today briefing, task &
case creation, demo email inbox, agent recommendation, payload-bound approval flow, audit endpoint,
memory endpoints, waiting-for. iOS: SwiftUI shell (Today/Agent/Approvals/Cases/More), backend
connection profile + environment banner, offline cache scaffold. Tests: approval policy, approval
invalidation, prompt injection, deadline extraction.

## Phase 2 — Gmail read-only integration
OAuth (completed on / associated with Backend Mac; tokens never reach iPhone), sync, thread
summaries, importance classification, task & deadline extraction, waiting-for detection,
email→case conversion, draft generation (no send). Dedicated test account + mock default.

## Phase 3 — Calendar, reminders & capture
EventKit read + approval-gated writes, reminders, calendar views, Share Extension, document scan,
voice capture, App Intents, widgets.

## Phase 4 — Controlled email actions
Approval-bound sending, archive/label, conservative spam review, provider confirmation + message
IDs, follow-up scheduling, duplicate-send prevention (idempotency keys). Feature-flagged until
tests pass.

## Phase 5 — Documents & workflow templates
Document inbox, local OCR, extraction, case linking; workflow templates: vehicle registration,
warranty, insurance, tax documents, subscription cancellation, purchase return/refund
(data-driven YAML/JSON).

## Phase 6 — Proactive life administration
Daily briefing, weekly/monthly reviews, stale-case detection, recurring obligations, personalized
rules, improved memory, advanced follow-up engine.

## Two-Mac deployment track (parallel, Phase 0/1)
Environment separation, deployment package scripts, launchd auto-start template, role separation,
secrets-on-Backend-Mac, pairing scaffold, first-deployment independence test. See
[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## Working method
Inspect before overwriting; document major decisions; keep `PROJECT_STATUS.md` current; one
vertical slice at a time; fix build/test failures before moving on; no credentials in code; mocks
until real integrations are intentionally enabled; never claim an integration works untested; mark
assumptions; prefer maintainable over clever.
