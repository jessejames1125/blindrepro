"""Arithmetic only. No model takes part in this step."""

from __future__ import annotations

import ast
import json
import math
import re
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


FORBIDDEN_IMPORTS = {
    "ctypes", "_ctypes", "cffi", "_winapi", "_posixsubprocess", "subprocess", "socket", "ssl",
    "urllib", "http", "requests", "httpx", "ftplib", "sqlite3", "mmap", "multiprocessing",
    "git", "pip", "site", "winreg", "msvcrt",
}


def import_check(source: str) -> list[str]:
    """Modules a derivation has no reason to import, so a reader can look closer."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found = set()
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        elif isinstance(node, ast.Call) and getattr(node.func, "id", "") == "__import__" and node.args:
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                names = [argument.value]
        found.update(name.split(".")[0] for name in names if name.split(".")[0] in FORBIDDEN_IMPORTS)
    return sorted(found)


INTERNALS = {
    "_getframe", "f_globals", "f_locals", "f_back", "f_builtins", "__closure__", "cell_contents",
    "__code__", "__globals__", "__builtins__", "addaudithook", "settrace", "setprofile",
}
PATCHED_MODULES = {"os", "sys", "io", "builtins", "ntpath", "posixpath", "genericpath", "nt", "posix", "pathlib", "stat"}


def tamper_check(source: str) -> list[str]:
    """Code that reaches into the interpreter or rewrites standard modules, which the guard
    cannot fully stop. A derivation has no reason to do either, so a reader should look."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in INTERNALS:
            found.add(node.attr)
        elif isinstance(node, ast.Name) and node.id in ("setattr", "delattr", "__builtins__"):
            found.add(node.id)
        targets = []
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete)):
            targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
        for target in targets:
            parts, root = [], target
            while isinstance(root, ast.Attribute):
                parts.insert(0, root.attr)
                root = root.value
            if parts and isinstance(root, ast.Name) and root.id in PATCHED_MODULES:
                found.add("assigns " + ".".join([root.id, *parts]))
    return sorted(found)


def significant_digits(printed: str) -> int:
    mantissa = re.match(r"[\d,]+(?:\.\d+)?", printed).group(0)
    return len(mantissa.replace(",", "").replace(".", "").lstrip("0"))


def rounds_to(number: float, digits: int, value: float) -> bool:
    """True when value, rounded to `digits` significant digits, gives number. Signs are ignored."""
    if number == 0 or digits <= 0:
        return number == value
    unit = 10.0 ** (math.floor(math.log10(abs(number))) - digits + 1)
    return abs(abs(number) - abs(value)) <= unit / 2 * (1 + 1e-9)


def digits_of(number: float) -> int:
    """Significant digits of a number as Python would print it; 1234.0 and 12000 count as 4 and 2."""
    number = abs(number)
    # Floats hold whole numbers exactly only up to about 1e15; past that, use their printed form.
    if number.is_integer() and number < 1e15:
        return len(str(int(number)).rstrip("0")) or 1
    return significant_digits(repr(number))


def matches(number: float, digits: int, value: float) -> bool:
    """True when number and value agree at the coarser of their two precisions, but never below 3 digits.

    A copy printed with more digits than the target is caught, and so is the target rounded.
    """
    if not (math.isfinite(number) and math.isfinite(value)):
        return False
    return rounds_to(number, min(digits, max(3, digits_of(value))), value)


def literal_check(source: str, values: dict[str, float | None]) -> list[dict]:
    """Numbers typed into the derivation that are a target value, rounded. A flag for a human, not a verdict."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            try:
                number = float(node.value)
            except OverflowError:
                continue
            if not math.isfinite(number):
                continue
            digits = digits_of(number)
            # Small integers and short numbers like 0.5 round from too many values to mean anything.
            if (abs(number) < 1000 and number.is_integer()) or digits < 3:
                continue
            # A minus sign is its own node, so the size is compared.
            for key, value in values.items():
                if value and matches(number, digits, value):
                    hits.append({"key": key, "literal": node.value, "line": node.lineno})
    return hits
