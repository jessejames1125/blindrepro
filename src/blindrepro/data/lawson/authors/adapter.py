"""Run the authors' Table 3 cells (minimum triple product, all reactions) from
code/lawson-criterion-paper.py verbatim and report the D-T entries.

The notebook as a whole needs LaTeX/matplotlib for figures; the two cells that
compute Table 3's numbers ("Calculate requirements for D-T, Catalyzed D-D,
D-3He, and p-11B" and the following "Numerically find minimum ..." cell) only
need math/numpy/pandas/lib.fusionlib, so we extract their source text and exec
it unchanged.
"""
import os
import sys
import json
import math
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(HERE, "code")
sys.path.insert(0, CODE)

import numpy as np
import pandas as pd
from lib import fusionlib

src = open(os.path.join(CODE, "lawson-criterion-paper.py"), encoding="utf-8").read()

start_marker = "# %% hidden=true\nlog_temperature_values = np.logspace(math.log10(0.5), math.log10(500), 300)\n\nall_reactions_df"
end_marker = "# %% hidden=true\n# Lawson parameter Table"
i0 = src.index(start_marker)
i1 = src.index(end_marker, i0)
cell_src = src[i0:i1]
assert "min_quantity_df = pd.DataFrame(data)" in cell_src

ns = {"math": math, "np": np, "pd": pd, "fusionlib": fusionlib}
t0 = time.time()
exec(compile(cell_src, "lawson-criterion-paper.py[Table3 cells]", "exec"), ns)
print(f"cells executed in {time.time() - t0:.1f} s")

df = ns["min_quantity_df"]
with pd.option_context("display.max_columns", None, "display.width", 200,
                       "display.float_format", lambda x: repr(x)):
    print(df)

def get(Q):
    row = df[(df["reaction"] == "T(d,n)4He") & (df["Q_fuel"] == Q)].iloc[0]
    tp = row["TP_minimum"]
    T = row["TP_T_i"]
    tp = None if tp is None or (isinstance(tp, float) and math.isnan(tp)) else float(tp)
    T = None if T is None or (isinstance(T, float) and math.isnan(T)) else float(T)
    return tp, T

tp1, T1 = get(1)
tpinf, Tinf = get(float("inf"))

# Diagnostic only (not reported): same grid/function but nonrelativistic
# bremsstrahlung, to quantify the spec-vs-code difference noted in notes.md.
grid = ns["log_temperature_values"]
for Q in [1, float("inf")]:
    vals = [fusionlib.optimal_mix_triple_product(T_i=T, reaction="T(d,n)4He", Q_fuel=Q,
                                                 density="ion", relativistic_mode="nonrelativistic")
            if 1 < T < 100 else float("inf") for T in grid]
    k = int(np.argmin(vals))
    print(f"[diagnostic, nonrelativistic brems] Q_fuel={Q}: min TP={vals[k]!r} at T={grid[k]!r}")

out = {
    "dt_min_triple_product_qfuel_1": tp1,
    "dt_temperature_at_min_triple_product_qfuel_1": T1,
    "dt_min_triple_product_qfuel_inf": tpinf,
    "dt_temperature_at_min_triple_product_qfuel_inf": Tinf,
}
print(json.dumps(out))
