#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail

if [[ "$#" -ne 3 ]]; then
  echo "usage: $0 <external-prx-template> <runtime-id> <output-directory>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_PATH="$(cd -- "$(dirname -- "$1")" && pwd)/$(basename -- "$1")"
RUNTIME_ID="$2"
DOTNET_BIN="${PS4FFPSC_DOTNET:-dotnet}"
mkdir -p "$3"
OUTPUT_PATH="$(cd -- "$3" && pwd)"

if [[ ! -f "${TEMPLATE_PATH}" ]]; then
  echo "PRX template does not exist: ${TEMPLATE_PATH}" >&2
  exit 1
fi
case "${OUTPUT_PATH}/" in
  "${SCRIPT_DIR}/"*)
    echo "output must be outside the vendored source directory" >&2
    exit 1
    ;;
esac
if ! command -v "${DOTNET_BIN}" >/dev/null 2>&1; then
  echo ".NET SDK 8 is required" >&2
  exit 1
fi
if ! "${DOTNET_BIN}" --list-sdks | grep -Eq '^8\.0\.'; then
  echo ".NET SDK 8 is required" >&2
  exit 1
fi

BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ps4-dlc-patch-build.XXXXXX")"
trap 'rm -rf -- "${BUILD_ROOT}"' EXIT

"${DOTNET_BIN}" publish "${SCRIPT_DIR}/ps4-dlc-patch.csproj" \
  --configuration Release \
  --runtime "${RUNTIME_ID}" \
  --self-contained true \
  --output "${OUTPUT_PATH}" \
  -p:PublishAot=true \
  "-p:DlcPrxTemplatePath=${TEMPLATE_PATH}" \
  "-p:BaseOutputPath=${BUILD_ROOT}/bin/" \
  "-p:BaseIntermediateOutputPath=${BUILD_ROOT}/obj/" \
  "-p:MSBuildProjectExtensionsPath=${BUILD_ROOT}/obj/"

echo "NativeAOT publish completed: ${OUTPUT_PATH}"
