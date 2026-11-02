# Blind reproduction: Greedy sampling designs via reduced basis methods: optimal recovery in the uniform norm

**Result: REPRODUCED: max error 4.9e-07%, limit 5%.**

- Paper: arXiv:2609.01578 https://arxiv.org/abs/2609.01578
- Authors' code: https://github.com/Zeppo1994/Gelfand-Numbers-and-P-Greedy at 9d20e919fcaa2a145f3df5350bb509a762a0143f
- Target: The numerical experiment for the Paley-Wiener sinc kernel on [-1, 1]: the P-greedy maximum of the power function and the covariance-eigenvalue-tail lower bound, at the measurement budgets the paper's experiment uses
- Claim tested: For the Paley-Wiener (band-limited sinc) kernel K_c(s,t) = sin(c(s-t))/(pi(s-t)) on D=[-1,1] with N_eff = 2c/pi in {20, 40, 80}, the P-greedy estimate of the linear sampling width (the maximum of the power function over the candidate grid after m greedy nodes) and the discrete Gauss-Legendre covariance-eigenvalue-tail lower bound on the Gelfand width are both approximately flat (near sqrt(c/pi)) up to n = N_eff and of comparable size, before decaying super-exponentially.

## Values

```
quantity                        blind  authors' code     error
----------------------------  -------  -------------  --------
pgreedy_max_power_neff20_m20   3.1623         3.1623  0.0e+00%  ok
gelfand_lower_neff20_n20      0.46881        0.46881  3.9e-08%  ok
pgreedy_max_power_neff40_m40   4.4721         4.4721  0.0e+00%  ok
gelfand_lower_neff40_n40      0.49485        0.49485  1.4e-07%  ok
pgreedy_max_power_neff80_m80   6.3242         6.3242  0.0e+00%  ok
gelfand_lower_neff80_n80      0.51946        0.51946  4.9e-07%  ok
```

Error is |blind - authors| / |authors|, or the plain difference where the authors' value is 0. The arithmetic is done by code, not a model.
Paper values, where shown, were read from the paper by a model and were hidden from the blind agent.

## What the blind agent says it assumed or took from memory

- Kernel evaluated as (c/pi)*numpy.sinc(c(s-t)/pi), which is algebraically identical to sin(c(s-t))/(pi(s-t)) and gives c/pi on the diagonal (spec/paper eq. paleywiener).
- P-greedy run exactly as in Algorithm 1 / spec, gamma=1 on grid; no early break (epsilon_pow not specified in spec; pivots stay well above float floor for m <= N_eff).
- argmax taken on squared power (same maximizer as on Pow since sqrt is monotone), first index on ties (numpy.argmax).
- Gauss-Legendre nodes/weights from numpy.polynomial.legendre.leggauss, weights divided by 2 (spec).
- Eigenvalues of A_q via numpy.linalg.eigvalsh on the symmetrized matrix; tiny negative round-off eigenvalues clipped to 0 (they are >=0 exactly; effect negligible).
- No constants taken from memory.

## How the authors' code was called

# Notes

- Entry point: `code/paley_wiener.py::comparison_figure()`, the authors' driver for `figures/paley_wiener.png`. It calls `lower_bounds.sampling_vs_lower_bound` with the authors' `SPECS`. I called it unchanged. The figure is written to `./figures/`. I did not call `points_figure()` because it is not needed for these quantities.
- P-greedy value = `ne{N}_sampling_curve[m]` with m = N_eff. This is the authors' `PGreedy.pmax_[m]`, i.e. sqrt(max over grid of the clamped squared power) after m centers, in float64 on CPU (no CUDA).
- Authors' settings: sel_grid = 8000 / 8000 / 10000, equidistant `torch.linspace(-1,1,N)`. This matches spec. m_max = 70 / 110 / 140 is a budget, not the reported m. The value at m = N_eff does not depend on it. Default tol_p = 1e-14 (on the squared power): N_eff=20 stopped at 40 centers, the others used the full budget. All of these are past m = N_eff.
- Lower-bound value = `ne{N}_lower` at n = N_eff, from `PaleyWienerSincKernel.gelfand_lower_tails(n_cap)`. The default n_quad = max(200, int(8*N_eff)+50, n_cap+1) gives q = 210 / 370 / 690, which matches spec.
- DIFFERENCE from spec: the authors do not compute sqrt(sum_{k>=n} theta_k) exactly. In `_discrete_covariance_lower_tails`, every eigenvalue is first shifted down by 32*q*eps*max(theta_max, c/pi) and clipped at 0. Only the n=0 entry is reset to the exact trace. I report the authors' shifted value. The shift is about 1.5e-11 to 1e-10 per eigenvalue, so it changes the tail only around the 8th significant digit.
- The matrix is symmetrised, 0.5*(A+A^T), before `numpy.linalg.eigvalsh`. The weights are leggauss weights times 0.5, and the diagonal is sinc(0)*c/pi = c/pi, as in spec.
- Observation (not a change): at n = N_eff the P-greedy grid maximum is still about sqrt(c/pi): 3.16226, 4.47205 and 6.32424, against 3.16228, 4.47214 and 6.32456. The lower bound at n = N_eff is only about 0.47 to 0.52, roughly 7 to 12 times smaller. So the claim that the two are "near sqrt(c/pi) and of comparable size" at n = N_eff does not hold for the lower bound. The authors' own printed median ratio over the "reliable" range is 2.12 / 1.69 / 1.55.
- requirements.txt pins numpy 2.2.6, scipy 1.15.3, torch 2.6.0 and matplotlib 3.10.3. These satisfy the ranges in code/requirements.txt.
- I made no edits under code/.

## What was blinded

- Authors' code: fetched at 2026-11-02T11:38:40Z, after the derivation froze at 2026-11-02T11:38:35Z.
- Agent tools: Edit, Glob, Grep, Read, Write, run. No shell, no web.
- Scripts run under a guard with network, other processes and outside files off. Blocked attempts: 0. Refused tool calls: 0.
- Target values in the paper: 0 passages and 1 code links removed before the agent read it.
- Leak check: no target value found in the text the agent read.
- Typed-in answers: no number in derive.py matches a target value.
- Scripts: the agent's drafts import no networking, process or low-level module.
- Memory check: asked with no paper and no tools, the model stated 0 of 6 values, 0 within the limit.
- Model training cutoff: 2026-06 per the vendor. Paper first posted 2026-09-01, after that, so it should not be in training data.

## What was not blinded

- The agent read the paper, including its method. That is the point of the test.
- A model may have seen this paper or code during training. The memory check catches stated values, not everything a model absorbed.
- The freeze hash proves the files did not change later. It does not prove when they were made, or that the operator ran this once. To prove the order, publish the hash before comparing (--stop-after-freeze).
- The guard stops accidents and ordinary model behavior. A script that patches Python's own modules or loads native code could get around it; the flags above and the transcript are the check for that.
- The adapter that calls the authors' code was written by a model. It is in the record for inspection.

## Record

- Freeze hash (SHA-256): `3f0d07b844d67a07f857b280c9266caafc208f128f7bfdd04da273f67e0b53b1`
- Model: claude-opus-5-5, through claude-cli 2.1.316
- Tool: blindrepro 0.1.0. Run date: 2026-11-02.
- Python 3.12.13. Packages: mpmath==1.3.0, numpy==2.5.4, scipy==1.18.1, sympy==1.14.0.
- Prompts, transcripts and the derivation are in this folder. The paper's text and the authors' code are withheld as hashes and links.
- The whole folder, the authors' side included, is hashed once more at the end in `seal.json`.
- Check again: `blindrepro verify <this folder> --expect <freeze hash>`
