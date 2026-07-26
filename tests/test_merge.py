from __future__ import annotations

from pathlib import Path

from ps4ffpsc.pipeline import (
    Settings,
    _deduplicate_packages_by_sha,
    merge_game,
    package_destination,
)
from ps4ffpsc.sfo import make_sfo, parse_sfo, validate_shadowmount_param_json
from ps4ffpsc.util import atomic_write_json, sha256_file


def _settings(root: Path) -> Settings:
    return Settings(
        root=root,
        pkg_dir=root / "pkg",
        unpacked_dir=root / "unpacked",
        output_dir=root / "output",
        work_dir=root / "work",
        temp_dir=root / "work" / "tmp",
    )


def _pkg(kind: str, sha: str, version: str) -> dict:
    return {
        "kind": kind,
        "sha256": sha,
        "app_version": version,
        "path": f"/mock/{sha}.pkg",
        "pkg_flags": ["DELTA_PATCH"] if kind == "patch" else [],
    }


def test_synthetic_base_patch_overlay_and_param_json(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    base = _pkg("base", "a" * 64, "01.00")
    patch = _pkg("patch", "b" * 64, "01.10")
    game = {
        "title_id": "CUSA12345",
        "title": "Игра с пробелами",
        "directory_name": "CUSA12345 - Игра с пробелами",
        "base": [base],
        "patches": [patch],
        "dlc": [],
        "unknown": [],
        "conflicts": [],
        "warnings": [],
        "buildable": True,
    }
    inventory = {"games": {"CUSA12345": game}}
    root = settings.unpacked_dir / game["directory_name"]
    atomic_write_json(root / "manifest.json", {"synthetic": True})
    base_dir = package_destination(root, base)
    patch_dir = package_destination(root, patch)
    (base_dir / "sce_sys").mkdir(parents=True)
    (patch_dir / "sce_sys").mkdir(parents=True)
    (base_dir / "eboot.bin").write_bytes(b"base executable")
    (base_dir / "data.bin").write_bytes(b"old")
    (base_dir / "sce_sys" / "param.sfo").write_bytes(
        make_sfo({"TITLE_ID": "CUSA12345", "TITLE": "Игра", "APP_VER": "01.00", "CATEGORY": "gd"})
    )
    (patch_dir / "data.bin").write_bytes(b"new")
    (patch_dir / "sce_sys" / "param.sfo").write_bytes(
        make_sfo({"TITLE_ID": "CUSA12345", "TITLE": "Игра", "APP_VER": "01.10", "CATEGORY": "gp"})
    )

    report = merge_game(settings, inventory, "CUSA12345")
    merged = root / "merged" / "app"
    assert (merged / "data.bin").read_bytes() == b"new"
    assert parse_sfo(merged / "sce_sys" / "param.sfo")["APP_VER"] == "01.10"
    validate_shadowmount_param_json(
        (merged / "sce_sys" / "param.json").read_bytes(), "CUSA12345"
    )
    replacement = next(item for item in report["overlay_changes"] if item["path"] == "data.bin")
    assert replacement["previous_sha256"] == sha256_file(base_dir / "data.bin")
    assert replacement["new_sha256"] == sha256_file(patch_dir / "data.bin")
    assert report["delta_patch_warning"]
    assert not report["ps5_runtime_verified"]


def test_patch_can_replace_path_with_case_only_name_change(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    base = _pkg("base", "c" * 64, "01.00")
    patch = _pkg("patch", "d" * 64, "02.04")
    game = {
        "title_id": "CUSA12878",
        "title": "Beat Saber",
        "directory_name": "CUSA12878 - Beat Saber",
        "base": [base],
        "patches": [patch],
        "dlc": [],
        "unknown": [],
        "conflicts": [],
        "warnings": [],
        "buildable": True,
    }
    inventory = {"games": {"CUSA12878": game}}
    root = settings.unpacked_dir / game["directory_name"]
    atomic_write_json(root / "manifest.json", {"synthetic": True})
    base_dir = package_destination(root, base)
    patch_dir = package_destination(root, patch)
    (base_dir / "sce_sys").mkdir(parents=True)
    (patch_dir / "sce_sys").mkdir(parents=True)
    (base_dir / "Media" / "Modules").mkdir(parents=True)
    (patch_dir / "Media" / "Modules").mkdir(parents=True)
    (base_dir / "eboot.bin").write_bytes(b"base executable")
    (base_dir / "Media" / "Modules" / "Il2CppUserAssemblies.prx").write_bytes(b"old")
    (base_dir / "sce_sys" / "param.sfo").write_bytes(
        make_sfo(
            {
                "TITLE_ID": "CUSA12878",
                "TITLE": "Beat Saber",
                "APP_VER": "01.00",
                "CATEGORY": "gd",
            }
        )
    )
    (patch_dir / "Media" / "Modules" / "Il2cppUserAssemblies.prx").write_bytes(b"new")
    (patch_dir / "sce_sys" / "param.sfo").write_bytes(
        make_sfo(
            {
                "TITLE_ID": "CUSA12878",
                "TITLE": "Beat Saber",
                "APP_VER": "02.04",
                "CATEGORY": "gp",
            }
        )
    )

    report = merge_game(settings, inventory, "CUSA12878")

    modules = root / "merged" / "app" / "Media" / "Modules"
    assert {item.name for item in modules.iterdir()} == {"Il2cppUserAssemblies.prx"}
    assert (modules / "Il2cppUserAssemblies.prx").read_bytes() == b"new"
    rename = next(
        item
        for item in report["overlay_changes"]
        if item["path"] == "Media/Modules/Il2cppUserAssemblies.prx"
    )
    assert rename["case_renamed_from"] == "Media/Modules/Il2CppUserAssemblies.prx"


def test_byte_identical_pkg_is_marked_as_duplicate() -> None:
    first = _pkg("dlc", "e" * 64, "01.00")
    first["path"] = "/mock/first.pkg"
    second = _pkg("dlc", "e" * 64, "01.00")
    second["path"] = "/mock/second.pkg"

    selected = _deduplicate_packages_by_sha([first, second])

    assert selected == [first]
    assert second["duplicate_of"] == first["path"]
