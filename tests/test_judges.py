import json
import os
import sys
import threading
import time
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
if mode == "hang":
    import subprocess, time
    marker = os.environ["FAKE_CLAUDE_MARKER"]
    child = f"import time, pathlib; time.sleep(4); pathlib.Path({marker!r}).write_text('alive')"
    subprocess.Popen([sys.executable, "-c", child])
    print(json.dumps({"type": "system", "subtype": "init", "model": "claude-fake-1", "tools": []}), flush=True)
    time.sleep(60)
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


def test_claude_that_runs_out_of_time_stops_with_everything_it_started(tmp_path, fake_claude, monkeypatch):
    command, _ = fake_claude
    marker = tmp_path / "tool-still-running.txt"
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "hang")
    monkeypatch.setenv("FAKE_CLAUDE_MARKER", str(marker))
    with pytest.raises(JudgeError, match="stopped after"):
        ClaudeCli(command=command).session("task", tmp_path / "work", [], None, minutes=0.03)
    time.sleep(6)
    assert not marker.exists()


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


def sse(reply):
    """A reply as the event stream the real API sends, so the SDK's own parser runs on it."""
    message = {
        "id": "msg_fake",
        "type": "message",
        "role": "assistant",
        "model": reply.get("model", "claude-opus-5-5"),
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    events = [("message_start", {"type": "message_start", "message": message})]
    for index, block in enumerate(reply["content"]):
        if block["type"] == "text":
            start, delta = {"type": "text", "text": ""}, {"type": "text_delta", "text": block["text"]}
        elif block["type"] == "tool_use":
            start = {"type": "tool_use", "id": block["id"], "name": block["name"], "input": {}}
            delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
        else:
            start = {"type": "thinking", "thinking": "", "signature": ""}
            delta = {"type": "thinking_delta", "thinking": block["thinking"]}
        events.append(("content_block_start", {"type": "content_block_start", "index": index, "content_block": start}))
        events.append(("content_block_delta", {"type": "content_block_delta", "index": index, "delta": delta}))
        if block["type"] == "thinking":
            signature = {"type": "signature_delta", "signature": block["signature"]}
            events.append(("content_block_delta", {"type": "content_block_delta", "index": index, "delta": signature}))
        events.append(("content_block_stop", {"type": "content_block_stop", "index": index}))
    stop = reply.get("stop_reason") or ("tool_use" if any(b["type"] == "tool_use" for b in reply["content"]) else "end_turn")
    delta = {"stop_reason": stop, "stop_sequence": None}
    if "stop_details" in reply:
        delta["stop_details"] = reply["stop_details"]
    events.append(("message_delta", {"type": "message_delta", "delta": delta, "usage": {"output_tokens": 1}}))
    events.append(("message_stop", {"type": "message_stop"}))
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events).encode()


class FakeApi(BaseHTTPRequestHandler):
    replies: list = []
    requests: list = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        FakeApi.requests.append({"body": body, "key": self.headers.get("authorization"), "path": self.path})
        reply = FakeApi.replies.pop(0)
        if isinstance(reply, int):
            data = json.dumps({"type": "error", "error": {"type": "overloaded_error", "message": "busy"}}).encode()
            self.send_response(reply)
            self.send_header("content-type", "application/json")
        else:
            data = sse(reply)
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
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
    yield f"http://127.0.0.1:{server.server_port}"
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
    assert FakeApi.requests[0]["key"] == "Bearer not-a-real-key"
    assert FakeApi.requests[0]["path"] == "/v1/messages"
    assert FakeApi.requests[0]["body"]["model"] == "claude-opus-5-5"
    assert FakeApi.requests[0]["body"]["output_config"] == {"effort": "high"}


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


def test_api_judge_runs_no_tools_from_a_reply_cut_off_at_the_limit(tmp_path, fake_api):
    work = tmp_path / "work"
    FakeApi.replies = [{**tool_use("a", "write_file", path="derive.py", content="print("), "stop_reason": "max_tokens"}]
    with pytest.raises(JudgeError, match="limit of"):
        ApiJudge(url=fake_api).session("task", work, ["Write"], None)
    assert not (work / "derive.py").exists()


def test_api_judge_runs_no_tools_from_a_refused_reply(tmp_path, fake_api):
    work = tmp_path / "work"
    FakeApi.replies = [
        {
            **tool_use("a", "write_file", path="derive.py", content="x"),
            "stop_reason": "refusal",
            "stop_details": {"type": "refusal", "category": "bio", "explanation": "no"},
        }
    ]
    with pytest.raises(JudgeError, match="declined this step \\(category: bio\\)"):
        ApiJudge(url=fake_api).session("task", work, ["Write"], None)
    assert not (work / "derive.py").exists()


def test_api_judge_resumes_a_paused_turn_with_no_extra_message(tmp_path, fake_api):
    FakeApi.replies = [
        {"content": [{"type": "text", "text": "part"}], "stop_reason": "pause_turn"},
        {"content": [{"type": "text", "text": "whole"}]},
    ]
    session = ApiJudge(url=fake_api).session("task", tmp_path / "work", [], None)
    assert session.text == "whole"
    assert [m["role"] for m in FakeApi.requests[1]["body"]["messages"]] == ["user", "assistant"]


def test_api_judge_retries_when_the_service_is_busy(tmp_path, fake_api):
    FakeApi.replies = [529, {"content": [{"type": "text", "text": "ok"}]}]
    assert ApiJudge(url=fake_api).session("task", tmp_path / "work", [], None).text == "ok"
    assert len(FakeApi.requests) == 2


def test_api_judge_reports_a_bad_request_without_the_key(tmp_path, fake_api):
    FakeApi.replies = [400]
    with pytest.raises(JudgeError, match="API call failed") as caught:
        ApiJudge(url=fake_api).session("task", tmp_path / "work", [], None)
    assert "not-a-real-key" not in str(caught.value)


def test_api_judge_sends_thinking_back_unchanged_and_records_the_serving_model(tmp_path, fake_api):
    work = tmp_path / "work"
    thinking = {"type": "thinking", "thinking": "hm", "signature": "sig"}
    FakeApi.replies = [
        {"model": "claude-served-9", "content": [thinking, {"type": "tool_use", "id": "a", "name": "list_files", "input": {}}]},
        {"model": "claude-served-9", "content": [{"type": "text", "text": "done"}]},
    ]
    session = ApiJudge(url=fake_api).session("task", work, ["Read"], None)
    assert FakeApi.requests[1]["body"]["messages"][1]["content"][0] == thinking
    assert session.model == "claude-served-9"


def test_api_judge_stops_at_the_clock(tmp_path, fake_api):
    with pytest.raises(JudgeError, match="Stopped after 0 minutes"):
        ApiJudge(url=fake_api).session("task", tmp_path / "work", [], None, minutes=0)


def test_api_judge_without_the_sdk_says_how_to_get_it(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(JudgeError, match="blindrepro\\[api\\]"):
        ApiJudge()


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
