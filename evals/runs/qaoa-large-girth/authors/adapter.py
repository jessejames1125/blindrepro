"""Build the authors' C++ code (code/src) with zig's clang (pip: ziglang) + Eigen headers (pip: cmeel-eigen)
and run it for q=2 (MaxCut, D->inf), p=1..8.

optimize.cpp needs LBFGSpp (<LBFGS.h>), which is not obtainable from pip, so it cannot be built; we attempt
it and print the compiler error. We evaluate nu_p with the authors' MatrixBuilder (evaluate.cpp) at the
authors' published optimal (gamma, beta) from code/data.csv.
"""
import os, sys, subprocess, json, csv, sysconfig

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "code", "src")
SHIM = os.path.join(HERE, "shim")
BUILD = os.path.join(HERE, "build")
os.makedirs(BUILD, exist_ok=True)
EIGEN = os.path.join(sysconfig.get_paths()["purelib"], "cmeel.prefix", "include", "eigen3")

env = dict(os.environ)
env["ZIG_GLOBAL_CACHE_DIR"] = os.path.join(BUILD, "zig-global-cache")
env["ZIG_LOCAL_CACHE_DIR"] = os.path.join(BUILD, "zig-local-cache")

# Makefile flags: -I. -I$(EIGEN) -I$(LBFGS) -fopenmp -O3 -march=native ; -fopenmp dropped (no OpenMP runtime),
# omp.h replaced by single-thread shim in shim/.
CFLAGS = ["-I" + SRC, "-I" + SHIM, "-I" + EIGEN, "-O3", "-march=native"]


def cxx(args):
    cmd = [sys.executable, "-m", "ziglang", "c++"] + CFLAGS + args
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=BUILD)
    return r


def build(name, sources):
    exe = os.path.join(BUILD, name + ".exe")
    r = cxx(["-o", exe] + sources)
    print("BUILD", name, "rc", r.returncode)
    if r.returncode != 0:
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
        return None
    return exe


mb = os.path.join(SRC, "matrix_builder.cpp")
opt_exe = build("optimize", [os.path.join(SRC, "optimize.cpp"), mb])
eval_exe = build("evaluate", [os.path.join(SRC, "evaluate.cpp"), mb])
evalfp_exe = build("evaluate_fullprec", [os.path.join(SHIM, "evaluate_fullprec.cpp"), mb])

# Authors' published optimal parameters (q=2 rows)
params = {}
with open(os.path.join(HERE, "code", "data.csv"), newline="") as f:
    rows = list(csv.reader(f))
for row in rows[2:]:
    if not row or row[0] != "2":
        continue
    p = int(row[1])
    vals = [float(v) for v in row[3:3 + 2 * p]]
    params[p] = (vals[:p], vals[p:])


def run_eval(exe, p, g, b, tag):
    out = os.path.join(BUILD, f"{tag}_p{p}.txt")
    args = [exe, out, "2", str(p)] + [repr(x) for x in g] + [repr(x) for x in b]
    r = subprocess.run(args, capture_output=True, text=True, cwd=BUILD)
    if r.returncode != 0:
        print("RUN FAIL", tag, p, r.returncode, r.stderr[-2000:])
        return None
    with open(out) as f:
        lines = f.read().splitlines()
    return float(lines[4])


result = {}
for p in range(1, 9):
    g, b = params[p]
    nu8 = run_eval(eval_exe, p, g, b, "evaluate") if eval_exe else None
    nufp = run_eval(evalfp_exe, p, g, b, "evaluate_fullprec") if evalfp_exe else None
    print(f"p={p} gammas={g} betas={b} evaluate.cpp(8 digits)={nu8!r} full-precision={nufp!r}")
    result[f"nu_bar_p{p}"] = nufp if nufp is not None else nu8

print(json.dumps(result))
