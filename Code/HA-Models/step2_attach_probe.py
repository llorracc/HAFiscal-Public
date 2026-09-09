"""step2_attach_probe.py — solve-level diagnostics for the S2/production solve path.

Phase 1 of plans_local/20260822-1030h_s2-production-solve-path_plan.md (owner charge
2026-08-22). Mirrors step1_attach_probe.py's discipline for the FromPandemicCode
world: exec the REAL `estim_phase2_tm_a.py` under its
`HAFISCAL_STEP2_RUN_ESTIMATION=0` eval mode (machinery built — BaseTypeList,
AggDemandEcon, the objective — estimation skipped via SystemExit, which this probe
catches while keeping the namespace), call `betas_obj_func_educ_tm_a` ONCE per
education group at the installed SoR (β, ∇, GICx), and dump the solved consumption
functions per group × discount-factor atom × Markov state.

The grid/attach configuration under test comes from the caller's environment
(HAFISCAL_SOLVE_GRID_PROFILE / HAFISCAL_PF_DECAY_Q / ...), exactly as a real Step-2
run would see it.

READ-ONLY: eval mode skips every estimation write; the probe additionally snapshots
Results/*.txt mtimes and exits 3 on any change (trap-15 guard).

npz payload per (group e, atom j, state s):
  e{e}a{j}s{s}_m / _c        dense evaluation of that slice's cFunc
  e{e}a{j}_grid              the type's aXtraGrid
plus a json `meta`: per-type scalars (DiscFac, LivPrb, Rfree, CRRA, PermGroFac,
per-state MPCmin/hNrm where exposed, installed decay attrs where discoverable),
group SoR values used, and the objective's returned distance.
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import sys

import numpy as np

# The probe's historical argv tail (Rfree CRRA IncUnemp NoB Splurge; the Splurge literal is
# the installed Step-1 SoR). An EMPTY tail is the production do_all invocation (Parameters
# defaults + Splurge from the resolved Step-1 file) — step2_curvature.py uses that.
ARGV_TAIL_DEFAULT = "1.01 2.0 0.7 0.5 0.3010418817919867"
SOR_FILE_DEFAULT = "DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt"


def estimator_paths():
    """(HA-Models dir, FromPandemicCode dir, the estimator script, Results dir)."""
    here = os.path.dirname(os.path.abspath(__file__))
    fpc = os.path.join(here, "FromPandemicCode")
    return here, fpc, os.path.join(fpc, "estim_phase2_tm_a.py"), os.path.join(here, "Results")


def snapshot_results_mtimes(res_dir):
    """mtimes of Results/*.txt — the read-only trap (exit 3 on any change)."""
    guard = sorted(glob.glob(os.path.join(res_dir, "*.txt")))
    return {f: os.path.getmtime(f) for f in guard}


def changed_results(mtimes):
    return [f for f in mtimes if os.path.getmtime(f) != mtimes[f]]


def load_sor(path):
    """{education group: {'EducationGroup', 'beta', 'nabla', 'GICx'}} from a DiscFacEstim_*.txt
    (dict rows; a trailing 'Parameters: ...' footer, as in the consolidated _TM_a files, is skipped)."""
    sor = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line and line.startswith("{"):
                d = ast.literal_eval(line)
                sor[int(d["EducationGroup"])] = d
    return sor


def exec_estimator_eval_mode(argv_tail=ARGV_TAIL_DEFAULT):
    """Exec the REAL estim_phase2_tm_a.py under its HAFISCAL_STEP2_RUN_ESTIMATION=0 eval mode
    and return its namespace (BaseTypeList, AggDemandEcon solved at the installed calibration,
    betas_obj_func_educ_tm_a, df_base / _INTERP_SUFFIX / res_dir, ...): the estimation loop and
    every file write are skipped via the SystemExit this catches. chdir's into FromPandemicCode
    and rewrites sys.argv, exactly as the probe's main() always did (EstimParameters parses
    argv: Rfree CRRA IncUnemp NoB Splurge; an EMPTY tail = the production do_all invocation).
    Shared with step2_curvature.py (Econ-4). Raises RuntimeError if the objective is not
    reached."""
    os.environ["HAFISCAL_STEP2_RUN_ESTIMATION"] = "0"
    here, fpc, script, _ = estimator_paths()
    sys.path.insert(0, fpc)
    sys.path.insert(0, here)
    os.chdir(fpc)
    sys.argv = [script] + argv_tail.split()
    g = {"__name__": "step2_probe_eval", "__file__": script}
    src = open(script).read()
    try:
        exec(compile(src, script, "exec"), g)  # noqa: S102 — the REAL file, eval mode
    except SystemExit:
        pass
    if "betas_obj_func_educ_tm_a" not in g:
        raise RuntimeError("eval-mode exec did not reach the objective definition")
    return g


def _walk_decay(obj, depth=0):
    """Find a decay-tail attribute holder inside a (possibly composed) function."""
    if obj is None or depth > 4:
        return None
    if getattr(obj, "decay_extrap", None) or hasattr(obj, "decay_extrap_Q"):
        return obj
    for attr in ("functions", "interpolants"):
        sub = getattr(obj, attr, None)
        if isinstance(sub, (list, tuple)):
            for s in sub:
                hit = _walk_decay(s, depth + 1)
                if hit is not None:
                    return hit
    for attr in ("function", "interpolant", "func"):
        hit = _walk_decay(getattr(obj, attr, None), depth + 1)
        if hit is not None:
            return hit
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--groups", default="0,1,2",
                    help="education groups to probe (default all three)")
    ap.add_argument("--mmax", type=float, default=2600.0,
                    help="far edge of the evaluation vector (dist top 1300 x2)")
    ap.add_argument("--argv", default=ARGV_TAIL_DEFAULT,
                    help="argv tail for the estim script (Rfree CRRA IncUnemp NoB Splurge)")
    args = ap.parse_args()

    _, _, _, res_dir = estimator_paths()
    mtimes = snapshot_results_mtimes(res_dir)

    # SoR values per group (ESC main spec)
    sor = load_sor(os.path.join(res_dir, SOR_FILE_DEFAULT))

    try:
        g = exec_estimator_eval_mode(args.argv)
    except RuntimeError:
        print("PROBE_FAIL: eval-mode exec did not reach the objective definition",
              file=sys.stderr)
        sys.exit(4)

    obj = g["betas_obj_func_educ_tm_a"]
    econ = g["AggDemandEcon"]
    dfc = int(g["DiscFacCount"])

    arrays = {}
    meta = {"argv": args.argv, "groups": [], "DiscFacCount": dfc}
    for e in [int(t) for t in args.groups.replace(",", " ").split()]:
        s_e = sor[e]
        dist = float(obj(s_e["beta"], s_e["nabla"], s_e["GICx"], educ_type=e,
                         print_mode=False))
        types = econ.agents[e * dfc:(e + 1) * dfc]
        ginfo = {"e": e, "beta": s_e["beta"], "nabla": s_e["nabla"],
                 "GICx": s_e["GICx"], "objective": dist, "atoms": []}
        for j, T in enumerate(types):
            sol = T.solution[0]
            cfs = sol.cFunc if isinstance(sol.cFunc, (list, tuple)) else [sol.cFunc]
            grid = np.asarray(T.aXtraGrid, dtype=float)
            arrays[f"e{e}a{j}_grid"] = grid
            m = np.unique(np.concatenate([
                np.geomspace(0.05, args.mmax, 500),
                np.array([grid.max() * (1 - 1e-8), grid.max() * (1 + 1e-8)])]))
            ainfo = {"j": j, "DiscFac": float(T.DiscFac),
                     "LivPrb": float(np.ravel(T.LivPrb)[0]),
                     "CRRA": float(T.CRRA),
                     "PermGroFac": float(np.ravel(T.PermGroFac)[0]),
                     "Rfree": float(np.ravel(T.Rfree)[0]),
                     "grid_top": float(grid.max()), "grid_len": int(grid.size),
                     "n_states": len(cfs), "states": []}
            for s_ix, cf in enumerate(cfs):
                # AggFiscalModel policies are 2-D: per state,
                # LowerEnvelope2D(VariableLowerBoundFunc2D(LinearInterpOnInterp1D
                # over the Cgrid), ...) with a PowerLawDecayLinearInterp per
                # C-node — the certified production attach. Dump BOTH:
                # (a) the COMPOSED surface at Cratio=1 (the consumed object —
                #     the window-error metric), and
                # (b) the raw C≈1 slice's attach attributes (the exponent
                #     certification: Q, limits, knot top).
                c_comp = np.asarray(cf(m, np.ones_like(m)), dtype=float)
                arrays[f"e{e}a{j}s{s_ix}_m"] = m
                arrays[f"e{e}a{j}s{s_ix}_c"] = c_comp
                # walk: LowerEnvelope2D.functions -> VariableLowerBoundFunc2D.func
                # -> LinearInterpOnInterp1D(.xInterpolators, .y_list)
                lio, node = None, None
                stack = [cf]
                while stack and lio is None:
                    o = stack.pop(0)
                    if hasattr(o, "xInterpolators") and hasattr(o, "y_list"):
                        lio = o
                        break
                    for a in ("functions",):
                        ss = getattr(o, a, None)
                        if isinstance(ss, (list, tuple)):
                            stack.extend(ss)
                    for a in ("func", "function"):
                        if getattr(o, a, None) is not None:
                            stack.append(getattr(o, a))
                sinfo = {"s": s_ix}
                if lio is not None:
                    yg = np.asarray(lio.y_list, dtype=float)
                    k = int(np.argmin(np.abs(yg - 1.0)))
                    sl = lio.xInterpolators[k]
                    node = float(yg[k])
                    sx = np.asarray(getattr(sl, "x_list", [np.nan]), dtype=float)
                    sinfo.update({
                        "c_node": node, "holder": type(sl).__name__,
                        "Q": float(getattr(sl, "decay_extrap_Q", np.nan)),
                        "form": str(getattr(sl, "decay_extrap_form", "")),
                        "intercept_limit": float(getattr(sl, "intercept_limit", np.nan) or np.nan),
                        "slope_limit": float(getattr(sl, "slope_limit", np.nan) or np.nan),
                        "slice_x_top": float(np.nanmax(sx)),
                        "n_cnodes": int(yg.size),
                    })
                    arrays[f"e{e}a{j}s{s_ix}_slc"] = np.asarray(sl(m), dtype=float)
                else:
                    sinfo.update({"c_node": None, "holder": "", "Q": float("nan"),
                                  "form": ""})
                ainfo["states"].append(sinfo)
            ginfo["atoms"].append(ainfo)
        meta["groups"].append(ginfo)
        print(f"[probe] group {e}: objective={dist:.8g}  atoms={len(types)}  "
              f"states/atom={ginfo['atoms'][0]['n_states']}")

    changed = changed_results(mtimes)
    if changed:
        print(f"PROBE_WRITE_VIOLATION: {changed}", file=sys.stderr)
        sys.exit(3)

    out = os.path.abspath(os.path.expanduser(args.out))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    np.savez_compressed(out, meta=json.dumps(meta), **arrays)
    print(f"PROBE_OK groups={args.groups} out={out}")


if __name__ == "__main__":
    main()
