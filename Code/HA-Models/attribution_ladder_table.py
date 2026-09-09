#!/usr/bin/env python3
"""Bug-fix attribution ladder (memo §2; owner "construct all", 2026-08-26): the as-corrected world = the BUGFIXED engine
(`Baseline_ac_pkg`, 5a + S=5) with ONE fix toggled back to its published value per arm — what each fix moves, on the
three AD multipliers and the nine welfare-6 cells. Arms (5a + seeds 0,1 each; dell P9 + m5 P9):

  published-path defects (in the published results themselves):
    pfdecay      HAFISCAL_PF_DECAY_EXTRAP=0           BUG-061/062  naive-linear cFunc extrapolation above the solve grid
  defects of the revision's own pipeline (never in the published numbers; caught by its guards):
    welfare6dur  HAFISCAL_WELFARE6_FIX_DUR_AVG=off   BUG-046  u(E[c]) in welfare6_mc(); the QE Welfare.py applied u per duration
  new-engine construction (choices in the transition-matrix engine; convergence evidence, not defects in the paper):
    tma          HAFISCAL_TM_A_INDEXED=0             BUG-033  m-indexed TM (collapses the splurge's xi-variance)
    amax         HAFISCAL_TM_AMAX=500                 BUG-084  distribution-grid top 500 (truncates the College GIC-cap atom);
                 null on the multipliers in BOTH worlds (uncapped check: Baseline_uiA_amax500 vs Baseline_uiA, +-0.1 %, xubuntark 2026-08-27)
    qmethod      HAFISCAL_TM_Q_METHOD=cohort          BUG-093  cap-exact start + plain kernel (~1 % L1 level offset)
    pfq          HAFISCAL_PF_DECAY_Q=slope            BUG-089  tail exponent from the top-segment slope, not measured
  not toggleable at run time (attributed by construction in the memo): BUG-053 (GIC-cap factor; re-estimation),
  BUG-090 / BUG-091 (the welfare battery solved policies the simulation did not deliver; SST fixes).

Usage: python attribution_ladder_table.py [--out FILE.md]   (arms missing tonight print as —)
"""
import argparse, glob, json, os, re
import numpy as np
from waterfall_table import T, mult_rows, welfare, CELLS

BASE = ("bug-fixed engine (as-corrected)", "Baseline_ac_pkg", "Baseline_ac_pkg_seed*")
ARMS = [("revision pipeline", "welfare formula u(E[c]) (BUG-046; the QE Welfare.py had the correct order)", "ac_nofix_welfare6dur"),
        ("published-path", "naive-linear cFunc tail (BUG-061/062)", "ac_nofix_pfdecay"),
        ("new-engine", "m-indexed TM (BUG-033)", "ac_nofix_tma"),
        ("new-engine", "grid top 500 (BUG-084)", "ac_nofix_amax"),
        ("new-engine", "cohort Q-construction (BUG-093)", "ac_nofix_qmethod"),
        ("new-engine", "slope tail exponent (BUG-089)", "ac_nofix_pfq")]
MKEYS = [("AD", "AD multiplier")]
SHOW = ["check_rec", "ui_rec", "taxcut_rec", "check_rec_AD", "ui_rec_AD", "taxcut_rec_AD"]


def pct(a, b):
    return "—" if not (np.isfinite(a) and np.isfinite(b)) or b == 0 else f"{100 * (a / b - 1):+.1f} %"


def same_seed_means(arm_glob, base_glob):
    """Per-cell (arm mean, base mean over the SAME seeds) -- the arms run 2 seeds on other machines, the base 5 on dell;
    comparing seed-for-seed removes the seed-subset difference (which is +0.1..+0.9 % on the UI cells)."""
    def by_seed(g):
        return {f.split("_seed")[1].split(os.sep)[0]: json.load(open(f))["welfare6"]
                for f in glob.glob(os.path.join(T, g, "welfare6_parallel_summary.json"))}
    a, b = by_seed(arm_glob), by_seed(base_glob)
    seeds = sorted(set(a) & set(b))
    out = {}
    for c in CELLS:
        va = np.array([a[k][c] for k in seeds], float); vb = np.array([b[k][c] for k in seeds], float)
        out[c] = (va.mean() if len(seeds) else np.nan, vb.mean() if len(seeds) else np.nan, len(seeds))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=None); a = ap.parse_args()
    mb = mult_rows(os.path.join(T, BASE[1], "Multiplier_candidate.tex")); wb = welfare(BASE[2])
    L = ["# Bug-fix attribution ladder — the as-corrected engine with ONE fix at its published value per arm", "",
         f"Base: {BASE[0]} — AD multipliers {' / '.join(mb.get('AD', ['—'] * 3))} (Check / UI / TaxCut); welfare S={wb['check_rec'][2]}.",
         "Entries: the arm's value and its change from the base (welfare: the arm's seeds vs the base's SAME seeds — seed-for-seed, so the",
         "S=2-vs-S=5 subset difference is removed; the base's across-seed SE is the noise scale — inside ±2 SE is not distinguishable from zero).", "",
         "| fix toggled off | class | AD mult. Check / UI / TaxCut (Δ %) | " + " | ".join(f"{c} (Δ %)" for c in SHOW) + " |",
         "|---|---|---|" + "---|" * len(SHOW)]
    for cls, label, tag in ARMS:
        m = mult_rows(os.path.join(T, f"Baseline_{tag}", "Multiplier_candidate.tex")); w = welfare(f"Baseline_{tag}_seed*")
        if "AD" in m and "AD" in mb:
            mcell = " / ".join(f"{v} ({pct(float(v), float(b))})" for v, b in zip(m["AD"], mb["AD"]))
        else:
            mcell = "—"
        cells = []
        ss = same_seed_means(f"Baseline_{tag}_seed*", BASE[2])
        for c in SHOW:
            am, bm_same, nS = ss.get(c, (np.nan, np.nan, 0)); bm, bse, bS = wb.get(c, (np.nan, np.nan, 0))
            cells.append("—" if not np.isfinite(am) else f"{am:.3f} ({pct(am, bm_same)} same-seed; {abs(am - bm_same) / bse:.1f} SE, S={nS})" if np.isfinite(bse) and bse > 0 else f"{am:.3f} ({pct(am, bm_same)}, S={nS})")
        L.append(f"| {label} | {cls} | {mcell} | " + " | ".join(cells) + " |")
    L += ["", "Not toggleable at run time: BUG-053 (GIC-cap factor 0.999 → 0.9995, carried by the re-estimated calibration), BUG-090 and",
          "BUG-091 (the welfare battery's own solve of the unemployed-income process and the tax cut's length — SST fixes; the",
          "battery now consumes the multiplier program's solutions and solves nothing)."]
    text = "\n".join(L) + "\n"
    if a.out:
        open(a.out, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
