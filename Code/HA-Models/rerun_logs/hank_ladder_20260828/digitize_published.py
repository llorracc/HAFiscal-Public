#!/usr/bin/env python
"""Digitize the published (QE-frozen) single-panel HANK figures — the three regime curves plotted at quarters
1..12 — from the PDFs' vector paths, using fig_axes.extract_axes_from_pdf for the frame -> data mapping, and
compare with one arm's summary.json (100*dC/C_ss for *_IRF, the cumulative multiplier series for *_multiplier).
usage: digitize_published.py <summary.json> <pdf> [<pdf> ...]"""
import json, os, sys
import numpy as np
sys.path.insert(0, "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models")
import fig_axes
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTCurve, LTLine

COLORS = {"taylor": (0.1216, 0.4667, 0.7059), "fixed_nominal": (1.0, 0.549, 0.0), "fixed_real": (1.0, 0.0, 0.0)}
POL = {"transfer": "transfers", "UI": "UI_extensions", "tax": "tax_cut"}
sj = json.load(open(sys.argv[1]))

def curves(path):
    page = next(extract_pages(path, laparams=LAParams()))
    out = []
    def walk(o):
        if isinstance(o, LTCurve) and not isinstance(o, LTLine) and len(o.pts) >= 10:
            c = o.stroking_color
            c = tuple(c) if isinstance(c, (list, tuple)) and len(c) == 3 else None
            if c is not None:
                out.append((c, o.pts))
        if hasattr(o, "_objs"):
            for c in o:
                walk(c)
    for el in page:
        walk(el)
    return out

for pdf in sys.argv[2:]:
    ax = fig_axes.extract_axes_from_pdf(pdf)[0]
    x0, y0, x1, y1 = ax["bbox"]; xl, yl = ax["xlim"], ax["ylim"]
    base = os.path.basename(pdf).replace(".pdf", "")
    kind = "irf" if base.endswith("_IRF") else "mult"
    pol = POL[base.split("_")[1]]
    print(f"\n== {base}  ({pdf})\n   axes bbox {ax['bbox']} xlim {np.round(xl,3).tolist()} ylim {np.round(yl,4).tolist()}")
    for col, pts in curves(pdf):
        xs = np.array([xl[0] + (p[0] - x0) / (x1 - x0) * (xl[1] - xl[0]) for p in pts])
        ys = np.array([yl[0] + (p[1] - y0) / (y1 - y0) * (yl[1] - yl[0]) for p in pts])
        reg = min(COLORS, key=lambda r: sum((a - b) ** 2 for a, b in zip(COLORS[r], col))) 
        # vertices sit at integer quarters 1..12: pick the one nearest each integer
        q = np.arange(1, 13); yq = np.array([ys[np.argmin(np.abs(xs - k))] for k in q])
        cell = sj["cells"][f"{pol}/{reg}"]
        mine = np.array(cell["irf_pct_12q"] if kind == "irf" else cell["cum_20h"][:12])
        print(f"   {reg:13s} color={np.round(col,3).tolist()} n_pts={len(pts)} x-range [{xs.min():.3f},{xs.max():.3f}]")
        print(f"      published: {np.round(yq, 4).tolist()}")
        print(f"      arm      : {np.round(mine, 4).tolist()}")
        print(f"      max|published-arm| = {np.max(np.abs(yq - mine)):.4e}   (published peak {yq.max():.4f} at q{q[np.argmax(yq)]}; arm peak {mine.max():.4f})")
