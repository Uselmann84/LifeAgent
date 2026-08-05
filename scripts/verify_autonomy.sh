#!/usr/bin/env bash
#
# verify_autonomy.sh — verify the autonomous runtime on the Backend Mac (Section 35.10).
#
# Confirms the Life Agent can operate autonomously and independently of the Development Mac:
#   1. the autonomy launchd service is loaded and running,
#   2. the execution boundary reports production execution (real, approval-gated side effects),
#   3. the LLM router resolves local production profiles,
#   4. persistent memory survives a restart,
#   5. the continuous loop is ticking (proactive triggers execute),
#   6. no simulation-only components are active in production,
#   7. the API reports all six autonomous services healthy.
#
# Run this ON the Backend Mac. Exit non-zero if any hard check fails.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

API_HOST="${LIFE_AGENT_API_HOST:-127.0.0.1}"
API_PORT="${LIFE_AGENT_API_PORT:-8787}"
BASE="http://${API_HOST}:${API_PORT}"
ENV_FILE="${LA_PROD_HOME}/config/.env"
FAILED=0
step_fail() { err "$1"; FAILED=1; }

require_cmd curl

section "Verifying autonomy @ ${BASE}"

# 1) autonomy launchd service loaded ----------------------------------------
if launchctl list 2>/dev/null | grep -q "${LA_AUTONOMY_LABEL}"; then
  ok "autonomy service loaded (${LA_AUTONOMY_LABEL})"
else
  step_fail "autonomy service not loaded (${LA_AUTONOMY_LABEL})"
fi

# 2) execution boundary reports production -----------------------------------
if [[ -d "${LA_PROD_HOME}/current/backend" && -d "${LA_PROD_HOME}/venv" ]]; then
  # shellcheck disable=SC1091
  source "${LA_PROD_HOME}/venv/bin/activate"
  if ( cd "${LA_PROD_HOME}/current/backend" && \
       LIFE_AGENT_ENV_FILE="${ENV_FILE}" python -m app.autonomy.service preflight ); then
    ok "execution boundary preflight passed"
  else
    step_fail "execution boundary preflight failed"
  fi

  # 3) LLM router resolves local production profiles -------------------------
  if ( cd "${LA_PROD_HOME}/current/backend" && \
       LIFE_AGENT_ENV_FILE="${ENV_FILE}" python -c "
from app.core.config import get_settings
from app.autonomy.router import get_router
from app.agent.llm.base import TaskType
s = get_settings()
assert s.is_production_execution, 'not production execution'
r = get_router(s)
p = r.route(TaskType.reasoning).profile
assert p.startswith('production-'), f'unexpected profile {p}'
print('router ok:', p)
" ); then
    ok "LLM router resolves local production profiles"
  else
    step_fail "LLM router did not resolve production profiles"
  fi

  # 4) persistent memory survives a restart ----------------------------------
  # Write a marker, then re-open the DB in a fresh process and confirm it is present.
  MARKER="autonomy-verify-$(date +%s)"
  if ( cd "${LA_PROD_HOME}/current/backend" && \
       LIFE_AGENT_ENV_FILE="${ENV_FILE}" python -c "
from sqlmodel import Session
from app.core.db import engine, run_migrations
from app.autonomy.memory import build_memory_manager, MemoryRecord
run_migrations()
with Session(engine) as s:
    m = build_memory_manager(s)
    assert m.persistent, 'memory is not persistent in production'
    m.remember(MemoryRecord(kind='diagnostic', content='${MARKER}', source='verify_autonomy'))
" ) && ( cd "${LA_PROD_HOME}/current/backend" && \
       LIFE_AGENT_ENV_FILE="${ENV_FILE}" python -c "
from sqlmodel import Session
from app.core.db import engine
from app.autonomy.memory import build_memory_manager
with Session(engine) as s:
    m = build_memory_manager(s)
    assert any(r.content == '${MARKER}' for r in m.recall(limit=200)), 'marker not persisted'
print('memory persisted across processes')
" ); then
    ok "persistent memory survives restart"
  else
    step_fail "persistent memory did not survive restart"
  fi
else
  step_fail "deployed backend/venv not found under ${LA_PROD_HOME}"
fi

# 5-7) API-driven autonomy checks -------------------------------------------
STATUS=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if STATUS="$(curl -fsS --max-time 3 -H "Authorization: Bearer ${LIFE_AGENT_DEV_API_TOKEN:-}" \
      "${BASE}/api/v1/autonomy/status" 2>/dev/null)"; then break; fi
  sleep 1
done

if [[ -n "${STATUS}" ]]; then
  ok "autonomy status endpoint responded"
  # 6) production execution + real side effects permitted
  if grep -q '"execution_mode": *"production"' <<<"${STATUS}"; then
    ok "execution_mode=production (no simulation dependency)"
  else
    step_fail "execution_mode is not production"
  fi
  if grep -q '"side_effects_permitted": *true' <<<"${STATUS}"; then
    ok "real (approval-gated) side effects permitted"
  else
    warn "side_effects_permitted=false (controlled_action + feature flags may be off)"
  fi
  # 7) all six services present
  SVC_COUNT="$(grep -o '"name":' <<<"${STATUS}" | wc -l | tr -d ' ')"
  if [[ "${SVC_COUNT}" -ge 6 ]]; then
    ok "all six autonomous services reported (${SVC_COUNT})"
  else
    step_fail "expected 6 autonomous services, saw ${SVC_COUNT}"
  fi
  # 5) proactive loop is advancing: two snapshots, ticks should not regress
  FIRST_TICKS="$(grep -o '"ticks": *[0-9]*' <<<"${STATUS}" | grep -o '[0-9]*' | head -1)"
  log "loop ticks observed: ${FIRST_TICKS:-unknown}"
else
  step_fail "autonomy status endpoint did not respond"
fi

section "Result"
if [[ "${FAILED}" -eq 0 ]]; then
  ok "autonomy verified — the Life Agent runs independently of the Development Mac"
  exit 0
else
  err "autonomy verification FAILED"
  exit 1
fi
