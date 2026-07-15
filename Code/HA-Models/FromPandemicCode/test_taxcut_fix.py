"""
Test the proposed fix for the TaxCut TM bug:
  Use the EXPERIMENT chain's cFunc (88-state TaxCut solve) for the baseline,
  not the BASE chain's cFunc (4-state base solve).

Implementation: build baseline_tm_data from the switched economy, then drive
it with EconomyMrkv_init = [0] * act_T (all-macro-0 path = no recession,
no tax cut, plain stationary). Subtract from the real TaxCut experiment.

If the fix is correct, the resulting TM-Q multiplier should drop by ~1.3%
relative to the buggy version, matching the MC-P seed mean.
"""
import sys, os
import numpy as np
from copy import deepcopy

_THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS)
sys.path.insert(0, os.path.dirname(_THIS))

from parity_solo_pol_linear import build_solo_pol_economy, mc_multiplier
from AggFiscalModel import DualAggFiscalType
from tm_methods import (
    calculate_NPV,
    compute_baseline_tm_data,
    run_experiment_tm,
    run_experiment_tm_nonbase,
)


def tm_q_buggy(eco_ref, meta, mCount):
    """Original buggy path: baseline via base chain, exp via TaxCut chain.
    Returns (multiplier, NPV(dC), NPV(dY))."""
    bl = compute_baseline_tm_data(eco_ref, mCount=mCount, neutral_measure=True, verbose=False)
    base = run_experiment_tm(eco_ref, "base", mCount=mCount, neutral_measure=True, verbose=False)
    eco = deepcopy(eco_ref)
    eco.switch_shock_type("TaxCut")
    eco.solve()
    EM_init = list(np.arange(1, meta["num_exp"] + 1) * 2) + [0] * 20
    exp = run_experiment_tm_nonbase(eco, "TaxCut", EM_init, bl,
                                    mCount=mCount, neutral_measure=True, verbose=False)
    Rfree = eco_ref.agents[0].Rfree[0]
    act_T = eco_ref.act_T
    dc = np.array(exp["AggCons"]) - np.array(base["AggCons"])
    dy = np.array(exp["AggIncome"]) - np.array(base["AggIncome"])
    npv_c = calculate_NPV(dc, act_T, Rfree)[-1]
    npv_y = calculate_NPV(dy, act_T, Rfree)[-1]
    return npv_c / npv_y, npv_c, npv_y


def tm_q_fixed(eco_ref, meta, mCount):
    """Fixed path: baseline ALSO via propagate_experiment_tm with EM=[0]*act_T,
    so it uses the same half-step + propagation pipeline as the experiment.
    Distributional drift cancels in dC = exp - base."""
    # Build baseline on UNSWITCHED economy (4-state ergodic, base_aPol from base cFunc).
    bl = compute_baseline_tm_data(eco_ref, mCount=mCount, neutral_measure=True, verbose=False)
    eco = deepcopy(eco_ref)
    eco.switch_shock_type("TaxCut")
    eco.solve()
    act_T = eco.act_T
    # Baseline: propagate through TaxCut-chain agent but along the all-macro-0
    # path (no policy applied; cFunc[0..3] used throughout).
    EM_zero = [0] * act_T
    base = run_experiment_tm_nonbase(eco, "TaxCut", EM_zero, bl,
                                     mCount=mCount, neutral_measure=True, verbose=False)
    EM_init = list(np.arange(1, meta["num_exp"] + 1) * 2) + [0] * 20
    exp = run_experiment_tm_nonbase(eco, "TaxCut", EM_init, bl,
                                    mCount=mCount, neutral_measure=True, verbose=False)
    Rfree = eco.agents[0].Rfree[0]
    dc = np.array(exp["AggCons"]) - np.array(base["AggCons"])
    dy = np.array(exp["AggIncome"]) - np.array(base["AggIncome"])
    return calculate_NPV(dc, act_T, Rfree)[-1] / calculate_NPV(dy, act_T, Rfree)[-1]


def main():
    eco_ref, meta = build_solo_pol_economy(DualAggFiscalType, 1, 0)
    mCount = 100

    print("=== TM-Q components ===")
    mult_tm, npvc_tm, npvy_tm = tm_q_buggy(eco_ref, meta, mCount)
    print(f"  multiplier = {mult_tm:.6f}")
    print(f"  NPV(dC)    = {npvc_tm:.6f}")
    print(f"  NPV(dY)    = {npvy_tm:.6f}")

    print("\n=== MC-P components (5 seeds, N=8000) ===")
    mc_multiplier._return_components = True
    u = getattr(eco_ref.agents[0], 'Urate_normal', 0.044)
    from tm_methods import compute_pLvl_distribution
    g, p = compute_pLvl_distribution(eco_ref.agents[0], n_points=200, unemployment_rate=u)
    tm_Ep = float(np.dot(p, g))
    cs, ys = [], []
    for s in range(5):
        c, y = mc_multiplier(eco_ref, "TaxCut", meta, s * 100, 8000, True, tm_Ep)
        cs.append(c); ys.append(y)
        print(f"  seed {s}: NPV(dC)={c:.6f}  NPV(dY)={y:.6f}  mult={c/y:.6f}")
    mean_c = float(np.mean(cs))
    mean_y = float(np.mean(ys))
    se_c = float(np.std(cs)/np.sqrt(5))
    se_y = float(np.std(ys)/np.sqrt(5))
    print(f"\n  mean NPV(dC) = {mean_c:.6f} ± {se_c:.6f}")
    print(f"  mean NPV(dY) = {mean_y:.6f} ± {se_y:.6f}")
    print(f"  mean mult    = {mean_c/mean_y:.6f}")
    print(f"\n  TM dC vs MC dC : diff {npvc_tm - mean_c:+.6f}  "
          f"({(npvc_tm-mean_c)/mean_c*100:+.3f}%)")
    print(f"  TM dY vs MC dY : diff {npvy_tm - mean_y:+.6f}  "
          f"({(npvy_tm-mean_y)/mean_y*100:+.3f}%)")


if __name__ == "__main__":
    main()
