#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
BUILD_ROOT="${PROJECT_ROOT}/build-release"
RELEASE_ROOT="${PROJECT_ROOT}/release"
APP_PATH="${BUILD_ROOT}/dist/PS4 FFPFSC.app"
VERSION="0.2.8"
BUILD_CACHE="${PS4FFPSC_BUILD_CACHE:-${TMPDIR:-/tmp}/ps4ffpsc-build-cache}"
DEPLOYMENT_TARGET="13.0"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "This release must be built natively on macOS arm64." >&2
  exit 1
fi
if [[ ! -x "${PROJECT_ROOT}/.venv/bin/pyinstaller" ]]; then
  echo "PyInstaller is missing. Run scripts/bootstrap_macos.sh first." >&2
  exit 1
fi
PYTHON_CACHE="${BUILD_CACHE}/python"
PYTHON_FRAMEWORK_ROOT="${PYTHON_CACHE}/Python.framework"
PYTHON_LIBRARY_ROOT="${PYTHON_FRAMEWORK_ROOT}/Versions/3.13/lib"
PYTHON_FRAMEWORK_SHA256="db77544e7135af8478d62c7d1289581d83714a676c7d3f2b7a4b996bdfef5717"
PYTHON_LAUNCHER="${PYTHON_FRAMEWORK_ROOT}/Versions/3.13/bin/python3.13"
PYTHON_LAUNCHER_SHA256="ee3c4103b97e32a98e98cfad7f6ca4d09b2ab2dc16f3d28e18b54a4a0244efe0"
if [[ ! -f "${PYTHON_FRAMEWORK_ROOT}/Versions/3.13/Python" ]] \
    || [[ ! -x "${PYTHON_LAUNCHER}" ]] \
    || [[ "$(shasum -a 256 "${PYTHON_FRAMEWORK_ROOT}/Versions/3.13/Python" | awk '{print $1}')" != "${PYTHON_FRAMEWORK_SHA256}" ]] \
    || [[ "$(shasum -a 256 "${PYTHON_LAUNCHER}" | awk '{print $1}')" != "${PYTHON_LAUNCHER_SHA256}" ]]; then
  echo "The verified official Python 3.13.14 build cache is missing." >&2
  echo "Run scripts/bootstrap_macos.sh first." >&2
  exit 1
fi
export DYLD_FRAMEWORK_PATH="${PYTHON_CACHE}${DYLD_FRAMEWORK_PATH:+:${DYLD_FRAMEWORK_PATH}}"
export DYLD_LIBRARY_PATH="${PYTHON_LIBRARY_ROOT}${DYLD_LIBRARY_PATH:+:${DYLD_LIBRARY_PATH}}"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
PS4FFPSC_EXPECTED_PYTHON_BASE="${PYTHON_FRAMEWORK_ROOT}/Versions/3.13" \
  "${PYTHON_BIN}" -c \
  'import os, platform, ssl, sys; from pathlib import Path; expected = Path(os.environ["PS4FFPSC_EXPECTED_PYTHON_BASE"]).resolve(); raise SystemExit(0 if sys.version_info[:3] == (3, 13, 14) and platform.machine() == "arm64" and Path(sys.base_prefix).resolve() == expected and ssl.OPENSSL_VERSION else 1)' || {
  echo "The release environment must use official native Python 3.13.14." >&2
  echo "Run scripts/bootstrap_macos.sh first." >&2
  exit 1
}
"${PYTHON_BIN}" -c \
  'from importlib.metadata import version; expected = {"PySide6-Essentials": "6.9.3", "shiboken6": "6.9.3", "pyinstaller": "6.21.0"}; raise SystemExit(0 if all(version(name) == value for name, value in expected.items()) else 1)' || {
  echo "Pinned Python release dependencies are missing or have wrong versions." >&2
  echo "Run scripts/bootstrap_macos.sh first." >&2
  exit 1
}
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew release tools are missing. Run scripts/bootstrap_macos.sh." >&2
  exit 1
fi
DOTNET_BIN="${PS4FFPSC_DOTNET:-$(brew --prefix dotnet@8)/libexec/dotnet}"
CLANG_BIN="${PS4FFPSC_CLANG:-$(brew --prefix llvm)/bin/clang}"
LLD_BIN="${PS4FFPSC_LLD:-$(brew --prefix lld)/bin/ld.lld}"
for executable in "${DOTNET_BIN}" "${CLANG_BIN}" "${LLD_BIN}"; do
  if [[ ! -x "${executable}" ]]; then
    echo "Required release tool is missing: ${executable}" >&2
    echo "Run scripts/bootstrap_macos.sh first." >&2
    exit 1
  fi
done
if ! "${DOTNET_BIN}" --list-sdks | grep -Eq '^8\.0\.'; then
  echo ".NET SDK 8 is required for the NativeAOT helper." >&2
  exit 1
fi
export MACOSX_DEPLOYMENT_TARGET="${DEPLOYMENT_TARGET}"

rm -rf "${BUILD_ROOT}"
mkdir -p "${BUILD_ROOT}" "${RELEASE_ROOT}"
rm -f -- \
  "${RELEASE_ROOT}/PS4-FFPFSC-v${VERSION}-macos-arm64.zip" \
  "${RELEASE_ROOT}/PS4-FFPFSC-v${VERSION}-macos-arm64.zip.sha256" \
  "${RELEASE_ROOT}/RELEASE_NOTES-v${VERSION}.md"

"${PYTHON_BIN}" -m pytest -q

CRYPTOPP_ROOT="$(
  "${PROJECT_ROOT}/scripts/prepare_cryptopp_macos.sh" \
    "${BUILD_CACHE}/cryptopp"
)"

cmake -S "${PROJECT_ROOT}" -B "${BUILD_ROOT}/helper" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_ARCHITECTURES=arm64 \
  "-DCMAKE_OSX_DEPLOYMENT_TARGET=${DEPLOYMENT_TARGET}" \
  -DPS4FFPSC_STATIC_CRYPTOPP=ON \
  "-DCRYPTOPP_INCLUDE_DIR=${CRYPTOPP_ROOT}/include" \
  "-DCRYPTOPP_LIBRARY=${CRYPTOPP_ROOT}/lib/libcryptopp.a"
cmake --build "${BUILD_ROOT}/helper" --parallel
ctest --test-dir "${BUILD_ROOT}/helper" --output-on-failure

OPENORBIS_ROOT="${PS4FFPSC_OPENORBIS_ROOT:-}"
if [[ -z "${OPENORBIS_ROOT}" ]]; then
  OPENORBIS_ROOT="$(
    "${PROJECT_ROOT}/scripts/fetch_openorbis_toolchain.sh" \
      "${BUILD_CACHE}/openorbis"
  )"
fi
DLC_TEMPLATE="${BUILD_ROOT}/dlc-template/dlcldr.prx"
PS4FFPSC_CLANG="${CLANG_BIN}" PS4FFPSC_LLD="${LLD_BIN}" \
  "${PROJECT_ROOT}/scripts/build_dlc_module.sh" \
  "${OPENORBIS_ROOT}" "${DLC_TEMPLATE}"
PS4FFPSC_DOTNET="${DOTNET_BIN}" \
DOTNET_CLI_HOME="${BUILD_CACHE}/dotnet-home" \
NUGET_PACKAGES="${BUILD_CACHE}/nuget-packages" \
  "${PROJECT_ROOT}/third_party/ps4_dlc_patch/publish-native.sh" \
  "${DLC_TEMPLATE}" osx-arm64 "${BUILD_ROOT}/dlc-helper"
test -x "${BUILD_ROOT}/dlc-helper/ps4-dlc-patch"

QT_QPA_PLATFORM=offscreen \
  "${PYTHON_BIN}" \
  "${PROJECT_ROOT}/packaging/macos/make_icon.py" \
  "${BUILD_ROOT}/AppIcon.icns"

cd "${PROJECT_ROOT}"
PYINSTALLER_CONFIG_DIR="${BUILD_ROOT}/pyinstaller-config" \
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
BUNDLED_DLC_HELPER="$(
  find "${APP_PATH}" -type f -name ps4-dlc-patch -print -quit
)"
test -n "${BUNDLED_DLC_HELPER}"
"${BUNDLED_DLC_HELPER}" --help > "${BUILD_ROOT}/dlc-helper-help.txt"
"${BUNDLED_DLC_HELPER}" --check-template \
  > "${BUILD_ROOT}/dlc-helper-template.json"

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
(cd "${RELEASE_ROOT}" && shasum -a 256 "$(basename "${ARCHIVE}")" > "$(basename "${ARCHIVE}").sha256")
cp "${PROJECT_ROOT}/packaging/releases/v${VERSION}.md" \
  "${RELEASE_ROOT}/RELEASE_NOTES-v${VERSION}.md"

echo "Release created: ${ARCHIVE}"
