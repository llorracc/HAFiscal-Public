"""HS_Only validation: JAX-shuffle vs HARK-shuffle.

Per-state agent counts must match exactly between JAX and HARK shuffle
since both use deterministic count-matching.
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
from welfare6_scenario import build_and_solve, run_base
from jax_mc_hark_integration import extract_recession_kernel_inputs, draw_newborn_pool_from_agent
from jax_mc_ad import extract_cfunc_table_per_period, compute_AggDemandFac_path
from jax_mc_ad_shuffle import simulate_jax_ad_shuffle


def main():
    print("=== HS_Only JAX-shuffle test ===", flush=True)
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    _ = run_base(ctx)

    # HARK reference WITH shuffle
    eco_h = deepcopy(AggEco)
    eco_h.switch_shock_type('recession')
    for ag in eco_h.agents:
        ag.mc_shuffle = True  # enable shuffle path

    print("\n[HARK] recession AD with shuffle ...", flush=True)
    t0 = time.time()
    eco_h.solve_ad_recession(num_max_iterations=ctx['num_max_iterations_solvingAD'],
                              convergence_cutoff=ctx['convergence_tol_solvingAD'],
                              name='recession')
    print(f"HARK shuffle AD: {time.time()-t0:.1f}s", flush=True)
    eco_h.switch_shock_type('recession')
    eco_h.restore_ADsolution(name='recession')
    num_exp = eco_h.num_experiment_periods
    rec_dict = {
        'shock_type': 'recession', 'UpdatePrb': 1.0,
        'Splurge': eco_h.agents[0].Splurge,
        'EconomyMrkv_init': list(np.arange(1, num_exp + 1) * 2 + 1) + [1]*12 + [0]*20,
    }
    h_res = eco_h.run_experiment(**rec_dict, Full_Output=True)
    hark_cratio = np.asarray(h_res['Cratio_hist'])
    hark_aggcons = np.asarray(h_res['AggCons'])
    print(f"HARK-shuffle Cratio[:5]: {hark_cratio[:5]}")
    print(f"HARK-shuffle AggCons[0]: {hark_aggcons[0]:.4f}")

    # Per-state counts at t=0 from HARK
    mrkv_t0 = np.asarray(h_res['Mrkv_hist'][0])
    J = eco_h.num_base_MrkvStates
    h_counts = [(mrkv_t0 % J == j).sum() for j in range(J)]
    print(f"HARK Mrkv micro counts at t=0: {h_counts}")

    # JAX shuffle (using HARK init for matching Cratio)
    print("\n[JAX] simulate_jax_ad_shuffle (recession, no policy) ...", flush=True)
    from AggFiscalModel import CRule
    eco_j = deepcopy(AggEco)
    eco_j.switch_shock_type('recession')
    # Install HARK-converged MacroCFunc
    n_combined = len(eco_j.CFunc)
    n_macro = n_combined // J
    MacroCFunc = [[CRule(1.0, 0.0) for _ in range(n_macro)] for _ in range(n_macro)]
    MacroCFunc[0][3] = CRule(float(hark_cratio[0]), 0.0)
    for j in range(num_exp - 1):
        MacroCFunc[2*j+3][2*j+5] = CRule(float(hark_cratio[j+1]), 0.0)
    MacroCFunc[2*num_exp+1][1] = CRule(float(hark_cratio[num_exp]), 0.0)
    MacroCFunc[1][1] = CRule(float(np.mean(hark_cratio[num_exp+1:num_exp+10])), 0.0)
    eco_j.CFunc = eco_j.Macro_2_Micro_CFunc(MacroCFunc)
    for agent in eco_j.agents:
        agent.CFunc = eco_j.CFunc
    eco_j.ADelasticity = eco_j.demand_ADelasticity
    eco_j.solve()
    agent = eco_j.agents[0]
    inp = extract_recession_kernel_inputs(agent, scenario='recession')
    m_grid = np.asarray(inp['m_grid']).astype(np.float64)
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
    ADF_path = compute_AggDemandFac_path(Cratio_obs, EconomyMrkv_path, 1, eco_j.demand_ADelasticity).astype(np.float64)
    cfunc_table = extract_cfunc_table_per_period(agent, Cratio_obs, m_grid, n_combined=n_combined).astype(np.float64)
    nbA, nbP, _ = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99)

    # Init from HARK shuffle history
    h_aNrm0 = np.asarray(h_res['aNrm_all'][0]).astype(np.float64)
    h_pLvl0 = np.asarray(h_res['pLvl_all'][0]).astype(np.float64)
    h_micro0 = (mrkv_t0 % J).astype(np.int32)

    cons_per_seed = []
    panel_jax_seeds = []
    for s in range(4):
        _, cons, panel = simulate_jax_ad_shuffle(
            h_aNrm0, h_pLvl0, h_micro0,
            EconomyMrkv_path, ADF_path, cfunc_table,
            m_grid,
            jnp.asarray(inp['Rfree_macro'], dtype=jnp.float64),
            jnp.asarray(inp['PermGroFac_macro'], dtype=jnp.float64),
            jnp.asarray(inp['MrkvArray_macro'], dtype=jnp.float64),
            jnp.asarray(inp['IncShk_psi_macro'], dtype=jnp.float64),
            jnp.asarray(inp['IncShk_xi_macro'], dtype=jnp.float64),
            jnp.asarray(inp['IncShk_pmv_macro'], dtype=jnp.float64),
            inp['Splurge'], inp['LivPrb'],
            jnp.asarray(nbA), jnp.asarray(nbP),
            act_T=act_T, seed_base=s, J=J)
        cons_per_seed.append(np.asarray(cons))
        panel_jax_seeds.append(np.asarray(panel))
    jax_aggcons = np.mean(cons_per_seed, axis=0)
    jax_cratio = jax_aggcons / eco_j.base_AggCons
    print(f"\nJAX-shuffle Cratio[:5]: {jax_cratio[:5]}")
    print(f"JAX-shuffle AggCons[0]: {jax_aggcons[0]:.4f}")
    print(f"Ratio JAX/HARK Cratio[:5]: {jax_cratio[:5]/hark_cratio[:5]}")
    n_act = num_exp + 12
    rel = (jax_cratio[:n_act] - hark_cratio[:n_act]) / hark_cratio[:n_act]
    print(f"Mean ratio (first {n_act}): {np.mean(jax_cratio[:n_act])/np.mean(hark_cratio[:n_act]):.6f}")
    print(f"Max |rel diff|: {np.max(np.abs(rel)):.4f}")


if __name__ == '__main__':
    main()
