from __future__ import annotations

import os
import sys
from pathlib import Path


APP_SUPPORT_NAME = "PS4 FFPFSC"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def source_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resource_root() -> Path:
    override = os.environ.get("PS4FFPSC_RESOURCE_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle).resolve()
    return source_project_root()


def application_data_root() -> Path:
    override = os.environ.get("PS4FFPSC_DATA_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if is_frozen() and sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / APP_SUPPORT_NAME).resolve()
    if is_frozen() and sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        parent = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return (parent / APP_SUPPORT_NAME).resolve()
    return source_project_root()


def worker_executable() -> Path:
    executable = Path(sys.executable)
    if is_frozen() and sys.platform == "win32":
        return executable.with_name("ps4ffpsc-worker.exe")
    return executable


def ensure_application_directories(root: Path) -> None:
    for name in ("pkg", "unpacked", "output", "work", "logs"):
        (root / name).mkdir(parents=True, exist_ok=True)
