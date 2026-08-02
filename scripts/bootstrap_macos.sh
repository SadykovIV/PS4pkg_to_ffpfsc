#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
BUILD_CACHE="${PS4FFPSC_BUILD_CACHE:-${TMPDIR:-/tmp}/ps4ffpsc-build-cache}"
PYTHON_VERSION="3.13.14"
PYTHON_PKG="python-${PYTHON_VERSION}-macos11.pkg"
PYTHON_SHA256="8e58affb218c155a1dfdc27b291f817129669f8760e7a297adb2e4439ba5d2e8"
PYTHON_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_PKG}"
PYTHON_CACHE="${BUILD_CACHE}/python"
PYTHON_PACKAGE_PATH="${PYTHON_CACHE}/${PYTHON_PKG}"
PYTHON_FRAMEWORK_ROOT="${PYTHON_CACHE}/Python.framework"
PYTHON_BIN="${PYTHON_FRAMEWORK_ROOT}/Versions/3.13/bin/python3.13"
PYTHON_LIBRARY_ROOT="${PYTHON_FRAMEWORK_ROOT}/Versions/3.13/lib"
PYTHON_FRAMEWORK_SHA256="db77544e7135af8478d62c7d1289581d83714a676c7d3f2b7a4b996bdfef5717"
PYTHON_LAUNCHER_SHA256="ee3c4103b97e32a98e98cfad7f6ca4d09b2ab2dc16f3d28e18b54a4a0244efe0"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This bootstrap script targets macOS." >&2
  exit 1
fi
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Apple Silicon arm64 is required; Rosetta is not used." >&2
  exit 1
fi
command -v brew >/dev/null 2>&1 || {
  echo "Homebrew is required for the .NET/OpenOrbis release toolchain." >&2
  exit 1
}

for formula in dotnet@8 llvm lld cmake; do
  if ! brew list --versions "${formula}" >/dev/null 2>&1; then
    brew install "${formula}"
  fi
done

python_is_expected() {
  local framework_hash launcher_hash
  [[ -x "${PYTHON_BIN}" ]] || return 1
  [[ -f "${PYTHON_FRAMEWORK_ROOT}/Versions/3.13/Python" ]] || return 1
  framework_hash="$(shasum -a 256 "${PYTHON_FRAMEWORK_ROOT}/Versions/3.13/Python" | awk '{print $1}')"
  launcher_hash="$(shasum -a 256 "${PYTHON_BIN}" | awk '{print $1}')"
  [[ "${framework_hash}" == "${PYTHON_FRAMEWORK_SHA256}" ]] || return 1
  [[ "${launcher_hash}" == "${PYTHON_LAUNCHER_SHA256}" ]] || return 1
  DYLD_FRAMEWORK_PATH="${PYTHON_CACHE}" \
  DYLD_LIBRARY_PATH="${PYTHON_LIBRARY_ROOT}" \
    "${PYTHON_BIN}" -c \
    'import platform, ssl, sys; raise SystemExit(0 if sys.version_info[:3] == (3, 13, 14) and platform.machine() == "arm64" and ssl.OPENSSL_VERSION else 1)'
}

verify_python_package() {
  local actual
  actual="$(shasum -a 256 "${PYTHON_PACKAGE_PATH}" | awk '{print $1}')"
  [[ "${actual}" == "${PYTHON_SHA256}" ]]
}

if ! python_is_expected; then
  mkdir -p "${PYTHON_CACHE}"
  if [[ ! -f "${PYTHON_PACKAGE_PATH}" ]] || ! verify_python_package; then
    rm -f -- "${PYTHON_PACKAGE_PATH}" "${PYTHON_PACKAGE_PATH}.partial"
    curl --fail --location --retry 3 --retry-delay 2 \
      --output "${PYTHON_PACKAGE_PATH}.partial" "${PYTHON_URL}"
    mv "${PYTHON_PACKAGE_PATH}.partial" "${PYTHON_PACKAGE_PATH}"
    if ! verify_python_package; then
      echo "Official Python ${PYTHON_VERSION} package checksum mismatch" >&2
      rm -f -- "${PYTHON_PACKAGE_PATH}"
      exit 1
    fi
  fi
  echo "Extracting verified official Python ${PYTHON_VERSION} into the build cache..." >&2
  PYTHON_EXPAND_ROOT="${PYTHON_CACHE}/python-${PYTHON_VERSION}-expanded"
  rm -rf -- "${PYTHON_EXPAND_ROOT}" "${PYTHON_EXPAND_ROOT}.partial" \
    "${PYTHON_FRAMEWORK_ROOT}"
  pkgutil --expand-full "${PYTHON_PACKAGE_PATH}" \
    "${PYTHON_EXPAND_ROOT}.partial"
  if [[ ! -d "${PYTHON_EXPAND_ROOT}.partial/Python_Framework.pkg/Payload/Versions/3.13" ]]; then
    echo "Official Python package framework layout is incomplete." >&2
    exit 1
  fi
  mv "${PYTHON_EXPAND_ROOT}.partial/Python_Framework.pkg/Payload" \
    "${PYTHON_FRAMEWORK_ROOT}"
  rm -rf -- "${PYTHON_EXPAND_ROOT}.partial"
fi
if ! python_is_expected; then
  echo "Official native Python ${PYTHON_VERSION} cache failed verification." >&2
  exit 1
fi
export DYLD_FRAMEWORK_PATH="${PYTHON_CACHE}${DYLD_FRAMEWORK_PATH:+:${DYLD_FRAMEWORK_PATH}}"
export DYLD_LIBRARY_PATH="${PYTHON_LIBRARY_ROOT}${DYLD_LIBRARY_PATH:+:${DYLD_LIBRARY_PATH}}"

DOTNET_BIN="$(brew --prefix dotnet@8)/libexec/dotnet"
CLANG_BIN="$(brew --prefix llvm)/bin/clang"
LLD_BIN="$(brew --prefix lld)/bin/ld.lld"
for executable in "${DOTNET_BIN}" "${CLANG_BIN}" "${LLD_BIN}"; do
  if [[ ! -x "${executable}" ]]; then
    echo "Required release tool is missing: ${executable}" >&2
    exit 1
  fi
done
if ! "${DOTNET_BIN}" --list-sdks | grep -Eq '^8\.0\.'; then
  echo ".NET SDK 8 is required for the NativeAOT helper." >&2
  exit 1
fi
"${CLANG_BIN}" --version >/dev/null
"${LLD_BIN}" --version >/dev/null

rm -rf -- "${PROJECT_ROOT}/.venv"
"${PYTHON_BIN}" -m venv "${PROJECT_ROOT}/.venv"
"${PROJECT_ROOT}/.venv/bin/python" -m pip install --upgrade pip
cd "${PROJECT_ROOT}"
"${PROJECT_ROOT}/.venv/bin/python" -m pip install -r "${PROJECT_ROOT}/requirements-dev.lock"
"${PROJECT_ROOT}/scripts/prepare_cryptopp_macos.sh" \
  "${BUILD_CACHE}/cryptopp" >/dev/null
echo "Bootstrap complete with official Python ${PYTHON_VERSION}."
echo "Run scripts/build_release_macos_arm64.sh for the release gate."
