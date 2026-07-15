#!/usr/bin/env python3
"""welfare_drift_report.py — MC cross-section drift report (v2: confound-robust).

Standing rule: every MC-mode welfare run must report the cross-section drift of the
simulated population vs the TM-a ergodic it was initialized from. This computes it
POST-HOC from the per-cell `aNrm_all_bs` / `pLvl_all_bs` panels welfare6_scenario saves
(no re-run). The "_bs" panels are the baseline (no-recession) sim, warm-started at the
TM-a ergodic (BUG-052 default-on TM_INIT), so the t=0 cross-section IS the ergodic
benchmark and the drift is t=end vs t=0.

v2 fixes the two interpretation confounds the v1 metric had:
  1. CONSTRAINED-MASS COMPOSITION (assets). aNrm has a borrowing-constrained mass at 0
     (log-undefined). v1's var(log aNrm | aNrm>0) was confounded by that mass *moving*
     (agents on/off the constraint change which agents enter the log-variance). v2's
     headline asset signal is composition-robust: the constrained FRACTION + aNrm
     quantiles (P10/P50/P90 of the WHOLE distribution, constrained mass included). The
     log-moments are still reported, but labeled CONFOUNDED-secondary.
  2. LEVEL TREND (income). pLvl is a level, so mean(log pLvl) drifts with the common
     permanent-income growth — that is a trend, not departure from the ergodic. The
     trend-INVARIANT income signal is var(log pLvl) (the idiosyncratic spread, which has
     an ergodic value); the mean drift is reported but labeled TREND.

STILL PENDING (needs compute, not a read): a multi-seed SE so drift can be separated from
MC sampling noise (the standing rule). This single-run report shows the raw drift; run the
multi-seed companion (welfare base cell across seed_offsets) to bound the SE.

Part of the --complete verification suite — plans/20260622_reuse-fidelity-verification-flag-taxonomy.md.

Usage: python welfare_drift_report.py [results_dir]
"""
from __future__ import annotations
import glob
import os
import pickle
import sys

import numpy as np

_FLOOR = 1e-12  # aNrm <= floor := borrowing-constrained (log undefined)


def _summary(a_row, p_row):
    """Confound-robust cross-section summary for one (aNrm, pLvl) time slice."""
    unc = a_row > _FLOOR
    aP10, aP50, aP90 = (float(x) for x in np.percentile(a_row, [10, 50, 90]))
    la = np.log(a_row[unc])
    lp = np.log(np.maximum(p_row, _FLOOR))
    return {
        "cfrac": float(1.0 - unc.mean()),
        "aP10": aP10, "aP50": aP50, "aP90": aP90,
        "la_m": float(la.mean()), "la_v": float(la.var()),
        "lp_m": float(lp.mean()), "lp_v": float(lp.var()),
    }


def _rel(s0, sE, k):
    return (sE[k] - s0[k]) / abs(s0[k]) if abs(s0[k]) > 1e-12 else (sE[k] - s0[k])


def drift_for_cell(pkl_path):
    d = pickle.load(open(pkl_path, "rb"))
    if "aNrm_all_bs" not in d or "pLvl_all_bs" not in d:
        return None
    a = np.asarray(d["aNrm_all_bs"], dtype=np.float64)   # (T, N)
    p = np.asarray(d["pLvl_all_bs"], dtype=np.float64)
    s0, sE = _summary(a[0], p[0]), _summary(a[-1], p[-1])
    return {
        "cell": os.path.basename(pkl_path)[:-4], "T": int(a.shape[0]), "N": int(a.shape[1]),
        # ROBUST drift signals (composition-robust assets; trend-invariant income spread):
        "d_cfrac": sE["cfrac"] - s0["cfrac"],
        "d_aP50_rel": _rel(s0, sE, "aP50"),
        "d_aP90_rel": _rel(s0, sE, "aP90"),
        "d_var_log_p": sE["lp_v"] - s0["lp_v"],
        # CONTEXT (not failures): income mean drift = growth trend; var(log a) = confounded.
        "d_mean_log_p_trend": sE["lp_m"] - s0["lp_m"],
        "d_var_log_a_confounded": sE["la_v"] - s0["la_v"],
        "start": s0,
    }


def multiseed_report(dirs):
    """Per-cell drift across >=2 seed result-dirs -> mean +/- SE + real-vs-noise verdict.

    The standing rule: never report a drift without a multi-seed SE. A robust drift signal
    whose |mean| exceeds ~2x its cross-seed SE is a REAL ergodic-departure; |mean| within
    the SE is sampling noise. Reports only cells present in ALL dirs (e.g. 'base')."""
    keys = ["d_cfrac", "d_aP50_rel", "d_aP90_rel", "d_var_log_p"]
    perdir, cell_sets = [], []
    for d in dirs:
        cells = {}
        for pkl in glob.glob(os.path.join(d, "*.pkl")):
            r = drift_for_cell(pkl)
            if r:
                cells[r["cell"]] = r
        perdir.append(cells)
        cell_sets.append(set(cells))
    common = sorted(set.intersection(*cell_sets)) if cell_sets else []
    if not common:
        print("no cell common to all seed dirs", file=sys.stderr)
        return 1
    print(f"MULTI-SEED MC DRIFT — {len(dirs)} seeds; mean +/- SE, |mean|/SE "
          f"(>2sigma => REAL drift, not noise)")
    print(f"dirs: {', '.join(dirs)}\n")
    for cell in common:
        print(f"  cell '{cell}'  (N={perdir[0][cell]['N']}/seed):")
        for k in keys:
            v = np.array([perdir[i][cell][k] for i in range(len(dirs))])
            m, sd = float(v.mean()), float(v.std(ddof=1))
            se = sd / np.sqrt(len(v))
            # se==0 means every seed agreed exactly: a nonzero common drift is then
            # infinitely significant (REAL), but a *zero* common drift is no drift at all
            # (noise) — guard the 0/0 so a flat moment is not mislabeled REAL.
            if se > 0:
                sig = abs(m) / se
            else:
                sig = float("inf") if m != 0 else 0.0
            verdict = "REAL" if sig > 2 else ("noise" if sig < 1 else "borderline")
            print(f"    {k:<14}{m:>+11.3e} +/- {se:.3e}   ({sig:>4.1f}sigma  {verdict})")
    return 0


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default = os.path.join(here, "FromPandemicCode",
                           "welfare6_scenario_results_Baseline")
    args = sys.argv[1:]
    if len(args) >= 2:   # >=2 result-dirs => multi-seed SE mode
        return multiseed_report(args)
    resdir = args[0] if args else default
    pkls = sorted(glob.glob(os.path.join(resdir, "*.pkl")))
    if not pkls:
        print(f"no .pkl cells found in {resdir}", file=sys.stderr)
        return 1
    print("MC CROSS-SECTION DRIFT (baseline-sim, t=0[ergodic init] -> t=end)  [v2 confound-robust]")
    print(f"dir: {resdir}\n")
    print("  ROBUST drift signals (composition-robust assets, trend-invariant income spread):")
    print(f"  {'cell':<22}{'Dconstr_frac':>13}{'D_aP50(rel)':>12}{'D_aP90(rel)':>12}{'Dvar_log_p':>12}")
    worst = 0.0
    rows = []
    for pkl in pkls:
        r = drift_for_cell(pkl)
        if r is None:
            continue
        rows.append(r)
        print(f"  {r['cell']:<22}{r['d_cfrac']:>13.3e}{r['d_aP50_rel']:>12.3e}"
              f"{r['d_aP90_rel']:>12.3e}{r['d_var_log_p']:>12.3e}")
        worst = max(worst, abs(r['d_cfrac']), abs(r['d_aP50_rel']),
                    abs(r['d_aP90_rel']), abs(r['d_var_log_p']))
    if rows:
        r0 = rows[0]
        print(f"\n  Worst |ROBUST drift| across cells = {worst:.3e}  "
              f"(T={r0['T']}, N={r0['N']}/cell).")
        # context, base cell
        b = next((r for r in rows if r['cell'] == 'base'), r0)
        print(f"  CONTEXT ('{b['cell']}'): income mean-log drift (growth TREND, expected) "
              f"= {b['d_mean_log_p_trend']:+.3e}; "
              f"var(log aNrm|>0) (CONFOUNDED by composition) = {b['d_var_log_a_confounded']:+.3e}")
        s = r0["start"]
        print(f"  ergodic init (t=0, '{r0['cell']}'): constr_frac={s['cfrac']:.4f}, "
              f"aNrm P10/P50/P90={s['aP10']:.3f}/{s['aP50']:.3f}/{s['aP90']:.3f}, "
              f"var(log pLvl)={s['lp_v']:.4f}")
        print("\n  NOTE: single run — no SE yet; a robust drift here that exceeds the "
              "multi-seed SE is a real ergodic-departure (run the multi-seed companion).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
