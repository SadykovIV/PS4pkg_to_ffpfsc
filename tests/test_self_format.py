# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import struct

import pytest

from ps4ffpsc.self_format import (
    SelfFormatError,
    SelfIdentity,
    read_self_identity,
    unwrap_fake_self,
    wrap_fake_self,
)


ELF_HEADER = struct.Struct("<16sHHIQQQIHHHHHH")
PROGRAM_HEADER = struct.Struct("<II6Q")
SELF_HEADER = struct.Struct("<4s4BIHHQHH4x")
SELF_ENTRY = struct.Struct("<4Q")


def _synthetic_elf() -> bytes:
    program_headers = (
        (1, 5, 0x4000, 0x400000, 0x400000, 0x180, 0x180, 0x4000),
        (2, 6, 0x4040, 0x400040, 0x400040, 0x30, 0x30, 8),
        (0x61000010, 4, 0x5000, 0x500000, 0x500000, 0x50, 0x50, 0x4000),
        (0x61000001, 4, 0x5010, 0x500010, 0x500010, 0x18, 0x18, 8),
        (0x61000000, 4, 0x6000, 0x600000, 0x600000, 0x80, 0x80, 0x10),
        (0x6FFFFF00, 4, 0x7000, 0, 0, 0x30, 0x30, 1),
        (0x6FFFFF01, 4, 0x7030, 0, 0, 0x27, 0x27, 1),
    )
    ident = b"\x7fELF" + bytes((2, 1, 1, 9, 0)) + b"\0" * 7
    output = bytearray(0x7840)
    ELF_HEADER.pack_into(
        output,
        0,
        ident,
        0xFE10,
        0x3E,
        1,
        0x400000,
        ELF_HEADER.size,
        0x7800,
        0,
        ELF_HEADER.size,
        PROGRAM_HEADER.size,
        len(program_headers),
        0x40,
        1,
        0,
    )
    for index, header in enumerate(program_headers):
        PROGRAM_HEADER.pack_into(
            output,
            ELF_HEADER.size + index * PROGRAM_HEADER.size,
            *header,
        )

    output[0x4000:0x4180] = bytes((index * 7 + 3) & 0xFF for index in range(0x180))
    output[0x4040:0x4070] = b"DYNAMIC" * 6
    output[0x5000:0x5050] = bytes(range(0x50))
    output[0x5010:0x5028] = b"PROCESS-PARAMETER-BYTES"[:0x18]
    output[0x6000:0x6080] = bytes((255 - index) & 0xFF for index in range(0x80))
    output[0x7000:0x7030] = b"synthetic comment segment".ljust(0x30, b"\0")
    output[0x7030:0x7057] = b"synthetic version trailer".ljust(0x27, b"\0")
    output[0x7800:0x7840] = b"section table intentionally unavailable".ljust(0x40, b"\0")
    return bytes(output)


def _program_segments(elf: bytes) -> tuple[bytes, ...]:
    header = ELF_HEADER.unpack_from(elf)
    phoff, phentsize, phnum = header[5], header[9], header[10]
    result = []
    for index in range(phnum):
        fields = PROGRAM_HEADER.unpack_from(elf, phoff + index * phentsize)
        offset, size = fields[2], fields[5]
        result.append(elf[offset : offset + size])
    return tuple(result)


def _entry_flags(wrapped: bytes, index: int) -> int:
    return SELF_ENTRY.unpack_from(wrapped, SELF_HEADER.size + index * SELF_ENTRY.size)[0]


def test_round_trip_preserves_identity_and_every_program_segment() -> None:
    source = _synthetic_elf()
    identity = SelfIdentity(
        paid=0x3100000000000001,
        ptype=1,
        app_version=0x0102030405060708,
        fw_version=0x090A0B0C0D0E0F10,
    )

    wrapped = wrap_fake_self(source, identity)
    restored, restored_identity = unwrap_fake_self(wrapped)

    assert read_self_identity(wrapped) == identity
    assert restored_identity == identity
    assert _program_segments(restored) == _program_segments(source)
    restored_header = ELF_HEADER.unpack_from(restored)
    assert restored_header[6] == 0
    assert restored_header[12] == 0
    assert restored_header[13] == 0


def test_second_round_trip_is_deterministic() -> None:
    identity = SelfIdentity(0x3100000000000001, 1, 17, 42)
    first = wrap_fake_self(_synthetic_elf(), identity)
    plain, _ = unwrap_fake_self(first)
    second = wrap_fake_self(plain, identity)
    third_plain, _ = unwrap_fake_self(second)

    assert second == wrap_fake_self(plain, identity)
    assert _program_segments(third_plain) == _program_segments(plain)


def test_transformations_do_not_mutate_mutable_source_buffers() -> None:
    elf = bytearray(_synthetic_elf())
    original_elf = bytes(elf)
    identity = SelfIdentity(1, 1, 2, 3)
    wrapped = wrap_fake_self(elf, identity)
    wrapped_buffer = bytearray(wrapped)
    original_wrapped = bytes(wrapped_buffer)

    unwrap_fake_self(memoryview(wrapped_buffer))

    assert bytes(elf) == original_elf
    assert bytes(wrapped_buffer) == original_wrapped


@pytest.mark.parametrize(
    ("flag", "message"),
    ((1 << 1, "encrypted"), (1 << 3, "compressed")),
)
def test_protected_entries_fail_clearly(flag: int, message: str) -> None:
    wrapped = bytearray(wrap_fake_self(_synthetic_elf(), SelfIdentity(1, 1, 0, 0)))
    first_data_entry = 1
    flags = _entry_flags(wrapped, first_data_entry)
    struct.pack_into(
        "<Q",
        wrapped,
        SELF_HEADER.size + first_data_entry * SELF_ENTRY.size,
        flags | flag,
    )

    with pytest.raises(SelfFormatError, match=message):
        unwrap_fake_self(wrapped)


def test_entry_outside_declared_file_fails_clearly() -> None:
    wrapped = bytearray(wrap_fake_self(_synthetic_elf(), SelfIdentity(1, 1, 0, 0)))
    self_header = SELF_HEADER.unpack_from(wrapped)
    declared_size = self_header[8]
    entry_offset = SELF_HEADER.size + SELF_ENTRY.size
    struct.pack_into("<Q", wrapped, entry_offset + 8, declared_size - 4)
    struct.pack_into("<Q", wrapped, entry_offset + 16, 8)

    with pytest.raises(SelfFormatError, match="outside the source"):
        unwrap_fake_self(wrapped)


def test_duplicate_program_mapping_fails_clearly() -> None:
    wrapped = bytearray(wrap_fake_self(_synthetic_elf(), SelfIdentity(1, 1, 0, 0)))
    first_flags = _entry_flags(wrapped, 1)
    second_data_entry = 3
    second_offset = SELF_HEADER.size + second_data_entry * SELF_ENTRY.size
    second_fields = list(SELF_ENTRY.unpack_from(wrapped, second_offset))
    second_fields[0] = (second_fields[0] & ~(((1 << 16) - 1) << 20)) | (
        first_flags & (((1 << 16) - 1) << 20)
    )
    SELF_ENTRY.pack_into(wrapped, second_offset, *second_fields)

    with pytest.raises(SelfFormatError, match="multiple SELF entries"):
        unwrap_fake_self(wrapped)


def test_non_fake_identity_is_rejected() -> None:
    with pytest.raises(SelfFormatError, match="fake type 1"):
        wrap_fake_self(_synthetic_elf(), SelfIdentity(1, 4, 0, 0))


@pytest.mark.parametrize(
    ("offset", "value", "message"),
    (
        (4, 1, "ELF64"),
        (5, 2, "little-endian"),
    ),
)
def test_unsupported_elf_encoding_fails_clearly(
    offset: int, value: int, message: str
) -> None:
    source = bytearray(_synthetic_elf())
    source[offset] = value

    with pytest.raises(SelfFormatError, match=message):
        wrap_fake_self(source, SelfIdentity(1, 1, 0, 0))
