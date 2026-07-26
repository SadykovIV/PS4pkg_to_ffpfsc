#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "usage: $0 <source-tree>" >&2
  exit 2
fi

SOURCE_ROOT="$(cd -- "$1" && pwd)"
failures=0

while IFS= read -r path; do
  echo "forbidden generated/user path: ${path}" >&2
  failures=1
done < <(
  find "${SOURCE_ROOT}" \
    -path "${SOURCE_ROOT}/.git" -prune -o \
    \( -type d \( \
      -name '.venv' -o -name '.pytest_cache' -o -name '__pycache__' -o \
      -name 'build' -o -name 'build-release' -o -name 'dist' -o \
      -name 'release' -o -name 'logs' -o -name 'output' -o \
      -name 'unpacked' -o -name 'work' -o -name '*.app' \
    \) -o -type f \( \
      -iname '*.pkg' -o -iname '*.ffpfsc' -o -iname '*.dmg' -o \
      -iname '*.zip' -o -iname '*.pyc' -o -iname '*.partial' \
    \) \) -print
)

while IFS= read -r path; do
  echo "unexpected large source file (>20 MiB): ${path}" >&2
  failures=1
done < <(
  find "${SOURCE_ROOT}" \
    -path "${SOURCE_ROOT}/.git" -prune -o \
    -type f -size +20480k -print
)

while IFS= read -r path; do
  if file -b "${path}" | grep -q 'Mach-O'; then
    echo "compiled Mach-O found in source tree: ${path}" >&2
    failures=1
  fi
done < <(
  find "${SOURCE_ROOT}" \
    -path "${SOURCE_ROOT}/.git" -prune -o \
    -type f -perm -111 -print
)

if [[ "${failures}" -ne 0 ]]; then
  exit 1
fi

echo "Source tree audit passed: ${SOURCE_ROOT}"
