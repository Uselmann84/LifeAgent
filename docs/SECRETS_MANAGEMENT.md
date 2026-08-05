# Secrets Management

**Principle:** production secrets are created or imported **directly on the Backend Mac** and stored
in the macOS Keychain. The Development Mac and Git repository receive only *public* configuration.

## Secret inventory (Backend Mac / Keychain)
- Email OAuth refresh tokens (Gmail; future providers).
- Database encryption key.
- Application master key.
- API signing keys (device token signing).
- Device-pairing secrets.
- Push-notification credentials (APNs).
- Backup encryption key.
- Remote AI provider key (only if remote AI is ever enabled; off by default).
- Private TLS keys.

## Storage rules
- Prefer **macOS Keychain**. Where a Keychain approach is unsuitable, use an encrypted config file
  with restricted permissions (`chmod 600`, owner-only).
- On iOS, per-device credentials live in the **iOS Keychain**. The iPhone **never** receives the
  Gmail refresh token — the backend talks to Gmail on its behalf.
- **Never** place secrets in: Swift source, iOS resources, Git history, shell scripts, Docker
  images, release archives, or documentation.

## `.env` policy
- `.env.example` is committed and contains **no real secrets** (placeholders only).
- `.env` is git-ignored. Development uses non-secret dev defaults (mock providers).
- The config loader reads secrets from the Keychain in production and from `.env`/env vars in
  development.

## Production secret initialization (on the Backend Mac)
`scripts/init_production_secrets.sh` (run on the Backend Mac only) generates/imports each secret
into the Keychain, printing which items exist without echoing values. It is idempotent and never
overwrites an existing secret unless `--rotate <name>` is passed.

## Rotation
- Master/backup/signing keys are rotatable via a documented procedure; rotating the signing key
  forces re-pairing (by design).
- OAuth tokens refresh automatically; a revoked token requires re-authorization from the Backend
  Mac.

## Secret scanning
`scripts/validate_release.sh` runs a secret-scan step (regex for tokens/keys/PEM headers) and fails
the build if a candidate secret is found in tracked files. CI must not include production secrets.

## Logs & audit
Structured logging redacts secrets, OAuth tokens, full email bodies, and sensitive document text by
default. Diagnostic/support packages exclude secrets, tokens, keys, personal email bodies, and
document contents. See [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md).
