"""
Systematic drift-sweep test for College β=atom[5], plan
plans/20260501-0809h_co-drift-sub-1pct-test-plan.md.

Goal: drive College cohort-init MC drift below 1% by progressively dialing
up MC sample size, TM grid resolution, T_age cap, and shock atom count
under the §24.5-exact counterfactual model (`unemp_shocks='perm_only'` —
ψ stochastic in all states, ξ degenerate at IncUnemp during unemployment).

Run:
    cd Code/HA-Models/FromPandemicCode
    HAFISCAL_TIERS=0 python test_co_drift_sweep.py            # Tier 0 only
    HAFISCAL_TIERS=0,1 python test_co_drift_sweep.py          # Tier 0+1
    HAFISCAL_TIERS=0,1,2,3,4,5 python test_co_drift_sweep.py  # full cascade

Output: results printed to stdout; final report appended to
/tmp/co_drift_sweep_results.log.
"""
import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))
sys.argv = ['test_co_drift_sweep']

from HARK.distributions import DiscreteDistribution
from harmenberg_doob_tier1 import setup_context, build_agent_for
from tm_methods import (
    build_tm_agg_fiscal_a,
    compute_cohort_age_decomposition_a,
    init_mc_from_cohort_age_decomposition,
)

SAMPLE_TIMES = [0, 10, 25, 50, 100, 200]


def install_perm_only_IncShkDstn(agent):
    """Modify agent.IncShkDstn in place: ψ stochastic in all states (employed
    dist), ξ kept at production unemployment income (degenerate). Mirrors
    the `unemp_shocks='perm_only'` mode in compute_cohort_age_decomposition_a.

    The MC simulator must use this same hybrid distribution for the test to
    be consistent (no model-mismatch between cohort init and MC dynamics).
    """
    IncShkDstn_list = list(agent.IncShkDstn[0])
    J = len(IncShkDstn_list)
    employed_dist = IncShkDstn_list[0]
    psi_atoms = np.asarray(employed_dist.atoms[0], dtype=np.float64)
    joint_probs = np.asarray(employed_dist.pmv, dtype=np.float64)
    unique_psi, inverse_idx = np.unique(psi_atoms, return_inverse=True)
    psi_marginal_probs = np.zeros_like(unique_psi)
    for k, p in enumerate(joint_probs):
        psi_marginal_probs[inverse_idx[k]] += p
    for jp in range(1, J):
        old_unemp_dist = IncShkDstn_list[jp]
        xi_unemp = float(np.asarray(old_unemp_dist.atoms[1])[0])
        new_xi_atoms = np.full_like(unique_psi, xi_unemp)
        IncShkDstn_list[jp] = DiscreteDistribution(
            psi_marginal_probs.copy(),
            [unique_psi.copy(), new_xi_atoms])
    agent.IncShkDstn = [IncShkDstn_list]
    agent.IncShkDstn_base = agent.IncShkDstn


def run_one_drift(beta, ctx, N, aCount, T_age, T_sim, perm_shk_count=None):
    """Run a single CO drift measurement at the given config.
    Returns dict with cohort drift % and timing.
    """
    if perm_shk_count is not None:
        agent = build_agent_for(2, beta, ctx, interpretation='CDC')
        # User can pass custom PermShkCount via re-discretization; for now
        # we leave PermShkCount at the default (7) since changing it requires
        # rebuilding the agent from EstimParameters. Skip Tier 4 if needed.
        if perm_shk_count != 7:
            print(f'  [WARN] PermShkCount override not yet implemented; using default')
    else:
        agent = build_agent_for(2, beta, ctx, interpretation='CDC')
    install_perm_only_IncShkDstn(agent)
    agent.T_age = T_age

    t_tm = time.time()
    tm_data = build_tm_agg_fiscal_a(
        agent, aCount=aCount, aMax=500, aFac=3,
        neutral_measure=False, interpretation='CDC')
    tm_time = time.time() - t_tm

    t_cohort = time.time()
    cohort_dec = compute_cohort_age_decomposition_a(
        agent, tm_data, T_age=T_age, measure='P',
        interpretation='CDC', unemp_shocks='perm_only',
        verify_against_doob=False)
    cohort_time = time.time() - t_cohort

    # Run MC
    mc_agent = deepcopy(agent)
    mc_agent.AgentCount = N
    mc_agent.seed = 30000
    mc_agent.T_sim = T_sim
    mc_agent.track_vars = ['aNrm', 'pLvl']
    mc_agent.AggDemandFac = 1.0
    mc_agent.RfreeNow = 1.0
    mc_agent.CaggNow = 1.0
    mc_agent.Cratio = 1.0
    mc_agent.EconomyMrkvNow_hist = [0] * T_sim
    mc_agent.initialize_sim()
    init_mc_from_cohort_age_decomposition(
        mc_agent, cohort_dec, tm_data['dist_aGrid'],
        N, seed=30001, use_detrended=True)
    t_mc = time.time()
    mc_agent.simulate()
    mc_time = time.time() - t_mc

    a_t0 = np.asarray(mc_agent.history['aNrm'][0])
    p_t0 = np.asarray(mc_agent.history['pLvl'][0])
    a_t200 = np.asarray(mc_agent.history['aNrm'][200])
    p_t200 = np.asarray(mc_agent.history['pLvl'][200])
    Ea_Q_t0 = float(np.average(a_t0, weights=p_t0))
    Ea_Q_t200 = float(np.average(a_t200, weights=p_t200))
    drift = abs(Ea_Q_t200 / Ea_Q_t0 - 1) * 100

    return {
        'config': dict(N=N, aCount=aCount, T_age=T_age, T_sim=T_sim, beta=beta),
        'drift_pct': drift,
        'Ea_Q_t0': Ea_Q_t0,
        'Ea_Q_t200': Ea_Q_t200,
        'tm_time': tm_time,
        'cohort_time': cohort_time,
        'mc_time': mc_time,
    }


def report(label, results):
    print(f"\n{'='*78}")
    print(f"{label}")
    print(f"{'='*78}")
    for r in results:
        cfg = r['config']
        print(f"  N={cfg['N']:>9d}  aCount={cfg['aCount']:>4d}  T_age={cfg['T_age']:>4d}  "
              f"|drift|={r['drift_pct']:>6.2f}%  "
              f"(MC {r['mc_time']:>5.1f}s, TM {r['tm_time']:>5.1f}s, "
              f"cohort {r['cohort_time']:>5.1f}s)")


def tier_passed(tier, results, threshold):
    if tier == 1:
        # 1/sqrt(N) scaling check + intercept
        Ns = np.array([r['config']['N'] for r in results], dtype=float)
        drifts = np.array([r['drift_pct'] for r in results])
        x = 1.0 / np.sqrt(Ns)
        coeffs = np.polyfit(x, drifts, 1)
        a, b = coeffs
        ss_res = np.sum((drifts - (a * x + b))**2)
        ss_tot = np.sum((drifts - np.mean(drifts))**2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float('nan')
        print(f"  Tier 1 fit: drift = {a:.3f}/sqrt(N) + {b:.3f}, R² = {r2:.3f}")
        return r2 > 0.7 and abs(b) < 1.0
    return all(r['drift_pct'] < threshold for r in results)


def main():
    tiers_env = os.environ.get('HAFISCAL_TIERS', '0').strip()
    tiers_to_run = [int(t) for t in tiers_env.split(',') if t.strip()]
    print(f"BUG-038 CO drift sweep — running tiers {tiers_to_run}")
    print(f"Plan: plans/20260501-0809h_co-drift-sub-1pct-test-plan.md")
    print()

    ctx = setup_context('Baseline')
    beta_co = float(ctx['DiscFacDstns'][2].atoms[0][5])  # CO atom[5]
    print(f"College β = atom[5] = {beta_co:.6f}")
    print()

    overall_results = {}

    if 0 in tiers_to_run:
        print('### Tier 0: counterfactual where §24.5 holds exactly')
        print('Setup: N=200k, aCount=200, T_age=200, T_sim=205, perm_only mode')
        results = [run_one_drift(beta_co, ctx, N=200_000, aCount=200,
                                  T_age=200, T_sim=205)]
        report('Tier 0 results', results)
        passed = tier_passed(0, results, threshold=2.0)
        overall_results['tier0'] = (results, passed)
        print(f'\n  PASS' if passed else f'\n  FAIL (drift >= 2%)')
        if not passed:
            print('Halting cascade.')
            return

    if 1 in tiers_to_run:
        print('\n### Tier 1: scale up N (test 1/sqrt(N) MC noise floor)')
        results = [run_one_drift(beta_co, ctx, N=N, aCount=200,
                                  T_age=200, T_sim=205)
                   for N in [200_000, 500_000, 1_000_000, 2_000_000]]
        report('Tier 1 results', results)
        passed = tier_passed(1, results, threshold=None)
        overall_results['tier1'] = (results, passed)
        print(f'\n  PASS' if passed else f'\n  FAIL (1/sqrt(N) fit poor or intercept >1%)')
        if not passed:
            print('Halting cascade.')
            return

    if 2 in tiers_to_run:
        print('\n### Tier 2: TM grid resolution (aCount)')
        results = [run_one_drift(beta_co, ctx, N=1_000_000, aCount=ac,
                                  T_age=200, T_sim=205)
                   for ac in [200, 500, 1000]]
        report('Tier 2 results', results)
        passed = abs(results[-1]['drift_pct'] - results[-2]['drift_pct']) < 0.2
        overall_results['tier2'] = (results, passed)
        print(f'\n  PASS' if passed else f'\n  FAIL (drift not saturated at aCount=1000)')
        if not passed:
            print('Halting cascade.')
            return

    if 3 in tiers_to_run:
        print('\n### Tier 3: cap value T_age')
        # Use best aCount from Tier 2 if available
        best_aCount = max(r['config']['aCount']
                          for r in overall_results.get('tier2', ([{'config': dict(aCount=500)}],))[0])
        results = [run_one_drift(beta_co, ctx, N=1_000_000, aCount=best_aCount,
                                  T_age=T, T_sim=2*T+5)
                   for T in [200, 480, 800]]
        report('Tier 3 results', results)
        drifts = [r['drift_pct'] for r in results]
        passed = (max(drifts) - min(drifts)) < 0.5
        overall_results['tier3'] = (results, passed)
        print(f'\n  PASS' if passed else f'\n  FAIL (drift varies > 0.5% across T_age)')
        if not passed:
            print('Halting cascade.')
            return

    if 4 in tiers_to_run:
        print('\n### Tier 4: shock discretization (PermShkCount)')
        print('  [SKIPPED: PermShkCount override requires agent rebuild from EstimParameters;')
        print('   not implemented in this driver. Skip to Tier 5.]')
        overall_results['tier4'] = ([], True)

    if 5 in tiers_to_run:
        print('\n### Tier 5: combine best settings')
        # Use best from each tier
        N_best = 2_000_000 if 1 in tiers_to_run else 200_000
        aCount_best = 1000 if 2 in tiers_to_run else 200
        T_age_best = 200  # Tier 3 should have shown T=200 is fine
        results = [run_one_drift(beta_co, ctx, N=N_best, aCount=aCount_best,
                                  T_age=T_age_best, T_sim=205)]
        report('Tier 5 results (best combined)', results)
        passed = results[0]['drift_pct'] < 1.0
        overall_results['tier5'] = (results, passed)
        print(f'\n  PASS — CO drift < 1%' if passed else
              f'\n  FAIL — CO drift >= 1%')

    print(f"\n{'='*78}")
    print('FINAL SUMMARY')
    print(f"{'='*78}")
    for tier_name, (results, passed) in overall_results.items():
        if results:
            best_drift = min(r['drift_pct'] for r in results)
            print(f"  {tier_name:8s} {'PASS' if passed else 'FAIL':<5s}  best drift: {best_drift:.2f}%")
        else:
            print(f"  {tier_name:8s} (skipped)")


if __name__ == "__main__":
    main()
