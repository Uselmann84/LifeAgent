# Operational Scripts

Bash scripts for building, deploying, and operating the Life Agent backend
across the two-Mac topology. All scripts source [lib.sh](lib.sh) for shared
config and helpers, use `set -euo pipefail`, and print clear, colored status.

## Where each script runs

| Script | Runs on | Purpose |
| --- | --- | --- |
| `validate_release.sh` | Development Mac | Lint + tests + secret scan + schema check. Gates everything else. |
| `build_backend_release.sh` | Development Mac | Package a versioned, checksummed release under `releases/`. |
| `deploy_to_backend.sh` | Development Mac | Ship a release to the Backend Mac over Tailscale and verify its checksum. |
| `install_backend.sh` | Backend Mac | Idempotent first-time install (dirs, venv, deps, migrate, symlink, launchd). |
| `update_backend.sh` | Backend Mac | Backup → migrate → flip symlink → verify, with auto-rollback on failure. |
| `rollback_backend.sh` | Backend Mac | Manually revert to a previous known-good release. |
| `backup_before_update.sh` | Backend Mac | Timestamped, checksummed snapshot of `data/` + `config/`. |
| `verify_deployment.sh` | Backend Mac | Post-deploy health checks (service, `/health`, model, schema). |
| `uninstall_backend.sh` | Backend Mac | Remove service + code; `--purge` also deletes data (guarded). |
| `init_production_secrets.sh` | Backend Mac | Store secrets in the macOS Keychain (interactive, hidden input). |
| `collect_diagnostics.sh` | Backend Mac | Redacted diagnostics bundle (versions, health, log tails). |

## Typical flow

```bash
# On the Development Mac
./scripts/validate_release.sh
./scripts/build_backend_release.sh
export LA_BACKEND_SSH="lifeagent@backend-mac.tailnet.ts.net"
./scripts/deploy_to_backend.sh

# On the Backend Mac (from the unpacked release)
./scripts/init_production_secrets.sh      # first time only
./scripts/install_backend.sh 0.1.0        # first time
# ...later releases:
./scripts/update_backend.sh 0.2.0         # auto-rolls back if verify fails
```

## Configuration (environment variables)

| Variable | Default | Meaning |
| --- | --- | --- |
| `LA_PROD_HOME` | `~/LifeAgent` | Production home on the Backend Mac. |
| `LA_BACKEND_SSH` | _(unset)_ | `user@host` ssh target for `deploy_to_backend.sh`. |
| `LIFE_AGENT_API_HOST` | `127.0.0.1` | Host used by health checks. |
| `LIFE_AGENT_API_PORT` | `8787` | Port used by health checks. |

## Safety guarantees

- **No secrets in Git or releases.** `validate_release.sh` and
  `build_backend_release.sh` scan for and refuse credential-like content;
  secrets live only in the Keychain via `init_production_secrets.sh`.
- **No data loss on update.** `update_backend.sh` always backs up first and
  auto-rolls back if verification fails.
- **Idempotent installs.** `install_backend.sh` never overwrites existing
  data, config, or secrets.
- **Redacted diagnostics.** `collect_diagnostics.sh` strips emails, tokens,
  and key material from log tails before bundling.
