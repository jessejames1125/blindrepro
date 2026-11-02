# Blind reproduction: Spectral Gap Bounds for Langevin Dynamics in Mixed Spherical Spin Glasses

**Result: REPRODUCED: max error 2.2e-12%, limit 5%.**

- Paper: arXiv:2609.15157 https://arxiv.org/abs/2609.15157
- Authors' code: https://github.com/mbadieik/spectral_gap_for_mixed_spherical_spin_glasses at 4fda784d6fe32bc53296064f736cc9253c01e07d
- Target: The theoretical threshold energies E_infinity, E_2, E_1 and E_0 for the pure spherical p-spin model at p = 4, from the paper's threshold equations
- Claim tested: For the pure spherical p-spin model xi(x)=x^p at p=4, the landscape threshold energies E_infinity (where the typical Hessian shift reaches the edge of the semicircle), E_2 and E_1 (zeros of the annealed index-k complexity functions), and E_0 (the ground-state energy constant) follow from the paper's closed-form pure-case complexity functions by root finding.

## Values

```
quantity        blind  authors' code   paper     error
-------------  ------  -------------  ------  --------
E_infinity_p4  1.7321         1.7321  1.7321  0.0e+00%  ok
E_2_p4         1.7765         1.7765  1.7765  1.2e-14%  ok
E_1_p4         1.7833         1.7833  1.7833  2.2e-12%  ok
E_0_p4         1.7941         1.7941  1.7941  8.7e-14%  ok
```

Error is |blind - authors| / |authors|, or the plain difference where the authors' value is 0. The arithmetic is done by code, not a model.
Paper values, where shown, were read from the paper by a model and were hidden from the blind agent.

## What the blind agent says it assumed or took from memory

- J(t) evaluated via the paper's antiderivative identity (eq. B-antiderivative), cross-checked against numerical quadrature of the definition (eq. Jgoe).
- Pure-case Theta_k from eq. Theta-explicit with p=4; valid for u <= -E_infinity, and all roots lie beyond E_infinity (Theta_k(-E_inf) = (1/2)log3 - 1/2 > 0, strictly decreasing beyond).
- E_0 taken as root of Theta_0 (k=0, coefficient 1 on I_1) as instructed by spec.json; this identification with the ground state is the Auffinger-Ben Arous-Cerny result for pure models (from spec/memory, not derived from the Parisi formula here).
- Roots found with mpmath (40 digits) and reported as float64.

## How the authors' code was called

# Notes

- Source of E_inf, E_0, E_1: `code/code/pspin_langevin.py::theory_thresholds(4)`, the function all of the authors' p=4 scripts import (pspin_p4.py, saddle_enumeration.py, phase_transitions.py).
- Source of E_2: `code/code/saddle_enumeration.py::threshold_E2()` (module constant P=4). It is the same brentq root of Theta_2(-z)=0 that phase_transitions.mechanism_phase_figure computes inline. I used the module-level function so I would not have to run the figure code.
- Authors' settings are kept unchanged: scipy `quad` for I_1, `brentq` with default tolerances, brackets [E_inf+1e-9, 2*E_inf] for E_0/E_1 and [E_inf+1e-9, E_0] for E_2.
- Authors' I_1(z) = (2/E_inf^2) ∫_{E_inf}^{z} sqrt(x^2-E_inf^2) dx. Substituting y = x*sqrt(p/(p-1)) shows it equals the spec's J(-z*sqrt(p/(p-1))). Theta_k matches the spec. No difference from spec.json.
- E_0 is the authors' Theta_0 root (the ABC pure-case formula). It is not checked against a separate Crisanti-Sommers/Parisi computation, and the repo has no code for one.
- No edits to code/. Importing the modules runs only the theory/style code at module level, not the simulations.
- requirements.txt pins numpy 1.26.4, scipy 1.11.4 and matplotlib 3.8.4 (the repo has only lower bounds: numpy>=1.24, scipy>=1.10, matplotlib>=3.7). matplotlib is needed because the modules import it.
- The sandbox blocked matplotlib's font-cache scan of C:\Windows\Fonts. This is harmless because nothing is plotted.
- Output: E_inf=1.7320508075688772, E_2=1.7764776117001901, E_1=1.7833003012540962, E_0=1.7940850281792529. These match the README/saddle_summary.txt to the 5 printed digits.

## What was blinded

- Authors' code: fetched at 2026-11-02T10:23:43Z, after the derivation froze at 2026-11-02T10:23:32Z.
- Agent tools: Edit, Glob, Grep, Read, Write, run. No shell, no web.
- Scripts run under a guard with network, other processes and outside files off. Blocked attempts: 0. Refused tool calls: 0.
- Target values in the paper: 8 passages and 2 code links removed before the agent read it.
- Leak check: no target value found in the text the agent read.
- Typed-in answers: no number in derive.py matches a target value.
- Scripts: the agent's drafts import no networking, process or low-level module.
- Memory check: asked with no paper and no tools, the model stated 0 of 4 values, 0 within the limit.
- Model training cutoff: 2026-06 per the vendor. Paper first posted 2026-09-14, after that, so it should not be in training data.

## What was not blinded

- The agent read the paper, including its method. That is the point of the test.
- A model may have seen this paper or code during training. The memory check catches stated values, not everything a model absorbed.
- The freeze hash proves the files did not change later. It does not prove when they were made, or that the operator ran this once. To prove the order, publish the hash before comparing (--stop-after-freeze).
- The guard stops accidents and ordinary model behavior. A script that patches Python's own modules or loads native code could get around it; the flags above and the transcript are the check for that.
- The adapter that calls the authors' code was written by a model. It is in the record for inspection.

## Record

- Freeze hash (SHA-256): `b8fb1683de9a34764c326fead91935a75dfb4527440a3eb8c431da2014174786`
- Model: claude-opus-5-5, through claude-cli 2.1.316
- Tool: blindrepro 0.1.0. Run date: 2026-11-02.
- Python 3.12.13. Packages: mpmath==1.3.0, numpy==2.5.4, scipy==1.18.1, sympy==1.14.0.
- Prompts, transcripts and the derivation are in this folder. The paper's text and the authors' code are withheld as hashes and links.
- The whole folder, the authors' side included, is hashed once more at the end in `seal.json`.
- Check again: `blindrepro verify <this folder> --expect <freeze hash>`
