from __future__ import annotations

from pathlib import Path

import pytest
from mkpfs.pbar import Progress

from ps4ffpsc.gui_model import (
    build_error_text,
    estimate_remaining_seconds,
    format_duration,
    game_block_reason,
    inventory_summary,
    normalize_pkg_files,
    package_version_text,
    parse_progress_event,
    scan_inventory_path,
    source_cli_arguments,
    temporary_cli_arguments,
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


def test_all_heavy_workspace_paths_use_selected_temp_directory(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "PS4 FFPFSC"
    assert temporary_cli_arguments(tmp_path) == [
        "--unpacked-dir",
        str(workspace / "unpacked"),
        "--work-dir",
        str(workspace / "work"),
        "--temp-dir",
        str(workspace / "tmp"),
    ]


def test_scan_uses_inventory_path_reported_by_worker(tmp_path: Path) -> None:
    reported = tmp_path / "worker" / "package_inventory.json"

    assert scan_inventory_path({"inventory": str(reported)}, tmp_path) == reported


def test_scan_inventory_fallback_uses_selected_temp_directory(
    tmp_path: Path,
) -> None:
    assert scan_inventory_path(None, tmp_path) == (
        tmp_path / "PS4 FFPFSC" / "unpacked" / "package_inventory.json"
    )


def test_progress_events_parse_scan_stage_and_structured_worker_lines() -> None:
    assert parse_progress_event(
        "2026-07-26 INFO scanning 12 PKG file(s)"
    ) == {"kind": "scan_total", "total": 12}
    assert parse_progress_event(
        r"2026-07-26 INFO inspecting PKG: \\server\games\base.pkg"
    ) == {"kind": "scan_item"}
    assert parse_progress_event(
        "2026-07-26 INFO stage 3/5: creating compressed FFPFSC image"
    ) == {"kind": "build_stage", "stage": 3, "total": 5}
    assert parse_progress_event(
        'PS4FFPSC_PROGRESS {"scope":"mkpfs","phase":"compress","current":25,"total":100}'
    ) == {
        "kind": "worker",
        "scope": "mkpfs",
        "phase": "compress",
        "current": 25,
        "total": 100,
    }


def test_duration_and_eta_are_stable_for_gui_display() -> None:
    assert format_duration(0) == "00:00"
    assert format_duration(65.9) == "01:05"
    assert format_duration(3661) == "01:01:01"
    assert estimate_remaining_seconds(30, 25) == 90
    assert estimate_remaining_seconds(30, 100) == 0
    assert estimate_remaining_seconds(30, 0) is None


def test_mkpfs_emits_machine_readable_progress_for_gui(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PS4FFPSC_GUI_PROGRESS", "1")
    Progress().step("compress", 50, 100, bytes_processed=1024)

    event = parse_progress_event(capsys.readouterr().err.strip())
    assert event is not None
    assert event["kind"] == "worker"
    assert event["scope"] == "mkpfs"
    assert event["phase"] == "compress"
    assert event["current"] == 50
    assert event["total"] == 100


def test_invalid_selected_file_is_rejected(tmp_path: Path) -> None:
    wrong = tmp_path / "readme.txt"
    wrong.write_text("not a pkg", encoding="utf-8")
    with pytest.raises(ValueError, match=r"\.pkg"):
        normalize_pkg_files([wrong])
    with pytest.raises(ValueError, match="selected file"):
        normalize_pkg_files([wrong], "en")


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
    english = game_block_reason(
        {"warnings": ["orphan_package"], "conflicts": []}, "en"
    )
    assert "base PKG is missing" in english


def test_build_error_text_reads_worker_json_error() -> None:
    payload = {
        "CUSA12878": {
            "error": "case-insensitive path collision: 'old' vs 'new'",
        }
    }
    assert build_error_text(payload, "CUSA12878", 1) == payload["CUSA12878"]["error"]


def test_build_error_text_falls_back_to_exit_code() -> None:
    assert build_error_text(None, "CUSA12878", 1) == (
        "код 1; подробности находятся в журнале"
    )
    assert build_error_text(None, "CUSA12878", 1, "en") == (
        "exit code 1; see the log for details"
    )
