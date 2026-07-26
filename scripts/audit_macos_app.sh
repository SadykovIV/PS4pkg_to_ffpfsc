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
while IFS= read -r -d '' candidate; do
  if ! file "${candidate}" | grep -q 'Mach-O'; then
    continue
  fi
  architectures="$(lipo -archs "${candidate}")"
  if [[ "${architectures}" != "arm64" ]]; then
    echo "Non-arm64 Mach-O: ${candidate} (${architectures})" >&2
    bad_arch=1
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

if [[ "${bad_arch}" -ne 0 || "${bad_link}" -ne 0 ]]; then
  exit 1
fi
echo "ARM64 and dependency audit passed: ${APP_PATH}"
