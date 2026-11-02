import json
import mpmath as mp

mp.mp.dps = 40
p = mp.mpf(4)


def J(t):
    """One-sided GOE outlier rate: (1/2) int_t^{-2} sqrt(x^2-4) dx for t<=-2."""
    if t > -2:
        return mp.mpf(0)
    s = -t
    return s * mp.sqrt(s * s - 4) / 4 - mp.log((s + mp.sqrt(s * s - 4)) / 2)


def J_quad(t):
    if t > -2:
        return mp.mpf(0)
    return mp.quad(lambda x: mp.sqrt(x * x - 4), [t, -2]) / 2


def I1(u):
    return J(u * mp.sqrt(p / (p - 1)))


def Theta(k, u):
    return mp.log(p - 1) / 2 - (p - 2) / (4 * (p - 1)) * u ** 2 - (k + 1) * I1(u)


E_inf = 2 * mp.sqrt((p - 1) / p)

# sanity check of closed form against quadrature
assert abs(J(mp.mpf(-3)) - J_quad(mp.mpf(-3))) < mp.mpf(10) ** -25


def root(k):
    f = lambda a: Theta(k, -a)
    # Theta_k(-E_inf) = 0.5 log 3 - (1/6)*3 > 0 ; decreasing beyond -> bracket
    lo, hi = E_inf, E_inf
    assert f(lo) > 0
    while f(hi) > 0:
        hi += mp.mpf("0.5")
    r = mp.findroot(f, (lo, hi), solver="anderson")
    # verify it is the sup: f<0 beyond r (f strictly decreasing for a>E_inf)
    assert f(r + mp.mpf("1e-10")) < 0
    return r


E2 = root(2)
E1 = root(1)
E0 = root(0)
assert E0 > E1 > E2 > E_inf

out = {
    "E_infinity_p4": float(E_inf),
    "E_2_p4": float(E2),
    "E_1_p4": float(E1),
    "E_0_p4": float(E0),
}
print("high precision:", mp.nstr(E_inf, 30), mp.nstr(E2, 30), mp.nstr(E1, 30), mp.nstr(E0, 30))
print(json.dumps(out))
