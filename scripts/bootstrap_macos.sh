#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This bootstrap script targets macOS." >&2
  exit 1
fi
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Apple Silicon arm64 is required; Rosetta is not used." >&2
  exit 1
fi
command -v brew >/dev/null 2>&1 || {
  echo "Homebrew is required to install Crypto++." >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  echo "Python 3.11+ is required." >&2
  exit 1
}
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' || {
  echo "Python 3.11+ is required." >&2
  exit 1
}

if ! brew list --versions cryptopp >/dev/null 2>&1; then
  brew install cryptopp
fi
python3 -m venv "${PROJECT_ROOT}/.venv"
"${PROJECT_ROOT}/.venv/bin/python" -m pip install --upgrade pip
cd "${PROJECT_ROOT}"
"${PROJECT_ROOT}/.venv/bin/python" -m pip install -r "${PROJECT_ROOT}/requirements-dev.lock"
echo "Bootstrap complete. Run scripts/build_macos.sh."
