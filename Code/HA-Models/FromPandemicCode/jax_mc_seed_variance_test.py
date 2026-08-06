"""Diagnostic: is the 6% welfare gap pure MC realization variance, or systematic?

Run HARK once (deterministic baseline) and JAX with 4 different seed sets:
  seeds=(0,1,2,3), (10,11,12,13), (20,21,22,23), (30,31,32,33)

Compute welfare cell per JAX run. If welfare cells vary by ~6% across seed sets,
the gap is MC noise. If they cluster within ~1% but all ~6% above HARK, it's
systematic.
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


def run_hark(eco, shock_type, num_exp, num_iter, cutoff):
    eco_h = deepcopy(eco)
    eco_h.switch_shock_type(shock_type)
    if shock_type == 'recession':
        eco_h.solve_ad_recession(num_max_iterations=num_iter,
                                  convergence_cutoff=cutoff, name=shock_type)
    elif shock_type == 'recessionCheck':
        eco_h.solve_ad_check_recession(num_max_iterations=num_iter,
                                        convergence_cutoff=cutoff, name=shock_type)
    eco_h.restore_ADsolution(name=shock_type)
    rec_dict = {'shock_type': shock_type, 'UpdatePrb': 1.0,
                'Splurge': eco_h.agents[0].Splurge,
                'EconomyMrkv_init': list(np.arange(1, num_exp+1)*2+1) + [1]*12 + [0]*20}
    return eco_h.run_experiment(**rec_dict, Full_Output=True)


def jax_run(eco_template, base_AggCons, shock_type, seeds, num_iter, cutoff):
    eco_j = deepcopy(eco_template)
    res = solve_ad_recession_jax_multicohort(
        eco_j, base_AggCons,
        num_max_iterations=num_iter, convergence_cutoff=cutoff,
        shock_type=shock_type, init_panels=None,
        seeds=seeds, verbose=False)
    return res


def main():
    print("=== Seed-variance test: HS_Only check_rec_AD welfare cell ===")
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    base_result = run_base(ctx)
    num_exp = ctx['num_experiment_periods']
    num_iter = ctx['num_max_iterations_solvingAD']
    cutoff = ctx['convergence_tol_solvingAD']

    print("\n[HARK] computing reference ...", flush=True)
    hark_rec = run_hark(AggEco, 'recession', num_exp, num_iter, cutoff)
    hark_chk = run_hark(AggEco, 'recessionCheck', num_exp, num_iter, cutoff)
    hark_cell = welfare6_mc(hark_chk, hark_rec, base_result, ctx['act_T'],
                              ctx['Rfree'], ctx['CRRA'])
    print(f"HARK welfare cell: {hark_cell:.6f}")

    seed_sets = [
        (0, 1, 2, 3),
        (10, 11, 12, 13),
        (20, 21, 22, 23),
        (30, 31, 32, 33),
    ]
    results = []
    for seeds in seed_sets:
        print(f"\n[JAX seeds={seeds}] ...", flush=True)
        t0 = time.time()
        rec = jax_run(AggEco, AggEco.base_AggCons, 'recession', seeds, num_iter, cutoff)
        chk = jax_run(AggEco, AggEco.base_AggCons, 'recessionCheck', seeds, num_iter, cutoff)
        cell = welfare6_mc(
            {'AggCons': chk['final_AggCons'],
             'AggIncome': chk['final_AggIncome'],
             'cLvl_all_splurge': chk['final_cLvl_all_splurge']},
            {'AggCons': rec['final_AggCons'],
             'AggIncome': rec['final_AggIncome'],
             'cLvl_all_splurge': rec['final_cLvl_all_splurge']},
            base_result, ctx['act_T'], ctx['Rfree'], ctx['CRRA'])
        print(f"  wall={time.time()-t0:.1f}s, welfare cell={cell:.6f}, "
              f"gap vs HARK = {(cell-hark_cell)/hark_cell*100:+.2f}%")
        results.append(cell)

    cells = np.array(results)
    print(f"\n=== Summary ===")
    print(f"HARK:    {hark_cell:.6f}")
    for i, s in enumerate(seed_sets):
        print(f"JAX{s}: {cells[i]:.6f}  ({(cells[i]-hark_cell)/hark_cell*100:+.2f}% vs HARK)")
    print(f"JAX mean: {cells.mean():.6f}")
    print(f"JAX std:  {cells.std():.6f}")
    print(f"JAX SE (4 batches): {cells.std()/np.sqrt(len(cells)):.6f}")
    print(f"JAX/HARK relative SE: {cells.std()/np.sqrt(len(cells))/hark_cell*100:.2f}%")
    z_score = (cells.mean() - hark_cell) / (cells.std() / np.sqrt(len(cells)))
    print(f"Z-score (mean-HARK)/(SE): {z_score:.2f}")
    if abs(z_score) < 2:
        print("✓ HARK within 2σ of JAX mean → gap is MC noise")
    else:
        print(f"✗ HARK is {abs(z_score):.1f}σ from JAX mean → systematic bias")


if __name__ == '__main__':
    main()
