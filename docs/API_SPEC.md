# API Specification (v1)

Base path: `/api/v1`. All responses JSON. Auth: `Authorization: Bearer <device-token>`
(dev shared token in Demo Mode; per-device paired credential in production). Roles enforced per
route (see [PERMISSION_MATRIX.md](PERMISSION_MATRIX.md)).

Interactive schema: `GET /docs` (Swagger) and `GET /openapi.json`.

## Health & version
- `GET /api/v1/health` → `{ status, mode, environment, backend_version, api_version,
  db_schema_version, uptime_seconds }`
- `GET /api/v1/health/model` → `{ provider, profiles_loaded[], reachable(bool), latency_ms?,
  detail }`

## Today / briefing
- `GET /api/v1/today` → `{ generated_at, top_priorities[], deadlines[], important_email[],
  waiting_for[], appointments[], pending_approvals[], suggested_actions[], collapsed_low_priority[] }`

## Agent chat
- `POST /api/v1/agent/chat` body `{ message, context? }` →
  `{ reply, found[], recommendations[], prepared[], requires_approval[], completed[],
  unverified[], created_approval_ids[] }`
  The reply always separates *found / recommend / prepared / needs-approval / completed /
  unverified*. No hidden chain-of-thought is returned.

## Tasks
- `GET /api/v1/tasks` · `POST /api/v1/tasks` · `GET /api/v1/tasks/{id}` ·
  `PATCH /api/v1/tasks/{id}`

## Cases
- `GET /api/v1/cases` (filter `?status=`) · `POST /api/v1/cases` · `GET /api/v1/cases/{id}` ·
  `PATCH /api/v1/cases/{id}`
- `POST /api/v1/cases/from-email/{email_id}` → creates a case from an email.

## Email (mock provider in Demo/dev)
- `GET /api/v1/email/threads` · `GET /api/v1/email/threads/{id}`
- `POST /api/v1/email/search` body `{ query }` (natural language)
- `POST /api/v1/email/draft` body `{ thread_id?, to[], subject, intent }` → draft (no send)
- `POST /api/v1/email/{id}/classify`

## Waiting-for
- `GET /api/v1/waiting` → items where someone owes the user a response, with expected/escalation dates.

## Approvals
- `GET /api/v1/approvals` (filter `?status=pending`)
- `GET /api/v1/approvals/{id}`
- `POST /api/v1/approvals/{id}/approve` body `{ payload_hash }` →
  400 if hash mismatch (invalidated) / 409 if expired.
- `POST /api/v1/approvals/{id}/reject` body `{ reason? }`
- `POST /api/v1/approvals/{id}/revise` body `{ instructions }`

## Activity / audit
- `GET /api/v1/activity` (paginated) → redacted `AgentAction` entries.

## Memory
- `GET /api/v1/memory` · `POST /api/v1/memory` · `DELETE /api/v1/memory/{id}`

## Calendar / reminders (drafts in Phase 1)
- `POST /api/v1/calendar/draft` · `POST /api/v1/reminders/draft`

## Pairing (scaffold)
- `POST /api/v1/pairing/start` (owner/admin) → `{ code, expires_at, qr_payload }`
- `POST /api/v1/pairing/complete` body `{ code, device_name, public_key, role }` →
  `{ device_id, backend_public_key }`
- `POST /api/v1/pairing/revoke/{device_id}` (owner)

## Admin (deploy_admin / owner roles only)
- `GET /api/v1/admin/status` · `POST /api/v1/admin/emergency-stop` · `GET /api/v1/admin/devices`

## Error shape
`{ error: { code, message, correlation_id } }`. Secrets/tokens/email bodies are never included in
error payloads.

## Versioning
`api_version = "v1"`. The iPhone app sends `X-App-Version` and reads `backend_version` +
`api_version` from `/health`; incompatible pairs surface a clear upgrade prompt.
