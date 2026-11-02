"""Check a finished run again with no model: hashes, the derivation, then the authors' code."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

from .compare import Comparison, compare, flatten, relative_error
from .envs import BadRequirement, check_requirements, ensure_env, env_for_requirements
from .pipeline import fetch_code, read_json
from .record import SEAL_FILE, check_freeze, check_seal
from .sandbox import DEFAULT_MEMORY_MB, DEFAULT_SECONDS, run_guarded
from .compare import parse_result_line
from .verdict import blinding_facts, headline, table

DRIFT_LIMIT = 1e-6


def apply_patch(code: Path, patch: Path) -> None:
    import subprocess

    if patch.exists():
        subprocess.run(["git", "-C", str(code), "apply", str(patch.resolve())], check=True)


def rerun_derivation(bundle: Path, record: dict) -> tuple[dict | None, float]:
    python = ensure_env(record["packages"])
    limits = record.get("limits", {})
    work = Path(tempfile.mkdtemp(prefix="blindrepro-verify-"))
    try:
        for item in (bundle / "frozen" / "blind").iterdir():
            shutil.copy2(item, work / item.name)
        result = run_guarded(
            python,
            work / "derive.py",
            work,
            seconds=limits.get("seconds", DEFAULT_SECONDS),
            memory_mb=limits.get("memory_mb", DEFAULT_MEMORY_MB),
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return (parse_result_line(result.stdout) if result.ok else None), result.seconds


def rerun_authors(bundle: Path, record: dict) -> tuple[dict | None, float, str]:
    folder = bundle / "authors"
    code_record = read_json(folder / "code_record.json")
    limits = record.get("limits", {})
    work = Path(tempfile.mkdtemp(prefix="blindrepro-verify-"))
    try:
        vendor = folder / "vendor"
        if vendor.exists():
            shutil.copytree(vendor, work / "code")
        else:
            fetch_code(code_record["url"], code_record["commit"], work / "code")
            apply_patch(work / "code", folder / "patch.diff")
        for name in ("adapter.py", "requirements.txt"):
            if (folder / name).exists():
                shutil.copy2(folder / name, work / name)
        if not (work / "adapter.py").exists():
            return None, 0.0, "No adapter exists: the authors' code did not run in the recorded run."
        requirements = work / "requirements.txt"
        try:
            python = env_for_requirements(requirements) if requirements.exists() else ensure_env(["numpy", "scipy"])
        except BadRequirement as bad:
            return None, 0.0, str(bad)
        result = run_guarded(
            python,
            work / "adapter.py",
            work,
            allow_process=True,
            seconds=limits.get("seconds", DEFAULT_SECONDS),
            memory_mb=limits.get("memory_mb", DEFAULT_MEMORY_MB),
        )
        values = parse_result_line(result.stdout) if result.ok else None
        return values, result.seconds, "" if values is not None else (result.stderr or result.stdout)[-1500:]
    finally:
        shutil.rmtree(work, ignore_errors=True)


def max_drift(old: dict, new: dict) -> float:
    a, b = flatten(old or {}), flatten(new or {})
    drifts = [0.0]
    for key, value in a.items():
        other = b.get(key)
        if value is None or other is None:
            if value != other:
                return float("inf")
            continue
        drifts.append(relative_error(other, value))
    return max(drifts)


TRUST_NOTE = (
    "Note: verify runs the scripts in this folder and installs the packages it lists. "
    "Run it only on records you trust, or inside a container."
)


def refuse(say, title: str, problems: list[str]) -> int:
    say(f"REFUSED: {title}")
    for line in problems:
        say(f"  {line}")
    return 2


def verify(bundle: Path, skip_authors: bool = False, say=print, expect: str = "", warn: bool = True) -> int:
    """0 means the record holds. 1 means the numbers moved or could not be rerun. 2 means the record was altered."""
    start = time.monotonic()
    if warn:
        say(TRUST_NOTE)
    problems = check_freeze(bundle / "frozen")
    if problems:
        return refuse(say, "this record does not match its freeze hash.", problems)
    record = read_json(bundle / "frozen" / "freeze.json")
    if expect and not record["freeze_hash"].startswith(expect.lower()):
        return refuse(say, "the freeze hash is not the one you expected.", [f"expected {expect}", f"found    {record['freeze_hash']}"])
    if (bundle / SEAL_FILE).exists():
        problems = check_seal(bundle)
        if read_json(bundle / SEAL_FILE).get("freeze_hash") != record["freeze_hash"]:
            problems.append("seal.json belongs to another freeze")
        if problems:
            return refuse(say, "the finished run does not match its seal.", problems)
    else:
        say("No seal.json, so only the frozen derivation is checked against a hash.")
    verdict = read_json(bundle / "verdict.json") if (bundle / "verdict.json").exists() else None
    say(f"Hashes match. Freeze hash {record['freeze_hash'][:16]}...")
    stored = read_json(bundle / "frozen" / "results.json")
    try:
        check_requirements(record["packages"])
    except BadRequirement as bad:
        return refuse(say, "the record lists a package line that is not a plain package name.", [str(bad)])
    derived, seconds = rerun_derivation(bundle, record)
    status = 0
    if derived is None:
        if stored:
            say("The frozen derivation did not run on this machine. The comparison below uses its recorded values, so this check is incomplete.")
            status = 1
        else:
            say("The recorded run has no derivation to rerun.")
        derived = stored or None
    else:
        say(f"Derivation rerun in {seconds:.1f} s. Largest change from the recorded values: {max_drift(stored, derived):.1e}.")
    if derived is not None and stored and max_drift(stored, derived) > DRIFT_LIMIT:
        say("The derivation's numbers moved since the freeze. This run is not deterministic or the platform differs.")
        status = 1
    authors = None
    if skip_authors:
        code_record = read_json(bundle / "authors" / "code_record.json")
        authors = code_record.get("values")
        say("Authors' code not rerun: using the values in the sealed record.")
    else:
        authors, seconds, error = rerun_authors(bundle, record)
        if authors is None:
            say(f"Authors' code gave no values here: {error}")
            if read_json(bundle / "authors" / "code_record.json").get("values"):
                status = 1
        else:
            say(f"Authors' code rerun in {seconds:.1f} s.")
    tolerance = record.get("tolerance", 0.05)
    spec_values = None
    if (bundle / "scope" / "spec.json").exists():
        spec_values = read_json(bundle / "scope" / "spec.json").get("paper_values")
    shown = bundle / "frozen" / "spec_shown.json"
    expected = [q["key"] for q in read_json(shown)["quantities"]] if shown.exists() else None
    comparison: Comparison = compare(derived, authors, spec_values, tolerance, expected)
    say("")
    say(table(comparison))
    say("")
    say(headline(comparison))
    if verdict is not None:
        was = verdict["comparison"]["status"]
        if was != comparison.status:
            say(f"The recorded verdict was {was}. This rerun does not match it.")
            status = 1
        say("")
        say("Blinding, as recorded:")
        for fact in blinding_facts(verdict):
            say(f"  {fact}")
    say("")
    say(f"Checked in {time.monotonic() - start:.0f} s. Freeze hash: {record['freeze_hash']}")
    return status


def as_json(path: Path) -> str:
    return json.dumps(read_json(path), indent=2)
