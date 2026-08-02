from __future__ import annotations

import os
import struct
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "packaging" / "macos" / "make_icon.py"


def test_macos_icon_generator_writes_complete_icns(tmp_path: Path) -> None:
    output = tmp_path / "AppIcon.icns"
    environment = os.environ.copy()
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    subprocess.run(
        [sys.executable, str(GENERATOR), str(output)],
        check=True,
        cwd=ROOT,
        env=environment,
    )

    data = output.read_bytes()
    assert data[:4] == b"icns"
    assert struct.unpack(">I", data[4:8])[0] == len(data)

    icon_types: list[bytes] = []
    image_sizes: list[tuple[int, int]] = []
    offset = 8
    while offset < len(data):
        icon_type = data[offset : offset + 4]
        chunk_size = struct.unpack(">I", data[offset + 4 : offset + 8])[0]
        assert chunk_size > 8
        assert offset + chunk_size <= len(data)
        image = data[offset + 8 : offset + chunk_size]
        assert image[:8] == b"\x89PNG\r\n\x1a\n"
        assert image[12:16] == b"IHDR"
        icon_types.append(icon_type)
        image_sizes.append(struct.unpack(">II", image[16:24]))
        offset += chunk_size

    assert offset == len(data)
    assert icon_types == [
        b"icp4",
        b"ic11",
        b"icp5",
        b"ic12",
        b"ic07",
        b"ic13",
        b"ic08",
        b"ic14",
        b"ic09",
        b"ic10",
    ]
    assert image_sizes == [
        (16, 16),
        (32, 32),
        (32, 32),
        (64, 64),
        (128, 128),
        (256, 256),
        (256, 256),
        (512, 512),
        (512, 512),
        (1024, 1024),
    ]
