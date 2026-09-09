#!/usr/bin/env python3
"""Breakdown of the '+corrections to the original code' column (owner protocol 2026-08-27, plan section 5e, ruling 4):
each correction measured FORWARD on the original model (the QE calibration + conventions on the current certified
machinery), one at a time; the estimation-side corrections attributed by ONE joint pair (ruling 3) = the remainder.

  original model            Baseline_orig       (5a) + Baseline_orig_seed*        dell P18
  + solver fix AFTER its matched re-estimation  Baseline_orig_pgf_reest (5a) + _seed*  dell P24  BUG-047 (the raw arm orig_pgf is record-only)
      (re-estimated by the CURRENT Step-2 estimator -- pinned GICx, BUG-034 aggregation -- at the paper's 40/48 grid, CDC, QE atom clip;
       65 solves/group, 2 min; atoms dropout 0.685/0.364, HS 0.906/0.109, college 0.9876/0.0202 vs QE 0.719/0.318, 0.929/0.072, 0.9825/0.0140)
  + tail extrapolation fix  Baseline_orig_pfx   (5a) + Baseline_orig_pfx_seed*    m5 P18   BUG-061/062
  all corrections           Baseline_ac_pkg     (5a) + Baseline_ac_pkg_seed*      (the chain's column: + the joint re-estimation, ESC)
ORIG arms carry HAFISCAL_GIC_SHAVE_ON_GPF=0 (the QE beta-atom clip; BUG-053 addendum 2026-08-27).
The remainder (all corrections minus the runtime-measurable rows) is the joint estimation-side pair: the corrected
Step-1/Step-2 (BUG-053 GIC cap on the growth-patience factor, BUG-034 wealth aggregation, ...) with the ESC interpretation.
Welfare cells compared seed-for-seed where seeds overlap. Usage: python corrections_breakdown_table.py [--out FILE.md]
"""
import argparse, glob, json, os
import numpy as np
from waterfall_table import T, mult_rows, welfare, CELLS

# Rows are cumulative from the TRUE original (orig_typo: the published tax-cut construction, BUG-023 present); the
# one-at-a-time rows (pgf, pfx) sit on top of `orig` (= original + the BUG-023 fix), which is what P18 ran.
# OWNER RULING 2026-08-27 16:05: a corrected bug is reported AFTER its matched re-estimation, never as a raw effect plus
# a separate re-estimation row. The raw arm (orig_pgf) stays on disk for the BUG-047 record only; the consumption-tail
# arm (orig_pfx) is not reported (owner 16:20: negligible) -- it remains on disk.
ROWS = [("original model (QE calibration + conventions; BUG-023 present)", "orig_typo"),
        ("+ tax-cut solve fix (BUG-023)", "orig"),
        ("+ solver fix (BUG-047) WITH its matched re-estimation (current Step-2 estimator; solve-time conventions the paper's; cold single start) [on top of the BUG-023 row]", "orig_pgf_reest"),
        ("+ the remaining corrections other than the cap, as one joint pair (estimation-side items, ESC) = the capped corrected world", "ac_pkg"),
        ("+ no age cap, with its re-estimation (owner 2026-08-27: a correction -- the published code estimated uncapped, simulated capped) = ALL corrections", "nocap_pkg")]
# the uncapped corrected world's 5a table lives under the multiplier program's arm name (its battery under nocap_pkg_seed*)
MULT_TAG = {"nocap_pkg": "uiL_permoff"}
SHOW = ["check_rec", "ui_rec", "taxcut_rec", "check_rec_AD", "ui_rec_AD", "taxcut_rec_AD"]


def by_seed(g):
    return {f.split("_seed")[1].split(os.sep)[0]: json.load(open(f))["welfare6"]
            for f in glob.glob(os.path.join(T, g, "welfare6_parallel_summary.json"))}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=None); a = ap.parse_args()
    base = by_seed("Baseline_orig_typo_seed*"); mb = mult_rows(os.path.join(T, "Baseline_orig_typo", "Multiplier_candidate.tex"))
    if not base:   # until the true-original battery lands, welfare deltas compare against `orig` (multipliers keep orig_typo's 5a)
        base = by_seed("Baseline_orig_seed*")
        if "AD" not in mb:
            mb = mult_rows(os.path.join(T, "Baseline_orig", "Multiplier_candidate.tex"))
    L = ["# Breakdown of the corrections column — forward, on the original model", "",
         "| step | AD multipliers Check / UI / TaxCut (Δ % vs original) | " + " | ".join(f"{c} (Δ %)" for c in SHOW) + " |",
         "|---|---|" + "---|" * len(SHOW)]
    for label, tag in ROWS:
        m = mult_rows(os.path.join(T, f"Baseline_{MULT_TAG.get(tag, tag)}", "Multiplier_candidate.tex")); arm = by_seed(f"Baseline_{tag}_seed*")
        # Every delta is against the TRUE original (orig_typo) -- since 2026-08-27 evening its tax-cut cells are the paper's
        # experiment reproduced on the exact TM (HAFISCAL_LEGACY_TAXCUT_ATOM=1), so no published-number fallback is needed.
        if "AD" in m and "AD" in mb and tag != "orig_typo":
            mcell = " / ".join(f"{v} ({100 * (float(v) / float(b) - 1):+.1f} %)" for v, b in zip(m["AD"], mb["AD"]))
        else:
            mcell = " / ".join(m.get("AD", ["—"] * 3))
        cells = []
        seeds = sorted(set(arm) & set(base))
        for c in SHOW:
            if not arm:
                cells.append("—"); continue
            va = np.mean([arm[k][c] for k in sorted(arm)])
            if tag == "orig_typo" or not seeds:
                cells.append(f"{va:.3f} (S={len(arm)})")
            else:
                vb = np.mean([base[k][c] for k in seeds]); vs = np.mean([arm[k][c] for k in seeds])
                cells.append(f"{va:.3f} ({100 * (vs / vb - 1):+.1f} % same-seed, S={len(seeds)})")
        L.append(f"| {label} | {mcell} | " + " | ".join(cells) + " |")
    L += ["", "The original model's tax-cut cells are the paper's experiment reproduced on the exact TM (HAFISCAL_LEGACY_TAXCUT_ATOM=1,",
          "2026-08-27): households solved under the published construction, the real cut paid. All deltas are same-machinery.",
          "", "The capped-corrected-world row minus the BUG-023 and BUG-047(+re-estimation) rows = the remaining estimation-side items as",
          "one joint pair (the corrected Step-1/Step-2: GIC cap on the growth-patience factor BUG-053, wealth aggregation BUG-034,",
          "the tail extrapolation BUG-061/062 at the K*h grid, the ESC interpretation). Walls: rerun_logs/ui_ext_20260826/p18*,p20,p24r,p28.out."]
    text = "\n".join(L) + "\n"
    if a.out:
        open(a.out, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
