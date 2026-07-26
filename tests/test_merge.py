from __future__ import annotations

from pathlib import Path

from ps4ffpsc.pipeline import Settings, merge_game, package_destination
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

