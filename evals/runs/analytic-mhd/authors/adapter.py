"""Adapter: obtain spec.json quantities by calling the authors' code in code/."""
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE / "code"
os.environ.setdefault("JAX_ENABLE_X64", "true")
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(HERE / ".mplconfig"))

import numpy as np


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


results = {k: None for k in ("iota_uniform_family", "iota_sheared_axis", "iota_sheared_edge",
                             "force_residual_uniform_family", "force_residual_sheared_family")}

# ---------------- Uniform-iota (iota=2) family ----------------
sys.path.insert(0, str(CODE / "iota_2"))
try:
    u2 = load(CODE / "iota_2" / "analytic_3d_equilibrium_iota_2.py", "analytic_3d_equilibrium_iota_2")
    ver = u2.verify()  # authors' check script, default settings (n_per_epsilon=120, seed=8)
    print("verify():", ver["status"])
    for w in ver["winding_checks"]:
        print("winding check:", repr(w))
    w05 = next(w for w in ver["winding_checks"] if w["epsilon"] == 0.5)
    # Authors' theta = angle[(R-Ra) + i(z-Za)] -> poloidal_turns = -2.
    # spec/paper theta = arg[(R-Ra) - i(z-Za)] flips the sign of the poloidal turns.
    print("eps=0.5 iota in authors' theta convention:", repr(w05["poloidal_turns"] / w05["toroidal_turns"]))
    results["iota_uniform_family"] = -w05["poloidal_turns"] / w05["toroidal_turns"]

    eps, delta = 0.5, 1.0 / 64
    res = []
    for alpha, zeta in ((0.0, 0.0), (np.pi / 2, np.pi / 4), (np.pi, np.pi / 3)):
        point = u2.surface(delta, alpha, zeta, eps)
        bb = u2.field(point, eps)
        current = u2._curl(u2._jacobian(lambda r: u2.field(r, eps), point))
        grad_psi = u2._jacobian(lambda r: u2.flux(r, eps), point)
        grad_p = -2 * grad_psi
        print("uniform point", alpha, zeta, "psi=", repr(float(u2.flux(point, eps))))
        res.append(float(np.linalg.norm(np.cross(current, bb) - grad_p) / np.linalg.norm(grad_p)))
    results["force_residual_uniform_family"] = res
except Exception as exc:  # pragma: no cover
    import traceback; traceback.print_exc()

# ---------------- Sheared-iota family ----------------
sys.path.insert(0, str(CODE / "sheared_iota"))
try:
    dsc = load(CODE / "sheared_iota" / "20260912-02_analytic_3D_equilibrium_with_sheared_iota_desc.py",
               "sheared_desc")
    # Set the module parameters exactly as main() does from command-line args.
    dsc.EPS, dsc.S, dsc.KAPPA, dsc.KB, dsc.LAM = 2.0, 1.0, 1.0, 0.1, 1.0
    dsc.PSI_B = dsc.KB**2 / 2
    dsc.P_AXIS = dsc.KAPPA**2 * dsc.PSI_B / (dsc.mu_0 * dsc.LAM**2)
    io = dsc.analytic_iota([0, dsc.KB])  # what main() prints as "Expected iota axis/edge"
    print("analytic_iota([0,k_b]) =", repr(io.tolist()))
    axis_t = np.arange(1024) * 2 * np.pi / 1024
    axis_iota = dsc.h(dsc.S) * np.mean(1 / np.cosh(dsc.EPS / 2 * np.sin(2 * axis_t)))
    print("axis_iota (check_reference formula h0*mean sech) =", repr(float(axis_iota)))
    results["iota_sheared_axis"] = float(io[0])
    results["iota_sheared_edge"] = float(io[1])

    fig = load(CODE / "sheared_iota" / "20260913-02_analytic_3D_equilibrium_sheared_iota_figures.py",
               "sheared_figures")
    case = fig.Case("spec", dsc.EPS, dsc.S, dsc.KB, dsc.LAM)
    pts = np.array([fig.surface(dsc.KB, chi, zeta, case)
                    for chi, zeta in ((0.0, 0.0), (np.pi / 2, np.pi / 4), (np.pi, np.pi / 3))])
    b, psi = dsc.exact_field(pts)
    print("sheared points psi =", repr(np.asarray(psi).tolist()), "expected", dsc.PSI_B)
    db, j, gps = dsc.exact_derivatives(pts)
    gp = -dsc.KAPPA**2 / (dsc.mu_0 * dsc.LAM**2) * gps  # as in check_reference()
    resid = np.linalg.norm(np.cross(j, b) - gp, axis=1) / np.linalg.norm(gp, axis=1)
    results["force_residual_sheared_family"] = [float(v) for v in resid]
except Exception:
    import traceback; traceback.print_exc()

print(json.dumps(results))
