# shellcheck shell=bash
# Shared helpers and configuration for Life Agent operational scripts.
# Source this from other scripts:  source "$(dirname "$0")/lib.sh"

set -euo pipefail

# --- Repo layout (Development Mac) ------------------------------------------
LA_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LA_REPO_ROOT="$(cd "${LA_SCRIPT_DIR}/.." && pwd)"
LA_BACKEND_DIR="${LA_REPO_ROOT}/backend"
LA_RELEASES_DIR="${LA_REPO_ROOT}/releases"
LA_INFRA_DIR="${LA_REPO_ROOT}/infrastructure"

# --- Production layout (Backend Mac) ----------------------------------------
# Home of the deployed system on the Backend MacBook Pro M3.
LA_PROD_HOME="${LA_PROD_HOME:-${HOME}/LifeAgent}"
LA_LAUNCHD_LABEL="com.lifeagent.backend"
LA_LAUNCHD_PLIST="${HOME}/Library/LaunchAgents/${LA_LAUNCHD_LABEL}.plist"
LA_AUTONOMY_LABEL="com.lifeagent.autonomy"
LA_AUTONOMY_PLIST="${HOME}/Library/LaunchAgents/${LA_AUTONOMY_LABEL}.plist"

# SSH target for pushing a release from Dev Mac -> Backend Mac.
# Example:  export LA_BACKEND_SSH="lifeagent@backend-mac.tailnet.ts.net"
LA_BACKEND_SSH="${LA_BACKEND_SSH:-}"

# --- Pretty output ----------------------------------------------------------
if [[ -t 1 ]]; then
  LA_C_RESET="\033[0m"; LA_C_RED="\033[31m"; LA_C_GRN="\033[32m"
  LA_C_YLW="\033[33m"; LA_C_BLU="\033[34m"; LA_C_BOLD="\033[1m"
else
  LA_C_RESET=""; LA_C_RED=""; LA_C_GRN=""; LA_C_YLW=""; LA_C_BLU=""; LA_C_BOLD=""
fi

log()  { printf "%b\n" "${LA_C_BLU}[life-agent]${LA_C_RESET} $*"; }
ok()   { printf "%b\n" "${LA_C_GRN}[ ok ]${LA_C_RESET} $*"; }
warn() { printf "%b\n" "${LA_C_YLW}[warn]${LA_C_RESET} $*" >&2; }
err()  { printf "%b\n" "${LA_C_RED}[fail]${LA_C_RESET} $*" >&2; }
die()  { err "$*"; exit 1; }

section() { printf "\n%b\n" "${LA_C_BOLD}== $* ==${LA_C_RESET}"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

confirm() {
  # confirm "message"  -> returns 0 if user types y/yes
  local reply
  read -r -p "$1 [y/N] " reply || true
  [[ "${reply}" == "y" || "${reply}" == "Y" || "${reply}" == "yes" ]]
}

# Read the backend version from app/__init__.py (single source of truth).
backend_version() {
  local init="${LA_BACKEND_DIR}/app/__init__.py"
  [[ -f "${init}" ]] || die "cannot find ${init}"
  grep -E '^__version__' "${init}" | sed -E 's/.*"([^"]+)".*/\1/'
}

# Activate the backend virtualenv if present.
activate_venv() {
  local venv="${LA_BACKEND_DIR}/.venv"
  if [[ -f "${venv}/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "${venv}/bin/activate"
  else
    warn "no venv at ${venv}; using system python"
  fi
}
