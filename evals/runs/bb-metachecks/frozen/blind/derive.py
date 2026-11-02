import json
from collections import deque
import sympy as sp

# ---------- GF(2) linear algebra with rows as Python ints ----------

def rank_gf2(rows):
    basis = {}  # pivot bit -> row
    r = 0
    for v in rows:
        while v:
            p = v.bit_length() - 1
            if p in basis:
                v ^= basis[p]
            else:
                basis[p] = v
                r += 1
                break
    return r


def nullspace_gf2(rows, ncols):
    """Return basis of {x in F2^ncols : row . x = 0 for all rows}."""
    # reduced row echelon form
    piv_rows = []  # list of (pivot, row)
    for v in rows:
        for p, r in piv_rows:
            if (v >> p) & 1:
                v ^= r
        if v:
            p = v.bit_length() - 1
            # eliminate p from existing rows
            piv_rows = [(q, (r ^ v) if (r >> p) & 1 else r) for q, r in piv_rows]
            piv_rows.append((p, v))
    pivots = {p: r for p, r in piv_rows}
    free = [c for c in range(ncols) if c not in pivots]
    basis = []
    for f in free:
        x = 1 << f
        for p, r in pivots.items():
            if (r >> f) & 1:
                x |= 1 << p
        basis.append(x)
    return basis

# ---------- BB code construction ----------

def mono_idx(i, j, l, m):
    return (i % l) + l * (j % m)


def mult_matrix_cols(c, l, m):
    """c: list of (i,j) exponents. Returns column list (as int bitmasks over rows)
    for L_c: column g = c*g."""
    N = l * m
    cols = []
    for j in range(m):
        for i in range(l):
            v = 0
            for (a, b) in c:
                v ^= 1 << mono_idx(i + a, j + b, l, m)
            cols.append(v)
    return cols


def star(c):
    return [(-a, -b) for (a, b) in c]


def analyse(l, m, a, b):
    N = l * m
    # H = [L_{b*} | L_{a*}]  (N x 2N); columns as bitmasks over N rows
    cols = mult_matrix_cols(star(b), l, m) + mult_matrix_cols(star(a), l, m)
    # rows of H as bitmasks over 2N columns
    rows = [0] * N
    for c_idx, col in enumerate(cols):
        for r in range(N):
            if (col >> r) & 1:
                rows[r] |= 1 << c_idx
    rkH = rank_gf2(rows)
    k = 2 * N - 2 * rkH
    # check H_X H_Z^T = 0, H_X = [L_a | L_b]
    HX_cols = mult_matrix_cols(a, l, m) + mult_matrix_cols(b, l, m)
    HX_rows = [0] * N
    for c_idx, col in enumerate(HX_cols):
        for r in range(N):
            if (col >> r) & 1:
                HX_rows[r] |= 1 << c_idx
    for rx in HX_rows:
        for rz in rows:
            assert bin(rx & rz).count("1") % 2 == 0
    assert rank_gf2(HX_rows) == rkH
    # metacheck space ker H^T = left null space: vectors y in F2^N with y^T H = 0
    # i.e. y orthogonal to every column of H
    M = nullspace_gf2(cols, N)
    rM = len(M)
    assert rM == N - rkH
    assert 2 * rM == k
    # M H = 0
    for mr in M:
        for col in cols:
            assert bin(mr & col).count("1") % 2 == 0
    # columns of M (metasyndrome of a single fault at coordinate h)
    mcols = []
    for h in range(N):
        v = 0
        for i, mr in enumerate(M):
            if (mr >> h) & 1:
                v |= 1 << i
        mcols.append(v)
    S = 1 << rM
    # coset-leader histogram by BFS over metasyndrome states
    dist = [-1] * S
    dist[0] = 0
    dq = deque([0])
    while dq:
        s = dq.popleft()
        for c in mcols:
            t = s ^ c
            if dist[t] < 0:
                dist[t] = dist[s] + 1
                dq.append(t)
    assert all(d >= 0 for d in dist)
    hist = {}
    for d in dist:
        hist[d] = hist.get(d, 0) + 1
    # syndrome distance: min number of columns of M summing to zero (= min wt in ker M = im H)
    dS = None
    if any(c == 0 for c in mcols):
        dS = 1
    else:
        best = None
        for h in range(N):
            others = mcols[:h] + mcols[h + 1:]
            target = mcols[h]
            dd = {0: 0}
            dq = deque([0])
            found = None
            while dq:
                s = dq.popleft()
                if s == target:
                    found = dd[s]
                    break
                for c in others:
                    t = s ^ c
                    if t not in dd:
                        dd[t] = dd[s] + 1
                        dq.append(t)
            if found is not None:
                w = found + 1
                if best is None or w < best:
                    best = w
        dS = best
    return dict(N=N, k=k, rM=rM, dS=dS, hist=hist)


def P_repair_coeff(hist, N, order):
    p = sp.symbols("p")
    P = 1 - sum(c * p**w * (1 - p) ** (N - w) for w, c in hist.items())
    P = sp.expand(P)
    return sp.Poly(P, p).coeff_monomial(p**order)


codes = {
    "72": (6, 6, [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)]),
    "90": (15, 3, [(9, 0), (0, 1), (0, 2)], [(0, 0), (2, 0), (7, 0)]),
    "108": (9, 6, [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)]),
    "144": (12, 6, [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)]),
    "288": (12, 12, [(3, 0), (0, 2), (0, 7)], [(0, 3), (1, 0), (2, 0)]),
}

# sanity: running example BB(3,3) from the paper: k=8, rank H=5, d_S=3, hist (1,9,6)
ex = analyse(3, 3, [(0, 0), (1, 0), (2, 0)], [(0, 0), (0, 1), (0, 2)])
print("running example:", ex)
assert ex["k"] == 8 and ex["dS"] == 3 and ex["hist"] == {0: 1, 1: 9, 2: 6}

out = {}
res = {}
for name, (l, m, a, b) in codes.items():
    r = analyse(l, m, a, b)
    res[name] = r
    print(name, r)
    out["k_" + name] = r["k"]
for name in codes:
    out["r_M_" + name] = res[name]["rM"]
for name in codes:
    out["d_S_" + name] = res[name]["dS"]
g = res["144"]["hist"]
out["gross_leader_c0"] = g.get(0, 0)
out["gross_leader_c1"] = g.get(1, 0)
out["gross_leader_c2"] = g.get(2, 0)
h72 = res["72"]["hist"]
c2 = P_repair_coeff(h72, 36, 2)
c1 = P_repair_coeff(h72, 36, 1)
print("72 p^1 coefficient:", c1, " p^2 coefficient:", c2)
out["p2_coefficient_exact_repair_72"] = int(c2)
print(json.dumps(out))
