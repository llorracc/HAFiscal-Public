"""Step-2 simulation-share profiler — decomposes ONE warm objective evaluation
(`betas_obj_func_educ`) into its components so we can see what the ~73%
"simulation" tail (the part Anderson cannot touch — see the 2026-06-17 solver
finding) actually is, and where it concentrates.

This is the Phase-A profiler for the simulation-speedup assessment branch
(`plans/20260617-1153h_step2-simulation-speedup-assessment.md`). It extends
`_poc_step2_profile.py` (which only measured the SOLVE fraction) by also timing:

  - AggDemandEconomy.solve()      (warm base Markov solve; via solve_agent patch)
  - AggDemandEconomy.make_history()  (act_T=400 market periods)
  - _mtc(...)                     (per-agent initialize_sim + simulate T_sim + save_state)
  - calc_estim_stats / calc_lorenz_pts  (the moment cross-section)

Default OFF / read-only: it imports EstimAggFiscalMAIN with
HAFISCAL_SKIP_ESTIMATION=1 (builds the economy, runs NO Nelder-Mead), patches a
few methods to accumulate wall time, and times a couple of warm
`betas_obj_func_educ` evaluations at PRODUCTION N. No default path is changed and
nothing is written to tracked result files.

Run (from FromPandemicCode/):
  PYTHONPATH=. HAFISCAL_SKIP_ESTIMATION=1 HAFISCAL_SERIAL=1 \
      <python> fti_diagnostics/_poc_step2_sim_profile.py
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np

os.environ.setdefault("HAFISCAL_SKIP_ESTIMATION", "1")  # import builds economy; no NM
os.environ.setdefault("HAFISCAL_SERIAL", "1")           # sequential -> clean wall timing

_HERE = os.path.dirname(os.path.abspath(__file__))
_FROMPANDEMIC = os.path.normpath(os.path.join(_HERE, ".."))
for _p in (_FROMPANDEMIC, os.path.normpath(os.path.join(_FROMPANDEMIC, ".."))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

EDTYPE = int(os.environ.get("PROF_STEP2_EDTYPE", "1"))  # 1 = highschool (mid difficulty)

# Per-component wall-time accumulators (reset each timed eval).
_acc = {"solve_agent": 0.0, "n_solve": 0, "make_history": 0.0, "mtc": 0.0,
        "estim_stats": 0.0, "lorenz_pts": 0.0}


def _reset():
    for k in _acc:
        _acc[k] = 0.0 if isinstance(_acc[k], float) else 0


def _patch_solve_agent():
    import HARK.core as hcore
    _real = hcore.solve_agent

    def _timed(agent, *a, **k):
        t0 = time.time()
        out = _real(agent, *a, **k)
        _acc["solve_agent"] += time.time() - t0
        _acc["n_solve"] += 1
        return out

    hcore.solve_agent = _timed


def _wrap(mod, name, key, on_obj=None):
    """Wrap a module-level (or object) callable to accumulate wall time under key."""
    target = on_obj if on_obj is not None else mod
    real = getattr(target, name)

    def _timed(*a, **k):
        t0 = time.time()
        out = real(*a, **k)
        _acc[key] += time.time() - t0
        return out

    setattr(target, name, _timed)
    return real


def main():
    _patch_solve_agent()
    print("Importing EstimAggFiscalMAIN (builds economy at production N; one-time)...",
          flush=True)
    t_imp = time.time()
    import EstimAggFiscalMAIN as E
    print(f"  import+build done in {time.time() - t_imp:.1f}s "
          f"(cold import-time solves={_acc['n_solve']})", flush=True)

    # Wrap the simulation/moment components. _mtc is a module global referenced
    # inside betas_obj_func_educ at call time, so patching E._mtc takes effect.
    _wrap(E, "_mtc", "mtc")
    _wrap(E, "calc_estim_stats", "estim_stats")
    _wrap(E, "calc_lorenz_pts", "lorenz_pts")
    # make_history is an instance method of the economy object.
    eco = E.AggDemandEconomy
    real_mh = eco.make_history

    def _mh_timed(*a, **k):
        t0 = time.time()
        out = real_mh(*a, **k)
        _acc["make_history"] += time.time() - t0
        return out

    eco.make_history = _mh_timed

    prod_N = int(E.AgentCountTotal)
    print(f"\nProfiling at PRODUCTION AgentCountTotal={prod_N}  "
          f"(act_T={E.base_dict.get('act_T', '?')}, T_sim={getattr(E, 'T_sim', '?')}).",
          flush=True)

    GICx = float(np.log(E.theGICfactor / (1 - E.theGICfactor)))
    educ_names = ["Dropout", "Highschool", "College"]
    beta0 = {0: 0.75, 1: 0.93, 2: 0.98}[EDTYPE]
    spread0 = {0: 0.30, 1: 0.07, 2: 0.015}[EDTYPE]

    # A few warm evals mimicking Nelder-Mead steps in beta (each reuses prior solution).
    betas = [beta0, beta0 + 0.003, beta0 + 0.006]
    print(f"\nTiming warm betas_obj_func_educ evals for {educ_names[EDTYPE]} "
          f"(edType={EDTYPE}):", flush=True)
    rows = []
    for i, b in enumerate(betas):
        _reset()
        t0 = time.time()
        dist = E.betas_obj_func_educ(b, spread0, GICx, educ_type=EDTYPE)
        ev = time.time() - t0
        solve = _acc["solve_agent"]
        mh = _acc["make_history"]
        mtc = _acc["mtc"]
        stats = _acc["estim_stats"] + _acc["lorenz_pts"]
        other = ev - solve - mh - mtc - stats
        rows.append(dict(ev=ev, solve=solve, mh=mh, mtc=mtc, stats=stats,
                         other=other, n_solve=_acc["n_solve"], dist=float(dist)))
        print(f"  eval {i}: beta={b:.4f} total={ev:.2f}s | "
              f"solve={solve:.2f} ({100*solve/ev:.1f}%) "
              f"make_history={mh:.2f} ({100*mh/ev:.1f}%) "
              f"_mtc={mtc:.2f} ({100*mtc/ev:.1f}%) "
              f"moments={stats:.3f} ({100*stats/ev:.1f}%) "
              f"other={other:.2f} ({100*other/ev:.1f}%) "
              f"| #solves={_acc['n_solve']} dist={dist:.5f}", flush=True)

    # Use the warm evals (skip eval 0 = first warm-from-import step).
    warm = rows[1:]

    def _mean(key):
        return float(np.mean([r[key] for r in warm]))

    ev = _mean("ev")
    solve, mh, mtc, stats, other = (_mean("solve"), _mean("mh"), _mean("mtc"),
                                    _mean("stats"), _mean("other"))
    print("\n" + "=" * 78, flush=True)
    print(f"WARM eval mean (production N={prod_N}, edType={EDTYPE}={educ_names[EDTYPE]}):",
          flush=True)
    print(f"  total          {ev:8.2f}s  100.0%", flush=True)
    print(f"  solve          {solve:8.2f}s  {100*solve/ev:5.1f}%", flush=True)
    sim = mh + mtc
    print(f"  SIMULATION     {sim:8.2f}s  {100*sim/ev:5.1f}%   "
          f"(make_history {mh:.2f}s + _mtc {mtc:.2f}s)", flush=True)
    print(f"    make_history {mh:8.2f}s  {100*mh/ev:5.1f}%", flush=True)
    print(f"    _mtc(sim)    {mtc:8.2f}s  {100*mtc/ev:5.1f}%", flush=True)
    print(f"  moments        {stats:8.2f}s  {100*stats/ev:5.1f}%", flush=True)
    print(f"  other          {other:8.2f}s  {100*other/ev:5.1f}%", flush=True)
    print("\nINTERPRETATION: 'solve' is the only part Anderson/EGM speedups touch "
          "(2026-06-17 solver finding). 'SIMULATION' (make_history + _mtc) is the "
          "Amdahl wall this assessment branch targets.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
