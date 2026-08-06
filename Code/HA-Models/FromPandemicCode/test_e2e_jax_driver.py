"""
Phase B end-to-end smoke test: compute_joint_welfare5d_jax vs
compute_joint_welfare5d (numpy) at HS_Only A=30 single duration.

Validates that the JAX driver produces same headline numbers as
the existing numpy driver, with paper-precision tolerance.
"""
from __future__ import annotations
import os, sys, time
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d import compute_joint_welfare5d
from welfare6_tm_joint5d_jax_kernel import compute_joint_welfare5d_jax
from tm_methods import compute_baseline_tm_data, calculate_NPV


def _build_econ_mrkv_path(act_T, num_experiment_periods, dur):
    path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T + 5)
    path = path[:act_T]
    for t in range(min(dur, len(path))):
        path[t] = path[t] + 1
    return path


def main():
    aCount = int(os.environ.get('JOINT5D_ACOUNT', 30))
    dur = int(os.environ.get('VALIDATE_DUR', 1))
    M_grid = int(os.environ.get('M_GRID', 500))
    print(f"{'='*70}\nE2E JAX driver vs numpy (A={aCount}, dur={dur}, M={M_grid})\n{'='*70}")

    t0 = time.time()
    ctx = build_and_solve('HS_Only')
    AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
    AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
    AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
    for ag in AggEco_pol.agents: ag.tm_a_indexed = True
    for ag in AggEco_none.agents: ag.tm_a_indexed = True
    for ag in AggEco_base.agents: ag.tm_a_indexed = True
    bd_list = compute_baseline_tm_data(AggEco_base, dist_aGrid_count=aCount, neutral_measure=True)
    print(f"  setup wall: {time.time() - t0:.1f}s")

    act_T = ctx['act_T']
    nep = ctx['num_experiment_periods']
    path = _build_econ_mrkv_path(act_T, nep, dur)

    print(f"\n  Running NUMPY driver...")
    t1 = time.time()
    np_res = compute_joint_welfare5d(
        AggEco_pol.agents[0], AggEco_none.agents[0], AggEco_base.agents[0],
        bd_list[0], EconomyMrkv_path_pn=path, act_T=act_T, verbose=False)
    np_wall = time.time() - t1
    print(f"  NUMPY wall: {np_wall:.2f}s")

    print(f"\n  Running JAX driver (first call includes per-period JIT compiles)...")
    t1 = time.time()
    jax_res = compute_joint_welfare5d_jax(
        AggEco_pol.agents[0], AggEco_none.agents[0], AggEco_base.agents[0],
        bd_list[0], EconomyMrkv_path_pn=path, act_T=act_T, M_grid=M_grid, verbose=True)
    jax_wall = time.time() - t1
    print(f"  JAX wall (cold): {jax_wall:.2f}s")

    print(f"\n  Running JAX driver again (warm)...")
    t1 = time.time()
    jax_res2 = compute_joint_welfare5d_jax(
        AggEco_pol.agents[0], AggEco_none.agents[0], AggEco_base.agents[0],
        bd_list[0], EconomyMrkv_path_pn=path, act_T=act_T, M_grid=M_grid, verbose=False)
    jax_wall_warm = time.time() - t1
    print(f"  JAX wall (warm): {jax_wall_warm:.2f}s")
    print(f"  speedup vs numpy: {np_wall/jax_wall_warm:.2f}x")

    print(f"\n=== Comparison ===")
    for k in ['welfare_num_series', 'AggInc_pol_series', 'AggInc_none_series',
              'AggCons_pol_series', 'AggCons_none_series', 'pLvl_factor_series']:
        v_np = np_res[k]
        v_jax = jax_res[k]
        max_diff = float(np.abs(v_np - v_jax).max())
        denom = max(float(np.abs(v_np).max()), 1e-12)
        rel = max_diff / denom
        print(f"  {k:<28} max|diff|={max_diff:.3e} rel|diff|={rel:.3e}")

    # Headline: NPVs and the welfare ratio
    Rfree = float(np.asarray(AggEco_pol.agents[0].Rfree).flatten()[0])
    def _npv(s):
        v = calculate_NPV(s, act_T, Rfree)
        return float(v[-1]) if hasattr(v, '__len__') else float(v)
    npv_w_np = _npv(np_res['welfare_num_series'])
    npv_w_jax = _npv(jax_res['welfare_num_series'])
    npv_addinc_np = _npv(np_res['AggInc_pol_series'] - np_res['AggInc_none_series'])
    npv_addinc_jax = _npv(jax_res['AggInc_pol_series'] - jax_res['AggInc_none_series'])
    npv_addcons_np = _npv(np_res['AggCons_pol_series'] - np_res['AggCons_none_series'])
    npv_addcons_jax = _npv(jax_res['AggCons_pol_series'] - jax_res['AggCons_none_series'])

    print(f"\n=== Headline ===")
    print(f"  NPV(welfare_num): numpy={npv_w_np:.4e}, jax={npv_w_jax:.4e}, rel={abs(npv_w_jax-npv_w_np)/(abs(npv_w_np)+1e-12):.3e}")
    if abs(npv_addinc_np) > 1e-10 and abs(npv_addinc_jax) > 1e-10:
        ui_np = npv_w_np / npv_addinc_np + (npv_addinc_np - npv_addcons_np) / npv_addinc_np
        ui_jax = npv_w_jax / npv_addinc_jax + (npv_addinc_jax - npv_addcons_jax) / npv_addinc_jax
        print(f"  ui_rec (5D-self denom):")
        print(f"    numpy = {ui_np:.4f}")
        print(f"    jax   = {ui_jax:.4f}")
        print(f"    rel diff = {abs(ui_jax-ui_np)/(abs(ui_np)+1e-12):.3e}")


if __name__ == '__main__':
    main()
