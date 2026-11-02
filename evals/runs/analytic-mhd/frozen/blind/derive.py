import json
import math
import numpy as np
from scipy.integrate import quad, solve_ivp

# ---------------------------------------------------------------------------
# Minimal forward-mode automatic differentiation (complex-valued dual numbers,
# derivatives along the three real Cartesian directions).
# ---------------------------------------------------------------------------
class D:
    __slots__ = ("v", "g")

    def __init__(self, v, g=None):
        self.v = complex(v)
        self.g = np.zeros(3, dtype=complex) if g is None else np.asarray(g, dtype=complex)

    @staticmethod
    def lift(o):
        return o if isinstance(o, D) else D(o)

    def __add__(self, o):
        o = D.lift(o); return D(self.v + o.v, self.g + o.g)
    __radd__ = __add__

    def __sub__(self, o):
        o = D.lift(o); return D(self.v - o.v, self.g - o.g)

    def __rsub__(self, o):
        return D.lift(o) - self

    def __neg__(self):
        return D(-self.v, -self.g)

    def __mul__(self, o):
        o = D.lift(o); return D(self.v * o.v, self.g * o.v + self.v * o.g)
    __rmul__ = __mul__

    def __truediv__(self, o):
        o = D.lift(o)
        return D(self.v / o.v, (self.g * o.v - self.v * o.g) / o.v ** 2)

    def __rtruediv__(self, o):
        return D.lift(o) / self


def dsqrt(a):
    r = np.sqrt(a.v)  # principal branch: Re >= 0
    return D(r, a.g / (2 * r))


def dsin(a):
    return D(np.sin(a.v), np.cos(a.v) * a.g)


def dcos(a):
    return D(np.cos(a.v), -np.sin(a.v) * a.g)


def dexp(a):
    e = np.exp(a.v); return D(e, e * a.g)


def dconj(a):
    return D(np.conj(a.v), np.conj(a.g))


def dre(a):
    return D(a.v.real, a.g.real)


def dim(a):
    return D(a.v.imag, a.g.imag)


def coords(p):
    return [D(p[i], np.eye(3)[i]) for i in range(3)]


def residual(Bfun, pfun, point):
    X = coords(point)
    B = Bfun(*X)
    pp = pfun(*X)
    Bv = np.array([b.v.real for b in B])
    J = np.array([[b.g[j].real for j in range(3)] for b in B])  # J[i,j] = dB_i/dx_j
    curl = np.array([J[2, 1] - J[1, 2], J[0, 2] - J[2, 0], J[1, 0] - J[0, 1]])
    gp = pp.g.real
    lhs = np.cross(curl, Bv)
    return float(np.linalg.norm(lhs - gp) / np.linalg.norm(gp)), pp, Bv


# ---------------------------------------------------------------------------
# Family 1 (integer iota)
# ---------------------------------------------------------------------------
eps1 = 0.5
a1 = math.sqrt(1 + eps1)
b1 = math.sqrt(1 - eps1)
delta1 = 1.0 / 64


def B_uniform(x, y, z):
    s = x * x / a1 ** 2 + y * y / b1 ** 2
    F = dsqrt(1 - (1 - s) * (1 - s) - 4 * z * z)
    return [(2 * z * x - (a1 / b1) * F * y) / s,
            (2 * z * y + (b1 / a1) * F * x) / s,
            1 - s]


def psi_uniform(x, y, z):
    B = B_uniform(x, y, z)
    B2 = B[0] * B[0] + B[1] * B[1] + B[2] * B[2]
    return (x * x + y * y + 4 * z * z + B2 - 2 + eps1 ** 2) / 4


def p_uniform(x, y, z):
    return 0.0 - 2 * psi_uniform(x, y, z)


def embed_uniform(u, v, zeta, a=a1, b=b1):
    q2 = u * u + v * v
    L = math.sqrt((1 + math.sqrt(1 - 4 * q2)) / 2)
    x = a * (L * np.cos(zeta) + (u * np.cos(zeta) + v * np.sin(zeta)) / L)
    y = b * (L * np.sin(zeta) + (v * np.cos(zeta) - u * np.sin(zeta)) / L)
    z = v * np.cos(2 * zeta) - u * np.sin(2 * zeta)
    return x, y, z


res1 = []
for alpha, zeta in [(0.0, 0.0), (math.pi / 2, math.pi / 4), (math.pi, math.pi / 3)]:
    u = -eps1 / 2 + math.sqrt(delta1) * math.cos(alpha)
    v = math.sqrt(delta1) * math.sin(alpha)
    pt = embed_uniform(u, v, zeta)
    r, pp, Bv = residual(B_uniform, p_uniform, pt)
    # sanity: psi on the point and B == d r / d zeta
    h = 1e-6
    dr = (np.array(embed_uniform(u, v, zeta + h)) - np.array(embed_uniform(u, v, zeta - h))) / (2 * h)
    print("fam1 point", pt, "psi=", -pp.v.real / 2, "|B-dr/dzeta|=", np.linalg.norm(Bv - dr), "res=", r)
    res1.append(r)

# Rotational transform of family 1 from geometric poloidal angle winding
def iota_uniform(eps, psi, alpha, n=20001):
    a = math.sqrt(1 + eps); b = math.sqrt(1 - eps)
    Ra = math.sqrt(1 - eps ** 2)
    u = -eps / 2 + math.sqrt(psi) * math.cos(alpha)
    v = math.sqrt(psi) * math.sin(alpha)
    zeta = np.linspace(0, 2 * np.pi, n)
    x, y, z = embed_uniform(u, v, zeta, a, b)
    phi = np.unwrap(np.arctan2(y, x))
    R = np.hypot(x, y)
    Za = (eps / 2) * np.sin(2 * phi)
    theta = np.unwrap(np.angle((R - Ra) - 1j * (z - Za)))
    dth = theta[-1] - theta[0]
    dph = phi[-1] - phi[0]
    return dth / dph, dth / (2 * np.pi), dph / (2 * np.pi)


iota_vals = []
for psi in [delta1, 4 * delta1 / 9, delta1 / 9, 1e-4]:
    for alpha in [0.0, 1.0, 2.5, 4.0]:
        ratio, nth, nph = iota_uniform(eps1, psi, alpha)
        iota_vals.append((ratio, nth, nph))
print("fam1 iota samples (ratio, poloidal turns, toroidal turns):")
for t in iota_vals:
    print("   ", t)
# The field lines close after one zeta period, so the turn counts are integers;
# report the ratio of the (rounded) integer winding numbers.
nth_int = {round(t[1]) for t in iota_vals}
nph_int = {round(t[2]) for t in iota_vals}
assert len(nth_int) == 1 and len(nph_int) == 1
iota_uniform_family = float(nth_int.pop() / nph_int.pop())
print("iota_uniform_family =", iota_uniform_family,
      "max dev of raw ratio:", max(abs(t[0] - iota_uniform_family) for t in iota_vals))

# ---------------------------------------------------------------------------
# Family 2 (sheared iota)
# ---------------------------------------------------------------------------
eps2 = 2.0
S2 = 1.0
lam2 = 1.0
kb = 0.1
delta2 = 1.0 / 200


def B_sheared(x, y, z):
    om = x + 1j * y
    omb = dconj(om)
    K = omb * dsqrt(1 + eps2 / (omb * omb))
    Xi = om * K + (math.pi / 2 - S2)
    ez = dexp(-1j * lam2 * z)
    W = 1j * dsin(Xi) / (2 * K)
    hor = ez * W
    Bz = dre(ez * dcos(Xi)) / lam2
    return [dre(hor), dim(hor), Bz]


def psi_sheared(x, y, z):
    om = x + 1j * y
    omb = dconj(om)
    K = omb * dsqrt(1 + eps2 / (omb * omb))
    Xi = om * K + (math.pi / 2 - S2)
    ez = dexp(-1j * lam2 * z)
    sl = dsin(lam2 * z)
    rc = dre(ez * dcos(Xi))
    return 0.5 * (sl * sl + rc * rc)


def p_sheared(x, y, z):
    return 0.0 - psi_sheared(x, y, z) / lam2 ** 2


def hfun(sig, eps):
    return math.sqrt(4 * sig * sig + eps * eps)


def sigma_of(X, Y, nu, S):
    return (S + math.atan(math.tanh(nu) * Y / math.sqrt(1 - Y * Y))
            - math.asin(X / math.sqrt(math.cosh(nu) ** 2 - Y * Y)))


def embed_sheared(X, Y, zeta, eps=eps2, S=S2, lam=lam2):
    nu = eps / 2 * math.sin(2 * zeta)
    sig = sigma_of(X, Y, nu, S)
    h = hfun(sig, eps)
    ac = math.sqrt((h - eps) / 2)
    bc = math.sqrt((h + eps) / 2)
    return (ac * math.cos(zeta), bc * math.sin(zeta), -math.asin(Y) / lam)


res2 = []
for chi, zeta in [(0.0, 0.0), (math.pi / 2, math.pi / 4), (math.pi, math.pi / 3)]:
    Xc = -kb * math.cos(chi); Yc = kb * math.sin(chi)
    pt = embed_sheared(Xc, Yc, zeta)
    r, pp, Bv = residual(B_sheared, p_sheared, pt)
    print("fam2 point", pt, "psi=", -pp.v.real * lam2 ** 2, "(target", kb ** 2 / 2, ") res=", r)
    res2.append(r)

# On-axis iota
h0 = hfun(S2, eps2)
Hval, Herr = quad(lambda zt: 1.0 / math.cosh(eps2 / 2 * math.sin(2 * zt)), 0, 2 * math.pi,
                  epsabs=1e-15, epsrel=1e-15, limit=200)
Hval /= 2 * math.pi
iota_axis = h0 * Hval
print("iota_sheared_axis =", iota_axis, "quad err", Herr)


def rhs_factory(k, eps=eps2, S=S2):
    def rhs(zeta, c):
        chi = c[0]
        nu = eps / 2 * math.sin(2 * zeta)
        X = -k * math.cos(chi); Y = k * math.sin(chi)
        sig = sigma_of(X, Y, nu, S)
        G = (hfun(sig, eps) + eps * math.cos(2 * zeta)) / 2
        return [2 * G * math.sqrt(1 - k * k * math.sin(chi) ** 2) / math.sqrt(math.cosh(nu) ** 2 - k * k)]
    return rhs


def period_map(k, chi0, rtol=1e-13, atol=1e-13):
    sol = solve_ivp(rhs_factory(k), (0.0, math.pi), [chi0], method="DOP853", rtol=rtol, atol=atol)
    return sol.y[0, -1]


def weighted_birkhoff(incr):
    N = len(incr)
    t = (np.arange(N) + 0.5) / N
    w = np.exp(-1.0 / (t * (1 - t)))
    return float(np.sum(w * incr) / np.sum(w))


def iota_sheared(k, M=128, Niter=200000, rtol=1e-13):
    # Lift of the Poincare map over one period (pi) of zeta; g(chi)=F(chi)-chi is 2pi-periodic.
    grid = 2 * np.pi * np.arange(M) / M
    g = np.array([period_map(k, c, rtol, rtol) - c for c in grid])
    coef = np.fft.rfft(g) / M
    ks = np.arange(len(coef))
    wgt = np.where((ks == 0) | ((M % 2 == 0) & (ks == M // 2)), 1.0, 2.0)
    cre = (wgt * coef.real); cim = (wgt * coef.imag)
    tail = np.max(np.abs(coef[-8:]))

    def gfun(c):
        ang = ks * c
        return float(np.dot(cre, np.cos(ang)) - np.dot(cim, np.sin(ang)))

    chi = 0.0
    incr = np.empty(Niter)
    for n in range(Niter):
        d = gfun(chi)
        incr[n] = d
        chi += d
    # increments per pi of zeta -> iota = <d> * 2 / (2 pi)
    return weighted_birkhoff(incr) / math.pi, float(np.mean(incr)) / math.pi, tail, g


iota_edge, iota_edge_plain, tail, gvals = iota_sheared(kb, M=128, Niter=100000)
print("iota_edge (M=128, N=1e5): weighted", iota_edge, "plain", iota_edge_plain, "fourier tail", tail)
iota_edge2, iota_edge_plain2, tail2, _ = iota_sheared(kb, M=64, Niter=50000)
print("iota_edge (M=64, N=5e4): weighted", iota_edge2, "plain", iota_edge_plain2, "fourier tail", tail2)

# Direct ODE cross-check over many transits (no interpolation)
Ndir = 400
chi = 0.0
incr = []
rhs = rhs_factory(kb)
for n in range(Ndir):
    sol = solve_ivp(rhs, (0.0, math.pi), [chi], method="DOP853", rtol=1e-13, atol=1e-13)
    chn = sol.y[0, -1]
    incr.append(chn - chi)
    chi = chn
incr = np.array(incr)
print("direct ODE, N=%d half-transits: weighted %.15g plain %.15g" %
      (Ndir, weighted_birkhoff(incr) / math.pi, np.mean(incr) / math.pi))

# Small-k check against on-axis formula
ia_small, _, _, _ = iota_sheared(1e-5, M=32, Niter=20000)
print("iota at k=1e-5:", ia_small, "vs axis formula", iota_axis)

out = {
    "iota_uniform_family": iota_uniform_family,
    "iota_sheared_axis": iota_axis,
    "iota_sheared_edge": iota_edge,
    "force_residual_uniform_family": res1,
    "force_residual_sheared_family": res2,
}
print(json.dumps(out))
