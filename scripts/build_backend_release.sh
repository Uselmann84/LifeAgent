#!/usr/bin/env bash
#
# build_backend_release.sh — package the backend into a versioned, verifiable
# release archive under releases/. Runs validation first unless --skip-validate.
#
#   releases/lifeagent-vX.Y.Z.tar.gz
#   releases/lifeagent-vX.Y.Z.tar.gz.sha256
#   releases/lifeagent-vX.Y.Z.manifest.json
#
# The archive contains ONLY source + config templates. No secrets, no venv,
# no local data, no .env files.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

SKIP_VALIDATE=0
[[ "${1:-}" == "--skip-validate" ]] && SKIP_VALIDATE=1

require_cmd tar
require_cmd shasum

VERSION="$(backend_version)"
TAG="lifeagent-v${VERSION}"
mkdir -p "${LA_RELEASES_DIR}"
ARCHIVE="${LA_RELEASES_DIR}/${TAG}.tar.gz"

section "Building release ${TAG}"

if [[ "${SKIP_VALIDATE}" -eq 0 ]]; then
  "${LA_SCRIPT_DIR}/validate_release.sh"
else
  warn "skipping validation (--skip-validate)"
fi

# Stage a clean tree ---------------------------------------------------------
STAGE="$(mktemp -d)"
trap 'rm -rf "${STAGE}"' EXIT
PKG="${STAGE}/${TAG}"
mkdir -p "${PKG}"

log "staging backend source"
# Copy backend source, excluding runtime + secret artifacts.
tar -C "${LA_BACKEND_DIR}" \
  --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.env' --exclude='data' --exclude='logs' --exclude='*.db' \
  --exclude='.pytest_cache' --exclude='.ruff_cache' \
  -cf - . | tar -C "${PKG}" -xf -

# Include deployment scripts and infra templates for on-host operations.
cp -R "${LA_SCRIPT_DIR}" "${PKG}/scripts"
[[ -d "${LA_INFRA_DIR}" ]] && cp -R "${LA_INFRA_DIR}" "${PKG}/infrastructure"
cp "${LA_REPO_ROOT}/.env.example" "${PKG}/.env.example" 2>/dev/null || true

# Safety: ensure no .env or secrets slipped in.
if find "${PKG}" -name '.env' -o -name '*.pem' | grep -q .; then
  die "refusing to build: secret-like files found in staging area"
fi

# Archive --------------------------------------------------------------------
log "creating ${ARCHIVE}"
tar -C "${STAGE}" -czf "${ARCHIVE}" "${TAG}"
SHA="$(shasum -a 256 "${ARCHIVE}" | awk '{print $1}')"
echo "${SHA}  ${TAG}.tar.gz" > "${ARCHIVE}.sha256"

# Manifest -------------------------------------------------------------------
GIT_REV="$(git -C "${LA_REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
BYTES="$(wc -c < "${ARCHIVE}" | tr -d ' ')"
cat > "${LA_RELEASES_DIR}/${TAG}.manifest.json" <<JSON
{
  "name": "${TAG}",
  "version": "${VERSION}",
  "git_rev": "${GIT_REV}",
  "archive": "${TAG}.tar.gz",
  "sha256": "${SHA}",
  "size_bytes": ${BYTES},
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "built_on": "$(hostname)"
}
JSON

section "Built"
ok "archive:  ${ARCHIVE}"
ok "sha256:   ${SHA}"
ok "manifest: ${LA_RELEASES_DIR}/${TAG}.manifest.json"
