"""Restore execute permission for SELF/ELF files in a staged game tree."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Any

from .util import iter_tree_files

_EXECUTABLE_MAGIC = (b"\x4f\x15\x3d\x1d", b"\x7fELF")


def normalize_executable_modes(root: Path) -> list[dict[str, Any]]:
    """Add execute bits corresponding to existing read bits, by file signature.

    Extraction and transfers can leave game modules at 0644. Folder launches
    require execute permission on both eboot and dynamically loaded modules.
    Stage a new inode before chmod: merge outputs can hardlink unpacked inputs.
    File contents and access granted to other users are preserved.
    """
    changes: list[dict[str, Any]] = []
    # Materialize before creating temporary files in the traversed tree.
    files = sorted(iter_tree_files(root), key=lambda item: item[0].as_posix())
    for relative, path in files:
        with path.open("rb") as stream:
            if stream.read(4) not in _EXECUTABLE_MAGIC:
                continue
        mode = stat.S_IMODE(path.stat().st_mode)
        desired = mode | ((mode & 0o444) >> 2)
        if mode == desired:
            continue
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.mode-", dir=path.parent)
        temporary = Path(name)
        os.close(fd)
        try:
            shutil.copy2(path, temporary, follow_symlinks=False)
            temporary.chmod(desired)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        changes.append({"path": relative.as_posix(),
                        "before": f"{mode:04o}", "after": f"{desired:04o}"})
    return changes
