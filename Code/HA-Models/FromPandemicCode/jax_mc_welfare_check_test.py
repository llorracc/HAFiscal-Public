"""End-to-end welfare-6 cell check_rec_AD from JAX-AD output vs HARK.

Pipeline:
  1. HARK runs base + recession_AD + recessionCheck_AD; compute HARK welfare cell
  2. JAX runs recession_AD + recessionCheck_AD using HARK init from step 1
  3. Compute JAX welfare cell using HARK's base panel + JAX-AD outputs
  4. Compare
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

os.environ['JAX_ENABLE_X64'] = 'True'
import jax
jax.config.update('jax_enable_x64', True)

import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base
from jax_mc_ad_multicohort import solve_ad_recession_jax_multicohort
from run_welfare6_parallel import welfare6_mc


def run_hark_scenario(eco, shock_type, num_exp, num_iter, cutoff,
                       capture_init=False):
    """Run HARK AD for one scenario, optionally capturing t=0 init panels.

    Returns (result_dict, optional init_panels list)."""
    eco_h = deepcopy(eco)
    eco_h.switch_shock_type(shock_type)
    captured_init = []

    if capture_init:
        orig_run = eco_h.run_experiment
        def logged_run(*args, **kwargs):
            r = orig_run(*args, **kwargs)
            cohort_panels = []
            for ThisType in eco_h.agents:
                cohort_panels.append({
                    'aNrm0': np.asarray(ThisType.history['aNrm'][0]),
                    'pLvl0': np.asarray(ThisType.history['pLvl'][0]),
                    'micro0': (np.asarray(ThisType.shock_history['Mrkv'][0])
                                % ThisType.num_base_MrkvStates).astype(np.int32),
                })
            captured_init[:] = cohort_panels
            return r
        eco_h.run_experiment = logged_run

    # Different solvers per scenario
    if shock_type == 'recession':
        eco_h.solve_ad_recession(num_max_iterations=num_iter,
                                  convergence_cutoff=cutoff, name=shock_type)
    elif shock_type == 'recessionCheck':
        eco_h.solve_ad_check_recession(num_max_iterations=num_iter,
                                        convergence_cutoff=cutoff, name=shock_type)

    eco_h.restore_ADsolution(name=shock_type)
    rec_dict = {
        'shock_type': shock_type,
        'UpdatePrb': 1.0,
        'Splurge': eco_h.agents[0].Splurge,
        'EconomyMrkv_init': list(np.arange(1, num_exp + 1) * 2 + 1) + [1]*12 + [0]*20,
    }
    result = eco_h.run_experiment(**rec_dict, Full_Output=True)
    return result, captured_init


def main():
    print("=== Welfare-6 cell check_rec_AD end-to-end: JAX vs HARK ===", flush=True)
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    base_result = run_base(ctx)
    num_exp = ctx['num_experiment_periods']
    act_T = ctx['act_T']
    Rfree = ctx['Rfree']
    CRRA = ctx['CRRA']

    # HARK references
    print("\n[HARK] recession_AD ...", flush=True)
    t0 = time.time()
    hark_recession, init_panels_recession = run_hark_scenario(
        AggEco, 'recession', num_exp,
        ctx['num_max_iterations_solvingAD'], ctx['convergence_tol_solvingAD'],
        capture_init=True)
    print(f"  HARK recession AD: {time.time()-t0:.1f}s", flush=True)

    print("\n[HARK] recessionCheck_AD ...", flush=True)
    t0 = time.time()
    hark_check, init_panels_check = run_hark_scenario(
        AggEco, 'recessionCheck', num_exp,
        ctx['num_max_iterations_solvingAD'], ctx['convergence_tol_solvingAD'],
        capture_init=True)
    print(f"  HARK recessionCheck AD: {time.time()-t0:.1f}s", flush=True)

    # HARK welfare cell
    hark_cell = welfare6_mc(hark_check, hark_recession, base_result,
                              act_T, Rfree, CRRA)
    print(f"\nHARK check_rec_AD welfare cell: {hark_cell:.6f}")

    # JAX scenarios
    init_p_rec = [(c['aNrm0'].astype(np.float32),
                   c['pLvl0'].astype(np.float32),
                   c['micro0']) for c in init_panels_recession]
    init_p_chk = [(c['aNrm0'].astype(np.float32),
                   c['pLvl0'].astype(np.float32),
                   c['micro0']) for c in init_panels_check]

    print("\n[JAX] recession_AD ...", flush=True)
    eco_j = deepcopy(AggEco)
    t0 = time.time()
    jax_rec = solve_ad_recession_jax_multicohort(
        eco_j, eco_j.base_AggCons,
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        shock_type='recession', init_panels=init_p_rec,
        seeds=(0, 1, 2, 3), verbose=False)
    print(f"  JAX recession AD: {time.time()-t0:.1f}s, Cratio[0]={jax_rec['final_Cratio_hist'][0]:.4f}",
          flush=True)

    print("\n[JAX] recessionCheck_AD ...", flush=True)
    eco_j2 = deepcopy(AggEco)
    t0 = time.time()
    jax_chk = solve_ad_recession_jax_multicohort(
        eco_j2, eco_j2.base_AggCons,
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        shock_type='recessionCheck', init_panels=init_p_chk,
        seeds=(0, 1, 2, 3), verbose=False)
    print(f"  JAX recessionCheck AD: {time.time()-t0:.1f}s, Cratio[0]={jax_chk['final_Cratio_hist'][0]:.4f}",
          flush=True)

    # Build JAX result dicts in the shape welfare6_mc expects
    def jax_to_result(jax_res):
        return {
            'AggCons': jax_res['final_AggCons'],
            'AggIncome': jax_res['final_AggIncome'],
            'cLvl_all_splurge': jax_res['final_cLvl_all_splurge'],
        }
    jax_chk_r = jax_to_result(jax_chk)
    jax_rec_r = jax_to_result(jax_rec)

    # JAX welfare cell (using HARK base panel — base is non-AD and same in both)
    jax_cell = welfare6_mc(jax_chk_r, jax_rec_r, base_result,
                            act_T, Rfree, CRRA)
    print(f"\n=== Welfare cell comparison ===")
    print(f"HARK check_rec_AD: {hark_cell:.6f}")
    print(f"JAX  check_rec_AD: {jax_cell:.6f}")
    print(f"Ratio JAX/HARK: {jax_cell/hark_cell:.4f}")
    print(f"Abs diff: {jax_cell-hark_cell:+.4f}, rel diff: {(jax_cell-hark_cell)/hark_cell*100:+.2f}%")

    # Diagnose: compare panel statistics
    print(f"\n=== Panel comparison (cLvl_all_splurge) ===")
    h_chk = hark_check['cLvl_all_splurge']
    j_chk = jax_chk_r['cLvl_all_splurge']
    h_rec = hark_recession['cLvl_all_splurge']
    j_rec = jax_rec_r['cLvl_all_splurge']
    print(f"HARK check panel: shape={h_chk.shape}, mean[0]={h_chk[0].mean():.3f}, mean[5]={h_chk[5].mean():.3f}")
    print(f"JAX  check panel: shape={j_chk.shape}, mean[0]={j_chk[0].mean():.3f}, mean[5]={j_chk[5].mean():.3f}")
    print(f"HARK rec panel: shape={h_rec.shape}, mean[0]={h_rec[0].mean():.3f}, mean[5]={h_rec[5].mean():.3f}")
    print(f"JAX  rec panel: shape={j_rec.shape}, mean[0]={j_rec[0].mean():.3f}, mean[5]={j_rec[5].mean():.3f}")
    print(f"Diff (check-rec) per-agent felicity at t=0:")
    print(f"  HARK: mean=(c_chk-c_rec)/c_base^2 at t=0: {((-1/h_chk[0]) - (-1/h_rec[0])).mean()*base_result['cLvl_all_splurge'][0].mean()**2:.4f}")
    print(f"  JAX:  mean=(c_chk-c_rec)/c_base^2 at t=0: {((-1/j_chk[0]) - (-1/j_rec[0])).mean()*base_result['cLvl_all_splurge'][0].mean()**2:.4f}")


if __name__ == '__main__':
    main()
