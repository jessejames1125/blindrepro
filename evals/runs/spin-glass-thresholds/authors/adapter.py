"""Obtain the p=4 thresholds E_inf, E_2, E_1, E_0 from the authors' code.

Uses pspin_langevin.theory_thresholds(4) (E_inf, E_0, E_1) and
saddle_enumeration.threshold_E2() (E_2 at P=4), exactly as the authors'
scripts compute them (saddle_summary.txt / README values).
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "code", "code"))

from pspin_langevin import theory_thresholds  # noqa: E402
import saddle_enumeration as se  # noqa: E402  (P = 4 at module level)

Einf, E0, E1 = theory_thresholds(4)
assert se.P == 4
E2 = se.threshold_E2()

print(f"E_inf={Einf!r} E_2={E2!r} E_1={E1!r} E_0={E0!r}")
print(json.dumps({
    "E_infinity_p4": float(Einf),
    "E_2_p4": float(E2),
    "E_1_p4": float(E1),
    "E_0_p4": float(E0),
}))
