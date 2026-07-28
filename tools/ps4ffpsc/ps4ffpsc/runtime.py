from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


APP_SUPPORT_NAME = "PS4 FFPFSC"
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
WINDOWS_JOB_ENVIRONMENT_VARIABLE = "PS4FFPSC_WINDOWS_JOB_NAME"


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


def temporary_workspace(temp_dir: Path) -> Path:
    base = temp_dir.expanduser().resolve()
    if base.name == APP_SUPPORT_NAME:
        return base
    return base / APP_SUPPORT_NAME


def default_temporary_directory() -> Path:
    if sys.platform == "darwin":
        return Path("/tmp")
    if sys.platform == "win32":
        windows_temp = os.environ.get("TEMP")
        if windows_temp:
            return Path(windows_temp).expanduser().resolve()
    return Path(tempfile.gettempdir())


def maximum_logical_cpu_count() -> int:
    process_cpu_count = getattr(os, "process_cpu_count", None)
    count = process_cpu_count() if callable(process_cpu_count) else None
    if count is None:
        get_affinity = getattr(os, "sched_getaffinity", None)
        if callable(get_affinity):
            try:
                count = len(get_affinity(0))
            except OSError:
                count = None
    if count is None:
        count = os.cpu_count()
    return max(1, int(count or 1))


def default_compression_worker_count(maximum: int | None = None) -> int:
    available = maximum_logical_cpu_count() if maximum is None else max(1, int(maximum))
    return max(1, available // 2)


def validate_compression_worker_count(
    value: int | str | None,
    maximum: int | None = None,
) -> int:
    available = maximum_logical_cpu_count() if maximum is None else max(1, int(maximum))
    workers = (
        default_compression_worker_count(available)
        if value is None
        else int(value)
    )
    if not 1 <= workers <= available:
        raise ValueError(
            f"compression workers must be within 1..{available}"
        )
    return workers


def configure_worker_process_group(
    process: Any,
    platform_name: str | None = None,
) -> bool:
    current_platform = platform_name or sys.platform
    if current_platform == "win32" and hasattr(
        process, "setCreateProcessArgumentsModifier"
    ):
        def configure_windows(arguments: Any) -> None:
            arguments.flags |= CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP

        process.setCreateProcessArgumentsModifier(configure_windows)
        return True
    if current_platform != "win32":
        if (
            hasattr(process, "setUnixProcessParameters")
            and hasattr(process, "unixProcessParameters")
            and hasattr(type(process), "UnixProcessFlag")
        ):
            parameters = process.unixProcessParameters()
            parameters.flags |= type(process).UnixProcessFlag.CreateNewSession
            process.setUnixProcessParameters(parameters)
            return True
        if hasattr(process, "setChildProcessModifier"):
            process.setChildProcessModifier(os.setsid)
            return True
    return False


def create_windows_kill_on_close_job(job_name: str) -> int | None:
    if sys.platform != "win32" or not job_name:
        return None
    import ctypes
    from ctypes import wintypes

    class IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimitInformation),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    job = kernel32.CreateJobObjectW(None, job_name)
    if not job:
        return None
    limits = ExtendedLimitInformation()
    limits.BasicLimitInformation.LimitFlags = 0x00002000
    if not kernel32.SetInformationJobObject(
        job,
        9,
        ctypes.byref(limits),
        ctypes.sizeof(limits),
    ):
        kernel32.CloseHandle(job)
        return None
    return int(job)


def join_windows_job_from_environment() -> bool:
    if sys.platform != "win32":
        return True
    job_name = os.environ.get(WINDOWS_JOB_ENVIRONMENT_VARIABLE)
    if not job_name:
        return True
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenJobObjectW.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    kernel32.OpenJobObjectW.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
    ]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.IsProcessInJob.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.BOOL),
    ]
    kernel32.IsProcessInJob.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    job = kernel32.OpenJobObjectW(0x0001 | 0x0004, False, job_name)
    if not job:
        return False
    try:
        current_process = kernel32.GetCurrentProcess()
        already_assigned = wintypes.BOOL()
        if (
            kernel32.IsProcessInJob(
                current_process,
                job,
                ctypes.byref(already_assigned),
            )
            and already_assigned.value
        ):
            return True
        return bool(
            kernel32.AssignProcessToJobObject(
                job,
                current_process,
            )
        )
    finally:
        kernel32.CloseHandle(job)


def windows_process_is_running(process_id: int) -> bool:
    if sys.platform != "win32" or process_id <= 0:
        return False
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    process = kernel32.OpenProcess(0x00100000, False, process_id)
    if not process:
        return False
    try:
        return kernel32.WaitForSingleObject(process, 0) == 0x00000102
    finally:
        kernel32.CloseHandle(process)


def terminate_windows_job(job_handle: int, exit_code: int = 130) -> bool:
    if sys.platform != "win32" or job_handle <= 0:
        return False
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    return bool(kernel32.TerminateJobObject(job_handle, exit_code))


def close_windows_job(job_handle: int | None) -> None:
    if sys.platform != "win32" or not job_handle:
        return
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle(job_handle)


def terminate_process_tree(
    process_id: int,
    *,
    force: bool = True,
    platform_name: str | None = None,
) -> bool:
    if process_id <= 0:
        return False
    current_platform = platform_name or sys.platform
    if current_platform == "win32":
        command = ["taskkill", "/PID", str(process_id), "/T"]
        if force:
            command.append("/F")
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
        )
        return completed.returncode == 0
    try:
        os.killpg(
            process_id,
            signal.SIGKILL if force else signal.SIGTERM,
        )
    except ProcessLookupError:
        return True
    except OSError:
        return False
    return True


def ensure_application_directories(root: Path) -> None:
    for name in ("pkg", "output", "logs"):
        (root / name).mkdir(parents=True, exist_ok=True)
