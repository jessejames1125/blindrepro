# Blind reproduction: Metachecks in Bivariate Bicycle Codes: Syndrome Distance, Measurement Faults, and Repair Limits

**Result: REPRODUCED: max error 0.0e+00%, limit 5%.**

- Paper: arXiv:2609.39121 https://arxiv.org/abs/2609.39121
- Authors' code: https://github.com/mohammad-rowshan/BB-Codes-Metachecks-Syndrome-Repair at b35ff72ad7d634fb922a5108d57b154497033d68
- Target: The table of standard codes: for each of the five standard bivariate bicycle codes, k, the metacheck rank r_M, and the syndrome distance d_S; plus the leader histogram for the [[144,12,12]] code and the p^2 coefficient of the exact repair curve
- Claim tested: For the five standard two-block bivariate bicycle (BB) codes [[72,12,6]], [[90,8,10]], [[108,8,10]], Gross [[144,12,12]] and [[288,12,18]] (generators and periods as listed in the paper's standard-code table, ring R=F2[x,y]/(x^l-1,y^m-1), selected check matrix H=[L_{b*}|L_{a*}]), the encoded dimension k, the metacheck rank r_M=dim ker H^T and the syndrome distance d_S (minimum nonzero weight of im H) take specific values. The test also covers the exact minimum-weight metasyndrome coset-leader histogram (c_0,c_1,c_2) of the Gross code and the p^2 coefficient of the exact minimum-weight syndrome-repair failure curve of the [[72,12,6]] code.

## Values

```
quantity                        blind  authors' code  paper     error
------------------------------  -----  -------------  -----  --------
k_72                               12             12     12  0.0e+00%  ok
r_M_72                              6              6      6  0.0e+00%  ok
d_S_72                              3              3      3  0.0e+00%  ok
k_90                                8              8      8  0.0e+00%  ok
r_M_90                              4              4      4  0.0e+00%  ok
d_S_90                              2              2      2  0.0e+00%  ok
k_108                               8              8      8  0.0e+00%  ok
r_M_108                             4              4      4  0.0e+00%  ok
d_S_108                             2              2      2  0.0e+00%  ok
k_144                              12             12     12  0.0e+00%  ok
r_M_144                             6              6      6  0.0e+00%  ok
d_S_144                             2              2      2  0.0e+00%  ok
k_288                              12             12     12  0.0e+00%  ok
r_M_288                             6              6      6  0.0e+00%  ok
d_S_288                             2              2      2  0.0e+00%  ok
gross_leader_c0                     1              1      1  0.0e+00%  ok
gross_leader_c1                    36             36     36  0.0e+00%  ok
gross_leader_c2                    27             27     27  0.0e+00%  ok
p2_coefficient_exact_repair_72    603            603    603  0.0e+00%  ok
```

Error is |blind - authors| / |authors|, or the plain difference where the authors' value is 0. The arithmetic is done by code, not a model.
Paper values, where shown, were read from the paper by a model and were hidden from the blind agent.

## What the blind agent says it assumed or took from memory

# Notes / assumptions

- Generators and periods for the five codes come from spec.json and match the paper text (108-qubit example). I typed in no other code constants.
- Monomial x^i y^j maps to index i + l*j (x index fastest), as the paper says. L_c has column g = c*g, and c* is (x,y) -> (x^-1, y^-1) with exponents taken mod l and m.
- H = H_Z = [L_{b*} | L_{a*}] (paper eq. sector). k = 2N - 2 rank(H). The script asserts H_X H_Z^T = 0 and rank H_X = rank H_Z.
- The metacheck space is ker H^T, the vectors orthogonal to every column of H. M is a basis of that space. Any basis gives the same d_S and the same leader histogram.
- d_S is the smallest nonzero weight in im H = ker M, i.e. the smallest number of columns of M that sum to zero. It is found by BFS: d_S = 1 + min over h of the BFS distance from 0 to column h, using only the other columns. This is exact because a shortest representation never repeats a column.
- The leader histogram c_w comes from a BFS over all 2^{r_M} metasyndromes, with the columns of M as generators (paper App. A). Only weights are counted, so the tie-break order does not matter.
- The p^2 coefficient is found by expanding P(p) = 1 - sum_w c_w p^w (1-p)^(N-w) exactly in sympy (paper eq. exact_repair).
- Sanity check: the running BB(3,3) example reproduces the paper's stated k=8, d_S=3 and histogram (1,9,6).
- I took no constants from memory.

## How the authors' code was called

# Notes

- Source: code/bb_manuscript_reproduce.py (the only script; README says it reproduces every exact quantity in the paper). No files under code/ were edited.
- adapter.py imports the module and calls the authors' `audit_code()` on their `STANDARD_CODES` with the same settings their `main()` uses by default (no `--quick`): exact_onesided=True, mu_max=16, cross_check=False. The spec quantities don't depend on these settings. I did not call `main()` itself because it only prints part of the values (r_M and the histograms go to a CSV); `audit_code` is the function `main()` calls.
- Code parameters (l, m, a, b) in STANDARD_CODES match spec.json for all five codes.
- H: the authors use H = H_Z = [L_b^T | L_a^T]. Since L_c^T = L_{c*}, this is the spec's [L_{b*} | L_{a*}]. Monomial index i + l*j matches the spec.
- k: the authors compute k = n - rank(H_X) - rank(H_Z), not the spec's 2N - 2 rank(H). These agree because rank H_X = rank H_Z here; their own check r_M = k/2 passes.
- r_M = number of rows of nullspace(H^T) = N - rank(H), as in the spec.
- d_S: the authors' `syndrome_distance(mcheck)` is exact only up to weight 4 and returns None above that. Every code gives 2 or 3, so this limit doesn't matter.
- Gross c_0, c_1, c_2: taken from the authors' breadth-first `coset_leaders(mcheck)` histogram, which is (1, 36, 27).
- p^2 coefficient: computed the authors' way, C(36,2) - c_2 = 603 (they derive it from d_S = 3). The spec defines it as the Taylor coefficient of 1 - sum_w c_w p^w (1-p)^(N-w). Working that expansion by hand with (c_0, c_1, c_2) = (1, 36, 27) gives -(630 - 36*35 + 27) = 603, so the two definitions agree. This hand check was not computed by adapter.py.
- The authors' built-in check against the manuscript reported no disagreements. Their P_repair(0.01) for [[72,12,6]] is 0.04842711803694644 (printed for information, not in spec).
- requirements.txt: numpy only, unpinned. The code needs nothing version-specific (Python >= 3.10 for int.bit_count). matplotlib is optional and isn't used by the adapter.
- Runtime is about 68 s, nearly all spent on the [[288,12,18]] one-sided and mu(g) searches that are part of audit_code under the default settings.

## What was blinded

- Authors' code: fetched at 2026-11-02T11:08:08Z, after the derivation froze at 2026-11-02T11:07:58Z.
- Agent tools: Edit, Glob, Grep, Read, Write, run. No shell, no web.
- Scripts run under a guard with network, other processes and outside files off. Blocked attempts: 0. Refused tool calls: 0.
- Target values in the paper: 61 passages and 1 code links removed before the agent read it.
- Leak check: 1 target values still appeared in the text the agent read (see verdict.json).
- Typed-in answers: no number in derive.py matches a target value.
- Scripts: the agent's drafts import no networking, process or low-level module.
- Memory check: asked with no paper and no tools, the model stated 5 of 19 values, 5 within the limit.
- Model training cutoff: 2026-06 per the vendor. Paper first posted 2026-09-30, after that, so it should not be in training data.

## What was not blinded

- The agent read the paper, including its method. That is the point of the test.
- A model may have seen this paper or code during training. The memory check catches stated values, not everything a model absorbed.
- The freeze hash proves the files did not change later. It does not prove when they were made, or that the operator ran this once. To prove the order, publish the hash before comparing (--stop-after-freeze).
- The guard stops accidents and ordinary model behavior. A script that patches Python's own modules or loads native code could get around it; the flags above and the transcript are the check for that.
- The adapter that calls the authors' code was written by a model. It is in the record for inspection.

## Record

- Freeze hash (SHA-256): `0c79313af4118a6d13fb7e9817b34e3fb53a0c75108ecf98fe465e2f12056419`
- Model: claude-opus-5-5, through claude-cli 2.1.316
- Tool: blindrepro 0.1.0. Run date: 2026-11-02.
- Python 3.12.13. Packages: mpmath==1.3.0, numpy==2.5.4, scipy==1.18.1, sympy==1.14.0.
- Prompts, transcripts and the derivation are in this folder. The paper's text and the authors' code are withheld as hashes and links.
- The whole folder, the authors' side included, is hashed once more at the end in `seal.json`.
- Check again: `blindrepro verify <this folder> --expect <freeze hash>`
