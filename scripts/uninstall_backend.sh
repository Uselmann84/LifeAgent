#!/usr/bin/env bash
#
# uninstall_backend.sh — remove the Life Agent service and (optionally) code
# from the Backend Mac. By default it preserves data, config, and backups.
# Use --purge to also delete data (irreversible) — requires explicit
# confirmation and does NOT remove Keychain secrets automatically.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

PURGE=0
[[ "${1:-}" == "--purge" ]] && PURGE=1

section "Uninstall Life Agent backend"

# 1) Stop + unload launchd ---------------------------------------------------
log "stopping service"
launchctl stop "${LA_AUTONOMY_LABEL}" 2>/dev/null || true
launchctl unload "${LA_AUTONOMY_PLIST}" 2>/dev/null || true
rm -f "${LA_AUTONOMY_PLIST}"
launchctl stop "${LA_LAUNCHD_LABEL}" 2>/dev/null || true
launchctl unload "${LA_LAUNCHD_PLIST}" 2>/dev/null || true
rm -f "${LA_LAUNCHD_PLIST}"
ok "launchd services removed"

# 2) Remove code, keep data --------------------------------------------------
log "removing releases, venv, and symlinks (data/config preserved)"
rm -rf "${LA_PROD_HOME}/releases" "${LA_PROD_HOME}/venv" \
       "${LA_PROD_HOME}/current" "${LA_PROD_HOME}/app"
ok "code removed"

# 3) Optional purge ----------------------------------------------------------
if [[ "${PURGE}" -eq 1 ]]; then
  warn "PURGE requested — this will permanently delete data, config, and backups."
  if confirm "Type y to permanently delete ${LA_PROD_HOME}/data, config, backups"; then
    rm -rf "${LA_PROD_HOME}/data" "${LA_PROD_HOME}/config" \
           "${LA_PROD_HOME}/logs" "${LA_PROD_HOME}/backups" "${LA_PROD_HOME}/models"
    ok "data purged"
    warn "Keychain secrets were NOT removed. To remove them:"
    warn "  security delete-generic-password -s life-agent -a \"\${USER}.<key>\""
  else
    log "purge cancelled; data preserved"
  fi
else
  log "data, config, backups preserved at ${LA_PROD_HOME}"
fi

section "Done"
ok "uninstall complete"
