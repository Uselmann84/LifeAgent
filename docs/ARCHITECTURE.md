# Architecture

Life Agent is a **local-first personal operations platform**. It is intentionally *not* an
unconstrained autonomous chatbot: a language model may *recommend* actions, but deterministic
application code decides whether any action with an external effect may execute.

## 1. Devices (two-Mac + iPhone)

```
┌─────────────────────────┐
│ Development MacBook      │  Claude Code, Xcode, source, mock providers, tests
└────────────┬────────────┘
             │ Secure deployment/admin path (Tailscale, admin/deploy role)
             ▼
┌─────────────────────────┐
│ Backend MacBook Pro M3   │  FastAPI + local AI + DB + jobs + secrets + backups
└────────────┬────────────┘
             │ Secure Life Agent API (Tailscale, iPhone user role)
             ▼
┌─────────────────────────┐
│ iPhone                   │  Native SwiftUI client
└─────────────────────────┘
```

Direct development testing (debug builds only) is a **separate, clearly labeled** path:

```
Development MacBook  ↕  iPhone Debug Build
```

After deployment the Life Agent runs on **Backend Mac + iPhone + Tailscale + Gmail/APNs** only.
The Development MacBook is a build/admin device, never a runtime dependency. See
[DEVELOPMENT_ENVIRONMENT.md](DEVELOPMENT_ENVIRONMENT.md) and
[PRODUCTION_BACKEND_SETUP.md](PRODUCTION_BACKEND_SETUP.md).

## 2. Backend layered architecture

```
apps/ios  ──HTTP/WS──►  backend/api  (FastAPI routes, auth, per-device tokens)
                              │
                              ▼
                      backend/agent  (controlled loop, tools, content-trust)
                              │
        ┌─────────────┬───────┴────────┬───────────────┐
        ▼             ▼                ▼               ▼
 backend/security  integrations   workflows        scheduler
 (approval/       (email/cal      (data-driven     (follow-ups,
  autonomy/        providers +     case templates)   jobs)
  redaction)       mocks)
        │             │                │               │
        └─────────────┴───────┬────────┴───────────────┘
                              ▼
                        backend/core
                (config, db, models, schemas, audit)
```

Key rule: **the agent never calls provider SDKs directly.** It calls typed *tools*
(`backend/agent/tools.py`). Each tool declares its permission requirement, approval requirement,
reversibility, idempotency and audit behavior. See [PERMISSION_MATRIX.md](PERMISSION_MATRIX.md).

## 3. The controlled agent loop

`observe → classify → connect → identify tasks/risks → plan → determine approval level →
request approval (if required) → execute approved action → verify → update tasks/cases/memory →
schedule follow-up → record audit entry`

Deterministic (never delegated to the LLM):
permissions, approval requirements, sending/deleting, deadline math, task-state transitions,
financial limits, recipient verification, audit logging, retries, retention, rate limits.

## 4. Trust model (prompt-injection defense)

Content is tagged with a trust level (highest → lowest authority):

1. System policy
2. Verified user instruction
3. Approved workflow policy
4. Trusted structured integration data
5. **Untrusted external text** (email bodies, attachments, web pages, documents)
6. Model-generated content

Untrusted content can **never** change permissions, approve actions, reveal secrets, override
user rules, initiate payments, send communications, delete data, or modify autonomy settings.
Tool parameters are assembled and validated by application code, not lifted verbatim from
untrusted text. See [THREAT_MODEL.md](THREAT_MODEL.md).

## 5. Data & persistence

- **Domain-first storage** (not chat blobs): explicit entities in `backend/core/models.py`.
- SQLite for the prototype behind a SQLAlchemy/SQLModel abstraction → PostgreSQL + pgvector in production.
- Versioned migrations in `backend/migrations/`.
- At-rest encryption for sensitive fields; secrets in macOS/iOS Keychain, never in DB or Git.

## 6. Model routing

A `LLMProvider` protocol (`backend/agent/llm/base.py`) abstracts all inference. Providers:
`mock` (default in dev), `ollama`, `openai_compatible`, `mlx`, optional remote fallback (off by
default). Separate model *profiles* for reasoning, fast classification, embeddings, document/OCR —
selected by profile name, never by a hard-coded model string. See [DOMAIN_MODEL.md](DOMAIN_MODEL.md)
and the model routing section of [PRODUCTION_BACKEND_SETUP.md](PRODUCTION_BACKEND_SETUP.md).

## 7. Safety modes & environments

| Mode | Real read | Real write | Default |
|------|-----------|-----------|---------|
| `demo` | ❌ (seeded) | ❌ | ✅ |
| `readonly_personal` | ✅ | ❌ | |
| `controlled_action` | ✅ | ✅ (approval-gated, feature-flagged) | |

Environments (`development`, `testing`, `staging`, `production`) each own their own config, DB,
keys, credentials, data dirs, and feature flags. See
[ENVIRONMENT_CONFIGURATION.md](ENVIRONMENT_CONFIGURATION.md).

## 8. Offline behavior

The iPhone app caches the latest briefing, tasks, cases, pending approvals and selected documents.
Actions requiring the backend are queued and clearly marked. Backend-online/offline and
backend-version/API-version compatibility are surfaced in the UI.
