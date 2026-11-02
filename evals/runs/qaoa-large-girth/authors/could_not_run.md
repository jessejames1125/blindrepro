# Partial failure: the authors' optimizer (code/src/optimize.cpp) could not be built

The authors get the maximum over (gamma, beta) by running optimize.cpp. It uses LBFGSpp's LBFGSSolver with epsilon=1e-7, max_iterations=1000, and forward-difference gradients with step delta taken from argv. This program could not be compiled.

What I tried:
- `ziglang` (clang 16/19 + libc++) with Eigen 3.4.0 from `cmeel-eigen`. optimize.cpp failed with:
  `code\src\optimize.cpp:6:10: fatal error: 'LBFGS.h' file not found`
- I looked for a pip package that ships the LBFGSpp headers. `lbfgspp` and `cmeel-lbfgspp` are not in the package registry ("was not found in the package registry"). The `gpboost` wheel does not ship them either. Scripts have no network access, so I could not fetch LBFGSpp (github.com/yixuan/LBFGSpp) any other way.
- No system C++ compiler or header tree was reachable. Listing C:\msys64 and Visual Studio was blocked by the guard.

Missing: the header-only LBFGSpp library (include/LBFGS.h and LBFGSpp/*.h).

What did run: the authors' evaluator (evaluate.cpp and MatrixBuilder in matrix_builder.cpp, after a two-line edit to make it compile, see notes.md). It was run at the authors' published optimal parameters from code/data.csv. The values in adapter.py's JSON are therefore nu_p at the published (rounded) optimal parameters. They are not the output of a fresh optimization run.
