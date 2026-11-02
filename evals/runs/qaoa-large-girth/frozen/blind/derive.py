"""Compute bar_nu_p = max_{gamma,beta} nu_p(gamma,beta) for p=1..8 using the
infinite-D G-matrix iteration of Basso et al. (Sec. 3.2), with an exact
reverse-mode gradient and L-BFGS-B multistart optimisation."""
import json
import time
import numpy as np
from scipy.optimize import minimize

T0 = time.time()


def build(p):
    """Bit configurations with position 0 (a_1) fixed to +1 (use f(-a)=f(a), H(-a)=H(a))."""
    n = 2 * p + 1
    N = 2 ** (n - 1)
    ints = np.arange(N, dtype=np.int64)
    A = np.ones((N, n))
    for k in range(1, n):
        A[:, k] = 1 - 2 * ((ints >> (k - 1)) & 1)
    # pairs (k, k+1); beta index and sign of the X-rotation
    eq = (A[:, :-1] == A[:, 1:])  # N x 2p
    bidx = np.array([k if k < p else 2 * p - k - 1 for k in range(2 * p)])  # 0-based beta index
    sgn = np.array([1.0 if k < p else -1.0 for k in range(2 * p)])
    return dict(p=p, n=n, A=A, eq=eq, bidx=bidx, sgn=sgn)


def f_and_grad(S, beta):
    p, eq, bidx, sgn = S["p"], S["eq"], S["bidx"], S["sgn"]
    b = beta[bidx]
    c, s = np.cos(b), np.sin(b)
    F = np.where(eq, c[None, :] + 0j, (1j * sgn * s)[None, :])
    dF = np.where(eq, -s[None, :] + 0j, (1j * sgn * c)[None, :])
    N, m = F.shape
    pre = np.ones((N, m + 1), complex)
    suf = np.ones((N, m + 1), complex)
    for k in range(m):
        pre[:, k + 1] = pre[:, k] * F[:, k]
    for k in range(m - 1, -1, -1):
        suf[:, k] = suf[:, k + 1] * F[:, k]
    f = 0.5 * pre[:, m]
    # df/dbeta_r
    dfdb = np.zeros((N, p), complex)
    for k in range(m):
        dfdb[:, bidx[k]] += 0.5 * pre[:, k] * dF[:, k] * suf[:, k + 1]
    return f, dfdb


def nu_and_grad(x, S, need_grad=True):
    p, n, A = S["p"], S["n"], S["A"]
    gam, beta = x[:p], x[p:]
    Gam = np.concatenate([gam, [0.0], -gam[::-1]])
    f, dfdb = f_and_grad(S, beta)
    B = A * Gam[None, :]
    G = [None] * (p + 1)
    h = [None] * (p + 1)
    G[0] = 2.0 * (A.T @ (f[:, None] * A))
    for m in range(1, p + 1):
        q = np.einsum("ij,ij->i", B @ G[m - 1], B)
        h[m] = np.exp(-0.5 * q)
        u = f * h[m]
        G[m] = 2.0 * (A.T @ (u[:, None] * A))
    g0 = G[p][p, :]  # row a_0 (position p)
    nu = 0.5j * np.sum(Gam * g0 ** 2)
    if not need_grad:
        return nu, None
    # reverse mode (holomorphic chain rule), d nu / d theta complex
    Gam_bar = 0.5j * g0 ** 2
    Gbar = np.zeros((n, n), complex)
    Gbar[p, :] = 1j * Gam * g0
    fbar = np.zeros(A.shape[0], complex)
    for m in range(p, 0, -1):
        ubar = 2.0 * np.einsum("ij,ij->i", A @ Gbar, A)
        fbar += ubar * h[m]
        hbar = ubar * f
        qbar = -0.5 * hbar * h[m]
        Gm1 = G[m - 1]
        Gbar_new = B.T @ (qbar[:, None] * B)
        Gam_bar += np.einsum("i,ij,ij->j", qbar, A, B @ (Gm1 + Gm1.T))
        Gbar = Gbar_new
    ubar = 2.0 * np.einsum("ij,ij->i", A @ Gbar, A)
    fbar += ubar
    gbeta = fbar @ dfdb
    ggam = Gam_bar[:p] - Gam_bar[p + 1:][::-1]
    return nu, np.concatenate([ggam, gbeta])


def optimise(S, x0):
    def obj(x):
        nu, g = nu_and_grad(x, S)
        return -nu.real, -g.real
    r = minimize(obj, x0, jac=True, method="L-BFGS-B",
                 options=dict(maxiter=3000, ftol=1e-16, gtol=1e-11, maxcor=30))
    return -r.fun, r.x


def interp(x, p):
    """INTERP heuristic (Zhou et al.) p -> p+1."""
    out = []
    for v in (x[:p], x[p:]):
        old = np.concatenate([[0.0], v, [0.0]])
        new = [((i - 1) / p) * old[i - 1] + ((p - i + 1) / p) * old[i] for i in range(1, p + 2)]
        out.append(np.array(new))
    return np.concatenate(out)


# Paper's Table (Appendix, 4-digit optimal angles) used only as warm starts
PAPER = {
    1: ([0.5], [np.pi / 8]),
    2: ([0.3817, 0.6655], [0.4960, 0.2690]),
    3: ([0.3297, 0.5688, 0.6406], [0.5500, 0.3675, 0.2109]),
    4: ([0.2949, 0.5144, 0.5586, 0.6429], [0.5710, 0.4176, 0.3028, 0.1729]),
    5: ([0.2705, 0.4804, 0.5074, 0.5646, 0.6397], [0.5899, 0.4492, 0.3559, 0.2643, 0.1486]),
    6: ([0.2528, 0.4531, 0.4750, 0.5146, 0.5650, 0.6392], [0.6004, 0.4670, 0.3880, 0.3176, 0.2325, 0.1291]),
    7: ([0.2383, 0.4327, 0.4516, 0.4830, 0.5147, 0.5686, 0.6393],
        [0.6085, 0.4810, 0.4090, 0.3534, 0.2857, 0.2080, 0.1146]),
    8: ([0.2268, 0.4162, 0.4332, 0.4608, 0.4818, 0.5179, 0.5717, 0.6393],
        [0.6151, 0.4906, 0.4244, 0.3780, 0.3224, 0.2606, 0.1884, 0.1030]),
}

rng = np.random.default_rng(12345)
results = {}
prev = None
NRAND = {1: 30, 2: 30, 3: 20, 4: 12, 5: 6, 6: 3, 7: 1, 8: 0}
for p in range(1, 9):
    S = build(p)
    starts = []
    g, b = PAPER[p]
    starts.append(("paper", np.array(g + b, float)))
    if prev is not None:
        starts.append(("interp", interp(prev, p - 1)))
    for k in range(NRAND[p]):
        starts.append(("rand", np.concatenate([rng.uniform(0.05, 1.2, p), rng.uniform(-0.8, 0.8, p)])))
    # gradient check
    if p <= 3:
        x = starts[0][1] + 0.01
        _, gr = nu_and_grad(x, S)
        eps = 1e-6
        fd = []
        for i in range(2 * p):
            e = np.zeros(2 * p); e[i] = eps
            fd.append((nu_and_grad(x + e, S, False)[0].real - nu_and_grad(x - e, S, False)[0].real) / (2 * eps))
        print(f"p={p} grad check max err {np.max(np.abs(np.array(fd) - gr.real)):.2e}")
    best = (-np.inf, None, None)
    vals = []
    for name, x0 in starts:
        v, x = optimise(S, x0)
        vals.append((name, v))
        if v > best[0]:
            best = (v, x, name)
    v, x, name = best
    nu_c, _ = nu_and_grad(x, S, False)
    print(f"p={p} best nu={v!r} from {name}; imag={nu_c.imag:.2e}; "
          f"gamma={np.round(x[:p], 4).tolist()} beta={np.round(x[p:], 4).tolist()} "
          f"other starts: {[round(t[1], 10) for t in vals]} t={time.time() - T0:.1f}s", flush=True)
    results[f"nu_bar_p{p}"] = float(v)
    prev = x

print(json.dumps(results))
