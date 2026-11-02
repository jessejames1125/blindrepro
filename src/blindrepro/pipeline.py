"""The run, in order: scope, derive, freeze, memory check, fetch code, adapter, compare, verdict.

Each step leaves its output on disk, so an interrupted run picks up where it stopped when
the same command runs again. The authors' code is not fetched until the freeze exists.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, prompts
from .compare import NOT_COMPARED, Comparison, compare, flatten, literal_check, parse_result_line, relative_error
from .envs import BLIND_PACKAGES, PYTHON_VERSION, ensure_env, env_for_requirements, installed_packages, python_version
from .judges import BUILT_IN, Session
from .paper import Paper, leak_check, load_paper, redact
from .record import check_freeze, freeze, shareable_transcript, sha256_file, tool_calls, write_jsonl
from .sandbox import DEFAULT_MEMORY_MB, DEFAULT_SECONDS, run_guarded
from .verdict import terminal_summary, verdict_markdown

# Source: Anthropic's models overview page, "Training data cutoff", read 2026-11-02.
TRAINING_CUTOFFS = {
    "claude-fable-5-1": "2026-06",
    "claude-opus-5-5": "2026-06",
    "claude-sonnet-5-5": "2026-06",
    "claude-haiku-5-5": "2026-06",
}
PRIVATE_NOTICE = "This folder holds the paper's full text. Do not publish it unless the paper's license allows.\n"
BLIND_EXCLUDE = {"paper.txt", "spec.json", ".tmp", "runs.jsonl", "__pycache__"}


class RunStopped(Exception):
    """A step ended the run early. The message says why."""


@dataclass
class Case:
    paper: str
    target: str
    code: str
    out: Path
    commit: str = ""
    tolerance: float = 0.05
    seconds: int = DEFAULT_SECONDS
    memory_mb: int = DEFAULT_MEMORY_MB
    minutes: int = 30
    allow_packages: list[str] = field(default_factory=list)
    show_values: bool = False
    skip_recall: bool = False
    stop_after_freeze: bool = False
    model_cutoff: str = ""
    spec: str = ""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(message: str) -> None:
    print(message, flush=True)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def swaps_for(workspace: Path) -> list[tuple[str, str]]:
    return [(str(workspace), "<work>"), (str(workspace.resolve()), "<work>"), (str(Path.home()), "<home>")]


def save_session(session: Session, workspace: Path, path: Path, prompt: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(path, shareable_transcript(session.transcript, swaps_for(workspace)))
    path.with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8", newline="\n")
    return {
        "model": session.model,
        "version": session.version,
        "seconds": round(session.seconds, 1),
        "tools_offered": session.tools_offered,
        "refused": session.refused,
        "calls": len(tool_calls(session.transcript)),
    }


def extract_json(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def check_spec(spec: dict) -> list[str]:
    problems = []
    keys = [q.get("key", "") for q in spec.get("quantities", [])]
    if not keys:
        problems.append("spec lists no quantities")
    if len(set(keys)) != len(keys):
        problems.append("spec repeats a key")
    for key in keys:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            problems.append(f"bad key {key!r}")
    return problems


def public_spec(spec: dict) -> dict:
    """What the blind agent and the adapter may see. Paper values and the redaction list stay sealed."""
    return {"claim": spec["claim"], "quantities": spec["quantities"]}


def scope(case: Case, judge, full_text: str) -> dict:
    sealed = case.out / "scope" / "spec.json"
    if sealed.exists():
        return read_json(sealed)
    if case.spec:
        spec = read_json(Path(case.spec))
    else:
        log("Step 1 of 5: an agent reads the paper and lists what to compute.")
        work = Path(tempfile.mkdtemp(prefix="blindrepro-scope-"))
        (work / "paper_full.txt").write_text(full_text, encoding="utf-8")
        prompt = prompts.SCOPE.format(target=case.target)
        session = judge.session(prompt, work, ["Read", "Grep", "Write"], None, min(case.minutes, 15), stage="scope")
        save_session(session, work, case.out / "scope" / "transcript.jsonl", prompt)
        if not (work / "spec.json").exists():
            raise RunStopped("The scoping step wrote no spec.json.")
        spec = read_json(work / "spec.json")
        shutil.rmtree(work, ignore_errors=True)
    if spec.get("not_computable"):
        write_json(sealed, spec)
        raise RunStopped(f"Not computable from the paper on a laptop: {spec['not_computable']}")
    problems = check_spec(spec)
    if problems:
        raise RunStopped("The spec is not usable: " + "; ".join(problems))
    write_json(sealed, spec)
    return spec


def run_script(python: Path, folder: Path, script: str, case: Case, **options) -> tuple[dict | None, object]:
    result = run_guarded(python, folder / script, folder, seconds=case.seconds, memory_mb=case.memory_mb, **options)
    return (parse_result_line(result.stdout) if result.ok else None), result


def derive(case: Case, judge, spec: dict, paper: Paper, redacted_text: str, redaction: dict) -> dict:
    frozen = case.out / "frozen"
    if (frozen / "freeze.json").exists():
        return read_json(frozen / "freeze.json")
    log("Step 2 of 5: the blind agent derives the result. It has no shell and no web, and the authors' code is not on this machine yet.")
    packages = BLIND_PACKAGES + case.allow_packages
    python = ensure_env(packages)
    work = Path(tempfile.mkdtemp(prefix="blindrepro-blind-"))
    (work / "paper.txt").write_text(redacted_text, encoding="utf-8")
    write_json(work / "spec.json", public_spec(spec))
    prompt = prompts.DERIVE.format(
        python=PYTHON_VERSION,
        packages=", ".join(packages),
        seconds=case.seconds,
        memory_mb=case.memory_mb,
    )
    run_config = {
        "workspace": str(work),
        "python": str(python),
        "script": "derive.py",
        "description": "Run derive.py in the work folder through the guard and return its output.",
        "log": str(work / "runs.jsonl"),
        "seconds": case.seconds,
        "memory_mb": case.memory_mb,
    }
    session = judge.session(prompt, work, BUILT_IN, run_config, case.minutes, stage="derive")
    frozen.mkdir(parents=True, exist_ok=True)
    info = save_session(session, work, frozen / "transcript.jsonl", prompt)
    blind = frozen / "blind"
    blind.mkdir(exist_ok=True)
    for item in work.iterdir():
        if item.name in BLIND_EXCLUDE:
            continue
        if item.is_file():
            shutil.copy2(item, blind / item.name)
    write_json(frozen / "spec_shown.json", public_spec(spec))
    runs = []
    if (work / "runs.jsonl").exists():
        runs = [json.loads(line) for line in (work / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    write_jsonl(frozen / "script_runs.jsonl", [{k: v for k, v in r.items() if k != "at"} for r in runs])

    log("Step 3 of 5: freezing. The derivation runs once more on its own, then every file is hashed.")
    values, result, blocked = None, None, 0
    if (blind / "derive.py").exists():
        fresh = Path(tempfile.mkdtemp(prefix="blindrepro-fresh-"))
        for item in blind.iterdir():
            shutil.copy2(item, fresh / item.name)
        values, result = run_script(python, fresh, "derive.py", case)
        blocked = len(result.blocked)
        (frozen / "derive_stdout.txt").write_text(result.stdout[-200000:], encoding="utf-8", newline="\n")
        shutil.rmtree(fresh, ignore_errors=True)
    write_json(frozen / "results.json", values if values is not None else {})
    private = case.out / "private"
    meta = {
        "frozen_at": now(),
        "tool_version": __version__,
        "paper": paper.to_dict(),
        "paper_shown_sha256": _text_hash(redacted_text),
        "redaction": redaction,
        "target": case.target,
        "tolerance": case.tolerance,
        "model": info["model"],
        "judge": judge.name,
        "judge_version": info["version"],
        "tools_offered": info["tools_offered"],
        "refused_calls": info["refused"],
        "agent_tool_calls": info["calls"],
        "agent_seconds": info["seconds"],
        "python": python_version(python),
        "packages": installed_packages(python),
        "allowed_packages": packages,
        "guard_blocked_during_session": sum(len(r.get("blocked", [])) for r in runs),
        "guard_blocked_at_freeze": blocked,
        "derivation_ran": bool(values),
        "script_error": "" if values or result is None else (result.stderr or result.stdout)[-2000:],
        "limits": {"seconds": case.seconds, "memory_mb": case.memory_mb},
    }
    (private / "README.txt").write_text(PRIVATE_NOTICE, encoding="utf-8")
    record = freeze(frozen, meta)
    shutil.rmtree(work, ignore_errors=True)
    log(f"Frozen. Hash: {record['freeze_hash']}")
    return record


def _text_hash(text: str) -> str:
    from .paper import sha256_text

    return sha256_text(text)


def recall_probe(case: Case, judge, paper: Paper, spec: dict) -> dict | None:
    path = case.out / "probe" / "recall.json"
    if path.exists():
        return read_json(path)
    if case.skip_recall:
        return None
    log("Memory check: the model is asked for the values with no paper and no tools.")
    quantities = "\n".join(f"- {q['key']}: {q['description']} ({q.get('units', '')})" for q in spec["quantities"])
    prompt = prompts.RECALL.format(paper=f"{paper.title} ({paper.ref})", claim=spec["claim"], quantities=quantities)
    work = Path(tempfile.mkdtemp(prefix="blindrepro-probe-"))
    session = judge.session(prompt, work, [], None, 5, stage="recall")
    save_session(session, work, case.out / "probe" / "transcript.jsonl", prompt)
    shutil.rmtree(work, ignore_errors=True)
    stated = extract_json(session.text) or {}
    write_json(path, {"stated": stated, "model": session.model})
    return read_json(path)


def fetch_code(url: str, commit: str, dest: Path) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    subprocess.run(
        ["git", "clone", "--quiet", "-c", "core.autocrlf=false", url, str(dest)],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    if commit:
        subprocess.run(["git", "-C", str(dest), "checkout", "--quiet", commit], check=True, env=env, capture_output=True, text=True)
    done = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
    return done.stdout.strip()


def code_changes(code: Path) -> str:
    done = subprocess.run(["git", "-C", str(code), "diff"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return done.stdout


def adapter_python(work: Path) -> Path:
    requirements = work / "requirements.txt"
    if requirements.exists():
        return env_for_requirements(requirements)
    return ensure_env(["numpy", "scipy"])


def authors_step(case: Case, judge, spec: dict, work: Path) -> dict:
    """Run the adapter step. Returns the code record. The derivation is already frozen."""
    folder = case.out / "authors"
    record_path = folder / "code_record.json"
    code_dir = work / "code"
    if record_path.exists():
        record = read_json(record_path)
        if not code_dir.exists():
            fetch_code(case.code, record["commit"], code_dir)
            patch = folder / "patch.diff"
            if patch.exists():
                subprocess.run(["git", "-C", str(code_dir), "apply", str(patch.resolve())], check=False)
        for item in folder.iterdir():
            if item.suffix in (".py", ".txt", ".md") and item.is_file():
                shutil.copy2(item, work / item.name)
        return record
    log("Step 4 of 5: fetching the authors' code. A separate agent writes an adapter that calls it. It cannot see the derivation.")
    fetched_at = now()
    try:
        commit = fetch_code(case.code, case.commit, code_dir)
    except subprocess.CalledProcessError as error:
        record = {"url": case.code, "commit": case.commit, "fetched_at": fetched_at, "fetch_error": (error.stderr or "")[-1000:], "values": None}
        write_json(record_path, record)
        return record
    write_json(work / "spec.json", public_spec(spec))
    prompt = prompts.ADAPTER.format(commit=commit, seconds=case.seconds, memory_mb=case.memory_mb)
    run_config = {
        "workspace": str(work),
        "python": str(ensure_env(["numpy", "scipy"])),
        "script": "adapter.py",
        "requirements": "requirements.txt",
        "description": "Build the environment from requirements.txt, run adapter.py through the guard, and return its output.",
        "log": str(work / "runs.jsonl"),
        "seconds": case.seconds,
        "memory_mb": case.memory_mb,
        "allow_process": True,
    }
    session = judge.session(prompt, work, BUILT_IN, run_config, case.minutes, stage="adapter")
    folder.mkdir(parents=True, exist_ok=True)
    info = save_session(session, work, folder / "transcript.jsonl", prompt)
    for name in ("adapter.py", "requirements.txt", "notes.md", "could_not_run.md"):
        if (work / name).exists():
            shutil.copy2(work / name, folder / name)
    diff = code_changes(code_dir)
    if diff:
        (folder / "patch.diff").write_text(diff, encoding="utf-8", newline="\n")
    values = None
    error_text = ""
    if (work / "adapter.py").exists():
        try:
            values, result = run_script(adapter_python(work), work, "adapter.py", case, allow_process=True)
            (folder / "adapter_stdout.txt").write_text(result.stdout[-200000:], encoding="utf-8", newline="\n")
            if values is None:
                error_text = (result.stderr or result.stdout)[-2000:]
        except subprocess.CalledProcessError as error:
            error_text = f"Could not build the environment: {error}"
    could_not_run = (work / "could_not_run.md").read_text(encoding="utf-8") if (work / "could_not_run.md").exists() else ""
    record = {
        "url": case.code,
        "commit": commit,
        "fetched_at": fetched_at,
        "values": values,
        "modified": bool(diff),
        "could_not_run": could_not_run or error_text,
        "model": info["model"],
        "agent_seconds": info["seconds"],
    }
    write_json(record_path, record)
    return record


def explain(case: Case, judge, spec: dict, comparison: Comparison, work: Path) -> str:
    path = case.out / "compare" / "explanation.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    log("Step 5 of 5: the numbers differ, so an agent reads both sides to find where.")
    explain_dir = Path(tempfile.mkdtemp(prefix="blindrepro-explain-"))
    shutil.copytree(case.out / "frozen" / "blind", explain_dir / "derivation")
    shutil.copytree(work, explain_dir / "authors", ignore=shutil.ignore_patterns(".git", ".tmp"))
    write_json(explain_dir / "comparison.json", comparison.to_dict())
    write_json(explain_dir / "spec.json", public_spec(spec))
    session = judge.session(prompts.EXPLAIN, explain_dir, ["Read", "Grep", "Glob"], None, 15, stage="explain")
    save_session(session, explain_dir, case.out / "compare" / "explain_transcript.jsonl", prompts.EXPLAIN)
    shutil.rmtree(explain_dir, ignore_errors=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(session.text, encoding="utf-8", newline="\n")
    return session.text


def recall_summary(recall: dict | None, authors: dict | None, tolerance: float) -> dict | None:
    if recall is None:
        return None
    stated = flatten(recall.get("stated", {}))
    truth = flatten(authors or {})
    given = {k: v for k, v in stated.items() if v is not None}
    matched = sum(1 for k, v in given.items() if truth.get(k) is not None and relative_error(v, truth[k]) <= tolerance)
    return {"stated": len(given), "total": len(stated), "matched": matched, "values": given}


def cutoff_statement(paper: Paper, model: str, override: str) -> dict:
    cutoff = override or next((v for k, v in TRAINING_CUTOFFS.items() if model.startswith(k)), "")
    if not cutoff:
        return {"cutoff": "", "statement": f"not known for {model}; pass --model-cutoff."}
    if not paper.first_public:
        return {"cutoff": cutoff, "statement": f"{cutoff}; paper date unknown, so no comparison."}
    after = paper.first_public[:7] > cutoff
    if after:
        return {"cutoff": cutoff, "after_cutoff": True, "statement": f"{cutoff} per the vendor. Paper first posted {paper.first_public}, after that, so it should not be in training data."}
    return {"cutoff": cutoff, "after_cutoff": False, "statement": f"{cutoff} per the vendor. Paper first posted {paper.first_public}, before that, so it may be in training data."}


def build_verdict(case: Case, spec: dict, record: dict, code: dict, comparison: Comparison, explanation: str, recall, leaks, literals, paper_dict: dict, run_extra: dict) -> dict:
    return {
        "tool": "blindrepro",
        "paper": paper_dict,
        "target": case.target,
        "claim": spec["claim"],
        "quantities": spec["quantities"],
        "code": {k: code.get(k) for k in ("url", "commit", "fetched_at", "modified", "could_not_run", "fetch_error")},
        "comparison": comparison.to_dict(),
        "explanation": explanation,
        "blinding": {
            "freeze_hash": record["freeze_hash"],
            "frozen_at": record["frozen_at"],
            "code_fetched_at": code.get("fetched_at", ""),
            "tools_offered": record["tools_offered"],
            "refused_calls": len(record["refused_calls"]),
            "guard_blocked": record["guard_blocked_during_session"] + record["guard_blocked_at_freeze"],
            "redaction": record["redaction"],
            "values_shown": case.show_values,
            "leaks": leaks,
            "literals": literals,
            "recall": recall,
            "cutoff": run_extra["cutoff"],
        },
        "run": {
            "model": record["model"],
            "judge": record["judge"],
            "judge_version": record["judge_version"],
            "tool_version": record["tool_version"],
            "date": record["frozen_at"][:10],
            "python": record["python"],
            "packages": record["packages"],
            "agent_seconds": record["agent_seconds"],
        },
    }


def run_case(case: Case, judge) -> dict:
    case.out.mkdir(parents=True, exist_ok=True)
    private = case.out / "private"
    private.mkdir(exist_ok=True)
    full_path = private / "paper_full.txt"
    if full_path.exists() and (private / "paper.json").exists():
        full_text = full_path.read_text(encoding="utf-8")
        paper = Paper(**read_json(private / "paper.json"))
    else:
        log(f"Reading the paper: {case.paper}")
        paper, full_text = load_paper(case.paper, private)
    write_json(case.out / "case.json", {k: (str(v) if isinstance(v, Path) else v) for k, v in asdict(case).items() if k != "out"})

    spec = scope(case, judge, full_text)
    if case.show_values:
        shown, redaction = redact(full_text, [])
    else:
        shown, redaction = redact(full_text, spec.get("redact", []))
    (private / "paper_shown.txt").write_text(shown, encoding="utf-8")

    record = derive(case, judge, spec, paper, shown, redaction)
    if case.stop_after_freeze and not (case.out / "authors" / "code_record.json").exists():
        raise RunStopped(
            f"Stopped after the freeze, as asked. Publish this hash somewhere public, then run the same command without --stop-after-freeze:\n{record['freeze_hash']}"
        )
    problems = check_freeze(case.out / "frozen")
    if problems:
        raise RunStopped("The frozen derivation changed: " + "; ".join(problems))
    recall = recall_probe(case, judge, paper, spec)

    work = Path(tempfile.mkdtemp(prefix="blindrepro-authors-"))
    code = authors_step(case, judge, spec, work)
    derived = read_json(case.out / "frozen" / "results.json") or None
    expected = [q["key"] for q in spec["quantities"]]
    comparison = compare(derived, code.get("values"), spec.get("paper_values"), case.tolerance, expected)
    if code.get("fetch_error"):
        comparison.reason = f"The authors' code could not be fetched: {code['fetch_error'].strip()}"
    elif comparison.status == NOT_COMPARED and code.get("could_not_run"):
        comparison.reason = "The authors' code did not run. See below."
    write_json(case.out / "compare" / "comparison.json", comparison.to_dict())
    explanation = ""
    if comparison.status == "DIVERGED" and not getattr(judge, "skip_explain", False):
        explanation = explain(case, judge, spec, comparison, work)
    truth = {k: v for k, v in flatten(code.get("values") or {}).items() if v is not None}
    truth.update({k: v for k, v in flatten(spec.get("paper_values") or {}).items() if v is not None and k not in truth})
    leaks = leak_check(shown, truth)
    derive_source = case.out / "frozen" / "blind" / "derive.py"
    literals = literal_check(derive_source.read_text(encoding="utf-8"), truth) if derive_source.exists() else []
    extra = {"cutoff": cutoff_statement(paper, record["model"], case.model_cutoff)}
    verdict = build_verdict(
        case, spec, record, code, comparison, explanation,
        recall_summary(recall, code.get("values"), case.tolerance),
        leaks, literals, paper.to_dict(), extra,
    )
    write_json(case.out / "verdict.json", verdict)
    (case.out / "verdict.md").write_text(verdict_markdown(verdict), encoding="utf-8", newline="\n")
    shutil.rmtree(work, ignore_errors=True)
    return verdict


def show(verdict: dict) -> None:
    print(terminal_summary(verdict), flush=True)


def elapsed(start: float) -> str:
    return f"{time.monotonic() - start:.0f} s"


def sha_of(path: Path) -> str:
    return sha256_file(path)
