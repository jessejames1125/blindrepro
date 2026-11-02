# Blind reproduction: Direct construction of optimized stellarator shapes. II. Numerical quasisymmetric solutions

**Result: DIVERGED: max error 18.14%, limit 5%. 1 of 6 outside the limit.**

- Paper: arXiv:1809.10246 https://arxiv.org/abs/1809.10246
- Authors' code: https://github.com/landreman/pyQSC at cd75359ea47548d5db7ccb458c100085c04ba1bc
- Target: The rotational transform on axis and the related near-axis quantities the paper reports for the configurations of sections 5.1, 5.2 and 5.3
- Claim tested: Solving the first-order (Garren-Boozer) near-axis quasisymmetry equation (the Riccati-type ODE for sigma, eq. QA, with the periodicity condition fixing iota) for three prescribed magnetic axis shapes (a stellarator-symmetric quasi-axisymmetric axis, a quasi-helically symmetric axis, and a non-stellarator-symmetric quasi-axisymmetric axis), each in vacuum (I_2 = 0) with given eta_bar and sigma(0), gives specific values of the on-axis rotational transform and of the maximum elongation of the first-order elliptical flux-surface cross sections in the cylindrical R-z plane.

## Values

```
quantity                     blind  authors' code  paper     error
-------------------------  -------  -------------  -----  --------
iota_qa_sec51              0.41831        0.41831  0.418  5.3e-14%  ok
max_elongation_qa_sec51     2.3995         2.4137    2.4     0.59%  ok
iota_qh_sec52               1.9311         1.9311   1.93  4.6e-14%  ok
max_elongation_qh_sec52     2.5223         3.0813   2.52    18.14%  MISS
iota_asym_sec53            0.31118        0.31118  0.311  1.5e-10%  ok
max_elongation_asym_sec53   3.2866         3.3048   3.29     0.55%  ok
```

Error is |blind - authors| / |authors|, or the plain difference where the authors' value is 0. The arithmetic is done by code, not a model.
Paper values, where shown, were read from the paper by a model and were hidden from the blind agent.

## Where it diverged (a model's reading, not a checked claim)

Only `max_elongation_qh_sec52` is marked within=false. The blind side gives 2.522 and the authors' side gives 3.081.

**First point of difference:** the two sides measure elongation in different planes.

- **Blind side:** `derivation/derive.py` lines 137–144 convert (X1, Y1) to (R1, z1) using the l'/R0 transform. They then take the elongation in the cylindrical R-z plane, which is what spec.json asks for.
- **Authors' side:** `authors/code/qsc/calculate_r1.py` lines 129–136 compute p and q directly from X1s, X1c, Y1s, Y1c. That is the elongation in the plane perpendicular to the axis. The comment at lines 129–130 says (R,Z) could be used instead, but the code doesn't. `authors/adapter.py` line 27 reports this `max_elongation` as is, and `authors/notes.md` line 6 admits the mismatch.

The other inputs agree: the iota values match to about 1e-15, so the geometry, N and sigma match too. The QH axis has the largest shaping, which is likely why the two planes differ most there. In the other two cases the gap is under 1%.

**My judgment:** this is a definition mismatch on the authors' side, introduced by the adapter. It is not an error on the blind side and not a paper ambiguity. The blind value (2.522) matches the paper's 2.52. pyQSC's number is correct for the quantity it defines. I read the code but did not run either side.

## What the blind agent says it assumed or took from memory

- Signs s_G = s_psi = +1, B0 = 1, I2 = 0, as given in spec.json; G0 = s_G B0 L/(2 pi), with the axis length L from periodic trapezoid quadrature (spectrally accurate).
- Curvature and torsion use the standard Frenet formulas kappa = |r' x r''|/|r'|^3 and tau = (r' x r'').r'''/|r' x r''|^2. This tau matches the paper's db/dl = -tau n convention. These are textbook results taken from memory.
- The cylindrical-basis derivatives of the axis position use de_R/dphi = e_phi and de_phi/dphi = -e_R. This is standard vector calculus, taken from memory.
- N is counted as the net winding of atan2(n_R, n_z) over one toroidal transit. That angle increases when n rotates toward b about t (t ~ +e_phi). The sign follows from det[[X1c,X1s],[Y1c,Y1s]] = s_G s_psi = +1, which makes theta increase from n toward b. I derived this myself; it matches my memory of pyQSC's helicity convention (iota_N = iota + helicity*nfp, i.e. N = -helicity*nfp).
- The ODE is solved by Newton iteration on Fourier pseudo-spectral collocation (Np = 151, odd), with unknowns [iota-N, sigma_2..sigma_N], following section 3 of the paper. Re-running with Np = 201 changes iota by less than 4e-15.
- The elongation uses theta shifted by N*varphi (X1c = etabar/kappa, X1s = 0, Y1s = kappa/etabar, Y1c = kappa*sigma/etabar). This is an exact rewriting of the paper's expressions. The R-z ellipse elongation does not change under a rotation of theta, so varphi(phi) is not needed.
- The maximum over phi is taken over one field period, which is enough because of the field-period symmetry. It uses a 4000-point scan with trigonometric interpolation of sigma, then a bounded 1D refinement.

## How the authors' code was called

# Notes

- Code used: pyQSC (`code/qsc`), `Qsc.from_paper("r1 section 5.1" | "r1 section 5.2" | "r1 section 5.3")`. These are the authors' predefined Landreman–Sengupta–Plunk (2019) configurations. Their parameters match spec.json: axis coefficients, nfp, etabar, sigma0, I2=0, B0=1, sG=spsi=+1.
- Resolution: I used the constructor default `nphi=61`, the authors' setting. The adapter also prints nphi = 31/101/151/201 as a check. At nphi=61, iota has converged to about 1e-12 or better. max_elongation at nphi=61 differs from nphi=201 by up to about 2e-6 (QH case: 3.0812714 vs 3.0812691), because it comes from `fourier_minimum` interpolation.
- iota: I report `stel.iota`, which is iota itself and not iota - N. For section 5.2 the code finds helicity = -1, so `iotaN` = iota - 4 = -2.0689 and iota = 1.9311.
- **Difference from spec (max_elongation):** spec.json asks for the elongation in the cylindrical R-z plane, using the first-order (X1,Y1)->(R1,z1) transform of section 4.1. pyQSC's `r1_diagnostics` (calculate_r1.py lines 129-136) computes the elongation from (X1s, X1c, Y1s, Y1c). That is the elongation in the plane perpendicular to the magnetic axis. A comment in the code notes that (R,Z) could be used instead, but the code uses (X,Y). The code has no function that gives the R-z-plane first-order elongation. I report the code's `max_elongation` (the maximum over phi via `fourier_minimum`) for the three max_elongation keys. These numbers are the perpendicular-plane elongation, not the R-z-plane quantity defined in spec.json. I did not write my own R-z version, because that would reimplement the method. The package's own test (tests/test_configurations.py) checks these same values (2.41373705531443, 3.08125973323805, 3.30480616121377) as the "published examples".
- No files under code/ were edited.
- Requirements pinned to the code's era (numpy 1.26.4, scipy 1.11.4 — that version still provides `scipy.io.netcdf`, imported in qsc.py — and matplotlib 3.8.2, imported by qsc/plot.py). The run's "blocked file read" messages come from matplotlib scanning the system fonts at import. They are harmless.

## What was blinded

- Authors' code: fetched at 2026-11-02T10:28:29Z, after the derivation froze at 2026-11-02T10:28:20Z.
- Agent tools: Edit, Glob, Grep, Read, Write, run. No shell, no web.
- Scripts run under a guard with network, other processes and outside files off. Blocked attempts: 0. Refused tool calls: 0.
- Target values in the paper: 6 passages and 0 code links removed before the agent read it.
- Leak check: no target value found in the text the agent read.
- Typed-in answers: no number in derive.py matches a target value.
- Scripts: the agent's drafts import no networking, process or low-level module.
- Memory check: asked with no paper and no tools, the model stated 3 of 6 values, 3 within the limit.
- Model training cutoff: 2026-06 per the vendor. Paper first posted 2018-09-26, before that, so it may be in training data.

## What was not blinded

- The agent read the paper, including its method. That is the point of the test.
- A model may have seen this paper or code during training. The memory check catches stated values, not everything a model absorbed.
- The freeze hash proves the files did not change later. It does not prove when they were made, or that the operator ran this once. To prove the order, publish the hash before comparing (--stop-after-freeze).
- The guard stops accidents and ordinary model behavior. A script that patches Python's own modules or loads native code could get around it; the flags above and the transcript are the check for that.
- The adapter that calls the authors' code was written by a model. It is in the record for inspection.

## Record

- Freeze hash (SHA-256): `ca70e018545baf3c0596b8b364ac124abafcca7825ef5a046917908493e4ea18`
- Model: claude-opus-5-5, through claude-cli 2.1.316
- Tool: blindrepro 0.1.0. Run date: 2026-11-02.
- Python 3.12.13. Packages: mpmath==1.3.0, numpy==2.5.4, scipy==1.18.1, sympy==1.14.0.
- Prompts, transcripts and the derivation are in this folder. The paper's text and the authors' code are withheld as hashes and links.
- The whole folder, the authors' side included, is hashed once more at the end in `seal.json`.
- Check again: `blindrepro verify <this folder> --expect <freeze hash>`
