from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ps4ffpsc import pipeline
from ps4ffpsc.pipeline import (
    EXTRACTOR_REVISION,
    EXTRACTION_STATE_SCHEMA_VERSION,
    Settings,
    _artifact_sidecar_path,
    _resume_merged_game,
    build_game,
)
from ps4ffpsc.sfo import build_param_json, make_sfo
from ps4ffpsc.util import (
    atomic_write_json,
    file_stat_identity,
    read_json,
    tree_stat_signature,
)


def _settings(root: Path) -> Settings:
    return Settings(
        root=root,
        pkg_dir=root / "pkg",
        unpacked_dir=root / "temporary" / "unpacked",
        output_dir=root / "output",
        work_dir=root / "temporary" / "work",
        temp_dir=root / "temporary" / "tmp",
    )


def _inventory(source: Path) -> dict:
    base = {
        "kind": "base",
        "supported": True,
        "app_version": "01.00",
        "path": str(source),
        "size": source.stat().st_size,
    }
    game = {
        "title_id": "CUSA12345",
        "title": "Synthetic Game",
        "directory_name": "CUSA12345 - Synthetic Game",
        "base": [base],
        "patches": [],
        "dlc": [],
        "unknown": [],
        "conflicts": [],
        "warnings": [],
        "buildable": True,
    }
    return {"games": {"CUSA12345": game}}


def _prepare_fake_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    inventory: dict,
) -> Path:
    game = inventory["games"]["CUSA12345"]
    root = settings.unpacked_dir / game["directory_name"]
    base = game["base"][0]

    def fake_unpack(
        _settings: Settings, _inventory: dict, _title_id: str
    ) -> dict:
        base["source_id"] = file_stat_identity(Path(base["path"]))
        extracted = root / "packages" / "base" / "aaaaaaaaaaaa"
        extracted.mkdir(parents=True)
        (extracted / "large.bin").write_bytes(b"temporary")
        return {"status": "verified"}

    def fake_merge(
        _settings: Settings,
        _inventory: dict,
        _title_id: str,
        _compat: str,
    ) -> dict:
        app = root / "merged" / "app"
        (app / "sce_sys").mkdir(parents=True)
        (app / "eboot.bin").write_bytes(b"eboot")
        (app / "sce_sys" / "param.sfo").write_bytes(
            make_sfo(
                {
                    "TITLE_ID": "CUSA12345",
                    "TITLE": "Synthetic Game",
                    "APP_VER": "01.00",
                    "CATEGORY": "gd",
                }
            )
        )
        (app / "sce_sys" / "param.json").write_text(
            '{"titleId":"CUSA12345"}', encoding="utf-8"
        )
        for item in game["dlc"]:
            if item.get("duplicate_of"):
                continue
            label = item["entitlement_label"]
            addcont = root / "merged" / "addcont" / label
            addcont.mkdir(parents=True)
            (addcont / "ps4ffpsc-dlc.json").write_text(
                '{"title_id":"CUSA12345"}', encoding="utf-8"
            )
            (addcont / "content.bin").write_bytes(label.encode("ascii"))
        return {"latest_app_version": "01.00"}

    def fake_run(
        command: list[str], _log_path: Path
    ) -> subprocess.CompletedProcess[str]:
        Path(command[-1]).write_bytes(b"verified ffpfsc")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pipeline, "_resume_merged_game", lambda *_args: None)
    monkeypatch.setattr(pipeline, "unpack_game", fake_unpack)
    monkeypatch.setattr(pipeline, "merge_game", fake_merge)
    monkeypatch.setattr(
        pipeline,
        "check_disk_space",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError(
                "packing must use MkPFS destination and spool space checks"
            )
        ),
    )
    monkeypatch.setattr(pipeline, "mkpfs_command", lambda *_args: ["mkpfs"])
    monkeypatch.setattr(pipeline, "_run_logged", fake_run)
    return root


def test_successful_build_removes_only_its_temporary_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    settings.compression_level = 9
    settings.compression_workers = 4
    monkeypatch.setattr(
        pipeline,
        "maximum_logical_cpu_count",
        lambda: 12,
    )
    source = tmp_path / "source.pkg"
    source.write_bytes(b"owned source")
    inventory = _inventory(source)
    root = _prepare_fake_pipeline(monkeypatch, settings, inventory)
    monkeypatch.setattr(
        pipeline,
        "_verify_image",
        lambda *_args, **_kwargs: {"verified": True},
    )
    monkeypatch.setattr(
        pipeline,
        "sha256_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("normal build must not hash file payloads")
        ),
    )
    expected_output = (
        settings.output_dir
        / "CUSA12345 - Synthetic Game [v01.00].ffpfsc"
    )
    settings.output_dir.mkdir(parents=True)
    stale_checksum = expected_output.with_name(f"{expected_output.name}.sha256")
    stale_checksum.write_text("stale\n", encoding="utf-8")

    result = build_game(settings, "CUSA12345", inventory)

    output = Path(result["artifact"])
    assert output.read_bytes() == b"verified ffpfsc"
    assert source.read_bytes() == b"owned source"
    assert not root.exists()
    assert result["temporary_workspace_cleaned"] is True
    assert result["sha256"] is None
    assert result["checksum_generated"] is False
    assert result["compression_level"] == 9
    assert result["compression_workers"] == 4
    assert result["compression_workers_mode"] == "selected"
    assert not stale_checksum.exists()
    assert read_json(_artifact_sidecar_path(output, ".manifest.json"))[
        "temporary_workspace_cleaned"
    ] is True


def test_transactional_publication_restores_existing_results_on_late_failure(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "game.ffpfsc"
    checksum = tmp_path / "game.ffpfsc.sha256"
    staged = tmp_path / "game.ffpfsc.partial"
    destination.write_bytes(b"old image")
    checksum.write_text("old checksum\n", encoding="utf-8")
    staged.write_bytes(b"new image")

    def fail_finalize() -> None:
        raise RuntimeError("late cleanup failure")

    with pytest.raises(RuntimeError, match="late cleanup failure"):
        pipeline._publish_files_transactionally(
            [(None, checksum), (staged, destination)],
            fail_finalize,
            allow_replace=True,
        )

    assert destination.read_bytes() == b"old image"
    assert checksum.read_text(encoding="utf-8") == "old checksum\n"
    assert not staged.exists()
    assert not list(tmp_path.glob(".*.backup-*"))


def test_missing_merged_dlc_tree_is_an_error_in_experimental_mode(
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="merged DLC tree is missing"):
        pipeline.embed_experimental_dlc(
            tmp_path / "merged" / "app",
            tmp_path / "merged" / "addcont",
            [
                {
                    "source_id": "stat-missing-dlc",
                    "entitlement_label": "ABCDEFGHIJKLMNOP",
                    "dlc_package_type": "PSAC",
                }
            ],
            tmp_path / "dlc-single-work",
            tmp_path,
        )


def test_default_off_mode_excludes_detected_dlc_and_publishes_one_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    assert settings.dlc_mode == "off"
    source = tmp_path / "source.pkg"
    source.write_bytes(b"owned source")
    inventory = _inventory(source)
    game = inventory["games"]["CUSA12345"]
    game["dlc"] = [
        {
            "kind": "dlc",
            "supported": True,
            "app_version": "",
            "path": str(tmp_path / "dlc.pkg"),
            "source_id": "stat-dlc",
            "size": 1,
            "entitlement_label": "ABCDEFGHIJKLMNOP",
            "validation_errors": ["region_or_content_mismatch"],
        }
    ]
    root = _prepare_fake_pipeline(monkeypatch, settings, inventory)
    monkeypatch.setattr(
        pipeline,
        "_verify_image",
        lambda *_args, **_kwargs: {"verified": True},
    )
    monkeypatch.setattr(
        pipeline,
        "embed_experimental_dlc",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("DLC embedding must remain disabled by default")
        ),
    )

    result = build_game(settings, "CUSA12345", inventory)

    assert result["dlc_detected"] is True
    assert result["dlc_packaged"] is False
    assert result["dlc_mode"] == "off"
    assert result["dlc_embedding"] is None
    assert result["dlc_artifacts"] == []
    assert [path.name for path in settings.output_dir.glob("*.ffpfsc")] == [
        "CUSA12345 - Synthetic Game [v01.00].ffpfsc"
    ]
    assert not root.exists()


def test_experimental_single_image_embeds_before_pack_and_publishes_one_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    settings.dlc_mode = "single-experimental"
    source = tmp_path / "source.pkg"
    source.write_bytes(b"owned source")
    inventory = _inventory(source)
    game = inventory["games"]["CUSA12345"]
    game["dlc"] = [
        {
            "kind": "dlc",
            "supported": True,
            "app_version": "",
            "path": str(tmp_path / "dlc.pkg"),
            "source_id": "stat-dlc",
            "size": 1,
            "entitlement_label": "ABCDEFGHIJKLMNOP",
        }
    ]
    root = _prepare_fake_pipeline(monkeypatch, settings, inventory)
    monkeypatch.setattr(
        pipeline,
        "_verify_image",
        lambda *_args, **_kwargs: {"verified": True},
    )
    events: list[str] = []
    embedding = {
        "mode": "single-experimental",
        "experimental": True,
        "applied": True,
        "dlc_count": 1,
        "runtime_verified": False,
        "entries": [{"label": "ABCDEFGHIJKLMNOP"}],
    }

    def fake_embed(
        app: Path,
        addcont_root: Path,
        dlc_items: list[dict],
        work_root: Path,
        resource_root: Path,
    ) -> dict:
        events.append("embed")
        assert app == root / "merged" / "app"
        assert addcont_root == root / "merged" / "addcont"
        assert dlc_items == game["dlc"]
        assert work_root == root / "dlc-single-work"
        assert resource_root == settings.root
        assert not list(settings.output_dir.glob("*.ffpfsc*"))
        return embedding

    def fake_pack(
        command: list[str],
        _log_path: Path,
    ) -> subprocess.CompletedProcess[str]:
        events.append("pack")
        destination = Path(command[-1])
        destination.write_bytes(b"verified ffpfsc")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pipeline, "embed_experimental_dlc", fake_embed)
    monkeypatch.setattr(pipeline, "_run_logged", fake_pack)

    result = build_game(settings, "CUSA12345", inventory)

    output = Path(result["artifact"])
    assert events == ["embed", "pack"]
    assert output.read_bytes() == b"verified ffpfsc"
    assert result["dlc_mode"] == "single-experimental"
    assert result["dlc_packaged"] is True
    assert result["dlc_embedding"] == embedding
    assert result["dlc_artifacts"] == []
    assert list(settings.output_dir.glob("*.ffpfsc")) == [output]
    assert not list(settings.output_dir.glob("*.partial"))
    assert not root.exists()


def test_experimental_embed_failure_publishes_nothing_and_allows_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    settings.dlc_mode = "single-experimental"
    source = tmp_path / "source.pkg"
    source.write_bytes(b"owned source")
    inventory = _inventory(source)
    game = inventory["games"]["CUSA12345"]
    game["dlc"] = [
        {
            "kind": "dlc",
            "supported": True,
            "app_version": "",
            "path": str(tmp_path / "dlc.pkg"),
            "source_id": "stat-dlc",
            "size": 1,
            "entitlement_label": "ABCDEFGHIJKLMNOP",
        }
    ]
    root = _prepare_fake_pipeline(monkeypatch, settings, inventory)
    monkeypatch.setattr(
        pipeline,
        "_verify_image",
        lambda *_args, **_kwargs: {"verified": True},
    )
    state = {"fail": True, "calls": 0}

    def embed_once_then_succeed(*_args: object, **_kwargs: object) -> dict:
        state["calls"] += 1
        if state["fail"]:
            raise RuntimeError("experimental DLC embedding failed")
        return {
            "mode": "single-experimental",
            "experimental": True,
            "applied": True,
            "dlc_count": 1,
            "runtime_verified": False,
            "entries": [{"label": "ABCDEFGHIJKLMNOP"}],
        }

    monkeypatch.setattr(
        pipeline,
        "embed_experimental_dlc",
        embed_once_then_succeed,
    )

    with pytest.raises(
        RuntimeError,
        match="experimental DLC embedding failed",
    ):
        build_game(settings, "CUSA12345", inventory)

    assert (root / "merged" / "app").is_dir()
    assert not list(settings.output_dir.glob("*.ffpfsc"))
    assert not list(settings.output_dir.glob("*.manifest.json"))
    assert not list(settings.output_dir.glob("*.shadowmount.txt"))
    assert not list(settings.output_dir.glob("*.partial"))

    state["fail"] = False
    result = build_game(settings, "CUSA12345", inventory)

    output = Path(result["artifact"])
    assert output.is_file()
    assert state["calls"] == 2
    assert result["dlc_packaged"] is True
    assert result["dlc_artifacts"] == []
    assert list(settings.output_dir.glob("*.ffpfsc")) == [output]
    assert _artifact_sidecar_path(output, ".manifest.json").is_file()
    assert _artifact_sidecar_path(output, ".shadowmount.txt").is_file()
    assert not list(settings.output_dir.glob("*.partial"))


def test_mkpfs_compression_arguments_use_selected_level_and_default_half_cpus(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    settings.compression_level = 3
    monkeypatch.setattr(
        pipeline,
        "maximum_logical_cpu_count",
        lambda: 20,
    )

    assert pipeline.mkpfs_compression_arguments(settings) == [
        "--cpu-count",
        "10",
        "--compression-level",
        "3",
    ]

    settings.compression_workers = 7
    assert pipeline.mkpfs_compression_arguments(settings) == [
        "--cpu-count",
        "7",
        "--compression-level",
        "3",
    ]


def test_failed_verification_keeps_resumable_merged_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / "source.pkg"
    source.write_bytes(b"owned source")
    inventory = _inventory(source)
    root = _prepare_fake_pipeline(monkeypatch, settings, inventory)

    def fail_verification(*_args: object, **_kwargs: object) -> dict:
        raise RuntimeError("verification failed")

    monkeypatch.setattr(pipeline, "_verify_image", fail_verification)

    with pytest.raises(RuntimeError, match="verification failed"):
        build_game(settings, "CUSA12345", inventory)

    assert (root / "merged" / "app").is_dir()
    assert source.read_bytes() == b"owned source"


def test_exfat_build_is_uncompressed_and_does_not_create_a_second_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    settings.output_format = "exfat"
    settings.keep_inner_image = False
    source = tmp_path / "source.pkg"
    source.write_bytes(b"owned source")
    inventory = _inventory(source)
    root = _prepare_fake_pipeline(monkeypatch, settings, inventory)
    commands: list[list[str]] = []

    def fake_run(
        command: list[str],
        _log_path: Path,
    ) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        assert command[1:3] == ["pack", "exfat"]
        Path(command[4]).write_bytes(b"verified raw exfat")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pipeline, "_run_logged", fake_run)
    monkeypatch.setattr(
        pipeline,
        "_verify_image",
        lambda *_args, **kwargs: {
            "verified": True,
            "verification_mode": "exfat_and_required_files",
            "image_format": kwargs["image_format"],
        },
    )

    result = build_game(settings, "CUSA12345", inventory)

    output = Path(result["artifact"])
    assert output.suffix == ".exfat"
    assert output.read_bytes() == b"verified raw exfat"
    assert commands == [
        [
            "mkpfs",
            "pack",
            "exfat",
            str(root / "merged" / "app"),
            str(output.with_name(f"{output.name}.partial")),
            "--cluster-size",
            "65536",
        ]
    ]
    assert result["output_format"] == "exfat"
    assert result["outer_container"] is None
    assert result["compression_level"] is None
    assert result["compression_workers"] is None
    assert result["compression_workers_mode"] == "not_applicable"
    assert result["kept_inner_image"] is None
    assert not list(settings.output_dir.glob("*.inner.exfat"))
    assert _artifact_sidecar_path(output, ".manifest.json").is_file()
    assert _artifact_sidecar_path(output, ".shadowmount.txt").is_file()
    assert not root.exists()


def test_ffpfsc_and_exfat_use_distinct_sidecar_paths(tmp_path: Path) -> None:
    ffpfsc = tmp_path / "Synthetic Game [v01.00].ffpfsc"
    exfat = tmp_path / "Synthetic Game [v01.00].exfat"

    assert _artifact_sidecar_path(
        ffpfsc,
        ".manifest.json",
    ) != _artifact_sidecar_path(exfat, ".manifest.json")
    assert _artifact_sidecar_path(
        ffpfsc,
        ".shadowmount.txt",
    ) != _artifact_sidecar_path(exfat, ".shadowmount.txt")


def test_output_inside_game_workspace_is_rejected_before_cleanup(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / "source.pkg"
    source.write_bytes(b"owned source")
    inventory = _inventory(source)
    game = inventory["games"]["CUSA12345"]
    root = settings.unpacked_dir / game["directory_name"]
    settings.output_dir = root / "unsafe-output"

    with pytest.raises(ValueError, match="must not be inside"):
        build_game(settings, "CUSA12345", inventory)

    assert source.read_bytes() == b"owned source"


def test_unpack_does_not_hash_source_or_extracted_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / "source.pkg"
    source.write_bytes(b"large source placeholder")
    inventory = _inventory(source)
    monkeypatch.setattr(pipeline, "check_disk_space", lambda *_args: None)
    monkeypatch.setattr(
        pipeline, "extractor_or_raise", lambda *_args: tmp_path / "extractor"
    )
    monkeypatch.setattr(
        pipeline,
        "sha256_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("normal extraction must not hash file payloads")
        ),
    )

    def fake_extract(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        destination = Path(command[command.index("--output") + 1])
        destination.mkdir(parents=True)
        (destination / "payload.bin").write_bytes(b"extracted")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pipeline, "_run_captured", fake_extract)

    manifest = pipeline.unpack_game(settings, inventory, "CUSA12345")

    package = manifest["packages"][0]
    assert package["source_id"].startswith("stat-")
    assert "sha256" not in package
    assert manifest["extractions"][0]["tree_signature"].startswith("stat-")


def test_unpack_manifest_records_explicit_same_version_layer_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    settings.dry_run = True
    base_source = tmp_path / "base.pkg"
    update_source = tmp_path / "ordinary-update.pkg"
    fix_source = tmp_path / "update-Fix5.05.pkg"
    for source in (base_source, update_source, fix_source):
        source.write_bytes(b"source")
    inventory = _inventory(base_source)
    game = inventory["games"]["CUSA12345"]
    update = {
        "kind": "patch",
        "supported": True,
        "app_version": "01.10",
        "path": str(update_source),
        "size": update_source.stat().st_size,
        "patch_role": "ordinary",
        "patch_role_reason": "no_explicit_filename_marker",
    }
    fix = {
        "kind": "patch",
        "supported": True,
        "app_version": "01.10",
        "path": str(fix_source),
        "size": fix_source.stat().st_size,
        "patch_role": "additional_layer",
        "patch_role_reason": "filename_marker:fix5.05",
    }
    game["patches"] = [fix, update]
    monkeypatch.setattr(pipeline, "check_disk_space", lambda *_args: None)
    monkeypatch.setattr(
        pipeline,
        "extractor_or_raise",
        lambda *_args: tmp_path / "extractor",
    )

    manifest = pipeline.unpack_game(settings, inventory, "CUSA12345")

    assert [item["source_id"] for item in manifest["patch_plan"]] == [
        update["source_id"],
        fix["source_id"],
    ]
    assert [item["role"] for item in manifest["patch_plan"]] == [
        "ordinary",
        "additional_layer",
    ]
    assert [Path(item["path"]).name for item in manifest["packages"]] == [
        "base.pkg",
        "ordinary-update.pkg",
        "update-Fix5.05.pkg",
    ]


def test_unpack_skips_dlc_when_experimental_mode_is_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    settings.dry_run = True
    base_source = tmp_path / "base.pkg"
    dlc_source = tmp_path / "dlc.pkg"
    base_source.write_bytes(b"base")
    dlc_source.write_bytes(b"dlc")
    inventory = _inventory(base_source)
    inventory["games"]["CUSA12345"]["dlc"] = [
        {
            "kind": "dlc",
            "supported": True,
            "path": str(dlc_source),
            "size": dlc_source.stat().st_size,
            "entitlement_label": "ABCDEFGHIJKLMNOP",
        }
    ]
    monkeypatch.setattr(pipeline, "check_disk_space", lambda *_args: None)
    monkeypatch.setattr(
        pipeline,
        "extractor_or_raise",
        lambda *_args: tmp_path / "extractor",
    )

    manifest = pipeline.unpack_game(settings, inventory, "CUSA12345")

    assert [Path(item["path"]).name for item in manifest["packages"]] == [
        "base.pkg"
    ]


def test_unpack_resumes_verified_pkg_and_extracts_only_pending_pkg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    base_source = tmp_path / "base.pkg"
    patch_source = tmp_path / "patch.pkg"
    base_source.write_bytes(b"base source")
    patch_source.write_bytes(b"patch source is larger")
    inventory = _inventory(base_source)
    game = inventory["games"]["CUSA12345"]
    base = game["base"][0]
    patch = {
        "kind": "patch",
        "supported": True,
        "app_version": "01.10",
        "path": str(patch_source),
        "size": patch_source.stat().st_size,
    }
    game["patches"] = [patch]
    base["source_id"] = file_stat_identity(base_source)
    root = settings.unpacked_dir / game["directory_name"]
    base_destination = pipeline.package_destination(root, base)
    base_destination.mkdir(parents=True)
    (base_destination / "base.bin").write_bytes(b"already extracted")
    base_record = {
        "status": "verified",
        "source_path": str(base_source),
        "source_id": base["source_id"],
        "destination": str(base_destination),
        "tree_signature": tree_stat_signature(base_destination),
        "file_count": 1,
        "total_size": len(b"already extracted"),
    }
    atomic_write_json(
        root / ".ps4ffpsc-state.json",
        {
            "schema_version": EXTRACTION_STATE_SCHEMA_VERSION,
            "extractor_revision": EXTRACTOR_REVISION,
            "packages": {base["source_id"]: base_record},
        },
    )
    disk_requirements: list[int] = []
    extracted_sources: list[Path] = []
    monkeypatch.setattr(
        pipeline,
        "check_disk_space",
        lambda _path, required: disk_requirements.append(required),
    )
    monkeypatch.setattr(
        pipeline,
        "extractor_or_raise",
        lambda *_args: tmp_path / "extractor",
    )

    def fake_extract(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        extracted_sources.append(Path(command[2]))
        destination = Path(command[command.index("--output") + 1])
        destination.mkdir(parents=True)
        (destination / "patch.bin").write_bytes(b"new extraction")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pipeline, "_run_captured", fake_extract)

    manifest = pipeline.unpack_game(settings, inventory, "CUSA12345")

    assert extracted_sources == [patch_source]
    assert disk_requirements == [pipeline._disk_required([patch], 1.25)]
    assert manifest["extractions"][0] == base_record
    assert manifest["extractions"][1]["source_path"] == str(patch_source)
    assert base_destination.joinpath("base.bin").read_bytes() == b"already extracted"


def test_unpack_fully_resumed_skips_extractor_and_space_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / "source.pkg"
    source.write_bytes(b"source")
    inventory = _inventory(source)
    game = inventory["games"]["CUSA12345"]
    package = game["base"][0]
    package["source_id"] = file_stat_identity(source)
    root = settings.unpacked_dir / game["directory_name"]
    destination = pipeline.package_destination(root, package)
    destination.mkdir(parents=True)
    (destination / "payload.bin").write_bytes(b"complete")
    atomic_write_json(
        root / ".ps4ffpsc-state.json",
        {
            "schema_version": EXTRACTION_STATE_SCHEMA_VERSION,
            "extractor_revision": EXTRACTOR_REVISION,
            "packages": {
                package["source_id"]: {
                    "status": "verified",
                    "source_path": str(source),
                    "source_id": package["source_id"],
                    "destination": str(destination),
                    "tree_signature": tree_stat_signature(destination),
                }
            },
        },
    )
    monkeypatch.setattr(
        pipeline,
        "check_disk_space",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("no new extraction needs a space check")
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "extractor_or_raise",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("no new extraction needs the helper")
        ),
    )

    manifest = pipeline.unpack_game(settings, inventory, "CUSA12345")

    assert len(manifest["extractions"]) == 1
    assert manifest["extractions"][0]["status"] == "verified"


def test_missing_state_is_recovered_from_current_manifest(
    tmp_path: Path,
) -> None:
    root = tmp_path / "unpacked" / "CUSA12345 - Synthetic Game"
    destination = root / "packages" / "base" / "existing"
    destination.mkdir(parents=True)
    (destination / "payload.bin").write_bytes(b"existing")
    record = {
        "status": "verified",
        "source_id": "stat-existing",
        "source_path": str(tmp_path / "source.pkg"),
        "destination": str(destination),
        "tree_signature": tree_stat_signature(destination),
    }
    atomic_write_json(
        root / "manifest.json",
        {
            "extractor_revision": EXTRACTOR_REVISION,
            "extractions": [record],
        },
    )

    state = pipeline._load_state(root)

    assert state["packages"] == {"stat-existing": record}
    assert state["extractor_revision"] == EXTRACTOR_REVISION
    assert read_json(root / ".ps4ffpsc-state.json")["packages"] == {
        "stat-existing": record
    }


def test_old_manifest_without_state_discards_orphaned_package_trees(
    tmp_path: Path,
) -> None:
    root = tmp_path / "unpacked" / "CUSA12345 - Synthetic Game"
    package_tree = root / "packages" / "base" / "stale"
    package_tree.mkdir(parents=True)
    (package_tree / "npbind.dat").write_bytes(b"stale")
    atomic_write_json(
        root / "manifest.json",
        {
            "extractor_revision": "older-extractor",
            "extractions": [],
        },
    )

    state = pipeline._load_state(root)

    assert state["extractor_revision"] == EXTRACTOR_REVISION
    assert state["packages"] == {}
    assert not (root / "packages").exists()


def test_unpack_rejects_pkg_changed_after_fast_metadata_scan(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / "source.pkg"
    source.write_bytes(b"original")
    inventory = _inventory(source)
    inventory["games"]["CUSA12345"]["base"][0]["source_id"] = file_stat_identity(
        source
    )
    source.write_bytes(b"changed and larger")

    with pytest.raises(RuntimeError, match="changed after scanning"):
        pipeline.unpack_game(settings, inventory, "CUSA12345")


def test_unpack_progress_is_weighted_by_source_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    base_source = tmp_path / "base.pkg"
    patch_source = tmp_path / "patch.pkg"
    base_source.write_bytes(b"b" * 10)
    patch_source.write_bytes(b"p" * 30)
    inventory = _inventory(base_source)
    game = inventory["games"]["CUSA12345"]
    patch = {
        "kind": "patch",
        "supported": True,
        "app_version": "01.10",
        "path": str(patch_source),
        "size": patch_source.stat().st_size,
    }
    game["patches"] = [patch]
    events: list[dict[str, object]] = []
    monkeypatch.setattr(pipeline, "check_disk_space", lambda *_args: None)
    monkeypatch.setattr(
        pipeline, "extractor_or_raise", lambda *_args: tmp_path / "extractor"
    )
    monkeypatch.setattr(
        pipeline,
        "_emit_gui_progress",
        lambda scope, **payload: events.append({"scope": scope, **payload}),
    )

    def fake_extract(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        destination = Path(command[command.index("--output") + 1])
        destination.mkdir(parents=True)
        (destination / "payload.bin").write_bytes(b"extracted")
        callback = kwargs["stdout_line_callback"]
        assert callable(callback)
        callback(
            '{"event":"extract_start","bytes_current":0,"bytes_total":200,'
            '"files_current":0,"files_total":2}'
        )
        callback(
            '{"event":"extract_progress","bytes_current":100,"bytes_total":200,'
            '"files_current":1,"files_total":2}'
        )
        callback(
            '{"event":"extract_complete","bytes_current":200,"bytes_total":200,'
            '"files":2}'
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pipeline, "_run_captured", fake_extract)

    pipeline.unpack_game(settings, inventory, "CUSA12345")

    halfway = [
        event
        for event in events
        if event.get("package_bytes_current") == 100
    ]
    assert [(event["package_index"], event["current"], event["total"]) for event in halfway] == [
        (1, 5, 40),
        (2, 25, 40),
    ]
    completed = [
        event
        for event in events
        if event.get("package_bytes_current") == 200
    ]
    assert [(event["package_index"], event["current"], event["total"]) for event in completed] == [
        (1, 10, 40),
        (2, 40, 40),
    ]


def test_verified_merged_workspace_can_resume_without_extracted_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / "source.pkg"
    source.write_bytes(b"owned source")
    inventory = _inventory(source)
    game = inventory["games"]["CUSA12345"]
    root = settings.unpacked_dir / game["directory_name"]
    app = root / "merged" / "app"
    (app / "sce_sys").mkdir(parents=True)
    (app / "eboot.bin").write_bytes(b"eboot")
    (app / "sce_sys" / "param.sfo").write_bytes(
        make_sfo(
            {
                "TITLE_ID": "CUSA12345",
                "TITLE": "Synthetic Game",
                "APP_VER": "01.00",
                "CATEGORY": "gd",
            }
        )
    )
    (app / "sce_sys" / "param.json").write_bytes(
        build_param_json("CUSA12345", "Synthetic Game")
    )
    source_id = file_stat_identity(source)
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
    monkeypatch.setattr(
        pipeline,
        "sha256_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("resume must not read full file payloads")
        ),
    )

    report = _resume_merged_game(settings, game, "CUSA12345")

    assert report is not None
    assert report["latest_app_version"] == "01.00"
    assert game["base"][0]["source_id"] == source_id
    assert not (root / "packages").exists()


def test_experimental_mode_rejects_selected_dlc_with_inventory_errors(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    settings.dlc_mode = "single-experimental"
    game = {
        "dlc": [
            {
                "path": str(tmp_path / "wrong-region.pkg"),
                "supported": True,
                "validation_errors": ["region_or_content_mismatch"],
            }
        ]
    }

    with pytest.raises(
        RuntimeError,
        match="selected experimental DLC failed inventory validation",
    ):
        pipeline._selected_dlc_packages(settings, game)


def _prepare_resumable_experimental_merge(
    tmp_path: Path,
    *,
    embedded: bool,
) -> tuple[Settings, dict, Path, Path]:
    settings = _settings(tmp_path)
    settings.dlc_mode = "single-experimental"
    base_source = tmp_path / "base.pkg"
    dlc_source = tmp_path / "dlc.pkg"
    base_source.write_bytes(b"base source")
    dlc_source.write_bytes(b"dlc source")
    inventory = _inventory(base_source)
    game = inventory["games"]["CUSA12345"]
    game["dlc"] = [
        {
            "kind": "dlc",
            "supported": True,
            "path": str(dlc_source),
            "size": dlc_source.stat().st_size,
            "entitlement_label": "ABCDEFGHIJKLMNOP",
        }
    ]
    root = settings.unpacked_dir / game["directory_name"]
    app = root / "merged" / "app"
    (app / "sce_sys").mkdir(parents=True)
    (app / "eboot.bin").write_bytes(b"eboot")
    (app / "sce_sys" / "param.sfo").write_bytes(
        make_sfo(
            {
                "TITLE_ID": "CUSA12345",
                "TITLE": "Synthetic Game",
                "APP_VER": "01.00",
                "CATEGORY": "gd",
            }
        )
    )
    (app / "sce_sys" / "param.json").write_bytes(
        build_param_json("CUSA12345", "Synthetic Game")
    )
    addcont_label = root / "merged" / "addcont" / "ABCDEFGHIJKLMNOP"
    addcont_label.mkdir(parents=True)
    (addcont_label / "content.bin").write_bytes(b"dlc content")
    (addcont_label / "ps4ffpsc-dlc.json").write_text(
        '{"title_id":"CUSA12345"}', encoding="utf-8"
    )
    dlc_manifest = pipeline._dlc_staging_manifest(addcont_label)
    atomic_write_json(
        root / "manifest.json",
        {
            "packages": [
                {
                    "path": str(base_source),
                    "source_id": file_stat_identity(base_source),
                },
                {
                    "path": str(dlc_source),
                    "source_id": file_stat_identity(dlc_source),
                },
            ]
        },
    )
    atomic_write_json(
        root / "reports" / "merge_report.json",
        {
            "title_id": "CUSA12345",
            "compatibility": "current-smp",
            "extractor_revision": EXTRACTOR_REVISION,
            "latest_app_version": "01.00",
            "merged_tree_signature": tree_stat_signature(app),
            "dlc_mode": "single-experimental",
            "dlc_staged_count": 1,
            "dlc_embedding": {"applied": True} if embedded else None,
            "dlc": [
                {
                    "entitlement_label": "ABCDEFGHIJKLMNOP",
                    "extracted_tree_signature": tree_stat_signature(
                        dlc_manifest
                    ),
                    "extracted_file_count": len(dlc_manifest),
                }
            ],
        },
    )
    return settings, game, root, addcont_label


def test_pre_embed_resume_rejects_missing_dlc_file_even_when_label_remains(
    tmp_path: Path,
) -> None:
    settings, game, _root, addcont_label = _prepare_resumable_experimental_merge(
        tmp_path,
        embedded=False,
    )

    assert _resume_merged_game(settings, game, "CUSA12345") is not None
    (addcont_label / "content.bin").unlink()

    assert _resume_merged_game(settings, game, "CUSA12345") is None


def test_applied_embed_resume_rejects_removed_selected_dlc(
    tmp_path: Path,
) -> None:
    settings, game, _root, _addcont_label = _prepare_resumable_experimental_merge(
        tmp_path,
        embedded=True,
    )
    game["dlc"] = []

    assert _resume_merged_game(settings, game, "CUSA12345") is None


def test_older_extractor_state_discards_only_stale_package_trees(
    tmp_path: Path,
) -> None:
    root = tmp_path / "unpacked" / "CUSA12345 - Synthetic Game"
    package_file = root / "packages" / "base" / "old" / "payload.bin"
    package_file.parent.mkdir(parents=True)
    package_file.write_bytes(b"stale extraction")
    unrelated = root / "merged" / "app" / "eboot.bin"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_bytes(b"keep")
    atomic_write_json(
        root / ".ps4ffpsc-state.json",
        {
            "schema_version": 2,
            "packages": {"old": {"status": "verified"}},
        },
    )

    state = pipeline._load_state(root)

    assert state["schema_version"] == EXTRACTION_STATE_SCHEMA_VERSION
    assert state["extractor_revision"] == EXTRACTOR_REVISION
    assert not (root / "packages").exists()
    assert unrelated.read_bytes() == b"keep"
