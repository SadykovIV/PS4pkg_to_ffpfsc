from __future__ import annotations

import os
from pathlib import Path

import pytest

from ps4ffpsc.util import (
    content_id_parts,
    ensure_within,
    entitlement_label,
    link_or_copy_file_atomic,
    sanitize_component,
    stage_file_atomic,
    tree_manifest,
    validate_title_id,
    version_key,
)


def test_numeric_version_order_is_not_float_order() -> None:
    versions = ["01.100", "01.09", "01.10"]
    assert sorted(versions, key=version_key) == ["01.09", "01.10", "01.100"]


@pytest.mark.parametrize("valid", ["CUSA00000", "CUSA12345", "CUSA99999"])
def test_title_id_valid(valid: str) -> None:
    assert validate_title_id(valid)


@pytest.mark.parametrize("invalid", ["cusa12345", "CUSA1234", "PPSA12345", "CUSA1234X"])
def test_title_id_invalid(invalid: str) -> None:
    assert not validate_title_id(invalid)


def test_content_id_and_entitlement_are_checked_before_indexing() -> None:
    content = "EP9000-CUSA12345_00-ABCDEFGHIJKLMNOP"
    assert content_id_parts(content) == ("EP9000", "CUSA12345_00", "ABCDEFGHIJKLMNOP")
    assert entitlement_label(content) == "ABCDEFGHIJKLMNOP"
    assert entitlement_label("too-short") is None
    assert entitlement_label("EP9000-CUSA12345_00-lowercase_label") is None


def test_sanitize_preserves_unicode_and_removes_only_invalid_characters() -> None:
    assert sanitize_component('  Игра: "Тест"  ', "fallback") == "  Игра_ _Тест_"
    assert sanitize_component("..", "CUSA12345") == "CUSA12345"


def test_path_traversal_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ValueError, match="escapes"):
        ensure_within(root, root / ".." / "outside")


def test_symlink_attack_rejected(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    target = tmp_path / "outside"
    target.write_text("outside")
    (root / "link").symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        tree_manifest(root)


def test_unicode_tree_and_host_metadata(tmp_path: Path) -> None:
    root = tmp_path / "Кириллица и пробелы"
    root.mkdir()
    (root / "файл.txt").write_text("данные", encoding="utf-8")
    (root / ".DS_Store").write_bytes(b"host")
    manifest = tree_manifest(root)
    assert [entry["path"] for entry in manifest] == ["файл.txt"]


def test_atomic_staging_prefers_hardlink_without_mutating_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    destination = tmp_path / "work" / "destination.bin"
    source.write_bytes(b"original")

    linked = link_or_copy_file_atomic(source, destination)

    assert destination.read_bytes() == b"original"
    if linked:
        assert os.path.samefile(source, destination)
    replacement = destination.with_name("replacement.partial")
    replacement.write_bytes(b"replacement")
    os.replace(replacement, destination)
    assert source.read_bytes() == b"original"
    assert destination.read_bytes() == b"replacement"


def test_atomic_staging_falls_back_to_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.bin"
    destination = tmp_path / "work" / "destination.bin"
    source.write_bytes(b"portable")

    def fail_link(*_args: object, **_kwargs: object) -> None:
        raise OSError("hardlinks unavailable")

    monkeypatch.setattr(os, "link", fail_link)
    assert not link_or_copy_file_atomic(source, destination)
    assert destination.read_bytes() == b"portable"


def test_consumable_staging_moves_when_hardlinks_are_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.bin"
    destination = tmp_path / "work" / "destination.bin"
    source.write_bytes(b"move instead of duplicate")

    def fail_link(*_args: object, **_kwargs: object) -> None:
        raise OSError("hardlinks unavailable")

    monkeypatch.setattr(os, "link", fail_link)
    assert stage_file_atomic(source, destination, consume_source=True) == "moved"
    assert not source.exists()
    assert destination.read_bytes() == b"move instead of duplicate"


def test_sparse_file_larger_than_4gib_when_supported(tmp_path: Path) -> None:
    path = tmp_path / "large sparse.bin"
    try:
        with path.open("wb") as stream:
            stream.seek(4 * 1024**3)
            stream.write(b"x")
    except OSError:
        pytest.skip("filesystem does not support sparse files above 4 GiB")
    assert path.stat().st_size == 4 * 1024**3 + 1
