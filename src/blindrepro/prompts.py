"""Every instruction any agent receives. All of it is written into the run's record."""

SCOPE = """paper_full.txt holds a research paper. A researcher wants to test whether this result can be reproduced from the paper alone: {target}

Write spec.json with this shape:
{{
  "claim": "one or two sentences stating the result being tested, with its setting and assumptions, and no target values",
  "quantities": [
    {{"key": "snake_case_name", "description": "exact definition with conditions, enough for an independent expert to compute it, and no target values", "units": "units or 'dimensionless'"}}
  ],
  "paper_values": {{"snake_case_name": 1.23}},
  "redact": ["exact substrings of paper_full.txt to blank"],
  "not_computable": ""
}}

Rules:
- quantities covers the target and nothing else, at most 30 entries. Each must be a single number or a list of numbers. If the target is an equation, choose evaluation points stated in the paper.
- paper_values holds each number exactly as the paper prints it. Use null where the paper prints no number.
- redact lists every string that prints a target value or gives it away: table rows, sentences of results, figure captions quoting the values, the abstract's numbers. Copy each string character for character, keep each as short as possible, and search the whole file, because results repeat. Keep every equation, method, parameter and input needed to do the computation.
- If the target cannot be computed from the paper on a laptop in about ten minutes with no outside dataset, write the reason in not_computable and leave the rest empty.

Do not compute anything. Finish by writing spec.json and stop."""

DERIVE = """paper.txt is a research paper with its target values removed; removed parts read "[value removed]". spec.json lists what to compute.

Write derive.py in this folder. It must compute every quantity and print exactly one JSON object as its last line of output, mapping each key in spec.json to a number or list of numbers, or to null if you could not compute it. Never guess a value.

You have: Python {python} with the standard library and these packages only: {packages}. Use the run tool to execute derive.py and read its output, then fix and repeat. Scripts have no network, cannot start other processes, can only touch files in this folder, and get {seconds} seconds and {memory_mb} MB per run. Do not have derive.py read paper.txt.

Rules:
- Compute each value from the method the paper states, or from first principles when it points to a standard result. Do not type a remembered or published result in as an answer.
- Where the paper leaves a choice open, take the most defensible reading and carry on.
- Write notes.md with one line for each assumption you made and each constant you took from memory rather than from the paper, saying where you believe it comes from. This is part of the record.
- You will never see the authors' code. Finish when derive.py prints every key. Then stop, with a one-line status."""

RECALL = """This is a memory check. You have no tools and no paper. Do not derive or calculate anything.

Paper: {paper}
Result: {claim}

From memory alone, what are these values as published?
{quantities}

Reply with one JSON object mapping each key to the published number as you recall it, or to null if you do not recall it. Null is the expected answer when you do not actually remember. Reply with the JSON only."""

ADAPTER = """code/ holds the public code released by the authors of a paper, at commit {commit}. spec.json lists quantities the paper reports.

Write adapter.py in this folder. Run from this folder, it must obtain each quantity by running the authors' code and print exactly one JSON object as its last line of output, mapping each key to a number or list of numbers, or to null if their code does not produce it.

Write requirements.txt with the pip packages their code needs, one per line, pinned to versions from the code's era if it needs that. The run tool builds that environment and runs adapter.py. Scripts have no network, can only write in this folder, and get {seconds} seconds and {memory_mb} MB per run.

Rules:
- Call their functions and scripts with the settings the paper uses. Do not reimplement their method and do not change it. Add code/ to sys.path yourself if needed.
- Do not edit anything under code/. If their code cannot run without an edit, make the smallest one and say why in notes.md. Every edit is recorded and reported.
- If the repository stores precomputed outputs but the code that made them cannot run, do not read those outputs as if you had run the code. Treat it as a failure to run.
- If you cannot get their code to run after honest attempts, write could_not_run.md: what you tried, the exact error and what is missing. Failing to run is a useful finding. Do not work around it by writing your own version.
- Write notes.md with one line per choice you made about settings.
Finish, then stop with a one-line status."""

EXPLAIN = """A blind derivation and the authors' code disagree. derivation/ holds the blind side, authors/ holds the authors' code and the adapter that called it, comparison.json holds the numbers, and spec.json defines the quantities.

Find the first concrete point where the two calculations differ for each quantity marked within=false: a formula, a constant, a unit, a parameter, a definition or a numerical choice. Name the file and line on each side. If you cannot find it, say so. Say whether the difference looks like a paper ambiguity, an error on the blind side, or an issue in the authors' code, and label that as your judgment. Reply in under 200 words. You cannot run anything. Do not claim more than you checked."""
