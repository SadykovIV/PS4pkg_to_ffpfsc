from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pytest

from ps4ffpsc.npbind import inspect_npbind, repair_npbind_footer, validate_npbind


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

    inspection = inspect_npbind(path)
    assert inspection["status"] == "repairable_footer"
    assert inspection["footer_valid"] is False


def test_npbind_footer_repair_is_atomic_and_changes_only_digest(
    tmp_path: Path,
) -> None:
    path = tmp_path / "npbind.dat"
    original = bytearray(_make_npbind())
    original[-4:] = bytes.fromhex("87f1c2cf")
    path.write_bytes(original)

    report = repair_npbind_footer(path)
    repaired = path.read_bytes()

    assert report["repaired"] is True
    assert report["previous_sha1"] == bytes(original[-20:]).hex()
    assert repaired[:-20] == bytes(original[:-20])
    assert repaired[-20:] == hashlib.sha1(repaired[:-20]).digest()
    assert validate_npbind(path)["footer_valid"] is True
    assert not list(tmp_path.glob("*.partial"))


def test_npbind_footer_repair_rejects_invalid_layout_without_writing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "npbind.dat"
    path.write_bytes(b"invalid")
    before = path.read_bytes()

    with pytest.raises(ValueError, match="too small"):
        repair_npbind_footer(path)

    assert path.read_bytes() == before
