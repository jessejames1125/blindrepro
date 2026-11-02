# How the blinding works, and where it stops

The claim of a blind run is narrow: the numbers came from an agent that had the paper and did not have the authors' code. This page lists what supports that claim and what does not.

## What the tool enforces

| Step | What happens | Where to check it |
|---|---|---|
| Scope | A first agent reads the paper and lists the quantities, the values it prints, and the passages that give them away. It sees no code. | `scope/spec.json` |
| Redact | Those passages and all links to code hosts are blanked by code, not by a model. | `freeze.json`: `redaction` |
| Derive | The blind agent works in a new temp folder with `paper.txt` and the quantity list. The authors' code has not been downloaded yet. | `freeze.json`: `frozen_at`, and `code_record.json`: `fetched_at` |
| Tools | The agent has Read, Write, Edit, Grep, Glob and one `run` tool. No shell, no web, no MCP servers but ours, no settings or CLAUDE.md files. The `claude` command's `--restricted` flag keeps its file tools inside the folder. | `freeze.json`: `tools_offered`, `transcript.jsonl` |
| Run | `run` executes `derive.py` under a Python audit hook that blocks network, other processes, and file access outside the folder, with a clean environment, a clock and a memory cap. Blocked attempts are logged. | `script_runs.jsonl` |
| Packages | The agent cannot add packages, because a package could be the authors' code. The researcher can, with `--allow-package`. | `freeze.json`: `allowed_packages` |
| Freeze | The derivation runs once more in a fresh folder. Its output becomes `results.json`. Every file is hashed, along with the tolerance, model, versions and date. | `freeze.json`: `freeze_hash` |
| Memory check | With no paper and no tools, the model is asked for the values. | `probe/` |
| Adapter | Only now is the code fetched. A second agent writes `adapter.py` to call it. It sees the quantity list and never the derivation or its values. Edits to the authors' code are recorded as a diff. | `authors/` |
| Compare | Plain arithmetic in `compare.py`. | `compare/comparison.json` |
| After the fact | Code searches the text the agent read for the target values (leak check) and searches `derive.py` for typed-in copies of them. Both are reported, neither changes the verdict. | `verdict.json`: `leaks`, `literals` |

`blindrepro verify <folder>` reruns all of this with no model and refuses a record whose hash does not match.

`evals/escape_test.py` asks a real agent under these settings to break out. Its last result is in `evals/escape-test.json`.

## What this cannot prove

**The model may have seen the paper or the code in training.** This is the largest gap, and no tool can close it from the outside. Two partial checks:

- The memory check asks for the values with nothing in front of the model. A match means agreement is weaker evidence. A null does not prove the model never saw the work, because knowledge can shape a derivation without being recallable as a number.
- The run reports the paper's first posting date against the model's published training cutoff. A paper posted after the cutoff should not be in training data. That rests on the vendor's stated date, and related earlier work can still be in training.

To get a clean test of the method, include papers posted after the cutoff, as `evals/` does.

**The hash does not prove when.** It proves the files have not changed since the freeze. It does not prove the freeze came before the comparison, or that the operator did not run ten times and keep the best. To prove order, run with `--stop-after-freeze`, publish the hash somewhere with a public timestamp, then finish the run. Publishing every attempt is the only answer to selection, and that is a matter of the operator's honesty.

**The guard is not a security boundary.** It uses CPython audit hooks, plus blocks on foreign calls, links and native modules from the work folder. The first version let a real agent read both test secrets through `ctypes` and through hard links, which is why those blocks exist (see the changelog). Assume a determined attacker can find another way through compiled code. It catches accidents and ordinary model behavior, and each draft script is kept in the transcript for a reader to inspect. If you need more, run the whole tool in a container with no network after packages are installed.

**The record of what the agent saw has gaps with the `claude` judge.** The `claude` command adds some context of its own, such as date, platform and the signed-in account's email, which is not in the transcript. With `--judge api`, the request bodies are the full record.

**Reading the paper is not blind.** The agent reads the method, the formulas and any intermediate numbers left in the text. Redaction removes what a model flagged and is checked by a number search at three or more significant digits. Values that appear in figures are gone, because only text reaches the agent, but so is any method detail that only a figure holds.

**Memory fills gaps.** When a paper cites a standard formula, the agent may use it from memory and must list it in `notes.md`. A wrong recalled constant shows up as a divergence. A right one means the result rests on that recollection.

**Agreement is not truth.** Two calculations can share a wrong assumption taken from the paper. Disagreement does not say who is wrong. The explanation in the verdict is a model's reading and has not been checked.
