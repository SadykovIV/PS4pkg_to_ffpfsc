#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 2 ]]; then
  echo "usage: $0 <openorbis-toolchain-root> <output-prx>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
SOURCE_ROOT="${PROJECT_ROOT}/third_party/ps4_dlc_patch/prx_src"
TOOLCHAIN_ROOT="$(cd -- "$1" && pwd)"
OUTPUT_PATH="$2"
CLANG_BIN="${PS4FFPSC_CLANG:-clang}"
LLD_BIN="${PS4FFPSC_LLD:-ld.lld}"

if [[ ! -f "${TOOLCHAIN_ROOT}/link.x" ]]; then
  echo "invalid OpenOrbis toolchain root: ${TOOLCHAIN_ROOT}" >&2
  exit 1
fi
if ! command -v "${CLANG_BIN}" >/dev/null 2>&1; then
  echo "clang is required to build the DLC module template" >&2
  exit 1
fi
if ! command -v "${LLD_BIN}" >/dev/null 2>&1; then
  echo "ld.lld is required to build the DLC module template" >&2
  exit 1
fi

case "$(uname -s)" in
  Darwin)
    CREATE_FSELF="${TOOLCHAIN_ROOT}/bin/macos/create-fself-macos"
    ;;
  Linux)
    CREATE_FSELF="${TOOLCHAIN_ROOT}/bin/linux/create-fself"
    ;;
  *)
    echo "module template build supports macOS and Linux hosts" >&2
    exit 1
    ;;
esac
if [[ ! -x "${CREATE_FSELF}" ]]; then
  echo "create-fself tool is missing: ${CREATE_FSELF}" >&2
  exit 1
fi

BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ps4ffpsc-dlc-module.XXXXXX")"
trap 'rm -rf "${BUILD_ROOT}"' EXIT
OBJECTS=()

for source in "${SOURCE_ROOT}"/*.c "${SOURCE_ROOT}"/*.s "${SOURCE_ROOT}"/*.S; do
  [[ -f "${source}" ]] || continue
  object="${BUILD_ROOT}/$(basename "${source}").o"
  "${CLANG_BIN}" --target=x86_64-pc-freebsd12-elf \
    -fPIC -funwind-tables -I"${TOOLCHAIN_ROOT}/include" \
    -c "${source}" -o "${object}"
  OBJECTS+=("${object}")
done

if [[ "${#OBJECTS[@]}" -eq 0 ]]; then
  echo "no DLC module sources were found" >&2
  exit 1
fi

ELF_PATH="${BUILD_ROOT}/dlcldr.elf"
OELF_PATH="${BUILD_ROOT}/dlcldr.oelf"
PRX_PATH="${BUILD_ROOT}/dlcldr.prx"
"${LLD_BIN}" -m elf_x86_64 -pie \
  --script "${TOOLCHAIN_ROOT}/link.x" --eh-frame-hdr \
  -o "${ELF_PATH}" -L"${TOOLCHAIN_ROOT}/lib" \
  -lc -lkernel -lSceSysmodule -lSceAppContent \
  -lSceAppContentIro -lSceAppContentSc \
  -e module_start "${OBJECTS[@]}"

(
  cd -- "${BUILD_ROOT}"
  export OO_PS4_TOOLCHAIN="${TOOLCHAIN_ROOT}"
  "${CREATE_FSELF}" -in "${ELF_PATH}" --out "${OELF_PATH}" \
    --lib "${PRX_PATH}" --libname dlcldr --paid 0x3800000000000011
)

if [[ ! -s "${PRX_PATH}" ]]; then
  echo "DLC module template was not created" >&2
  exit 1
fi
magic="$(od -An -tx1 -N4 "${PRX_PATH}" | tr -d ' \n')"
if [[ "${magic}" != "4f153d1d" ]]; then
  echo "DLC module template has unexpected magic: ${magic}" >&2
  exit 1
fi

mkdir -p "$(dirname -- "${OUTPUT_PATH}")"
cp "${PRX_PATH}" "${OUTPUT_PATH}.partial"
mv "${OUTPUT_PATH}.partial" "${OUTPUT_PATH}"
echo "DLC module template created: ${OUTPUT_PATH}"
