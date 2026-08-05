#!/usr/bin/env bash
#
# backup_before_update.sh — snapshot production data + config before any update.
# Creates a timestamped, self-describing backup under ~/LifeAgent/backups/.
# Never touches secrets in the Keychain (those are backed up separately by the
# OS / user). Databases and the vector store are copied consistently.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_cmd tar
require_cmd shasum

TS="$(date -u +%Y%m%dT%H%M%SZ)"
CURRENT="unknown"
[[ -L "${LA_PROD_HOME}/current" ]] && CURRENT="$(basename "$(readlink "${LA_PROD_HOME}/current")")"
BACKUP="${LA_PROD_HOME}/backups/backup-${TS}.tar.gz"

section "Backing up production state (${CURRENT})"

[[ -d "${LA_PROD_HOME}/data" ]] || die "no data directory at ${LA_PROD_HOME}/data"

mkdir -p "${LA_PROD_HOME}/backups"

log "archiving data/ and config/"
tar -C "${LA_PROD_HOME}" -czf "${BACKUP}" \
  --exclude='data/cache' \
  data config 2>/dev/null

SHA="$(shasum -a 256 "${BACKUP}" | awk '{print $1}')"
echo "${SHA}  $(basename "${BACKUP}")" > "${BACKUP}.sha256"

cat > "${BACKUP}.meta.json" <<JSON
{
  "created_at": "${TS}",
  "active_release": "${CURRENT}",
  "archive": "$(basename "${BACKUP}")",
  "sha256": "${SHA}",
  "host": "$(hostname)"
}
JSON

# Retention: keep the 10 most recent backups.
log "pruning old backups (keep 10)"
ls -1t "${LA_PROD_HOME}"/backups/backup-*.tar.gz 2>/dev/null | tail -n +11 | while read -r old; do
  rm -f "${old}" "${old}.sha256" "${old}.meta.json"
done

section "Done"
ok "backup: ${BACKUP}"
ok "sha256: ${SHA}"
echo "${BACKUP}"   # emit path on stdout for callers
