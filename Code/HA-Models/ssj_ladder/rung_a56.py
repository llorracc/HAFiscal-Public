"""Rungs A5 and A6: heterogeneity and production semantics, as verdicts.

Plan 20260901-2010h §2. Both rungs certify the PRODUCTION construction, so
they run against existing artifacts and SSTs rather than minimal cells:

A5 (beta fan-out incl. the cap atom; educations; the drift pathology):
  - step4/test_zeroth_column_flow_budget.py — the per-cell budget SST at the
    cap-atom cell (the drift pathology's home), run as a gate;
  - the exact weighted-aggregation identity on the TRACKED production obj
    (J_agg == sum_e w_e J_e), tolerance 1e-12 (audit measured 8.3e-17).

A6 (production semantics: kernels, pe grids/chains, Harmenberg):
  - kernel equivalence is certified by Phase B's B9 rung (kernels ON, chain
    attribution + the exit identity) — referenced, not re-run;
  - the by-educ leaf spot: ONE full education's C/A leaves in the tracked
    obj against the recorded reference build
    (rerun_logs/zerocol_fix_20260901/jacs_unanticipated.obj), tolerance
    1e-9 (the recorded cross-run floor is 8.5e-11..1.4e-10).

Usage:  python -m ssj_ladder.rung_a56 --out DIR
"""
import argparse
import json
import os
import pickle
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
HA = os.path.dirname(HERE)
TRACKED = os.path.join(HA, "FromPandemicCode", "HA_Fiscal_Jacs.obj")
REF = os.path.join(HA, "rerun_logs", "zerocol_fix_20260901",
                   "jacs_unanticipated.obj")


def clean_env():
    e = {k: v for k, v in os.environ.items()
         if not k.startswith("HAFISCAL_")}
    e.update({"PYTHONUNBUFFERED": "1", "MPLBACKEND": "Agg"})
    return e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    sys.path.insert(0, HA)
    from ssj_ladder import budget_suite

    stamp = time.strftime("%Y%m%d-%H%M%S")

    # ---- A5 ----------------------------------------------------------
    v5 = {"rung": "A5", "stamp": stamp, "gates": {}}
    log = os.path.join(out, "a5_zeroth_flow_budget.log")
    rc = subprocess.call([sys.executable, "-m", "pytest",
                          "step4/test_zeroth_column_flow_budget.py",
                          "-q", "--no-header"],
                         cwd=HA, env=clean_env(),
                         stdout=open(log, "w"), stderr=subprocess.STDOUT)
    v5["gates"]["sst:zeroth_column_flow_budget"] = {
        "measured": rc, "threshold": 0, "PASS": rc == 0}
    with open(TRACKED, "rb") as f:
        obj = pickle.load(f)
    ok, worst = budget_suite.by_educ_identity(obj, tol=1e-12)
    v5["gates"]["weighted_aggregation_identity"] = {
        "measured": worst, "threshold": 1e-12, "PASS": bool(ok)}
    v5["PASS"] = all(g["PASS"] for g in v5["gates"].values())
    with open(os.path.join(out, f"verdict_A5_{stamp}.json"), "w") as f:
        json.dump(v5, f, indent=1, default=float)
    print(f"[A5] {'PASS' if v5['PASS'] else 'FAIL'}: "
          f"{json.dumps({k: g['PASS'] for k, g in v5['gates'].items()})}")

    # ---- A6 ----------------------------------------------------------
    v6 = {"rung": "A6", "stamp": stamp, "gates": {},
          "kernel_equivalence": "certified by Phase B rung B9 "
          "(rerun_logs/phase_b_20260902/verdict_B9.json: kernels ON, budget "
          "floors green, exit identity = production goldens)"}
    if os.path.exists(REF):
        with open(REF, "rb") as f:
            ref = pickle.load(f)
        educ = "college"
        worst6 = 0.0
        rows = {}
        for top in ("C_by_educ", "A_by_educ"):
            for k in sorted(obj[top][educ]):
                d = float(np.max(np.abs(
                    np.asarray(obj[top][educ][k], float)
                    - np.asarray(ref[top][educ][k], float))))
                rows[f"{top}.{k}"] = d
                worst6 = max(worst6, d)
        v6["gates"]["by_educ_leaf_spot_college"] = {
            "measured": worst6, "threshold": 1e-9,
            "PASS": bool(worst6 <= 1e-9)}
        v6["leaf_diffs"] = rows
    else:
        v6["gates"]["by_educ_leaf_spot_college"] = {
            "measured": None, "threshold": 1e-9, "PASS": False,
            "note": f"reference missing: {REF}"}
    v6["PASS"] = all(g["PASS"] for g in v6["gates"].values())
    with open(os.path.join(out, f"verdict_A6_{stamp}.json"), "w") as f:
        json.dump(v6, f, indent=1, default=float)
    print(f"[A6] {'PASS' if v6['PASS'] else 'FAIL'}: "
          f"spot worst={v6['gates']['by_educ_leaf_spot_college']['measured']}")
    return 0 if (v5["PASS"] and v6["PASS"]) else 1


if __name__ == "__main__":
    sys.exit(main())
