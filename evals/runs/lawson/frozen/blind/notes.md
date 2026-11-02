# Assumptions and constants from memory

- Bosch & Hale (1992) D-T cross-section S-factor coefficients (B_G=34.3827 keV^1/2, A1..A5=6.927e4, 7.454e8, 2.050e6, 5.2002e4, 0; B1..B4=63.8, -0.995, 6.981e-5, 1.728e-4; sigma in mb, E = CM energy in keV) are from memory of Bosch & Hale, Nucl. Fusion 32, 611 (1992), Table IV (fit range 0.5-550 keV).
- Reduced-mass energy mu c^2 = 1124656 keV for D-T is from memory (Bosch & Hale 1992, Table VII); speed of light 2.99792458e8 m/s is the SI exact value.
- The paper says reactivities come from numerically integrating the Bosch-Hale cross section, so the reported values use Maxwellian integration: <sigma v> = c*sqrt(8/(pi mu c^2)) T^-3/2 * integral sigma(E) E exp(-E/T) dE.
- Above 550 keV the low-energy fit is simply extended; at T of about 14 keV this tail is negligible (exp(-550/14) ~ 1e-17 relative).
- For a cross-check, the script also computes the Bosch-Hale reactivity parametrization (C1..C7 = 1.17302e-9, 1.51361e-2, 7.51886e-2, 4.60643e-3, 1.35e-2, -1.0675e-4, 1.366e-5; Table VII, from memory). It gives minima about 0.6% higher and T_min about 0.03 keV lower. This difference is within the stated fit accuracy of the S-factor fit. These values are printed but are not the reported values.
- Units: in 3T^2, one factor of T is converted keV->J using 1 keV = 1.6e-16 J (from the paper's 1 MeV = 1.6e-13 J) so that 3nT is an energy density. The other T stays in keV, so the result is in m^-3 keV s.
- The minimum over T is found with a grid from 1 to 100 keV (0.01 keV step), then refined with Brent's method. Only points with a positive denominator are used.
