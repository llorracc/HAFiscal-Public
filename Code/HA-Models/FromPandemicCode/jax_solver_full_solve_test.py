"""P6: full agent.solve() with JAX drop-in installed — integration test.

This tests the iterative path: HARK's solver iterates by calling
solve_one_period (= our JAX wrapper) until convergence, recursively
passing each iter's output as solution_next to the next iter.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
os.environ['JAX_ENABLE_X64'] = 'True'
import jax
jax.config.update('jax_enable_x64', True)

import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve
from jax_solver_drop_in import install_jax_solver


def main():
    print("=== P6: full agent.solve() with JAX drop-in ===")
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']

    # HARK reference
    eco_h = deepcopy(AggEco)
    agent_h = eco_h.agents[0]
    print("\n[HARK] solving ...", flush=True)
    t0 = time.time()
    agent_h.solve()
    t_hark = time.time() - t0
    print(f"  HARK full-solve: {t_hark:.2f}s")
    sol_h = agent_h.solution[0]
    StateCount = len(sol_h.cFunc)

    # JAX drop-in
    eco_j = deepcopy(AggEco)
    agent_j = eco_j.agents[0]
    install_jax_solver(agent_j)
    print("\n[JAX-drop-in] full solve (incl. JIT compile per shape) ...", flush=True)
    t0 = time.time()
    agent_j.solve()
    t_jax = time.time() - t0
    print(f"  JAX full-solve: {t_jax:.2f}s")
    sol_j = agent_j.solution[0]

    n_query = 50
    m_query = np.linspace(1.0, 10.0, n_query)
    C_query = np.full(n_query, 1.0)

    print(f"\n=== Converged cFunc comparison ({StateCount} states) ===")
    print(f"{'state':>5} {'max rel':>12} {'mean rel':>12} {'pass':>5}")
    n_pass = 0
    for j in range(StateCount):
        c_h = sol_h.cFunc[j](m_query, C_query)
        c_j = sol_j.cFunc[j](m_query, C_query)
        denom = np.maximum(np.abs(c_h), 1e-12)
        rd = np.abs((c_j - c_h) / denom)
        passed = rd.max() < 5e-3
        if passed: n_pass += 1
        mark = '✓' if passed else '✗'
        print(f"{j:>5} {rd.max():>12.4e} {rd.mean():>12.4e} {mark:>5}")

    print(f"\nWall: HARK {t_hark:.1f}s, JAX {t_jax:.1f}s")
    print(f"Pass: {n_pass}/{StateCount}")
    if n_pass == StateCount:
        print("\n✓ P6 full-solve integration works")
    else:
        print(f"\n⚠ {StateCount - n_pass} states fail")


if __name__ == '__main__':
    main()
