"""Print the results table from the recorded verdicts. Nothing here is typed by hand.

    python evals/table.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def percent(value) -> str:
    if value is None:
        return "-"
    if value < 0.0001:
        return f"{value * 100:.1e}%"
    return f"{value * 100:.2f}%"


def row(case: dict) -> str:
    folder = HERE / "runs" / case["name"]
    verdict_path = folder / "verdict.json"
    if not verdict_path.exists():
        stopped = folder / "stopped.txt"
        reason = " ".join(stopped.read_text(encoding="utf-8").split()) if stopped.exists() else "no verdict recorded"
        result = "could not run the authors' code" if reason.startswith("Could not run the authors' code") else "STOPPED"
        note = (case.get("note") or reason[:300]).replace("|", "/")
        return f"| {case['name']} | {case['field']} | {case['paper']} | {case.get('posted', '')} | {result} | - | - | - | {note} |"
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    comparison = verdict["comparison"]
    rows = comparison["rows"]
    within = sum(1 for r in rows if r["within"])
    blind = verdict["blinding"]
    recall = blind.get("recall") or {}
    memory = f"{recall.get('matched', 0)} of {recall.get('total', 0)}" if recall else "not run"
    return (
        f"| {case['name']} | {case['field']} | {verdict['paper']['ref']} | {verdict['paper'].get('first_public', '')} "
        f"| {comparison['status']} | {percent(comparison['max_error'])} | {within} of {len(rows)} | {memory} | {case.get('note', '')} |"
    )


def main() -> None:
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    print("| Case | Field | Paper | First posted | Result | Max error | Within 5% | Memory check matched | Note |")
    print("|---|---|---|---|---|---|---|---|---|")
    for case in cases:
        print(row(case))


if __name__ == "__main__":
    main()
