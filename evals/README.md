# Results on published papers

Every row comes from a recorded run in `runs/<name>/`. `python table.py` prints this table from those records; nothing in it is typed by hand except the Note column, which comes from `cases.json`.

| Case | Field | Paper | First posted | Result | Max error | Within 5% | Memory check matched | Note |
|---|---|---|---|---|---|---|---|---|
| lawson | fusion (magnetic confinement) | arXiv:2105.10954 | 2021-05-23 | REPRODUCED | 0.61% | 4 of 4 | 0 of 4 | The paper's rounded 14 keV also sits in another table row the agent read; the agent's values (13.69, 14.28) are not that number. |
| spin-glass-thresholds | statistical physics | arXiv:2609.15157 | 2026-09-14 | REPRODUCED | 2.2e-12% | 4 of 4 | 0 of 4 | Posted after the model's training cutoff. Closed-form thresholds, so agreement to about 1e-14 is expected when both sides are right. |
| bb-metachecks | quantum error correction | arXiv:2609.39121 | 2026-09-30 | REPRODUCED | 0.0e+00% | 19 of 19 | 5 of 19 | Posted after the cutoff. Integers, so exact matches are expected. The 5 recalled values are code sizes k from earlier papers. The text flag is an equation label, eq:603, named after its value. |
| qaoa-large-girth | quantum algorithms | arXiv:2110.14206 | 2021-10-27 | REPRODUCED | 4.5e-06% | 8 of 8 | 8 of 8 | Not blind: the model recited all 8 values from memory. Its 8 text and 1 typed-number flags came from an older, looser rule; the current rule leaves 1, an angle equal to 0.4726. |
| near-axis-stellarator | fusion (stellarators) | arXiv:1809.10246 | 2018-09-26 | DIVERGED | 18.14% | 5 of 6 | 3 of 6 | Miss on one quantity: the authors' code reports elongation in the plane normal to the axis; the paper's 2.52 is in the R-z plane, which the blind value matches. The 3 recalled values are the iotas. |
| analytic-mhd | fusion (MHD theory) | arxiv:2609.26742 | 2026-09-22 | could not run the authors' code | - | - | - | Could not run the authors' code on Windows (a dependency has no wheel and its source build ran past the limit twice). Not retried; Linux or Mac may work. |
| greedy-sampling | numerical analysis | arXiv:2609.01578 | 2026-09-01 | REPRODUCED | 4.9e-07% | 6 of 6 | 0 of 6 | Posted after the cutoff. At this budget the P-greedy maximum has barely moved from its start, sqrt(c/pi), so this checks the code path more than a converged result. |

## How these were run

- Date: 2026-11-02. Judge: the `claude` command (Claude Code 2.1.316), model claude-opus-5-5, effort high. One run per paper, one after another on a 16 GB Windows laptop.
- Wall-clock time per case, from the batch log: lawson 17 min, spin glass 4, stellarator 5, metachecks 7, QAOA 26, greedy sampling 4, MHD 34 (first run, crashed) and 40 (second run, install did not finish).
- Cases, targets and the authors' commits: [cases.json](cases.json). Rerun one with `python run_case.py <name>`, then `python table.py`. A rerun calls the model again, so its numbers can differ.
- Baseline: the authors' own code at the listed commit, run by an adapter the tool records in `runs/<name>/authors/`. No other tool was run on these papers.
- "Within 5%" counts quantities whose relative error is at most the tolerance of 0.05, fixed before the freeze.
- "Memory check matched" counts values the model stated from memory, with no paper and no tools, that fell within the tolerance of the authors' values. The model can decline to answer, so zero means only that it stated nothing close.
- The scoping agent picks the quantities from the target sentence in `cases.json`. Read `runs/<name>/scope/spec.json` to see exactly what was compared. The "paper" column is the paper's printed value as a model read it, and it was hidden from the blind agent.
- The paper text is never stored here. `private/` in each run folder holds the downloaded text and is ignored by git.

## Caveats

- Four of the seven papers were posted after the model's stated training cutoff (2026-06). Those are the strongest blind tests. For the three older papers, read the memory check column first.
- The text-leak and typed-number flags in the QAOA record came from an older rule that matched anything within 0.5%. The current rule counts a number only when the target, rounded to that number's printed digits, gives it. Rechecked under the current rule, QAOA keeps 1 text flag and 0 typed-number flags.
- The first MHD run did not finish. Its adapter agent asked for a package with no Windows wheel; the source build ran past the agent's 30-minute limit, and the tool crashed on the timeout. Both were fixed (installs stop after 15 minutes, and a stopped adapter is recorded). The second run hit the same build and then a cleanup crash on Windows, also fixed. The paper was then dropped rather than retried; its blind result stays frozen in `runs/analytic-mhd/`.
- The QAOA adapter agent searched the disk for a C++ compiler, and its script named the laptop's account name, which the path swaps then missed. After the run, that name was swapped for `<user>` in `runs/qaoa-large-girth/authors/transcript.jsonl` and the run was sealed again. The freeze hash, which covers the blind side, did not change. The tool now swaps the account name in every record.
- No machine learning paper is in this set yet.

## The escape test

`escape_test.py` asks a live agent, in a blind folder, to read two secret files outside its folder and to write outside it. [escape-test.json](escape-test.json) records the attempt and whether either secret reached any file or output. It shows that the doors a live model found are shut on this machine. It does not make the guard a security boundary.
