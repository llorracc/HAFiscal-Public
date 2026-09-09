#!/usr/bin/env python
"""Compare two HA_Fiscal_Jacs.obj pickles: max|A-B| per key/instrument (+ by education) and the SS aggregates.
usage: compare_jacs.py <A.obj> <B.obj> [label]"""
import pickle, sys
import numpy as np
A = pickle.load(open(sys.argv[1], "rb")); B = pickle.load(open(sys.argv[2], "rb"))
lab = sys.argv[3] if len(sys.argv) > 3 else ""
print(f"compare_jacs {lab}\n  A={sys.argv[1]}\n  B={sys.argv[2]}\n  keys A={sorted(A)} B={sorted(B)}")
overall = 0.0
for key in ("C", "A"):
    for ins in A[key]:
        a = np.asarray(A[key][ins]); b = np.asarray(B[key][ins])
        m = float(np.max(np.abs(a - b))); sa = float(np.max(np.abs(a))); overall = max(overall, m)
        print(f"  {key:2s} {ins:10s} max|dJ|={m:.3e}  max|A|={sa:.4e}  rel={m/sa if sa else 0:.3e}  A[0,0]={a[0,0]:+.7f} B[0,0]={b[0,0]:+.7f}")
for key in ("C_by_educ", "A_by_educ"):
    for e in A[key]:
        ms = []
        for ins in A[key][e]:
            a = np.asarray(A[key][e][ins]); b = np.asarray(B[key][e][ins])
            ms.append((float(np.max(np.abs(a - b))), ins))
        mm = max(ms); overall = max(overall, mm[0])
        print(f"  {key} {e:10s} max over instruments |dJ|={mm[0]:.3e} ({mm[1]})")
for k in ("C_ss_weighted", "A_ss_weighted"):
    if k in A or k in B:
        print(f"  {k}: A={A.get(k)} B={B.get(k)}")
print(f"  OVERALL max|dJ| = {overall:.3e}")
