from __future__ import annotations

import hashlib
import os
import stat
import struct
from pathlib import Path
from typing import Any


NPBIND_MAGIC = 0xD294A018
NPBIND_HEADER_SIZE = 0x80
NPBIND_ENTRY_SIZE = 0x180
NPBIND_DIGEST_SIZE = 20
_NPBIND_HEADER = struct.Struct(">IIQQQ")


def inspect_npbind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    minimum_size = NPBIND_HEADER_SIZE + NPBIND_DIGEST_SIZE
    if len(data) < minimum_size:
        raise ValueError(
            f"npbind.dat is too small: expected at least {minimum_size} bytes, "
            f"got {len(data)}"
        )
    magic, version, declared_size, entry_size, entry_count = _NPBIND_HEADER.unpack_from(data)
    if magic != NPBIND_MAGIC:
        raise ValueError(f"npbind.dat has invalid magic: 0x{magic:08X}")
    if version != 1:
        raise ValueError(f"npbind.dat has unsupported version: {version}")
    if declared_size != len(data):
        raise ValueError(
            "npbind.dat declared size does not match the file: "
            f"declared={declared_size}, actual={len(data)}"
        )
    if entry_size != NPBIND_ENTRY_SIZE:
        raise ValueError(
            f"npbind.dat has unsupported entry size: 0x{entry_size:X}"
        )
    expected_size = (
        NPBIND_HEADER_SIZE + entry_count * entry_size + NPBIND_DIGEST_SIZE
    )
    if entry_count <= 0 or expected_size != len(data):
        raise ValueError(
            "npbind.dat entry layout does not match the file size: "
            f"expected={expected_size}, actual={len(data)}"
        )
    calculated_digest = hashlib.sha1(
        data[:-NPBIND_DIGEST_SIZE],
        usedforsecurity=False,
    ).digest()
    stored_digest = data[-NPBIND_DIGEST_SIZE:]
    return {
        "status": "valid" if calculated_digest == stored_digest else "repairable_footer",
        "declared_size": declared_size,
        "entry_size": entry_size,
        "entry_count": entry_count,
        "sha1": stored_digest.hex(),
        "calculated_sha1": calculated_digest.hex(),
        "footer_valid": calculated_digest == stored_digest,
    }


def validate_npbind(path: Path) -> dict[str, Any]:
    report = inspect_npbind(path)
    if report["footer_valid"]:
        return report
    raise ValueError(
        "npbind.dat SHA-1 footer mismatch: "
        f"expected={report['calculated_sha1']}, actual={report['sha1']}"
    )


def repair_npbind_footer(path: Path) -> dict[str, Any]:
    """Repair only a structurally valid SHA-1 footer via atomic replacement."""

    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError(f"npbind.dat must be a regular file: {path}")
    report = inspect_npbind(path)
    if report["footer_valid"]:
        return {**report, "repaired": False}

    data = path.read_bytes()
    corrected = data[:-NPBIND_DIGEST_SIZE] + bytes.fromhex(
        report["calculated_sha1"]
    )
    partial = path.with_name(f".{path.name}.footer-repair.partial")
    if partial.exists():
        partial.unlink()
    try:
        with partial.open("xb") as stream:
            stream.write(corrected)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)
    verified = validate_npbind(path)
    return {
        **verified,
        "repaired": True,
        "previous_sha1": report["sha1"],
    }
