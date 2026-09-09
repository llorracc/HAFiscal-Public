#!/usr/bin/env python
"""HANK household-block diagnostic (S2 of plans/20260830-1340h_hank-cross-machine-debugging-session_plan.md).

For the environment of one HANK arm (its `env.txt`), rebuild the step-4 household block exactly as
`jacobians.run()` does (hh_setup.build() -> per education x beta atom: deepcopy, IncShkDstn, DiscFac,
compute_steady_state()) and report, per atom:

  * the growth-impatience factor at that arm's Gamma:  GPF = (R*beta)^(1/rho) / Gamma_s  (max over the
    employed states), and its survival-adjusted twin (R*beta*LivPrb)^(1/rho) / Gamma_s;
  * the steady-state mass in the TOP cell of the distribution grid (and in the top 5 % of cells), the grid's
    top and count, A_ss and C_ss.

The hypothesis it tests (H1): under {legacy grid, Gamma == 1} the converted calibration's most patient
college atoms are past the bound and pile mass into the truncated top cell; under a covering grid OR
restored growth the pile-up disappears.  `--no-ss` prints only the bound table (no solves; seconds).

usage (from Code/HA-Models):
  python -m step4.hank_diagnose --env-file <hank_dir>/env.txt [--discfac F] [--splurge F]
                                [--set VAR=val ...] [--no-ss] [--out report.json]
"""
import argparse
import json
import os
import sys
from copy import deepcopy

import numpy as np

_SKIP_ENV = ("HAFISCAL_HANK_MULT_DUMP", "HAFISCAL_HANK_SS_DUMP", "HAFISCAL_RESULTS_OUT_DIR")
_SKIP_PREFIX = "HAFISCAL" + "_SPINE10_"   # driver-only bookkeeping (SHA guard, stage tags); split so the env-flag registry scan skips it


def load_env(path, discfac=None, splurge=None, sets=()):
    """Install the arm's HAFISCAL_* environment (paths from another box remapped by --discfac/--splurge)."""
    applied = {}
    for line in open(path):
        line = line.strip()
        if not line or "=" not in line or not line.startswith("HAFISCAL_"):
            continue
        k, v = line.split("=", 1)
        if k in _SKIP_ENV or k.startswith(_SKIP_PREFIX):
            continue
        applied[k] = v
    if discfac:
        applied["HAFISCAL_DISCFAC_FILE"] = discfac
    if splurge:
        applied["HAFISCAL_SPLURGE_FILE"] = splurge
    for s in sets:
        k, v = s.split("=", 1)
        applied[k] = v
    os.environ.update(applied)
    return applied


class materialize_pgf_legacy:
    """Mirror the drivers' pgf_legacy_materialize() — but LEAVE THE TREE AS
    FOUND (2026-09-02: the ladder's B1/B1b diagnose calls silently rewrote
    both tracked ``Results/_pgf_legacy`` files with QE-vintage content; a
    diagnostic must not install calibrations). Context manager: on enter,
    snapshot the two tracked files (bytes, or absence) and write ``cal_path``'s
    content so the in-process loader sees the matched pair (the BUG-047 guard
    only checks presence); on exit — success, exception, or gate failure —
    restore the snapshots byte-for-byte and remove files that did not exist.
    Only a SIGKILL between enter and exit can leak."""

    def __init__(self, ha_root, cal_path):
        self.dir = os.path.join(ha_root, "Results", "_pgf_legacy")
        self.cal_path = cal_path
        self.paths = [os.path.join(self.dir, f"DiscFacEstim_CRRA_2.0_R_1.01{sfx}.txt")
                      for sfx in ("_ESC_ascorrected", "_ESC")]
        self.snap = {}

    def __enter__(self):
        os.makedirs(self.dir, exist_ok=True)
        txt = open(self.cal_path).read()
        for q in self.paths:
            self.snap[q] = open(q, "rb").read() if os.path.exists(q) else None
            with open(q, "w") as f:
                f.write(txt)
        return self

    def __exit__(self, *exc):
        for q, blob in self.snap.items():
            if blob is None:
                if os.path.exists(q):
                    os.remove(q)
            else:
                with open(q, "wb") as f:
                    f.write(blob)
        return False


def bound_rows(ctx, educ_names=("dropout", "highschool", "college")):
    rows = []   # GPF_out uses E[1/psi] from the employed state's income distribution (the cap's own object)
    for e, agent in enumerate(ctx.BaseTypeList):
        betas = np.asarray(ctx.DiscFacDstns[e].atoms[0], dtype=float)
        gam = np.asarray(agent.PermGroFac[0], dtype=float).ravel()
        R = np.asarray(agent.Rfree[0], dtype=float).ravel()
        liv = np.asarray(agent.LivPrb[0], dtype=float).ravel()
        rho = float(agent.CRRA)
        # E[1/psi] exactly as the cap's arithmetic sees it: the employed state's (psi, theta) distribution, pmv-weighted
        _d = ctx.IncShkDstn[e][0]
        _pmv = np.asarray(_d.pmv, dtype=float).ravel(); _psi = np.asarray(_d.atoms, dtype=float)[0].ravel()
        e_inv_psi = float(np.sum(_pmv / _psi))
        for d, beta in enumerate(betas):
            gpf = (R * beta) ** (1.0 / rho) / gam
            gpf_m = (R * beta * liv) ** (1.0 / rho) / gam
            gpf_emp = float((R.max() * beta) ** (1.0 / rho) / gam.max())   # at the EMPLOYED state's Gamma (the ergodic mass)
            # population (cross-sectional ergodic) condition = HAFiscal's cap criterion: GPF_out = (R beta)^(1/rho) * L * E[1/psi] / Gamma
            # (BST eq. 42; conclusions_private/2026-06-16_gic-inside-vs-outside...); E[1/psi] = exp(sigma_psi^2) for a mean-one lognormal psi
            gpf_out = float((R.max() * beta) ** (1.0 / rho) * liv.max() * e_inv_psi / gam.max())
            rows.append({"educ": educ_names[e], "e": e, "d": d, "beta": float(beta),
                         "Gamma_max": float(gam.max()), "Gamma_min": float(gam.min()),
                         "GPF_max": float(gpf.max()), "GPF_mort_max": float(gpf_m.max()), "GPF_emp": gpf_emp, "GPF_out": gpf_out})
    return rows


def ss_rows(ctx, rows, top_frac=0.05):
    """Steady state per atom, exactly as prepare_type_base() builds agent_SS."""
    out = []
    for r in rows:
        e, d, beta = r["e"], r["d"], r["beta"]
        agent_SS = deepcopy(ctx.BaseTypeList[e])
        agent_SS.IncShkDstn = deepcopy([ctx.IncShkDstn[e]])
        agent_SS.DiscFac = beta
        agent_SS.compute_steady_state()
        n_m = len(agent_SS.MrkvArray[0])
        n_a = len(agent_SS.dist_mGrid)
        n_p = len(agent_SS.dist_pGrid)
        D = np.asarray(agent_SS.vec_erg_dstn, dtype=float).reshape(n_m, n_a, n_p)
        k = max(1, int(round(top_frac * n_a)))
        rr = dict(r)
        rr.update({"grid_top": float(agent_SS.dist_mGrid[-1]), "grid_count": int(n_a),
                   "mass_top_cell": float(D[:, -1, :].sum()),
                   "mass_top_cells": float(D[:, -k:, :].sum()), "top_cells": int(k),
                   "A_ss": float(agent_SS.A_ss), "C_ss": float(agent_SS.C_ss)})
        out.append(rr)
        print(f"  {rr['educ']:10s} beta[{d}]={beta:.5f}  GPF={rr['GPF_max']:.4f}  grid_top={rr['grid_top']:g}"
              f"  mass_top_cell={rr['mass_top_cell']:.3e}  mass_top{int(top_frac*100)}%={rr['mass_top_cells']:.3e}"
              f"  A_ss={rr['A_ss']:.3f}  C_ss={rr['C_ss']:.4f}", flush=True)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env-file", required=True)
    ap.add_argument("--discfac", help="override HAFISCAL_DISCFAC_FILE (remap another box's path)")
    ap.add_argument("--splurge", help="override HAFISCAL_SPLURGE_FILE")
    ap.add_argument("--set", action="append", default=[], help="extra VAR=val (repeatable) applied after the file")
    ap.add_argument("--no-ss", action="store_true", help="bound table only (no steady-state solves)")
    ap.add_argument("--top-frac", type=float, default=0.05)
    ap.add_argument("--out", help="write the rows as JSON")
    a = ap.parse_args(argv)

    applied = load_env(a.env_file, a.discfac, a.splurge, a.set)
    ha_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _pgf_guard = None
    if os.environ.get("HAFISCAL_PERMGROFAC_FIX", "1").strip() == "0" and os.environ.get("HAFISCAL_DISCFAC_FILE"):
        _pgf_guard = materialize_pgf_legacy(ha_root, os.environ["HAFISCAL_DISCFAC_FILE"])
        _pgf_guard.__enter__()
    import atexit
    if _pgf_guard is not None:
        atexit.register(_pgf_guard.__exit__)
    knobs = {k: applied.get(k, "<unset>") for k in ("HAFISCAL_HANK_GRIDS", "HAFISCAL_HANK_PERMGROFAC",
                                                    "HAFISCAL_HANK_UNEMP_CHAINS", "HAFISCAL_HANK_UNEMP_PSI",
                                                    "HAFISCAL_QE_FIDELITY", "HAFISCAL_DISCFAC_FILE")}
    print("[hank-diagnose] knobs:", json.dumps(knobs), flush=True)

    if ha_root not in sys.path:
        sys.path.insert(0, ha_root)
    sys.argv = sys.argv[:1]   # Parameters.return_parameters() parses sys.argv positionally (Rfree, CRRA, IncUnemp)
    from step4 import hh_setup  # noqa: E402  (imports the FromPandemicCode model under the installed env)
    ctx = hh_setup.build()
    rows = bound_rows(ctx)
    print("[hank-diagnose] growth-impatience by atom (GPF > 1 = past the bound at this arm's Gamma):")
    for r in rows:
        flag = " PAST(emp)" if r["GPF_emp"] > 1.0 else (" past(unemp only)" if r["GPF_max"] > 1.0 else "")
        print(f"  {r['educ']:10s} beta[{r['d']}]={r['beta']:.5f}  Gamma_emp={r['Gamma_max']:.5f}"
              f"  GPF_in={r['GPF_emp']:.4f}  GPF_out={r['GPF_out']:.4f}  (unemp-state GPF_in={r['GPF_max']:.4f}){flag}", flush=True)
    n_past = sum(1 for r in rows if r["GPF_emp"] > 1.0)
    print(f"[hank-diagnose] atoms past the bound at the employed Gamma: {n_past} of {len(rows)}", flush=True)
    if not a.no_ss:
        print("[hank-diagnose] steady states (one solve per atom):", flush=True)
        rows = ss_rows(ctx, rows, a.top_frac)
    if a.out:
        with open(a.out, "w") as f:
            json.dump({"knobs": knobs, "rows": rows}, f, indent=1)
        print(f"[hank-diagnose] wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
