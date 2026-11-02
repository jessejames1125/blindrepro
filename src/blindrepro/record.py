"""Hashes and transcripts: what makes a frozen derivation checkable later."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

WITHHELD_TOOLS = {"Read", "Grep", "read_file", "mcp__blindrepro__read"}
DROP_EVENTS = {"rate_limit_event", "stream_event"}
DROP_FIELDS = {"uuid", "session_id", "parent_tool_use_id", "signature", "tool_use_result", "usage", "capabilities", "plugins", "agents"}
FREEZE_FILE = "freeze.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _swap_paths(text: str, swaps: list[tuple[str, str]]) -> str:
    # Windows paths ignore case, and the guard reports them lower-cased.
    flags = re.IGNORECASE if os.name == "nt" else 0
    for old, new in swaps:
        if old and not any(sep in old for sep in ("\\", "/")):
            # A bare name, such as the account name, is swapped only as a whole word.
            text = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])", lambda _match: new, text, flags=flags)
        elif old:
            for form in (old, old.replace("\\", "/"), old.replace("\\", "\\\\")):
                text = re.sub(re.escape(form), lambda _match: new, text, flags=flags)
    return text


def _clean(value, swaps):
    if isinstance(value, str):
        return _swap_paths(value, swaps)
    if isinstance(value, list):
        return [_clean(v, swaps) for v in value]
    if isinstance(value, dict):
        return {k: _clean(v, swaps) for k, v in value.items() if k not in DROP_FIELDS}
    return value


def _flat_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in content)
    return str(content)


def shareable_transcript(events: list[dict], swaps: list[tuple[str, str]]) -> list[dict]:
    """A transcript safe to publish: local paths swapped, and what the agent read kept as hashes.

    The paper and the authors' code have their own licenses, so their text never goes in the
    record. The hash lets someone holding the same text confirm it is what the agent read.
    """
    names: dict[str, str] = {}
    out = []
    for event in events:
        if event.get("type") in DROP_EVENTS:
            continue
        message = event.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), list):
            for block in message["content"]:
                if block.get("type") == "tool_use":
                    names[block.get("id", "")] = block.get("name", "")
                elif block.get("type") == "tool_result" and names.get(block.get("tool_use_id", "")) in WITHHELD_TOOLS:
                    text = _flat_text(block.get("content", ""))
                    block["content"] = f"[withheld, {len(text)} characters, sha256 {sha256_bytes(text.encode('utf-8'))}]"
        out.append(_clean(event, swaps))
    return out


def write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=True) + "\n")


def tool_calls(events: list[dict]) -> list[dict]:
    """Every tool the agent called, for the verdict's account of what it touched."""
    calls = []
    for event in events:
        message = event.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), list):
            for block in message["content"]:
                if block.get("type") == "tool_use":
                    target = block.get("input", {}) or {}
                    calls.append({"tool": block.get("name"), "target": target.get("file_path") or target.get("path") or target.get("pattern") or ""})
    return calls


SEAL_FILE = "seal.json"
UNSEALED = ("private",)


def _tree(folder: Path, record_name: str, skip: tuple[str, ...] = ()) -> dict[str, str]:
    """Hash of every file under the folder except the record itself and skipped top folders."""
    files = {}
    for path in sorted(folder.rglob("*")):
        relative = path.relative_to(folder).as_posix()
        if not path.is_file() or relative == record_name or relative.split("/", 1)[0] in skip:
            continue
        files[relative] = sha256_file(path)
    return files


def _write_record(folder: Path, name: str, key: str, files: dict, meta: dict) -> dict:
    record = {"files": files, **meta}
    record[key] = sha256_bytes(canonical(record))
    (folder / name).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return record


def _check_record(folder: Path, name: str, key: str, when: str, skip: tuple[str, ...] = ()) -> list[str]:
    record_path = folder / name
    if not record_path.exists():
        return [f"{name} is missing"]
    record = json.loads(record_path.read_text(encoding="utf-8"))
    stated = record.pop(key, "")
    problems = []
    if sha256_bytes(canonical(record)) != stated:
        problems.append(f"{name} was edited: its hash no longer matches")
    on_disk = _tree(folder, name, skip)
    for name_, digest in record["files"].items():
        if name_ not in on_disk:
            problems.append(f"{name_} is missing")
        elif on_disk[name_] != digest:
            problems.append(f"{name_} changed after the {when}")
    for name_ in on_disk:
        if name_ not in record["files"]:
            problems.append(f"{name_} was added after the {when}")
    return problems


def freeze(folder: Path, meta: dict) -> dict:
    """Hash every file in the folder, then hash that list with the run's facts. Returns the record."""
    return _write_record(folder, FREEZE_FILE, "freeze_hash", _tree(folder, FREEZE_FILE), meta)


def check_freeze(folder: Path) -> list[str]:
    """Empty list means every byte matches. Otherwise one line per problem."""
    return _check_record(folder, FREEZE_FILE, "freeze_hash", "freeze")


def seal(run: Path, freeze_hash: str) -> dict:
    """Hash the whole finished run (the authors' side and the verdict too), tied to the freeze."""
    return _write_record(run, SEAL_FILE, "seal_hash", _tree(run, SEAL_FILE, UNSEALED), {"freeze_hash": freeze_hash})


def check_seal(run: Path) -> list[str]:
    return _check_record(run, SEAL_FILE, "seal_hash", "seal", UNSEALED)

