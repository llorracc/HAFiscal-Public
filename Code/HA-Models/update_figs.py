"""Render the HAFiscal_update figure panels (task #50; the August HAFiscal_update.pdf was retired 2026-09-09 -- the panels now serve the co-author briefing HAFiscal_update_for_coauthors.md).

Reproduces the PUBLISHED figure's construction (Output_Results.py,
Cumulative_multipliers_withHank): the PE cumulative multipliers as
SOLID lines and the HANK-SAM series as DOTTED lines in the same colors
(check #4daf4a, UI #377eb8, tax cut #ff7f00), horizons 1-12 quarters —
but with the corrected HANK artifacts, one panel per monetary regime:

  HAFiscal_update_figs/withHank_taylor.pdf      — FEATURED (active
      Taylor; the 2026-08-10 "mainly" ruling)
  HAFiscal_update_figs/withHank_fixed_real.pdf  — the robustness
      companion (level-invariant; matches the PE fixed-R assumption)

The PE lines are identical in both panels and reproduce the published
PE results (their long-run limits are the published table's
1.239/1.248/1.016 — verified).

Inputs: the regime-pure 3x3 HANK dump (HAFISCAL_HANK_MULT_DUMP) and
the Step-5 Baseline PE arrays
(FromPandemicCode/Figures/Baseline/C_Multiplier_Baseline_Results.csv —
a pickle despite the extension).

Usage: python Code/HA-Models/update_figs.py [hank_dump] [pe_pickle]
"""
import os
import pickle
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT_DIR = os.path.join(ROOT, "HAFiscal_update_figs")

HANK_DUMP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, "solution_cache", "_armc_bench", "update_figs_dump.obj")
PE_PICKLE = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    HERE, "FromPandemicCode", "Figures", "Baseline",
    "C_Multiplier_Baseline_Results.csv")

# The certified current-default whole-cell battery (production seed 0; the
# post-epoch 2026-07-28 run — cross-validated 2026-08-10 against a cold m5
# end-to-end regeneration to ~1%).
W6_PICKLE_DIR = os.path.join(HERE, "FromPandemicCode",
                             "welfare6_scenario_results_Baseline")

GREEN, BLUE, ORANGE = "#4daf4a", "#377eb8", "#ff7f00"
MAX_T = 12


def render(pe, hank, regime, regime_label, title, out_pdf):
    x = np.arange(MAX_T) + 1
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    ax.plot(x, pe["C_Multiplier_Rec_Check_AD"][:MAX_T], color=GREEN, linestyle="-")
    ax.plot(x, np.asarray(hank["transfers"][regime])[:MAX_T], color=GREEN, linestyle=":")
    ax.plot(x, pe["C_Multiplier_UI_Rec_AD"][:MAX_T], color=BLUE, linestyle="-")
    ax.plot(x, np.asarray(hank["UI_extensions"][regime])[:MAX_T], color=BLUE, linestyle=":")
    ax.plot(x, pe["C_Multiplier_Rec_TaxCut_AD"][:MAX_T], color=ORANGE, linestyle="-")
    ax.plot(x, np.asarray(hank["tax_cut"][regime])[:MAX_T], color=ORANGE, linestyle=":")
    ax.legend(["Check", f"Check, HANK ({regime_label})",
               "UI extension", f"UI extension, HANK ({regime_label})",
               "Tax cut", f"Tax cut, HANK ({regime_label})"],
              fontsize=9)
    plt.xticks(np.arange(1, MAX_T + 1, 1))
    ax.set_xlabel("quarter")
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(out_pdf)
    plt.close(fig)
    h = MAX_T - 1
    print(f"[update-figs] wrote {out_pdf}  (HANK h=12: "
          f"{hank['transfers'][regime][h]:.3f}/"
          f"{hank['UI_extensions'][regime][h]:.3f}/"
          f"{hank['tax_cut'][regime][h]:.3f}; PE h=12: "
          f"{pe['C_Multiplier_Rec_Check_AD'][h]:.3f}/"
          f"{pe['C_Multiplier_UI_Rec_AD'][h]:.3f}/"
          f"{pe['C_Multiplier_Rec_TaxCut_AD'][h]:.3f})")




def render_pe_published_vs_current():
    """Paired-bar proof figure: QE-published vs corrected-pipeline PE
    multipliers (spending 10-yr NPV + welfare6 Rec=1 rows), with the
    percent change printed above each pair. Published spending = the
    frozen QE table (printed 3dp); current spending = the
    provenance-verified Baseline C_Multiplier arrays (limits);
    welfare rows parsed from the QE repo's and the current pipeline's
    welfare6.tex."""
    import re
    import matplotlib.patches as mpatches
    pub_spend = [1.239, 1.248, 1.016]
    pe = pickle.load(open(PE_PICKLE, "rb"))
    cur_spend = [pe["C_Multiplier_Rec_Check_AD"][399],
                 pe["C_Multiplier_UI_Rec_AD"][399],
                 pe["C_Multiplier_Rec_TaxCut_AD"][399]]

    def parse_w6(path):
        txt = open(path).read()
        out = {}
        for tag, key in (("Rec=1, AD=0", "ad0"), ("Rec=1, AD=1", "ad1")):
            m = re.search(re.escape(tag) + r"\)\$\s*&\s*([\d.]*)\s*&\s*([\d.]*)\s*&\s*([\d.]*)", txt)
            out[key] = [float(x) for x in m.groups()]
        return out

    pub_w = parse_w6(os.path.join(ROOT, "..", "HAFiscal-QE", "Code",
                     "HA-Models", "FromPandemicCode", "Tables", "CRRA2", "welfare6.tex"))
    # Current welfare MUST come from the certified battery pickles, never from
    # Tables/Baseline/welfare6.tex: under the QE candidate-freeze that file is
    # a 2026-05-10 fossil (batteries write welfare6_candidate.tex siblings), and
    # reading it as "current" produced the stale +12/+17% UI claim corrected
    # 2026-08-10.
    fpc = os.path.join(HERE, "FromPandemicCode")
    _cwd = os.getcwd()
    os.chdir(fpc)
    try:
        sys.argv = [sys.argv[0]]
        sys.path.insert(0, fpc)
        from run_welfare6_parallel import compute_welfare6_table
        w6, _ = compute_welfare6_table(W6_PICKLE_DIR)
    finally:
        os.chdir(_cwd)
    cur_w = {"ad0": [w6["check_rec"], w6["ui_rec"], w6["taxcut_rec"]],
             "ad1": [w6["check_rec_AD"], w6["ui_rec_AD"], w6["taxcut_rec_AD"]]}
    colors = ["#4daf4a", "#377eb8", "#ff7f00"]
    pols = ["Check", "UI ext.", "Tax cut"]

    def panel(ax, pub, cur, title, fmt):
        xs = np.arange(3); w = 0.36
        for i, (p, c, col) in enumerate(zip(pub, cur, colors)):
            ax.bar(xs[i] - w/2, p, w, color=col, alpha=0.38, hatch="//",
                   edgecolor=col, linewidth=1.2)
            ax.bar(xs[i] + w/2, c, w, color=col)
            ax.text(xs[i], max(p, c) * 1.02, fmt(100*(c-p)/p),
                    ha="center", fontsize=9, fontweight="bold")
        ax.set_xticks(xs); ax.set_xticklabels(pols, fontsize=9)
        ax.set_title(title, fontsize=10)
        ax.set_ylim(0, max(max(pub), max(cur)) * 1.16)
        ax.tick_params(axis="y", labelsize=8)

    fig, axs = plt.subplots(1, 3, figsize=(10.8, 3.9))
    panel(axs[0], pub_spend, cur_spend,
          "Spending multipliers (10-yr NPV, AD effects)", lambda d: f"{d:+.2f}%")
    panel(axs[1], pub_w["ad0"], cur_w["ad0"],
          "Welfare multipliers (Rec=1, AD=0)", lambda d: f"{d:+.1f}%")
    panel(axs[2], pub_w["ad1"], cur_w["ad1"],
          "Welfare multipliers (Rec=1, AD=1)", lambda d: f"{d:+.1f}%")
    h1 = mpatches.Patch(facecolor="grey", alpha=0.38, hatch="//",
                        edgecolor="grey", label="Published (QE)")
    h2 = mpatches.Patch(facecolor="grey", label="Current (corrected pipeline)")
    fig.legend(handles=[h1, h2], loc="lower center", ncol=2, fontsize=9,
               frameon=False)
    plt.tight_layout(rect=[0, 0.06, 1, 1])
    for ext in ("pdf", "png"):
        plt.savefig(os.path.join(OUT_DIR, f"pe_published_vs_current.{ext}"), dpi=150)
    plt.close(fig)
    print("[update-figs] wrote pe_published_vs_current.pdf/.png")


def main():
    with open(HANK_DUMP, "rb") as f:
        hank = pickle.load(f)
    with open(PE_PICKLE, "rb") as f:
        pe = pickle.load(f)
    os.makedirs(OUT_DIR, exist_ok=True)
    render(pe, hank, "taylor", "active Taylor",
           "Corrected, FEATURED: PE model vs. HANK under the active Taylor rule",
           os.path.join(OUT_DIR, "withHank_taylor.pdf"))
    render(pe, hank, "fixed_real", "fixed real",
           "Corrected, companion: PE model vs. HANK under a fixed real rate",
           os.path.join(OUT_DIR, "withHank_fixed_real.pdf"))
    render_pe_published_vs_current()


if __name__ == "__main__":
    main()
