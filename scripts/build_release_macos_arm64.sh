#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
BUILD_ROOT="${PROJECT_ROOT}/build-release"
RELEASE_ROOT="${PROJECT_ROOT}/release"
APP_PATH="${BUILD_ROOT}/dist/PS4 FFPFSC.app"
VERSION="0.2.2"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "This release must be built natively on macOS arm64." >&2
  exit 1
fi
if [[ ! -x "${PROJECT_ROOT}/.venv/bin/pyinstaller" ]]; then
  echo "PyInstaller is missing. Run scripts/bootstrap_macos.sh first." >&2
  exit 1
fi

rm -rf "${BUILD_ROOT}" "${RELEASE_ROOT}"
mkdir -p "${BUILD_ROOT}" "${RELEASE_ROOT}"

"${PROJECT_ROOT}/.venv/bin/python" -m pytest -q

cmake -S "${PROJECT_ROOT}" -B "${BUILD_ROOT}/helper" \
  -DCMAKE_BUILD_TYPE=Release \
  -DPS4FFPSC_STATIC_CRYPTOPP=ON
cmake --build "${BUILD_ROOT}/helper" --parallel
ctest --test-dir "${BUILD_ROOT}/helper" --output-on-failure

QT_QPA_PLATFORM=offscreen \
  "${PROJECT_ROOT}/.venv/bin/python" \
  "${PROJECT_ROOT}/packaging/macos/make_icon.py" \
  "${BUILD_ROOT}/AppIcon.icns"

cd "${PROJECT_ROOT}"
"${PROJECT_ROOT}/.venv/bin/pyinstaller" \
  --clean \
  --noconfirm \
  --distpath "${BUILD_ROOT}/dist" \
  --workpath "${BUILD_ROOT}/pyinstaller" \
  "${PROJECT_ROOT}/packaging/macos/PS4FFPFSC.spec"

SIGNING_IDENTITY="${PS4FFPSC_CODESIGN_IDENTITY:--}"
codesign --force --deep --options runtime --timestamp=none \
  --sign "${SIGNING_IDENTITY}" "${APP_PATH}"
codesign --verify --deep --strict --verbose=2 "${APP_PATH}"
"${PROJECT_ROOT}/scripts/audit_macos_app.sh" "${APP_PATH}"

SMOKE_ROOT="$(mktemp -d /tmp/ps4ffpsc-release-smoke.XXXXXX)"
trap 'rm -rf "${SMOKE_ROOT}"' EXIT
mkdir -p "${SMOKE_ROOT}/input" "${SMOKE_ROOT}/selected-temp"
TEMP_WORKSPACE="${SMOKE_ROOT}/selected-temp/PS4 FFPFSC"
PS4FFPSC_DATA_ROOT="${SMOKE_ROOT}" \
  "${APP_PATH}/Contents/MacOS/PS4 FFPFSC" --worker doctor \
  --pkg-dir "${SMOKE_ROOT}/input" \
  --unpacked-dir "${TEMP_WORKSPACE}/unpacked" \
  --work-dir "${TEMP_WORKSPACE}/work" \
  --temp-dir "${TEMP_WORKSPACE}/tmp" \
  --output-dir "${SMOKE_ROOT}/output" \
  --json \
  > "${BUILD_ROOT}/doctor.json"
PS4FFPSC_DATA_ROOT="${SMOKE_ROOT}" \
  "${APP_PATH}/Contents/MacOS/PS4 FFPFSC" --worker scan \
  --pkg-dir "${SMOKE_ROOT}/input" \
  --unpacked-dir "${TEMP_WORKSPACE}/unpacked" \
  --work-dir "${TEMP_WORKSPACE}/work" \
  --temp-dir "${TEMP_WORKSPACE}/tmp" \
  --output-dir "${SMOKE_ROOT}/output" \
  --json > "${BUILD_ROOT}/temp-routing.json"
test -f "${TEMP_WORKSPACE}/unpacked/package_inventory.json"
test ! -e "${SMOKE_ROOT}/unpacked"
test ! -e "${SMOKE_ROOT}/work"
PS4FFPSC_DATA_ROOT="${SMOKE_ROOT}" \
  "${APP_PATH}/Contents/MacOS/PS4 FFPFSC" --mkpfs -V \
  > "${BUILD_ROOT}/mkpfs-version.txt"
PS4FFPSC_DATA_ROOT="${SMOKE_ROOT}" QT_QPA_PLATFORM=offscreen \
  "${APP_PATH}/Contents/MacOS/PS4 FFPFSC" --gui-smoke-test \
  > "${BUILD_ROOT}/gui-smoke.txt"

ARCHIVE="${RELEASE_ROOT}/PS4-FFPFSC-v${VERSION}-macos-arm64.zip"
ditto -c -k --sequesterRsrc --keepParent "${APP_PATH}" "${ARCHIVE}"
shasum -a 256 "${ARCHIVE}" > "${ARCHIVE}.sha256"
cp "${PROJECT_ROOT}/packaging/macos/RELEASE_NOTES.md" \
  "${RELEASE_ROOT}/RELEASE_NOTES-v${VERSION}.md"

echo "Release created: ${ARCHIVE}"
