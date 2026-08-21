#!/usr/bin/env bash
#
# install_autonomy_from_checkout.sh — run the autonomy loop as a launchd agent
# directly from THIS git checkout (Backend Mac), using backend/.venv and
# backend/.env. This is the lightweight alternative to install_backend.sh's
# releases/current + Keychain layout: it points launchd straight at the repo.
#
# Run ON the Backend Mac, from anywhere in the repo:
#   bash scripts/install_autonomy_from_checkout.sh
#
# Manage afterwards:
#   launchctl kickstart -k gui/$(id -u)/com.lifeagent.autonomy   # restart (after git pull)
#   launchctl stop  com.lifeagent.autonomy                        # graceful stop
#   launchctl bootout gui/$(id -u)/com.lifeagent.autonomy         # remove
set -euo pipefail

LABEL="com.lifeagent.autonomy"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="${REPO_ROOT}/backend"
VENV_PY="${BACKEND}/.venv/bin/python"
ENV_FILE="${BACKEND}/.env"
LOG_DIR="${REPO_ROOT}/logs"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"

# --- sanity checks ----------------------------------------------------------
[[ "$(uname)" == "Darwin" ]] || { echo "ERROR: launchd is macOS-only"; exit 1; }
[[ -x "${VENV_PY}" ]] || { echo "ERROR: venv python not found at ${VENV_PY} (create backend/.venv first)"; exit 1; }
[[ -f "${ENV_FILE}" ]] || { echo "ERROR: ${ENV_FILE} not found"; exit 1; }
mkdir -p "${LOG_DIR}" "${HOME}/Library/LaunchAgents"

# Fail closed if the execution boundary is not satisfied.
echo "==> preflight"
( cd "${BACKEND}" && LIFE_AGENT_ENV_FILE="${ENV_FILE}" "${VENV_PY}" -m app.autonomy.service preflight )

# --- write the launchd plist ------------------------------------------------
echo "==> writing ${PLIST}"
cat > "${PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${VENV_PY}</string>
    <string>-m</string>
    <string>app.autonomy.service</string>
    <string>run</string>
  </array>
  <key>WorkingDirectory</key><string>${BACKEND}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>LIFE_AGENT_ENVIRONMENT</key><string>production</string>
    <key>LIFE_AGENT_EXECUTION_MODE</key><string>production</string>
    <key>LIFE_AGENT_ENV_FILE</key><string>${ENV_FILE}</string>
    <key>PATH</key><string>${BACKEND}/.venv/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key><false/>
    <key>Crashed</key><true/>
  </dict>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>RunAtLoad</key><true/>
  <key>ProcessType</key><string>Background</string>
  <key>ExitTimeOut</key><integer>20</integer>
  <key>StandardOutPath</key><string>${LOG_DIR}/autonomy.out.log</string>
  <key>StandardErrorPath</key><string>${LOG_DIR}/autonomy.err.log</string>
</dict>
</plist>
EOF

# Validate before loading so a bad plist is caught with a clear message.
plutil -lint "${PLIST}"

# --- (re)load via modern launchctl ------------------------------------------
echo "==> (re)bootstrapping ${LABEL}"
launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
launchctl bootstrap "${DOMAIN}" "${PLIST}"
launchctl kickstart -k "${DOMAIN}/${LABEL}"

echo "==> done. status:"
launchctl print "${DOMAIN}/${LABEL}" | grep -E 'state =|pid =' || true
echo "logs: ${LOG_DIR}/autonomy.out.log"
