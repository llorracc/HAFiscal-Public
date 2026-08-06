"""P5 validation: drop-in JAX solver as agent.solve_one_period.

Strategy (single-step, not iterative):
  1. Build HS_Only agent + run HARK solve to convergence
  2. Call solve_agg_cons_markov_jax ONCE with solution_next = converged solution
  3. Compare returned cFunc evaluations to HARK's converged cFunc
  4. This validates the drop-in wrapper without recursing through HARK's
     full solve loop (which compounds JAX overhead unhelpfully)
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
os.environ['JAX_ENABLE_X64'] = 'True'
import jax
jax.config.update('jax_enable_x64', True)

import numpy as np
import jax.numpy as jnp
from copy import deepcopy
from welfare6_scenario import build_and_solve
from jax_solver_drop_in import install_jax_solver


def main():
    print("=== P5: drop-in JAX solver (single-step test) ===")
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    agent = AggEco.agents[0]

    # HARK reference: full solve
    print("\n[HARK] solving ...", flush=True)
    t0 = time.time()
    agent.solve()
    t_hark = time.time() - t0
    print(f"  HARK: {t_hark:.2f}s")
    sol_h = agent.solution[0]
    StateCount = len(sol_h.cFunc)
    print(f"  StateCount={StateCount}")

    # JAX drop-in: single solve_one_period call at the fixed point
    from jax_solver_drop_in import solve_agg_cons_markov_jax
    print("\n[JAX drop-in] one-step solve at converged solution_next ...", flush=True)
    t0 = time.time()
    sol_j = solve_agg_cons_markov_jax(
        sol_h,                         # solution_next = converged
        agent.IncShkDstn[0],           # per-state distributions
        agent.LivPrb[0],
        agent.DiscFac,
        agent.CRRA,
        agent.Rfree,
        agent.PermGroFac[0],
        agent.MrkvArray[0],
        agent.BoroCnstArt,
        agent.aXtraGrid,
        agent.Cgrid,
        AggEco.CFunc,
        AggEco.ADFunc,
        agent.num_experiment_periods,
        agent.num_base_MrkvStates,
    )
    t_jax = time.time() - t0
    print(f"  JAX (incl. JIT): {t_jax:.2f}s")
    assert len(sol_j.cFunc) == StateCount, f"State count mismatch: {len(sol_j.cFunc)} vs {StateCount}"

    # Compare per-state cFunc evaluations at interior points
    n_query = 50
    m_query = np.linspace(1.0, 10.0, n_query)
    C_query = np.full(n_query, 1.0)

    print(f"\n=== Per-state cFunc comparison ({StateCount} states) ===")
    print(f"{'state':>5} {'max rel':>12} {'mean rel':>12} {'pass':>5}")
    n_pass = 0
    rel_diffs = []
    for j in range(StateCount):
        c_h = sol_h.cFunc[j](m_query, C_query)
        c_j = sol_j.cFunc[j](m_query, C_query)
        denom = np.maximum(np.abs(c_h), 1e-12)
        rd = np.abs((c_j - c_h) / denom)
        passed = rd.max() < 2e-3
        if passed: n_pass += 1
        rel_diffs.append(rd.max())
        mark = '✓' if passed else '✗'
        if j < 6 or not passed:
            print(f"{j:>5} {rd.max():>12.4e} {rd.mean():>12.4e} {mark:>5}")
    rel_diffs = np.asarray(rel_diffs)
    print(f"\nOverall: {n_pass}/{StateCount} pass; "
          f"global max rel = {rel_diffs.max():.4e}; "
          f"global mean rel = {rel_diffs.mean():.4e}")
    print(f"HARK: {t_hark:.1f}s, JAX (incl JIT): {t_jax:.1f}s")
    if n_pass == StateCount:
        print(f"\n✓ P5 drop-in validated at HS_Only ({StateCount} states)")
    else:
        print(f"\n⚠ {StateCount - n_pass} states fail")


if __name__ == '__main__':
    main()
