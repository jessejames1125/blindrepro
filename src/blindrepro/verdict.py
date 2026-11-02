"""The two outputs: a table for the terminal and a note for a referee report or lab notebook."""

from __future__ import annotations

from .compare import Comparison


def number(value) -> str:
    if value is None:
        return "-"
    if value == 0:
        return "0"
    if value == int(value) and abs(value) < 1e7:
        return str(int(value))
    return f"{value:.5g}"


def percent(value) -> str:
    if value is None:
        return "-"
    if value < 0.0001:
        return f"{value * 100:.1e}%"
    return f"{value * 100:.2f}%"


def table(comparison: Comparison) -> str:
    has_paper = any(r.paper is not None for r in comparison.rows)
    headers = ["quantity", "blind", "authors' code"] + (["paper"] if has_paper else []) + ["error", ""]
    lines = []
    for row in comparison.rows:
        cells = [row.key, number(row.derived), number(row.authors)]
        if has_paper:
            cells.append(number(row.paper))
        mark = "ok" if row.within else (row.note or "MISS")
        lines.append(cells + [percent(row.error), mark])
    widths = [max(len(str(item[i])) for item in [headers] + lines) for i in range(len(headers))]

    def fmt(cells: list[str]) -> str:
        parts = [str(cells[0]).ljust(widths[0])]
        parts += [str(c).rjust(w) for c, w in zip(cells[1:-1], widths[1:-1])]
        parts.append(str(cells[-1]))
        return "  ".join(parts).rstrip()

    return "\n".join([fmt(headers), fmt(["-" * w for w in widths[:-1]] + [""])] + [fmt(c) for c in lines])


def headline(comparison: Comparison) -> str:
    if comparison.status == "NOT COMPARED":
        return f"NOT COMPARED: {comparison.reason}"
    limit = f"{comparison.tolerance * 100:g}%"
    missed = sum(not r.within for r in comparison.rows)
    tail = f"{missed} of {len(comparison.rows)} outside the limit. " if missed else ""
    return f"{comparison.status}: max error {percent(comparison.max_error)}, limit {limit}. {tail}".rstrip()


def blinding_facts(data: dict) -> list[str]:
    facts = []
    blind = data["blinding"]
    facts.append(f"Authors' code: fetched at {blind['code_fetched_at'] or 'never'}, after the derivation froze at {blind['frozen_at']}.")
    facts.append(f"Agent tools: {', '.join(blind['tools_offered']) or 'none'}. No shell, no web.")
    facts.append(
        f"Scripts run under a guard with network, other processes and outside files off. "
        f"Blocked attempts: {blind['guard_blocked']}. Refused tool calls: {blind['refused_calls']}."
    )
    redaction = blind["redaction"]
    if blind.get("values_shown"):
        facts.append("Target values in the paper: left visible, at the researcher's request.")
    else:
        facts.append(
            f"Target values in the paper: {redaction.get('strings_removed', 0)} passages and "
            f"{redaction.get('code_links_removed', 0)} code links removed before the agent read it."
        )
    leaks = blind.get("leaks", [])
    facts.append(
        "Leak check: no target value found in the text the agent read."
        if not leaks
        else f"Leak check: {len(leaks)} target values still appeared in the text the agent read (see verdict.json)."
    )
    literals = blind.get("literals", [])
    facts.append(
        "Typed-in answers: no number in derive.py matches a target value."
        if not literals
        else f"Typed-in answers: {len(literals)} numbers in derive.py match a target value (see verdict.json)."
    )
    recall = blind.get("recall")
    if recall is None:
        facts.append("Memory check: not run.")
    else:
        facts.append(
            f"Memory check: asked with no paper and no tools, the model stated {recall['stated']} of "
            f"{recall['total']} values, {recall['matched']} within the limit."
        )
    cutoff = blind.get("cutoff", {})
    facts.append(f"Model training cutoff: {cutoff.get('statement', 'unknown')}")
    return facts


NOT_BLINDED = [
    "The agent read the paper, including its method. That is the point of the test.",
    "A model may have seen this paper or code during training. The memory check catches stated values, not everything a model absorbed.",
    "The freeze hash proves the files did not change later. It does not prove when they were made, or that the operator ran this once. To prove the order, publish the hash before comparing (--stop-after-freeze).",
    "The guard stops accidents and ordinary model behavior. Native code could get around it.",
    "The adapter that calls the authors' code was written by a model. It is in the record for inspection.",
]


def verdict_markdown(data: dict) -> str:
    comparison = Comparison.from_dict(data["comparison"])
    paper = data["paper"]
    lines = [
        f"# Blind reproduction: {paper.get('title') or paper.get('ref')}",
        "",
        f"**Result: {headline(comparison)}**",
        "",
        f"- Paper: {paper.get('ref')} {paper.get('url', '')}".rstrip(),
        f"- Authors' code: {data['code']['url']} at {data['code'].get('commit') or 'unknown commit'}",
        f"- Target: {data['target']}",
        f"- Claim tested: {data['claim']}",
        "",
        "## Values",
        "",
        "```",
        table(comparison),
        "```",
        "",
        "Error is |blind - authors| / |authors|. The arithmetic is done by code, not a model.",
        "Paper values, where shown, were read from the paper by a model and were hidden from the blind agent.",
    ]
    code = data["code"]
    if code.get("modified"):
        lines += ["", "**The authors' code needed an edit to run.** See `authors/patch.diff`."]
    if code.get("could_not_run"):
        lines += ["", "## Authors' code did not run", "", code["could_not_run"].strip()]
    if data.get("explanation"):
        lines += ["", "## Where it diverged (a model's reading, not a checked claim)", "", data["explanation"].strip()]
    lines += ["", "## What was blinded", ""]
    lines += [f"- {fact}" for fact in blinding_facts(data)]
    lines += ["", "## What was not blinded", ""]
    lines += [f"- {item}" for item in NOT_BLINDED]
    run = data["run"]
    lines += [
        "",
        "## Record",
        "",
        f"- Freeze hash (SHA-256): `{data['blinding']['freeze_hash']}`",
        f"- Model: {run['model']}, through {run['judge']} {run['judge_version']}",
        f"- Tool: blindrepro {run['tool_version']}. Run date: {run['date']}.",
        f"- Python {run['python']}. Packages: {', '.join(run['packages'])}.",
        "- Prompts, transcripts and the derivation are in this folder. The paper's text and the authors' code are withheld as hashes and links.",
        "- Check again: `blindrepro verify <this folder>`",
        "",
    ]
    return "\n".join(lines)


def terminal_summary(data: dict) -> str:
    comparison = Comparison.from_dict(data["comparison"])
    parts = [table(comparison), "", headline(comparison), ""]
    parts += ["Blinding:"] + [f"  {fact}" for fact in blinding_facts(data)]
    parts += ["", f"Freeze hash: {data['blinding']['freeze_hash']}"]
    return "\n".join(parts)
