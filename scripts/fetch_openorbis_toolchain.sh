#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "usage: $0 <cache-directory>" >&2
  exit 2
fi

VERSION="0.5.4"
ARCHIVE_NAME="toolchain-llvm-18.tar.gz"
ARCHIVE_SHA256="3c7cd5bb593ca74fa1c13fd59f3938dc0fc07985167f7275063019e63abe4526"
DOWNLOAD_URL="https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain/releases/download/v${VERSION}/${ARCHIVE_NAME}"
CACHE_ROOT="$(mkdir -p "$1" && cd -- "$1" && pwd)"
ARCHIVE_PATH="${CACHE_ROOT}/${ARCHIVE_NAME}"
EXTRACT_ROOT="${CACHE_ROOT}/v${VERSION}"
TOOLCHAIN_ROOT="${EXTRACT_ROOT}/OpenOrbis/PS4Toolchain"

verify_archive() {
  local actual
  actual="$(shasum -a 256 "${ARCHIVE_PATH}" | awk '{print $1}')"
  [[ "${actual}" == "${ARCHIVE_SHA256}" ]]
}

if [[ ! -f "${ARCHIVE_PATH}" ]] || ! verify_archive; then
  rm -f "${ARCHIVE_PATH}"
  curl --fail --location --retry 3 --retry-delay 2 \
    --output "${ARCHIVE_PATH}.partial" "${DOWNLOAD_URL}"
  mv "${ARCHIVE_PATH}.partial" "${ARCHIVE_PATH}"
  if ! verify_archive; then
    echo "OpenOrbis archive checksum mismatch" >&2
    rm -f "${ARCHIVE_PATH}"
    exit 1
  fi
fi

if [[ ! -f "${TOOLCHAIN_ROOT}/link.x" ]]; then
  rm -rf "${EXTRACT_ROOT}"
  mkdir -p "${EXTRACT_ROOT}"
  tar -xzf "${ARCHIVE_PATH}" -C "${EXTRACT_ROOT}"
fi

if [[ ! -f "${TOOLCHAIN_ROOT}/link.x" ]]; then
  echo "OpenOrbis toolchain layout is incomplete" >&2
  exit 1
fi

printf '%s\n' "${TOOLCHAIN_ROOT}"
