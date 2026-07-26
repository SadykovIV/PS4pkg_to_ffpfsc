from __future__ import annotations

from pathlib import Path

from ps4ffpsc import runtime


def test_frozen_windows_uses_local_app_data(
    monkeypatch,
    tmp_path: Path,
) -> None:
    local_app_data = tmp_path / "Local"
    monkeypatch.setattr(runtime, "is_frozen", lambda: True)
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.delenv("PS4FFPSC_DATA_ROOT", raising=False)

    assert runtime.application_data_root() == (
        local_app_data / runtime.APP_SUPPORT_NAME
    ).resolve()


def test_frozen_windows_uses_sibling_worker(
    monkeypatch,
    tmp_path: Path,
) -> None:
    gui = tmp_path / "PS4 FFPFSC.exe"
    monkeypatch.setattr(runtime, "is_frozen", lambda: True)
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setattr(runtime.sys, "executable", str(gui))

    assert runtime.worker_executable() == tmp_path / "ps4ffpsc-worker.exe"
