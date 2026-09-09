"""Smoke test for cached_solve_ad_recession_hark.

Runs the HARK-AD solver twice on HS_Only with the cache on:
  - First call: MISS, solves and saves
  - Second call: HIT, loads
Confirms the second call is dramatically faster and reproduces the same
numerical output at probe points on agent.solution[0].cFunc and on
eco.stored_solutions['recession'].

Usage:
    HAFISCAL_USE_SOLUTION_CACHE=1 \
        .venv-linux-x86_64/bin/python Code/HA-Models/solution_cache/smoke_test_hark_ad.py
"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
# _HERE = .../Code/HA-Models/solution_cache; FromPandemicCode is a sibling
_HAMODELS = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, _HERE)  # solution_cache package
sys.path.insert(0, os.path.join(_HAMODELS, "FromPandemicCode"))

import numpy as np

# Force cache on for this smoke
os.environ["HAFISCAL_USE_SOLUTION_CACHE"] = "1"
# Clear sys.argv so Parameters.py sees defaults
sys.argv = [sys.argv[0]]


def _build_eco_and_solve_base(parametrization="HS_Only"):
    """Build a fresh eco at HS_Only via welfare6_scenario.build_and_solve,
    then run_base so eco.base_AggCons and eco.stored_solutions are
    initialized (required by solve_ad_recession's store_ADsolution call)."""
    from welfare6_scenario import build_and_solve, run_base
    ctx = build_and_solve(parametrization)
    run_base(ctx)
    return ctx


def _probe_agent_cfunc(eco, n_states_to_probe=4):
    """Sample cFunc at fixed (m, C) for parity comparison. Returns array
    of shape (n_cohorts, n_states_to_probe, 3) where 3 = [c(m=1,C=1),
    c(m=2,C=1), c(m=0.5,C=1)]."""
    out = []
    for agent in eco.agents:
        sol = agent.solution[0]
        n_states = min(n_states_to_probe, len(sol.cFunc))
        cohort_probes = []
        for j in range(n_states):
            cf = sol.cFunc[j]
            c1 = float(cf(np.array([1.0]), np.array([1.0]))[0])
            c2 = float(cf(np.array([2.0]), np.array([1.0]))[0])
            c05 = float(cf(np.array([0.5]), np.array([1.0]))[0])
            cohort_probes.append([c1, c2, c05])
        out.append(cohort_probes)
    return np.asarray(out)


def _probe_stored_solution_cfunc(eco, name):
    """Probe eco.stored_solutions[name].agent_solutions[i][0].cFunc[j] at
    fixed (m, C). Mirrors _probe_agent_cfunc structure."""
    stored = eco.stored_solutions[name]
    out = []
    for c_idx, agent_sols in enumerate(stored.agent_solutions):
        sol = agent_sols[0]
        n_states = min(4, len(sol.cFunc))
        cohort_probes = []
        for j in range(n_states):
            cf = sol.cFunc[j]
            c1 = float(cf(np.array([1.0]), np.array([1.0]))[0])
            c2 = float(cf(np.array([2.0]), np.array([1.0]))[0])
            c05 = float(cf(np.array([0.5]), np.array([1.0]))[0])
            cohort_probes.append([c1, c2, c05])
        out.append(cohort_probes)
    return np.asarray(out)


def main():
    print("[smoke] Wiping HS_Only HARK-AD cache entries...", flush=True)
    import glob
    for f in glob.glob(os.path.join(_HERE, "HS_Only", "recession",
                                     "ad_hark_*.pkl")):
        os.remove(f)
        print(f"   removed {os.path.basename(f)}", flush=True)
    for f in glob.glob(os.path.join(_HERE, "HS_Only", "recession",
                                     "ad_hark_*.meta.json")):
        os.remove(f)

    print("[smoke] === RUN 1: should MISS (solve + save) ===", flush=True)
    t0 = time.time()
    ctx1 = _build_eco_and_solve_base("HS_Only")
    eco1 = ctx1["AggEco"]
    # Mirror welfare6_scenario.run_recession_AD: deepcopy + switch_shock_type
    # before calling solve_ad_recession. switch_shock_type resizes CFunc to
    # the larger recession state space.
    from copy import deepcopy
    eco1 = deepcopy(eco1)
    eco1.switch_shock_type("recession")
    print(f"  build_and_solve + switch_shock_type done in {time.time()-t0:.1f}s",
          flush=True)

    from ad_cache import cached_solve_ad_recession_hark
    t_ad1 = time.time()
    cached_solve_ad_recession_hark(
        {"AggEco": eco1},
        num_max_iterations=ctx1["num_max_iterations_solvingAD"],
        convergence_cutoff=ctx1["convergence_tol_solvingAD"],
        shock_type="recession", name="recession",
        verbose=True,
    )
    wall_miss = time.time() - t_ad1
    print(f"[smoke] RUN 1 AD wall: {wall_miss:.1f}s", flush=True)

    probes1 = _probe_agent_cfunc(eco1)
    stored_probes1 = _probe_stored_solution_cfunc(eco1, "recession")

    print("[smoke] === RUN 2: should HIT (load) ===", flush=True)
    ctx2 = _build_eco_and_solve_base("HS_Only")
    eco2 = deepcopy(ctx2["AggEco"])
    eco2.switch_shock_type("recession")
    t_ad2 = time.time()
    cached_solve_ad_recession_hark(
        {"AggEco": eco2},
        num_max_iterations=ctx2["num_max_iterations_solvingAD"],
        convergence_cutoff=ctx2["convergence_tol_solvingAD"],
        shock_type="recession", name="recession",
        verbose=True,
    )
    wall_hit = time.time() - t_ad2
    print(f"[smoke] RUN 2 AD wall: {wall_hit:.1f}s "
          f"({wall_miss/max(wall_hit,1e-3):.1f}x speedup)", flush=True)

    probes2 = _probe_agent_cfunc(eco2)
    stored_probes2 = _probe_stored_solution_cfunc(eco2, "recession")

    # Parity check
    abs_diff_live = np.max(np.abs(probes1 - probes2))
    rel_diff_live = np.max(np.abs((probes1 - probes2)
                                   / np.maximum(np.abs(probes1), 1e-12)))
    abs_diff_stored = np.max(np.abs(stored_probes1 - stored_probes2))
    rel_diff_stored = np.max(np.abs((stored_probes1 - stored_probes2)
                                     / np.maximum(np.abs(stored_probes1), 1e-12)))

    print(f"\n[smoke] PARITY CHECK", flush=True)
    print(f"  live cFunc probes:   max abs diff = {abs_diff_live:.2e}, "
          f"max rel diff = {rel_diff_live:.2e}", flush=True)
    print(f"  stored cFunc probes: max abs diff = {abs_diff_stored:.2e}, "
          f"max rel diff = {rel_diff_stored:.2e}", flush=True)
    print(f"  miss wall: {wall_miss:.1f}s, hit wall: {wall_hit:.1f}s "
          f"({wall_miss/max(wall_hit,1e-3):.1f}x speedup)", flush=True)

    threshold = 1e-9
    if abs_diff_live > threshold or abs_diff_stored > threshold:
        print(f"\n[smoke] FAIL: parity exceeded {threshold:.0e} "
              f"(live={abs_diff_live:.2e}, stored={abs_diff_stored:.2e})",
              flush=True)
        sys.exit(1)
    if wall_hit > wall_miss * 0.5:
        print(f"\n[smoke] WARN: hit wall ({wall_hit:.1f}s) >= 50% of "
              f"miss wall ({wall_miss:.1f}s) — cache may not be loading",
              flush=True)

    print("\n[smoke] PASS", flush=True)


if __name__ == "__main__":
    main()
