import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from blindrepro import toolserver
from blindrepro.judges import ApiJudge, ClaudeCli, JudgeError, make_judge

FAKE_CLAUDE = r"""
import json, os, sys
args = sys.argv[1:]
log = os.environ["FAKE_CLAUDE_LOG"]
if "--version" in args:
    print("9.9.9 (fake)")
    sys.exit(0)
prompt = sys.stdin.read()
with open(log, "w", encoding="utf-8") as handle:
    json.dump({"args": args, "prompt": prompt, "env": sorted(os.environ), "cwd": os.getcwd()}, handle)
mode = os.environ.get("FAKE_CLAUDE_MODE", "ok")
if mode == "crash":
    sys.stderr.write("not signed in")
    sys.exit(1)
print(json.dumps({"type": "system", "subtype": "init", "model": "claude-fake-1", "tools": ["Read", "Write"], "claude_code_version": "9.9.9"}))
print("not json")
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}}))
print(json.dumps({"type": "result", "result": "done", "permission_denials": [{"tool_name": "WebFetch"}]}))
"""


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    script = tmp_path / "fake_claude.py"
    script.write_text(FAKE_CLAUDE, encoding="utf-8")
    if os.name == "nt":
        command = tmp_path / "claude.cmd"
        command.write_text(f'@"{sys.executable}" "{script}" %*\n', encoding="utf-8")
    else:
        command = tmp_path / "claude"
        command.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        command.chmod(0o755)
    log = tmp_path / "log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    return str(command), log


def test_claude_command_is_locked_down(tmp_path, fake_claude, monkeypatch):
    command, log = fake_claude
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setenv("CLAUDECODE", "1")
    session = ClaudeCli(command=command).session("task", tmp_path / "work", ["Read", "Write"], None)
    seen = json.loads(log.read_text(encoding="utf-8"))
    args = seen["args"]
    assert "--restricted" in args
    assert "--strict-mcp-config" in args
    assert "--no-session-persistence" in args
    assert args[args.index("--tools") + 1] == "Read,Write"
    assert args[args.index("--permission-mode") + 1] == "dontAsk"
    assert "--dangerously-skip-permissions" not in args
    assert seen["prompt"] == "task"
    assert "ANTHROPIC_API_KEY" not in seen["env"]
    assert "CLAUDECODE" not in seen["env"]
    assert session.text == "done"
    assert session.model == "claude-fake-1"
    assert session.refused == ["WebFetch"]


def test_claude_command_gets_the_run_tool_only_when_given(tmp_path, fake_claude):
    command, log = fake_claude
    config = {"workspace": str(tmp_path), "python": sys.executable, "script": "d.py", "description": "run", "log": "x"}
    ClaudeCli(command=command).session("task", tmp_path / "work", ["Read"], config)
    args = json.loads(log.read_text(encoding="utf-8"))["args"]
    assert "--mcp-config" in args
    assert "mcp__blindrepro__run" in args[args.index("--allowedTools") + 1]


def test_claude_failure_is_a_clear_error(tmp_path, fake_claude, monkeypatch):
    command, _ = fake_claude
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "crash")
    with pytest.raises(JudgeError, match="not signed in"):
        ClaudeCli(command=command).session("task", tmp_path / "work", [], None)


def test_missing_claude_is_a_clear_error(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(JudgeError, match="not found"):
        ClaudeCli()


def test_api_judge_needs_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(JudgeError, match="ANTHROPIC_API_KEY"):
        make_judge("api", None)


def test_unknown_judge_is_a_clear_error():
    with pytest.raises(JudgeError, match="Unknown judge"):
        make_judge("nope", None)


class FakeApi(BaseHTTPRequestHandler):
    replies: list = []
    requests: list = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        FakeApi.requests.append({"body": body, "key": self.headers.get("x-api-key"), "version": self.headers.get("anthropic-version")})
        reply = FakeApi.replies.pop(0)
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_api(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    FakeApi.requests = []
    server = HTTPServer(("127.0.0.1", 0), FakeApi)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/v1/messages"
    server.shutdown()


def tool_use(identity, name, **inputs):
    return {"content": [{"type": "tool_use", "id": identity, "name": name, "input": inputs}]}


def test_api_judge_runs_the_tool_loop_inside_the_work_folder(tmp_path, fake_api):
    work = tmp_path / "work"
    work.mkdir()
    (work / "paper.txt").write_text("line one\nline two\n", encoding="utf-8")
    FakeApi.replies = [
        tool_use("a", "read_file", path="paper.txt", offset=2),
        tool_use("b", "write_file", path="derive.py", content='print("{}")'),
        tool_use("c", "read_file", path="../secret.txt"),
        {"content": [{"type": "text", "text": "finished"}]},
    ]
    session = ApiJudge(url=fake_api).session("task", work, ["Read", "Write"], None)
    assert session.text == "finished"
    assert (work / "derive.py").exists()
    first_results = FakeApi.requests[1]["body"]["messages"][-1]["content"]
    assert first_results[0]["content"] == "2\tline two"
    blocked = FakeApi.requests[3]["body"]["messages"][-1]["content"][0]
    assert blocked["is_error"] is True
    assert "outside" in blocked["content"]
    assert FakeApi.requests[0]["key"] == "not-a-real-key"
    assert FakeApi.requests[0]["version"] == "2023-06-01"
    assert FakeApi.requests[0]["body"]["model"] == "claude-opus-5-5"


def test_api_judge_offers_no_tools_for_the_memory_check(tmp_path, fake_api):
    FakeApi.replies = [{"content": [{"type": "text", "text": "{}"}]}]
    ApiJudge(url=fake_api).session("task", tmp_path / "work", [], None)
    assert "tools" not in FakeApi.requests[0]["body"]


def test_api_judge_run_tool_goes_through_the_guard(tmp_path, fake_api):
    work = tmp_path / "work"
    work.mkdir()
    (work / "derive.py").write_text("import socket\nsocket.getaddrinfo('example.com', 80)\n", encoding="utf-8")
    config = {
        "workspace": str(work),
        "python": sys.executable,
        "script": "derive.py",
        "description": "run",
        "log": str(tmp_path / "runs.jsonl"),
        "seconds": 30,
    }
    FakeApi.replies = [tool_use("a", "run"), {"content": [{"type": "text", "text": "ok"}]}]
    ApiJudge(url=fake_api).session("task", work, ["Read"], config)
    output = FakeApi.requests[1]["body"]["messages"][-1]["content"][0]["content"]
    assert "blocked: network" in output
    assert "exit code: 1" in output


def test_run_tool_server_answers_the_protocol(tmp_path):
    (tmp_path / "derive.py").write_text("print(41 + 1)\n", encoding="utf-8")
    config = {
        "workspace": str(tmp_path),
        "python": sys.executable,
        "script": "derive.py",
        "description": "run it",
        "log": str(tmp_path / "runs.jsonl"),
        "seconds": 30,
    }
    start = toolserver.answer({"id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}, config)
    assert start["result"]["protocolVersion"] == "2025-06-18"
    listing = toolserver.answer({"id": 2, "method": "tools/list"}, config)
    assert [t["name"] for t in listing["result"]["tools"]] == ["run"]
    called = toolserver.answer({"id": 3, "method": "tools/call", "params": {"name": "run"}}, config)
    assert "42" in called["result"]["content"][0]["text"]
    assert json.loads((tmp_path / "runs.jsonl").read_text(encoding="utf-8"))["exit"] == 0
    assert toolserver.answer({"method": "notifications/initialized"}, config) is None
    assert "error" in toolserver.answer({"id": 4, "method": "nope"}, config)


def test_run_tool_cuts_very_long_output():
    assert len(toolserver.tail("x" * 100000)) < 21000
