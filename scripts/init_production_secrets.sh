#!/usr/bin/env bash
#
# init_production_secrets.sh — create/import production secrets into the macOS
# Keychain ON the Backend Mac. Secrets NEVER live in Git, source, .env, or a
# release archive. This script only stores values you type interactively; it
# does not print them and does not accept them as arguments.
#
# Stored as generic-password items under service "life-agent".

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_cmd security   # macOS keychain CLI

SERVICE="life-agent"
ACCOUNT_PREFIX="${USER}"

[[ "$(uname)" == "Darwin" ]] || die "Keychain storage requires macOS"

section "Initialize production secrets (macOS Keychain)"
warn "You will be prompted for each secret. Input is hidden and never logged."
echo

# key -> human description
SECRET_KEYS=(
  "api_token:Production API bearer token (iPhone <-> backend auth)"
  "email_password:mail.com email/app password (IMAP + SMTP)"
  "apple_app_password:Apple ID app-specific password (iCloud Calendar / CalDAV)"
  "remote_ai_api_key:Optional remote AI provider key (leave blank to skip)"
)

set_secret() {
  local key="$1" desc="$2" val=""
  local account="${ACCOUNT_PREFIX}.${key}"
  if security find-generic-password -s "${SERVICE}" -a "${account}" >/dev/null 2>&1; then
    if ! confirm "Secret '${key}' already exists. Replace it?"; then
      log "keeping existing '${key}'"; return 0
    fi
  fi
  # Read hidden.
  read -r -s -p "${desc}: " val; echo
  if [[ -z "${val}" ]]; then
    warn "skipped '${key}' (empty)"; return 0
  fi
  security add-generic-password -U -s "${SERVICE}" -a "${account}" -w "${val}" \
    && ok "stored '${key}'"
  val=""   # clear
}

for entry in "${SECRET_KEYS[@]}"; do
  set_secret "${entry%%:*}" "${entry#*:}"
done

echo
section "Done"
ok "secrets stored under Keychain service '${SERVICE}'"
log "the backend reads these at runtime via the Keychain; nothing was written to disk"
