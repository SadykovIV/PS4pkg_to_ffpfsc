from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ps4ffpsc import pipeline
from ps4ffpsc.pipeline import Settings, _resume_merged_game, build_game
from ps4ffpsc.sfo import build_param_json, make_sfo
from ps4ffpsc.util import atomic_write_json, read_json, sha256_file, tree_sha256


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
        base["sha256"] = "a" * 64
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
        return {"latest_app_version": "01.00"}

    def fake_run(
        command: list[str], _log_path: Path
    ) -> subprocess.CompletedProcess[str]:
        Path(command[-1]).write_bytes(b"verified ffpfsc")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pipeline, "_resume_merged_game", lambda *_args: None)
    monkeypatch.setattr(pipeline, "unpack_game", fake_unpack)
    monkeypatch.setattr(pipeline, "merge_game", fake_merge)
    monkeypatch.setattr(pipeline, "check_disk_space", lambda *_args: None)
    monkeypatch.setattr(pipeline, "mkpfs_command", lambda *_args: ["mkpfs"])
    monkeypatch.setattr(pipeline, "_run_logged", fake_run)
    return root


def test_successful_build_removes_only_its_temporary_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / "source.pkg"
    source.write_bytes(b"owned source")
    inventory = _inventory(source)
    root = _prepare_fake_pipeline(monkeypatch, settings, inventory)
    monkeypatch.setattr(
        pipeline,
        "_verify_image",
        lambda *_args, **_kwargs: {"verified": True},
    )

    result = build_game(settings, "CUSA12345", inventory)

    output = Path(result["artifact"])
    assert output.read_bytes() == b"verified ffpfsc"
    assert source.read_bytes() == b"owned source"
    assert not root.exists()
    assert result["temporary_workspace_cleaned"] is True
    assert read_json(output.with_suffix(".manifest.json"))[
        "temporary_workspace_cleaned"
    ] is True


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


def test_verified_merged_workspace_can_resume_without_extracted_packages(
    tmp_path: Path,
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
    source_sha = sha256_file(source)
    atomic_write_json(
        root / "manifest.json",
        {"packages": [{"path": str(source), "sha256": source_sha}]},
    )
    atomic_write_json(
        root / "reports" / "merge_report.json",
        {
            "title_id": "CUSA12345",
            "compatibility": "current-smp",
            "latest_app_version": "01.00",
            "merged_tree_sha256": tree_sha256(app),
        },
    )

    report = _resume_merged_game(settings, game, "CUSA12345")

    assert report is not None
    assert report["latest_app_version"] == "01.00"
    assert game["base"][0]["sha256"] == source_sha
    assert not (root / "packages").exists()
