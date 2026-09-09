"""The two comparison figure sets (owner charge 2026-09-02).

Set A — the original QE HANK vs the debugged HANK, consumption IRFs.
  QE side: rerun_logs/hank_ladder_20260828/arm0_published/mult_dump.pkl —
  the frozen monolith at the published shape on the QE calibration, verified
  against the published 0.14.1 pickle at 2.0e-8 (rung B0's dual-verified
  basis). New side: the current production dump (all fixes + the adopted
  improvements). IRFs plotted as dC_t / C_ss (percent of steady-state
  consumption, level-invariant across the two calibrations), 20 quarters,
  one figure per regime (taylor, fixed_real; the peg is excluded per the
  standing rule), three policy panels each.

Set B — the debugged HANK multipliers vs the PE multipliers.
  PE side: the world-of-record Step-5a cumulative multipliers by horizon
  (Figures/Baseline_lam/C_Multiplier_Baseline_Results.csv — a pickle:
  check 1.3183 / UI 1.2500 / tax 1.0857 at the long horizon). HANK side:
  the same production dump, taylor and fixed_real. Conventions mirror the
  paper's Cumulative_multipliers_withHank figure exactly: 12 quarters,
  check #4daf4a / UI #377eb8 / tax #ff7f00, PE solid vs HANK dotted.

Usage: python -m ssj_ladder.make_compare_figs --new-dump D --out DIR
"""
import argparse
import os
import pickle

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
HA = os.path.dirname(HERE)
QE_DUMP = os.path.join(HA, "rerun_logs", "hank_ladder_20260828",
                       "arm0_published", "mult_dump.pkl")
PE_MULT = os.path.join(HA, "FromPandemicCode", "Figures", "Baseline_lam",
                       "C_Multiplier_Baseline_Results.csv")

# Every figure carries a small verification footnote (owner charge
# 2026-09-02: "reassure the user looking at the figure that it has been
# verified and is not a bug") pointing at the README.md sidecar in the
# output directory, which holds the reasoning and links the full records.
README_URL = ("https://github.com/llorracc/HAFiscal-Latest/blob/"
              "0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC/"
              "Code/HA-Models/rerun_logs/hank_compare_figs_20260902/README.md")


def _verification_note(fig, text):
    fig.text(0.01, 0.034, text, fontsize=6.5, color="0.45",
             ha="left", va="bottom")
    t = fig.text(0.01, 0.008, "details: " + README_URL,
                 fontsize=6.0, color="0.45", ha="left", va="bottom")
    t.set_url(README_URL)          # clickable in the PDF outputs


NOTE_A = ("Verified, not a bug: at published settings this construction reproduces the published curves; the "
          "tax-cut shape changes because the published block omitted permanent-income growth.")
NOTE_B = ("Verified: the HANK block reproduces the PE model with GE mechanisms off (the PE-reproduction "
          "gate); remaining HANK-vs-PE gaps are general-equilibrium economics, not defects.")
NOTE_C = ("Verified, not a bug: cumulative totals nearly coincide by q12; the tax cut's early gap comes from "
          "adding permanent-income growth to the household block (omitted in the published version).")


POLICIES = (("transfers", "Stimulus check", "#4daf4a"),
            ("UI_extensions", "UI extension", "#377eb8"),
            ("tax_cut", "Tax cut", "#ff7f00"))
REGIMES = (("taylor", "Taylor rule"), ("fixed_real", "Fixed real rate"))
T_IRF = 20
T_MULT = 12


def _css_from_dump(d, fallback):
    ss = d.get("ss", {})
    for k in ("C_ss", "household"):
        if k in ss:
            v = ss[k]
            return float(v["C_ss"]) if isinstance(v, dict) else float(v)
    return fallback


def set_a(qe, new, css_qe, css_new, out):
    for reg, reg_lab in REGIMES:
        fig, axes = plt.subplots(1, 3, figsize=(11, 3.4), sharex=True)
        for ax, (pol, lab, col) in zip(axes, POLICIES):
            cq = np.asarray(qe["irfs"][pol][reg]["C"], float)[:T_IRF]
            cn = np.asarray(new["irfs"][pol][reg]["C"], float)[:T_IRF]
            x = np.arange(1, T_IRF + 1)
            ax.plot(x, 100 * cq / css_qe, color="0.35", linestyle="--",
                    label="original (QE)")
            ax.plot(x, 100 * cn / css_new, color=col, linestyle="-",
                    label="debugged")
            ax.axhline(0, color="0.85", lw=0.8, zorder=0)
            ax.set_title(lab, fontsize=11)
            ax.set_xlabel("quarter")
        axes[0].set_ylabel("consumption, % of steady state")
        axes[0].legend(frameon=False, fontsize=9)
        fig.suptitle(f"Consumption IRFs — original QE HANK vs debugged HANK "
                     f"({reg_lab})", fontsize=12)
        fig.tight_layout(rect=(0, 0.075, 1, 0.94))
        _verification_note(fig, NOTE_A)
        for ext in ("pdf", "png"):
            fig.savefig(os.path.join(out, f"IRF_compare_QE_vs_new_{reg}.{ext}"),
                        dpi=150)
        plt.close(fig)
        print(f"[figs] set A: IRF_compare_QE_vs_new_{reg}.pdf/png")


def set_b(pe, new, out):
    pe_series = {"transfers": np.asarray(pe["C_Multiplier_Rec_Check_AD"], float),
                 "UI_extensions": np.asarray(pe["C_Multiplier_UI_Rec_AD"], float),
                 "tax_cut": np.asarray(pe["C_Multiplier_Rec_TaxCut_AD"], float)}
    x = np.arange(1, T_MULT + 1)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), sharey=True)
    for ax, (reg, reg_lab) in zip(axes, REGIMES):
        handles = []
        for pol, lab, col in POLICIES:
            h1, = ax.plot(x, pe_series[pol][:T_MULT], color=col, linestyle="-")
            hk = np.atleast_1d(np.asarray(new[pol][reg], float))[:T_MULT]
            h2, = ax.plot(x, hk, color=col, linestyle=":")
            handles += [(h1, lab), (h2, f"{lab}, HANK")]
        ax.set_title(f"HANK: {reg_lab}", fontsize=11)
        ax.set_xlabel("quarter")
        ax.set_xticks(np.arange(1, T_MULT + 1, 1))
    axes[0].set_ylabel("cumulative multiplier")
    axes[0].legend([h for h, _ in handles], [l for _, l in handles],
                   frameon=False, fontsize=8, ncol=1)
    fig.suptitle("Cumulative multipliers — PE model vs debugged HANK",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0.075, 1, 0.93))
    _verification_note(fig, NOTE_B)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(out, f"Multipliers_PE_vs_newHANK.{ext}"),
                    dpi=150)
    plt.close(fig)
    print("[figs] set B: Multipliers_PE_vs_newHANK.pdf/png")


def set_c(qe, new, out):
    """Set C (owner request 2026-09-02): cumulative multipliers, original QE
    HANK vs the debugged HANK, per regime. Each model runs its OWN rule —
    the QE original's published un-smoothed Taylor (rho_r = 0) vs the
    debugged model's adopted inertial rule (rho_r = 0.70, IMPROVEMENT-003);
    fixed-real needs no such caveat (structurally rho_r-free in both)."""
    x = np.arange(1, T_MULT + 1)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), sharey=True)
    for ax, (reg, reg_lab) in zip(axes, REGIMES):
        handles = []
        for pol, lab, col in POLICIES:
            mq = np.atleast_1d(np.asarray(qe[pol][reg], float))[:T_MULT]
            mn = np.atleast_1d(np.asarray(new[pol][reg], float))[:T_MULT]
            h1, = ax.plot(x, mq, color=col, linestyle="--")
            h2, = ax.plot(x, mn, color=col, linestyle="-")
            handles += [(h1, f"{lab}, original (QE)"), (h2, f"{lab}, debugged")]
        ax.set_title(reg_lab, fontsize=11)
        ax.set_xlabel("quarter")
        ax.set_xticks(np.arange(1, T_MULT + 1, 1))
    axes[0].set_ylabel("cumulative multiplier")
    axes[0].legend([h for h, _ in handles], [l for _, l in handles],
                   frameon=False, fontsize=8, ncol=1)
    fig.suptitle("Cumulative multipliers — original QE HANK vs debugged HANK",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0.075, 1, 0.93))
    _verification_note(fig, NOTE_C)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(out, f"Multipliers_QEHANK_vs_newHANK.{ext}"),
                    dpi=150)
    plt.close(fig)
    print("[figs] set C: Multipliers_QEHANK_vs_newHANK.pdf/png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new-dump", required=True)
    ap.add_argument("--new-ss", default="", help="ss.pkl for the new side's C_ss")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    with open(QE_DUMP, "rb") as f:
        qe = pickle.load(f)
    with open(a.new_dump, "rb") as f:
        new = pickle.load(f)
    with open(PE_MULT, "rb") as f:
        pe = pickle.load(f)
    css_qe = _css_from_dump(qe, 0.7229)
    if a.new_ss:
        with open(a.new_ss, "rb") as f:
            css_new = float(pickle.load(f)["household"]["C_ss"])
    else:
        css_new = _css_from_dump(new, 0.7047)
    print(f"[figs] C_ss: QE {css_qe:.4f}  new {css_new:.4f}")
    set_a(qe, new, css_qe, css_new, out)
    set_b(pe, new, out)
    set_c(qe, new, out)


if __name__ == "__main__":
    main()
