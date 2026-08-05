#!/usr/bin/env bash
#
# deploy_to_backend.sh — copy a built release from the Development Mac to the
# Backend Mac over the private network (Tailscale), verify its checksum, and
# hand off to install/update on the remote host.
#
# Usage:
#   export LA_BACKEND_SSH="lifeagent@backend-mac.tailnet.ts.net"
#   ./scripts/deploy_to_backend.sh [vX.Y.Z]
#
# If no version is given, the current backend version is used.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_cmd scp
require_cmd ssh
require_cmd shasum

[[ -n "${LA_BACKEND_SSH}" ]] || die "set LA_BACKEND_SSH to the Backend Mac ssh target"

VERSION="${1:-$(backend_version)}"
VERSION="${VERSION#v}"
TAG="lifeagent-v${VERSION}"
ARCHIVE="${LA_RELEASES_DIR}/${TAG}.tar.gz"

[[ -f "${ARCHIVE}" ]] || die "release not found: ${ARCHIVE} (run build_backend_release.sh first)"

section "Deploying ${TAG} -> ${LA_BACKEND_SSH}"

# Verify local integrity before shipping.
log "verifying local checksum"
( cd "${LA_RELEASES_DIR}" && shasum -a 256 -c "${TAG}.tar.gz.sha256" ) \
  || die "local checksum failed; rebuild the release"

REMOTE_INBOX="LifeAgent/releases/incoming"
log "ensuring remote inbox exists"
ssh "${LA_BACKEND_SSH}" "mkdir -p ~/${REMOTE_INBOX}"

log "copying archive + checksum + manifest"
scp "${ARCHIVE}" "${ARCHIVE}.sha256" "${LA_RELEASES_DIR}/${TAG}.manifest.json" \
  "${LA_BACKEND_SSH}:~/${REMOTE_INBOX}/"

log "verifying checksum on Backend Mac"
ssh "${LA_BACKEND_SSH}" "cd ~/${REMOTE_INBOX} && shasum -a 256 -c ${TAG}.tar.gz.sha256" \
  || die "remote checksum failed; aborting"

ok "release delivered and verified on Backend Mac"
cat <<EOF

Next, on the Backend Mac:
  cd ~/${REMOTE_INBOX}
  tar xzf ${TAG}.tar.gz
  ./${TAG}/scripts/update_backend.sh ${VERSION}      # for an existing install
  # or, for a first-time install:
  ./${TAG}/scripts/install_backend.sh ${VERSION}
EOF
