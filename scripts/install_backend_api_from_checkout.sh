#!/usr/bin/env bash
#
# install_backend_api_from_checkout.sh — run the FastAPI API server as a launchd
# agent directly from THIS git checkout (Backend Mac), using backend/.venv and
# backend/.env. Companion to install_autonomy_from_checkout.sh (the autonomy loop
# and the API are two independent processes). The API binds 127.0.0.1:8787;
# Tailscale Serve proxies HTTPS on the tailnet in front of it.
#
# Run ON the Backend Mac, from anywhere in the repo:
#   bash scripts/install_backend_api_from_checkout.sh
#
# Manage afterwards:
#   launchctl kickstart -k gui/$(id -u)/com.lifeagent.backend   # restart (after git pull)
#   launchctl stop  com.lifeagent.backend                        # graceful stop
#   launchctl bootout gui/$(id -u)/com.lifeagent.backend         # remove
set -euo pipefail

LABEL="com.lifeagent.backend"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="${REPO_ROOT}/backend"
VENV_PY="${BACKEND}/.venv/bin/python"
ENV_FILE="${BACKEND}/.env"
LOG_DIR="${REPO_ROOT}/logs"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"
HOST="127.0.0.1"
PORT="8787"

# --- sanity checks ----------------------------------------------------------
[[ "$(uname)" == "Darwin" ]] || { echo "ERROR: launchd is macOS-only"; exit 1; }
[[ -x "${VENV_PY}" ]] || { echo "ERROR: venv python not found at ${VENV_PY} (create backend/.venv first)"; exit 1; }
[[ -f "${ENV_FILE}" ]] || { echo "ERROR: ${ENV_FILE} not found"; exit 1; }
mkdir -p "${LOG_DIR}" "${HOME}/Library/LaunchAgents"

# Free port 8787 from any hand-started (nohup) uvicorn so launchd can bind it.
echo "==> stopping any manually started API on ${PORT}"
pkill -f "uvicorn app.main:create_app" 2>/dev/null || true

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
    <string>uvicorn</string>
    <string>app.main:create_app</string>
    <string>--factory</string>
    <string>--host</string>
    <string>${HOST}</string>
    <string>--port</string>
    <string>${PORT}</string>
  </array>
  <key>WorkingDirectory</key><string>${BACKEND}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>LIFE_AGENT_ENVIRONMENT</key><string>production</string>
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
  <key>StandardOutPath</key><string>${LOG_DIR}/backend.out.log</string>
  <key>StandardErrorPath</key><string>${LOG_DIR}/backend.err.log</string>
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

echo "==> waiting for the API to answer on http://${HOST}:${PORT} ..."
ok=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "http://${HOST}:${PORT}/api/v1/health" >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done

echo "==> status:"
launchctl print "${DOMAIN}/${LABEL}" | grep -E 'state =|pid =' || true
if [[ -n "${ok}" ]]; then
  echo "OK: API healthy at http://${HOST}:${PORT}/api/v1/health"
else
  echo "WARN: API did not answer yet — check ${LOG_DIR}/backend.err.log"
fi
echo "logs: ${LOG_DIR}/backend.out.log  (errors: ${LOG_DIR}/backend.err.log)"
