"""RR replay v2 sanity — should match HARK to bit-precision like HS_Only."""
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
from jax_mc_hark_integration import extract_recession_kernel_inputs
from jax_mc_ad import extract_cfunc_table_per_period, compute_AggDemandFac_path
from jax_mc_ad_replay_v2 import simulate_jax_replay_v2


def main():
    print("=== Reduced_Run replay v2 sanity ===", flush=True)
    t0 = time.time()
    ctx = build_and_solve('Reduced_Run')
    AggEco = ctx['AggEco']
    _ = run_base(ctx)
    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')
    for agent in eco.agents:
        if 't_age' not in agent.track_vars:
            agent.track_vars = list(agent.track_vars) + ['t_age']
    print(f"build/base: {time.time()-t0:.1f}s", flush=True)

    captured = {id(a): {'aNrm_init': [], 'pLvl_init': []} for a in eco.agents}
    for agent in eco.agents:
        orig_mort = agent.get_mortality
        cap = captured[id(agent)]
        def make_wrap(a_ref, c_ref, of):
            def wrapped():
                of()
                c_ref['aNrm_init'].append(np.asarray(a_ref.state_now['aNrm']).copy())
                c_ref['pLvl_init'].append(np.asarray(a_ref.state_now['pLvl']).copy())
            return wrapped
        agent.get_mortality = make_wrap(agent, cap, orig_mort)

    iter_logs = []
    orig_run = eco.run_experiment
    def logged_run(*args, **kwargs):
        for cv in captured.values():
            cv['aNrm_init'].clear(); cv['pLvl_init'].clear()
        result = orig_run(*args, **kwargs)
        per_cohort = []
        for ThisType in eco.agents:
            cap = captured[id(ThisType)]
            per_cohort.append({
                'aNrm_t0': np.asarray(ThisType.history['aNrm'][0]),
                'pLvl_t0': np.asarray(ThisType.history['pLvl'][0]),
                'shock_Mrkv': np.asarray(ThisType.shock_history['Mrkv'], dtype=np.int32),
                'shock_TranShk': np.asarray(ThisType.shock_history['TranShk'], dtype=np.float64),
                'shock_PermShk': np.asarray(ThisType.shock_history['PermShk'], dtype=np.float64),
                'shock_who_dies': np.asarray(ThisType.shock_history['who_dies'], dtype=bool),
                'aNrm_init_perperiod': np.stack(cap['aNrm_init'], axis=0).astype(np.float64),
                'pLvl_init_perperiod': np.stack(cap['pLvl_init'], axis=0).astype(np.float64),
            })
        iter_logs.append({
            'Cratio_hist': np.asarray(result['Cratio_hist']),
            'AggCons': np.asarray(result['AggCons']),
            'per_cohort': per_cohort,
        })
        return result
    eco.run_experiment = logged_run

    t0 = time.time()
    eco.solve_ad_recession(num_max_iterations=ctx['num_max_iterations_solvingAD'],
                            convergence_cutoff=ctx['convergence_tol_solvingAD'], name=None)
    print(f"HARK AD: {time.time()-t0:.1f}s ({len(iter_logs)} iters)", flush=True)

    hark_cratio = iter_logs[-1]['Cratio_hist']
    hark_aggcons = iter_logs[-1]['AggCons']
    base_AggCons = np.asarray(eco.base_AggCons)

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
    eco.solve()

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

    per_cohort = iter_logs[-1]['per_cohort']
    per_cohort_aggcons = []
    for c_idx, agent in enumerate(eco.agents):
        inp = extract_recession_kernel_inputs(agent, scenario='recession')
        m_grid = np.asarray(inp['m_grid']).astype(np.float64)
        cfunc_table = extract_cfunc_table_per_period(agent, Cratio_obs, m_grid,
                                                       n_combined=n_combined).astype(np.float64)
        h_p = per_cohort[c_idx]
        aNrm0 = h_p['aNrm_init_perperiod'][0].astype(np.float64)
        pLvl0 = h_p['pLvl_init_perperiod'][0].astype(np.float64)
        _, cons, _ = simulate_jax_replay_v2(
            aNrm0, pLvl0, ADF_path, cfunc_table, jnp.asarray(m_grid),
            h_p['shock_Mrkv'].astype(np.int32),
            h_p['shock_TranShk'].astype(np.float64),
            h_p['shock_PermShk'].astype(np.float64),
            h_p['shock_who_dies'].astype(bool),
            h_p['aNrm_init_perperiod'].astype(np.float64),
            h_p['pLvl_init_perperiod'].astype(np.float64),
            Rfree_macro=jnp.asarray(inp['Rfree_macro'], dtype=jnp.float64),
            PermGroFac_macro=jnp.asarray(inp['PermGroFac_macro'], dtype=jnp.float64),
            Splurge=inp['Splurge'], act_T=act_T, J=J)
        per_cohort_aggcons.append(np.asarray(cons))
        print(f"  cohort {c_idx} N={agent.AgentCount} JAX-replay-v2 AggCons[0]={per_cohort_aggcons[-1][0]:.4f}",
              flush=True)

    jax_total = np.sum(per_cohort_aggcons, axis=0)
    jax_cratio = jax_total / base_AggCons
    print(f"\n=== RR Replay-v2 Summary ===")
    print(f"JAX AggCons[0]={jax_total[0]:.4f}, HARK={hark_aggcons[0]:.4f}, ratio={jax_total[0]/hark_aggcons[0]:.6f}")
    print(f"JAX Cratio[:8]: {jax_cratio[:8]}")
    print(f"HARK Cratio[:8]: {hark_cratio[:8]}")
    n_act = num_exp + 12
    rel = (jax_cratio[:n_act] - hark_cratio[:n_act]) / hark_cratio[:n_act]
    print(f"Mean ratio (first {n_act}): {np.mean(jax_cratio[:n_act])/np.mean(hark_cratio[:n_act]):.6f}")
    print(f"Max |rel diff|: {np.max(np.abs(rel)):.6f}, mean diff: {np.mean(rel):+.6f}")


if __name__ == '__main__':
    main()
