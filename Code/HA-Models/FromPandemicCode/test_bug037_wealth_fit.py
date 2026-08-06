"""
Wealth-fit verification under BUG-037 fix.

The Step 2 estimator (`estim_phase2_tm_a.py`) targets:
  - medianLWPI: median liquid-wealth/permanent-income ratio per cohort
  - LorenzPts: Lorenz shares at percentiles 0.2, 0.4, 0.6, 0.8

These are computed on aNrm (normalized assets). Under the BUG-037 fix:
  - PermGroFacAgg=1.00455 (was 1.0): does NOT enter the aNrm chain
    dynamics for survivors — agents' aNrm chain uses G_g only.
  - pLogInitMean changes from group-specific to common: but newborns
    enter at aNrm=0 regardless, so this doesn't affect the aNrm
    distribution either.
  - pLogInitStd (group-specific σ_g) — unchanged.

Hypothesis: wealth fit is BIT-IDENTICAL pre vs post BUG-037 fix.

This script computes the Step 2 wealth-fit metrics under the production
calibration (β = 0.72/0.91/0.98) on the post-BUG-037-fix branch and
compares to the SCF targets. If the fit looks similar to the
pre-fix Apr-18 calibration distances (recorded in
Code/HA-Models/Results/DiscFacEstim_*.txt), the fix doesn't disturb
Step 2 estimation.

(BUG-037 was later superseded by BUG-038 — the T_age-cap restoration;
kept as a historical diagnostic.)
"""
import os
import sys
import time
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['test_bug037_wealth_fit']

from copy import deepcopy
from HARK.distributions import DiscreteDistribution
from HARK.utilities import get_percentiles, get_lorenz_shares
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
import EstimParameters as ep
from EstimParameters import (
    data_LorenzPts, data_medianLWPI, data_EducShares,
    pLogInitMean_avg, PermGroFacAgg, GICmaxBetas, theGICfactor,
)
from tm_methods import (
    build_tm_agg_fiscal_a,
    find_ergodic_distribution,
)


def banner(t):
    print(f"\n{'='*78}\n{t}\n{'='*78}")


def build_solved_agent(edType, beta, init_dict, init_AD, UBspell):
    agent = AggFiscalType(**init_dict)
    agent.cycles = 0
    agent.DiscFac = float(beta)
    eco = AggregateDemandEconomy(**init_AD)
    agent.get_economy_data(eco)
    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([agent.IncUnemp])])
    IncShkDstn_unemp_nb = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]),
                          np.array([agent.IncUnempNoBenefits])])
    agent.IncShkDstn[0].seed = 763607781
    agent.IncShkDstn[0].reset()
    agent.IncShkDstn = [
        [agent.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell
        + [IncShkDstn_unemp_nb]]
    agent.IncShkDstn_base = agent.IncShkDstn
    eco.agents = [agent]
    eco.solve()
    return eco.agents[0]


def compute_wealth_fit(agent, educ_type, aCount=100):
    """Compute medianLWPI and Lorenz shares per Step 2 estimator's logic."""
    tm_data = build_tm_agg_fiscal_a(agent, aCount=aCount)
    ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
    dist_aGrid = tm_data['dist_aGrid']
    J = agent.MrkvArray[0].shape[0]
    A = len(dist_aGrid)
    erg = np.asarray(ergodic).reshape(J, A)
    a_vals_list = []
    w_vals_list = []
    for j in range(J):
        dstn_j = erg[j, :]
        mask = dstn_j > 1e-15
        if np.any(mask):
            aNrm_vals = dist_aGrid[mask]
            weights = dstn_j[mask]
            a_vals_list.append(aNrm_vals)
            w_vals_list.append(weights)
    a_array = np.concatenate(a_vals_list)
    w_array = np.concatenate(w_vals_list)
    w_array /= np.sum(w_array)

    medianLWPI = float(100.0 * get_percentiles(
        a_array, weights=w_array, percentiles=[0.5])[0])
    LorenzPts = 100.0 * get_lorenz_shares(
        a_array, weights=w_array, percentiles=[0.2, 0.4, 0.6, 0.8])
    return {
        'medianLWPI': medianLWPI,
        'LorenzPts': np.asarray(LorenzPts),
        'data_medianLWPI': float(data_medianLWPI[educ_type]),
        'data_LorenzPts': data_LorenzPts[educ_type],
    }


def compute_wealth_fit_multibeta(agents, agent_weights, educ_type, aCount=100):
    """Same as compute_wealth_fit but aggregates a list of multi-β agents
    with given weights — matches the Step 2 estimator's multi-β logic
    (estim_phase2_tm_a.py:120-148)."""
    a_vals_list = []
    w_vals_list = []
    for agent, agent_w in zip(agents, agent_weights):
        tm_data = build_tm_agg_fiscal_a(agent, aCount=aCount)
        ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
        dist_aGrid = tm_data['dist_aGrid']
        J = agent.MrkvArray[0].shape[0]
        A = len(dist_aGrid)
        erg = np.asarray(ergodic).reshape(J, A)
        for j in range(J):
            dstn_j = erg[j, :]
            mask = dstn_j > 1e-15
            if np.any(mask):
                a_vals_list.append(dist_aGrid[mask])
                w_vals_list.append(dstn_j[mask] * agent_w)
    a_array = np.concatenate(a_vals_list)
    w_array = np.concatenate(w_vals_list)
    w_array /= np.sum(w_array)
    medianLWPI = float(100.0 * get_percentiles(
        a_array, weights=w_array, percentiles=[0.5])[0])
    LorenzPts = 100.0 * get_lorenz_shares(
        a_array, weights=w_array, percentiles=[0.2, 0.4, 0.6, 0.8])
    return {
        'medianLWPI': medianLWPI,
        'LorenzPts': np.asarray(LorenzPts),
        'data_medianLWPI': float(data_medianLWPI[educ_type]),
        'data_LorenzPts': data_LorenzPts[educ_type],
    }


def read_calibration_from_file():
    """Read the actually-calibrated β/nabla from saved estimation files."""
    res_dir = os.path.join(_HERE, '..', 'Results')
    main_path = os.path.join(res_dir, 'DiscFacEstim_CRRA_2.0_R_1.01.txt')
    with open(main_path) as f:
        lines = [l.strip() for l in f.readlines() if l.strip().startswith('{')]
    cal = {}
    for line in lines:
        d = eval(line)
        cal[d['EducationGroup']] = (d['beta'], d['nabla'])
    return cal


def discretize_uniform_beta(beta_center, nabla, n_atoms=7):
    """Match HAFiscal's _approx_equiprobable: equal-weight atoms uniform on
    [β-∇, β+∇], with mass at midpoints of equal-probability bins."""
    # Mid-points of n_atoms equal-prob bins on uniform [β-∇, β+∇]
    edges = np.linspace(0, 1, n_atoms + 1)
    mids = (edges[:-1] + edges[1:]) / 2
    atoms = beta_center - nabla + 2 * nabla * mids
    weights = np.ones(n_atoms) / n_atoms
    return atoms, weights


def main():
    banner("Wealth-fit verification under BUG-037 fix (Baseline 7-β per cohort)")
    print(f"  pLogInitMean_avg = {pLogInitMean_avg:.6f}")
    print(f"  PermGroFacAgg    = {PermGroFacAgg:.6f}")

    # Read calibrated values from saved file (actual production targets)
    try:
        cal = read_calibration_from_file()
        print(f"\n  CALIBRATED β / nabla (from DiscFacEstim_CRRA_2.0_R_1.01.txt):")
        for ed in [0, 1, 2]:
            print(f"    edType={ed}: β={cal[ed][0]:.4f}, nabla={cal[ed][1]:.4f}")
        use_calibrated = True
    except FileNotFoundError:
        print(f"\n  WARNING: calibration file not found; using Baseline defaults.")
        use_calibrated = False

    [init_dropout, init_highschool, init_college, init_AD, DiscFacDstns,
     DiscFacCount, _ACT, _bd, _nm, _ct, UBspell, _nb, _ed, _md, _np, _rc, _ui, _rui,
     _tc, _rtc, _ck, _rck] = return_parameters(
        Parametrization='Baseline', OutputFor='_Main.py')

    init_dicts = [init_dropout, init_highschool, init_college]
    names = ['Dropout', 'HighSchool', 'College']

    print(f"\n  DiscFacCount = {DiscFacCount} β-atoms per cohort")
    print(f"  data_medianLWPI = {data_medianLWPI}  (× 4 quarters; weighted median LW/PI in %)")
    print(f"  data_LorenzPts:")
    for ed, name in enumerate(names):
        print(f"    {name:<11} {data_LorenzPts[ed]}")

    banner("Step 2 wealth-fit metrics under BUG-037 fix calibration")
    total_distance_sq = 0.0
    for ed, (name, init_d) in enumerate(zip(names, init_dicts)):
        if use_calibrated:
            beta_center, nabla = cal[ed]
            beta_atoms, beta_pmv = discretize_uniform_beta(
                beta_center, nabla, n_atoms=DiscFacCount)
        else:
            DFD_g = DiscFacDstns[ed]
            beta_atoms = DFD_g.atoms[0]
            beta_pmv = DFD_g.pmv
        print(f"\n  {name}: β-atoms = {[f'{b:.4f}' for b in beta_atoms]}")
        print(f"    weights      = {[f'{w:.4f}' for w in beta_pmv]}")

        # Build solved agent for each β atom
        t0 = time.time()
        agents = []
        weights = []
        for ib, (beta, w) in enumerate(zip(beta_atoms, beta_pmv)):
            agent = build_solved_agent(ed, beta, init_d, init_AD, UBspell)
            agents.append(agent)
            weights.append(float(w))
        fit = compute_wealth_fit_multibeta(agents, weights, ed, aCount=100)
        dt = time.time() - t0

        d_med = fit['medianLWPI'] - fit['data_medianLWPI']
        d_lorenz = fit['LorenzPts'] - fit['data_LorenzPts']
        sumSq = d_med**2 + np.sum(d_lorenz**2)
        distance = np.sqrt(sumSq)
        total_distance_sq += distance**2

        print(f"    medianLWPI:  model={fit['medianLWPI']:>7.2f}  "
              f"data={fit['data_medianLWPI']:>7.2f}  "
              f"Δ={d_med:>+7.2f}")
        print(f"    Lorenz pts:")
        for pct, m, d in zip([20, 40, 60, 80], fit['LorenzPts'], fit['data_LorenzPts']):
            print(f"      {pct}th: model={m:>6.3f}  data={d:>6.3f}  Δ={m-d:>+6.3f}")
        print(f"    distance     ={distance:>7.4f}     ({dt:.1f}s, "
              f"{len(agents)} agents)")

    print(f"\n  Total RMSE across 3 cohorts: {np.sqrt(total_distance_sq):.4f}")

    banner("Compare to known pre-fix distances from Apr-18 calibration files")
    # The Apr 18 results (pre-BUG-037) recorded their own distances.
    # If our post-fix distances match those, the fix is wealth-fit-invariant.
    res_dir = os.path.join(_HERE, '..', 'Results')
    pre_fix_files = {
        0: 'DiscFacEstim_CRRA_2.0_R_1.01_edType0_TM_a_BUG036_bad_basin.txt',
        1: None,  # current production used a single-file format
    }
    print("  See Code/HA-Models/Results/DiscFacEstim_*_TM_a*.txt for pre-fix")
    print("  distance values (Apr-18 estimation). Our post-fix distances should")
    print("  closely match those — confirming aNrm-distribution-invariance under")
    print("  the fix.\n")
    print("  KEY QUESTION: is the wealth fit GOOD ENOUGH to call HAFiscal calibration")
    print("  validated? i.e., distance < some threshold (e.g., per-cohort < 1.0)?")


if __name__ == "__main__":
    main()
