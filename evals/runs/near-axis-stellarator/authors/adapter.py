"""Adapter: obtain the r1 (Landreman, Sengupta, Plunk 2019) quantities by running pyQSC."""
import os
import sys
import json

os.environ.setdefault("MPLBACKEND", "Agg")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "code"))

from qsc import Qsc  # noqa: E402

cases = {
    "qa_sec51": "r1 section 5.1",
    "qh_sec52": "r1 section 5.2",
    "asym_sec53": "r1 section 5.3",
}

result = {}
for suffix, name in cases.items():
    # Authors' predefined configuration with the default constructor settings (nphi=61).
    stel = Qsc.from_paper(name)
    print(f"{name}: nphi={stel.nphi} helicity={stel.helicity} iota={stel.iota!r} "
          f"iotaN={stel.iotaN!r} max_elongation(code, X-Y plane)={stel.max_elongation!r}")
    result[f"iota_{suffix}"] = float(stel.iota)
    # NOTE: pyQSC's max_elongation is computed from (X1, Y1), i.e. in the plane
    # perpendicular to the axis, not in the R-z plane (see notes.md).
    result[f"max_elongation_{suffix}"] = float(stel.max_elongation)

    # Resolution check only (diagnostic output, not used for reported values).
    for nphi in [31, 101, 151, 201]:
        s = Qsc.from_paper(name, nphi=nphi)
        print(f"   check nphi={s.nphi}: iota={s.iota!r} max_elongation={s.max_elongation!r}")

print(json.dumps(result))
