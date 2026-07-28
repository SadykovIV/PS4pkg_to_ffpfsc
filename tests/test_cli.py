from __future__ import annotations

from pathlib import Path

import pytest

from ps4ffpsc import cli
from ps4ffpsc.pipeline import Settings
from ps4ffpsc.runtime import (
    default_compression_worker_count,
    maximum_logical_cpu_count,
)


def test_build_parser_accepts_full_mkpfs_compression_range(
    tmp_path: Path,
) -> None:
    parser = cli.build_parser()

    args = parser.parse_args(
        ["build", "CUSA12345", "--compression-level", "9"]
    )
    assert args.compression_level == 9

    no_deflate_args = parser.parse_args(
        ["build", "CUSA12345", "--compression-level", "0"]
    )
    settings = Settings.load(tmp_path, no_deflate_args, tmp_path)
    assert settings.compression_level == 0
    assert settings.compression_workers is None


def test_build_parser_accepts_output_format_and_bounded_workers(
    tmp_path: Path,
) -> None:
    parser = cli.build_parser()
    maximum = maximum_logical_cpu_count()
    requested = min(3, maximum)
    args = parser.parse_args(
        [
            "build",
            "CUSA12345",
            "--output-format",
            "exfat",
            "--compression-workers",
            str(requested),
        ]
    )
    settings = Settings.load(tmp_path, args, tmp_path)

    assert settings.output_format == "exfat"
    assert settings.compression_workers == requested
    assert default_compression_worker_count(maximum) >= 1

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "build",
                "CUSA12345",
                "--compression-workers",
                str(maximum + 1),
            ]
        )


def test_build_reuses_inventory_from_initial_scan(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    settings = Settings(
        root=tmp_path,
        pkg_dir=tmp_path / "pkg",
        unpacked_dir=tmp_path / "unpacked",
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "work",
        temp_dir=tmp_path / "tmp",
        json_output=True,
    )
    game = {
        "title_id": "CUSA12345",
        "title": "Test",
        "buildable": True,
        "conflicts": [],
        "warnings": [],
    }
    inventory = {
        "games": {"CUSA12345": game},
        "packages": [],
        "unsupported": [],
    }
    scan_calls: list[bool] = []
    received: list[dict] = []

    monkeypatch.setattr(cli, "_settings", lambda _args: settings)
    monkeypatch.setattr(cli, "configure_logging", lambda _settings: None)

    def load(_settings: Settings, refresh: bool = False) -> dict:
        scan_calls.append(refresh)
        return inventory

    def build(_settings: Settings, title_id: str, scanned: dict) -> dict:
        assert title_id == "CUSA12345"
        received.append(scanned)
        return {"status": "completed"}

    monkeypatch.setattr(cli, "load_or_scan", load)
    monkeypatch.setattr(cli, "build_game", build)

    assert cli.main(["build", "CUSA12345", "--json"]) == 0
    assert scan_calls == [True]
    assert received == [inventory]
    assert '"status": "completed"' in capsys.readouterr().out
