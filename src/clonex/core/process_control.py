"""Process control helpers for background git execution and shutdown."""

import platform
import subprocess
import threading
from typing import Any, Dict, Set


IS_WINDOWS = platform.system() == "Windows"

_active_processes: Set[subprocess.Popen] = set()
_active_processes_lock = threading.Lock()
_shutdown_event = threading.Event()


def background_subprocess_kwargs() -> Dict[str, Any]:
    """Return subprocess kwargs that hide console windows on Windows."""
    if not IS_WINDOWS:
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def start_tracked_process(command, **kwargs) -> subprocess.Popen:
    """Start a subprocess in background mode and track it for shutdown cleanup."""
    popen_kwargs = dict(kwargs)
    for key, value in background_subprocess_kwargs().items():
        popen_kwargs.setdefault(key, value)

    process = subprocess.Popen(command, **popen_kwargs)
    with _active_processes_lock:
        _active_processes.add(process)
    return process


def untrack_process(process: subprocess.Popen) -> None:
    """Remove process from tracked set."""
    with _active_processes_lock:
        _active_processes.discard(process)


def terminate_process(process: subprocess.Popen, timeout: float = 2.0) -> None:
    """Terminate a process (and children on Windows) best-effort."""
    if process.poll() is not None:
        return

    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                **background_subprocess_kwargs(),
            )
        else:
            process.terminate()
    except Exception:
        pass

    try:
        process.wait(timeout=timeout)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def terminate_all_tracked_processes() -> None:
    """Terminate all tracked subprocesses best-effort."""
    with _active_processes_lock:
        processes = list(_active_processes)

    for process in processes:
        terminate_process(process)
        untrack_process(process)


def request_shutdown() -> None:
    """Signal shutdown and terminate running tracked subprocesses."""
    _shutdown_event.set()
    terminate_all_tracked_processes()


def clear_shutdown_request() -> None:
    """Clear shutdown signal before a new run."""
    _shutdown_event.clear()


def is_shutdown_requested() -> bool:
    """Whether app requested background task shutdown."""
    return _shutdown_event.is_set()

