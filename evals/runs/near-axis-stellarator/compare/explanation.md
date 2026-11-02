Only `max_elongation_qh_sec52` is marked within=false. The blind side gives 2.522 and the authors' side gives 3.081.

**First point of difference:** the two sides measure elongation in different planes.

- **Blind side:** `derivation/derive.py` lines 137–144 convert (X1, Y1) to (R1, z1) using the l'/R0 transform. They then take the elongation in the cylindrical R-z plane, which is what spec.json asks for.
- **Authors' side:** `authors/code/qsc/calculate_r1.py` lines 129–136 compute p and q directly from X1s, X1c, Y1s, Y1c. That is the elongation in the plane perpendicular to the axis. The comment at lines 129–130 says (R,Z) could be used instead, but the code doesn't. `authors/adapter.py` line 27 reports this `max_elongation` as is, and `authors/notes.md` line 6 admits the mismatch.

The other inputs agree: the iota values match to about 1e-15, so the geometry, N and sigma match too. The QH axis has the largest shaping, which is likely why the two planes differ most there. In the other two cases the gap is under 1%.

**My judgment:** this is a definition mismatch on the authors' side, introduced by the adapter. It is not an error on the blind side and not a paper ambiguity. The blind value (2.522) matches the paper's 2.52. pyQSC's number is correct for the quantity it defines. I read the code but did not run either side.