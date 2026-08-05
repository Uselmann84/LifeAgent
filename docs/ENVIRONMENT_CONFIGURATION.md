# Environment Configuration

Four explicitly separated environments; each owns its own configuration, DB, keys, credentials,
data dirs, logging, model config, backup location, and feature flags.

| Env | Where it runs | Mode default | LLM | Real side effects |
|-----|---------------|--------------|-----|-------------------|
| `development` | Development Mac | `demo` | `mock` | off |
| `testing` | CI / Development Mac | `demo` | `mock` | off (mocks only) |
| `staging` | Backend Mac (optional) | `readonly_personal` | local | off |
| `production` | Backend Mac | `controlled_action` | local | approval-gated + feature-flagged |

## Backend configuration
Driven by env vars / `.env` (see [`.env.example`](../.env.example)) resolved in
`backend/core/config.py`. Key variables: `LIFE_AGENT_ENV`, `LIFE_AGENT_MODE`,
`LIFE_AGENT_DATABASE_URL`, data/log dirs, `LIFE_AGENT_DEFAULT_AUTONOMY_LEVEL`, feature flags,
`LIFE_AGENT_LLM_PROVIDER` + model profile names.

### Guardrails
- `LIFE_AGENT_ENV=development` **rejects** a `postgres...production` DB URL (prevents the Development
  Mac from touching the production database).
- `demo` mode ignores real-integration flags entirely.
- Feature flags for real email send / calendar write / spam-move / remote AI default to `false`
  everywhere and are only meaningful in `controlled_action`.
- Model *profiles* (not model names) are configured per environment so dev and prod hardware differ
  safely.

## iOS configuration (`.xcconfig`, no secrets)
```
Config/Debug.xcconfig     BACKEND_ENV = development   ALLOW_ENV_SWITCHER = YES
Config/Internal.xcconfig  BACKEND_ENV = staging       ALLOW_ENV_SWITCHER = YES
Config/Release.xcconfig   BACKEND_ENV = production     ALLOW_ENV_SWITCHER = NO
```
- **No IP addresses or secrets** in `.xcconfig`. The actual backend host + pinned key come from the
  secure **pairing** flow / connection profile, not source.
- Release builds hide the environment switcher and all debug controls and default to Production.
- A connection profile stores: display name, base URL (from pairing/MagicDNS), environment,
  backend public key, paired credential (Keychain), backend version, last-successful-connection,
  status.

## Never
- Never use production credentials in automated testing.
- Never copy production secrets into Git or onto the Development Mac.
- Never let the Development Mac connect to/modify the production DB by default.
