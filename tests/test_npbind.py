from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pytest

from ps4ffpsc.npbind import validate_npbind


def _make_npbind(entry_count: int = 1) -> bytes:
    size = 0x80 + 0x180 * entry_count + 20
    data = bytearray(size)
    struct.pack_into(
        ">IIQQQ",
        data,
        0,
        0xD294A018,
        1,
        size,
        0x180,
        entry_count,
    )
    data[-20:] = hashlib.sha1(data[:-20]).digest()
    return bytes(data)


@pytest.mark.parametrize(("entry_count", "size"), [(1, 532), (3, 1300)])
def test_npbind_validator_accepts_declared_layout_and_sha1(
    tmp_path: Path,
    entry_count: int,
    size: int,
) -> None:
    path = tmp_path / "npbind.dat"
    path.write_bytes(_make_npbind(entry_count))

    report = validate_npbind(path)

    assert report["status"] == "valid"
    assert report["entry_count"] == entry_count
    assert report["declared_size"] == size
    assert len(report["sha1"]) == 40


def test_npbind_validator_rejects_metro_style_four_byte_footer_corruption(
    tmp_path: Path,
) -> None:
    path = tmp_path / "npbind.dat"
    damaged = bytearray(_make_npbind())
    damaged[-4:] = bytes.fromhex("87f1c2cf")
    path.write_bytes(damaged)

    with pytest.raises(ValueError, match="SHA-1 footer mismatch"):
        validate_npbind(path)
