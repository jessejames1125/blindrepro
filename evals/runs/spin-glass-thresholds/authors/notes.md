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
