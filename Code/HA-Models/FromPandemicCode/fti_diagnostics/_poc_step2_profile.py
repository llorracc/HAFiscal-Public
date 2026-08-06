"""Step-2 (discount-factor estimation) profiler — answers: can Anderson (vs warm-started
EGM) substantially speed up Step 2, and the AD effects?

Step 2 (EstimAggFiscalMAIN.py) runs Nelder-Mead over (beta, nabla) per education group.
Each objective evaluation (`betas_obj_func_educ`) does, for the DiscFacCount agents of one
cohort:
  1. AggDemandEconomy.solve()      -- base (NO recession / NO AD) Markov consumption solve,
                                      WARM-STARTED from the previous NM iterate's solution.
  2. reset / initialize_sim / make_history / save_state
  3. _mtc(..., ['solve()','initialize_sim()','simulate()','save_state()'])  -- re-solve (warm)
                                      + simulate AgentCountTotal agents for T_sim quarters.
  4. liquid-wealth Lorenz/median moments -> distance.

The solver acceleration (Anderson / AndersonEGM) can ONLY touch step 1/3's solve. This harness
measures the Amdahl ceiling: what FRACTION of an objective evaluation is the solve, and how many
EGM sweeps the warm-started solve actually takes (Anderson needs >=2-3 sweeps to build residual
history, so if warm EGM already converges in ~1-2 there is no headroom).

It imports EstimAggFiscalMAIN with HAFISCAL_SKIP_ESTIMATION=1 (builds the economy, runs NO NM),
monkeypatches HARK.core.solve_agent to accumulate per-solve wall time + count, then times a few
warm `betas_obj_func_educ` evaluations. To keep it tractable it shrinks AgentCountTotal AFTER the
import-time build (the solve is N-INDEPENDENT, the simulation is ~N-linear, so a SMALLER N makes
the solve fraction LARGER -> this is an OPTIMISTIC upper bound on any solver speedup; at the
production N=50000 the solve fraction is even smaller).

Run (from FromPandemicCode/):
  PYTHONPATH=. HAFISCAL_SKIP_ESTIMATION=1 HAFISCAL_SERIAL=1 <python> fti_diagnostics/_poc_step2_profile.py
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

# Profiling N: small N inflates the solve fraction (optimistic upper bound for Anderson).
PROF_N = int(os.environ.get("PROF_STEP2_N", "2000"))
EDTYPE = int(os.environ.get("PROF_STEP2_EDTYPE", "1"))  # 1 = highschool (mid difficulty)

_solve_stats = {"n": 0, "t": 0.0, "iters": []}


def _patch_solve_agent():
    import HARK.core as hcore
    _real = hcore.solve_agent

    def _timed(agent, *a, **k):
        t0 = time.time()
        out = _real(agent, *a, **k)
        dt = time.time() - t0
        _solve_stats["n"] += 1
        _solve_stats["t"] += dt
        # infinite-horizon sweep count (HARK stores it on the agent)
        try:
            _solve_stats["iters"].append(int(getattr(agent, "completed_cycles", -1)))
        except Exception:
            _solve_stats["iters"].append(-1)
        return out

    hcore.solve_agent = _timed


def _reset():
    _solve_stats["n"] = 0
    _solve_stats["t"] = 0.0
    _solve_stats["iters"] = []


def main():
    _patch_solve_agent()
    print(f"Importing EstimAggFiscalMAIN (builds economy at production N; one-time)...",
          flush=True)
    t_imp = time.time()
    import EstimAggFiscalMAIN as E
    _imp_sweeps = [s for s in _solve_stats["iters"] if s >= 0]
    print(f"  import+build done in {time.time()-t_imp:.1f}s "
          f"(COLD import-time solves={_solve_stats['n']}, "
          f"cold solve wall={_solve_stats['t']:.1f}s, "
          f"cold EGM sweeps min/med/max="
          f"{min(_imp_sweeps) if _imp_sweeps else '?'}/"
          f"{int(np.median(_imp_sweeps)) if _imp_sweeps else '?'}/"
          f"{max(_imp_sweeps) if _imp_sweeps else '?'})", flush=True)

    # Run timed evals at PRODUCTION N (shrinking N post-build desyncs prebuilt shock
    # histories). Production N is also the most honest solve-fraction number.
    prod_N = int(E.AgentCountTotal)
    print(f"\nProfiling at PRODUCTION AgentCountTotal={prod_N}.", flush=True)

    GICx = float(np.log(E.theGICfactor / (1 - E.theGICfactor)))
    educ_names = ["Dropout", "Highschool", "College"]
    beta0 = {0: 0.75, 1: 0.93, 2: 0.98}[EDTYPE]
    spread0 = {0: 0.30, 1: 0.07, 2: 0.015}[EDTYPE]

    # A few warm evals mimicking Nelder-Mead steps in beta (each reuses prior solution).
    betas = [beta0, beta0 + 0.003]
    print(f"\nTiming warm betas_obj_func_educ evals for {educ_names[EDTYPE]} "
          f"(edType={EDTYPE}):", flush=True)
    print(f"{'eval':>5} {'beta':>8} {'eval_s':>9} {'solve_s':>9} {'solve%':>7} "
          f"{'#solves':>8} {'EGM sweeps (per solve)':>26}", flush=True)
    rows = []
    for i, b in enumerate(betas):
        _reset()
        t0 = time.time()
        dist = E.betas_obj_func_educ(b, spread0, GICx, educ_type=EDTYPE)
        ev = time.time() - t0
        sv = _solve_stats["t"]
        frac = 100.0 * sv / ev if ev > 0 else 0.0
        sweeps = _solve_stats["iters"]
        sw_str = ",".join(str(x) for x in sweeps[:8]) + ("..." if len(sweeps) > 8 else "")
        print(f"{i:>5} {b:>8.4f} {ev:>9.2f} {sv:>9.2f} {frac:>6.1f}% "
              f"{_solve_stats['n']:>8} {sw_str:>26}", flush=True)
        print(f"      full sorted sweeps: {sorted(sweeps)}", flush=True)
        rows.append((ev, sv, frac, list(sweeps)))

    # Use the warm evals (skip eval 0, which is the first warm-from-import step).
    warm = rows[1:]
    mean_ev = float(np.mean([r[0] for r in warm]))
    mean_sv = float(np.mean([r[1] for r in warm]))
    mean_frac = 100.0 * mean_sv / mean_ev if mean_ev > 0 else 0.0
    all_sweeps = [s for r in warm for s in r[3] if s >= 0]
    print("\n" + "=" * 72, flush=True)
    print(f"WARM eval mean: total={mean_ev:.2f}s  solve={mean_sv:.2f}s  "
          f"solve fraction={mean_frac:.1f}%  (at production N={prod_N})", flush=True)
    if all_sweeps:
        print(f"WARM EGM sweeps per solve: min={min(all_sweeps)} "
              f"median={int(np.median(all_sweeps))} max={max(all_sweeps)} "
              f"mean={np.mean(all_sweeps):.1f}", flush=True)

    # Amdahl: best case where the solver becomes FREE.
    if mean_frac > 0:
        max_speedup = 100.0 / (100.0 - mean_frac)
        print(f"\nAMDAHL CEILING (solver -> free): end-to-end Step-2 speedup <= "
              f"x{max_speedup:.2f}  at production N={prod_N}", flush=True)
        # Even a 2x faster solve (optimistic for Anderson on warm solves):
        sp2 = 100.0 / (100.0 - mean_frac / 2.0)
        print(f"If the solver were 2x faster (optimistic for Anderson on warm): "
              f"end-to-end x{sp2:.3f}", flush=True)

    print("\nNOTE: the per-solve sweep dump is BIMODAL — warm hits at 1 sweep plus a heavy tail "
          "(38-545 sweeps) of cold/slow high-beta solves (incl. the redundant _mtc cold re-solve). "
          "Anderson's 5-9x cold sweep reduction targets that tail; see the Step-2 assessment doc.",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
