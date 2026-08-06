"""Tier-1 cascade: HS_Only check_rec_AD welfare cell with autoinit (#6 fix).

Same harness as jax_mc_welfare_check_test.py but JAX uses init_panels=None
(triggering the auto-init via HARK no-AD ref sim — the #6 fix).

Confirms the original 6% welfare-cell gap closes when autoinit is on.
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


def jax_to_result(jax_res):
    return {
        'AggCons': jax_res['final_AggCons'],
        'AggIncome': jax_res['final_AggIncome'],
        'cLvl_all_splurge': jax_res['final_cLvl_all_splurge'],
    }


def main():
    print("=== Tier-1: HS_Only check_rec_AD welfare cell, JAX-autoinit vs HARK ===",
          flush=True)
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
    hark_rec = run_hark_scenario(AggEco, 'recession', num_exp,
                                   ctx['num_max_iterations_solvingAD'],
                                   ctx['convergence_tol_solvingAD'])
    print(f"  HARK recession AD: {time.time()-t0:.1f}s", flush=True)

    print("\n[HARK] recessionCheck_AD ...", flush=True)
    t0 = time.time()
    hark_chk = run_hark_scenario(AggEco, 'recessionCheck', num_exp,
                                   ctx['num_max_iterations_solvingAD'],
                                   ctx['convergence_tol_solvingAD'])
    print(f"  HARK recessionCheck AD: {time.time()-t0:.1f}s", flush=True)

    hark_cell = welfare6_mc(hark_chk, hark_rec, base_result, act_T, Rfree, CRRA)
    print(f"\nHARK check_rec_AD welfare cell: {hark_cell:.6f}")

    # JAX with autoinit (init_panels=None — triggers HARK no-AD ref sim per scenario)
    print("\n[JAX-autoinit] recession_AD ...", flush=True)
    eco_j = deepcopy(AggEco)
    t0 = time.time()
    jax_rec = solve_ad_recession_jax_multicohort(
        eco_j, eco_j.base_AggCons,
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        shock_type='recession', init_panels=None,  # ← autoinit
        seeds=(0, 1, 2, 3), verbose=False)
    print(f"  JAX recession AD: {time.time()-t0:.1f}s, "
          f"Cratio[0]={jax_rec['final_Cratio_hist'][0]:.4f}", flush=True)

    print("\n[JAX-autoinit] recessionCheck_AD ...", flush=True)
    eco_j2 = deepcopy(AggEco)
    t0 = time.time()
    jax_chk = solve_ad_recession_jax_multicohort(
        eco_j2, eco_j2.base_AggCons,
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        shock_type='recessionCheck', init_panels=None,  # ← autoinit
        seeds=(0, 1, 2, 3), verbose=False)
    print(f"  JAX recessionCheck AD: {time.time()-t0:.1f}s, "
          f"Cratio[0]={jax_chk['final_Cratio_hist'][0]:.4f}", flush=True)

    jax_cell = welfare6_mc(jax_to_result(jax_chk), jax_to_result(jax_rec),
                            base_result, act_T, Rfree, CRRA)

    print(f"\n=== Welfare cell comparison (HS_Only check_rec_AD) ===")
    print(f"HARK : {hark_cell:.6f}")
    print(f"JAX-A: {jax_cell:.6f}")
    print(f"Ratio JAX/HARK: {jax_cell/hark_cell:.4f}")
    rel = (jax_cell - hark_cell) / hark_cell * 100
    print(f"Abs diff: {jax_cell-hark_cell:+.4f}, rel diff: {rel:+.2f}%")
    print(f"\nPRIOR (with init_panels supplied from HARK): 6.3% gap")
    print(f"NEW   (with autoinit fix #6):                  {rel:+.2f}% gap")
    if abs(rel) < 1.5:
        print("✓ Gap closed (within 1.5% — MC noise at N=10000)")
    elif abs(rel) < 3.0:
        print(f"⚠ Improved but still {abs(rel):.1f}% > MC noise; investigate")
    else:
        print(f"✗ Gap NOT closed — still {abs(rel):.1f}% off")


if __name__ == '__main__':
    main()
