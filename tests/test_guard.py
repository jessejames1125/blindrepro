import json
import sys
from pathlib import Path

import pytest

from blindrepro.sandbox import run_guarded


def run(tmp_path, body, **options):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    script = work / "s.py"
    script.write_text(body, encoding="utf-8")
    return run_guarded(Path(sys.executable), script, work, seconds=options.pop("seconds", 30), **options)


def attempt(code):
    return f"try:\n    {code}\n    print('ALLOWED')\nexcept PermissionError as e:\n    print('BLOCKED', e)\n"


@pytest.mark.parametrize(
    "code, kind",
    [
        ("import socket; socket.create_connection(('example.com', 80), timeout=2)", "network"),
        ("import socket; socket.getaddrinfo('example.com', 80)", "network"),
        ("import urllib.request; urllib.request.urlopen('https://example.com', timeout=2)", "network"),
        ("import subprocess; subprocess.run(['python', '--version'])", "process"),
        ("import os; os.system('echo hi')", "process"),
    ],
)
def test_blocks_network_and_processes(tmp_path, code, kind):
    result = run(tmp_path, attempt(code))
    assert "BLOCKED" in result.stdout
    assert "ALLOWED" not in result.stdout
    assert result.blocked[0]["blocked"] == kind


def test_blocks_reading_a_file_outside_the_work_folder(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    result = run(tmp_path, attempt(f"open({str(outside)!r}).read()"))
    assert "BLOCKED" in result.stdout
    assert result.blocked[0]["blocked"] == "file read"


def test_blocks_listing_a_folder_outside_the_work_folder(tmp_path):
    result = run(tmp_path, attempt(f"import os; os.listdir({str(tmp_path)!r})"))
    assert "BLOCKED" in result.stdout


def test_blocks_writing_outside_the_work_folder(tmp_path):
    outside = tmp_path / "written.txt"
    result = run(tmp_path, attempt(f"open({str(outside)!r}, 'w').write('x')"))
    assert "BLOCKED" in result.stdout
    assert not outside.exists()


def test_allows_files_inside_the_work_folder(tmp_path):
    result = run(tmp_path, "open('a.txt', 'w').write('x')\nprint(open('a.txt').read())\n")
    assert result.ok
    assert result.stdout.strip() == "x"
    assert result.blocked == []


def test_keeps_keys_out_of_the_script(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setenv("GITHUB_TOKEN", "not-a-real-token")
    result = run(tmp_path, "import os\nprint(sorted(os.environ))\n")
    assert "ANTHROPIC_API_KEY" not in result.stdout
    assert "GITHUB_TOKEN" not in result.stdout


def test_stops_a_script_past_the_time_limit(tmp_path):
    result = run(tmp_path, "import time\ntime.sleep(30)\n", seconds=1)
    assert result.timed_out
    assert not result.ok


def test_stops_a_script_past_the_memory_limit(tmp_path):
    if sys.platform == "darwin":
        pytest.skip("Mac refuses the address-space limit; the clock still applies there")
    body = "x = bytearray(400 * 1024 * 1024)\nprint(len(x))\n"
    result = run(tmp_path, body, memory_mb=120)
    assert not result.ok


def test_authors_mode_allows_processes_but_not_network(tmp_path):
    body = (
        "import subprocess, sys\n"
        "print(subprocess.run([sys.executable, '-c', 'print(7)'], capture_output=True, text=True).stdout)\n"
        + attempt("import socket; socket.getaddrinfo('example.com', 80)")
    )
    result = run(tmp_path, body, allow_process=True)
    assert "7" in result.stdout
    assert "BLOCKED" in result.stdout


def test_blocked_log_is_valid_json(tmp_path):
    result = run(tmp_path, attempt("import socket; socket.gethostbyname('example.com')"))
    assert json.loads(json.dumps(result.blocked))[0]["detail"]


def test_blocks_hard_links_to_outside_files(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    result = run(tmp_path, attempt(f"import os; os.link({str(outside)!r}, 'inside.txt'); print(open('inside.txt').read())"))
    assert "BLOCKED" in result.stdout
    assert "secret" not in result.stdout


def test_blocks_symlinks(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    result = run(tmp_path, attempt(f"import os; os.symlink({str(outside)!r}, 'inside.txt')"))
    assert "BLOCKED" in result.stdout


def test_blocks_moving_outside_files_in(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    result = run(tmp_path, attempt(f"import os; os.rename({str(outside)!r}, 'inside.txt')"))
    assert "BLOCKED" in result.stdout
    assert outside.exists()


def test_blocks_foreign_calls_through_ctypes(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    if sys.platform == "win32":
        code = f"import ctypes; print(ctypes.WinDLL('kernel32').CreateFileW({str(outside)!r}, 0x80000000, 1, None, 3, 0, None))"
    else:
        code = f"import ctypes; print(ctypes.CDLL(None).open({str(outside).encode()!r}, 0))"
    result = run(tmp_path, attempt(code))
    assert "BLOCKED" in result.stdout
    assert "ALLOWED" not in result.stdout


def test_blocks_foreign_calls_through_pythonapi(tmp_path):
    code = "import ctypes; ctypes.pythonapi.Py_GetVersion()"
    result = run(tmp_path, attempt(code))
    assert "BLOCKED" in result.stdout


def test_blocks_sqlite_reading_outside_files(tmp_path):
    outside = tmp_path / "outside.db"
    result = run(tmp_path, attempt(f"import sqlite3; sqlite3.connect({str(outside)!r})"))
    assert "BLOCKED" in result.stdout


def test_blocks_process_functions_with_no_audit_event(tmp_path):
    if sys.platform == "win32":
        code = "import _winapi; _winapi.CreateProcess(None, 'cmd /c echo hi', None, None, False, 0, None, None, None)"
    else:
        code = "import _posixsubprocess; _posixsubprocess.fork_exec()"
    result = run(tmp_path, attempt(code))
    assert "BLOCKED" in result.stdout
    assert "ALLOWED" not in result.stdout


def test_blocks_native_modules_from_the_work_folder(tmp_path):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    name = "fake.pyd" if sys.platform == "win32" else "fake.so"
    (work / name).write_bytes(b"not really a module")
    body = (
        "import importlib.machinery, importlib.util\n"
        f"loader = importlib.machinery.ExtensionFileLoader('fake', {name!r})\n"
        "spec = importlib.util.spec_from_loader('fake', loader)\n"
        "try:\n    loader.create_module(spec)\nexcept PermissionError as e:\n    print('BLOCKED', e)\nexcept Exception as e:\n    print('REACHED', e)\n"
    )
    result = run(tmp_path, body)
    assert "BLOCKED" in result.stdout


def test_authors_mode_is_not_strict(tmp_path):
    code = "import ctypes; ctypes.pythonapi.Py_GetVersion"
    result = run(tmp_path, attempt(code), allow_process=True)
    assert "ALLOWED" in result.stdout


def test_system_facts_are_read_before_the_guard_starts(tmp_path):
    """A busy Windows system query makes platform fall back to starting a process, which the guard logs."""
    result = run(tmp_path, "import platform\nprint(platform._uname_cache is not None)\nprint(platform.machine() != '')\n")
    assert result.stdout.split() == ["True", "True"]
    assert result.blocked == []


def test_real_numeric_packages_work_under_the_strict_guard(tmp_path):
    """Builds the actual environment, so this needs the network once."""
    from blindrepro.envs import BLIND_PACKAGES, ensure_env

    work = tmp_path / "work"
    work.mkdir()
    script = work / "s.py"
    script.write_text(
        "import numpy as np, scipy, scipy.linalg, scipy.integrate, scipy.optimize, scipy.special, scipy.sparse, scipy.stats\n"
        "import sympy, mpmath\n"
        "a = np.random.default_rng(1).normal(size=(30, 30))\n"
        "print(float(np.linalg.norm(scipy.linalg.eigvals(a + a.T)[0])) > 0)\n"
        "print(round(scipy.integrate.quad(lambda x: x * x, 0, 1)[0], 6))\n"
        "print(round(scipy.optimize.brentq(lambda x: x * x - 2, 0, 2), 6))\n"
        "print(scipy.special.gamma(5))\n"
        "print(sympy.integrate(sympy.Symbol('x') ** 2, (sympy.Symbol('x'), 0, 1)))\n"
        "print(mpmath.mp.pi)\n",
        encoding="utf-8",
    )
    result = run_guarded(ensure_env(BLIND_PACKAGES), script, work, seconds=180)
    assert result.ok, result.stderr[-2000:]
    assert result.blocked == [], result.blocked
    assert "0.333333" in result.stdout
    assert "1.414214" in result.stdout
