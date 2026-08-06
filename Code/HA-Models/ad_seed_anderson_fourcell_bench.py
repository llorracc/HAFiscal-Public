"""Four-cell HS_Only AD-loop bench: {off/off, seed, anderson, seed+anderson}.

R8 items 5+6 (plans/20260724_speed-defaults-deep-dive_plan.md): measure, on ONE
HS_Only economy and ONE recession-class AD solve, the outer-iteration counts and
fixed-point agreement of the two opt-in AD-loop levers and their composition:

  A  off/off   : cold flat reset + stock damped-Picard loop (production behavior)
  B  seed      : eco.CFunc seeded from A's converged belief + eco._ad_warm_start=True
                 — the exact warm path the HAFISCAL_AD_BELIEF_SEED consumer
                 (welfare6_scenario.run_recession_AD) arms.  The sidecar
                 load / fingerprint soft-gate is exercised by the slow suite
                 solution_cache/test_ad_belief_seed_parity.py, not here.
  C  anderson  : cold + Anderson-accelerated outer loop (eco.ad_anderson=True,
                 the HAFISCAL_AD_ANDERSON branch).
  D  both      : warm seed + Anderson.

Construction mirrors FromPandemicCode/fti_diagnostics/_poc_ad_anderson.py: ONE
``build_and_solve`` + ``run_base``, then a FRESH ``deepcopy`` of the pre-AD
economy per cell, so every cell starts from the identical state and the AD map
G is deterministic (same seeds, same shock histories) — cells differ only in
starting belief and/or update rule.  Cell B/D's seed provenance (A's converged
belief) is the cross-phase consume pattern: Step-5a publishes its converged
belief, Step-5b (or a re-run) warm-starts from it.

Outputs: per-cell iters / converged / final step diff / wall + fixed-point
deltas vs cell A (max|dCratio_hist| on the converged paths and max|dCFunc| on
the [intercept, slope] parameter vector).  Walls on a busy box are PROVISIONAL
— rerun on an idle box for wall-bearing numbers (see the quiet-box script in
the session scratchpad).

Usage (from repo root; NOT on any production path — diagnostic harness):
  PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
    .venv-linux-x86_64/bin/python Code/HA-Models/ad_seed_anderson_fourcell_bench.py \
    --shock recession [--agent-count-total N] [--maxit K] [--cutoff X] [--json OUT.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_FPC = os.path.join(_HERE, "FromPandemicCode")
for _p in (_HERE, _FPC):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shock", default="recession",
                    choices=["recession", "recessionUI", "recessionTaxCut",
                             "recessionCheck"])
    ap.add_argument("--parametrization", default="HS_Only")
    ap.add_argument("--agent-count-total", type=int, default=None,
                    help="override AgentCountTotal (default: parametrization's)")
    ap.add_argument("--maxit", type=int, default=None,
                    help="override num_max_iterations_solvingAD")
    ap.add_argument("--cutoff", type=float, default=None,
                    help="override convergence_tol_solvingAD")
    ap.add_argument("--cells", default="A,B,C,D",
                    help="comma list from {A,B,C,D}; A always runs first")
    ap.add_argument("--json", default=None, help="write results JSON here")
    return ap.parse_args(argv)


def _cfunc_vec(eco):
    from AggFiscalModel import AggregateDemandEconomy
    return np.asarray(AggregateDemandEconomy._cfunc_to_vec(eco.CFunc), dtype=float)


def _copy_belief(CFunc):
    from AggFiscalModel import CRule
    return [[CRule(c.intercept, c.slope) for c in row] for row in CFunc]


def _run_cell(ctx, shock, *, anderson, seed_belief, maxit, cutoff, label):
    from copy import deepcopy
    print(f"\n=== cell {label}: anderson={anderson} warm_seed={seed_belief is not None} ===",
          flush=True)
    eco = deepcopy(ctx["AggEco"])
    eco.switch_shock_type(shock)
    eco.ad_anderson = bool(anderson)
    if seed_belief is not None:
        # Mirror welfare6_scenario.run_recession_AD's consume wiring exactly
        # (welfare6_scenario.py ~817-824): seed eco+agent CFunc, arm the
        # seed-aware reset. The loop still runs to its own cutoff unchanged.
        eco.CFunc = _copy_belief(seed_belief)
        for ag in eco.agents:
            ag.CFunc = eco.CFunc
        eco._ad_warm_start = True
    t0 = time.time()
    eco.solve_ad_recession(maxit, convergence_cutoff=cutoff, name=None,
                           shock_type=shock)
    wall = time.time() - t0
    out = dict(
        label=label,
        anderson=bool(anderson),
        warm=seed_belief is not None,
        iters=int(eco._ad_last_iters),
        converged=bool(eco._ad_last_converged),
        final_total_diff=float(eco._ad_last_total_diff),
        wall_s=float(wall),
        cratio=np.asarray(eco._ad_last_cratio_hist, dtype=float),
        cfunc_vec=_cfunc_vec(eco),
    )
    print(f"cell {label}: iters={out['iters']} converged={out['converged']} "
          f"final_diff={out['final_total_diff']:.3e} wall={wall/60:.1f} min",
          flush=True)
    return out, _copy_belief(eco.CFunc)


def main(argv=None):
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    # EstimParameters reads sys.argv numerically on import — strip ours first
    # (same pattern as fti_diagnostics/_poc_ad_anderson.py).
    sys.argv = sys.argv[:1]
    os.environ.setdefault("HAFISCAL_SIM_METHOD", "MC")

    import welfare6_scenario as ws

    t_build = time.time()
    print(f"Building {args.parametrization} economy "
          f"(agent_count_total={args.agent_count_total})...", flush=True)
    ctx = ws.build_and_solve(args.parametrization,
                             agent_count_total=args.agent_count_total)
    ws.run_base(ctx)  # base results / base_AggCons, matching production ordering
    build_wall = time.time() - t_build
    maxit = args.maxit if args.maxit is not None else ctx["num_max_iterations_solvingAD"]
    cutoff = args.cutoff if args.cutoff is not None else ctx["convergence_tol_solvingAD"]
    print(f"built in {build_wall/60:.1f} min; {len(ctx['AggEco'].agents)} cohort agent(s); "
          f"shock={args.shock} maxit={maxit} cutoff={cutoff:g}", flush=True)

    cells = [c.strip().upper() for c in args.cells.split(",") if c.strip()]
    results = {}

    # Cell A always runs (it defines the reference fixed point + the seed).
    res_a, belief_a = _run_cell(ctx, args.shock, anderson=False, seed_belief=None,
                                maxit=maxit, cutoff=cutoff, label="A off/off")
    results["A"] = res_a

    spec = {
        "B": dict(anderson=False, seed=True, label="B seed"),
        "C": dict(anderson=True, seed=False, label="C anderson"),
        "D": dict(anderson=True, seed=True, label="D both"),
    }
    for key in ("B", "C", "D"):
        if key not in cells:
            continue
        s = spec[key]
        res, _ = _run_cell(ctx, args.shock, anderson=s["anderson"],
                           seed_belief=belief_a if s["seed"] else None,
                           maxit=maxit, cutoff=cutoff, label=s["label"])
        results[key] = res

    # ----- report ------------------------------------------------------
    print("\n" + "=" * 76, flush=True)
    print(f"FOUR-CELL AD-LOOP BENCH  {args.parametrization} {args.shock}  "
          f"maxit={maxit} cutoff={cutoff:g} "
          f"agent_count_total={args.agent_count_total or 'default'}", flush=True)
    print("(walls PROVISIONAL if the box is busy; iteration counts + deltas are "
          "load-independent)", flush=True)
    hdr = (f"{'cell':<12} {'iters':>5} {'conv':>5} {'final_diff':>11} "
           f"{'wall_min':>9} {'max|dCratio|':>13} {'max|dCFunc|':>12}")
    print(hdr, flush=True)
    ref = results["A"]
    for key in ("A", "B", "C", "D"):
        if key not in results:
            continue
        r = results[key]
        n = min(ref["cratio"].size, r["cratio"].size)
        dcr = float(np.max(np.abs(ref["cratio"][:n] - r["cratio"][:n]))) if key != "A" else 0.0
        dcf = float(np.max(np.abs(ref["cfunc_vec"] - r["cfunc_vec"]))) if key != "A" else 0.0
        print(f"{r['label']:<12} {r['iters']:>5d} {str(r['converged']):>5} "
              f"{r['final_total_diff']:>11.3e} {r['wall_s']/60:>9.1f} "
              f"{dcr:>13.3e} {dcf:>12.3e}", flush=True)

    if args.json:
        payload = dict(
            parametrization=args.parametrization, shock=args.shock,
            maxit=int(maxit), cutoff=float(cutoff),
            agent_count_total=args.agent_count_total,
            build_wall_s=float(build_wall),
            cells={k: {kk: (vv.tolist() if isinstance(vv, np.ndarray) else vv)
                       for kk, vv in r.items()}
                   for k, r in results.items()},
        )
        with open(args.json, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"\nwrote {args.json}", flush=True)

    ok = all(r["converged"] for r in results.values())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
