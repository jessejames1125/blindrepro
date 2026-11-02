# Notes / assumptions

- Generators and periods for the five codes come from spec.json and match the paper text (108-qubit example). I typed in no other code constants.
- Monomial x^i y^j maps to index i + l*j (x index fastest), as the paper says. L_c has column g = c*g, and c* is (x,y) -> (x^-1, y^-1) with exponents taken mod l and m.
- H = H_Z = [L_{b*} | L_{a*}] (paper eq. sector). k = 2N - 2 rank(H). The script asserts H_X H_Z^T = 0 and rank H_X = rank H_Z.
- The metacheck space is ker H^T, the vectors orthogonal to every column of H. M is a basis of that space. Any basis gives the same d_S and the same leader histogram.
- d_S is the smallest nonzero weight in im H = ker M, i.e. the smallest number of columns of M that sum to zero. It is found by BFS: d_S = 1 + min over h of the BFS distance from 0 to column h, using only the other columns. This is exact because a shortest representation never repeats a column.
- The leader histogram c_w comes from a BFS over all 2^{r_M} metasyndromes, with the columns of M as generators (paper App. A). Only weights are counted, so the tie-break order does not matter.
- The p^2 coefficient is found by expanding P(p) = 1 - sum_w c_w p^w (1-p)^(N-w) exactly in sympy (paper eq. exact_repair).
- Sanity check: the running BB(3,3) example reproduces the paper's stated k=8, d_S=3 and histogram (1,9,6).
- I took no constants from memory.
