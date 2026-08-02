from __future__ import annotations

from pathlib import Path

import pytest

from ps4ffpsc import pipeline
from ps4ffpsc.dump_source import DumpSourceError, discover_dump_records
from ps4ffpsc.inventory import scan_dump_directories
from ps4ffpsc.pipeline import (
    EXTRACTOR_REVISION,
    Settings,
    _resume_merged_game,
    merge_game,
    unpack_game,
)
from ps4ffpsc.sfo import build_param_json, make_sfo
from ps4ffpsc.util import atomic_write_json, tree_stat_signature


def _game_tree(
    root: Path,
    *,
    title_id: str = "CUSA12345",
    category: str = "gd",
    app_version: str = "01.00",
    content_id: str = "EP9000-CUSA12345_00-ABCDEFGHIJKLMNOP",
    eboot: bool = True,
) -> Path:
    (root / "sce_sys").mkdir(parents=True)
    if eboot:
        (root / "eboot.bin").write_bytes(b"ELF")
    (root / "sce_sys" / "param.sfo").write_bytes(
        make_sfo(
            {
                "TITLE_ID": title_id,
                "TITLE": "Тестовая игра™",
                "CATEGORY": category,
                "APP_VER": app_version,
                "VERSION": "01.00",
                "CONTENT_ID": content_id,
                "USER_DEFINED_PARAM_1": 2,
            }
        )
    )
    return root


def _snapshot(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _single_base_inventory(record: dict, directory_name: str) -> dict:
    title_id = str(record["title_id"])
    return {
        "games": {
            title_id: {
                "title_id": title_id,
                "title": record["title"],
                "directory_name": directory_name,
                "base": [record],
                "patches": [],
                "dlc": [],
                "unknown": [],
                "conflicts": [],
                "warnings": [],
                "buildable": True,
            }
        }
    }


def test_flat_dump_is_a_consolidated_base_and_keeps_final_patch_category(
    tmp_path: Path,
) -> None:
    source = _game_tree(
        tmp_path / "CUSA12345",
        category="gp",
        app_version="01.10",
    )

    records = discover_dump_records(source)

    assert len(records) == 1
    record = records[0]
    assert record["source_kind"] == "dump_tree"
    assert record["source_layout"] == "consolidated"
    assert record["kind"] == "base"
    assert record["category"] == "gp"
    assert record["app_version"] == "01.10"
    assert record["title"] == "Тестовая игра™"
    assert record["size"] == sum(
        path.stat().st_size for path in source.rglob("*") if path.is_file()
    )
    assert record["source_id"].startswith("stat-")


def test_dumper_app_and_patch_are_returned_in_explicit_overlay_order(
    tmp_path: Path,
) -> None:
    container = tmp_path / "CUSA12345"
    _game_tree(container / "app")
    _game_tree(
        container / "patch",
        category="gp",
        app_version="01.10",
        eboot=False,
    )

    records = discover_dump_records(container)

    assert [record["kind"] for record in records] == ["base", "patch"]
    assert [record["source_layout"] for record in records] == [
        "dumper_app",
        "dumper_patch",
    ]


def test_dump_source_requires_game_files_and_matching_title_id(tmp_path: Path) -> None:
    missing_eboot = tmp_path / "missing"
    _game_tree(missing_eboot, eboot=False)
    with pytest.raises(DumpSourceError, match="flat game root|app directory"):
        discover_dump_records(missing_eboot)

    container = tmp_path / "mismatch"
    _game_tree(container / "app")
    _game_tree(
        container / "patch",
        title_id="CUSA54321",
        category="gp",
        content_id="EP9000-CUSA54321_00-ABCDEFGHIJKLMNOP",
        eboot=False,
    )
    with pytest.raises(DumpSourceError, match="do not match"):
        discover_dump_records(container)


def test_dump_discovery_never_changes_source_tree(tmp_path: Path) -> None:
    source = _game_tree(tmp_path / "source")
    before = _snapshot(source)

    discover_dump_records(source)

    after = _snapshot(source)
    assert after == before


def test_dump_scan_rejects_an_unpacked_workspace_overlap_without_writing_source(
    tmp_path: Path,
) -> None:
    unpacked = tmp_path / "temporary" / "unpacked"
    source = _game_tree(unpacked / "CUSA12345 - Тестовая игра™" / "app")
    selected = source.parent
    before = _snapshot(selected)

    with pytest.raises(DumpSourceError, match="overlaps.*unpacked workspace"):
        scan_dump_directories(tmp_path / "data", (selected,), unpacked)

    assert _snapshot(selected) == before
    assert not (unpacked / "package_inventory.json").exists()


def test_dump_build_rejects_game_workspace_overlap_without_deleting_source(
    tmp_path: Path,
) -> None:
    unpacked = tmp_path / "temporary" / "unpacked"
    selected = unpacked / "CUSA12345 - Тестовая игра™"
    source = _game_tree(selected / "app")
    record = discover_dump_records(selected)[0]
    settings = Settings(
        root=tmp_path / "data",
        pkg_dir=tmp_path / "unused-pkg",
        unpacked_dir=unpacked,
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "temporary" / "work",
        temp_dir=tmp_path / "temporary" / "tmp",
    )
    inventory = _single_base_inventory(record, selected.name)
    before = _snapshot(selected)

    with pytest.raises(ValueError, match="temporary game workspace"):
        unpack_game(settings, inventory, "CUSA12345")

    assert source.is_dir()
    assert _snapshot(selected) == before


@pytest.mark.parametrize(
    ("unsafe_setting", "expected_message"),
    [
        ("output_dir", "output directory must not be inside"),
        ("temp_dir", "temporary files directory"),
        ("work_dir", "work directory"),
    ],
)
def test_dump_build_rejects_unsafe_storage_paths_before_touching_source(
    tmp_path: Path,
    unsafe_setting: str,
    expected_message: str,
) -> None:
    source = _game_tree(tmp_path / "source")
    output_dir = tmp_path / "output"
    work_dir = tmp_path / "temporary" / "work"
    temp_dir = tmp_path / "temporary" / "tmp"
    unsafe_path = source / "application-files"
    if unsafe_setting == "output_dir":
        output_dir = unsafe_path
    elif unsafe_setting == "temp_dir":
        temp_dir = unsafe_path
    else:
        work_dir = unsafe_path
    settings = Settings(
        root=tmp_path / "data",
        pkg_dir=tmp_path / "unused-pkg",
        unpacked_dir=tmp_path / "temporary" / "unpacked",
        output_dir=output_dir,
        work_dir=work_dir,
        temp_dir=temp_dir,
    )
    inventory = scan_dump_directories(
        settings.root,
        (source,),
        settings.unpacked_dir,
    )
    before = _snapshot(source)

    with pytest.raises(ValueError, match=expected_message):
        pipeline.build_game(settings, "CUSA12345", inventory)

    assert _snapshot(source) == before
    assert not unsafe_path.exists()


def test_dump_inventory_and_merge_use_source_in_place_without_extractor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _game_tree(
        tmp_path / "owned-dump" / "CUSA12345",
        category="gp",
        app_version="01.10",
    )
    before = _snapshot(source)
    settings = Settings(
        root=tmp_path / "app-data",
        pkg_dir=tmp_path / "unused-pkg",
        unpacked_dir=tmp_path / "temporary" / "unpacked",
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "temporary" / "work",
        temp_dir=tmp_path / "temporary" / "tmp",
        dump_dirs=(source,),
    )
    settings.root.mkdir(parents=True)
    settings.unpacked_dir.mkdir(parents=True)
    inventory = scan_dump_directories(
        settings.root,
        settings.dump_dirs,
        settings.unpacked_dir,
    )
    monkeypatch.setattr(
        pipeline,
        "extractor_or_raise",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("an unpacked source must not invoke the PKG extractor")
        ),
    )

    manifest = unpack_game(settings, inventory, "CUSA12345")
    report = merge_game(settings, inventory, "CUSA12345")

    extraction = manifest["extractions"][0]
    assert extraction["status"] == "verified_source_tree"
    assert extraction["source_preserved"] is True
    assert extraction["destination"] == str(source)
    assert report["latest_app_version"] == "01.10"
    assert report["staging_moves"] == 0
    merged = (
        settings.unpacked_dir
        / inventory["games"]["CUSA12345"]["directory_name"]
        / "merged"
        / "app"
    )
    assert (merged / "eboot.bin").is_file()
    assert (merged / "sce_sys" / "param.sfo").read_bytes() == before[
        Path("sce_sys/param.sfo")
    ]
    assert (merged / "sce_sys" / "param.json").is_file()
    after = _snapshot(source)
    assert after == before


def test_successful_dump_build_preserves_the_selected_source_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _game_tree(tmp_path / "source")
    settings = Settings(
        root=tmp_path / "data",
        pkg_dir=tmp_path / "unused-pkg",
        unpacked_dir=tmp_path / "temporary" / "unpacked",
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "temporary" / "work",
        temp_dir=tmp_path / "temporary" / "tmp",
    )
    inventory = scan_dump_directories(
        settings.root,
        (source,),
        settings.unpacked_dir,
    )
    before = _snapshot(source)
    monkeypatch.setattr(pipeline, "mkpfs_command", lambda *_args: ["mkpfs"])
    monkeypatch.setattr(
        pipeline,
        "_verify_image",
        lambda *_args, **_kwargs: {"verified": True},
    )

    def fake_run(command: list[str], _log_path: Path) -> None:
        Path(command[-1]).write_bytes(b"verified image")

    monkeypatch.setattr(pipeline, "_run_logged", fake_run)

    result = pipeline.build_game(settings, "CUSA12345", inventory)

    assert Path(result["artifact"]).is_file()
    assert not (
        settings.unpacked_dir / "CUSA12345 - Тестовая игра™"
    ).exists()
    assert _snapshot(source) == before


def test_resume_for_dump_tree_uses_tree_signature(tmp_path: Path) -> None:
    source = _game_tree(tmp_path / "owned-dump" / "CUSA12345")
    settings = Settings(
        root=tmp_path / "app-data",
        pkg_dir=tmp_path / "unused-pkg",
        unpacked_dir=tmp_path / "temporary" / "unpacked",
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "temporary" / "work",
        temp_dir=tmp_path / "temporary" / "tmp",
        dump_dirs=(source,),
    )
    settings.root.mkdir(parents=True)
    inventory = scan_dump_directories(
        settings.root,
        settings.dump_dirs,
        settings.unpacked_dir,
    )
    game = inventory["games"]["CUSA12345"]
    root = settings.unpacked_dir / game["directory_name"]
    app = root / "merged" / "app"
    (app / "sce_sys").mkdir(parents=True)
    (app / "eboot.bin").write_bytes(b"ELF")
    (app / "sce_sys" / "param.sfo").write_bytes(
        (source / "sce_sys" / "param.sfo").read_bytes()
    )
    (app / "sce_sys" / "param.json").write_bytes(
        build_param_json("CUSA12345", "Тестовая игра™")
    )
    source_id = game["base"][0]["source_id"]
    atomic_write_json(
        root / "manifest.json",
        {"packages": [{"path": str(source), "source_id": source_id}]},
    )
    atomic_write_json(
        root / "reports" / "merge_report.json",
        {
            "title_id": "CUSA12345",
            "compatibility": "current-smp",
            "extractor_revision": EXTRACTOR_REVISION,
            "latest_app_version": "01.00",
            "merged_tree_signature": tree_stat_signature(app),
        },
    )

    report = _resume_merged_game(settings, game, "CUSA12345")

    assert report is not None
    assert game["base"][0]["source_id"] == source_id
    (source / "changed.bin").write_bytes(b"changed")
    assert _resume_merged_game(settings, game, "CUSA12345") is None
