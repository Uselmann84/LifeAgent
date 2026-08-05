#!/usr/bin/env bash
#
# validate_release.sh — gate a release before it can be built or deployed.
# Runs: lint (ruff), tests (pytest), a secret scan, and a schema/version check.
# Exit non-zero (and stop the pipeline) if any required check fails.
#
# This is intended to be safe to run on the Development Mac.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

FAILED=0
fail_step() { err "$1"; FAILED=1; }

section "Validating release"
log "backend version: $(backend_version)"

cd "${LA_BACKEND_DIR}"
activate_venv

# 1) Lint -------------------------------------------------------------------
section "Lint (ruff)"
if command -v ruff >/dev/null 2>&1; then
  if ruff check app tests; then ok "ruff clean"; else fail_step "ruff reported issues"; fi
else
  fail_step "ruff not installed (pip install ruff)"
fi

# 2) Tests ------------------------------------------------------------------
section "Tests (pytest)"
if command -v pytest >/dev/null 2>&1; then
  if pytest -q; then ok "tests passed"; else fail_step "tests failed"; fi
else
  fail_step "pytest not installed"
fi

# 3) Secret scan ------------------------------------------------------------
# Fail if anything that looks like a real credential is committed to source.
# .env files and the local venv/data are intentionally excluded.
section "Secret scan"
SECRET_PATTERNS='(-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{10,}|gh[pousr]_[0-9A-Za-z]{30,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,})'
if git -C "${LA_REPO_ROOT}" rev-parse >/dev/null 2>&1; then
  SCAN_FILES="$(git -C "${LA_REPO_ROOT}" ls-files -- ':!:*.env' ':!:**/.venv/**')"
else
  SCAN_FILES="$(find "${LA_REPO_ROOT}" -type f -not -path '*/.venv/*' -not -path '*/data/*' -not -name '*.env')"
fi
HITS=0
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  full="${LA_REPO_ROOT}/$f"; [[ -f "$full" ]] || full="$f"
  if grep -EInq "${SECRET_PATTERNS}" "$full" 2>/dev/null; then
    err "possible secret in: $f"; HITS=$((HITS+1))
  fi
done <<< "${SCAN_FILES}"
if [[ "${HITS}" -eq 0 ]]; then ok "no secrets detected"; else fail_step "${HITS} possible secret(s) found"; fi

# 4) Schema / version consistency ------------------------------------------
section "Schema + version check"
if python -c "
import sys
from app.core import versions as v
from app.core.db import current_schema_version, run_migrations
run_migrations()
got = current_schema_version()
if got != v.DB_SCHEMA_VERSION:
    print(f'schema mismatch: db={got} expected={v.DB_SCHEMA_VERSION}'); sys.exit(1)
print(f'backend={v.BACKEND_VERSION} api={v.API_VERSION} schema={v.DB_SCHEMA_VERSION}')
"; then ok "schema/version consistent"; else fail_step "schema/version check failed"; fi

# Result --------------------------------------------------------------------
section "Result"
if [[ "${FAILED}" -eq 0 ]]; then
  ok "release validation PASSED"
  exit 0
else
  die "release validation FAILED — do not deploy"
fi
