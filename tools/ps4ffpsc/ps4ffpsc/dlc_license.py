from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


_LICENSE_SIZE = 0x400
_CONTENT_ID_OFFSET = 0x20
_CONTENT_ID_SIZE = 48
_CONTENT_TYPE_OFFSET = 0x54
_SECRET_IV_OFFSET = 0x260
_SECRET_OFFSET = 0x270
_SECRET_SIZE = 0x90
_ENTITLEMENT_KEY_OFFSET = 0x70
_ENTITLEMENT_KEY_SIZE = 0x10
_RIF_DEBUG_KEY = bytes.fromhex("96c2268d69261c8b1e3b6bff2fe04e12")
_CONTENT_TYPES = {0x1B: "PSAC", 0x1C: "PSAL"}


@dataclass(frozen=True)
class DlcLicense:
    content_id: str
    package_type: str
    entitlement_key: bytes = field(repr=False)
    secret_was_encrypted: bool


def _decode_content_id(raw: bytes) -> str:
    text = raw.split(b"\0", 1)[0]
    try:
        value = text.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("license.dat content ID is not ASCII") from error
    if not value or len(value) > 48:
        raise ValueError("license.dat has an invalid content ID")
    return value


def _decrypt_secret(secret: bytes, iv: bytes) -> bytes:
    decryptor = Cipher(
        algorithms.AES(_RIF_DEBUG_KEY),
        modes.CBC(iv),
    ).decryptor()
    return decryptor.update(secret) + decryptor.finalize()


def parse_dlc_license(
    path: Path,
    *,
    expected_package_type: str | None = None,
    expected_content_id: str | None = None,
) -> DlcLicense:
    """Read the minimum DLC identity required by the experimental image mode.

    The function accepts only the fixed-size debug RIF form emitted by supported
    PS4 DLC PKGs.  It validates the decrypted secret before returning the
    in-memory entitlement key.  The caller must never persist that key in logs,
    reports or release artifacts.
    """

    # Read at most one byte beyond the only accepted representation.  Dump
    # directories are user-provided, so a malformed multi-gigabyte file must
    # not be loaded into memory merely to reject its length.
    with path.open("rb") as handle:
        data = handle.read(_LICENSE_SIZE + 1)
    if len(data) != _LICENSE_SIZE:
        raise ValueError(
            f"license.dat must be exactly {_LICENSE_SIZE} bytes, got {len(data)}"
        )
    if data[:4] != b"RIF\0":
        raise ValueError("license.dat has an invalid RIF header")

    content_id_raw = data[
        _CONTENT_ID_OFFSET : _CONTENT_ID_OFFSET + _CONTENT_ID_SIZE
    ]
    content_id = _decode_content_id(content_id_raw)
    content_type = int.from_bytes(
        data[_CONTENT_TYPE_OFFSET : _CONTENT_TYPE_OFFSET + 2],
        "big",
    )
    package_type = _CONTENT_TYPES.get(content_type)
    if package_type is None:
        raise ValueError(
            f"license.dat content type 0x{content_type:04x} is not PSAC or PSAL"
        )
    if expected_package_type is not None and package_type != expected_package_type:
        raise ValueError(
            "license.dat package type does not match the PKG header: "
            f"{package_type} != {expected_package_type}"
        )
    if expected_content_id is not None and content_id != expected_content_id:
        raise ValueError(
            "license.dat content ID does not match the PKG header"
        )

    iv = data[_SECRET_IV_OFFSET : _SECRET_IV_OFFSET + 16]
    stored_secret = data[_SECRET_OFFSET : _SECRET_OFFSET + _SECRET_SIZE]
    expected_prefix = hashlib.sha256(content_id_raw).digest()[16:32]
    if stored_secret[:16] == expected_prefix:
        secret = stored_secret
        encrypted = False
    else:
        secret = _decrypt_secret(stored_secret, iv)
        encrypted = True
    if secret[:16] != expected_prefix:
        raise ValueError("license.dat secret validation failed")

    entitlement_key = secret[
        _ENTITLEMENT_KEY_OFFSET : _ENTITLEMENT_KEY_OFFSET
        + _ENTITLEMENT_KEY_SIZE
    ]
    if len(entitlement_key) != _ENTITLEMENT_KEY_SIZE:
        raise ValueError("license.dat entitlement key is truncated")
    return DlcLicense(
        content_id=content_id,
        package_type=package_type,
        entitlement_key=entitlement_key,
        secret_was_encrypted=encrypted,
    )


def entitlement_key_fingerprint(key: bytes) -> str:
    if len(key) != _ENTITLEMENT_KEY_SIZE:
        raise ValueError("entitlement key must be exactly 16 bytes")
    return hashlib.sha256(key).hexdigest()
