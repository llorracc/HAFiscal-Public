"""
Test Option B claim: with many seeds, stochastic JAX has lower MC noise
than a single HARK realization.

Runs JAX MC at HS_Only with 100 seeds, measures Cratio[0] std and SE.
Compares to HARK's single-realization expected noise (~0.5-1% per single
trajectory at N=1800).
"""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

os.environ['JAX_ENABLE_X64'] = 'True'
import jax
jax.config.update('jax_enable_x64', True)

import numpy as np
import jax.numpy as jnp
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base
from jax_mc_hark_integration import extract_recession_kernel_inputs, draw_newborn_pool_from_agent
from jax_mc_ad import simulate_jax_ad, extract_cfunc_table_per_period, compute_AggDemandFac_path


def main():
    print("=== Many-seed JAX MC noise test (HS_Only) ===", flush=True)

    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    _ = run_base(ctx)
    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')

    # Install identity CFunc + solve (so we measure NO-AD MC noise directly)
    from AggFiscalModel import CRule
    n_combined = len(eco.CFunc)
    J = eco.num_base_MrkvStates
    n_macro = n_combined // J
    num_exp = eco.num_experiment_periods
    eco.CFunc = [[CRule(1.0, 0.0) for _ in range(n_combined)] for _ in range(n_combined)]
    for agent in eco.agents:
        agent.CFunc = eco.CFunc
    eco.ADelasticity = eco.demand_ADelasticity
    eco.solve()

    agent = eco.agents[0]
    inp = extract_recession_kernel_inputs(agent, scenario='recession')
    m_grid = np.asarray(inp['m_grid']).astype(np.float64)
    act_T = 40
    EconomyMrkv_init = list(np.arange(1, num_exp+1)*2+1) + [1]*12 + [0]*20
    EconomyMrkv_path = (EconomyMrkv_init + [0]*act_T)[:act_T]
    Cratio_obs = np.ones(act_T)  # identity CFunc → Cratio_obs=1 always
    ADF_path = compute_AggDemandFac_path(Cratio_obs, EconomyMrkv_path, 1, eco.demand_ADelasticity).astype(np.float64)
    cfunc_table = extract_cfunc_table_per_period(agent, Cratio_obs, m_grid, n_combined=n_combined).astype(np.float64)

    nbA, nbP, _ = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99)
    nbA = nbA.astype(np.float64); nbP = nbP.astype(np.float64)
    # Fresh init from newborn pool (no HARK ref needed for noise test)
    N = agent.AgentCount
    T_age_max = int(getattr(agent, 'T_age', 100) or 100)
    rs = np.random.RandomState(42)
    idx = rs.choice(len(nbA), size=N, replace=True)
    aNrm0 = nbA[idx]; pLvl0 = nbP[idx]
    micro0 = np.zeros(N, dtype=np.int32)

    common = dict(
        Rfree_macro=jnp.asarray(inp['Rfree_macro'], dtype=jnp.float64),
        PermGroFac_macro=jnp.asarray(inp['PermGroFac_macro'], dtype=jnp.float64),
        MrkvArray_macro=jnp.asarray(inp['MrkvArray_macro'], dtype=jnp.float64),
        IncShk_psi_macro=jnp.asarray(inp['IncShk_psi_macro'], dtype=jnp.float64),
        IncShk_xi_macro=jnp.asarray(inp['IncShk_xi_macro'], dtype=jnp.float64),
        IncShk_pmv_macro=jnp.asarray(inp['IncShk_pmv_macro'], dtype=jnp.float64),
        Splurge=inp['Splurge'], LivPrb=inp['LivPrb'],
        newborn_aNrm=jnp.asarray(nbA), newborn_pLvl=jnp.asarray(nbP),
        act_T=act_T, T_age_max=T_age_max,
    )

    seeds = list(range(100))
    cratio_t0 = []
    cratio_means = []  # mean Cratio over first 22 periods per seed
    AggCons_runs = []
    t0 = time.time()
    for s in seeds:
        _, cons, _ = simulate_jax_ad(
            aNrm0, pLvl0, micro0,
            EconomyMrkv_path, ADF_path, cfunc_table,
            jnp.asarray(m_grid), **common, seed_base=s)
        AggCons_runs.append(np.asarray(cons))

    wall = time.time() - t0
    AggCons_arr = np.stack(AggCons_runs, axis=0)  # (100, T)
    base = float(AggCons_arr.mean(axis=0).mean())  # roughly base value
    cratio_arr = AggCons_arr  # not normalized; just look at AggCons SE
    print(f"\nWall for 100 seeds: {wall:.1f}s ({wall/100:.2f}s/seed after JIT)", flush=True)

    # Stats on AggCons[0]
    print(f"\nAggCons[0] across 100 seeds:")
    print(f"  mean = {AggCons_arr[:, 0].mean():.3f}")
    print(f"  std  = {AggCons_arr[:, 0].std():.3f}")
    print(f"  rel std = {AggCons_arr[:, 0].std()/AggCons_arr[:, 0].mean()*100:.3f}%")
    print(f"  SE of seed-mean (100 seeds) = {AggCons_arr[:, 0].std()/np.sqrt(100)/AggCons_arr[:, 0].mean()*100:.4f}%")

    # MC SE for a single HARK realization (theoretical)
    # SE_single ≈ σ_per_agent / sqrt(N). Compute σ per-agent.
    # We don't have per-agent here; use the relative std as a proxy.
    print(f"\nInterpretation:")
    print(f"  Single-realization SE of AggCons[0]: ~{AggCons_arr[:, 0].std()/AggCons_arr[:, 0].mean()*100:.3f}% (matches a single HARK MC run)")
    print(f"  100-seed-mean SE: ~{AggCons_arr[:, 0].std()/np.sqrt(100)/AggCons_arr[:, 0].mean()*100:.4f}% (10x tighter)")
    print(f"  Net cost: {wall:.0f}s for 100 seeds vs ~1-3s for 1 HARK realization at HS_Only")

    # Per-period
    print(f"\nPer-period std/mean of AggCons (first 8):")
    for t in range(8):
        m, s = AggCons_arr[:, t].mean(), AggCons_arr[:, t].std()
        print(f"  t={t}: mean={m:.3f}, std={s:.3f} ({s/m*100:.3f}%)")


if __name__ == '__main__':
    main()
