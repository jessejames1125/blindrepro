# Notes

- Source: code/bb_manuscript_reproduce.py (the only script; README says it reproduces every exact quantity in the paper). No files under code/ were edited.
- adapter.py imports the module and calls the authors' `audit_code()` on their `STANDARD_CODES` with the same settings their `main()` uses by default (no `--quick`): exact_onesided=True, mu_max=16, cross_check=False. The spec quantities don't depend on these settings. I did not call `main()` itself because it only prints part of the values (r_M and the histograms go to a CSV); `audit_code` is the function `main()` calls.
- Code parameters (l, m, a, b) in STANDARD_CODES match spec.json for all five codes.
- H: the authors use H = H_Z = [L_b^T | L_a^T]. Since L_c^T = L_{c*}, this is the spec's [L_{b*} | L_{a*}]. Monomial index i + l*j matches the spec.
- k: the authors compute k = n - rank(H_X) - rank(H_Z), not the spec's 2N - 2 rank(H). These agree because rank H_X = rank H_Z here; their own check r_M = k/2 passes.
- r_M = number of rows of nullspace(H^T) = N - rank(H), as in the spec.
- d_S: the authors' `syndrome_distance(mcheck)` is exact only up to weight 4 and returns None above that. Every code gives 2 or 3, so this limit doesn't matter.
- Gross c_0, c_1, c_2: taken from the authors' breadth-first `coset_leaders(mcheck)` histogram, which is (1, 36, 27).
- p^2 coefficient: computed the authors' way, C(36,2) - c_2 = 603 (they derive it from d_S = 3). The spec defines it as the Taylor coefficient of 1 - sum_w c_w p^w (1-p)^(N-w). Working that expansion by hand with (c_0, c_1, c_2) = (1, 36, 27) gives -(630 - 36*35 + 27) = 603, so the two definitions agree. This hand check was not computed by adapter.py.
- The authors' built-in check against the manuscript reported no disagreements. Their P_repair(0.01) for [[72,12,6]] is 0.04842711803694644 (printed for information, not in spec).
- requirements.txt: numpy only, unpinned. The code needs nothing version-specific (Python >= 3.10 for int.bit_count). matplotlib is optional and isn't used by the adapter.
- Runtime is about 68 s, nearly all spent on the [[288,12,18]] one-sided and mu(g) searches that are part of audit_code under the default settings.
