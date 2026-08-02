from __future__ import annotations

import json
from pathlib import Path

import pytest

from ps4ffpsc import inventory as inventory_module
from ps4ffpsc.inventory import (
    PATCH_ROLE_ADDITIONAL_LAYER,
    PATCH_ROLE_ORDINARY,
    classify_patch_filename,
    find_extractor,
    ordered_patches,
    scan_packages,
)


def _record(path: Path, sha: str, kind: str, title_id: str = "CUSA12345") -> dict:
    return {
        "path": str(path),
        "sha256": sha,
        "supported": True,
        "title_id": title_id,
        "title": f"Игра {title_id}",
        "category": {"base": "gd", "patch": "gp", "dlc": "ac"}[kind],
        "content_id": f"EP9000-{title_id}_00-ABCDEFGHIJKLMNOP",
        "app_version": "01.00" if kind == "base" else "01.10",
        "version": "01.00",
        "system_version": "0x02508000",
        "pkg_flags": ["CUMULATIVE_PATCH"] if kind == "patch" else [],
        "kind": kind,
        "entitlement_label": "ABCDEFGHIJKLMNOP",
        "pkg_content_type": 0x1B if kind == "dlc" else 0,
        "dlc_package_type": "PSAC" if kind == "dlc" else None,
        "size": 1024,
        "package_digest": sha,
        "localized_titles": {},
    }


@pytest.mark.parametrize(
    ("pkg_content_type", "dlc_package_type"),
    [(0x1B, "PSAC"), (0x1C, "PSAL")],
)
def test_dlc_package_type_metadata_is_validated(
    tmp_path: Path,
    pkg_content_type: int,
    dlc_package_type: str,
) -> None:
    record = {
        **_record(tmp_path / "dlc.pkg", "a" * 64, "dlc"),
        "pkg_content_type": pkg_content_type,
        "dlc_package_type": dlc_package_type,
    }

    assert "invalid_dlc_package_type" not in inventory_module._validate_record(
        record
    )


@pytest.mark.parametrize(
    ("pkg_content_type", "dlc_package_type"),
    [
        (0x1B, "PSAL"),
        (0x1C, "PSAC"),
        (0x1D, None),
        (None, "PSAC"),
        (0x1B, ["PSAC"]),
    ],
)
def test_invalid_or_mismatched_dlc_package_type_is_reported(
    tmp_path: Path,
    pkg_content_type: int | None,
    dlc_package_type: object,
) -> None:
    record = {
        **_record(tmp_path / "dlc.pkg", "a" * 64, "dlc"),
        "pkg_content_type": pkg_content_type,
        "dlc_package_type": dlc_package_type,
    }

    assert "invalid_dlc_package_type" in inventory_module._validate_record(record)


def test_dump_dlc_without_pkg_header_metadata_remains_compatible(
    tmp_path: Path,
) -> None:
    record = _record(tmp_path / "dump", "a" * 64, "dlc")
    record.pop("pkg_content_type")
    record.pop("dlc_package_type")

    assert "invalid_dlc_package_type" not in inventory_module._validate_record(
        record
    )


def test_fast_duplicate_key_distinguishes_psac_from_psal(tmp_path: Path) -> None:
    psac = _record(tmp_path / "ac.pkg", "a" * 64, "dlc")
    psal = {
        **psac,
        "path": str(tmp_path / "al.pkg"),
        "pkg_content_type": 0x1C,
        "dlc_package_type": "PSAL",
    }

    assert inventory_module._fast_duplicate_key(
        psac
    ) != inventory_module._fast_duplicate_key(psal)


def test_wrong_region_dlc_warns_without_blocking_base_game(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    base = pkg / "base.pkg"
    dlc = pkg / "wrong-region-dlc.pkg"
    base.write_bytes(b"base")
    dlc.write_bytes(b"dlc")
    records = {
        base: _record(base, "a" * 64, "base"),
        dlc: {
            **_record(dlc, "b" * 64, "dlc"),
            "content_id": "UP9000-CUSA12345_00-ABCDEFGHIJKLMNOP",
        },
    }
    monkeypatch.setattr(
        inventory_module,
        "inspect_package",
        lambda _extractor, path, compute_sha256=False: dict(records[path]),
    )

    result = scan_packages(tmp_path, pkg, tmp_path / "unpacked", tmp_path / "helper")

    game = result["games"]["CUSA12345"]
    assert game["buildable"]
    assert game["conflicts"] == []
    assert game["warnings"] == ["incompatible_dlc_package"]
    assert game["dlc"][0]["validation_errors"] == [
        "region_or_content_mismatch"
    ]


def test_find_extractor_accepts_bundled_windows_executable(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    extractor = resources / "bin" / "ps4_pkg_extract.exe"
    extractor.parent.mkdir(parents=True)
    extractor.write_bytes(b"MZ")

    assert find_extractor(tmp_path, resources) == extractor


def test_unicode_pkg_path_and_title_are_preserved_while_windows_unsafe_title_chars_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "Игры ™"
    pkg.mkdir()
    source = pkg / "Sekiro™ Shadows Die Twice.pkg"
    source.write_bytes(b"pkg")
    record = {
        **_record(source, "a" * 64, "base", "CUSA13801"),
        "title": "Sekiro™: Shadows Die Twice",
    }
    monkeypatch.setattr(
        inventory_module,
        "inspect_package",
        lambda _extractor, path, compute_sha256=False: dict(record),
    )

    result = scan_packages(
        tmp_path,
        pkg,
        tmp_path / "unpacked",
        tmp_path / "helper",
    )

    game = result["games"]["CUSA13801"]
    assert game["base"][0]["path"] == str(source.resolve())
    assert game["directory_name"] == (
        "CUSA13801 - Sekiro™_ Shadows Die Twice"
    )
    assert game["buildable"] is True


def test_fast_metadata_duplicate_is_unchecked_candidate_without_full_hashing(
    monkeypatch, tmp_path: Path
) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    files = [pkg / "a.pkg", pkg / "b.PKG"]
    for path in files:
        path.write_bytes(b"x")
    records = {str(path): _record(path, "a" * 64, "base") for path in files}
    monkeypatch.setattr(
        inventory_module,
        "inspect_package",
        lambda _extractor, path, compute_sha256=False: dict(records[str(path)]),
    )
    result = scan_packages(tmp_path, pkg, tmp_path / "unpacked", tmp_path / "helper")
    game = result["games"]["CUSA12345"]
    assert game["buildable"]
    assert game["conflicts"] == []
    assert "duplicate_of" not in game["base"][0]
    assert game["base"][1]["duplicate_of"] == str(files[0].resolve())
    assert (
        game["base"][1]["duplicate_match"]
        == "package_digest_metadata_and_size"
    )
    assert all("sha256" not in item for item in game["base"])
    assert all(item["source_id"].startswith("stat-") for item in game["base"])


def test_conflicting_bases_and_orphan_patch(monkeypatch, tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    inputs = {
        pkg / "a.pkg": _record(pkg / "a.pkg", "a" * 64, "base"),
        pkg / "b.pkg": _record(pkg / "b.pkg", "b" * 64, "base"),
        pkg / "orphan.pkg": _record(pkg / "orphan.pkg", "c" * 64, "patch", "CUSA54321"),
    }
    for path in inputs:
        path.write_bytes(b"x")
    monkeypatch.setattr(
        inventory_module,
        "inspect_package",
        lambda _extractor, path, compute_sha256=False: dict(inputs[path]),
    )
    result = scan_packages(tmp_path, pkg, tmp_path / "unpacked", tmp_path / "helper")
    assert "conflicting_base_packages" in result["games"]["CUSA12345"]["conflicts"]
    assert "orphan_package" in result["games"]["CUSA54321"]["warnings"]


def test_equal_metadata_and_size_with_different_package_digests_are_not_duplicates(
    monkeypatch, tmp_path: Path
) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    files = [pkg / "part1.pkg", pkg / "part2.pkg"]
    records = {
        str(files[0]): _record(files[0], "a" * 64, "base"),
        str(files[1]): _record(files[1], "b" * 64, "base"),
    }
    for path in files:
        path.write_bytes(b"x")
    monkeypatch.setattr(
        inventory_module,
        "inspect_package",
        lambda _extractor, path, compute_sha256=False: dict(records[str(path)]),
    )

    result = scan_packages(
        tmp_path,
        pkg,
        tmp_path / "unpacked",
        tmp_path / "helper",
    )

    game = result["games"]["CUSA12345"]
    assert not game["buildable"]
    assert "conflicting_base_packages" in game["conflicts"]
    assert all("duplicate_of" not in package for package in game["base"])


def test_explicit_pkg_files_override_recursive_directory(monkeypatch, tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    selected_dir = tmp_path / "selected"
    pkg.mkdir()
    selected_dir.mkdir()
    ignored = pkg / "ignored.pkg"
    selected = selected_dir / "selected.PKG"
    ignored.write_bytes(b"ignored")
    selected.write_bytes(b"selected")
    visited: list[Path] = []
    hash_modes: list[bool] = []

    def inspect(_extractor: Path, path: Path, compute_sha256: bool = False) -> dict:
        visited.append(path)
        hash_modes.append(compute_sha256)
        return _record(path, "d" * 64, "base")

    monkeypatch.setattr(inventory_module, "inspect_package", inspect)
    result = scan_packages(
        tmp_path,
        pkg,
        tmp_path / "unpacked",
        tmp_path / "helper",
        (selected,),
    )
    assert visited == [selected.resolve()]
    assert hash_modes == [False]
    assert result["source_mode"] == "selected_files"
    assert result["selected_pkg_files"] == [str(selected.resolve())]


@pytest.mark.parametrize(
    ("filename", "reason"),
    [
        ("Game.Backport.pkg", "filename_marker:backport"),
        ("Game.Back-Port.pkg", "filename_marker:back-port"),
        ("Game-Fix5.05.pkg", "filename_marker:fix5.05"),
    ],
)
def test_explicit_additional_layer_filename_markers(
    filename: str,
    reason: str,
) -> None:
    role, actual_reason = classify_patch_filename(Path(filename))

    assert role == PATCH_ROLE_ADDITIONAL_LAYER
    assert actual_reason == reason


def test_same_version_explicit_layer_is_buildable_and_has_fixed_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    base = pkg / "Overcooked.2.PS4-DUPLEX.pkg"
    update = pkg / "Overcooked.2.Update.v1.10.PS4-DUPLEX.pkg"
    fix = pkg / "UP4064-CUSA10940_00-OVERCOOKED200000-A0110-V0100(Fix5.05).pkg"
    for path in (base, update, fix):
        path.write_bytes(b"x")
    records = {
        base: _record(base, "a" * 64, "base", "CUSA10940"),
        update: _record(update, "b" * 64, "patch", "CUSA10940"),
        fix: _record(fix, "c" * 64, "patch", "CUSA10940"),
    }
    monkeypatch.setattr(
        inventory_module,
        "inspect_package",
        lambda _extractor, path, compute_sha256=False: dict(records[path]),
    )

    result = scan_packages(tmp_path, pkg, tmp_path / "unpacked", tmp_path / "helper")
    game = result["games"]["CUSA10940"]
    patch_by_name = {Path(item["path"]).name: item for item in game["patches"]}

    assert game["buildable"]
    assert game["conflicts"] == []
    assert patch_by_name[update.name]["patch_role"] == PATCH_ROLE_ORDINARY
    assert patch_by_name[update.name]["patch_role_reason"] == "no_explicit_filename_marker"
    assert patch_by_name[fix.name]["patch_role"] == PATCH_ROLE_ADDITIONAL_LAYER
    assert patch_by_name[fix.name]["patch_role_reason"] == "filename_marker:fix5.05"
    assert [item["source_id"] for item in game["patch_plan"]] == [
        patch_by_name[update.name]["source_id"],
        patch_by_name[fix.name]["source_id"],
    ]
    assert [item["role"] for item in game["patch_plan"]] == [
        PATCH_ROLE_ORDINARY,
        PATCH_ROLE_ADDITIONAL_LAYER,
    ]


def test_same_version_unmarked_variants_conflict_but_selected_subset_builds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    base = pkg / "base.pkg"
    first = pkg / "update-a.pkg"
    second = pkg / "update-b.pkg"
    for path in (base, first, second):
        path.write_bytes(b"x")
    records = {
        base: _record(base, "a" * 64, "base"),
        first: _record(first, "b" * 64, "patch"),
        second: _record(second, "c" * 64, "patch"),
    }
    monkeypatch.setattr(
        inventory_module,
        "inspect_package",
        lambda _extractor, path, compute_sha256=False: dict(records[path]),
    )

    all_files = scan_packages(tmp_path, pkg, tmp_path / "unpacked", tmp_path / "helper")
    blocked = all_files["games"]["CUSA12345"]
    assert not blocked["buildable"]
    assert blocked["conflicts"] == ["conflicting_patch_version:01.10"]

    selected = scan_packages(
        tmp_path,
        pkg,
        tmp_path / "unpacked",
        tmp_path / "helper",
        (base, first),
    )
    ready = selected["games"]["CUSA12345"]
    assert ready["buildable"]
    assert ready["conflicts"] == []


@pytest.mark.parametrize("app_version", ["", "v1.10"])
def test_invalid_or_empty_patch_app_version_blocks_game_without_aborting_scan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    app_version: str,
) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    base = pkg / "base.pkg"
    patch = pkg / "bad-version.pkg"
    for path in (base, patch):
        path.write_bytes(b"x")
    records = {
        base: _record(base, "a" * 64, "base"),
        patch: {
            **_record(patch, "b" * 64, "patch"),
            "app_version": app_version,
        },
    }
    monkeypatch.setattr(
        inventory_module,
        "inspect_package",
        lambda _extractor, path, compute_sha256=False: dict(records[path]),
    )

    result = scan_packages(tmp_path, pkg, tmp_path / "unpacked", tmp_path / "helper")

    game = result["games"]["CUSA12345"]
    assert not game["buildable"]
    assert game["conflicts"] == ["invalid_patch_app_version"]
    assert "invalid_app_version" in game["patches"][0]["validation_errors"]
    assert game["patch_plan"][0]["app_version"] == app_version


def test_patch_order_is_deterministic_when_input_order_is_reversed() -> None:
    ordinary = {
        "kind": "patch",
        "supported": True,
        "app_version": "01.10",
        "path": "/tmp/z-ordinary.pkg",
        "source_id": "stat-ordinary",
        "patch_role": PATCH_ROLE_ORDINARY,
    }
    additional = {
        "kind": "patch",
        "supported": True,
        "app_version": "01.10",
        "path": "/tmp/a-Fix5.05.pkg",
        "source_id": "stat-additional",
        "patch_role": PATCH_ROLE_ADDITIONAL_LAYER,
        "patch_role_reason": "filename_marker:fix5.05",
    }
    lower_version = {
        "kind": "patch",
        "supported": True,
        "app_version": "01.05",
        "path": "/tmp/mid.pkg",
        "source_id": "stat-lower",
        "patch_role": PATCH_ROLE_ORDINARY,
    }

    ordered = ordered_patches(
        {"patches": [additional, ordinary, lower_version]}
    )

    assert [item["source_id"] for item in ordered] == [
        "stat-lower",
        "stat-ordinary",
        "stat-additional",
    ]
