"""HS_Only recessionCheck under AD: JAX vs HARK AggCons comparison.

Validates that the JAX AD policy kernel handles Check-stimulus per HARK.
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


def main():
    print("=== HS_Only recessionCheck_AD: JAX vs HARK ===", flush=True)
    t0 = time.time()
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    _ = run_base(ctx)
    print(f"build/base: {time.time()-t0:.1f}s", flush=True)

    # HARK reference
    print("\n[HARK] solve_ad_check_recession ...", flush=True)
    eco_h = deepcopy(AggEco)
    eco_h.switch_shock_type('recessionCheck')  # expand CFunc to recession size
    t0 = time.time()
    eco_h.solve_ad_check_recession(
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        name='recessionCheck')
    print(f"HARK AD: {time.time()-t0:.1f}s", flush=True)

    eco_h.switch_shock_type('recessionCheck')
    eco_h.restore_ADsolution(name='recessionCheck')
    # Run one experiment to get AggCons
    num_exp = eco_h.num_experiment_periods
    rec_dict = {
        'shock_type': 'recessionCheck',
        'UpdatePrb': 1.0,
        'Splurge': eco_h.agents[0].Splurge,
        'EconomyMrkv_init': list(np.arange(1, num_exp + 1) * 2 + 1) + [1]*12 + [0]*20,
    }
    h_res = eco_h.run_experiment(**rec_dict)
    hark_aggcons = np.asarray(h_res['AggCons'])
    hark_cratio = np.asarray(h_res['Cratio_hist'])
    print(f"HARK Cratio[:8]: {hark_cratio[:8]}")
    print(f"HARK AggCons[0]: {hark_aggcons[0]:.4f}", flush=True)

    # JAX equivalent via solve_ad_recession_jax_multicohort with shock_type='recessionCheck'
    print("\n[JAX] solve_ad_recession_jax_multicohort(shock_type=recessionCheck) ...", flush=True)
    eco_j = deepcopy(AggEco)
    t0 = time.time()
    jax_res = solve_ad_recession_jax_multicohort(
        eco_j, eco_j.base_AggCons,
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        shock_type='recessionCheck',
        seeds=(0, 1, 2, 3),
        verbose=True)
    print(f"JAX AD: {time.time()-t0:.1f}s", flush=True)

    jax_cratio = jax_res['final_Cratio_hist']
    print(f"\nJAX Cratio[:8]: {jax_cratio[:8]}")
    print(f"HARK Cratio[:8]: {hark_cratio[:8]}")
    n_act = num_exp + 12
    rel = (jax_cratio[:n_act] - hark_cratio[:n_act]) / hark_cratio[:n_act]
    print(f"Mean ratio (first {n_act}): {np.mean(jax_cratio[:n_act])/np.mean(hark_cratio[:n_act]):.6f}")
    print(f"Max |rel diff|: {np.max(np.abs(rel)):.4f}, mean diff: {np.mean(rel):+.4f}")


if __name__ == '__main__':
    main()
