#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

PYTHON="${PYTHON:-${PROJECT_ROOT}/.venv/bin/python}"
BUILD_DIR="${PROJECT_ROOT}/build"
DIST_DIR="${PROJECT_ROOT}/dist/PS4 FFPFSC"
APPDIR="${PROJECT_ROOT}/AppDir"
TOOLS_DIR="${BUILD_TOOLS_DIR:-${PROJECT_ROOT}/build-tools}"
RELEASE_DIR="${PROJECT_ROOT}/release"

APPIMAGETOOL_VERSION="1.9.1"
APPIMAGETOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-x86_64.AppImage"

RUNTIME_VERSION="20251108"
RUNTIME_SHA256="2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d"
RUNTIME_URL="https://github.com/AppImage/type2-runtime/releases/download/${RUNTIME_VERSION}/runtime-x86_64"

APPIMAGETOOL="${TOOLS_DIR}/appimagetool-x86_64.AppImage"
RUNTIME="${TOOLS_DIR}/runtime-x86_64"

fetch_verified() {
    local url="$1"
    local expected="$2"
    local destination="$3"

    mkdir -p "$(dirname -- "${destination}")"

    if [[ -f "${destination}" ]] &&
       printf '%s  %s\n' "${expected}" "${destination}" | sha256sum -c - >/dev/null 2>&1; then
        return
    fi

    rm -f -- "${destination}"
    curl --fail --location --retry 3 --retry-delay 2 \
        --output "${destination}" "${url}"

    printf '%s  %s\n' "${expected}" "${destination}" | sha256sum -c -
}

if [[ ! -x "${PYTHON}" ]]; then
    echo "Python environment not found: ${PYTHON}" >&2
    echo "Create .venv and install requirements-dev.lock first." >&2
    exit 1
fi

"${PYTHON}" -m PyInstaller --version >/dev/null

cd "${PROJECT_ROOT}"

# Native PS4 PKG extractor.
cmake -S . -B "${BUILD_DIR}" -DCMAKE_BUILD_TYPE=Release
cmake --build "${BUILD_DIR}" --parallel "${CMAKE_BUILD_PARALLEL_LEVEL:-2}"

ctest --test-dir "${BUILD_DIR}" --output-on-failure

HELPER="${BUILD_DIR}/tools/ps4_pkg_extract/ps4_pkg_extract"
test -x "${HELPER}"

# Frozen Python application.
rm -rf -- "${PROJECT_ROOT}/build/PS4FFPFSC" "${DIST_DIR}"

"${PYTHON}" -m PyInstaller \
    --clean \
    --noconfirm \
    "${PROJECT_ROOT}/packaging/linux/PS4FFPFSC.spec"

test -x "${DIST_DIR}/PS4 FFPFSC"
test -x "${DIST_DIR}/ps4ffpsc-worker"
test -x "${DIST_DIR}/_internal/bin/ps4_pkg_extract"

# AppDir.
rm -rf -- "${APPDIR}"
cp -a "${DIST_DIR}" "${APPDIR}"

cp "${PROJECT_ROOT}/packaging/linux/AppRun" \
    "${APPDIR}/AppRun"
cp "${PROJECT_ROOT}/packaging/linux/PS4FFPFSC.desktop" \
    "${APPDIR}/PS4FFPFSC.desktop"
cp "${PROJECT_ROOT}/packaging/linux/ps4ffpsc.svg" \
    "${APPDIR}/ps4ffpsc.svg"

chmod +x "${APPDIR}/AppRun"

# Version: release tag when available, otherwise current macOS spec version.
APP_VERSION="${APP_VERSION:-}"
if [[ -z "${APP_VERSION}" ]]; then
    APP_VERSION="$("${PYTHON}" - <<'PY'
from pathlib import Path
import re

text = Path("packaging/macos/PS4FFPFSC.spec").read_text(encoding="utf-8")
match = re.search(
    r'CFBundleShortVersionString"\s*:\s*"([^"]+)"',
    text,
)
if not match:
    raise SystemExit("Unable to determine application version")
print(match.group(1))
PY
)"
fi
APP_VERSION="${APP_VERSION#v}"

mkdir -p "${RELEASE_DIR}"

OUTPUT="${RELEASE_DIR}/PS4-FFPFSC-${APP_VERSION}-linux-x86_64.AppImage"
CHECKSUM="${OUTPUT}.sha256"

rm -f -- "${OUTPUT}" "${CHECKSUM}"

# Pin the packer and its runtime instead of using moving 'continuous' builds.
fetch_verified \
    "${APPIMAGETOOL_URL}" \
    "${APPIMAGETOOL_SHA256}" \
    "${APPIMAGETOOL}"

fetch_verified \
    "${RUNTIME_URL}" \
    "${RUNTIME_SHA256}" \
    "${RUNTIME}"

chmod +x "${APPIMAGETOOL}" "${RUNTIME}"

ARCH=x86_64 \
"${APPIMAGETOOL}" \
    --appimage-extract-and-run \
    --runtime-file "${RUNTIME}" \
    "${APPDIR}" \
    "${OUTPUT}"

chmod +x "${OUTPUT}"
sha256sum "${OUTPUT}" > "${CHECKSUM}"

# Self-contained smoke tests.
QT_QPA_PLATFORM=offscreen \
"${OUTPUT}" \
    --appimage-extract-and-run \
    --gui-smoke-test

"${OUTPUT}" \
    --appimage-extract-and-run \
    --mkpfs -V

echo
echo "Linux AppImage:"
echo "  ${OUTPUT}"
echo "SHA256:"
cat "${CHECKSUM}"
