import json
import sys
from pathlib import Path

import pytest

from blindrepro.pipeline import Case


@pytest.fixture
def python():
    """Tests run scripts with the current interpreter; only the standard library is needed."""
    return Path(sys.executable)


@pytest.fixture(autouse=True)
def plain_env(monkeypatch, tmp_path):
    """Environments resolve to this interpreter, so tests never build or download anything."""
    from blindrepro import pipeline, verify

    monkeypatch.setattr(pipeline, "ensure_env", lambda packages: Path(sys.executable))
    monkeypatch.setattr(pipeline, "env_for_requirements", lambda path: Path(sys.executable))
    monkeypatch.setattr(verify, "ensure_env", lambda packages: Path(sys.executable))
    monkeypatch.setattr(verify, "env_for_requirements", lambda path: Path(sys.executable))


SPEC = {
    "claim": "The area of a unit circle.",
    "quantities": [
        {"key": "area", "description": "Area of a circle of radius 1", "units": "dimensionless"},
        {"key": "half", "description": "Half of that area", "units": "dimensionless"},
    ],
    "paper_values": {"area": 3.14159, "half": None},
    "redact": ["The area is 3.14159."],
}

PAPER = "A circle of radius 1 has area pi r^2.\nThe area is 3.14159.\nCode is at https://github.com/someone/circle.\n"


def make_authors_repo(folder: Path, area: str = "3.14159265") -> Path:
    import subprocess

    folder.mkdir(parents=True)
    (folder / "circle.py").write_text(f"AREA = {area}\n", encoding="utf-8")
    env_args = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "init", "-q", str(folder)], check=True)
    subprocess.run(["git", "-C", str(folder), "add", "."], check=True)
    subprocess.run(["git", *env_args, "-C", str(folder), "commit", "-q", "-m", "init"], check=True)
    return folder


def write_recording(folder: Path, derive: str, adapter: str | None, spec: dict | None = None) -> Path:
    (folder / "scope").mkdir(parents=True)
    (folder / "frozen" / "blind").mkdir(parents=True)
    (folder / "authors").mkdir(parents=True)
    (folder / "scope" / "spec.json").write_text(json.dumps(spec or SPEC), encoding="utf-8")
    (folder / "frozen" / "blind" / "derive.py").write_text(derive, encoding="utf-8")
    (folder / "frozen" / "blind" / "notes.md").write_text("assumed nothing\n", encoding="utf-8")
    if adapter is not None:
        (folder / "authors" / "adapter.py").write_text(adapter, encoding="utf-8")
    else:
        (folder / "authors" / "could_not_run.md").write_text("Their code needs a compiler that is missing.\n", encoding="utf-8")
    return folder


GOOD_DERIVE = 'import json, math\nprint(json.dumps({"area": math.pi, "half": math.pi / 2}))\n'
GOOD_ADAPTER = (
    'import json, sys\nsys.path.insert(0, "code")\nimport circle\n'
    'print(json.dumps({"area": circle.AREA, "half": circle.AREA / 2}))\n'
)


@pytest.fixture
def spec():
    return json.loads(json.dumps(SPEC))


@pytest.fixture
def case_for(tmp_path):
    def build(repo: Path, **options) -> Case:
        paper = tmp_path / "paper.txt"
        paper.write_text(PAPER, encoding="utf-8")
        return Case(paper=str(paper), target="the area", code=str(repo), out=tmp_path / "run", **options)

    return build
