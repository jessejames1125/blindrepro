"""Copy a finished run into the package as the offline demo.

    python evals/bundle_demo.py lawson

Takes evals/runs/<name>, keeps what verify needs, and adds the files of the authors' code
that the adapter imports, at the recorded commit, fetched fresh from the authors' repository.
The paper text never goes in. The demo folder gets its own seal tied to the same freeze hash.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from blindrepro.record import seal

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "src" / "blindrepro" / "data"
KEEP = [
    "frozen",
    "scope/spec.json",
    "probe/recall.json",
    "compare/comparison.json",
    "authors/adapter.py",
    "authors/requirements.txt",
    "authors/notes.md",
    "authors/code_record.json",
    "authors/patch.diff",
    "verdict.json",
    "verdict.md",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--vendor", nargs="+", required=True, help="paths in the authors' repository to include, such as lib LICENSE")
    options = parser.parse_args()
    run = HERE / "runs" / options.name
    out = DATA / options.name
    shutil.rmtree(out, ignore_errors=True)
    for item in KEEP:
        source = run / item
        if source.is_dir():
            shutil.copytree(source, out / item)
        elif source.exists():
            (out / item).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, out / item)
    record = json.loads((run / "authors" / "code_record.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as scratch:
        clone = Path(scratch) / "code"
        subprocess.run(["git", "clone", "--quiet", record["url"], str(clone)], check=True)
        subprocess.run(["git", "-C", str(clone), "checkout", "--quiet", record["commit"]], check=True)
        for part in options.vendor:
            source = clone / part
            target = out / "authors" / "vendor" / part
            if source.is_dir():
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    patch = out / "authors" / "patch.diff"
    if patch.exists():
        subprocess.run(["git", "apply", "--directory=" + str((out / "authors" / "vendor").relative_to(Path.cwd())), str(patch)], check=True)
    freeze_hash = json.loads((out / "frozen" / "freeze.json").read_text(encoding="utf-8"))["freeze_hash"]
    sealed = seal(out, freeze_hash)
    print(f"Bundled {options.name}: freeze {freeze_hash}, demo seal {sealed['seal_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
