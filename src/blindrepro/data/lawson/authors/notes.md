# Notes

- Source of the result: the Table 3 (`tab:minimum_triple_product_table`) cells in `code/lawson-criterion-paper.py` ("Calculate requirements for D-T, Catalyzed D-D, D-3He, and p-11B" plus the "Numerically find minimum ..." cell). adapter.py pulls the text of those two cells out of the file and runs it with exec, unchanged. Only the D-T rows are reported.
- I did not run the whole notebook: it needs LaTeX (`text.usetex`) and builds every figure. The cells I ran only need math, numpy, pandas and `lib.fusionlib`.
- No files under code/ were edited.
- Settings are the authors' as written in the cell: `relativistic_mode='putvinski'`, `density='ion'`, `method='integrated'` (the `optimal_mix_triple_product` default, which numerically integrates the Bosch-Hale cross section), xi=1, a grid of 300 log-spaced points from 0.5 to 500 keV, D-T kept only for 1 < T < 100 keV, minimum taken with idxmin.
- The minimum temperatures are points on the authors' 300-point grid (13.6067 and 14.2502 keV). They are not continuous optima, and I did not refine them.
- Difference from spec (f_c): spec says f_c = 3.5/17.6 = 0.19886. The code uses `fraction_charged = 0.2` from `lib/reactions.ini`. I used the code's value.
- Difference from spec (bremsstrahlung): spec says the loss term is C_B T^1/2 with no relativistic correction. The Table 3 cell uses the Putvinski relativistic correction (Zeff*(1+1.78 t^1.34) + 2.12 t (...), t = T/511). I used the code's version. As a check only, the same code with `'nonrelativistic'` gives 4.644767e20 (Q=1) and 2.931542e21 (Q=inf) at the same grid temperatures. The reported values are 4.648208e20 and 2.945042e21.
- Difference from spec (units): spec says 1 MeV = 1.6e-13 J and C_B = 5.34e-37 W m^3 keV^-1/2. The code works in keV: C_B = 1.69e-38 * 6.24e18 / sqrt(1000) keV s^-1 m^3 keV^-1/2 (6.24e18 eV/J, i.e. 1 eV = 1.6026e-19 J), and eps_F = 17.6e3 keV. I used the code's values.
- Requirements are pinned to the versions in the authors' uv.lock: numpy 2.2.6, scipy 1.16.1, pandas 2.2.2.
- One run takes about 260 s, because the cell computes every reaction with integrated reactivities.
