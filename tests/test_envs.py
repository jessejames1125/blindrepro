import subprocess
import sys
import time

import pytest

from blindrepro import envs, sandbox, toolserver


def test_an_install_that_runs_too_long_stops_with_a_clear_message(tmp_path, monkeypatch):
    monkeypatch.setenv("BLINDREPRO_CACHE", str(tmp_path))
    monkeypatch.setattr(envs.shutil, "which", lambda name: None)

    def slow(command, *, env, seconds):
        assert seconds == envs.INSTALL_SECONDS
        return sandbox.RunResult(None, "", "", seconds, timed_out=True)

    monkeypatch.setattr(envs.subprocess, "run", lambda command, **options: subprocess.CompletedProcess(command, 0))
    monkeypatch.setattr(sandbox, "run_tree", slow)
    with pytest.raises(envs.InstallFailed, match="minutes"):
        envs.ensure_env(["some-package==1.0"])
    assert not any((tmp_path / "envs").iterdir())


def test_a_failed_install_says_what_the_installer_said(tmp_path, monkeypatch):
    monkeypatch.setenv("BLINDREPRO_CACHE", str(tmp_path))
    monkeypatch.setattr(envs.shutil, "which", lambda name: None)

    def broken(command, *, env, seconds):
        return sandbox.RunResult(1, "", "no matching distribution for some-package", 0.1)

    monkeypatch.setattr(envs.subprocess, "run", lambda command, **options: subprocess.CompletedProcess(command, 0))
    monkeypatch.setattr(sandbox, "run_tree", broken)
    with pytest.raises(envs.InstallFailed, match="no matching distribution"):
        envs.ensure_env(["some-package==1.0"])


def test_the_run_tool_reports_a_failed_install_to_the_agent(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("some-package\n", encoding="utf-8")

    def fail(requirements):
        raise envs.InstallFailed("Installing the packages took more than 15 minutes, so it was stopped.")

    monkeypatch.setattr(envs, "env_for_requirements", fail)
    result = toolserver.execute({"workspace": str(tmp_path), "python": "python", "script": "adapter.py", "requirements": "requirements.txt"})
    assert result.returncode is None
    assert "15 minutes" in result.stderr


def test_a_file_still_held_by_a_dying_child_does_not_crash_the_run(monkeypatch):
    # On Windows a stopped job's processes exit a moment later, so their output files can still be open.
    real = sandbox.tempfile.TemporaryDirectory
    seen = []

    def recording(*args, **options):
        seen.append(options)
        return real(*args, **options)

    monkeypatch.setattr(sandbox.tempfile, "TemporaryDirectory", recording)
    sandbox.run_tree([sys.executable, "-c", "print(1)"], env=None, seconds=30)
    assert seen and all(options.get("ignore_cleanup_errors") for options in seen)


def test_a_stopped_command_takes_its_child_processes_with_it(tmp_path):
    marker = tmp_path / "child-still-alive.txt"
    child = f"import time, pathlib; time.sleep(4); pathlib.Path({str(marker)!r}).write_text('alive')"
    parent = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(30)"
    result = sandbox.run_tree([sys.executable, "-c", parent], env=None, seconds=1)
    assert result.timed_out
    time.sleep(6)
    assert not marker.exists()
