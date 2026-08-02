#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <Application.app>" >&2
  exit 2
fi

APP_PATH="$(cd -- "$(dirname -- "$1")" && pwd)/$(basename -- "$1")"
if [[ ! -d "${APP_PATH}" ]]; then
  echo "Application bundle not found: ${APP_PATH}" >&2
  exit 1
fi

bad_arch=0
bad_link=0
bad_minos=0
max_minos="13.0"

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

declared_minos="$(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' \
  "${APP_PATH}/Contents/Info.plist" 2>/dev/null || true)"
if [[ "${declared_minos}" != "${max_minos}" ]]; then
  echo "Unexpected LSMinimumSystemVersion: ${declared_minos:-missing} (expected ${max_minos})" >&2
  bad_minos=1
fi
while IFS= read -r -d '' candidate; do
  if ! file "${candidate}" | grep -q 'Mach-O'; then
    continue
  fi
  architectures="$(lipo -archs "${candidate}")"
  if [[ "${architectures}" != "arm64" ]]; then
    echo "Non-arm64 Mach-O: ${candidate} (${architectures})" >&2
    bad_arch=1
  fi
  minos_values="$(vtool -show-build "${candidate}" 2>/dev/null | \
    awk '$1 == "minos" {print $2}')"
  if [[ -z "${minos_values}" ]]; then
    echo "Missing Mach-O deployment target: ${candidate}" >&2
    bad_minos=1
  else
    while IFS= read -r minos; do
      if version_exceeds "${minos}" "${max_minos}"; then
        echo "Mach-O requires macOS ${minos}, above ${max_minos}: ${candidate}" >&2
        bad_minos=1
      fi
    done <<< "${minos_values}"
  fi
  while IFS= read -r dependency; do
    dependency="${dependency#"${dependency%%[![:space:]]*}"}"
    dependency="${dependency%% *}"
    case "${dependency}" in
      ""|@rpath/*|@loader_path/*|@executable_path/*|/usr/lib/*|/System/Library/*)
        ;;
      *)
        echo "External dependency: ${candidate} -> ${dependency}" >&2
        bad_link=1
        ;;
    esac
  done < <(otool -L "${candidate}" | tail -n +2)
done < <(find "${APP_PATH}" -type f -print0)

if [[ "${bad_arch}" -ne 0 || "${bad_link}" -ne 0 || "${bad_minos}" -ne 0 ]]; then
  exit 1
fi
echo "ARM64, macOS ${max_minos}, and dependency audit passed: ${APP_PATH}"
