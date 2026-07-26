#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

if [[ ! -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
  echo "Python environment is missing. Run scripts/bootstrap_macos.sh first." >&2
  exit 1
fi
exec "${PROJECT_ROOT}/.venv/bin/python" "${PROJECT_ROOT}/ps4ffpsc-gui"
