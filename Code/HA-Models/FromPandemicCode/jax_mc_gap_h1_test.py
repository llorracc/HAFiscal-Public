"""H1 test: divide pLvl0 by G before passing to JAX (correct off-by-one growth).

If H1 is the dominant source of the 6% welfare gap, this should close it
or substantially reduce it.
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
from jax_mc_ad_multicohort import (solve_ad_recession_jax_multicohort,
                                    _build_init_panels_via_hark_quick_sim)
from run_welfare6_parallel import welfare6_mc


def run_hark_scenario(eco, shock_type, num_exp, num_iter, cutoff):
    eco_h = deepcopy(eco)
    eco_h.switch_shock_type(shock_type)
    if shock_type == 'recession':
        eco_h.solve_ad_recession(num_max_iterations=num_iter,
                                  convergence_cutoff=cutoff, name=shock_type)
    elif shock_type == 'recessionCheck':
        eco_h.solve_ad_check_recession(num_max_iterations=num_iter,
                                        convergence_cutoff=cutoff, name=shock_type)
    eco_h.restore_ADsolution(name=shock_type)
    rec_dict = {
        'shock_type': shock_type, 'UpdatePrb': 1.0,
        'Splurge': eco_h.agents[0].Splurge,
        'EconomyMrkv_init': list(np.arange(1, num_exp + 1) * 2 + 1) + [1]*12 + [0]*20,
    }
    return eco_h.run_experiment(**rec_dict, Full_Output=True)


def main():
    print("=== H1 test: divide pLvl0 by G to correct off-by-one growth ===")
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    base_result = run_base(ctx)
    num_exp = ctx['num_experiment_periods']

    print("\n[HARK] recession + recessionCheck AD ...", flush=True)
    hark_rec = run_hark_scenario(AggEco, 'recession', num_exp,
                                  ctx['num_max_iterations_solvingAD'],
                                  ctx['convergence_tol_solvingAD'])
    hark_chk = run_hark_scenario(AggEco, 'recessionCheck', num_exp,
                                  ctx['num_max_iterations_solvingAD'],
                                  ctx['convergence_tol_solvingAD'])
    hark_cell = welfare6_mc(hark_chk, hark_rec, base_result,
                              ctx['act_T'], ctx['Rfree'], ctx['CRRA'])
    print(f"HARK check_rec_AD welfare cell: {hark_cell:.6f}")

    # Build init_panels with pLvl divided by G per cohort
    def make_corrected_init(eco_template, shock_type):
        init_panels_raw = _build_init_panels_via_hark_quick_sim(
            eco_template, shock_type, verbose=False)
        eco_ref = deepcopy(eco_template)
        eco_ref.switch_shock_type(shock_type)
        corrected = []
        for c_idx, (a0, p0, m0) in enumerate(init_panels_raw):
            # PermGroFac[0] is a list/array of per-state G values. For employed (Mrkv=0),
            # G is PermGroFac[0][0]. We approximate by using the employed G (most agents).
            G_employed = float(eco_ref.agents[c_idx].PermGroFac[0][0])
            p0_corrected = (p0 / G_employed).astype(np.float32)
            corrected.append((a0, p0_corrected, m0))
        print(f"  G correction factors: {[float(eco_ref.agents[c].PermGroFac[0][0]) for c in range(len(eco_ref.agents))]}")
        return corrected

    print("\n[JAX-autoinit-H1] building corrected init (pLvl /= G) ...", flush=True)
    init_p_rec = make_corrected_init(AggEco, 'recession')
    init_p_chk = make_corrected_init(AggEco, 'recessionCheck')

    print("\n[JAX-autoinit-H1] recession_AD ...", flush=True)
    eco_j = deepcopy(AggEco)
    jax_rec = solve_ad_recession_jax_multicohort(
        eco_j, eco_j.base_AggCons,
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        shock_type='recession', init_panels=init_p_rec,
        seeds=(0, 1, 2, 3), verbose=False)
    print(f"  JAX recession AD: Cratio[0]={jax_rec['final_Cratio_hist'][0]:.4f}")

    print("\n[JAX-autoinit-H1] recessionCheck_AD ...", flush=True)
    eco_j2 = deepcopy(AggEco)
    jax_chk = solve_ad_recession_jax_multicohort(
        eco_j2, eco_j2.base_AggCons,
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        shock_type='recessionCheck', init_panels=init_p_chk,
        seeds=(0, 1, 2, 3), verbose=False)
    print(f"  JAX recessionCheck AD: Cratio[0]={jax_chk['final_Cratio_hist'][0]:.4f}")

    jax_cell = welfare6_mc(
        {'AggCons': jax_chk['final_AggCons'],
         'AggIncome': jax_chk['final_AggIncome'],
         'cLvl_all_splurge': jax_chk['final_cLvl_all_splurge']},
        {'AggCons': jax_rec['final_AggCons'],
         'AggIncome': jax_rec['final_AggIncome'],
         'cLvl_all_splurge': jax_rec['final_cLvl_all_splurge']},
        base_result, ctx['act_T'], ctx['Rfree'], ctx['CRRA'])

    print(f"\n=== H1 result (pLvl0 /= G) ===")
    print(f"HARK welfare cell: {hark_cell:.6f}")
    print(f"JAX-H1 welfare cell: {jax_cell:.6f}")
    print(f"Gap H1: {(jax_cell-hark_cell)/hark_cell*100:+.2f}%")
    print(f"PRIOR (no H1): +6.40%")
    if abs((jax_cell-hark_cell)/hark_cell*100) < 1.5:
        print("✓ H1 closes the gap")
    elif abs((jax_cell-hark_cell)/hark_cell*100) < 3.0:
        print("⚠ H1 partially closes")
    else:
        print("✗ H1 does not close the gap")


if __name__ == '__main__':
    main()
