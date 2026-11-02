"""The model behind each step: the claude command, an API key, or a recorded run.

This module never reads, stores or forwards a login token. The claude command handles
its own sign-in. The API judge reads ANTHROPIC_API_KEY only when asked to use it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from .sandbox import IN_GROUP, run_tree
from .toolserver import run_tool

SYSTEM_PROMPT = (
    "You are a careful research engineer. You work only inside the current folder. "
    "You have no web access and no shell. Finish the task, then stop."
)
RUN_TOOL = "mcp__blindrepro__run"
# A session transcript is read whole: its first line names the model.
TRANSCRIPT_LIMIT = 500_000_000
BUILT_IN = ["Read", "Write", "Edit", "Grep", "Glob"]


class JudgeError(RuntimeError):
    pass


@dataclass
class Session:
    text: str
    model: str
    version: str
    seconds: float
    transcript: list[dict] = field(default_factory=list)
    tools_offered: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)


def _env_for_claude() -> dict[str, str]:
    """Drop nested-session variables, and API keys so a subscription is never billed by accident."""
    drop = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in drop and not key.startswith(("CLAUDECODE", "CLAUDE_CODE_", "CLAUDE_PID", "CLAUDE_EFFORT"))
    }
    # Keep the agent's context to our prompt: no CLAUDE.md files, no saved memory, and the
    # one tool loaded up front, because the tool-search tool is not on the list.
    env.update(
        CLAUDE_CODE_DISABLE_CLAUDE_MDS="1",
        CLAUDE_CODE_DISABLE_AUTO_MEMORY="1",
        ENABLE_TOOL_SEARCH="false",
    )
    return env


class ClaudeCli:
    """Runs the official claude command, signed in by its owner, with a locked-down tool list."""

    name = "claude-cli"

    def __init__(self, model: str = "opus", effort: str = "high", command: str | None = None):
        self.model = model
        self.effort = effort
        self.command = command or shutil.which("claude")
        if not self.command:
            raise JudgeError("The claude command was not found. Install Claude Code or use --judge api.")

    def _version(self) -> str:
        done = subprocess.run([self.command, "--version"], capture_output=True, text=True, env=_env_for_claude())
        return done.stdout.strip()

    def session(
        self,
        prompt: str,
        workspace: Path,
        tools: list[str],
        run_config: dict | None = None,
        minutes: int = 30,
        stage: str = "",
    ) -> Session:
        workspace.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="blindrepro-mcp-") as scratch:
            command = [
                self.command,
                "-p",
                "--output-format",
                "stream-json",
                "--verbose",
                "--model",
                self.model,
                "--effort",
                self.effort,
                "--restricted",
                "--no-session-persistence",
                "--permission-mode",
                "dontAsk",
                "--permission-prompts",
                "none",
                "--disable-slash-commands",
                "--strict-mcp-config",
                "--system-prompt",
                SYSTEM_PROMPT,
                "--tools",
                ",".join(tools) if tools else "",
            ]
            allowed = list(tools)
            if run_config is not None:
                config_path = Path(scratch) / "run.json"
                config_path.write_text(json.dumps(run_config), encoding="utf-8")
                mcp = {
                    "mcpServers": {
                        "blindrepro": {
                            "command": sys.executable,
                            "args": ["-m", "blindrepro.toolserver", str(config_path)],
                            # IN_GROUP keeps the server's scripts in the session's process group.
                            "env": {"PYTHONPATH": str(Path(__file__).resolve().parents[1]), IN_GROUP: "1"},
                        }
                    }
                }
                mcp_path = Path(scratch) / "mcp.json"
                mcp_path.write_text(json.dumps(mcp), encoding="utf-8")
                command += ["--mcp-config", str(mcp_path)]
                allowed.append(RUN_TOOL)
            if allowed:
                command += ["--allowedTools", ",".join(allowed)]
            # Run so that a timeout also ends the tool server and anything it started, such as an install.
            done = run_tree(
                command,
                env=_env_for_claude(),
                seconds=minutes * 60,
                cwd=workspace,
                input_text=prompt,
                output_limit=TRANSCRIPT_LIMIT,
            )
            stdout = done.stdout
            stderr = f"stopped after {minutes:g} minutes" if done.timed_out else done.stderr
        events = []
        for line in stdout.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return self._session_from(events, stderr, time.monotonic() - start)

    def _session_from(self, events: list[dict], stderr: str, seconds: float) -> Session:
        init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
        result = next((e for e in reversed(events) if e.get("type") == "result"), {})
        if not init or not result:
            raise JudgeError(f"claude returned no usable session. Its error output: {stderr[-1500:]}")
        if result.get("is_error") and not result.get("result"):
            raise JudgeError(f"claude reported an error: {str(result)[:1500]}")
        return Session(
            text=result.get("result") or "",
            model=init.get("model", self.model),
            version=init.get("claude_code_version") or self._version(),
            seconds=seconds,
            transcript=events,
            tools_offered=list(init.get("tools", [])),
            refused=[str(d.get("tool_name")) for d in result.get("permission_denials", [])],
        )


class ApiJudge:
    """Runs the same steps through the Messages API, with the researcher's own key."""

    name = "anthropic-api"

    def __init__(self, model: str = "claude-opus-5-5", effort: str = "high", url: str | None = None, max_tokens: int = 64000):
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise JudgeError("Set ANTHROPIC_API_KEY to use --judge api.")
        try:
            import anthropic
        except ImportError as missing:
            raise JudgeError('--judge api needs the Anthropic SDK. Run with: uvx --from "blindrepro[api]" blindrepro ...') from missing
        self.sdk = anthropic
        self.client = anthropic.Anthropic(api_key=key, base_url=url, max_retries=5)
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens

    def _reply(self, messages: list[dict], specs: list[dict]) -> "object":
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": messages,
            "output_config": {"effort": self.effort},
        }
        if specs:
            body["tools"] = specs
        try:
            with self.client.messages.stream(**body) as stream:
                return stream.get_final_message()
        except self.sdk.APIError as error:
            raise JudgeError(f"The API call failed: {error}") from error

    @staticmethod
    def _tool_list(tools: list[str], run_config: dict | None) -> list[dict]:
        text = {"type": "string"}
        specs = []
        if "Read" in tools:
            specs.append(
                {
                    "name": "read_file",
                    "description": "Read a text file in the work folder. Lines are 1-indexed.",
                    "input_schema": {
                        "type": "object",
                        "properties": {"path": text, "offset": {"type": "integer"}, "limit": {"type": "integer"}},
                        "required": ["path"],
                    },
                }
            )
            specs.append(
                {
                    "name": "list_files",
                    "description": "List files under a folder in the work folder.",
                    "input_schema": {"type": "object", "properties": {"path": text}},
                }
            )
        if "Write" in tools:
            specs.append(
                {
                    "name": "write_file",
                    "description": "Create or replace a file in the work folder.",
                    "input_schema": {
                        "type": "object",
                        "properties": {"path": text, "content": text},
                        "required": ["path", "content"],
                    },
                }
            )
        if run_config is not None:
            specs.append(
                {
                    "name": "run",
                    "description": run_config["description"],
                    "input_schema": {"type": "object", "properties": {}},
                }
            )
        return specs

    @staticmethod
    def _inside(workspace: Path, relative: str) -> Path:
        path = (workspace / relative).resolve()
        if path != workspace and workspace not in path.parents:
            raise PermissionError(f"{relative} is outside the work folder")
        return path

    def _call(self, name: str, args: dict, workspace: Path, run_config: dict | None) -> str:
        if name == "read_file":
            lines = self._inside(workspace, args["path"]).read_text(encoding="utf-8", errors="replace").splitlines()
            first = max(int(args.get("offset", 1)), 1) - 1
            count = int(args.get("limit", 2000))
            return "\n".join(f"{i + first + 1}\t{line}" for i, line in enumerate(lines[first : first + count]))
        if name == "list_files":
            root = self._inside(workspace, args.get("path", "."))
            return "\n".join(str(p.relative_to(workspace)) for p in sorted(root.rglob("*")) if p.is_file())[:20000]
        if name == "write_file":
            path = self._inside(workspace, args["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args["content"], encoding="utf-8")
            return "written"
        if name == "run" and run_config is not None:
            return run_tool(run_config)
        raise PermissionError(f"unknown tool {name}")

    def session(
        self,
        prompt: str,
        workspace: Path,
        tools: list[str],
        run_config: dict | None = None,
        minutes: int = 30,
        stage: str = "",
    ) -> Session:
        workspace = workspace.resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        specs = self._tool_list(tools, run_config)
        messages: list[dict] = [{"role": "user", "content": prompt}]
        transcript: list[dict] = [{"type": "system", "subtype": "init", "model": self.model, "tools": [s["name"] for s in specs]}]
        text = ""
        served_by = self.model
        while time.monotonic() - start < minutes * 60:
            reply = self._reply(messages, specs)
            served_by = reply.model
            # Thinking blocks go back unchanged, so the whole reply is kept as it came.
            content = [block.to_dict() for block in reply.content]
            transcript.append({"type": "assistant", "message": {"content": content}, "stop_reason": reply.stop_reason})
            if reply.stop_reason == "refusal":
                category = getattr(reply.stop_details, "category", None)
                raise JudgeError(f"The model declined this step (category: {category}). No tools from that reply were run.")
            if reply.stop_reason == "max_tokens":
                raise JudgeError(f"A reply hit the limit of {self.max_tokens} tokens. No tools from that reply were run.")
            messages.append({"role": "assistant", "content": content})
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text") or text
            if reply.stop_reason == "pause_turn":
                continue
            calls = [b for b in content if b.get("type") == "tool_use"]
            if not calls:
                return Session(text, served_by, f"anthropic-sdk {self.sdk.__version__}", time.monotonic() - start, transcript, [s["name"] for s in specs])
            results = []
            for call in calls:
                try:
                    result, is_error = self._call(call["name"], call["input"], workspace, run_config), False
                except (OSError, PermissionError, KeyError, ValueError, TypeError) as error:
                    result, is_error = str(error), True
                results.append({"type": "tool_result", "tool_use_id": call["id"], "content": result, "is_error": is_error})
            transcript.append({"type": "user", "message": {"content": results}})
            messages.append({"role": "user", "content": results})
        raise JudgeError(f"Stopped after {minutes} minutes with the task unfinished.")


class RecordedJudge:
    """Replays a finished run's files through the real pipeline. It calls no model.

    Everything after the model's files (the freeze, the guard, the authors' code and the
    comparison) still runs for real. Used by the tests and by --judge recorded:<folder>.
    """

    name = "recorded"
    skip_explain = True
    STAGE_FILES = {
        "scope": ("scope", ["spec.json"]),
        "derive": ("frozen/blind", None),
        "adapter": ("authors", ["adapter.py", "requirements.txt", "notes.md", "could_not_run.md"]),
    }

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def session(
        self,
        prompt: str,
        workspace: Path,
        tools: list[str],
        run_config: dict | None = None,
        minutes: int = 30,
        stage: str = "",
    ) -> Session:
        workspace.mkdir(parents=True, exist_ok=True)
        place = self.STAGE_FILES.get(stage)
        if place:
            source = self.folder / place[0]
            names = place[1] or [p.name for p in source.iterdir() if p.is_file()]
            for name in names:
                if (source / name).exists():
                    shutil.copy2(source / name, workspace / name)
        text = ""
        if stage == "recall" and (self.folder / "probe" / "recall.json").exists():
            text = json.dumps(json.loads((self.folder / "probe" / "recall.json").read_text(encoding="utf-8"))["stated"])
        return Session(text, "recorded", "replay", 0.0, [{"type": "system", "subtype": "init", "tools": tools}], list(tools))


def make_judge(name: str, model: str | None, effort: str = "high"):
    if name.startswith("recorded:"):
        return RecordedJudge(Path(name.split(":", 1)[1]))
    if name in ("claude", "claude-cli"):
        return ClaudeCli(model=model or "opus", effort=effort)
    if name == "api":
        return ApiJudge(model=model or "claude-opus-5-5", effort=effort)
    raise JudgeError(f"Unknown judge {name}. Use claude or api.")
