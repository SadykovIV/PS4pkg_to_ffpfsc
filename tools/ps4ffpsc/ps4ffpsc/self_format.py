# SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
# SPDX-FileCopyrightText: Copyright 2023-2025 OpenOrbis contributors
# SPDX-FileCopyrightText: Copyright 2026 PS4pkg_to_ffpfsc contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small, dependency-free helpers for unencrypted PS4 fake SELF files.

The container and ELF structures are adapted from the GPL-2.0-or-later
shadPS4 loader and the GPL-3.0 OpenOrbis ``make_fself.py`` implementation:

* https://github.com/shadps4-emu/shadPS4
* https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain

Only the deliberately simple fake-SELF subset is supported: ELF64 little
endian input and plain, uncompressed SELF entries.  Unsupported protection or
compression flags fail explicitly instead of producing a subtly damaged ELF.
All public transformations return new immutable ``bytes`` objects and never
modify their source buffer.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
from typing import TypeAlias


Buffer: TypeAlias = bytes | bytearray | memoryview


class SelfFormatError(ValueError):
    """Raised when a SELF/ELF file is malformed or outside the safe subset."""


@dataclass(frozen=True, slots=True)
class SelfIdentity:
    """Identity fields stored in the extended fake-SELF information block."""

    paid: int
    ptype: int
    app_version: int
    fw_version: int

    def __post_init__(self) -> None:
        for name in ("paid", "ptype", "app_version", "fw_version"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be an integer")
            if not 0 <= value <= _U64_MAX:
                raise ValueError(f"{name} must fit in an unsigned 64-bit value")


@dataclass(frozen=True, slots=True)
class _ElfHeader:
    phoff: int
    shoff: int
    ehsize: int
    phentsize: int
    phnum: int
    shentsize: int
    shnum: int
    shstrndx: int


@dataclass(frozen=True, slots=True)
class _ProgramHeader:
    index: int
    ptype: int
    flags: int
    offset: int
    vaddr: int
    paddr: int
    file_size: int
    memory_size: int
    alignment: int


@dataclass(frozen=True, slots=True)
class _SelfEntry:
    index: int
    flags: int
    file_offset: int
    file_size: int
    memory_size: int

    @property
    def segment_index(self) -> int:
        return (self.flags >> _ENTRY_SEGMENT_SHIFT) & _ENTRY_SEGMENT_MASK

    @property
    def has_digests(self) -> bool:
        return bool(self.flags & _ENTRY_HAS_DIGESTS)


@dataclass(frozen=True, slots=True)
class _ParsedSelf:
    raw: bytes
    declared_file_size: int
    header_size: int
    embedded_elf_offset: int
    elf: _ElfHeader
    program_headers: tuple[_ProgramHeader, ...]
    entries: tuple[_SelfEntry, ...]
    identity: SelfIdentity


_U64_MAX = (1 << 64) - 1

_SELF_MAGIC = b"\x4f\x15\x3d\x1d"
_SELF_HEADER = struct.Struct("<4s4BIHHQHH4x")
_SELF_ENTRY = struct.Struct("<4Q")
_SELF_EXTENDED_INFO = struct.Struct("<4Q32s")
_SELF_NPDRM_CONTROL_SIZE = 0x30
_SELF_META_BLOCK_SIZE = 0x50
_SELF_META_FOOTER_SIZE = 0x50
_SELF_SIGNATURE_SIZE = 0x100

_SELF_VERSION = 0
_SELF_MODE = 1
_SELF_ENDIAN_LITTLE = 1
_SELF_ATTRIBUTES = 0x12
_SELF_KEY_TYPE = 0x101
_SELF_FLAGS = 0x22
_FAKE_PROGRAM_TYPE = 1

_ENTRY_ENCRYPTED = 1 << 1
_ENTRY_SIGNED = 1 << 2
_ENTRY_COMPRESSED = 1 << 3
_ENTRY_HAS_BLOCKS = 1 << 11
_ENTRY_BLOCK_SIZE_16K = 2 << 12
_ENTRY_HAS_DIGESTS = 1 << 16
_ENTRY_SEGMENT_SHIFT = 20
_ENTRY_SEGMENT_MASK = 0xFFFF

_ELF_HEADER = struct.Struct("<16sHHIQQQIHHHHHH")
_PROGRAM_HEADER = struct.Struct("<II6Q")
_ELF_MAGIC = b"\x7fELF"
_ELF_CLASS_64 = 2
_ELF_DATA_LITTLE = 1
_ELF_VERSION_CURRENT = 1
_ELF_MACHINE_X86_64 = 0x3E
_ELF_TYPES = frozenset((2, 0xFE00, 0xFE10, 0xFE18))

_PT_LOAD = 1
_PT_SCE_DYNLIBDATA = 0x61000000
_PT_SCE_RELRO = 0x61000010
_PT_SCE_COMMENT = 0x6FFFFF00
_PT_SCE_VERSION = 0x6FFFFF01
_WRAPPED_SEGMENT_TYPES = frozenset(
    (_PT_LOAD, _PT_SCE_RELRO, _PT_SCE_DYNLIBDATA, _PT_SCE_COMMENT)
)

_BLOCK_SIZE = 0x4000
_DIGEST_SIZE = 0x20
_MAX_UNMAPPED_SPACE = 16 * 1024 * 1024


def read_self_identity(source: Buffer) -> SelfIdentity:
    """Read the four identity values from a validated fake SELF container."""

    parsed = _parse_self(_copy_source(source))
    _require_fake_identity(parsed.identity)
    return parsed.identity


def unwrap_fake_self(source: Buffer) -> tuple[bytes, SelfIdentity]:
    """Return a plain ELF and its identity without changing ``source``.

    Section tables are intentionally removed: fake SELF files retain the ELF
    and program headers plus runtime segments, but do not retain arbitrary ELF
    section contents.  Every non-empty program segment must be recoverable from
    a plain SELF entry, a containing program segment, or the standard version
    trailer; otherwise the operation fails.
    """

    parsed = _parse_self(_copy_source(source))
    _require_fake_identity(parsed.identity)

    data_entries: dict[int, _SelfEntry] = {}
    for entry in parsed.entries:
        if entry.has_digests:
            continue
        segment_index = entry.segment_index
        if segment_index >= len(parsed.program_headers):
            raise SelfFormatError(
                f"SELF entry {entry.index} maps to missing program segment "
                f"{segment_index}"
            )
        if segment_index in data_entries:
            raise SelfFormatError(
                f"multiple SELF entries map to program segment {segment_index}"
            )
        program_header = parsed.program_headers[segment_index]
        if entry.file_size != program_header.file_size:
            raise SelfFormatError(
                f"SELF entry {entry.index} size does not match program segment "
                f"{segment_index}"
            )
        data_entries[segment_index] = entry

    header_end = max(
        parsed.elf.ehsize,
        parsed.elf.phoff + parsed.elf.phentsize * parsed.elf.phnum,
    )
    intervals: list[tuple[int, int]] = [(0, header_end)]
    output_end = header_end

    for segment_index, entry in data_entries.items():
        program_header = parsed.program_headers[segment_index]
        segment_end = _checked_add(
            program_header.offset,
            program_header.file_size,
            f"program segment {segment_index}",
        )
        intervals.append((program_header.offset, segment_end))
        output_end = max(output_end, segment_end)

    version_headers = tuple(
        header
        for header in parsed.program_headers
        if header.ptype == _PT_SCE_VERSION and header.file_size
    )
    if len(version_headers) > 1:
        raise SelfFormatError("multiple PS4 version segments are unsupported")
    version_header = version_headers[0] if version_headers else None
    if version_header is not None:
        trailer_end = _checked_add(
            parsed.declared_file_size,
            version_header.file_size,
            "SELF version trailer",
        )
        if trailer_end > len(parsed.raw):
            raise SelfFormatError("SELF version trailer extends outside the source")
        version_end = _checked_add(
            version_header.offset,
            version_header.file_size,
            "PS4 version segment",
        )
        intervals.append((version_header.offset, version_end))
        output_end = max(output_end, version_end)

    _validate_program_segment_coverage(parsed.program_headers, intervals)
    if output_end > len(parsed.raw) + _MAX_UNMAPPED_SPACE:
        raise SelfFormatError("ELF layout contains an excessive sparse gap")

    output = bytearray(output_end)
    embedded_header = _bounded_slice(
        parsed.raw,
        parsed.embedded_elf_offset,
        header_end,
        "embedded ELF headers",
    )
    output[:header_end] = embedded_header
    _strip_section_table(output)

    for segment_index, entry in data_entries.items():
        program_header = parsed.program_headers[segment_index]
        segment_data = _bounded_slice(
            parsed.raw,
            entry.file_offset,
            entry.file_size,
            f"SELF entry {entry.index}",
        )
        start = program_header.offset
        output[start : start + program_header.file_size] = segment_data

    if version_header is not None:
        start = version_header.offset
        trailer = _bounded_slice(
            parsed.raw,
            parsed.declared_file_size,
            version_header.file_size,
            "SELF version trailer",
        )
        output[start : start + version_header.file_size] = trailer

    return bytes(output), parsed.identity


def wrap_fake_self(source_elf: Buffer, identity: SelfIdentity) -> bytes:
    """Wrap a plain PS4 ELF in an unencrypted, uncompressed fake SELF."""

    if not isinstance(identity, SelfIdentity):
        raise TypeError("identity must be a SelfIdentity")
    _require_fake_identity(identity)

    elf_bytes = _copy_source(source_elf)
    elf, program_headers = _parse_elf(elf_bytes, 0)
    normalized_elf = bytearray(elf_bytes)
    _strip_section_table(normalized_elf)

    selected = tuple(
        header
        for header in program_headers
        if header.ptype in _WRAPPED_SEGMENT_TYPES and header.file_size
    )
    if not selected:
        raise SelfFormatError("ELF has no supported non-empty program segments")

    version_headers = tuple(
        header
        for header in program_headers
        if header.ptype == _PT_SCE_VERSION and header.file_size
    )
    if len(version_headers) > 1:
        raise SelfFormatError("multiple PS4 version segments are unsupported")
    version_header = version_headers[0] if version_headers else None

    for header in selected:
        _bounded_slice(
            normalized_elf,
            header.offset,
            header.file_size,
            f"program segment {header.index}",
        )
    if version_header is not None:
        _bounded_slice(
            normalized_elf,
            version_header.offset,
            version_header.file_size,
            "PS4 version segment",
        )

    header_end = max(elf.ehsize, elf.phoff + elf.phentsize * elf.phnum)
    coverage = [(0, header_end)] + [
        (header.offset, header.offset + header.file_size) for header in selected
    ]
    if version_header is not None:
        coverage.append(
            (
                version_header.offset,
                version_header.offset + version_header.file_size,
            )
        )
    _validate_program_segment_coverage(program_headers, coverage)

    entry_count = len(selected) * 2
    embedded_elf_offset = _SELF_HEADER.size + entry_count * _SELF_ENTRY.size
    embedded_header_size = _align_up(header_end, 16)
    identity_offset = embedded_elf_offset + embedded_header_size
    self_header_size = (
        identity_offset
        + _SELF_EXTENDED_INFO.size
        + _SELF_NPDRM_CONTROL_SIZE
    )
    meta_size = (
        entry_count * _SELF_META_BLOCK_SIZE
        + _SELF_META_FOOTER_SIZE
        + _SELF_SIGNATURE_SIZE
    )
    if self_header_size > 0xFFFF or meta_size > 0xFFFF:
        raise SelfFormatError("SELF header metadata exceeds the format limit")

    entries: list[_SelfEntry] = []
    entry_data: list[bytes] = []
    cursor = self_header_size + meta_size
    for header in selected:
        block_count = _align_up(header.file_size, _BLOCK_SIZE) // _BLOCK_SIZE
        digest_bytes = b"\0" * (block_count * _DIGEST_SIZE)
        meta_index = len(entries)
        meta_flags = (
            _ENTRY_SIGNED
            | _ENTRY_HAS_DIGESTS
            | ((meta_index + 1) << _ENTRY_SEGMENT_SHIFT)
        )
        entries.append(
            _SelfEntry(meta_index, meta_flags, cursor, len(digest_bytes), len(digest_bytes))
        )
        entry_data.append(digest_bytes)
        cursor = _align_up(cursor + len(digest_bytes), 16)

        segment_data = bytes(
            normalized_elf[header.offset : header.offset + header.file_size]
        )
        data_index = len(entries)
        data_flags = (
            _ENTRY_SIGNED
            | _ENTRY_HAS_BLOCKS
            | _ENTRY_BLOCK_SIZE_16K
            | (header.index << _ENTRY_SEGMENT_SHIFT)
        )
        entries.append(
            _SelfEntry(
                data_index,
                data_flags,
                cursor,
                header.file_size,
                header.file_size,
            )
        )
        entry_data.append(segment_data)
        cursor = _align_up(cursor + header.file_size, 16)

    declared_file_size = cursor
    trailer_size = version_header.file_size if version_header is not None else 0
    output = bytearray(declared_file_size + trailer_size)
    _SELF_HEADER.pack_into(
        output,
        0,
        _SELF_MAGIC,
        _SELF_VERSION,
        _SELF_MODE,
        _SELF_ENDIAN_LITTLE,
        _SELF_ATTRIBUTES,
        _SELF_KEY_TYPE,
        self_header_size,
        meta_size,
        declared_file_size,
        entry_count,
        _SELF_FLAGS,
    )

    for entry in entries:
        _SELF_ENTRY.pack_into(
            output,
            _SELF_HEADER.size + entry.index * _SELF_ENTRY.size,
            entry.flags,
            entry.file_offset,
            entry.file_size,
            entry.memory_size,
        )

    embedded_headers = normalized_elf[:header_end]
    output[
        embedded_elf_offset : embedded_elf_offset + len(embedded_headers)
    ] = embedded_headers
    _SELF_EXTENDED_INFO.pack_into(
        output,
        identity_offset,
        identity.paid,
        identity.ptype,
        identity.app_version,
        identity.fw_version,
        hashlib.sha256(elf_bytes).digest(),
    )

    control_offset = identity_offset + _SELF_EXTENDED_INFO.size
    struct.pack_into("<H", output, control_offset, 3)
    meta_footer_offset = (
        self_header_size + entry_count * _SELF_META_BLOCK_SIZE
    )
    struct.pack_into("<I", output, meta_footer_offset + 0x30, 0x10000)

    for entry, data in zip(entries, entry_data, strict=True):
        output[entry.file_offset : entry.file_offset + len(data)] = data

    if version_header is not None:
        version_data = normalized_elf[
            version_header.offset : version_header.offset + version_header.file_size
        ]
        output[declared_file_size:] = version_data

    return bytes(output)


def _copy_source(source: Buffer) -> bytes:
    if not isinstance(source, (bytes, bytearray, memoryview)):
        raise TypeError("source must be bytes, bytearray, or memoryview")
    try:
        return bytes(source)
    except (TypeError, ValueError) as exc:
        raise TypeError("source must be a contiguous byte buffer") from exc


def _parse_self(raw: bytes) -> _ParsedSelf:
    if len(raw) < _SELF_HEADER.size:
        raise SelfFormatError("SELF header is truncated")
    (
        magic,
        version,
        mode,
        endian,
        attributes,
        key_type,
        header_size,
        meta_size,
        declared_file_size,
        entry_count,
        self_flags,
    ) = _SELF_HEADER.unpack_from(raw)
    if magic != _SELF_MAGIC:
        raise SelfFormatError("invalid SELF magic")
    if (version, mode, endian, attributes) != (
        _SELF_VERSION,
        _SELF_MODE,
        _SELF_ENDIAN_LITTLE,
        _SELF_ATTRIBUTES,
    ):
        raise SelfFormatError("unsupported SELF header mode or attributes")
    if key_type != _SELF_KEY_TYPE:
        raise SelfFormatError(f"unsupported SELF key type 0x{key_type:x}")
    if self_flags != _SELF_FLAGS:
        raise SelfFormatError(f"unsupported SELF flags 0x{self_flags:x}")
    if not entry_count:
        raise SelfFormatError("SELF has no entries")

    embedded_elf_offset = _checked_add(
        _SELF_HEADER.size,
        entry_count * _SELF_ENTRY.size,
        "SELF entry table",
    )
    if embedded_elf_offset > len(raw):
        raise SelfFormatError("SELF entry table is truncated")
    if header_size < embedded_elf_offset or header_size > len(raw):
        raise SelfFormatError("SELF header size is invalid")
    if declared_file_size < header_size + meta_size:
        raise SelfFormatError("SELF declared file size is invalid")
    if declared_file_size > len(raw):
        raise SelfFormatError("SELF declared file size exceeds the source")

    entries: list[_SelfEntry] = []
    for index in range(entry_count):
        offset = _SELF_HEADER.size + index * _SELF_ENTRY.size
        flags, file_offset, file_size, memory_size = _SELF_ENTRY.unpack_from(raw, offset)
        if flags & _ENTRY_ENCRYPTED:
            raise SelfFormatError(
                f"SELF entry {index} is encrypted; encrypted entries are unsupported"
            )
        if flags & _ENTRY_COMPRESSED:
            raise SelfFormatError(
                f"SELF entry {index} is compressed; compressed entries are unsupported"
            )
        end = _checked_add(file_offset, file_size, f"SELF entry {index}")
        if end > declared_file_size:
            raise SelfFormatError(f"SELF entry {index} extends outside the source")
        entries.append(_SelfEntry(index, flags, file_offset, file_size, memory_size))

    elf, program_headers = _parse_elf(raw, embedded_elf_offset)
    header_end = max(elf.ehsize, elf.phoff + elf.phentsize * elf.phnum)
    identity_offset = _align_up(embedded_elf_offset + header_end, 16)
    if identity_offset + _SELF_EXTENDED_INFO.size > header_size:
        raise SelfFormatError("SELF extended identity block is outside the header")
    paid, ptype, app_version, fw_version, _digest = _SELF_EXTENDED_INFO.unpack_from(
        raw, identity_offset
    )
    identity = SelfIdentity(paid, ptype, app_version, fw_version)

    for entry in entries:
        if not entry.has_digests:
            continue
        target = entry.segment_index
        if target >= len(entries):
            raise SelfFormatError(
                f"SELF metadata entry {entry.index} maps to missing entry {target}"
            )
        if entries[target].has_digests:
            raise SelfFormatError(
                f"SELF metadata entry {entry.index} does not map to a data entry"
            )

    return _ParsedSelf(
        raw,
        declared_file_size,
        header_size,
        embedded_elf_offset,
        elf,
        program_headers,
        tuple(entries),
        identity,
    )


def _parse_elf(
    raw: bytes | bytearray, base_offset: int
) -> tuple[_ElfHeader, tuple[_ProgramHeader, ...]]:
    if base_offset < 0 or base_offset + _ELF_HEADER.size > len(raw):
        raise SelfFormatError("ELF header is truncated")
    (
        ident,
        elf_type,
        machine,
        version,
        _entry,
        phoff,
        shoff,
        _flags,
        ehsize,
        phentsize,
        phnum,
        shentsize,
        shnum,
        shstrndx,
    ) = _ELF_HEADER.unpack_from(raw, base_offset)
    if ident[:4] != _ELF_MAGIC:
        raise SelfFormatError("invalid ELF magic")
    if ident[4] != _ELF_CLASS_64 or ident[5] != _ELF_DATA_LITTLE:
        raise SelfFormatError("only ELF64 little-endian input is supported")
    if ident[6] != _ELF_VERSION_CURRENT or version != _ELF_VERSION_CURRENT:
        raise SelfFormatError("unsupported ELF version")
    if machine != _ELF_MACHINE_X86_64:
        raise SelfFormatError("only x86-64 ELF input is supported")
    if elf_type not in _ELF_TYPES:
        raise SelfFormatError(f"unsupported ELF type 0x{elf_type:x}")
    if ehsize != _ELF_HEADER.size:
        raise SelfFormatError(f"unsupported ELF header size {ehsize}")
    if phentsize != _PROGRAM_HEADER.size:
        raise SelfFormatError(f"unsupported ELF program header size {phentsize}")
    if not phnum:
        raise SelfFormatError("ELF has no program headers")
    program_table_size = phnum * phentsize
    program_table_end = _checked_add(phoff, program_table_size, "ELF program table")
    if base_offset + program_table_end > len(raw):
        raise SelfFormatError("ELF program table is truncated")

    headers: list[_ProgramHeader] = []
    for index in range(phnum):
        offset = base_offset + phoff + index * phentsize
        fields = _PROGRAM_HEADER.unpack_from(raw, offset)
        header = _ProgramHeader(index, *fields)
        _checked_add(header.offset, header.file_size, f"program segment {index}")
        headers.append(header)
    return (
        _ElfHeader(
            phoff,
            shoff,
            ehsize,
            phentsize,
            phnum,
            shentsize,
            shnum,
            shstrndx,
        ),
        tuple(headers),
    )


def _validate_program_segment_coverage(
    program_headers: tuple[_ProgramHeader, ...],
    intervals: list[tuple[int, int]],
) -> None:
    merged = _merge_intervals(intervals)
    for header in program_headers:
        if not header.file_size:
            continue
        start = header.offset
        end = _checked_add(start, header.file_size, f"program segment {header.index}")
        covered = any(
            interval_start <= start and end <= interval_end
            for interval_start, interval_end in merged
        )
        if not covered:
            raise SelfFormatError(
                f"program segment {header.index} has no recoverable plain data"
            )


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if end < start:
            raise SelfFormatError("invalid byte interval")
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _strip_section_table(elf: bytearray) -> None:
    if len(elf) < _ELF_HEADER.size:
        raise SelfFormatError("ELF header is truncated")
    struct.pack_into("<Q", elf, 0x28, 0)
    struct.pack_into("<H", elf, 0x3C, 0)
    struct.pack_into("<H", elf, 0x3E, 0)


def _require_fake_identity(identity: SelfIdentity) -> None:
    if identity.ptype != _FAKE_PROGRAM_TYPE:
        raise SelfFormatError(
            f"unsupported SELF program type {identity.ptype}; expected fake type 1"
        )


def _bounded_slice(
    data: bytes | bytearray,
    offset: int,
    size: int,
    description: str,
) -> bytes:
    if offset < 0 or size < 0:
        raise SelfFormatError(f"{description} has a negative range")
    end = _checked_add(offset, size, description)
    if end > len(data):
        raise SelfFormatError(f"{description} extends outside the source")
    return bytes(data[offset:end])


def _checked_add(left: int, right: int, description: str) -> int:
    if left < 0 or right < 0 or left > _U64_MAX or right > _U64_MAX:
        raise SelfFormatError(f"{description} contains an invalid unsigned value")
    result = left + right
    if result > _U64_MAX:
        raise SelfFormatError(f"{description} overflows an unsigned 64-bit value")
    return result


def _align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)
