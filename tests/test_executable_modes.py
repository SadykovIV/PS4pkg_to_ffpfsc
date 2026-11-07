from pathlib import Path
import os
import stat

import pytest

from ps4ffpsc.executable_modes import normalize_executable_modes


def test_nested_modules_detach_hardlinks_and_preserve_inputs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    originals = {}
    for name, magic in (("eboot.bin", b"\x4f\x15\x3d\x1d"),
                        ("Media/Plugins/SaveData.prx", b"\x4f\x15\x3d\x1d"),
                        ("custom.extension", b"\x7fELF")):
        src, dst = source / name, output / name
        src.parent.mkdir(parents=True, exist_ok=True)
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(magic + b"unchanged executable payload")
        src.chmod(0o644)
        os.link(src, dst)
        originals[name] = src.read_bytes()
    (output / "asset.prx").write_bytes(b"ordinary data despite the extension")
    (output / "asset.prx").chmod(0o644)
    changes = normalize_executable_modes(output)
    assert {item["path"] for item in changes} == set(originals)
    for name, contents in originals.items():
        src, dst = source / name, output / name
        assert stat.S_IMODE(src.stat().st_mode) == 0o644
        assert stat.S_IMODE(dst.stat().st_mode) == 0o755
        assert src.read_bytes() == dst.read_bytes() == contents
        assert src.stat().st_ino != dst.stat().st_ino
    assert stat.S_IMODE((output / "asset.prx").stat().st_mode) == 0o644
    before = {name: (output / name).stat().st_ino for name in originals}
    assert normalize_executable_modes(output) == []
    assert before == {name: (output / name).stat().st_ino for name in originals}


@pytest.mark.parametrize("before,after", [(0o600, 0o700), (0o640, 0o750),
                                          (0o644, 0o755), (0o755, 0o755)])
def test_preserves_access_scope(tmp_path: Path, before: int, after: int) -> None:
    module = tmp_path / "module"
    module.write_bytes(b"\x4f\x15\x3d\x1dcontent")
    module.chmod(before)
    normalize_executable_modes(tmp_path)
    assert stat.S_IMODE(module.stat().st_mode) == after


def test_symlink_input_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.write_bytes(b"\x7fELFdata")
    outside.chmod(0o644)
    root = tmp_path / "output"
    root.mkdir()
    (root / "module").symlink_to(outside)
    with pytest.raises(ValueError):
        normalize_executable_modes(root)
    assert stat.S_IMODE(outside.stat().st_mode) == 0o644
