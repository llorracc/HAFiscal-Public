#!/usr/bin/env python3
"""N-ladder analysis (certification §2): as-corrected world at HS_Only, paper's engine (legacy, non-shuffled) vs the
certified package (calendar + stratified), N in {1500, 6000, 24000}, seeds 0..5. Prints per cell and N: mean gap
(package - paper), its SE, the per-seed SDs of both engines and the variance ratio. Reads
Tables/HS_Only_ac_{paper,pkg}_N{N}_seed{K}/welfare6_parallel_summary.json (whatever exists so far)."""
import glob, json, os, sys
import numpy as np
T = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Tables"
CELLS = ["ui_norec", "ui_rec", "ui_rec_AD", "check_rec", "check_rec_AD", "taxcut_rec_AD"]
def load(tag, N):
    rows = []
    for K in range(12):
        f = f"{T}/HS_Only_{tag}_N{N}_seed{K}/welfare6_parallel_summary.json"
        if os.path.exists(f): rows.append(json.load(open(f))["welfare6"])
    return rows
for N in (1500, 6000, 24000, 96000):
    P, Q = load("ac_paper", N), load("ac_pkg", N)
    if not P or not Q: print(f"N={N}: paper {len(P)} seeds, package {len(Q)} seeds -- not ready"); continue
    print(f"\nN={N}: paper's engine {len(P)} seeds, package {len(Q)} seeds")
    print(f"{'cell':14s}{'paper mean':>12s}{'SD':>9s}{'pkg mean':>12s}{'SD':>9s}{'gap':>10s}{'gap SE':>9s}{'gap/SE':>8s}{'var ratio':>11s}")
    for c in CELLS:
        a = np.array([float(r[c]) for r in P]); b = np.array([float(r[c]) for r in Q])
        sa, sb = a.std(ddof=1), b.std(ddof=1); gap = b.mean() - a.mean(); se = np.sqrt(sa**2/len(a) + sb**2/len(b))
        print(f"{c:14s}{a.mean():12.4f}{sa:9.4f}{b.mean():12.4f}{sb:9.4f}{gap:10.4f}{se:9.4f}{gap/se if se else 0:8.2f}{(sa/sb)**2 if sb else float('nan'):11.2f}")
