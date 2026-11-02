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
