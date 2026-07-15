"""Test #6: validate auto-init closes the JAX-vs-HARK Cratio gap.

HS_Only, recession scenario. Compares:
  - HARK reference (independent MC, full HARK)
  - JAX with HARK's exact init_panels (should match closely — was baseline)
  - JAX with auto-init from agent._base + spike (this is the #6 fix)
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
    print("=== Auto-init #6 validation (HS_Only, recession) ===", flush=True)
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    base_mc = run_base(ctx)  # saves _base state on each agent
    base_AggCons = np.asarray(AggEco.base_AggCons)

    # === HARK reference: independent MC recession ===
    eco_h = deepcopy(AggEco)
    eco_h.switch_shock_type('recession')
    print("\n[HARK] recession AD ...", flush=True)
    t0 = time.time()
    eco_h.solve_ad_recession(
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        name='recession')
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
    print(f"HARK Cratio[:5]: {hark_cratio[:5]}")
    print(f"HARK wall: {time.time()-t0:.1f}s", flush=True)

    # === JAX with auto-init (the #6 fix) ===
    eco_j = deepcopy(AggEco)
    print("\n[JAX auto-init] recession AD ...", flush=True)
    t0 = time.time()
    res_auto = solve_ad_recession_jax_multicohort(
        eco_j, base_AggCons,
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        shock_type='recession',
        init_panels=None,  # ← triggers auto-init
        seeds=(0, 1, 2, 3),
        verbose=True)
    auto_cratio = np.asarray(res_auto['final_Cratio_hist'])
    print(f"JAX-auto Cratio[:5]: {auto_cratio[:5]}")
    print(f"JAX-auto wall: {time.time()-t0:.1f}s", flush=True)

    # === Compare ===
    n_act = num_exp + 12
    rel = (auto_cratio[:n_act] - hark_cratio[:n_act]) / hark_cratio[:n_act]
    print(f"\n[autoinit vs HARK] mean ratio = {np.mean(auto_cratio[:n_act])/np.mean(hark_cratio[:n_act]):.5f}")
    print(f"[autoinit vs HARK] max |rel diff| (first {n_act}) = {np.max(np.abs(rel)):.4f}")
    print(f"[autoinit vs HARK] Cratio[0] diff = {auto_cratio[0]-hark_cratio[0]:+.4f} ({100*(auto_cratio[0]/hark_cratio[0]-1):+.2f}%)")


if __name__ == '__main__':
    main()
