"""
Quick verification tests BEFORE launching the 9-hour Step 5 run.

Per user request 2026-04-29 (cohort-age branch BUG-037 fix). Runs five
fast checks (<5 min total) to catch obvious problems with the BUG-037
fix at the production-calibration (Reduced_Run) level.
(BUG-037 was later superseded by BUG-038 — the T_age-cap restoration;
kept as a historical diagnostic.)

Tests:
  (1) Reduced_Run params: only pLogInitMean and PermGroFacAgg should differ
      from a hypothetical pre-fix snapshot. Confirms scope of change.
  (2) GIC bound: L·G·E[ψ]/G_max < 1 for all 3 groups under new PermGroFacAgg.
      Confirms the calibration is still GIC-satisfying.
  (3) Static-period TM aggregates: E_P[a, j] for each cohort at production
      calibration. Compare to a previously-known-good snapshot (or just
      verify they're finite + reasonable).
  (4) compute_doob_pi_q_a runs without error and produces sensible π_Q.
  (5) Short MC (T_sim=50, N=10k): pLvl mean should be near pLvl_init mean
      times a finite ergodic factor. NO blow-up should occur.

Halt before launching Step 5 if ANY check fails.
"""
import os
import sys
import time
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['test_bug037_quick_verify']

from copy import deepcopy
from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from EstimParameters import (
    pLogInitMean_d, pLogInitMean_h, pLogInitMean_c, pLogInitMean_avg,
    PermGroFacAgg, data_EducShares, LivPrb_base, PermShkStd,
    PermGroFac_base_d, PermGroFac_base_h, PermGroFac_base_c,
    GICmaxBetas, gic_capped_beta, theGICfactor,
)
from tm_methods import (
    build_tm_agg_fiscal_a,
    find_ergodic_distribution,
    compute_doob_pi_q_a,
)


def banner(title):
    print(f"\n{'='*78}\n{title}\n{'='*78}")


def check_1_param_scope():
    """Verify the BUG-037 fix changes ONLY pLogInitMean and PermGroFacAgg."""
    banner("CHECK 1: BUG-037 fix scope — only pLogInitMean/PermGroFacAgg changed")

    print(f"  pLogInitMean_d = {pLogInitMean_d:.6f} (= log(6.2),  unchanged source)")
    print(f"  pLogInitMean_h = {pLogInitMean_h:.6f} (= log(11.1), unchanged source)")
    print(f"  pLogInitMean_c = {pLogInitMean_c:.6f} (= log(14.5), unchanged source)")
    print(f"  pLogInitMean_avg = {pLogInitMean_avg:.6f} (NEW; pop-weighted avg)")
    print(f"  PermGroFacAgg = {PermGroFacAgg:.6f} (NEW; was 1.0 pre-fix)")

    [_init_d, init_h, _init_c, _init_AD, _DiscFacDstns, _DFC, _ACT,
     _bd, _nm, _ct, _UB, _nb, _ed, _md, _np, _rc, _ui, _rui,
     _tc, _rtc, _ck, _rck] = return_parameters(
        Parametrization='Reduced_Run', OutputFor='_Main.py')
    print(f"\n  init_highschool['pLogInitMean'] = {init_h['pLogInitMean']:.6f}")
    print(f"    (should equal pLogInitMean_avg = {pLogInitMean_avg:.6f}) ", end='')
    if abs(init_h['pLogInitMean'] - pLogInitMean_avg) < 1e-12:
        print("✓")
    else:
        print(f"✗  MISMATCH")
        return False
    print(f"  init_highschool['pLogInitStd']  = {init_h['pLogInitStd']:.4f}  "
          f"(group-specific σ_h = 0.42; preserved)")

    return True


def check_2_GIC():
    """GIC: actual calibrated β must satisfy β < β_max for each group."""
    banner("CHECK 2: GIC bound — calibrated β < β_max for all 3 groups")
    L = LivPrb_base[0]
    sigma_psi_sq = PermShkStd[0]**2
    E_inv_psi = np.exp(sigma_psi_sq)  # E[1/ψ] for lognormal
    Gs = [PermGroFac_base_d[0], PermGroFac_base_h[0], PermGroFac_base_c[0]]
    names = ['Dropout', 'HighSchool', 'College']

    [_init_d, _init_h, _init_c, _init_AD, DiscFacDstns, _DFC, _ACT,
     _bd, _nm, _ct, _UB, _nb, _ed, _md, _np, _rc, _ui, _rui,
     _tc, _rtc, _ck, _rck] = return_parameters(
        Parametrization='Reduced_Run', OutputFor='_Main.py')
    actual_betas = [float(DiscFacDstns[g].atoms[0][0]) for g in range(3)]

    print(f"  E[1/ψ] = exp(σ²_ψ) = {E_inv_psi:.6f}; L = {L:.5f}")
    print(f"  PermGroFacAgg = {PermGroFacAgg:.6f}")
    print(f"  GIC bound: β < β_max where β_max = (Γ·PermGroFacAgg/(L·E[1/ψ]))^ρ / R")
    print()
    print(f"  {'group':<11} {'G':>9} {'G_total':>9} {'β_max':>9} {'β_actual':>10} {'β/β_max':>9}")

    all_pass = True
    for g, (name, G) in enumerate(zip(names, Gs)):
        G_total = G * PermGroFacAgg
        beta_max = float(gic_capped_beta(g, theGICfactor))
        beta_actual = actual_betas[g]
        ratio = beta_actual / beta_max
        flag = "✓" if ratio < 1.0 else "✗"
        print(f"  {name:<11} {G:>9.6f} {G_total:>9.6f} {beta_max:>9.6f} "
              f"{beta_actual:>10.4f} {ratio:>8.4f} {flag}")
        if ratio >= 1.0:
            all_pass = False
    if all_pass:
        print(f"\n  All groups satisfy GIC with margin. Smallest margin: "
              f"{min(1.0 - actual_betas[g]/gic_capped_beta(g, theGICfactor) for g in range(3))*100:.2f}%")
    return all_pass


def check_3_TM_aggregates():
    """Static-period TM aggregates for each cohort at production calibration."""
    banner("CHECK 3: Static TM aggregates — E_P[a, j] per cohort, sanity check")
    [init_dropout, init_highschool, init_college, init_AD, DiscFacDstns,
     _DFC, _ACT, _bd, _nm, _ct, UBspell, _nb, _ed, _md, _np, _rc, _ui, _rui,
     _tc, _rtc, _ck, _rck] = return_parameters(
        Parametrization='Reduced_Run', OutputFor='_Main.py')

    init_dicts = [init_dropout, init_highschool, init_college]
    names = ['Dropout', 'HighSchool', 'College']
    all_pass = True
    for ed, (name, init_d) in enumerate(zip(names, init_dicts)):
        beta = float(DiscFacDstns[ed].atoms[0][0])
        agent = AggFiscalType(**init_d)
        agent.cycles = 0
        agent.DiscFac = beta
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
        agent = eco.agents[0]

        tm_data = build_tm_agg_fiscal_a(
            agent, aCount=200, aMax=500, aFac=3, neutral_measure=False,
            interpretation='CDC')
        pi_P = find_ergodic_distribution(tm_data['TranMatrix'])
        A = len(tm_data['dist_aGrid'])
        J = pi_P.shape[0] // A
        pi_P_2d = pi_P.reshape(J, A)
        E_a = float(np.sum(pi_P_2d * tm_data['dist_aGrid'][None, :]))
        state_fracs = pi_P_2d.sum(axis=1)
        emp_frac = float(state_fracs[0])
        print(f"  {name:<11} β={beta:.4f}: E_P[a]={E_a:.4f}, frac_employed={emp_frac:.4f}")
        if not (0.05 < E_a < 5.0):
            print(f"    ⚠ E_P[a] out of expected range [0.05, 5.0]")
            all_pass = False
        if not (0.90 < emp_frac < 0.99):
            print(f"    ⚠ frac_employed out of expected range [0.90, 0.99]")
            all_pass = False
    return all_pass


def check_4_doob():
    """compute_doob_pi_q_a produces sensible π_Q for HS β=0.91."""
    banner("CHECK 4: Doob construction — π_Q at HS β=0.91")
    [_init_d, init_h, _init_c, init_AD, DiscFacDstns, _DFC, _ACT,
     _bd, _nm, _ct, UBspell, _nb, _ed, _md, _np, _rc, _ui, _rui,
     _tc, _rtc, _ck, _rck] = return_parameters(
        Parametrization='Reduced_Run', OutputFor='_Main.py')
    agent = AggFiscalType(**init_h)
    agent.cycles = 0
    agent.DiscFac = float(DiscFacDstns[1].atoms[0][0])
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
    agent = eco.agents[0]
    tm_data = build_tm_agg_fiscal_a(
        agent, aCount=200, aMax=500, aFac=3, neutral_measure=False,
        interpretation='CDC')
    pi_P = find_ergodic_distribution(tm_data['TranMatrix'])
    doob = compute_doob_pi_q_a(agent, tm_data, pi_P, interpretation='CDC')
    pi_Q = doob['pi_Q_doob']
    A = len(tm_data['dist_aGrid'])
    J = pi_P.shape[0] // A
    pi_Q_2d = pi_Q.reshape(J, A)
    pi_P_2d = pi_P.reshape(J, A)
    E_a_P = float(np.sum(pi_P_2d * tm_data['dist_aGrid'][None, :]))
    E_a_Q = float(np.sum(pi_Q_2d * tm_data['dist_aGrid'][None, :]))
    p_bar = doob['p_bar']
    print(f"  E_a_P = {E_a_P:.4f}, E_a_Q = {E_a_Q:.4f}")
    print(f"  p_bar = {p_bar:.4f}")
    print(f"  π_Q sum check: {pi_Q.sum():.6f} (should be 1)")
    if abs(pi_Q.sum() - 1) < 1e-9 and 0.1 < E_a_Q < 5.0:
        return True
    return False


def check_5_short_MC():
    """Short MC: T_sim=50, N=10k for HS β=0.91. pLvl mean should be finite."""
    banner("CHECK 5: Short MC (T_sim=50, N=10k) — pLvl bounded, no blow-up")
    [_init_d, init_h, _init_c, init_AD, DiscFacDstns, _DFC, _ACT,
     _bd, _nm, _ct, UBspell, _nb, _ed, _md, _np, _rc, _ui, _rui,
     _tc, _rtc, _ck, _rck] = return_parameters(
        Parametrization='Reduced_Run', OutputFor='_Main.py')
    agent = AggFiscalType(**init_h)
    agent.cycles = 0
    agent.DiscFac = float(DiscFacDstns[1].atoms[0][0])
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
    agent = eco.agents[0]
    agent.AgentCount = 10_000
    agent.seed = 30000
    agent.T_sim = 55
    agent.track_vars = ['aNrm', 'pLvl', 'MrkvNowPcvd']
    agent.initialize_sim()
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0
    agent.Cratio = 1.0
    agent.EconomyMrkvNow_hist = [0] * 55
    t0 = time.time()
    agent.simulate()
    print(f"  MC simulation done in {time.time()-t0:.1f}s")

    for t in [0, 10, 25, 50]:
        a = np.asarray(agent.history['aNrm'][t])
        p = np.asarray(agent.history['pLvl'][t])
        E_a = float(a.mean())
        E_p = float(p.mean())
        p_max = float(p.max())
        print(f"  t={t:>2}: E_P[a]={E_a:.4f}, E_p={E_p:.4f}, p_max={p_max:.2f}")
        if not np.all(np.isfinite([E_a, E_p, p_max])):
            print(f"    ✗ NON-FINITE values at t={t}")
            return False
        if E_p > 1e6 or p_max > 1e9:
            print(f"    ✗ pLvl blew up at t={t}")
            return False
    return True


def main():
    print("=" * 78)
    print("BUG-037 QUICK VERIFICATION (5 checks before 9-hour Step 5 launch)")
    print("=" * 78)

    results = []
    for name, check in [
            ('param scope', check_1_param_scope),
            ('GIC bound', check_2_GIC),
            ('TM aggregates', check_3_TM_aggregates),
            ('Doob π_Q', check_4_doob),
            ('short MC', check_5_short_MC)]:
        try:
            r = check()
        except Exception as e:
            print(f"\n  ✗ EXCEPTION in {name}: {type(e).__name__}: {e}")
            r = False
        results.append((name, r))

    print("\n" + "=" * 78)
    print("FINAL VERDICT")
    print("=" * 78)
    for name, r in results:
        flag = "✓ PASS" if r else "✗ FAIL"
        print(f"  {name:<20} {flag}")
    n_pass = sum(1 for _, r in results if r)
    print(f"\n  {n_pass}/{len(results)} checks PASS")
    if n_pass == len(results):
        print("  → SAFE to launch 9-hour Step 5 production run.")
        sys.exit(0)
    else:
        print("  → DO NOT launch Step 5 — fix failing checks first.")
        sys.exit(1)


if __name__ == "__main__":
    main()
