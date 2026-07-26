from __future__ import annotations

from pathlib import Path

import pytest

from ps4ffpsc.gui_model import (
    game_block_reason,
    inventory_summary,
    normalize_pkg_files,
    package_version_text,
    source_cli_arguments,
)


def test_selected_pkg_files_are_deduplicated_and_keep_order(tmp_path: Path) -> None:
    first = tmp_path / "Base.PKG"
    second = tmp_path / "patch.pkg"
    first.write_bytes(b"base")
    second.write_bytes(b"patch")
    result = normalize_pkg_files([first, second, first])
    assert result == (first.resolve(), second.resolve())


def test_selected_file_mode_does_not_add_default_directory(tmp_path: Path) -> None:
    package = tmp_path / "game.pkg"
    package.write_bytes(b"pkg")
    assert source_cli_arguments("files", [package], None) == [
        "--pkg-file",
        str(package.resolve()),
    ]


def test_folder_mode_is_recursive_cli_source(tmp_path: Path) -> None:
    nested = tmp_path / "library"
    nested.mkdir()
    assert source_cli_arguments("folder", [], nested) == [
        "--pkg-dir",
        str(nested.resolve()),
    ]


def test_invalid_selected_file_is_rejected(tmp_path: Path) -> None:
    wrong = tmp_path / "readme.txt"
    wrong.write_text("not a pkg", encoding="utf-8")
    with pytest.raises(ValueError, match=r"\.pkg"):
        normalize_pkg_files([wrong])


def test_inventory_summary_and_dlc_label() -> None:
    inventory = {
        "packages": [{}, {}, {}],
        "unsupported": [{}],
        "games": {
            "CUSA00001": {"buildable": True, "conflicts": []},
            "CUSA00002": {"buildable": False, "conflicts": ["base"]},
        },
    }
    assert inventory_summary(inventory) == {
        "packages": 3,
        "games": 2,
        "buildable": 1,
        "unsupported": 1,
        "conflicts": 1,
    }
    assert package_version_text(
        {"kind": "dlc", "entitlement_label": "EXAMPLE000000001"}
    ) == "EXAMPLE000000001"


def test_orphan_game_explains_missing_base_pkg() -> None:
    reason = game_block_reason(
        {"warnings": ["orphan_package"], "conflicts": [], "patches": [{}], "dlc": [{}]}
    )
    assert "base PKG" in reason
    assert "patch" in reason
