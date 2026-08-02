from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

PSF_MAGIC = b"\x00PSF"
PSF_TEXT = 0x0204
PSF_INTEGER = 0x0404
PSF_BINARY = 0x0004

# SCE system-language order used by localized TITLE_00…TITLE_29 fields.
# JSON locale spellings follow the native FW 12.70 appmeta convention where it
# differs from the shorter system-language name (notably Chinese scripts,
# Latin American Spanish, and Arabic).
SFO_TITLE_LOCALES = (
    "ja-JP",
    "en-US",
    "fr-FR",
    "es-ES",
    "de-DE",
    "it-IT",
    "nl-NL",
    "pt-PT",
    "ru-RU",
    "ko-KR",
    "zh-Hant",
    "zh-Hans",
    "fi-FI",
    "sv-SE",
    "da-DK",
    "no-NO",
    "pl-PL",
    "pt-BR",
    "en-GB",
    "tr-TR",
    "es-419",
    "ar-AE",
    "fr-CA",
    "cs-CZ",
    "hu-HU",
    "el-GR",
    "ro-RO",
    "th-TH",
    "vi-VN",
    "id-ID",
)


class SfoError(ValueError):
    pass


def parse_sfo_bytes(data: bytes) -> dict[str, Any]:
    if len(data) < 20:
        raise SfoError("param.sfo is truncated")
    magic, version, key_offset, data_offset, count = struct.unpack_from("<4sIIII", data)
    if magic != PSF_MAGIC:
        raise SfoError("invalid param.sfo magic")
    if version not in {0x00000100, 0x00000101}:
        raise SfoError(f"unsupported param.sfo version: 0x{version:08x}")
    index_end = 20 + count * 16
    if count > 4096 or not (index_end <= key_offset <= data_offset <= len(data)):
        raise SfoError("param.sfo table bounds are invalid")

    result: dict[str, Any] = {}
    for index in range(count):
        key_rel, fmt_be, length, max_length, value_rel = struct.unpack_from(
            "<HHIII", data, 20 + index * 16
        )
        # The two format bytes are stored as 04 02 (text), 04 04 (integer),
        # or 04 00 (binary). Reading the raw field as little-endian yields the
        # public shadPS4 constants 0x0204, 0x0404 and 0x0004 directly.
        fmt = fmt_be
        key_start = key_offset + key_rel
        value_start = data_offset + value_rel
        value_end = value_start + length
        if key_start >= data_offset or value_start > len(data) or value_end > len(data):
            raise SfoError("param.sfo entry bounds are invalid")
        key_end = data.find(b"\0", key_start, data_offset)
        if key_end < 0:
            raise SfoError("param.sfo key is not terminated")
        try:
            key = data[key_start:key_end].decode("utf-8")
        except UnicodeDecodeError as error:
            raise SfoError("param.sfo key is not UTF-8") from error
        raw = data[value_start:value_end]
        if fmt == PSF_TEXT:
            if not raw or raw[-1] != 0:
                raise SfoError(f"param.sfo text value {key!r} is not terminated")
            try:
                result[key] = raw[:-1].decode("utf-8")
            except UnicodeDecodeError as error:
                raise SfoError(f"param.sfo value {key!r} is not UTF-8") from error
        elif fmt == PSF_INTEGER:
            if length != 4:
                raise SfoError(f"param.sfo integer {key!r} has invalid length")
            result[key] = struct.unpack("<i", raw)[0]
        elif fmt == PSF_BINARY:
            result[key] = raw
        else:
            raise SfoError(f"unknown param.sfo format 0x{fmt:04x}")
        if max_length < length:
            raise SfoError(f"param.sfo entry {key!r} exceeds max length")
    return result


def parse_sfo(path: Path) -> dict[str, Any]:
    return parse_sfo_bytes(path.read_bytes())


def make_sfo(values: dict[str, str | int | bytes]) -> bytes:
    """Create a deterministic minimal PSF fixture for host-side tests."""
    keys = bytearray()
    value_table = bytearray()
    entries: list[tuple[int, int, int, int, int]] = []
    for key in sorted(values):
        key_rel = len(keys)
        keys.extend(key.encode("utf-8") + b"\0")
        while len(value_table) % 4:
            value_table.append(0)
        value_rel = len(value_table)
        value = values[key]
        if isinstance(value, str):
            encoded = value.encode("utf-8") + b"\0"
            fmt = PSF_TEXT
        elif isinstance(value, int):
            encoded = struct.pack("<i", value)
            fmt = PSF_INTEGER
        else:
            encoded = bytes(value)
            fmt = PSF_BINARY
        value_table.extend(encoded)
        entries.append((key_rel, fmt, len(encoded), len(encoded), value_rel))

    key_offset = 20 + len(entries) * 16
    data_offset = key_offset + len(keys)
    header = struct.pack("<4sIIII", PSF_MAGIC, 0x00000101, key_offset, data_offset, len(entries))
    index = bytearray()
    for key_rel, fmt, length, max_length, value_rel in entries:
        index.extend(struct.pack("<HHIII", key_rel, fmt, length, max_length, value_rel))
    return bytes(header + index + keys + value_table)


def choose_title(values: dict[str, Any], preferred_index: int | None = None) -> str:
    if isinstance(values.get("TITLE"), str) and values["TITLE"].strip():
        return values["TITLE"].strip()
    if preferred_index is not None:
        preferred = values.get(f"TITLE_{preferred_index:02d}")
        if isinstance(preferred, str) and preferred.strip():
            return preferred.strip()
    english_title = values.get("TITLE_01")
    if isinstance(english_title, str) and english_title.strip():
        return english_title.strip()
    for index in range(30):
        if index == 1:
            continue
        title = values.get(f"TITLE_{index:02d}")
        if isinstance(title, str) and title.strip():
            return title.strip()
    for key in ("CONTENT_ID", "TITLE_ID"):
        value = values.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Unknown Game"


def build_param_json(
    title_id: str,
    title_name: str,
    existing_data: bytes | None = None,
    sfo_values: dict[str, Any] | None = None,
) -> bytes:
    payload: dict[str, Any] = {}
    if existing_data is not None and not existing_data.startswith(b"\xef\xbb\xbf"):
        try:
            existing_payload = json.loads(existing_data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            existing_payload = None
        if isinstance(existing_payload, dict):
            payload = existing_payload

    localized = payload.get("localizedParameters")
    if not isinstance(localized, dict):
        localized = {}
    if sfo_values is not None:
        for index, locale in enumerate(SFO_TITLE_LOCALES):
            value = sfo_values.get(f"TITLE_{index:02d}")
            if not isinstance(value, str) or not value.strip():
                continue
            language = localized.get(locale)
            if not isinstance(language, dict):
                language = {}
            language["titleName"] = value.strip()
            localized[locale] = language

    # ShadowMountPlus currently requires an en-US title fallback.  Prefer the
    # exact TITLE_01 text when available, otherwise expose the selected title
    # without discarding any other localized SFO entries.
    english = localized.get("en-US")
    if not isinstance(english, dict):
        english = {}
    english_title = (
        sfo_values.get("TITLE_01") if sfo_values is not None else None
    )
    english["titleName"] = (
        english_title.strip()
        if isinstance(english_title, str) and english_title.strip()
        else title_name
    )
    localized["en-US"] = english
    existing_default = localized.get("defaultLanguage")
    if not (
        isinstance(existing_default, str)
        and isinstance(localized.get(existing_default), dict)
    ):
        localized["defaultLanguage"] = "en-US"
    payload["localizedParameters"] = localized
    payload["titleId"] = title_id
    payload["titleName"] = title_name
    # Native PS4 appmeta JSON normally remains minimal and the game reads
    # USER_DEFINED_PARAM_* from param.sfo. Some image-launched games, however,
    # have been observed to lose their language/region selector unless the
    # non-zero value is also exposed through the camelCase JSON projection.
    # Mirror only explicit non-zero integers; param.sfo remains authoritative.
    if sfo_values is not None:
        for index in range(1, 5):
            value = sfo_values.get(f"USER_DEFINED_PARAM_{index}")
            if isinstance(value, int) and value != 0:
                payload[f"userDefinedParam{index}"] = value
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def validate_shadowmount_param_json(data: bytes, expected_title_id: str) -> dict[str, Any]:
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("param.json must not contain a UTF-8 BOM")
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid UTF-8 JSON in param.json") from error
    title_id = payload.get("titleId", payload.get("title_id"))
    if title_id != expected_title_id:
        raise ValueError(f"param.json titleId mismatch: {title_id!r}")
    if len(title_id) != 9:
        raise ValueError("param.json titleId must contain exactly 9 characters")
    title_name = payload.get("titleName")
    localized = payload.get("localizedParameters")
    if not title_name and isinstance(localized, dict):
        language = localized.get("en-US")
        if isinstance(language, dict):
            title_name = language.get("titleName")
    if not isinstance(title_name, str) or not title_name:
        raise ValueError("param.json does not expose titleName to ShadowMountPlus")
    return payload
