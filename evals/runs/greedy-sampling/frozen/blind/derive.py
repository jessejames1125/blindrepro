import json
import numpy as np


def K(c, s, t):
    # sin(c(s-t))/(pi(s-t)) = (c/pi) * sinc(c(s-t)/pi), np.sinc(x)=sin(pi x)/(pi x); diag = c/pi
    d = np.subtract.outer(np.asarray(s, float), np.asarray(t, float))
    return (c / np.pi) * np.sinc(c * d / np.pi)


def pgreedy_max_power(c, ngrid, m):
    X = np.linspace(-1.0, 1.0, ngrid)
    pow2 = np.full(ngrid, c / np.pi)
    V = np.zeros((m, ngrid))
    for j in range(m):
        idx = int(np.argmax(pow2))  # first index on ties; argmax of Pow == argmax of Pow^2
        piv = np.sqrt(pow2[idx])
        kcol = K(c, X, np.array([X[idx]]))[:, 0]
        if j > 0:
            kcol = kcol - V[:j].T @ V[:j, idx]
        v = kcol / piv
        V[j] = v
        pow2 = np.maximum(pow2 - v * v, 0.0)
    return float(np.sqrt(np.max(pow2)))


def gelfand_lower(c, q, n):
    x, w = np.polynomial.legendre.leggauss(q)
    w = w / 2.0  # probability weights
    sw = np.sqrt(w)
    A = sw[:, None] * K(c, x, x) * sw[None, :]
    A = 0.5 * (A + A.T)
    th = np.sort(np.linalg.eigvalsh(A))[::-1]
    th = np.maximum(th, 0.0)  # eigenvalues are >= 0 in exact arithmetic
    return float(np.sqrt(np.sum(th[n:q])))


res = {}
for neff, ngrid, q in [(20, 8000, 210), (40, 8000, 370), (80, 10000, 690)]:
    c = neff * np.pi / 2.0
    res[f"pgreedy_max_power_neff{neff}_m{neff}"] = pgreedy_max_power(c, ngrid, neff)
    res[f"gelfand_lower_neff{neff}_n{neff}"] = gelfand_lower(c, q, neff)
    print(f"Neff={neff}: sqrt(c/pi)={np.sqrt(c/np.pi)}")

print(json.dumps(res))
