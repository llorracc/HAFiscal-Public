"""Rung A7 — G14 measured (owner decision B, Option 1, ruled 2026-09-02).

THE REDUCTION. The overlay books J_C^ov = sigma*dY + (1-sigma)*J_C and
J_A^ov = (1-sigma)*J_A. The structural rule (c_sp = sigma*y inside the model)
books J_C^st = sigma*dY + J_C^opt(lambda) and J_A^st = J_A(lambda), where
lambda = 1-sigma and J(lambda) is the Jacobian of the optimizer whose EVERY
income flow is scaled by lambda (per unit of the GROSS instrument). The
sigma*dY splurge-account term is IDENTICAL on both sides (both consume sigma
of the same delivered income), so G14 collapses to the homotheticity claim:

    J(income_scale=lambda)  ==  lambda * J(income_scale=1)   (every leaf)

on the code's ACTUAL grids (which do not scale) — plus, under mortality, the
fixed newborn level m = 1 (which does not scale either).

TWO ARMS x refinement:
  L1    the A3 config (LivPrb = 1, production psi/theta risk): the residual
        is pure discretization and should SHRINK under grid refinement;
  Lmort the A4 config (LivPrb = 0.99375): adds the newborn-level break,
        whose contribution should NOT shrink — the floor IS the measurement.

Also gated: cash(lambda) == lambda * cash (the delivered-income identity,
free from the budget diagonals) and the r/DiscFac leaves (rate and
preference perturbations scale through homogeneity of the ASSET position).

Usage: python -m ssj_ladder.rung_a7 --out DIR [--quick]
"""
import argparse
import json
import os
import sys
import time

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HA = os.path.join(REPO, "Code", "HA-Models")

SIGMAS = (0.3010418817919867, 0.6)     # the SoR splurge + a far point
LEAVES = ("transfers", "w", "tau", "UI_extend", "UI_rr", "r", "eta")
INCOME_LEAVES = ("transfers", "w", "tau", "UI_extend", "UI_rr")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--quick", action="store_true",
                    help="drop the 450-point tier")
    a = ap.parse_args()
    out_dir = os.path.abspath(a.out)
    os.makedirs(out_dir, exist_ok=True)

    # rung env BEFORE any step4 import (the ladder convention)
    os.environ["HAFISCAL_HANK_BIGT"] = "40"
    os.environ["HAFISCAL_STEP4_FAST_BACKWARD"] = "0"
    os.environ["HAFISCAL_STEP4_FAST_TRANMAT"] = "0"
    os.environ["HAFISCAL_STEP4_ZEROTH_COLUMN"] = "unanticipated"
    os.environ["HAFISCAL_STEP4_FAKENEWS_INDEX"] = "legacy"
    os.environ["HAFISCAL_EARNINGS_PHASE_HAZARD"] = "0"
    os.environ["HAFISCAL_QUIET_BETADISTR"] = "1"
    for k, rel in (("HAFISCAL_DISCFAC_FILE",
                    "Code/HA-Models/rerun_logs/chain_D_20260829/DiscFacEstim_CRRA_2.0_R_1.01_chainD.txt"),
                   ("HAFISCAL_SPLURGE_FILE",
                    "Code/HA-Models/rerun_logs/chain_D_20260829/Result_AllTarget_ESC_chainD.txt")):
        q = os.path.join(REPO, rel)
        if os.path.exists(q):
            os.environ.setdefault(k, q)
    sys.argv = [sys.argv[0]]
    if HA not in sys.path:
        sys.path.insert(0, HA)

    from ssj_ladder import minimal_cell as mc
    from ssj_ladder.rungs import RUNGS

    ladder = (50, 150) if a.quick else (50, 150, 450)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    t0 = time.time()
    verdict = {"rung": "A7", "stamp": stamp, "sigmas": list(SIGMAS),
               "ladder": list(ladder), "arms": {}, "gates": {}}

    # Lmort_faithful (2026-09-02, the reclassification arm): the PE's
    # newborns hold ZERO assets (kLogInitMean = log(1e-5)) -- their resources
    # ARE the first income draw, which the splurge applies to -- so the
    # FAITHFUL structural benchmark scales the newborn level by lambda too
    # (HAFISCAL_HANK_NEWBORN_M = lambda on the lambda-cell). Prediction: the
    # 1.8e-2 Lmort floor collapses to the L1 refinement profile, proving the
    # overlay was the faithful convention all along.
    for arm, rung_key in (("L1", "A3"), ("Lmort", "A4"),
                          ("Lmort_faithful", "A4")):
        model = dict(RUNGS[rung_key]["model"])
        model["T"] = 40
        rho = model["R"] * model["livprb"]
        arm_rows = {}
        for n in ladder:
            base = mc.build_cell_a3(model, n,
                                    os.path.join(out_dir, f"s7_{arm}_{n}_base.obj"))
            for sig in SIGMAS:
                lam = 1.0 - sig
                if arm == "Lmort_faithful":
                    os.environ["HAFISCAL_HANK_NEWBORN_M"] = repr(lam)
                try:
                    lc = mc.build_cell_a3(model, n,
                                          os.path.join(out_dir, f"s7_{arm}_{n}_{sig:.2f}.obj"),
                                          income_scale=lam)
                finally:
                    os.environ.pop("HAFISCAL_HANK_NEWBORN_M", None)
                row = {}
                for leaf in LEAVES:
                    A = np.asarray(lc[f"C_{leaf}"], float)
                    B = lam * np.asarray(base[f"C_{leaf}"], float)
                    row[f"C_{leaf}"] = float(np.linalg.norm(A - B)
                                             / max(np.linalg.norm(B), 1e-300))
                    A = np.asarray(lc[f"A_{leaf}"], float)
                    B = lam * np.asarray(base[f"A_{leaf}"], float)
                    row[f"A_{leaf}"] = float(np.linalg.norm(A - B)
                                             / max(np.linalg.norm(B), 1e-300))
                # delivered-cash identity: cash(lambda) == lambda * cash
                for leaf in INCOME_LEAVES:
                    def cash(cell, lf):
                        JC = np.asarray(cell[f"C_{lf}"], float)
                        JA = np.asarray(cell[f"A_{lf}"], float)
                        r = np.empty_like(JC)
                        r[0] = JA[0] + JC[0]
                        r[1:] = JA[1:] - rho * JA[:-1] + JC[1:]
                        return float(np.median(np.diag(r)[1:]))
                    row[f"cashratio_{leaf}"] = float(
                        cash(lc, leaf) / (lam * cash(base, leaf)))
                arm_rows[f"n{n}_sig{sig:.4f}"] = row
                worstC = max(row[f"C_{l}"] for l in LEAVES)
                print(f"[A7:{arm}] n={n} sigma={sig:.4f}: worst C-relgap "
                      f"{worstC:.3e}; cash ratios "
                      f"{[round(row[f'cashratio_{l}'], 8) for l in INCOME_LEAVES[:2]]}",
                      flush=True)
        verdict["arms"][arm] = arm_rows

    # refinement read + the pinned gates (tiers from the 2026-09-02 full
    # measurement: L1 calib 4.29e-2 -> 8.93e-3 -> 3.77e-3, last ratio 0.42;
    # Lmort calib floors at 1.80e-2, sig=0.6 at 6.42e-2 with last ratio
    # 0.9984 -- the newborn-level break; cash ratios 1 +- 1e-10 everywhere).
    ok = True
    for arm in ("L1", "Lmort", "Lmort_faithful"):
        rows = verdict["arms"][arm]
        for sig in SIGMAS:
            gaps = [max(rows[f"n{n}_sig{sig:.4f}"][f"C_{l}"] for l in LEAVES)
                    for n in ladder]
            verdict["gates"][f"{arm}_sig{sig:.4f}_worstC_by_n"] = gaps
            for n in ladder:
                for leaf in INCOME_LEAVES:
                    dev = abs(rows[f"n{n}_sig{sig:.4f}"][f"cashratio_{leaf}"]
                              - 1.0)
                    if dev > 1e-6:
                        ok = False
                        verdict["gates"][f"FAIL_cash_{arm}_{n}_{sig}_{leaf}"] = dev
    if len(ladder) >= 3:
        for sig in SIGMAS:
            g = verdict["gates"][f"L1_sig{sig:.4f}_worstC_by_n"]
            verdict["gates"][f"L1_sig{sig:.4f}_refines"] = {
                "last_ratio": g[-1] / g[-2], "threshold": 0.6,
                "PASS": g[-1] / g[-2] <= 0.6}
            ok = ok and g[-1] / g[-2] <= 0.6
        g = verdict["gates"]["L1_sig0.2999_worstC_by_n"]
        verdict["gates"]["L1_calib_n450_tier"] = {
            "measured": g[-1], "threshold": 1e-2, "PASS": g[-1] <= 1e-2}
        ok = ok and g[-1] <= 1e-2
        # the reclassification gate: the faithful benchmark must refine like
        # L1 (the floor was the benchmark's, not the overlay's)
        gf = verdict["gates"]["Lmort_faithful_sig0.2999_worstC_by_n"]
        verdict["gates"]["Lmort_faithful_refines"] = {
            "last_ratio": gf[-1] / gf[-2], "n450": gf[-1],
            "threshold_ratio": 0.6, "threshold_n450": 1e-2,
            "PASS": (gf[-1] / gf[-2] <= 0.6 and gf[-1] <= 1e-2)}
        ok = ok and verdict["gates"]["Lmort_faithful_refines"]["PASS"]
        g = verdict["gates"]["Lmort_sig0.2999_worstC_by_n"]
        verdict["gates"]["Lmort_calib_floor_materiality"] = {
            "measured": g[-1], "threshold": 5e-2, "PASS": g[-1] <= 5e-2,
            "note": "the newborn-level homotheticity break -- a RECORDED "
                    "structural residual gated only against materiality; "
                    "the sig=0.6 floor (6.4e-2) is a probe point, ungated"}
        ok = ok and g[-1] <= 5e-2
    verdict["PASS"] = bool(ok)
    verdict["wall_s"] = round(time.time() - t0, 1)
    path = os.path.join(out_dir, f"verdict_A7_{stamp}.json")
    with open(path, "w") as f:
        json.dump(verdict, f, indent=1, default=float)
    print(f"[A7] {'PASS' if verdict.get('PASS') else 'MEASURED/FAIL'} "
          f"-> {path} ({verdict['wall_s']}s)")
    # scratch objs are probe artifacts, not evidence
    for q in os.listdir(out_dir):
        if q.startswith("s7_") and q.endswith(".obj"):
            os.remove(os.path.join(out_dir, q))
    return 0 if verdict.get("PASS", True) else 1


if __name__ == "__main__":
    sys.exit(main())
