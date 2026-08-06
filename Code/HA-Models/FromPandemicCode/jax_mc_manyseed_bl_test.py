"""
Many-seed JAX MC at Baseline (validates Option B at production scale).

Runs JAX MC at Baseline with 100 seeds × 21 cohorts under HARK-converged
CFunc. Measures std of seed-averaged Cratio[0] and compares to HARK's
single-realization noise.
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
    print("=== Baseline many-seed JAX MC (Option B validation at scale) ===", flush=True)
    ref = pickle.load(open('welfare6_BL_ad_ref_v4/recession_AD.pkl', 'rb'))
    hark_cratio = ref['iter_logs'][-1]['Cratio_hist']
    hark_aggcons = ref['iter_logs'][-1]['AggCons']
    base_AggCons = np.asarray(ref['base_AggCons'])

    t0 = time.time()
    ctx = build_and_solve('Baseline')
    AggEco = ctx['AggEco']
    _ = run_base(ctx)
    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')
    print(f"build/solve/base: {time.time()-t0:.1f}s", flush=True)

    from AggFiscalModel import CRule
    n_combined = len(eco.CFunc)
    J = eco.num_base_MrkvStates
    n_macro = n_combined // J
    num_exp = eco.num_experiment_periods
    MacroCFunc = [[CRule(1.0, 0.0) for _ in range(n_macro)] for _ in range(n_macro)]
    MacroCFunc[0][3] = CRule(float(hark_cratio[0]), 0.0)
    for j in range(num_exp - 1):
        MacroCFunc[2*j+3][2*j+5] = CRule(float(hark_cratio[j+1]), 0.0)
    MacroCFunc[2*num_exp+1][1] = CRule(float(hark_cratio[num_exp]), 0.0)
    MacroCFunc[1][1] = CRule(float(np.mean(hark_cratio[num_exp+1:num_exp+10])), 0.0)
    eco.CFunc = eco.Macro_2_Micro_CFunc(MacroCFunc)
    for agent in eco.agents:
        agent.CFunc = eco.CFunc
    eco.ADelasticity = eco.demand_ADelasticity

    print("Solving eco...", flush=True)
    t0 = time.time()
    eco.solve()
    print(f"solve: {time.time()-t0:.1f}s", flush=True)

    act_T = len(hark_cratio)
    EconomyMrkv_init = list(np.arange(1, num_exp+1)*2+1) + [1]*12 + [0]*20
    EconomyMrkv_path = (EconomyMrkv_init + [0]*act_T)[:act_T]
    macros = np.array(EconomyMrkv_path, dtype=int)
    Cratio_obs = np.zeros(act_T)
    Cratio_obs[0] = MacroCFunc[0][macros[0]].intercept
    for t in range(1, act_T):
        i, j = macros[t-1], macros[t]
        rule = MacroCFunc[i][j]
        Cratio_obs[t] = rule.intercept + rule.slope * (Cratio_obs[t-1] - 1.0)
    ADF_path = compute_AggDemandFac_path(Cratio_obs, EconomyMrkv_path, 1, eco.demand_ADelasticity).astype(np.float64)

    per_cohort = ref['iter_logs'][-1]['per_cohort']
    cohort_weights = ref['cohort_pop_factors']
    SEEDS = list(range(50))  # 50 seeds, reasonable balance
    AggCons_per_seed = np.zeros((len(SEEDS), act_T))

    t_total = time.time()
    for c_idx, agent in enumerate(eco.agents):
        t_c = time.time()
        inp = extract_recession_kernel_inputs(agent, scenario='recession')
        m_grid = np.asarray(inp['m_grid']).astype(np.float64)
        cfunc_table = extract_cfunc_table_per_period(agent, Cratio_obs, m_grid,
                                                       n_combined=n_combined).astype(np.float64)
        nbA, nbP, _ = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99+c_idx)
        nbA = nbA.astype(np.float64); nbP = nbP.astype(np.float64)
        h_p = per_cohort[c_idx]
        aNrm0 = h_p['aNrm_init_perperiod'][0].astype(np.float64)
        pLvl0 = h_p['pLvl_init_perperiod'][0].astype(np.float64)
        micro0 = (h_p['shock_Mrkv'][0] % J).astype(np.int32)
        T_age_max = int(getattr(agent, 'T_age', 100) or 100)

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
        for s_idx, s in enumerate(SEEDS):
            _, cons, _ = simulate_jax_ad(
                aNrm0, pLvl0, micro0,
                EconomyMrkv_path, ADF_path, cfunc_table,
                jnp.asarray(m_grid), **common, seed_base=s*31+c_idx)
            AggCons_per_seed[s_idx] += cohort_weights[c_idx] * np.asarray(cons)
        print(f"  cohort {c_idx:2d} N={agent.AgentCount:4d} done in {time.time()-t_c:.1f}s",
              flush=True)
    print(f"\nTotal wall for {len(SEEDS)} seeds × {len(eco.agents)} cohorts: {time.time()-t_total:.1f}s",
          flush=True)

    cratio_per_seed = AggCons_per_seed / base_AggCons
    mean_cratio = cratio_per_seed.mean(axis=0)
    std_cratio = cratio_per_seed.std(axis=0)
    se_cratio = std_cratio / np.sqrt(len(SEEDS))

    print(f"\n=== Many-seed JAX vs HARK at Baseline ===")
    print(f"JAX {len(SEEDS)}-seed mean Cratio[0]: {mean_cratio[0]:.6f}")
    print(f"  std across seeds:   {std_cratio[0]:.6f} ({std_cratio[0]/mean_cratio[0]*100:.3f}%)")
    print(f"  SE of seed-mean:    {se_cratio[0]:.6f} ({se_cratio[0]/mean_cratio[0]*100:.4f}%)")
    print(f"HARK Cratio[0]: {hark_cratio[0]:.6f}")
    print(f"JAX-mean vs HARK: ratio={mean_cratio[0]/hark_cratio[0]:.6f}, diff={(mean_cratio[0]-hark_cratio[0])/hark_cratio[0]*100:+.4f}%")
    print(f"How many SE between JAX-mean and HARK[0]: {abs(mean_cratio[0]-hark_cratio[0])/se_cratio[0]:.2f}σ")

    print(f"\nMean Cratio over 32 periods:")
    print(f"  JAX {len(SEEDS)}-seed mean: {mean_cratio[:32].mean():.6f}")
    print(f"  HARK:                    {hark_cratio[:32].mean():.6f}")
    print(f"  ratio:                   {mean_cratio[:32].mean()/hark_cratio[:32].mean():.6f}")


if __name__ == '__main__':
    main()
