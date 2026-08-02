from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ps4ffpsc.dlc_license import (
    entitlement_key_fingerprint,
    parse_dlc_license,
)


DEBUG_KEY = bytes.fromhex("96c2268d69261c8b1e3b6bff2fe04e12")


def _license_bytes(
    *,
    content_id: str = "EP0000-CUSA12345_00-ABCDEFGHIJKLMNOP",
    content_type: int = 0x1B,
    key: bytes = bytes(range(16)),
    encrypted: bool = True,
) -> bytes:
    result = bytearray(0x400)
    result[:4] = b"RIF\0"
    result[4:6] = (1).to_bytes(2, "big")
    content_id_raw = content_id.encode("ascii").ljust(48, b"\0")
    result[0x20:0x50] = content_id_raw
    result[0x54:0x56] = content_type.to_bytes(2, "big")
    iv = bytes(range(16, 32))
    result[0x260:0x270] = iv
    secret = bytearray(0x90)
    secret[:16] = hashlib.sha256(content_id_raw).digest()[16:32]
    secret[0x70:0x80] = key
    if encrypted:
        encryptor = Cipher(
            algorithms.AES(DEBUG_KEY), modes.CBC(iv)
        ).encryptor()
        stored = encryptor.update(bytes(secret)) + encryptor.finalize()
    else:
        stored = bytes(secret)
    result[0x270:0x300] = stored
    return bytes(result)


@pytest.mark.parametrize(
    ("content_type", "package_type"),
    [(0x1B, "PSAC"), (0x1C, "PSAL")],
)
@pytest.mark.parametrize("encrypted", [False, True])
def test_parse_dlc_license_validates_and_returns_key(
    tmp_path: Path,
    content_type: int,
    package_type: str,
    encrypted: bool,
) -> None:
    key = bytes(reversed(range(16)))
    path = tmp_path / "license.dat"
    path.write_bytes(
        _license_bytes(
            content_type=content_type,
            key=key,
            encrypted=encrypted,
        )
    )

    result = parse_dlc_license(
        path,
        expected_package_type=package_type,
        expected_content_id="EP0000-CUSA12345_00-ABCDEFGHIJKLMNOP",
    )

    assert result.package_type == package_type
    assert result.entitlement_key == key
    assert result.secret_was_encrypted is encrypted
    assert entitlement_key_fingerprint(key) == hashlib.sha256(key).hexdigest()


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda data: data.__setitem__(slice(0, 4), b"BAD!"), "RIF header"),
        (lambda data: data.__setitem__(slice(0x54, 0x56), b"\x00\x01"), "not PSAC or PSAL"),
        (lambda data: data.__setitem__(0x270, data[0x270] ^ 1), "validation failed"),
    ],
)
def test_parse_dlc_license_fails_closed(
    tmp_path: Path,
    mutation,
    match: str,
) -> None:
    data = bytearray(_license_bytes())
    mutation(data)
    path = tmp_path / "license.dat"
    path.write_bytes(data)

    with pytest.raises(ValueError, match=match):
        parse_dlc_license(path)


def test_parse_dlc_license_rejects_identity_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "license.dat"
    path.write_bytes(_license_bytes())

    with pytest.raises(ValueError, match="package type"):
        parse_dlc_license(path, expected_package_type="PSAL")
    with pytest.raises(ValueError, match="content ID"):
        parse_dlc_license(path, expected_content_id="different")


def test_key_never_appears_in_validation_error(tmp_path: Path) -> None:
    key = bytes.fromhex("00112233445566778899aabbccddeeff")
    data = bytearray(_license_bytes(key=key))
    data[0x270] ^= 1
    path = tmp_path / "license.dat"
    path.write_bytes(data)

    with pytest.raises(ValueError) as raised:
        parse_dlc_license(path)
    assert key.hex() not in str(raised.value)


def test_key_is_hidden_from_license_repr(tmp_path: Path) -> None:
    key = bytes.fromhex("00112233445566778899aabbccddeeff")
    path = tmp_path / "license.dat"
    path.write_bytes(_license_bytes(key=key))

    parsed = parse_dlc_license(path)

    assert key.hex() not in repr(parsed)
    assert repr(key) not in repr(parsed)


def test_oversized_license_is_rejected_with_bounded_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "license.dat"
    path.write_bytes(_license_bytes() + b"extra bytes")
    real_open = Path.open
    requested_sizes: list[int] = []

    class TrackedFile:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def read(self, size: int = -1) -> bytes:
            requested_sizes.append(size)
            return self.handle.read(size)

    def tracked_open(self: Path, *args, **kwargs):
        return TrackedFile(real_open(self, *args, **kwargs))

    monkeypatch.setattr(Path, "open", tracked_open)

    with pytest.raises(ValueError, match="exactly 1024 bytes"):
        parse_dlc_license(path)

    assert requested_sizes == [1025]
