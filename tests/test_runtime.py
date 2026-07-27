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


def test_temporary_workspace_is_namespaced_and_not_application_data(
    tmp_path: Path,
) -> None:
    selected_temp = tmp_path / "tmp"

    assert runtime.temporary_workspace(selected_temp) == (
        selected_temp / runtime.APP_SUPPORT_NAME
    ).resolve()


def test_macos_default_temporary_directory_is_tmp(monkeypatch) -> None:
    monkeypatch.setattr(runtime.sys, "platform", "darwin")

    assert runtime.default_temporary_directory() == Path("/tmp")


def test_windows_default_temporary_directory_uses_temp_environment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    windows_temp = tmp_path / "Windows TEMP"
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setenv("TEMP", str(windows_temp))

    assert runtime.default_temporary_directory() == windows_temp.resolve()


def test_maximum_logical_cpu_count_uses_process_available_cpus(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime.os,
        "process_cpu_count",
        lambda: 24,
        raising=False,
    )
    monkeypatch.setattr(runtime.os, "cpu_count", lambda: 4)

    assert runtime.maximum_logical_cpu_count() == 24


def test_maximum_logical_cpu_count_uses_affinity_and_never_returns_zero(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime.os,
        "process_cpu_count",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        runtime.os,
        "sched_getaffinity",
        lambda _pid: {0, 1, 2, 3, 4, 5},
        raising=False,
    )
    assert runtime.maximum_logical_cpu_count() == 6

    monkeypatch.setattr(runtime.os, "sched_getaffinity", lambda _pid: set())
    monkeypatch.setattr(runtime.os, "cpu_count", lambda: None)
    assert runtime.maximum_logical_cpu_count() == 1


def test_application_data_root_does_not_create_heavy_workspace(
    tmp_path: Path,
) -> None:
    runtime.ensure_application_directories(tmp_path)

    assert (tmp_path / "pkg").is_dir()
    assert (tmp_path / "logs").is_dir()
    assert (tmp_path / "output").is_dir()
    assert not (tmp_path / "unpacked").exists()
    assert not (tmp_path / "work").exists()
