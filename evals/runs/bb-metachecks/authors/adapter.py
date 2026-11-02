"""Adapter: obtain the spec quantities by running the authors' bb_manuscript_reproduce.py.

Uses the authors' audit_code() on their STANDARD_CODES with the settings their
main() uses by default (exact one-sided enumeration, mu_max_weight=16, no
cross-check), and the p^2 coefficient exactly as main() computes it.
"""
import json
import sys
import time
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "code"))

import bb_manuscript_reproduce as bb  # noqa: E402

SUFFIX = {
    "[[72,12,6]]": "72",
    "[[90,8,10]]": "90",
    "[[108,8,10]]": "108",
    "Gross [[144,12,12]]": "144",
    "[[288,12,18]]": "288",
}

out = {}
raws = {}
problems = []
for code in bb.STANDARD_CODES:
    t0 = time.time()
    # main() defaults (no --quick): exact_onesided=True, mu_max=16, cross_check=False
    row, raw = bb.audit_code(code, exact_onesided=True, mu_max=16, cross_check=False)
    problems += bb.compare_with_manuscript(row, raw)
    raws[code.name] = (code, raw)
    s = SUFFIX[code.name]
    out[f"k_{s}"] = row["k"]
    out[f"r_M_{s}"] = row["r_M"]
    out[f"d_S_{s}"] = row["d_S"]  # None if > 4 (authors' search only goes through weight 4)
    print(f"{code.name}: k={row['k']} r_M={row['r_M']} d_S={row['d_S']} "
          f"hist={row['leader_hist']} ({time.time() - t0:.1f}s)", flush=True)

gross_hist = raws["Gross [[144,12,12]]"][1]["hist_counter"]
out["gross_leader_c0"] = gross_hist.get(0, 0)
out["gross_leader_c1"] = gross_hist.get(1, 0)
out["gross_leader_c2"] = gross_hist.get(2, 0)

# Exactly as in the authors' main(): coeff = C(36,2) - c_2 of [[72,12,6]]
coeff = comb(36, 2) - raws["[[72,12,6]]"][1]["hist_counter"][2]
out["p2_coefficient_exact_repair_72"] = coeff

# Authors' own repair-curve function at p=0.01, for information only
code72, raw72 = raws["[[72,12,6]]"]
print("P_repair(0.01) [[72,12,6]] =", bb.exact_repair_failure(raw72["hist_counter"], code72.N, 0.01))
print("disagreements with manuscript (authors' check):", problems)

print(json.dumps(out))
