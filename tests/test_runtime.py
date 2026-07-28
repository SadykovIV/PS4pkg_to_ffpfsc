from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QProcess, QProcessEnvironment

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


@pytest.mark.parametrize(
    ("maximum", "expected"),
    [(1, 1), (2, 1), (7, 3), (8, 4), (24, 12)],
)
def test_default_compression_workers_use_half_logical_cpus(
    maximum: int,
    expected: int,
) -> None:
    assert runtime.default_compression_worker_count(maximum) == expected


def test_compression_worker_validation_enforces_available_range() -> None:
    assert runtime.validate_compression_worker_count(None, 10) == 5
    assert runtime.validate_compression_worker_count(1, 10) == 1
    assert runtime.validate_compression_worker_count(10, 10) == 10
    with pytest.raises(ValueError, match=r"1\.\.10"):
        runtime.validate_compression_worker_count(0, 10)
    with pytest.raises(ValueError, match=r"1\.\.10"):
        runtime.validate_compression_worker_count(11, 10)


def test_worker_process_group_configuration_is_platform_specific(
    monkeypatch,
) -> None:
    class FakeProcess:
        child_modifier = None
        windows_modifier = None

        def setChildProcessModifier(self, modifier) -> None:
            self.child_modifier = modifier

        def setCreateProcessArgumentsModifier(self, modifier) -> None:
            self.windows_modifier = modifier

    fake_setsid = lambda: None
    monkeypatch.setattr(
        runtime.os,
        "setsid",
        fake_setsid,
        raising=False,
    )
    posix_process = FakeProcess()
    assert runtime.configure_worker_process_group(
        posix_process,
        "darwin",
    )
    assert posix_process.child_modifier is fake_setsid

    windows_process = FakeProcess()
    assert runtime.configure_worker_process_group(
        windows_process,
        "win32",
    )

    class Arguments:
        flags = 0

    arguments = Arguments()
    windows_process.windows_modifier(arguments)
    assert arguments.flags & runtime.CREATE_NO_WINDOW
    assert arguments.flags & runtime.CREATE_NEW_PROCESS_GROUP


def test_posix_tree_termination_targets_the_worker_process_group(
    monkeypatch,
) -> None:
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        runtime.os,
        "killpg",
        lambda process_id, selected_signal: calls.append(
            (process_id, selected_signal)
        ),
        raising=False,
    )

    assert runtime.terminate_process_tree(
        1234,
        force=False,
        platform_name="darwin",
    )
    assert calls == [(1234, runtime.signal.SIGTERM)]


def test_process_tree_cancellation_stops_worker_and_child() -> None:
    process = QProcess()
    process_group_configured = runtime.configure_worker_process_group(process)
    if sys.platform != "win32" and not process_group_configured:
        pytest.skip("QProcess process-group support is unavailable")
    job_handle = None
    if sys.platform == "win32":
        job_name = f"PS4FFPSC-test-{os.getpid()}-{time.time_ns()}"
        job_handle = runtime.create_windows_kill_on_close_job(job_name)
        assert job_handle is not None
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert(
            runtime.WINDOWS_JOB_ENVIRONMENT_VARIABLE,
            job_name,
        )
        package_root = (
            Path(__file__).resolve().parents[1] / "tools" / "ps4ffpsc"
        )
        previous_python_path = environment.value("PYTHONPATH")
        environment.insert(
            "PYTHONPATH",
            str(package_root)
            + (
                os.pathsep + previous_python_path
                if previous_python_path
                else ""
            ),
        )
        process.setProcessEnvironment(environment)
    child_code = (
        "import subprocess,sys,time;"
        + (
            "from ps4ffpsc.runtime import join_windows_job_from_environment;"
            "assert join_windows_job_from_environment();"
            if sys.platform == "win32"
            else ""
        )
        + "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
        "print(child.pid,flush=True);"
        "time.sleep(60)"
    )
    process.setProgram(sys.executable)
    process.setArguments(["-c", child_code])
    process.start()
    assert process.waitForStarted(5000)
    worker_pid = int(process.processId())
    assert process.waitForReadyRead(5000)
    child_pid = int(bytes(process.readAllStandardOutput()).decode().strip())

    try:
        if sys.platform == "win32":
            assert job_handle is not None
            assert runtime.terminate_windows_job(job_handle)
        else:
            assert runtime.terminate_process_tree(worker_pid, force=True)
        assert process.waitForFinished(5000)

        deadline = time.monotonic() + 3
        child_alive = True
        while time.monotonic() < deadline:
            if sys.platform == "win32":
                child_alive = runtime.windows_process_is_running(child_pid)
            else:
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    child_alive = False
            if not child_alive:
                break
            time.sleep(0.05)
        assert not child_alive
    finally:
        runtime.close_windows_job(job_handle)
        if process.state() != QProcess.ProcessState.NotRunning:
            process.kill()
            process.waitForFinished(2000)
        if sys.platform != "win32":
            try:
                os.kill(child_pid, signal.SIGKILL)
            except (OSError, UnboundLocalError):
                pass
