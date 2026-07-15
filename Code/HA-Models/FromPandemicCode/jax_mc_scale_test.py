"""
Scale the JAX MC kernel using HARK's actual cFunc tables, at increasing N.
Measures speedup vs (a) numpy reference, (b) extrapolated HARK CPU MC cost.
"""
from __future__ import annotations
import os, sys, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import jax.numpy as jnp
from welfare6_scenario import build_and_solve
from jax_mc_hark_integration import extract_hark_kernel_inputs
from jax_mc_minimal import simulate_jax, simulate_np


def main():
    print("=== JAX MC scale test (HARK cFunc tables, HS_Only) ===")
    print("\n[1/3] build_and_solve HS_Only...")
    t0 = time.time()
    ctx = build_and_solve('HS_Only')
    print(f"  solve wall: {time.time()-t0:.1f}s")
    AggEco = ctx['AggEco']
    AggEco.switch_shock_type('base')
    AggEco.solve()
    agent = AggEco.agents[0]

    print(f"\n[2/3] Extract kernel inputs...")
    inp = extract_hark_kernel_inputs(agent, scenario='base')

    # Initial state from agent
    agent.initialize_sim()
    pLvl_init = np.asarray(agent.state_now['pLvl'], dtype=np.float32)
    aNrm_init = np.asarray(agent.state_now['aNrm'], dtype=np.float32)

    # Newborn pool: use first 200 of the lognormal-drawn agents
    nb_N = 200
    newborn_aNrm = aNrm_init[:nb_N].copy()
    newborn_pLvl = pLvl_init[:nb_N].copy()
    newborn_mrkv = np.zeros(nb_N, dtype=np.int32)

    act_T = 40
    print(f"  act_T={act_T}, J={inp['J']}, M_grid={inp['M_grid']}")

    print(f"\n[3/3] Scale sweep (N = 1800 → 1M):")
    print(f"{'N':>8}  {'np wall':>10}  {'jax wall':>10}  {'speedup':>8}  {'AggInc mean':>14}")
    print('-' * 70)

    for N in [1800, 10000, 50000, 100000, 500000, 1_000_000]:
        # Build initial state by replicating the lognormal-drawn pool
        rs = np.random.RandomState(0)
        idx = rs.choice(len(pLvl_init), size=N, replace=True)
        aNrm0 = aNrm_init[idx].copy()
        pLvl0 = pLvl_init[idx].copy()
        mrkv0 = np.zeros(N, dtype=np.int32)   # all employed start

        # numpy bench
        t0 = time.time()
        np_inc, _, _ = simulate_np(
            aNrm0, pLvl0, mrkv0,
            inp['cfunc_table'], inp['m_grid'],
            inp['Rfree'], inp['PermGroFac'], inp['MrkvArray'],
            inp['IncShk_psi'], inp['IncShk_xi'], inp['IncShk_pmv'], inp['IncShk_natoms'],
            1.0, 1.0, inp['Splurge'], inp['LivPrb'],
            newborn_aNrm, newborn_pLvl, newborn_mrkv,
            act_T, seed_base=0)
        wall_np = time.time() - t0

        # JAX bench (warm-up first, then timed)
        jax_args = (
            aNrm0, pLvl0, mrkv0,
            jnp.asarray(inp['cfunc_table']), jnp.asarray(inp['m_grid']),
            jnp.asarray(inp['Rfree']), jnp.asarray(inp['PermGroFac']),
            jnp.asarray(inp['MrkvArray']),
            jnp.asarray(inp['IncShk_psi']), jnp.asarray(inp['IncShk_xi']),
            jnp.asarray(inp['IncShk_pmv']),
            1.0, 1.0, inp['Splurge'], inp['LivPrb'],
            jnp.asarray(newborn_aNrm), jnp.asarray(newborn_pLvl),
            jnp.asarray(newborn_mrkv),
        )
        _ = simulate_jax(*jax_args, act_T, seed_base=0)
        t0 = time.time()
        jax_inc, _, _ = simulate_jax(*jax_args, act_T, seed_base=0)
        wall_jax = time.time() - t0
        sp = wall_np / wall_jax if wall_jax > 0 else float('nan')
        print(f"{N:>8}  {wall_np:>10.3f}s  {wall_jax:>10.3f}s  {sp:>7.1f}x  "
              f"{float(jax_inc.mean()):>14.3f}")


if __name__ == '__main__':
    main()
