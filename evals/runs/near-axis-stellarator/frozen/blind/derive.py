"""First-order near-axis quasisymmetry (Garren-Boozer) solutions, following Landreman, Sengupta & Plunk Paper II."""
import json
import numpy as np
from scipy.optimize import minimize_scalar

B0 = 1.0
SG = 1.0
SPSI = 1.0
I2 = 0.0


def axis_derivs(phi, rc, zc, zs, nfp):
    """R0, z0 and derivatives (orders 0..3) in phi. rc,zc,zs: dicts {m: amp} for cos/sin(m nfp phi)."""
    R = [np.zeros_like(phi) for _ in range(4)]
    Z = [np.zeros_like(phi) for _ in range(4)]
    for m, a in rc.items():
        k = m * nfp
        R[0] += a * np.cos(k * phi)
        R[1] += -a * k * np.sin(k * phi)
        R[2] += -a * k**2 * np.cos(k * phi)
        R[3] += a * k**3 * np.sin(k * phi)
    for m, a in zc.items():
        k = m * nfp
        Z[0] += a * np.cos(k * phi)
        Z[1] += -a * k * np.sin(k * phi)
        Z[2] += -a * k**2 * np.cos(k * phi)
        Z[3] += a * k**3 * np.sin(k * phi)
    for m, a in zs.items():
        k = m * nfp
        Z[0] += a * np.sin(k * phi)
        Z[1] += a * k * np.cos(k * phi)
        Z[2] += -a * k**2 * np.sin(k * phi)
        Z[3] += -a * k**3 * np.cos(k * phi)
    return R, Z


def geometry(phi, rc, zc, zs, nfp):
    R, Z = axis_derivs(phi, rc, zc, zs, nfp)
    # Position in cylindrical basis (e_R, e_phi, e_z) components; derivatives d/dphi
    # r = R e_R + z e_z ; de_R/dphi = e_phi, de_phi/dphi = -e_R
    R0, R1, R2, R3 = R
    Z0, Z1, Z2, Z3 = Z
    d1 = np.stack([R1, R0, Z1], axis=-1)
    d2 = np.stack([R2 - R0, 2 * R1, Z2], axis=-1)
    d3 = np.stack([R3 - 3 * R1, 3 * R2 - R0, Z3], axis=-1)
    lp = np.linalg.norm(d1, axis=-1)
    c = np.cross(d1, d2)
    cn = np.linalg.norm(c, axis=-1)
    kappa = cn / lp**3
    tau = np.einsum('ij,ij->i', c, d3) / cn**2
    t = d1 / lp[:, None]
    b = c / cn[:, None]
    n = np.cross(b, t)
    return dict(R0=R0, lp=lp, kappa=kappa, tau=tau, t=t, n=n, b=b)


def count_N(rc, zc, zs, nfp, M=20000):
    phi = np.linspace(0, 2 * np.pi, M + 1)
    g = geometry(phi, rc, zc, zs, nfp)
    nR, nz = g['n'][:, 0], g['n'][:, 2]
    # angle measured from e_z toward e_R: positive = rotation from n toward b about t (t ~ +e_phi)
    ang = np.unwrap(np.arctan2(nR, nz))
    Nf = (ang[-1] - ang[0]) / (2 * np.pi)
    N = int(round(Nf))
    assert abs(Nf - N) < 1e-8, Nf
    return N


def diff_matrix(Np, T):
    k = np.fft.fftfreq(Np, d=1.0 / Np) * 2 * np.pi / T
    if Np % 2 == 0:
        k[Np // 2] = 0.0
    I = np.eye(Np)
    return np.real(np.fft.ifft(1j * k[:, None] * np.fft.fft(I, axis=0), axis=0))


def solve(rc, zc, zs, nfp, etabar, sigma0, Np):
    T = 2 * np.pi / nfp
    phi = np.arange(Np) * T / Np
    g = geometry(phi, rc, zc, zs, nfp)
    # Axis length L by spectral (trapezoid, periodic) quadrature over a period, times nfp
    L = nfp * np.mean(g['lp']) * T
    G0 = SG * B0 * L / (2 * np.pi)
    a = abs(G0) / (g['lp'] * B0)
    kap, tau = g['kappa'], g['tau']
    P = etabar**4 / kap**4 + 1.0
    Q = -2 * G0 * etabar**2 / (B0 * kap**2) * (I2 / B0 - SPSI * tau)
    D = diff_matrix(Np, T)
    x = np.zeros(Np)  # [iotaN, sigma_2..sigma_N]

    def unpack(x):
        s = np.empty(Np)
        s[0] = sigma0
        s[1:] = x[1:]
        return x[0], s

    for it in range(100):
        iN, s = unpack(x)
        res = a * (D @ s) + iN * (P + s**2) + Q
        J = np.empty((Np, Np))
        J[:, 0] = P + s**2
        J[:, 1:] = a[:, None] * D[:, 1:] + np.diag(2 * iN * s)[:, 1:]
        dx = np.linalg.solve(J, -res)
        x = x + dx
        if np.linalg.norm(dx) < 1e-15 and it > 2:
            break
    iN, s = unpack(x)
    res = a * (D @ s) + iN * (P + s**2) + Q
    return iN, s, phi, L, np.linalg.norm(res)


def interp_sigma(s, T, phis):
    Np = len(s)
    c = np.fft.fft(s) / Np
    m = np.fft.fftfreq(Np, d=1.0 / Np)
    k = m * 2 * np.pi / T
    out = np.zeros_like(phis, dtype=complex)
    for j in range(Np):
        if Np % 2 == 0 and abs(m[j]) == Np // 2:
            out += c[j] * np.cos(k[j] * phis)
        else:
            out += c[j] * np.exp(1j * k[j] * phis)
    return out.real


def elongation(phis, s_at, rc, zc, zs, nfp, etabar):
    g = geometry(np.atleast_1d(phis), rc, zc, zs, nfp)
    kap = g['kappa']
    sig = s_at
    # theta shifted by N varphi (elongation invariant under rotation of theta)
    X1c = etabar / kap
    X1s = 0.0 * kap
    Y1s = SG * SPSI * kap / etabar
    Y1c = SG * SPSI * kap * sig / etabar
    n, b = g['n'], g['b']
    nR, nz, bR, bz = n[:, 0], n[:, 2], b[:, 0], b[:, 2]
    f = g['lp'] / g['R0']
    R1c = f * (-bz * X1c + nz * Y1c)
    R1s = f * (-bz * X1s + nz * Y1s)
    z1c = f * (bR * X1c - nR * Y1c)
    z1s = f * (bR * X1s - nR * Y1s)
    p = R1s**2 + R1c**2 + z1s**2 + z1c**2
    q = R1s * z1c - R1c * z1s
    return (p + np.sqrt(np.maximum(p**2 - 4 * q**2, 0))) / (2 * np.abs(q))


def run_case(rc, zc, zs, nfp, etabar, sigma0, Np=151):
    N = count_N(rc, zc, zs, nfp)
    iN, s, phi, L, rn = solve(rc, zc, zs, nfp, etabar, sigma0, Np)
    iN2, _, _, _, _ = solve(rc, zc, zs, nfp, etabar, sigma0, Np + 50)
    iota = iN + N
    T = 2 * np.pi / nfp
    fine = np.linspace(0, T, 4001)[:-1]
    el = elongation(fine, interp_sigma(s, T, fine), rc, zc, zs, nfp, etabar)
    j = int(np.argmax(el))
    h = fine[1] - fine[0]

    def negel(p):
        return -elongation(np.array([p]), interp_sigma(s, T, np.array([p])), rc, zc, zs, nfp, etabar)[0]

    r = minimize_scalar(negel, bounds=(fine[j] - h, fine[j] + h), method='bounded',
                        options={'xatol': 1e-13})
    maxel = max(-r.fun, el[j])
    print(f"N={N} iota={iota!r} (iota-N={iN!r}, diff vs Np+50: {iN-iN2:.2e}), resid={rn:.2e}, L={L!r}, "
          f"max elong={maxel!r} at phi={r.x!r}, grid max={el[j]!r}")
    return iota, maxel


out = {}
iota, el = run_case({0: 1.0, 1: 0.045}, {}, {1: -0.045}, 3, -0.9, 0.0)
out['iota_qa_sec51'] = iota
out['max_elongation_qa_sec51'] = el
iota, el = run_case({0: 1.0, 1: 0.265}, {}, {1: -0.21}, 4, -2.25, 0.0)
out['iota_qh_sec52'] = iota
out['max_elongation_qh_sec52'] = el
iota, el = run_case({0: 1.0, 1: 0.042}, {1: -0.025}, {1: -0.042}, 3, -1.1, -0.6)
out['iota_asym_sec53'] = iota
out['max_elongation_asym_sec53'] = el
print(json.dumps(out))
