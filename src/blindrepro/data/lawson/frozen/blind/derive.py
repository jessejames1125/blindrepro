import json
import numpy as np
from scipy import integrate, optimize

# ---------------- constants (from paper / spec) ----------------
MeV_J = 1.6e-13                 # paper: 1 MeV = 1.6e-13 J
eps_F = 17.6 * MeV_J            # J
f_c = 3.5 / 17.6
C_B = 5.34e-37                  # W m^3 keV^-1/2

# ---------------- Bosch & Hale (1992) D-T (from memory) ----------------
BG = 34.3827                    # keV^1/2
MRC2 = 1124656.0                # keV, reduced mass energy D-T
C_LIGHT = 2.99792458e8          # m/s
# cross-section S-factor coefficients, 0.5 - 550 keV
A = [6.927e4, 7.454e8, 2.050e6, 5.2002e4, 0.0]
B = [6.38e1, -9.95e-1, 6.981e-5, 1.728e-4]


def sigma_mb(E):
    """Bosch-Hale D-T cross section in mb, E = CM energy in keV."""
    num = A[0] + E * (A[1] + E * (A[2] + E * (A[3] + E * A[4])))
    den = 1.0 + E * (B[0] + E * (B[1] + E * (B[2] + E * B[3])))
    S = num / den
    return S / (E * np.exp(BG / np.sqrt(E)))


def sv_integrated(T):
    """Maxwellian reactivity in m^3/s by numerical integration of sigma(E)."""
    f = lambda E: sigma_mb(E) * 1e-31 * E * np.exp(-E / T)
    # integrate up to energies where the Maxwellian factor is negligible
    Emax = min(550.0, 60.0 * T) if T < 9.0 else 550.0
    pts = [T, 5 * T]
    pts = [p for p in pts if p < Emax]
    val, _ = integrate.quad(f, 1e-6, Emax, points=pts, limit=500,
                            epsabs=0, epsrel=1e-13)
    # tail above 550 keV (outside low-energy fit range); negligible at T<~100 keV
    if Emax == 550.0:
        tail, _ = integrate.quad(f, 550.0, 550.0 + 60 * T, limit=200,
                                 epsabs=0, epsrel=1e-12)
        val += tail
    return C_LIGHT * np.sqrt(8.0 / (np.pi * MRC2)) * T ** -1.5 * val


# Bosch-Hale reactivity parametrization (cross-check)
C1, C2, C3, C4, C5, C6, C7 = (1.17302e-9, 1.51361e-2, 7.51886e-2, 4.60643e-3,
                              1.35e-2, -1.0675e-4, 1.366e-5)


def sv_param(T):
    theta = T / (1 - T * (C2 + T * (C4 + T * C6)) / (1 + T * (C3 + T * (C5 + T * C7))))
    xi = (BG ** 2 / (4 * theta)) ** (1 / 3)
    return C1 * theta * np.sqrt(xi / (MRC2 * T ** 3)) * np.exp(-3 * xi) * 1e-6


def triple(T, invQ, sv):
    den = (f_c + invQ) * sv(T) * eps_F / 4 - C_B * np.sqrt(T)
    if den <= 0:
        return np.inf
    # numerator: 3 n T (energy, T converted keV->J) times T in keV
    return 3 * (T * MeV_J * 1e-3) * T / den


def minimize(invQ, sv):
    Ts = np.linspace(1.0, 100.0, 9901)
    vals = np.array([triple(T, invQ, sv) for T in Ts])
    i = int(np.argmin(vals))
    res = optimize.minimize_scalar(lambda T: triple(T, invQ, sv),
                                   bracket=(Ts[i - 1], Ts[i], Ts[i + 1]),
                                   tol=1e-12)
    return float(res.fun), float(res.x)


out = {}
for label, invQ in (("1", 1.0), ("inf", 0.0)):
    v, T = minimize(invQ, sv_integrated)
    vp, Tp = minimize(invQ, sv_param)
    print(f"Q={label}: integrated min={v:.10e} at T={T:.8f} keV; "
          f"parametrized min={vp:.10e} at T={Tp:.8f} keV")
    out[f"dt_min_triple_product_qfuel_{label}"] = v
    out[f"dt_temperature_at_min_triple_product_qfuel_{label}"] = T

for T in (10.0, 20.0):
    print(f"sv check T={T}: int={sv_integrated(T):.6e} param={sv_param(T):.6e} m^3/s")

print(json.dumps(out))
