#!/usr/bin/env bash
#
# collect_diagnostics.sh — gather a redacted diagnostics bundle for support/
# debugging on the Backend Mac. Never includes secrets, .env values, personal
# email content, or database contents — only versions, health, logs (tail),
# service status, and disk usage. Log lines are passed through a redactor.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${LA_PROD_HOME}/logs/diagnostics-${TS}"
mkdir -p "${OUT}"

section "Collecting diagnostics -> ${OUT}"

# System ---------------------------------------------------------------------
{
  echo "collected_at: ${TS}"
  echo "host: $(hostname)"
  echo "os: $(sw_vers 2>/dev/null | tr '\n' ' ')"
  echo "arch: $(uname -m)"
  echo "uptime: $(uptime)"
} > "${OUT}/system.txt"

# Active release + versions --------------------------------------------------
{
  if [[ -L "${LA_PROD_HOME}/current" ]]; then
    echo "active_release: $(basename "$(readlink "${LA_PROD_HOME}/current")")"
  fi
  if [[ -d "${LA_PROD_HOME}/venv" && -d "${LA_PROD_HOME}/current/backend" ]]; then
    # shellcheck disable=SC1091
    source "${LA_PROD_HOME}/venv/bin/activate"
    ( cd "${LA_PROD_HOME}/current/backend" && python -c "
from app.core import versions as v
print('backend', v.BACKEND_VERSION)
print('api', v.API_VERSION)
print('schema', v.DB_SCHEMA_VERSION)
" ) 2>/dev/null || echo "version query failed"
  fi
} > "${OUT}/versions.txt"

# Service status -------------------------------------------------------------
launchctl list 2>/dev/null | grep -i lifeagent > "${OUT}/launchd.txt" || true

# Health endpoints -----------------------------------------------------------
BASE="http://${LIFE_AGENT_API_HOST:-127.0.0.1}:${LIFE_AGENT_API_PORT:-8787}"
{
  echo "GET ${BASE}/health"
  curl -fsS --max-time 3 "${BASE}/health" 2>/dev/null || echo "(unreachable)"
  echo
  echo "GET ${BASE}/health/model"
  curl -fsS --max-time 5 "${BASE}/health/model" 2>/dev/null || echo "(unreachable)"
} > "${OUT}/health.txt"

# Disk usage -----------------------------------------------------------------
du -sh "${LA_PROD_HOME}"/* 2>/dev/null > "${OUT}/disk.txt" || true

# Redacted log tails ---------------------------------------------------------
# Redact anything resembling emails, tokens, or PEM material before saving.
redact() {
  sed -E \
    -e 's/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/<email>/g' \
    -e 's/(token|secret|password|api[_-]?key)[":= ]+[^ ",}]+/\1=<redacted>/gI' \
    -e 's/-----BEGIN[^-]+-----/<redacted-key>/g'
}
mkdir -p "${OUT}/logs"
if [[ -d "${LA_PROD_HOME}/logs" ]]; then
  find "${LA_PROD_HOME}/logs" -maxdepth 1 -name '*.log' -print0 2>/dev/null | \
  while IFS= read -r -d '' f; do
    tail -n 500 "$f" | redact > "${OUT}/logs/$(basename "$f")"
  done
fi

# Bundle ---------------------------------------------------------------------
BUNDLE="${LA_PROD_HOME}/logs/diagnostics-${TS}.tar.gz"
tar -C "${LA_PROD_HOME}/logs" -czf "${BUNDLE}" "diagnostics-${TS}"
rm -rf "${OUT}"

section "Done"
ok "diagnostics bundle: ${BUNDLE}"
warn "review before sharing; it contains redacted logs and host metadata only"
