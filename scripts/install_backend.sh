#!/usr/bin/env bash
#
# install_backend.sh — first-time / idempotent install on the Backend Mac.
# Safe to run repeatedly: it never overwrites existing production data or
# secrets. Creates the directory tree, a venv, installs deps, runs migrations,
# activates the release via the `current` symlink, and installs launchd.
#
# Run this ON the Backend Mac, from an unpacked release:
#   ./scripts/install_backend.sh [vX.Y.Z]

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

VERSION="${1:-$(backend_version)}"
VERSION="${VERSION#v}"
TAG="lifeagent-v${VERSION}"

section "Installing ${TAG} on $(hostname)"

# 0) Host sanity checks ------------------------------------------------------
[[ "$(uname)" == "Darwin" ]] || die "Backend host must be macOS"
if [[ "$(uname -m)" != "arm64" ]]; then
  warn "expected Apple Silicon (arm64); continuing anyway"
fi
require_cmd python3

# 1) Directory tree (never clobber data/secrets) -----------------------------
section "Directory tree at ${LA_PROD_HOME}"
for d in app config data/database data/documents data/vector_store data/cache \
         models logs backups releases; do
  mkdir -p "${LA_PROD_HOME}/${d}"
done
ok "directories present"

# 2) Place the release -------------------------------------------------------
RELEASE_DIR="${LA_PROD_HOME}/releases/${TAG}"
SRC_ROOT="$(cd "${LA_SCRIPT_DIR}/.." && pwd)"   # unpacked release root
if [[ ! -d "${RELEASE_DIR}" ]]; then
  log "copying release into ${RELEASE_DIR}"
  mkdir -p "${RELEASE_DIR}"
  tar -C "${SRC_ROOT}" --exclude='.venv' --exclude='data' --exclude='logs' \
    -cf - . | tar -C "${RELEASE_DIR}" -xf -
else
  warn "release ${TAG} already staged; leaving as-is"
fi

# 3) Virtualenv + production deps -------------------------------------------
section "Python environment"
VENV="${LA_PROD_HOME}/venv"
if [[ ! -d "${VENV}" ]]; then
  python3 -m venv "${VENV}"; ok "created venv"
fi
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
python -m pip install --quiet --upgrade pip
if [[ -f "${RELEASE_DIR}/backend/pyproject.toml" ]]; then
  python -m pip install --quiet "${RELEASE_DIR}/backend"
  ok "installed backend package"
else
  die "pyproject.toml missing in release"
fi

# 4) Config (non-secret) -----------------------------------------------------
section "Configuration"
ENV_FILE="${LA_PROD_HOME}/config/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${RELEASE_DIR}/.env.example" "${ENV_FILE}" 2>/dev/null || true
  warn "created ${ENV_FILE} from template — review it and set LIFE_AGENT_ENVIRONMENT=production"
  warn "secrets belong in the Keychain, NOT in this file (see init_production_secrets.sh)"
else
  ok "existing config preserved"
fi

# 5) Activate via symlink ----------------------------------------------------
section "Activation"
ln -sfn "${RELEASE_DIR}" "${LA_PROD_HOME}/current"
ln -sfn "${RELEASE_DIR}/backend/app" "${LA_PROD_HOME}/app"
ok "current -> ${RELEASE_DIR}"

# 6) Migrations --------------------------------------------------------------
section "Database migrations"
( cd "${RELEASE_DIR}/backend" && \
  LIFE_AGENT_ENV_FILE="${ENV_FILE}" python -c "from app.core.db import run_migrations; run_migrations(); print('migrations ok')" )

# 7) launchd service ---------------------------------------------------------
section "launchd service"
PLIST_SRC="${RELEASE_DIR}/infrastructure/launchd/${LA_LAUNCHD_LABEL}.plist"
if [[ -f "${PLIST_SRC}" ]]; then
  mkdir -p "${HOME}/Library/LaunchAgents"
  sed -e "s#{{LA_PROD_HOME}}#${LA_PROD_HOME}#g" \
      -e "s#{{LA_VENV}}#${VENV}#g" \
      "${PLIST_SRC}" > "${LA_LAUNCHD_PLIST}"
  launchctl unload "${LA_LAUNCHD_PLIST}" 2>/dev/null || true
  launchctl load "${LA_LAUNCHD_PLIST}"
  ok "launchd service installed (${LA_LAUNCHD_LABEL})"
else
  warn "launchd template not found; skipping service install"
fi

# 8) autonomy service --------------------------------------------------------
section "autonomy service"
AUTONOMY_SRC="${RELEASE_DIR}/infrastructure/launchd/${LA_AUTONOMY_LABEL}.plist"
if [[ -f "${AUTONOMY_SRC}" ]]; then
  mkdir -p "${HOME}/Library/LaunchAgents"
  sed -e "s#{{LA_PROD_HOME}}#${LA_PROD_HOME}#g" \
      -e "s#{{LA_VENV}}#${VENV}#g" \
      "${AUTONOMY_SRC}" > "${LA_AUTONOMY_PLIST}"
  launchctl unload "${LA_AUTONOMY_PLIST}" 2>/dev/null || true
  launchctl load "${LA_AUTONOMY_PLIST}"
  ok "autonomy service installed (${LA_AUTONOMY_LABEL})"
else
  warn "autonomy template not found; skipping autonomy install"
fi

section "Done"
ok "installed ${TAG}"
log "start:  launchctl start ${LA_LAUNCHD_LABEL}"
log "verify: ./scripts/verify_deployment.sh"
