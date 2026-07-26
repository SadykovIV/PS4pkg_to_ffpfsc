from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ps4ffpsc.pipeline import Settings, _verify_image, mkpfs_command
from ps4ffpsc.sfo import build_param_json, make_sfo


@pytest.mark.integration
def test_mkpfs_nested_exfat_build_verify_and_deep_unpack(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    settings = Settings(
        root=root,
        pkg_dir=root / "pkg",
        unpacked_dir=tmp_path / "unpacked",
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "work",
        temp_dir=tmp_path / "work" / "tmp",
    )
    settings.temp_dir.mkdir(parents=True)
    source = tmp_path / "Игра с пробелами"
    (source / "sce_sys").mkdir(parents=True)
    (source / "eboot.bin").write_bytes(b"synthetic eboot")
    (source / "sce_sys" / "param.sfo").write_bytes(
        make_sfo({"TITLE_ID": "CUSA12345", "TITLE": "Тест", "APP_VER": "01.00", "CATEGORY": "gd"})
    )
    (source / "sce_sys" / "param.json").write_bytes(build_param_json("CUSA12345", "Тест"))
    (source / "данные.bin").write_bytes(b"unicode")
    output = tmp_path / "synthetic.ffpfsc.partial"
    mkpfs = mkpfs_command(settings)
    process = subprocess.run(
        [
            *mkpfs,
            "pack",
            "folder",
            "--no-adjust-output-file-extension",
            "--version",
            "PS5",
            "--inode-bits",
            "32",
            str(source),
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    result = _verify_image(settings, output, source, "current-smp")
    assert result["verified"]
    assert result["deep_tree_line_count"] > 3
