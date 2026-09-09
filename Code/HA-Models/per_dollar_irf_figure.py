#!/usr/bin/env python3
"""Per-dollar IRF panels (owner-approved normalization, 2026-08-26): consumption response per dollar of the policy's
outlay, by quarter, with AD effects — the revised run from its pickles (thick), the PUBLISHED run recovered from the
published cumulative-multiplier figures (thin; those figures plot cumulative NPV(dC_AD)_t divided by the policy's TOTAL
10-year outlay — verified on the revised tax-cut candidate, whose extracted curve matches that definition and not the
cumulative/cumulative one — so the per-quarter value is the plotted curve's first difference, undiscounted; exact for
all three policies). Writes PDF + PNG.

Usage: python per_dollar_irf_figure.py [--revised Baseline_uiB] [--bugfixed Baseline_ac_pkg] [--out FILE.pdf]
"""
import argparse, os, sys, pickle
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); FPC = os.path.join(HERE, "FromPandemicCode")
QE = os.path.normpath(os.path.join(HERE, "..", "..", "..", "HAFiscal-QE", "Code", "HA-Models", "FromPandemicCode", "Figures"))
sys.path.insert(0, HERE)
import fig_axes
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTCurve
R = 1.01
POLICIES = [("Check", "recessionCheck", "Stimulus check"), ("UI", "recessionUI", "UI extension"), ("TaxCut", "recessionTaxCut", "Tax cut")]


def published_cumulative(policy):
    pdf = os.path.join(QE, f"Cumulative_multiplier_{policy}.pdf")
    ax = fig_axes.extract_axes_from_pdf(pdf)[0]; (x0, y0, x1, y1) = ax["bbox"]; xl, yl = ax["xlim"], ax["ylim"]
    def walk(objs):
        for o in objs:
            if isinstance(o, LTCurve) and len(o.pts) >= 6: yield o
            if hasattr(o, "_objs"): yield from walk(o._objs)
    curves = [c for page in extract_pages(pdf, laparams=LAParams()) for c in walk(page)]
    pts = sorted(max(curves, key=lambda c: len(c.pts)).pts)
    q = np.array([xl[0] + (px - x0) / (x1 - x0) * (xl[1] - xl[0]) for px, py in pts])
    m = np.array([yl[0] + (py - y0) / (y1 - y0) * (yl[1] - yl[0]) for px, py in pts])
    return np.round(q).astype(int), m


def revised(d, pol):
    L = lambda n: pickle.load(open(os.path.join(FPC, "Figures", d, n + ".csv"), "rb"))
    pA, rA, p0, r0 = L(f"{pol}_results_AD"), L("recession_results_AD"), L(f"{pol}_results"), L("recession_results")
    dC = np.asarray(pA["AggCons"]) - np.asarray(rA["AggCons"]); dY = np.asarray(p0["AggIncome"]) - np.asarray(r0["AggIncome"])
    # Normalize by the DISCOUNTED total outlay, matching the convention embedded in
    # published_per_quarter (its un-cumulation multiplies by R**(t+1), i.e. the published
    # cumulative multiplier discounts both legs). The old dY.sum() mixed an undiscounted
    # denominator with a discounted published one — invisible for the 1-quarter check,
    # ~1.5%/3.5% on the 4q/8q policies (dual-path sweep 2026-09-02, NPV domain risk 5).
    dY_npv = float((dY / R ** np.arange(1, len(dY) + 1)).sum())
    return dC / dY_npv, dY / dY_npv          # consumption per discounted dollar of outlay; outlay profile


def published_per_quarter(policy, outlay_profile=None):
    """m(t) = sum_{s<=t} R^-s dC_s / D_total  =>  dC_t / D_total = (m(t) - m(t-1)) * R^t (m(0) = 0)."""
    q, m = published_cumulative(policy)
    per = np.empty(len(q)); per[0] = m[0] * R
    for i in range(1, len(q)): per[i] = (m[i] - m[i - 1]) * R ** (i + 1)
    return q, per


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--revised", default="Baseline_uiB"); ap.add_argument("--bugfixed", default="Baseline_ac_pkg")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "..", "conclusions_private", "artifacts_20260826_uiAB", "per_dollar_irf_20260826.pdf"))
    a = ap.parse_args()
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True)
    for ax, (pol, key, title) in zip(axes, POLICIES):
        cR, yR = revised(a.revised, key); cB, yB = revised(a.bugfixed, key)
        q, cP = published_per_quarter(pol, yR)
        T = 12; x = np.arange(1, T + 1)
        ax.plot(x, 100 * yR[:T], color="#377eb8", lw=1.0, ls=":", label="outlay (income), revised")
        ax.plot(q[:T], 100 * cP[:T], color="#ff7f00", lw=1.2, alpha=0.8, label="consumption, published (recovered)")
        ax.plot(x, 100 * cB[:T], color="#ff7f00", lw=1.6, ls="--", label="consumption, bug-fixed")
        ax.plot(x, 100 * cR[:T], color="#ff7f00", lw=2.4, label="consumption, revised")
        ax.set_title(title); ax.set_xlabel("quarter"); ax.set_xticks(x); ax.grid(alpha=0.25)
    axes[0].set_ylabel("% of the policy's total outlay, per quarter (AD effects)")
    axes[0].legend(fontsize=7.5, loc="upper right")
    fig.tight_layout(); fig.savefig(a.out); fig.savefig(a.out.replace(".pdf", ".png"), dpi=130)
    print("wrote", a.out)
    for pol, key, title in POLICIES:
        cR, yR = revised(a.revised, key); cB, _ = revised(a.bugfixed, key); q, cP = published_per_quarter(pol, yR)
        print(f"{title:14s} published {np.round(100*cP[:6],1)}  bug-fixed {np.round(100*cB[:6],1)}  revised {np.round(100*cR[:6],1)}  (outlay profile {np.round(100*yR[:4],1)})")


if __name__ == "__main__":
    main()
