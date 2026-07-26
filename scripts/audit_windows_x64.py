from __future__ import annotations

import argparse
import struct
from pathlib import Path


PE_X64 = 0x8664
PE_SUFFIXES = {".exe", ".dll", ".pyd"}


def pe_machine(path: Path) -> int:
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("missing MZ header")
        stream.seek(0x3C)
        pe_offset_data = stream.read(4)
        if len(pe_offset_data) != 4:
            raise ValueError("truncated DOS header")
        pe_offset = struct.unpack("<I", pe_offset_data)[0]
        stream.seek(pe_offset)
        if stream.read(4) != b"PE\0\0":
            raise ValueError("missing PE signature")
        machine_data = stream.read(2)
        if len(machine_data) != 2:
            raise ValueError("truncated PE header")
        return struct.unpack("<H", machine_data)[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("application", type=Path)
    args = parser.parse_args()
    root = args.application.resolve()
    required = [
        root / "PS4 FFPFSC.exe",
        root / "ps4ffpsc-worker.exe",
        root / "_internal" / "bin" / "ps4_pkg_extract.exe",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("missing required bundled file(s): " + ", ".join(missing))

    checked = 0
    invalid: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in PE_SUFFIXES:
            continue
        checked += 1
        try:
            machine = pe_machine(path)
        except ValueError as error:
            invalid.append(f"{path}: {error}")
            continue
        if machine != PE_X64:
            invalid.append(f"{path}: machine=0x{machine:04X}, expected x64")
    if invalid:
        raise SystemExit("\n".join(invalid))
    if checked < 3:
        raise SystemExit("no complete Windows executable set was found")
    print(f"Windows x64 PE audit passed: {root} ({checked} binaries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
