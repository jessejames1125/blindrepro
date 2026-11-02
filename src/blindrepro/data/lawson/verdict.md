# Blind reproduction: Progress toward fusion energy breakeven and gain as measured against the Lawson criterion

**Result: REPRODUCED: max error 0.61%, limit 5%.**

- Paper: arXiv:2105.10954 https://arxiv.org/abs/2105.10954
- Authors' code: https://github.com/swurzel/lawson-criterion-paper at 4ae563bfc409db5fb4afb2f9930a3a4fafba4f0d
- Target: Table 3, the deuterium-tritium row only for magnetic confinement: the minimum triple product and the temperature where it occurs, at Q_fuel = 1 and Q_fuel = infinity, for the uniform-profile case
- Claim tested: For an idealized, steady-state (tau >> tau_E), spatially uniform, impurity-free equimolar D-T magnetic-confinement plasma with T = T_i = T_e and n = n_i = n_e, the triple product needed for a given fuel gain is n T tau_E = 3T^2 / [ (f_c + 1/Q_fuel) <sigma v>(T) eps_F / 4 - C_B T^{1/2} ] (Eq. triple_product_steady_state). The test is the minimum over T of this required triple product, and the temperature where the minimum occurs, for Q_fuel = 1 (fuel breakeven) and Q_fuel = infinity (ignition).

## Values

```
quantity                                             blind  authors' code    paper  error
----------------------------------------------  ----------  -------------  -------  -----
dt_min_triple_product_qfuel_1                   4.6491e+20     4.6482e+20  4.6e+20  0.02%  ok
dt_temperature_at_min_triple_product_qfuel_1        13.689         13.607       14  0.61%  ok
dt_min_triple_product_qfuel_inf                 2.9495e+21      2.945e+21  2.9e+21  0.15%  ok
dt_temperature_at_min_triple_product_qfuel_inf      14.275          14.25       14  0.18%  ok
```

Error is |blind - authors| / |authors|, or the plain difference where the authors' value is 0. The arithmetic is done by code, not a model.
Paper values, where shown, were read from the paper by a model and were hidden from the blind agent.

## What the blind agent says it assumed or took from memory

# Assumptions and constants from memory

- Bosch & Hale (1992) D-T cross-section S-factor coefficients (B_G=34.3827 keV^1/2, A1..A5=6.927e4, 7.454e8, 2.050e6, 5.2002e4, 0; B1..B4=63.8, -0.995, 6.981e-5, 1.728e-4; sigma in mb, E = CM energy in keV) are from memory of Bosch & Hale, Nucl. Fusion 32, 611 (1992), Table IV (fit range 0.5-550 keV).
- Reduced-mass energy mu c^2 = 1124656 keV for D-T is from memory (Bosch & Hale 1992, Table VII); speed of light 2.99792458e8 m/s is the SI exact value.
- The paper says reactivities come from numerically integrating the Bosch-Hale cross section, so the reported values use Maxwellian integration: <sigma v> = c*sqrt(8/(pi mu c^2)) T^-3/2 * integral sigma(E) E exp(-E/T) dE.
- Above 550 keV the low-energy fit is simply extended; at T of about 14 keV this tail is negligible (exp(-550/14) ~ 1e-17 relative).
- For a cross-check, the script also computes the Bosch-Hale reactivity parametrization (C1..C7 = 1.17302e-9, 1.51361e-2, 7.51886e-2, 4.60643e-3, 1.35e-2, -1.0675e-4, 1.366e-5; Table VII, from memory). It gives minima about 0.6% higher and T_min about 0.03 keV lower. This difference is within the stated fit accuracy of the S-factor fit. These values are printed but are not the reported values.
- Units: in 3T^2, one factor of T is converted keV->J using 1 keV = 1.6e-16 J (from the paper's 1 MeV = 1.6e-13 J) so that 3nT is an energy density. The other T stays in keV, so the result is in m^-3 keV s.
- The minimum over T is found with a grid from 1 to 100 keV (0.01 keV step), then refined with Brent's method. Only points with a positive denominator are used.

## How the authors' code was called

# Notes

- Source of the result: the Table 3 (`tab:minimum_triple_product_table`) cells in `code/lawson-criterion-paper.py` ("Calculate requirements for D-T, Catalyzed D-D, D-3He, and p-11B" plus the "Numerically find minimum ..." cell). adapter.py pulls the text of those two cells out of the file and runs it with exec, unchanged. Only the D-T rows are reported.
- I did not run the whole notebook: it needs LaTeX (`text.usetex`) and builds every figure. The cells I ran only need math, numpy, pandas and `lib.fusionlib`.
- No files under code/ were edited.
- Settings are the authors' as written in the cell: `relativistic_mode='putvinski'`, `density='ion'`, `method='integrated'` (the `optimal_mix_triple_product` default, which numerically integrates the Bosch-Hale cross section), xi=1, a grid of 300 log-spaced points from 0.5 to 500 keV, D-T kept only for 1 < T < 100 keV, minimum taken with idxmin.
- The minimum temperatures are points on the authors' 300-point grid (13.6067 and 14.2502 keV). They are not continuous optima, and I did not refine them.
- Difference from spec (f_c): spec says f_c = 3.5/17.6 = 0.19886. The code uses `fraction_charged = 0.2` from `lib/reactions.ini`. I used the code's value.
- Difference from spec (bremsstrahlung): spec says the loss term is C_B T^1/2 with no relativistic correction. The Table 3 cell uses the Putvinski relativistic correction (Zeff*(1+1.78 t^1.34) + 2.12 t (...), t = T/511). I used the code's version. As a check only, the same code with `'nonrelativistic'` gives 4.644767e20 (Q=1) and 2.931542e21 (Q=inf) at the same grid temperatures. The reported values are 4.648208e20 and 2.945042e21.
- Difference from spec (units): spec says 1 MeV = 1.6e-13 J and C_B = 5.34e-37 W m^3 keV^-1/2. The code works in keV: C_B = 1.69e-38 * 6.24e18 / sqrt(1000) keV s^-1 m^3 keV^-1/2 (6.24e18 eV/J, i.e. 1 eV = 1.6026e-19 J), and eps_F = 17.6e3 keV. I used the code's values.
- Requirements are pinned to the versions in the authors' uv.lock: numpy 2.2.6, scipy 1.16.1, pandas 2.2.2.
- One run takes about 260 s, because the cell computes every reaction with integrated reactivities.

## What was blinded

- Authors' code: fetched at 2026-11-02T10:10:54Z, after the derivation froze at 2026-11-02T10:10:47Z.
- Agent tools: Edit, Glob, Grep, Read, Write, run. No shell, no web.
- Scripts run under a guard with network, other processes and outside files off. Blocked attempts: 0. Refused tool calls: 0.
- Target values in the paper: 2 passages and 0 code links removed before the agent read it.
- Leak check: 2 target values still appeared in the text the agent read (see verdict.json).
- Typed-in answers: no number in derive.py matches a target value.
- Scripts: the agent's drafts import no networking, process or low-level module.
- Memory check: asked with no paper and no tools, the model stated 0 of 4 values, 0 within the limit.
- Model training cutoff: 2026-06 per the vendor. Paper first posted 2021-05-23, before that, so it may be in training data.

## What was not blinded

- The agent read the paper, including its method. That is the point of the test.
- A model may have seen this paper or code during training. The memory check catches stated values, not everything a model absorbed.
- The freeze hash proves the files did not change later. It does not prove when they were made, or that the operator ran this once. To prove the order, publish the hash before comparing (--stop-after-freeze).
- The guard stops accidents and ordinary model behavior. A script that patches Python's own modules or loads native code could get around it; the flags above and the transcript are the check for that.
- The adapter that calls the authors' code was written by a model. It is in the record for inspection.

## Record

- Freeze hash (SHA-256): `0da2b99365c949607bc6b88b1c8e692268f27f2e683bca2556da58b720f996d2`
- Model: claude-opus-5-5, through claude-cli 2.1.316
- Tool: blindrepro 0.1.0. Run date: 2026-11-02.
- Python 3.12.13. Packages: mpmath==1.3.0, numpy==2.5.4, scipy==1.18.1, sympy==1.14.0.
- Prompts, transcripts and the derivation are in this folder. The paper's text and the authors' code are withheld as hashes and links.
- The whole folder, the authors' side included, is hashed once more at the end in `seal.json`.
- Check again: `blindrepro verify <this folder> --expect <freeze hash>`
