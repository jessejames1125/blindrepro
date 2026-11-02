"""Start a guarded Python script with a clean environment, a clock and a memory cap."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

GUARD = Path(__file__).with_name("guard.py")
DEFAULT_SECONDS = 600
DEFAULT_MEMORY_MB = 4096
OUTPUT_LIMIT = 2_000_000
KEEP_ENV = ("SYSTEMROOT", "WINDIR", "PATH", "LANG", "LC_ALL", "TZ", "PATHEXT", "NUMBER_OF_PROCESSORS")


@dataclass
class RunResult:
    returncode: int | None
    stdout: str
    stderr: str
    seconds: float
    timed_out: bool = False
    blocked: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def clean_env(workspace: Path) -> dict[str, str]:
    """Only what Python needs. Keys, tokens and home folders stay out of the script's reach."""
    env = {k: os.environ[k] for k in KEEP_ENV if k in os.environ}
    tmp = workspace / ".tmp"
    tmp.mkdir(exist_ok=True)
    env.update(
        PYTHONIOENCODING="utf-8",
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
        OMP_NUM_THREADS="2",
        OPENBLAS_NUM_THREADS="2",
        MKL_NUM_THREADS="2",
        MPLCONFIGDIR=str(tmp),
        MPLBACKEND="Agg",
        TMP=str(tmp),
        TEMP=str(tmp),
        TMPDIR=str(tmp),
        HOME=str(tmp),
        USERPROFILE=str(tmp),
    )
    return env


def _posix_limit(memory_mb: int):
    def apply() -> None:
        import resource

        limit = memory_mb * 1024 * 1024
        for name in ("RLIMIT_AS",):
            kind = getattr(resource, name, None)
            if kind is None:
                continue
            try:
                resource.setrlimit(kind, (limit, limit))
            except (ValueError, OSError):
                pass  # Mac refuses RLIMIT_AS; the clock still applies.

    return apply


def _windows_job(process: subprocess.Popen, memory_mb: int | None):
    """Cap memory with a job object (unless memory_mb is None), and kill child processes along with the parent."""
    from ctypes import wintypes

    class BASIC(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in ("r", "w", "o", "rb", "wb", "ob")]

    class EXTENDED(ctypes.Structure):
        _fields_ = [
            ("Basic", BASIC),
            ("Io", IO),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    info = EXTENDED()
    job_memory, kill_on_close = 0x200, 0x2000
    info.Basic.LimitFlags = kill_on_close if memory_mb is None else job_memory | kill_on_close
    info.JobMemoryLimit = 0 if memory_mb is None else memory_mb * 1024 * 1024
    extended_limit_class = 9
    kernel.SetInformationJobObject(job, extended_limit_class, ctypes.byref(info), ctypes.sizeof(info))
    kernel.AssignProcessToJobObject(job, int(process._handle))
    return job


def run_guarded(
    python: Path,
    script: Path,
    workspace: Path,
    *,
    read_roots: list[Path] | None = None,
    allow_process: bool = False,
    seconds: int = DEFAULT_SECONDS,
    memory_mb: int = DEFAULT_MEMORY_MB,
) -> RunResult:
    workspace = workspace.resolve()
    (workspace / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="blindrepro-guard-") as scratch:
        log_path = Path(scratch) / "blocked.jsonl"
        policy_path = Path(scratch) / "policy.json"
        policy_path.write_text(
            json.dumps(
                {
                    "write_roots": [str(workspace)],
                    "read_roots": [str(p) for p in (read_roots or [])],
                    "allow_process": allow_process,
                    "log": str(log_path),
                }
            ),
            encoding="utf-8",
        )
        start = time.monotonic()
        # Output goes to files, so a script that prints without end cannot fill this process's
        # memory, and a child that keeps the output open cannot stall the clock.
        out_path, err_path = Path(scratch) / "stdout.txt", Path(scratch) / "stderr.txt"
        with out_path.open("wb") as out_file, err_path.open("wb") as err_file:
            process = subprocess.Popen(
                [str(python), "-I", "-B", str(GUARD), str(policy_path), str(script)],
                cwd=workspace,
                env=clean_env(workspace),
                stdin=subprocess.DEVNULL,
                stdout=out_file,
                stderr=err_file,
                preexec_fn=None if os.name == "nt" else _posix_limit(memory_mb),
                start_new_session=os.name != "nt",
            )
            job = _windows_job(process, memory_mb) if os.name == "nt" else None
            timed_out = False
            try:
                process.wait(timeout=seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                _stop(process)
            if job is not None:
                # Closing the job ends every process the script started.
                ctypes.WinDLL("kernel32").CloseHandle(ctypes.c_void_p(job))
            elif not timed_out:
                _stop(process)
        out, err = _tail(out_path), _tail(err_path)
        blocked = []
        if log_path.exists():
            for line in log_path.read_text(encoding="utf-8").splitlines()[:1000]:
                blocked.append(json.loads(line))
    return RunResult(process.returncode, out, err, time.monotonic() - start, timed_out, blocked)


def run_tree(command: list[str], *, env: dict[str, str] | None, seconds: int) -> RunResult:
    """Run a command with a clock. When the clock runs out, everything it started stops too."""
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="blindrepro-run-") as scratch:
        out_path, err_path = Path(scratch) / "stdout.txt", Path(scratch) / "stderr.txt"
        with out_path.open("wb") as out_file, err_path.open("wb") as err_file:
            process = subprocess.Popen(
                command, env=env, stdin=subprocess.DEVNULL, stdout=out_file, stderr=err_file, start_new_session=os.name != "nt"
            )
            job = _windows_job(process, None) if os.name == "nt" else None
            timed_out = False
            try:
                process.wait(timeout=seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                _stop(process)
            if job is not None:
                ctypes.WinDLL("kernel32").CloseHandle(ctypes.c_void_p(job))
            elif not timed_out:
                _stop(process)
        out, err = _tail(out_path), _tail(err_path)
    return RunResult(process.returncode, out, err, time.monotonic() - start, timed_out)


def _stop(process: subprocess.Popen) -> None:
    """End the script and, on Linux and Mac, anything it started."""
    if os.name != "nt":
        import signal

        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    if process.poll() is None:
        process.kill()
    process.wait()


def _tail(path: Path) -> str:
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > OUTPUT_LIMIT:
            handle.seek(size - OUTPUT_LIMIT)
            prefix = f"[first {size - OUTPUT_LIMIT} bytes of output cut]\n"
        else:
            prefix = ""
        return prefix + handle.read().decode("utf-8", "replace")


def default_python() -> Path:
    return Path(sys.executable)
