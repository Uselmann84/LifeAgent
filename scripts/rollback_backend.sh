#!/usr/bin/env bash
#
# rollback_backend.sh — manually revert to a previous known-good release.
# Lists available releases if none is specified.
#
#   ./scripts/rollback_backend.sh            # show releases
#   ./scripts/rollback_backend.sh vX.Y.Z     # roll back to that release

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

RELEASES_ROOT="${LA_PROD_HOME}/releases"
[[ -d "${RELEASES_ROOT}" ]] || die "no releases directory at ${RELEASES_ROOT}"

CURRENT="none"
[[ -L "${LA_PROD_HOME}/current" ]] && CURRENT="$(basename "$(readlink "${LA_PROD_HOME}/current")")"

if [[ $# -eq 0 ]]; then
  section "Available releases (active: ${CURRENT})"
  ls -1 "${RELEASES_ROOT}" | grep -E '^lifeagent-v' || warn "none found"
  echo
  log "usage: $0 vX.Y.Z"
  exit 0
fi

VERSION="${1#v}"
TAG="lifeagent-v${VERSION}"
TARGET="${RELEASES_ROOT}/${TAG}"

[[ -d "${TARGET}" ]] || die "release not installed: ${TAG}"
[[ "${TAG}" == "${CURRENT}" ]] && { warn "${TAG} is already active"; exit 0; }

section "Rolling back to ${TAG} (from ${CURRENT})"
confirm "Proceed with rollback?" || die "aborted"

# Snapshot current state first.
"${LA_SCRIPT_DIR}/backup_before_update.sh" >/dev/null

launchctl stop "${LA_LAUNCHD_LABEL}" 2>/dev/null || true
ln -sfn "${TARGET}" "${LA_PROD_HOME}/current"
ln -sfn "${TARGET}/backend/app" "${LA_PROD_HOME}/app"
launchctl start "${LA_LAUNCHD_LABEL}" 2>/dev/null || true

if "${LA_SCRIPT_DIR}/verify_deployment.sh"; then
  ok "rolled back to ${TAG}"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) rolled back to ${TAG}" >> "${RELEASES_ROOT}/history.log"
else
  die "verification failed after rollback — investigate manually"
fi
