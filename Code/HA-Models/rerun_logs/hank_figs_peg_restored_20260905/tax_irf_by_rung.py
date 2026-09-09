#!/usr/bin/env python
"""Tax-cut consumption IRF by ladder rung, one panel per monetary regime (peg, active Taylor rule, fixed real
rate), plus today's production model. Reads each arm's mult_dump.pkl (QE calibration, rho_r = 0 in every arm)
and the production dump. Every panel carries a legend (owner rule 2026-09-05).
usage: tax_irf_by_rung.py <ladder dir> <out stem> arm:label [arm:label ...] [--production path:label]"""
import os, pickle, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
root, stem = sys.argv[1], sys.argv[2]; specs = sys.argv[3:]
series = []
i = 0
while i < len(specs):
    if specs[i] == "--production":
        p, lab = specs[i + 1].split(":", 1); d = pickle.load(open(p, "rb")); css = float((d.get("ss") or {}).get("C_ss", 0.6986))
        nprod = sum(1 for x in series if x[3].get("color") in ("black", "dimgray"))
        series.append((lab, d, css, dict(linewidth=2.5, color="black" if nprod == 0 else "dimgray", linestyle="-" if nprod == 0 else "--"))); i += 2; continue
    arm, lab = specs[i].split(":", 1); p = os.path.join(root, arm, "mult_dump.pkl")
    if os.path.exists(p):
        d = pickle.load(open(p, "rb")); css = float((d.get("ss") or {}).get("C_ss", 0.69105))
        series.append((lab, d, css, dict(linewidth=1.6)))
    i += 1
Q = 8; x = np.arange(1, Q + 1)
fig, axs = plt.subplots(1, 3, figsize=(13, 4))
for ax, (reg, title) in zip(axs, (("fixed_nominal", "fixed nominal rate (peg)"), ("taylor", "active Taylor rule"), ("fixed_real", "fixed real rate"))):
    for lab, d, css, kw in series:
        C = 100 * np.asarray(d["irfs"]["tax_cut"][reg]["C"])[:Q] / css
        ax.plot(x, C, marker="o", markersize=3, label=lab, **kw)
    ax.axhline(0, color="k", linewidth=0.6); ax.set_title(f"tax cut, {title}", fontsize=10)
    ax.set_xlabel("quarter"); ax.set_ylabel("% consumption deviation"); ax.set_xticks(x)
    ax.legend(fontsize=7, loc="best")
fig.suptitle("Tax-cut consumption IRF by ladder rung (QE calibration, rho_r = 0 in every rung) and today's production model", fontsize=10)
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(f"{stem}.{ext}", dpi=150)
print("wrote", stem + ".{png,pdf}", "series:", [s[0] for s in series])
