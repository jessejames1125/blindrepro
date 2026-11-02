"""Command line entry point."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from importlib import resources
from pathlib import Path

from . import __version__
from .judges import JudgeError, make_judge


# The freeze hash of each bundled demo, so a demo folder changed and rehashed is refused too.
DEMO_HASHES: dict[str, str] = {
    "lawson": "0da2b99365c949607bc6b88b1c8e692268f27f2e683bca2556da58b720f996d2",
}


def _bundled(name: str) -> Path | None:
    root = resources.files("blindrepro") / "data" / name
    return Path(str(root)) if root.is_dir() else None


def _demo(args) -> int:
    from .verify import verify

    source = _bundled(args.case)
    if source is None:
        print(f"No demo named {args.case}. Try: blindrepro demo lawson")
        return 2
    with tempfile.TemporaryDirectory(prefix="blindrepro-demo-") as scratch:
        bundle = Path(scratch) / args.case
        shutil.copytree(source, bundle)
        if args.tamper:
            target = bundle / "frozen" / "blind" / "derive.py"
            target.write_text(target.read_text(encoding="utf-8") + "\n# one line added after the freeze\n", encoding="utf-8")
            print("Added one comment line to the frozen derivation. Checking the record:")
            code = verify(bundle, say=print, warn=False)
            print()
            print("That refusal is the demo: a changed file no longer matches its hash. Anyone can rehash a")
            print("folder, so compare the freeze hash with one published before the comparison (verify --expect).")
            return 0 if code == 2 else 1
        if args.full:
            print("Replaying a recorded blind run: no model, no key. The hashes, the derivation and the authors' code run for real.")
        else:
            print("Replaying a recorded blind run: no model, no key. The hashes, the derivation and the comparison run for real.")
        code = verify(bundle, skip_authors=not args.full, say=print, warn=False, expect=DEMO_HASHES.get(args.case, ""))
    print()
    if not args.full:
        print("Add --full to rerun the authors' code too (the Lawson case takes about 5 minutes).")
    print("Next: blindrepro demo lawson --tamper   |   blindrepro doctor   |   blindrepro run <paper> --target \"...\" --code <repo>")
    return code


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()[:48] or "run"


def _run(args) -> int:
    from .envs import InstallFailed
    from . import pipeline
    from .pipeline import Case, RunStopped, show

    out = Path(args.out) if args.out else Path("blindrepro-runs") / _slug(args.paper)
    case = Case(
        paper=args.paper,
        target=args.target,
        code=args.code,
        out=out,
        commit=args.commit or "",
        tolerance=args.tolerance,
        seconds=args.script_seconds,
        memory_mb=args.script_memory_mb,
        minutes=args.agent_minutes,
        allow_packages=args.allow_package or [],
        show_values=args.show_values,
        skip_recall=args.skip_memory_check,
        stop_after_freeze=args.stop_after_freeze,
        model_cutoff=args.model_cutoff or "",
        spec=args.spec or "",
    )
    print("Note: this runs the authors' code on your machine under the guard, which is not a security boundary. Use a container for code you do not trust.")
    judge = make_judge(args.judge, args.model, args.effort)
    try:
        verdict = pipeline.run_case(case, judge)
    except (RunStopped, InstallFailed) as stopped:
        print(stopped)
        out.mkdir(parents=True, exist_ok=True)
        (out / "stopped.txt").write_text(f"{stopped}\n", encoding="utf-8", newline="\n")
        return 3
    print()
    show(verdict)
    print()
    print(f"Paste-ready note: {out / 'verdict.md'}")
    return 0 if verdict["comparison"]["status"] == "REPRODUCED" else 1


def _verify(args) -> int:
    from .verify import verify

    return verify(Path(args.folder), skip_authors=args.skip_authors, expect=args.expect or "")


def _doctor(_args) -> int:
    from .doctor import run

    return run()


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        prog="blindrepro",
        description="An agent re-derives a published result from the paper alone, then code compares it with the authors' own code.",
    )
    parser.add_argument("--version", action="version", version=f"blindrepro {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    demo = commands.add_parser("demo", help="replay a recorded blind run; needs no account or key")
    demo.add_argument("case", nargs="?", default="lawson")
    demo.add_argument("--tamper", action="store_true", help="change the frozen record and watch the check refuse it")
    demo.add_argument("--full", action="store_true", help="also rerun the authors' code instead of using its sealed values")
    demo.set_defaults(func=_demo)

    run = commands.add_parser("run", help="run a new blind reproduction")
    run.add_argument("paper", help="arxiv:ID, a URL to a PDF, or a local .pdf, .tex, .txt or .md file")
    run.add_argument("--target", required=True, help='the result to test, such as "Table 3" or "Eq. 12 at T = 15 keV"')
    run.add_argument("--code", required=True, help="the authors' repository: a URL or a local git folder")
    run.add_argument("--commit", help="the commit to use; default is the latest")
    run.add_argument("--out", help="the run folder; default is blindrepro-runs/<paper>")
    run.add_argument("--judge", default="claude", help="claude (default) or api; or recorded:<folder>, which replays a past run's files")
    run.add_argument("--model", help="model name or alias for the judge")
    run.add_argument("--effort", default="high", help="effort level for the claude judge")
    run.add_argument("--tolerance", type=float, default=0.05, help="largest relative error that counts as reproduced; fixed before the freeze (default 0.05)")
    run.add_argument("--spec", help="a spec.json you wrote yourself, instead of the scoping step")
    run.add_argument("--allow-package", action="append", help="add a package the blind agent may import; cannot be the authors' own")
    run.add_argument("--show-values", action="store_true", help="leave target values in the paper the agent reads")
    run.add_argument("--skip-memory-check", action="store_true", help="skip asking the model for the values from memory")
    run.add_argument("--stop-after-freeze", action="store_true", help="stop at the freeze so you can publish the hash, then run again to finish")
    run.add_argument("--model-cutoff", help="the model's training cutoff as YYYY-MM, when it is not known to this tool")
    run.add_argument("--script-seconds", type=int, default=600, help="time limit for each script run")
    run.add_argument("--script-memory-mb", type=int, default=4096, help="memory limit for each script run")
    run.add_argument("--agent-minutes", type=int, default=30, help="time limit for each agent session")
    run.set_defaults(func=_run)

    check = commands.add_parser("verify", help="check a finished run again with no model")
    check.add_argument("folder")
    check.add_argument("--skip-authors", action="store_true", help="use the recorded authors' values instead of rerunning their code")
    check.add_argument("--expect", help="the freeze hash published before the comparison; refuse the record if it differs")
    check.set_defaults(func=_verify)

    doctor = commands.add_parser("doctor", help="say what is missing")
    doctor.set_defaults(func=_doctor)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except JudgeError as error:
        print(error)
        return 3


if __name__ == "__main__":
    sys.exit(main())
