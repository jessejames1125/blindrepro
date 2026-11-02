"""The one tool an agent has for running code: a small MCP server over standard input.

Started by the claude command as: python -m blindrepro.toolserver CONFIG.json

The agent gets no shell. It writes a script, calls this tool, and this tool runs the
script through the guard. Every call goes in the log named by the config.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .sandbox import RunResult, run_guarded

OUTPUT_LIMIT = 20_000


def tail(text: str) -> str:
    if len(text) <= OUTPUT_LIMIT:
        return text
    return f"[first {len(text) - OUTPUT_LIMIT} characters cut]\n" + text[-OUTPUT_LIMIT:]


def execute(config: dict) -> RunResult:
    workspace = Path(config["workspace"])
    python = config["python"]
    if config.get("requirements"):
        from .envs import env_for_requirements

        requirements = workspace / config["requirements"]
        if requirements.exists():
            python = str(env_for_requirements(requirements))
    return run_guarded(
        Path(python),
        workspace / config["script"],
        workspace,
        read_roots=[Path(p) for p in config.get("read_roots", [])],
        allow_process=config.get("allow_process", False),
        seconds=config.get("seconds", 600),
        memory_mb=config.get("memory_mb", 4096),
    )


def report(result: RunResult) -> str:
    lines = [
        f"exit code: {result.returncode}",
        f"seconds: {result.seconds:.1f}",
    ]
    if result.timed_out:
        lines.append("stopped: ran past the time limit")
    for item in result.blocked:
        lines.append(f"blocked: {item['blocked']} ({item['detail']})")
    lines += ["--- stdout ---", tail(result.stdout), "--- stderr ---", tail(result.stderr)]
    return "\n".join(lines)


def run_tool(config: dict) -> str:
    result = execute(config)
    with open(config["log"], "a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "at": time.time(),
                    "exit": result.returncode,
                    "seconds": round(result.seconds, 2),
                    "timed_out": result.timed_out,
                    "blocked": result.blocked,
                }
            )
            + "\n"
        )
    return report(result)


def answer(request: dict, config: dict) -> dict | None:
    method = request.get("method")
    identity = request.get("id")
    if identity is None:
        return None
    if method == "initialize":
        result = {
            "protocolVersion": request["params"].get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "blindrepro", "version": "1"},
        }
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": "run",
                    "description": config["description"],
                    "inputSchema": {"type": "object", "properties": {}},
                }
            ]
        }
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": run_tool(config)}]}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": identity, "error": {"code": -32601, "message": "unknown method"}}
    return {"jsonrpc": "2.0", "id": identity, "result": result}


def main() -> None:
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    for line in stdin:
        if not line.strip():
            continue
        reply = answer(json.loads(line), config)
        if reply is not None:
            stdout.write(json.dumps(reply).encode("utf-8") + b"\n")
            stdout.flush()


if __name__ == "__main__":
    main()
