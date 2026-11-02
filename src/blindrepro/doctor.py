"""Say what is present and what is missing, with the fix for each."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__
from .judges import _env_for_claude
from .sandbox import run_guarded

GUARD_TEST = """
import socket, subprocess, urllib.request
for name, attempt in (
    ("network", lambda: socket.create_connection(("example.com", 80), timeout=2)),
    ("process", lambda: subprocess.run(["python", "--version"])),
    ("outside file", lambda: open(OUTSIDE)),
):
    try:
        attempt()
        print(name, "ALLOWED")
    except PermissionError:
        print(name, "blocked")
"""


def check_guard() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="blindrepro-doctor-") as scratch:
        work = Path(scratch) / "work"
        work.mkdir()
        outside = Path(scratch) / "outside.txt"
        outside.write_text("x", encoding="utf-8")
        script = work / "test.py"
        script.write_text(f"OUTSIDE = {str(outside)!r}\n{GUARD_TEST}", encoding="utf-8")
        result = run_guarded(Path(sys.executable), script, work, seconds=30)
    allowed = "ALLOWED" in result.stdout
    if result.returncode != 0 or allowed:
        return False, (result.stdout + result.stderr).strip()[-300:]
    return True, "network, other processes and outside files are blocked"


def check_claude() -> tuple[bool, str]:
    command = shutil.which("claude")
    if not command:
        return False, "not found. Install Claude Code, or use --judge api with your own key."
    env = _env_for_claude()
    version = subprocess.run([command, "--version"], capture_output=True, text=True, env=env).stdout.strip()
    done = subprocess.run([command, "auth", "status"], capture_output=True, text=True, env=env)
    signed_in = False
    try:
        signed_in = bool(json.loads(done.stdout).get("loggedIn"))
    except (json.JSONDecodeError, AttributeError):
        pass
    if not signed_in:
        return False, f"{version} found, but not signed in. Run: claude auth login"
    return True, f"{version}, signed in"


def check_network() -> tuple[bool, str]:
    try:
        socket.create_connection(("arxiv.org", 443), timeout=5).close()
        return True, "arxiv.org reachable"
    except OSError as error:
        return False, f"arxiv.org not reachable ({error}). Local paper files and the demo's rerun still work once packages are cached."


def run() -> int:
    rows: list[tuple[str, bool, str, bool]] = []
    version_ok = sys.version_info >= (3, 10)
    rows.append(("python", version_ok, sys.version.split()[0], True))
    git = shutil.which("git")
    rows.append(("git", bool(git), git and "found" or "not found. Install git to fetch authors' code.", True))
    uv = shutil.which("uv")
    rows.append(("uv", bool(uv), "found" if uv else "not found. Falling back to venv and pip, which is slower.", False))
    rows.append(("guard", *check_guard(), True))
    rows.append(("network", *check_network(), False))
    claude_ok, claude_note = check_claude()
    key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    rows.append(("claude judge", claude_ok, claude_note, False))
    rows.append(("api judge", key, "ANTHROPIC_API_KEY is set" if key else "ANTHROPIC_API_KEY not set. Needed only for --judge api.", False))
    print(f"blindrepro {__version__}")
    for name, ok, note, _required in rows:
        print(f"{'ok ' if ok else 'no '} {name:<13}{note}")
    required_missing = any(not ok and required for _n, ok, _t, required in rows)
    live_ready = claude_ok or key
    print()
    print("Demo: ready." if not required_missing else "Demo: fix the required items above first.")
    print("Live runs: ready." if live_ready and not required_missing else "Live runs: need the claude command or an API key.")
    return 1 if required_missing else 0
