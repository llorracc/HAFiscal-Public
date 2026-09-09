#!/usr/bin/env python
"""Tax-cut and check consumption responses under the three regimes, quarters 1-5 in % of C_ss, per ladder arm.
usage: peg_impact_by_arm.py <ladder dir> arm ..."""
import os, pickle, sys
import numpy as np
root = sys.argv[1]
for arm in sys.argv[2:]:
    p = os.path.join(root, arm, "mult_dump.pkl")
    if not os.path.exists(p): print(f"{arm}: no dump"); continue
    d = pickle.load(open(p, "rb")); ss = d.get("ss", {}) or {}
    css = float(ss.get("C_ss", 0.69105))
    for pol in ("tax_cut", "transfers"):
        line = f"{arm:24s} {pol:9s}"
        for reg in ("fixed_nominal", "taylor", "fixed_real"):
            C = 100 * np.asarray(d["irfs"][pol][reg]["C"])[:5] / css
            line += f" | {reg[:5]} " + " ".join(f"{x:5.2f}" for x in C)
        print(line)
