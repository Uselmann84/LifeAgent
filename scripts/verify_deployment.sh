#!/usr/bin/env bash
#
# verify_deployment.sh — post-deploy health check on the Backend Mac.
# Confirms the service is loaded, the API answers /health, the model provider
# reports healthy, and the DB schema matches the deployed backend.
# Exit non-zero if any check fails (used by update/rollback for auto-rollback).

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

API_HOST="${LIFE_AGENT_API_HOST:-127.0.0.1}"
API_PORT="${LIFE_AGENT_API_PORT:-8787}"
BASE="http://${API_HOST}:${API_PORT}"
FAILED=0
step_fail() { err "$1"; FAILED=1; }

section "Verifying deployment @ ${BASE}"

# 1) launchd loaded ----------------------------------------------------------
if launchctl list 2>/dev/null | grep -q "${LA_LAUNCHD_LABEL}"; then
  ok "launchd service loaded"
else
  warn "launchd service not listed (may be running manually)"
fi

# 2) /health responds, allowing a short warm-up window -----------------------
require_cmd curl
HEALTH=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if HEALTH="$(curl -fsS --max-time 3 "${BASE}/health" 2>/dev/null)"; then break; fi
  sleep 1
done
if [[ -n "${HEALTH}" ]]; then
  ok "/health OK: ${HEALTH}"
else
  step_fail "/health did not respond"
fi

# 3) model health ------------------------------------------------------------
if MODEL="$(curl -fsS --max-time 5 "${BASE}/health/model" 2>/dev/null)"; then
  ok "/health/model OK: ${MODEL}"
else
  warn "/health/model not reachable (non-fatal)"
fi

# 4) schema/version consistency ---------------------------------------------
if [[ -d "${LA_PROD_HOME}/current/backend" && -d "${LA_PROD_HOME}/venv" ]]; then
  # shellcheck disable=SC1091
  source "${LA_PROD_HOME}/venv/bin/activate"
  if ( cd "${LA_PROD_HOME}/current/backend" && \
       LIFE_AGENT_ENV_FILE="${LA_PROD_HOME}/config/.env" python -c "
from app.core import versions as v
from app.core.db import current_schema_version
assert current_schema_version() == v.DB_SCHEMA_VERSION, 'schema mismatch'
print('schema', v.DB_SCHEMA_VERSION, 'ok')
" ); then
    ok "schema/version consistent"
  else
    step_fail "schema/version check failed"
  fi
fi

section "Result"
if [[ "${FAILED}" -eq 0 ]]; then
  ok "deployment verified"
  exit 0
else
  err "deployment verification FAILED"
  exit 1
fi
