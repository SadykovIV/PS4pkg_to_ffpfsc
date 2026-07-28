from __future__ import annotations

import hashlib
import struct
import subprocess
from pathlib import Path

import pytest

from ps4ffpsc.pipeline import (
    Settings,
    _verify_image,
    mkpfs_command,
    mkpfs_compression_arguments,
    verify_artifact,
)
from ps4ffpsc.sfo import build_param_json, make_sfo


def _make_npbind() -> bytes:
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
    return bytes(data)


@pytest.mark.integration
@pytest.mark.parametrize("compression_level", [0, 9])
def test_mkpfs_nested_exfat_build_verify_and_deep_unpack(
    tmp_path: Path,
    compression_level: int,
) -> None:
    root = Path(__file__).resolve().parents[1]
    settings = Settings(
        root=root,
        pkg_dir=root / "pkg",
        unpacked_dir=tmp_path / "unpacked",
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "work",
        temp_dir=tmp_path / "work" / "tmp",
        compression_level=compression_level,
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
            *mkpfs_compression_arguments(settings),
            str(source),
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert f"Zlib level:        {compression_level}" in process.stdout
    result = _verify_image(settings, output, source, "current-smp")
    assert result["verified"]
    assert result["verification_mode"] == "container_and_required_files"
    assert set(result["required_file_sizes"]) == {
        "eboot.bin",
        "sce_sys/param.sfo",
        "sce_sys/param.json",
    }

    # Detection follows the on-disk signature, not a misleading extension.
    misnamed = tmp_path / f"synthetic-{compression_level}.exfat"
    output.replace(misnamed)
    standalone = verify_artifact(settings, misnamed)
    assert standalone["verified"]
    assert standalone["verification_mode"] == "container_and_required_files"


@pytest.mark.integration
def test_raw_exfat_build_verifies_only_required_metadata(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    settings = Settings(
        root=root,
        pkg_dir=root / "pkg",
        unpacked_dir=tmp_path / "unpacked",
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "work",
        temp_dir=tmp_path / "work" / "tmp",
        output_format="exfat",
    )
    settings.temp_dir.mkdir(parents=True)
    source = tmp_path / "raw-exfat-source"
    (source / "sce_sys").mkdir(parents=True)
    (source / "eboot.bin").write_bytes(b"synthetic eboot")
    (source / "sce_sys" / "param.sfo").write_bytes(
        make_sfo(
            {
                "TITLE_ID": "CUSA12345",
                "TITLE": "Raw exFAT",
                "APP_VER": "01.00",
                "CATEGORY": "gd",
            }
        )
    )
    (source / "sce_sys" / "param.json").write_bytes(
        build_param_json("CUSA12345", "Raw exFAT")
    )
    (source / "sce_sys" / "npbind.dat").write_bytes(_make_npbind())
    (source / "large-payload.bin").write_bytes(b"x" * (2 * 1024 * 1024))
    output = tmp_path / "synthetic.exfat.partial"
    mkpfs = mkpfs_command(settings)
    packed = subprocess.run(
        [
            *mkpfs,
            "pack",
            "exfat",
            str(source),
            str(output),
            "--cluster-size",
            "65536",
            "--no-progress",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert packed.returncode == 0, packed.stdout + packed.stderr

    selected = tmp_path / "selected"
    unpacked = subprocess.run(
        [
            *mkpfs,
            "unpack",
            str(output),
            str(selected),
            "--deep",
            "--format",
            "exfat",
            "--no-progress",
            "--only",
            "eboot.bin",
            "--only",
            "sce_sys/param.sfo",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert unpacked.returncode == 0, unpacked.stdout + unpacked.stderr
    assert (selected / "eboot.bin").is_file()
    assert (selected / "sce_sys" / "param.sfo").is_file()
    assert not (selected / "large-payload.bin").exists()

    result = _verify_image(
        settings,
        output,
        source,
        "current-smp",
        image_format="exfat",
    )
    assert result["verified"]
    assert result["verification_mode"] == "exfat_and_required_files"

    original_eboot = (source / "eboot.bin").read_bytes()
    (source / "eboot.bin").write_bytes(b"x" * len(original_eboot))
    with pytest.raises(
        RuntimeError,
        match="required file content mismatch: eboot.bin",
    ):
        _verify_image(
            settings,
            output,
            source,
            "current-smp",
            image_format="exfat",
        )
    (source / "eboot.bin").write_bytes(original_eboot)

    renamed = tmp_path / "synthetic.img"
    output.replace(renamed)
    standalone = verify_artifact(settings, renamed)
    assert standalone["verified"]
    assert standalone["verification_mode"] == "exfat_and_required_files"
    assert standalone["optional_files_validated"] == [
        "sce_sys/npbind.dat"
    ]

    damaged_npbind = bytearray(_make_npbind())
    damaged_npbind[-4:] = b"bad!"
    (source / "sce_sys" / "npbind.dat").write_bytes(damaged_npbind)
    damaged_output = tmp_path / "damaged-npbind.exfat"
    damaged_pack = subprocess.run(
        [
            *mkpfs,
            "pack",
            "exfat",
            str(source),
            str(damaged_output),
            "--cluster-size",
            "65536",
            "--no-progress",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert damaged_pack.returncode == 0, (
        damaged_pack.stdout + damaged_pack.stderr
    )
    with pytest.raises(RuntimeError, match="invalid npbind.dat"):
        verify_artifact(settings, damaged_output)
