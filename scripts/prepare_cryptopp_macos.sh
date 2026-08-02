#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "usage: $0 <cache-directory>" >&2
  exit 2
fi
if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "This Crypto++ build targets native macOS arm64." >&2
  exit 1
fi

VERSION="8.9.0"
ARCHIVE_NAME="cryptopp890.zip"
ARCHIVE_SHA256="4cc0ccc324625b80b695fcd3dee63a66f1a460d3e51b71640cdbfc4cd1a3779c"
DOWNLOAD_URL="https://github.com/weidai11/cryptopp/releases/download/CRYPTOPP_8_9_0/${ARCHIVE_NAME}"
DEPLOYMENT_TARGET="13.0"
CACHE_ROOT="$(mkdir -p "$1" && cd -- "$1" && pwd)"
ARCHIVE_PATH="${CACHE_ROOT}/${ARCHIVE_NAME}"
SOURCE_ROOT="${CACHE_ROOT}/cryptopp-${VERSION}-source"
INSTALL_ROOT="${CACHE_ROOT}/cryptopp-${VERSION}-macos-arm64-${DEPLOYMENT_TARGET}"
STAMP_PATH="${INSTALL_ROOT}/.ps4ffpsc-build-stamp"
EXPECTED_STAMP="sha256=${ARCHIVE_SHA256};arch=arm64;minos=${DEPLOYMENT_TARGET};cxx=apple-clang-cxx17"

version_exceeds() {
  awk -v actual="$1" -v maximum="$2" 'BEGIN {
    split(actual, a, "."); split(maximum, m, ".");
    for (i = 1; i <= 3; i++) {
      av = (a[i] == "" ? 0 : a[i] + 0);
      mv = (m[i] == "" ? 0 : m[i] + 0);
      if (av > mv) exit 0;
      if (av < mv) exit 1;
    }
    exit 1;
  }'
}

verify_archive() {
  local actual
  actual="$(shasum -a 256 "${ARCHIVE_PATH}" | awk '{print $1}')"
  [[ "${actual}" == "${ARCHIVE_SHA256}" ]]
}

audit_static_archive() {
  local archive="$1"
  local audit_root object architectures minos checked
  [[ -s "${archive}" ]] || return 1
  audit_root="$(mktemp -d "${TMPDIR:-/tmp}/ps4ffpsc-cryptopp-audit.XXXXXX")"
  checked=0
  (
    cd -- "${audit_root}"
    /usr/bin/ar -x "${archive}"
  )
  while IFS= read -r -d '' object; do
    if ! file "${object}" | grep -q 'Mach-O'; then
      continue
    fi
    checked=$((checked + 1))
    architectures="$(lipo -archs "${object}")"
    if [[ "${architectures}" != "arm64" ]]; then
      echo "Unexpected Crypto++ object architecture: ${object} (${architectures})" >&2
      rm -rf -- "${audit_root}"
      return 1
    fi
    minos="$(vtool -show-build "${object}" 2>/dev/null | awk '$1 == "minos" {print $2}')"
    if [[ -z "${minos}" ]] || version_exceeds "${minos}" "${DEPLOYMENT_TARGET}"; then
      echo "Crypto++ object exceeds macOS ${DEPLOYMENT_TARGET}: ${object} (${minos:-unknown})" >&2
      rm -rf -- "${audit_root}"
      return 1
    fi
  done < <(find "${audit_root}" -type f -name '*.o' -print0)
  rm -rf -- "${audit_root}"
  [[ "${checked}" -gt 0 ]]
}

if [[ ! -f "${ARCHIVE_PATH}" ]] || ! verify_archive; then
  rm -f -- "${ARCHIVE_PATH}" "${ARCHIVE_PATH}.partial"
  curl --fail --location --retry 3 --retry-delay 2 \
    --output "${ARCHIVE_PATH}.partial" "${DOWNLOAD_URL}"
  mv "${ARCHIVE_PATH}.partial" "${ARCHIVE_PATH}"
  if ! verify_archive; then
    echo "Crypto++ archive checksum mismatch" >&2
    rm -f -- "${ARCHIVE_PATH}"
    exit 1
  fi
fi

if [[ -f "${STAMP_PATH}" ]] \
    && [[ "$(cat "${STAMP_PATH}")" == "${EXPECTED_STAMP}" ]] \
    && [[ -f "${INSTALL_ROOT}/include/cryptopp/aes.h" ]] \
    && audit_static_archive "${INSTALL_ROOT}/lib/libcryptopp.a"; then
  printf '%s\n' "${INSTALL_ROOT}"
  exit 0
fi

rm -rf -- "${SOURCE_ROOT}" "${INSTALL_ROOT}" "${INSTALL_ROOT}.partial"
mkdir -p "${SOURCE_ROOT}" "${INSTALL_ROOT}.partial"
ditto -x -k "${ARCHIVE_PATH}" "${SOURCE_ROOT}"
if [[ ! -f "${SOURCE_ROOT}/GNUmakefile" ]]; then
  echo "Crypto++ source archive layout is incomplete" >&2
  exit 1
fi

JOBS="$(sysctl -n hw.logicalcpu 2>/dev/null || printf '4')"
case "${JOBS}" in
  ''|*[!0-9]*) JOBS=4 ;;
esac
CXXFLAGS="-std=c++17 -stdlib=libc++ -DNDEBUG -O3 -fPIC -arch arm64 -mmacosx-version-min=${DEPLOYMENT_TARGET}"
MACOSX_DEPLOYMENT_TARGET="${DEPLOYMENT_TARGET}" \
  make -s -C "${SOURCE_ROOT}" -f GNUmakefile -j"${JOBS}" static \
    CXX=/usr/bin/c++ CC=/usr/bin/cc CXXFLAGS="${CXXFLAGS}" >&2
make -s -C "${SOURCE_ROOT}" -f GNUmakefile install-lib \
  PREFIX="${INSTALL_ROOT}.partial" CXX=/usr/bin/c++ CXXFLAGS="${CXXFLAGS}" >&2

if [[ ! -f "${INSTALL_ROOT}.partial/include/cryptopp/aes.h" ]] \
    || ! audit_static_archive "${INSTALL_ROOT}.partial/lib/libcryptopp.a"; then
  echo "Crypto++ macOS 13 static build audit failed" >&2
  exit 1
fi
printf '%s\n' "${EXPECTED_STAMP}" > "${INSTALL_ROOT}.partial/.ps4ffpsc-build-stamp"
mv "${INSTALL_ROOT}.partial" "${INSTALL_ROOT}"
printf '%s\n' "${INSTALL_ROOT}"
