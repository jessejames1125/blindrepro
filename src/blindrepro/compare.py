"""Arithmetic only. No model takes part in this step."""

from __future__ import annotations

import ast
import json
import math
from dataclasses import dataclass, field

REPRODUCED = "REPRODUCED"
DIVERGED = "DIVERGED"
NOT_COMPARED = "NOT COMPARED"


@dataclass
class Row:
    key: str
    derived: float | None
    authors: float | None
    paper: float | None
    error: float | None
    within: bool
    note: str = ""


@dataclass
class Comparison:
    rows: list[Row] = field(default_factory=list)
    tolerance: float = 0.05
    status: str = NOT_COMPARED
    max_error: float | None = None
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "tolerance": self.tolerance,
            "max_error": self.max_error,
            "reason": self.reason,
            "rows": [vars(r) for r in self.rows],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Comparison":
        return cls(
            rows=[Row(**r) for r in data["rows"]],
            tolerance=data["tolerance"],
            status=data["status"],
            max_error=data["max_error"],
            reason=data.get("reason", ""),
        )


def flatten(values: dict) -> dict[str, float | None]:
    """Lists become key[0], key[1]; anything that is not a finite number becomes None."""
    flat: dict[str, float | None] = {}
    for key, value in values.items():
        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                flat.update(flatten({f"{key}[{index}]": item}))
        elif isinstance(value, bool):
            flat[key] = float(value)
        elif isinstance(value, (int, float)) and math.isfinite(value):
            flat[key] = float(value)
        else:
            flat[key] = None
    return flat


def relative_error(derived: float, authors: float) -> float:
    """Measured against the authors' value. Plain difference when their value is zero."""
    if authors == 0:
        return abs(derived)
    return abs(derived - authors) / abs(authors)


def compare(
    derived: dict | None,
    authors: dict | None,
    paper: dict | None = None,
    tolerance: float = 0.05,
    expected_keys: list[str] | None = None,
) -> Comparison:
    if derived is None:
        return Comparison(tolerance=tolerance, reason="The blind derivation produced no values.")
    if authors is None:
        rows = [
            Row(k, v, None, flatten(paper or {}).get(k), None, False, "authors' code gave no value")
            for k, v in flatten(derived).items()
        ]
        return Comparison(rows=rows, tolerance=tolerance, reason="The authors' code did not produce values.")
    flat_d, flat_a, flat_p = flatten(derived), flatten(authors), flatten(paper or {})
    keys = list(flat_a)
    keys += [k for k in flat_d if k not in flat_a]
    for key in expected_keys or []:
        if key not in keys and not any(k.startswith(key + "[") for k in keys):
            keys.append(key)
    rows = []
    for key in keys:
        d, a, p = flat_d.get(key), flat_a.get(key), flat_p.get(key)
        if d is None:
            rows.append(Row(key, None, a, p, None, False, "blind side gave no value"))
        elif a is None:
            rows.append(Row(key, d, None, p, None, False, "authors' code gave no value"))
        else:
            error = relative_error(d, a)
            rows.append(Row(key, d, a, p, error, error <= tolerance))
    errors = [r.error for r in rows if r.error is not None]
    both = [r for r in rows if r.error is not None]
    if not both:
        return Comparison(rows, tolerance, NOT_COMPARED, None, "No quantity had a value on both sides.")
    status = REPRODUCED if all(r.within for r in rows) else DIVERGED
    return Comparison(rows, tolerance, status, max(errors))


def parse_result_line(stdout: str) -> dict | None:
    """The last line of output that is a JSON object is the script's answer."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            return parsed if isinstance(parsed, dict) else None
    try:
        parsed = json.loads(stdout)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def literal_check(source: str, values: dict[str, float | None], rel: float = 0.001) -> list[dict]:
    """Numbers typed into the derivation that match a target value. A flag for a human, not a verdict."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            number = float(node.value)
            if abs(number) < 1000 and float(number).is_integer():
                continue
            for key, value in values.items():
                if value and abs(number - value) <= rel * abs(value):
                    hits.append({"key": key, "literal": node.value, "line": node.lineno})
    return hits
