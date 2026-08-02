from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pytest

from ps4ffpsc import pipeline
from ps4ffpsc.pipeline import (
    EXTRACTOR_REVISION,
    Settings,
    merge_game,
    package_destination,
)
from ps4ffpsc.sfo import make_sfo, parse_sfo, validate_shadowmount_param_json
from ps4ffpsc.util import atomic_write_json


def _npbind_with_damaged_footer() -> bytes:
    size = 0x80 + 0x180 + 20
    data = bytearray(size)
    struct.pack_into(
        ">IIQQQ",
        data,
        0,
        0xD294A018,
        1,
        size,
        0x180,
        1,
    )
    data[-20:] = hashlib.sha1(data[:-20]).digest()
    data[-4:] = bytes.fromhex("87f1c2cf")
    return bytes(data)


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
        "source_id": "stat-" + sha,
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
    atomic_write_json(
        root / "manifest.json",
        {"synthetic": True, "extractor_revision": EXTRACTOR_REVISION},
    )
    base_dir = package_destination(root, base)
    patch_dir = package_destination(root, patch)
    (base_dir / "sce_sys").mkdir(parents=True)
    (patch_dir / "sce_sys").mkdir(parents=True)
    (base_dir / "eboot.bin").write_bytes(b"base executable")
    (base_dir / "data.bin").write_bytes(b"old")
    base_param_sfo = make_sfo(
        {
            "TITLE_ID": "CUSA12345",
            "TITLE": "Игра",
            "APP_VER": "01.00",
            "CATEGORY": "gd",
        }
    )
    (base_dir / "sce_sys" / "param.sfo").write_bytes(base_param_sfo)
    original_param_json = (
        b'{\n  "gameIntent": {"permittedIntents": '
        b'[{"intentType": "joinSession"}]}\n}\n'
    )
    (base_dir / "sce_sys" / "param.json").write_bytes(original_param_json)
    (patch_dir / "data.bin").write_bytes(b"new")
    patch_param_sfo = make_sfo(
        {
            "TITLE_ID": "CUSA12345",
            "TITLE": "Игра",
            "APP_VER": "01.10",
            "CATEGORY": "gp",
            "TITLE_04": "Spiel",
            "TITLE_08": "Игра",
            "USER_DEFINED_PARAM_1": 2,
            "USER_DEFINED_PARAM_2": 0,
        }
    )
    (patch_dir / "sce_sys" / "param.sfo").write_bytes(patch_param_sfo)
    report = merge_game(settings, inventory, "CUSA12345")
    merged = root / "merged" / "app"
    assert (merged / "data.bin").read_bytes() == b"new"
    merged_param_sfo = merged / "sce_sys" / "param.sfo"
    assert merged_param_sfo.read_bytes() == patch_param_sfo
    assert parse_sfo(merged_param_sfo)["APP_VER"] == "01.10"
    assert parse_sfo(merged_param_sfo)["CATEGORY"] == "gp"
    merged_param_json = validate_shadowmount_param_json(
        (merged / "sce_sys" / "param.json").read_bytes(), "CUSA12345"
    )
    assert merged_param_json["gameIntent"]["permittedIntents"] == [
        {"intentType": "joinSession"}
    ]
    assert merged_param_json["userDefinedParam1"] == 2
    assert "userDefinedParam2" not in merged_param_json
    assert merged_param_json["localizedParameters"]["de-DE"]["titleName"] == "Spiel"
    assert merged_param_json["localizedParameters"]["ru-RU"]["titleName"] == "Игра"
    assert (base_dir / "sce_sys" / "param.json").read_bytes() == original_param_json
    replacement = next(item for item in report["overlay_changes"] if item["path"] == "data.bin")
    assert replacement["previous_size"] == 3
    assert replacement["new_size"] == 3
    assert report["delta_patch_warning"]
    assert not report["generated_param_json"]
    assert report["normalized_existing_param_json"]
    assert report["mirrored_user_defined_params"] == {"userDefinedParam1": 2}
    assert report["mirrored_localized_titles"] == {
        "TITLE_04": "Spiel",
        "TITLE_08": "Игра",
    }
    assert not report["ps5_runtime_verified"]


def test_patched_smp_report_does_not_claim_param_json_projection(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    settings.compat = "patched-smp"
    base = _pkg("base", "1" * 64, "01.00")
    game = {
        "title_id": "CUSA12345",
        "title": "Localized Game",
        "directory_name": "CUSA12345 - Localized Game",
        "base": [base],
        "patches": [],
        "dlc": [],
        "unknown": [],
        "conflicts": [],
        "warnings": [],
        "buildable": True,
    }
    inventory = {"games": {"CUSA12345": game}}
    root = settings.unpacked_dir / game["directory_name"]
    atomic_write_json(
        root / "manifest.json",
        {"synthetic": True, "extractor_revision": EXTRACTOR_REVISION},
    )
    base_dir = package_destination(root, base)
    (base_dir / "sce_sys").mkdir(parents=True)
    (base_dir / "eboot.bin").write_bytes(b"base executable")
    (base_dir / "sce_sys" / "param.sfo").write_bytes(
        make_sfo(
            {
                "TITLE_ID": "CUSA12345",
                "TITLE": "Localized Game",
                "TITLE_08": "Локализованная игра",
                "APP_VER": "01.00",
                "CATEGORY": "gd",
                "USER_DEFINED_PARAM_1": 2,
            }
        )
    )

    report = merge_game(settings, inventory, "CUSA12345")

    assert not (root / "merged" / "app" / "sce_sys" / "param.json").exists()
    assert not report["generated_param_json"]
    assert not report["normalized_existing_param_json"]
    assert report["mirrored_localized_titles"] == {}
    assert report["mirrored_user_defined_params"] == {}


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
    atomic_write_json(
        root / "manifest.json",
        {"synthetic": True, "extractor_revision": EXTRACTOR_REVISION},
    )
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


def test_same_version_additional_layer_has_fixed_overlay_order(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    base = _pkg("base", "e" * 64, "01.00")
    update = _pkg("patch", "f" * 64, "01.10")
    update["path"] = "/mock/original-update.pkg"
    update["patch_role"] = "ordinary"
    update["patch_role_reason"] = "no_explicit_filename_marker"
    fix = _pkg("patch", "0" * 64, "01.10")
    fix["path"] = "/mock/update-Fix5.05.pkg"
    fix["patch_role"] = "additional_layer"
    fix["patch_role_reason"] = "filename_marker:fix5.05"
    game = {
        "title_id": "CUSA10940",
        "title": "Overcooked 2",
        "directory_name": "CUSA10940 - Overcooked 2",
        "base": [base],
        # Deliberately reverse the input order: the plan, not list position,
        # must put the ordinary update before the explicitly marked layer.
        "patches": [fix, update],
        "dlc": [],
        "unknown": [],
        "conflicts": [],
        "warnings": [],
        "buildable": True,
    }
    inventory = {"games": {"CUSA10940": game}}
    root = settings.unpacked_dir / game["directory_name"]
    atomic_write_json(
        root / "manifest.json",
        {"synthetic": True, "extractor_revision": EXTRACTOR_REVISION},
    )
    base_dir = package_destination(root, base)
    update_dir = package_destination(root, update)
    fix_dir = package_destination(root, fix)
    for directory in (base_dir, update_dir, fix_dir):
        (directory / "sce_sys").mkdir(parents=True)
    (base_dir / "eboot.bin").write_bytes(b"base executable")
    (base_dir / "data.bin").write_bytes(b"base")
    (base_dir / "sce_sys" / "param.sfo").write_bytes(
        make_sfo(
            {
                "TITLE_ID": "CUSA10940",
                "TITLE": "Overcooked 2",
                "APP_VER": "01.00",
                "CATEGORY": "gd",
            }
        )
    )
    (update_dir / "data.bin").write_bytes(b"ordinary-update")
    (update_dir / "sce_sys" / "param.sfo").write_bytes(
        make_sfo(
            {
                "TITLE_ID": "CUSA10940",
                "TITLE": "Overcooked 2",
                "APP_VER": "01.10",
                "CATEGORY": "gp",
            }
        )
    )
    (fix_dir / "data.bin").write_bytes(b"additional-layer")

    report = merge_game(settings, inventory, "CUSA10940")

    assert (root / "merged" / "app" / "data.bin").read_bytes() == b"additional-layer"
    assert [entry["source_id"] for entry in report["patch_order"]] == [
        update["source_id"],
        fix["source_id"],
    ]
    assert [entry["role"] for entry in report["patch_order"]] == [
        "ordinary",
        "additional_layer",
    ]


def test_merge_discards_workspace_from_older_extractor_revision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    base = _pkg("base", "e" * 64, "01.00")
    game = {
        "title_id": "CUSA00592",
        "title": "Metro Last Light Redux",
        "directory_name": "CUSA00592 - Metro Last Light Redux",
        "base": [base],
        "patches": [],
        "dlc": [],
        "unknown": [],
        "conflicts": [],
        "warnings": [],
        "buildable": True,
    }
    inventory = {"games": {"CUSA00592": game}}
    root = settings.unpacked_dir / game["directory_name"]
    stale_file = root / "merged" / "app" / "stale.bin"
    stale_file.parent.mkdir(parents=True)
    stale_file.write_bytes(b"old extractor")
    atomic_write_json(
        root / "manifest.json",
        {"extractor_revision": "older-extractor"},
    )

    def fake_unpack(*_args: object) -> dict[str, str]:
        destination = package_destination(root, base)
        (destination / "sce_sys").mkdir(parents=True)
        (destination / "eboot.bin").write_bytes(b"new extraction")
        (destination / "sce_sys" / "param.sfo").write_bytes(
            make_sfo(
                {
                    "TITLE_ID": "CUSA00592",
                    "TITLE": "Metro Last Light Redux",
                    "APP_VER": "01.00",
                    "CATEGORY": "gd",
                }
            )
        )
        atomic_write_json(
            root / "manifest.json",
            {"extractor_revision": EXTRACTOR_REVISION},
        )
        return {"status": "verified"}

    monkeypatch.setattr(pipeline, "unpack_game", fake_unpack)

    report = merge_game(settings, inventory, "CUSA00592")

    assert report["extractor_revision"] == EXTRACTOR_REVISION
    assert not stale_file.exists()
    assert (root / "merged" / "app" / "eboot.bin").read_bytes() == (
        b"new extraction"
    )


def test_dump_merge_repairs_only_npbind_footer_in_temporary_copy(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / "selected-dump"
    (source / "sce_sys").mkdir(parents=True)
    (source / "eboot.bin").write_bytes(b"dump executable")
    (source / "sce_sys" / "param.sfo").write_bytes(
        make_sfo(
            {
                "TITLE_ID": "CUSA00592",
                "TITLE": "Metro Last Light Redux",
                "APP_VER": "01.03",
                "CATEGORY": "gp",
            }
        )
    )
    damaged = _npbind_with_damaged_footer()
    source_npbind = source / "sce_sys" / "npbind.dat"
    source_npbind.write_bytes(damaged)
    base = {
        "kind": "base",
        "source_kind": "dump_tree",
        "source_id": "stat-dump",
        "tree_signature": "stat-dump",
        "app_version": "01.03",
        "path": str(source),
        "pkg_flags": [],
    }
    game = {
        "title_id": "CUSA00592",
        "title": "Metro Last Light Redux",
        "directory_name": "CUSA00592 - Metro Last Light Redux",
        "base": [base],
        "patches": [],
        "dlc": [],
        "unknown": [],
        "conflicts": [],
        "warnings": [],
        "buildable": True,
    }
    inventory = {"games": {"CUSA00592": game}}
    root = settings.unpacked_dir / game["directory_name"]
    atomic_write_json(
        root / "manifest.json",
        {"extractor_revision": EXTRACTOR_REVISION},
    )

    report = merge_game(settings, inventory, "CUSA00592")

    merged = root / "merged" / "app" / "sce_sys" / "npbind.dat"
    assert source_npbind.read_bytes() == damaged
    assert merged.read_bytes()[:-20] == damaged[:-20]
    assert merged.read_bytes()[-20:] == hashlib.sha1(
        merged.read_bytes()[:-20]
    ).digest()
    assert report["npbind_footer_repair"]["repaired"] is True
    assert report["unpacked_source_preserved"] is True
