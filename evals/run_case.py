"""Run one case from cases.json for real, or print the command that does.

    python evals/run_case.py lawson            # live, uses the claude command
    python evals/run_case.py lawson --print    # show the blindrepro command only
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from blindrepro.cli import main as blindrepro

HERE = Path(__file__).resolve().parent


def arguments(case: dict) -> list[str]:
    args = [
        "run",
        case["paper"],
        "--target",
        case["target"],
        "--code",
        case["code"],
        "--commit",
        case["commit"],
        "--out",
        str(Path("evals") / "runs" / case["name"]),
        "--model",
        "opus",
        "--script-memory-mb",
        "2048",
    ]
    for package in case.get("allow_package", []):
        args += ["--allow-package", package]
    return args + case.get("extra", [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--print", action="store_true", dest="print_only")
    options = parser.parse_args()
    cases = {c["name"]: c for c in json.loads((HERE / "cases.json").read_text(encoding="utf-8"))}
    case = cases[options.name]
    if options.print_only:
        print("blindrepro " + " ".join(shlex.quote(a) for a in arguments(case)))
        return 0
    return blindrepro(arguments(case))


if __name__ == "__main__":
    sys.exit(main())
