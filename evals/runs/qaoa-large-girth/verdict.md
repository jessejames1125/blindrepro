# Blind reproduction: The Quantum Approximate Optimization Algorithm at High Depth for MaxCut on Large-Girth Regular Graphs and the Sherrington-Kirkpatrick Model

**Result: REPRODUCED: max error 4.5e-06%, limit 5%.**

- Paper: arXiv:2110.14206 https://arxiv.org/abs/2110.14206
- Authors' code: https://github.com/benjaminvillalonga/large-girth-maxcut-qaoa at b5bbc23ad4309af12a95666862cd082bddcac0e3
- Target: The table of the infinite-degree QAOA MaxCut values nu_p and the optimal parameters' energy for depths p = 1 to 8
- Claim tested: For the depth-p QAOA applied to MaxCut on large-girth (D+1)-regular graphs, in the limit D -> infinity, the cut fraction is 1/2 + nu_p(gamma,beta)/sqrt(D), where nu_p is given by the paper's infinite-D G-matrix iteration (equivalently, the QAOA energy density on the SK model). The tested result is the optimum bar_nu_p = max over (gamma,beta) of nu_p for depths p = 1 to 8.

## Values

```
quantity     blind  authors' code   paper     error
---------  -------  -------------  ------  --------
nu_bar_p1  0.30327        0.30327  0.3033  6.7e-10%  ok
nu_bar_p2  0.40755        0.40755  0.4075  3.0e-06%  ok
nu_bar_p3  0.47262        0.47262  0.4726  7.8e-07%  ok
nu_bar_p4  0.51568        0.51568  0.5157  1.2e-06%  ok
nu_bar_p5  0.54765        0.54765  0.5476  1.9e-06%  ok
nu_bar_p6  0.57214        0.57214  0.5721  3.9e-06%  ok
nu_bar_p7  0.59148        0.59148  0.5915  4.0e-06%  ok
nu_bar_p8  0.60727        0.60727  0.6073  4.5e-06%  ok
```

Error is |blind - authors| / |authors|, or the plain difference where the authors' value is 0. The arithmetic is done by code, not a model.
Paper values, where shown, were read from the paper by a model and were hidden from the blind agent.

**The authors' code needed an edit to run.** See `authors/patch.diff`.

## Authors' code did not run

# Partial failure: the authors' optimizer (code/src/optimize.cpp) could not be built

The authors get the maximum over (gamma, beta) by running optimize.cpp. It uses LBFGSpp's LBFGSSolver with epsilon=1e-7, max_iterations=1000, and forward-difference gradients with step delta taken from argv. This program could not be compiled.

What I tried:
- `ziglang` (clang 16/19 + libc++) with Eigen 3.4.0 from `cmeel-eigen`. optimize.cpp failed with:
  `code\src\optimize.cpp:6:10: fatal error: 'LBFGS.h' file not found`
- I looked for a pip package that ships the LBFGSpp headers. `lbfgspp` and `cmeel-lbfgspp` are not in the package registry ("was not found in the package registry"). The `gpboost` wheel does not ship them either. Scripts have no network access, so I could not fetch LBFGSpp (github.com/yixuan/LBFGSpp) any other way.
- No system C++ compiler or header tree was reachable. Listing C:\msys64 and Visual Studio was blocked by the guard.

Missing: the header-only LBFGSpp library (include/LBFGS.h and LBFGSpp/*.h).

What did run: the authors' evaluator (evaluate.cpp and MatrixBuilder in matrix_builder.cpp, after a two-line edit to make it compile, see notes.md). It was run at the authors' published optimal parameters from code/data.csv. The values in adapter.py's JSON are therefore nu_p at the published (rounded) optimal parameters. They are not the output of a fresh optimization run.

## What the blind agent says it assumed or took from memory

- Method: infinite-D G-matrix iteration exactly as in paper Sec. 3.2 / spec.json; nu taken as the real part (imaginary part ~1e-15 is roundoff).
- Used symmetry f(-a)=f(a), H(-a)=H(a) (paper Sec. 4.1) to sum over half the bit strings (a_1=+1) and double; exact, not an approximation.
- Gradient by hand-written reverse-mode differentiation of the iteration (holomorphic chain rule, real part taken); checked against central finite differences for p<=3 (err ~1e-10).
- Optimizer: scipy L-BFGS-B (paper used LBFGS++); "global maximum" = best over multistart: the paper's 4-digit optimal angles (Appendix table) as one warm start, the INTERP p->p+1 heuristic (from memory: Zhou et al., PRX 2020, ref ZhouQAOA in paper) as another, plus uniform random starts (gamma in [0.05,1.2], beta in [-0.8,0.8]; ranges my own choice). Fewer random starts at p=7,8 because of the 600 s runtime limit.
- Global optimality cannot be proven; the reported values are the best local maxima found, and all non-random starts converged to the same value.
- Sanity check from memory: p=1 SK optimum is 1/sqrt(4e)=0.303265... at gamma=1/2, beta=pi/8 (Farhi et al. 2019); the code reproduces it but does not use it.

## How the authors' code was called

# Notes on settings and choices

- Authors' code: C++ in code/src (matrix_builder.cpp = infinite-D G-matrix iteration; evaluate.cpp = nu_p at given params; optimize.cpp = LBFGS++ maximization). MaxCut is the q=2 case (`evaluate_matrix` uses M^q and sqrt(2/q), which is 1 for q=2).
- **The authors' optimizer (optimize.cpp) could not be built:** it needs the header-only LBFGSpp library (`#include <LBFGS.h>`), which is not in the repo and not on PyPI (tried `lbfgspp`, `cmeel-lbfgspp`, and checked the `gpboost` wheel). See could_not_run.md.
- So the reported numbers are NOT outputs of their optimization run. Each one is nu_p from the authors' own evaluator (MatrixBuilder::build_matrix + evaluate_matrix, i.e. evaluate.cpp) at the authors' published optimal (gamma, beta) for q=2, p=1..8, which come from code/data.csv (columns 4..4+2p-1, given to 4 decimals). The "optimal nu" column of data.csv is not used. It is only a sanity check (it matches to 4 digits).
- Because the parameters are rounded to 4 decimals, each value is a lower bound on the true maximum and sits very close to it (the gradient is zero at the optimum, so the error is second order). For p=1 the exact value is 1/sqrt(4e)=0.303265329856317. We get 0.3032653298542708, which is about 2e-12 lower.
- Compiler: no system compiler is reachable, so I used zig's clang/libc++ (pip `ziglang==0.14.0`). zig 0.11.0 failed at link time (`undefined symbol _create_locale`, a mingw/libc++ issue). Eigen 3.4.0 headers come from pip `cmeel-eigen==3.4.0.2` (the code needs Eigen >= 3.4 for `Eigen::all` / `Eigen::Vector`).
- Build flags: same as the Makefile (-O3 -march=native) but without -fopenmp, because zig ships no OpenMP runtime. `<omp.h>` is replaced by a single-thread stub, shim/omp.h (omp_get_thread_num()=0, omp_get_max_threads()=1). This does not change the math. It only changes the order of the floating-point summation compared with a multi-threaded run.
- **Edit to code/ (required to compile):** in code/src/matrix_builder.cpp, lines 29 and 31, `types::Complex({0., 1.})` was changed to `types::Complex(0., 1.)`. Under libc++ (zig 0.11 and 0.14) the braced form is an ambiguous constructor call (complex<float> vs complex<long double> converting constructors). It compiles under the authors' g++/libstdc++. Both forms give the same value, the imaginary unit i.
- Precision: evaluate.cpp prints with setprecision(8). To report full precision I also built shim/evaluate_fullprec.cpp. It is a copy of evaluate.cpp's main with setprecision(17) that does not print the matrix, and it links the authors' unchanged matrix_builder.cpp. The adapter runs both binaries: the 8-digit output of the authors' evaluate.cpp matches the 17-digit values for every p. The JSON reports the 17-digit values.
- Spec vs. code: the spec's definition (Gamma ordering, f(a), G iteration, nu = (i/2) sum Gamma_j G_{0j}^2) is what MatrixBuilder implements for q=2. I found no difference in settings.

## What was blinded

- Authors' code: fetched at 2026-11-02T11:26:55Z, after the derivation froze at 2026-11-02T11:26:48Z.
- Agent tools: Edit, Glob, Grep, Read, Write, run. No shell, no web.
- Scripts run under a guard with network, other processes and outside files off. Blocked attempts: 0. Refused tool calls: 0.
- Target values in the paper: 2 passages and 2 code links removed before the agent read it.
- Leak check: 8 target values still appeared in the text the agent read (see verdict.json).
- Typed-in answers: 1 numbers in derive.py match a target value (see verdict.json).
- Scripts: the agent's drafts import no networking, process or low-level module.
- Memory check: asked with no paper and no tools, the model stated 8 of 8 values, 8 within the limit.
- Model training cutoff: 2026-06 per the vendor. Paper first posted 2021-10-27, before that, so it may be in training data.

## What was not blinded

- The agent read the paper, including its method. That is the point of the test.
- A model may have seen this paper or code during training. The memory check catches stated values, not everything a model absorbed.
- The freeze hash proves the files did not change later. It does not prove when they were made, or that the operator ran this once. To prove the order, publish the hash before comparing (--stop-after-freeze).
- The guard stops accidents and ordinary model behavior. A script that patches Python's own modules or loads native code could get around it; the flags above and the transcript are the check for that.
- The adapter that calls the authors' code was written by a model. It is in the record for inspection.

## Record

- Freeze hash (SHA-256): `d8f4e3677325f709e02216672f13d6225e2981e6ab13750d03dc9018a1e1b80d`
- Model: claude-opus-5-5, through claude-cli 2.1.316
- Tool: blindrepro 0.1.0. Run date: 2026-11-02.
- Python 3.12.13. Packages: mpmath==1.3.0, numpy==2.5.4, scipy==1.18.1, sympy==1.14.0.
- Prompts, transcripts and the derivation are in this folder. The paper's text and the authors' code are withheld as hashes and links.
- The whole folder, the authors' side included, is hashed once more at the end in `seal.json`.
- Check again: `blindrepro verify <this folder> --expect <freeze hash>`
