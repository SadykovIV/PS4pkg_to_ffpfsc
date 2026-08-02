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


def test_build_parser_accepts_canonical_and_legacy_dlc_options() -> None:
    parser = cli.build_parser()

    canonical = parser.parse_args(
        ["build", "CUSA12345", "--dlc-mode", "single-experimental"]
    )
    assert canonical.dlc_mode == "single-experimental"
    assert canonical.include_dlc is None

    legacy = parser.parse_args(
        ["build", "CUSA12345", "--include-dlc", "bundle"]
    )
    assert legacy.dlc_mode is None
    assert legacy.include_dlc == "bundle"

    with pytest.raises(SystemExit):
        parser.parse_args(
            ["build", "CUSA12345", "--dlc-mode", "separate"]
        )


@pytest.mark.parametrize(
    ("arguments", "expected_mode"),
    [
        (["build", "CUSA12345"], "off"),
        (["build", "CUSA12345", "--dlc-mode", "off"], "off"),
        (
            ["build", "CUSA12345", "--dlc-mode", "single-experimental"],
            "single-experimental",
        ),
        (["build", "CUSA12345", "--include-dlc", "off"], "off"),
        (
            ["build", "CUSA12345", "--include-dlc", "bundle"],
            "single-experimental",
        ),
    ],
)
def test_settings_load_maps_canonical_and_legacy_dlc_modes(
    tmp_path: Path,
    arguments: list[str],
    expected_mode: str,
) -> None:
    args = cli.build_parser().parse_args(arguments)

    settings = Settings.load(tmp_path, args, tmp_path)

    assert settings.dlc_mode == expected_mode


def test_legacy_cli_dlc_mode_overrides_canonical_config(
    tmp_path: Path,
) -> None:
    (tmp_path / "ps4ffpsc.toml").write_text(
        '[shadowmount]\ndlc_mode = "off"\n',
        encoding="utf-8",
    )
    args = cli.build_parser().parse_args(
        ["build", "CUSA12345", "--include-dlc", "bundle"]
    )

    settings = Settings.load(tmp_path, args, tmp_path)

    assert settings.dlc_mode == "single-experimental"


@pytest.mark.parametrize("legacy_mode", ["auto", "separate"])
def test_settings_load_rejects_removed_legacy_dlc_modes(
    tmp_path: Path,
    legacy_mode: str,
) -> None:
    args = cli.build_parser().parse_args(
        ["build", "CUSA12345", "--include-dlc", legacy_mode]
    )

    with pytest.raises(ValueError, match="no longer supported"):
        Settings.load(tmp_path, args, tmp_path)


def test_settings_load_rejects_conflicting_dlc_arguments(
    tmp_path: Path,
) -> None:
    args = cli.build_parser().parse_args(
        [
            "build",
            "CUSA12345",
            "--dlc-mode",
            "off",
            "--include-dlc",
            "bundle",
        ]
    )

    with pytest.raises(ValueError, match="cannot be combined"):
        Settings.load(tmp_path, args, tmp_path)


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


def test_cli_accepts_unpacked_game_source_and_rejects_mixed_inputs(
    tmp_path: Path,
) -> None:
    dumped = tmp_path / "CUSA12345"
    dumped.mkdir()
    package = tmp_path / "base.pkg"
    package.write_bytes(b"pkg")
    parser = cli.build_parser()

    args = parser.parse_args(["scan", "--dump-dir", str(dumped)])
    settings = Settings.load(tmp_path, args, tmp_path)
    assert settings.dump_dirs == (dumped.resolve(),)
    assert settings.pkg_files == ()

    mixed = parser.parse_args(
        [
            "scan",
            "--dump-dir",
            str(dumped),
            "--pkg-file",
            str(package),
        ]
    )
    with pytest.raises(ValueError, match="cannot be combined"):
        Settings.load(tmp_path, mixed, tmp_path)


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


@pytest.mark.parametrize("command", ["unpack", "merge"])
def test_cli_stage_commands_rescan_explicit_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    command: str,
) -> None:
    source = tmp_path / "selected.pkg"
    source.write_bytes(b"source")
    settings = Settings(
        root=tmp_path,
        pkg_dir=tmp_path / "pkg",
        unpacked_dir=tmp_path / "unpacked",
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "work",
        temp_dir=tmp_path / "tmp",
        pkg_files=(source,),
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

    monkeypatch.setattr(cli, "_settings", lambda _args: settings)
    monkeypatch.setattr(cli, "configure_logging", lambda _settings: None)

    def load(_settings: Settings, refresh: bool = False) -> dict:
        scan_calls.append(refresh)
        return inventory

    monkeypatch.setattr(cli, "load_or_scan", load)
    if command == "unpack":
        monkeypatch.setattr(
            cli,
            "unpack_game",
            lambda _settings, scanned, title_id: {
                "title_id": title_id,
                "scanned": scanned is inventory,
            },
        )
    else:
        monkeypatch.setattr(
            cli,
            "merge_game",
            lambda _settings, scanned, title_id: {
                "title_id": title_id,
                "scanned": scanned is inventory,
            },
        )

    assert (
        cli.main([command, "CUSA12345", "--pkg-file", str(source), "--json"])
        == 0
    )
    assert scan_calls == [True]


def test_cli_list_uses_effective_same_version_patch_order(capsys) -> None:
    ordinary = {
        "path": "/tmp/z-ordinary.pkg",
        "supported": True,
        "kind": "patch",
        "app_version": "01.10",
        "source_id": "stat-ordinary",
        "patch_role": "ordinary",
    }
    additional = {
        "path": "/tmp/a-Fix5.05.pkg",
        "supported": True,
        "kind": "patch",
        "app_version": "01.10",
        "source_id": "stat-additional",
        "patch_role": "additional_layer",
    }
    inventory = {
        "games": {
            "CUSA12345": {
                "title": "Test",
                "buildable": True,
                "base": [{}],
                "patches": [additional, ordinary],
                "dlc": [],
                "conflicts": [],
                "warnings": [],
            }
        },
        "unsupported": [],
    }

    cli._print_list(inventory, json_output=False)

    output = capsys.readouterr().out
    assert output.index("z-ordinary.pkg") < output.index("a-Fix5.05.pkg")
