#!/usr/bin/env python
"""Per-column Jacobian comparison: max|A-B| over column 0 vs over columns s>=1, per key/instrument, plus the SS
aggregates. usage: compare_cols.py <A.obj> <B.obj> [label]  (A = reference)"""
import pickle, sys
import numpy as np
A = pickle.load(open(sys.argv[1], "rb")); B = pickle.load(open(sys.argv[2], "rb"))
print(f"compare_cols {sys.argv[3] if len(sys.argv) > 3 else ''}\n  A={sys.argv[1]}\n  B={sys.argv[2]}")
m0 = m1 = 0.0
for key in ("C", "A"):
    for ins in A[key]:
        a = np.asarray(A[key][ins]); b = np.asarray(B[key][ins]); d = np.abs(a - b)
        c0, c1 = float(d[:, 0].max()), float(d[:, 1:].max()); m0 = max(m0, c0); m1 = max(m1, c1)
        print(f"  {key:2s} {ins:10s} col0 max|dJ|={c0:.3e} (A[0,0]={a[0,0]:+.6f} B[0,0]={b[0,0]:+.6f})   cols>=1 max|dJ|={c1:.3e}   max|A|={float(np.abs(a).max()):.3e}")
for k in ("C_ss_weighted", "A_ss_weighted"):
    print(f"  {k}: A={A.get(k)} B={B.get(k)}")
print(f"  OVERALL column-0 max|dJ| = {m0:.3e};  columns>=1 max|dJ| = {m1:.3e}")
