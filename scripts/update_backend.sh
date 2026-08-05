#!/usr/bin/env bash
#
# update_backend.sh — safely update an existing install to a new release.
# Flow: backup -> stop service -> install deps -> migrate -> flip symlink ->
# start service -> verify. On any failure after the flip, auto-rollback.
#
# Run ON the Backend Mac from an unpacked release:
#   ./scripts/update_backend.sh vX.Y.Z

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

VERSION="${1:-$(backend_version)}"
VERSION="${VERSION#v}"
TAG="lifeagent-v${VERSION}"
RELEASE_DIR="${LA_PROD_HOME}/releases/${TAG}"
VENV="${LA_PROD_HOME}/venv"
ENV_FILE="${LA_PROD_HOME}/config/.env"

section "Updating to ${TAG}"

PREVIOUS="none"
[[ -L "${LA_PROD_HOME}/current" ]] && PREVIOUS="$(readlink "${LA_PROD_HOME}/current")"
log "current active release: $(basename "${PREVIOUS}")"

# 1) Stage release if needed -------------------------------------------------
SRC_ROOT="$(cd "${LA_SCRIPT_DIR}/.." && pwd)"
if [[ ! -d "${RELEASE_DIR}" ]]; then
  log "staging release into ${RELEASE_DIR}"
  mkdir -p "${RELEASE_DIR}"
  tar -C "${SRC_ROOT}" --exclude='.venv' --exclude='data' --exclude='logs' \
    -cf - . | tar -C "${RELEASE_DIR}" -xf -
fi

# 2) Backup ------------------------------------------------------------------
"${LA_SCRIPT_DIR}/backup_before_update.sh" >/dev/null

# 3) Stop service ------------------------------------------------------------
section "Stopping service"
launchctl stop "${LA_LAUNCHD_LABEL}" 2>/dev/null || true

# 4) Install deps + migrate --------------------------------------------------
section "Installing deps + migrating"
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
python -m pip install --quiet "${RELEASE_DIR}/backend" || die "dependency install failed"
( cd "${RELEASE_DIR}/backend" && \
  LIFE_AGENT_ENV_FILE="${ENV_FILE}" python -c "from app.core.db import run_migrations; run_migrations()" ) \
  || die "migration failed (data backed up; not yet activated)"

# 5) Flip symlink ------------------------------------------------------------
section "Activating ${TAG}"
ln -sfn "${RELEASE_DIR}" "${LA_PROD_HOME}/current"
ln -sfn "${RELEASE_DIR}/backend/app" "${LA_PROD_HOME}/app"

# 6) Start + verify (auto-rollback on failure) ------------------------------
section "Starting service"
launchctl start "${LA_LAUNCHD_LABEL}" 2>/dev/null || true

if "${LA_SCRIPT_DIR}/verify_deployment.sh"; then
  ok "update to ${TAG} succeeded"
  # record success
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) activated ${TAG}" >> "${LA_PROD_HOME}/releases/history.log"
else
  err "verification failed — rolling back"
  if [[ "${PREVIOUS}" != "none" ]]; then
    ln -sfn "${PREVIOUS}" "${LA_PROD_HOME}/current"
    ln -sfn "${PREVIOUS}/backend/app" "${LA_PROD_HOME}/app"
    launchctl kickstart -k "gui/$(id -u)/${LA_LAUNCHD_LABEL}" 2>/dev/null || true
    die "rolled back to $(basename "${PREVIOUS}")"
  else
    die "no previous release to roll back to"
  fi
fi
