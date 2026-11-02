"""Run the authors' Paley-Wiener driver and extract the requested quantities."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "code"))
os.chdir(HERE)  # figures/ is written relative to cwd (this folder)

import numpy as np  # noqa: E402
import paley_wiener  # noqa: E402

print("SPECS used by authors:", paley_wiener.SPECS)

# Authors' entry point for the published comparison figure (paley_wiener.png).
combined = paley_wiener.comparison_figure(out=os.path.join(HERE, "figures", "paley_wiener.png"))

out = {}
for n_eff in (20, 40, 80):
    tag = f"ne{n_eff}"
    g_curve = np.asarray(combined[f"{tag}_sampling_curve"], dtype=np.float64)
    lower_n = np.asarray(combined[f"{tag}_lower_n"])
    lower = np.asarray(combined[f"{tag}_lower"], dtype=np.float64)
    m = n_eff
    print(f"{tag}: n_used={combined[f'{tag}_n_used']} len(g_curve)={g_curve.size}")
    out[f"pgreedy_max_power_neff{n_eff}_m{m}"] = (
        float(g_curve[m]) if m < g_curve.size else None
    )
    hit = np.flatnonzero(lower_n == m)
    out[f"gelfand_lower_neff{n_eff}_n{m}"] = float(lower[hit[0]]) if hit.size else None
    print(f"{tag}: sqrt(c/pi)={np.sqrt(combined[f'{tag}_diag'])!r}")

print(json.dumps({k: (repr(v) if v is not None else None) for k, v in out.items()}))
print(json.dumps(out))
