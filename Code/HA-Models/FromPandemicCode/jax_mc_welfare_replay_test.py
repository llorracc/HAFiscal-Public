"""Decisive test: does replay-v2 close the welfare gap?

Run HARK AD for recession + recessionCheck, capture shock_history per cohort.
Run JAX replay-v2 on each scenario using HARK's captured shocks + newborn states.
Compute welfare cell from JAX replay panels and compare to HARK.

If welfare gap closes to ~0%, the kernel is bit-correct and the 6% gap is
purely from JAX's independent RNG realization. If gap stays ~6%, the kernel
has a scenario-specific bug for Check delivery.
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
from run_welfare6_parallel import welfare6_mc
from jax_mc_ad_replay_v2 import simulate_jax_replay_v2
from jax_mc_ad import extract_cfunc_table_per_period, compute_AggDemandFac_path
from jax_mc_hark_integration import extract_recession_kernel_inputs


def _setup_capture_hooks(eco):
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
        if 't_age' not in agent.track_vars:
            agent.track_vars = list(agent.track_vars) + ['t_age']
    return captured


def run_hark_with_capture(AggEco, shock_type, num_exp, num_iter, cutoff):
    eco = deepcopy(AggEco)
    eco.switch_shock_type(shock_type)
    captured = _setup_capture_hooks(eco)
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
                'shock_Mrkv': np.asarray(ThisType.shock_history['Mrkv'], dtype=np.int32),
                'shock_TranShk': np.asarray(ThisType.shock_history['TranShk'], dtype=np.float64),
                'shock_PermShk': np.asarray(ThisType.shock_history['PermShk'], dtype=np.float64),
                'shock_who_dies': np.asarray(ThisType.shock_history['who_dies'], dtype=bool),
                'aNrm_init_perperiod': np.stack(cap['aNrm_init'], axis=0).astype(np.float64),
                'pLvl_init_perperiod': np.stack(cap['pLvl_init'], axis=0).astype(np.float64),
                'cLvl_all_splurge': np.asarray(result['cLvl_all_splurge']),
            })
        iter_logs.append({
            'Cratio_hist': np.asarray(result['Cratio_hist']),
            'AggCons': np.asarray(result['AggCons']),
            'AggIncome': np.asarray(result.get('AggIncome', result.get('AggInc'))),
            'cLvl_all_splurge': np.asarray(result['cLvl_all_splurge']),
            'per_cohort': per_cohort,
            'result_full': result,
        })
        return result

    eco.run_experiment = logged_run
    if shock_type == 'recession':
        eco.solve_ad_recession(num_max_iterations=num_iter,
                                convergence_cutoff=cutoff, name=shock_type)
    elif shock_type == 'recessionCheck':
        eco.solve_ad_check_recession(num_max_iterations=num_iter,
                                      convergence_cutoff=cutoff, name=shock_type)
    elif shock_type == 'recessionTaxCut':
        eco.solve_ad_recession_taxcut(num_max_iterations=num_iter,
                                       convergence_cutoff=cutoff, name=shock_type)
    elif shock_type == 'recessionUI':
        eco.solve_ad_ui_extension_recession(num_max_iterations=num_iter,
                                             convergence_cutoff=cutoff, name=shock_type)
    else:
        raise ValueError(f"run_hark_with_capture: unsupported shock_type={shock_type!r}")
    return eco, iter_logs[-1]


def jax_replay_scenario(eco, hark_log, shock_type, num_exp):
    """Run JAX replay-v2 for one scenario, return dict matching welfare6_mc input."""
    hark_cratio = hark_log['Cratio_hist']
    base_AggCons = np.asarray(eco.base_AggCons)
    act_T = len(hark_cratio)
    n_combined = len(eco.CFunc)
    J = eco.num_base_MrkvStates

    # Install HARK-converged MacroCFunc + re-solve
    from AggFiscalModel import CRule
    n_macro = n_combined // J
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

    EconomyMrkv_init = list(np.arange(1, num_exp+1)*2+1) + [1]*12 + [0]*20
    EconomyMrkv_path = (EconomyMrkv_init + [0]*act_T)[:act_T]
    macros = np.array(EconomyMrkv_path, dtype=int)
    Cratio_obs = np.zeros(act_T)
    Cratio_obs[0] = MacroCFunc[0][macros[0]].intercept
    for t in range(1, act_T):
        i, j = macros[t-1], macros[t]
        rule = MacroCFunc[i][j]
        Cratio_obs[t] = rule.intercept + rule.slope * (Cratio_obs[t-1] - 1.0)
    ADF_path = compute_AggDemandFac_path(Cratio_obs, EconomyMrkv_path, 1,
                                          eco.demand_ADelasticity).astype(np.float64)

    cohort_weights = [float(getattr(a, 'pop_rescale_factor', 1.0))
                      for a in eco.agents]
    AggCons_total = np.zeros(act_T)
    AggInc_total = np.zeros(act_T)
    cLvl_panels = []
    for c_idx, agent in enumerate(eco.agents):
        inp = extract_recession_kernel_inputs(agent, scenario=shock_type)
        m_grid = np.asarray(inp['m_grid']).astype(np.float64)
        cfunc_table = extract_cfunc_table_per_period(
            agent, Cratio_obs, m_grid, n_combined=n_combined).astype(np.float64)
        h_p = hark_log['per_cohort'][c_idx]
        aNrm0 = h_p['aNrm_init_perperiod'][0].astype(np.float64)
        pLvl0 = h_p['pLvl_init_perperiod'][0].astype(np.float64)
        inc, cons, panel = simulate_jax_replay_v2(
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
        AggCons_total += np.asarray(cons) * cohort_weights[c_idx]
        AggInc_total += np.asarray(inc) * cohort_weights[c_idx]
        cLvl_panels.append(np.asarray(panel))

    cLvl_full = np.concatenate(cLvl_panels, axis=1) if cLvl_panels else None
    return {
        'AggCons': AggCons_total,
        'AggIncome': AggInc_total,
        'cLvl_all_splurge': cLvl_full,
        'Cratio_hist': AggCons_total / base_AggCons,
    }


def main():
    print("=== Replay-v2 welfare gap test: HS_Only check_rec_AD ===")
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    base_result = run_base(ctx)
    num_exp = ctx['num_experiment_periods']
    num_iter = ctx['num_max_iterations_solvingAD']
    cutoff = ctx['convergence_tol_solvingAD']

    print("\n[HARK+capture] recession_AD ...", flush=True)
    eco_rec, hark_rec_log = run_hark_with_capture(
        AggEco, 'recession', num_exp, num_iter, cutoff)

    print("[HARK+capture] recessionCheck_AD ...", flush=True)
    eco_chk, hark_chk_log = run_hark_with_capture(
        AggEco, 'recessionCheck', num_exp, num_iter, cutoff)

    # HARK welfare cell (canonical)
    hark_rec_r = {'AggCons': hark_rec_log['AggCons'],
                  'AggIncome': hark_rec_log['AggIncome'],
                  'cLvl_all_splurge': hark_rec_log['cLvl_all_splurge']}
    hark_chk_r = {'AggCons': hark_chk_log['AggCons'],
                  'AggIncome': hark_chk_log['AggIncome'],
                  'cLvl_all_splurge': hark_chk_log['cLvl_all_splurge']}
    hark_cell = welfare6_mc(hark_chk_r, hark_rec_r, base_result,
                              ctx['act_T'], ctx['Rfree'], ctx['CRRA'])
    print(f"\nHARK welfare cell: {hark_cell:.6f}", flush=True)

    print("\n[JAX-replay-v2] recession_AD ...", flush=True)
    jax_rec_r = jax_replay_scenario(eco_rec, hark_rec_log, 'recession', num_exp)
    print(f"  JAX-replay rec Cratio[0]={jax_rec_r['Cratio_hist'][0]:.4f} vs HARK {hark_rec_log['Cratio_hist'][0]:.4f}")

    print("\n[JAX-replay-v2] recessionCheck_AD ...", flush=True)
    jax_chk_r = jax_replay_scenario(eco_chk, hark_chk_log, 'recessionCheck', num_exp)
    print(f"  JAX-replay chk Cratio[0]={jax_chk_r['Cratio_hist'][0]:.4f} vs HARK {hark_chk_log['Cratio_hist'][0]:.4f}")

    jax_cell = welfare6_mc(jax_chk_r, jax_rec_r, base_result,
                            ctx['act_T'], ctx['Rfree'], ctx['CRRA'])

    print(f"\n=== Result ===")
    print(f"HARK welfare cell: {hark_cell:.6f}")
    print(f"JAX-replay-v2 welfare cell: {jax_cell:.6f}")
    rel = (jax_cell - hark_cell) / hark_cell * 100
    print(f"Gap: {rel:+.4f}%")
    print(f"\nPRIOR (JAX-autoinit with own RNG): +6.40%")
    print(f"NOW   (JAX-replay-v2 with HARK shocks): {rel:+.2f}%")
    if abs(rel) < 0.5:
        print("✓ Gap CLOSES under replay-v2 → 6% gap was from independent RNG")
    elif abs(rel) < 2.0:
        print(f"⚠ Gap partially closes ({rel:+.2f}% vs prior +6.40%)")
    else:
        print(f"✗ Gap PERSISTS under replay-v2 → kernel has bug")


if __name__ == '__main__':
    main()
