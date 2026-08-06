"""
Single-type (highschool) convergence analysis.

Isolates one agent type to cleanly measure:
  1. The within-type ergodic Corr(mNrm, pLvl) and Cov(cNrm, pLvl)
  2. How agent count, TM grid, and warmup duration affect MC-vs-TM agreement
  3. Whether a correlated pLvl initialization improves convergence
"""

import sys
import os
import warnings

warnings.filterwarnings("ignore")

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
_HA_MODELS_DIR = os.path.dirname(_THIS_DIR)
if _HA_MODELS_DIR not in sys.path:
    sys.path.insert(0, _HA_MODELS_DIR)

_orig_argv = sys.argv[:]
sys.argv = [sys.argv[0], "1.01", "2.0", "0.7"]

import numpy as np
from copy import deepcopy
import time

from Parameters import return_parameters
from income_process_sst import effective_perm_shock_periods_for_t_age, effective_pLvl_growth, effective_perm_shock_variance_periods
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from tm_methods import compute_baseline_tm_data, run_experiment_tm

sys.argv = _orig_argv


# ──────────────────────────────────────────────────────────────────────
# Setup: single highschool type
# ──────────────────────────────────────────────────────────────────────

def setup_single_hs(AgentCount=20000, seed=0):
    """Create economy with a single highschool agent type."""
    params = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
    (init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
     DiscFacCount, _AgentCountTotal, base_dict, num_max_iterations_solvingAD,
     convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_recession_duration, num_experiment_periods,
     *_rest) = params

    agent = AggFiscalType(**init_highschool)
    agent.cycles = 0
    agent.AgentCount = AgentCount
    agent.DiscFac = DiscFacDstns[1].atoms[0][0]  # median HS beta
    agent.seed = seed

    economy = AggregateDemandEconomy(**init_ADEconomy)
    agent.get_economy_data(economy)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agent.IncUnemp])],
    )
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agent.IncUnempNoBenefits])],
    )
    agent.IncShkDstn[0].seed = 763607780
    agent.IncShkDstn[0].reset()
    agent.IncShkDstn = [[agent.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
    agent.IncShkDstn_base = agent.IncShkDstn

    economy.agents = [agent]
    economy.solve()
    return economy, base_dict, agent


# ──────────────────────────────────────────────────────────────────────
# Measurement
# ──────────────────────────────────────────────────────────────────────

def cross_section_stats(agent):
    """Measure within-type cross-sectional statistics."""
    pLvl = agent.state_now["pLvl"].copy()
    mNrm = agent.state_now.get("mNrm")
    if mNrm is None:
        aNrm = agent.state_now.get("aNrm", np.zeros(agent.AgentCount))
        mNrm = aNrm
    mNrm = mNrm.copy()

    Mrkv = agent.shocks.get("Mrkv", np.zeros(agent.AgentCount, dtype=int))
    J = agent.num_base_MrkvStates
    sol = agent.solution[0]
    cNrm = np.zeros(agent.AgentCount)
    for j in range(J):
        mask = Mrkv == j
        if np.any(mask):
            cNrm[mask] = sol.cFunc[j](mNrm[mask], np.ones(np.sum(mask)))

    E_cNrm = np.mean(cNrm)
    E_pLvl = np.mean(pLvl)
    AggC_pc = np.mean(cNrm * pLvl)
    Cov_c_p = AggC_pc - E_cNrm * E_pLvl

    valid = (mNrm > 0) & (pLvl > 0)
    if np.sum(valid) > 10:
        Corr_m_p = np.corrcoef(mNrm[valid], pLvl[valid])[0, 1]
        Corr_logm_logp = np.corrcoef(np.log(mNrm[valid]), np.log(pLvl[valid]))[0, 1]
    else:
        Corr_m_p = Corr_logm_logp = float("nan")

    return {
        "AggC_pc": AggC_pc,
        "E_cNrm": E_cNrm,
        "E_pLvl": E_pLvl,
        "Cov_c_p": Cov_c_p,
        "Corr_m_p": Corr_m_p,
        "Corr_logm_logp": Corr_logm_logp,
        "E_mNrm": float(np.mean(mNrm)),
    }


def run_base_experiment(economy, base_dict, n_periods=20):
    """Run base experiment, return per-capita AggCons time series."""
    economy.save_state()
    economy.switch_to_counterfactual_mode("base")
    economy.make_idiosyncratic_shock_histories()
    bd = deepcopy(base_dict)
    res = economy.run_experiment(**bd, Full_Output=True)
    N = economy.agents[0].AgentCount
    return res["AggCons"][:n_periods] / N


# ──────────────────────────────────────────────────────────────────────
# Initialization methods
# ──────────────────────────────────────────────────────────────────────

def _prep_agent(agent):
    agent.initialize_sim()
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0
    agent.Cratio = 1.0
    agent.state_now["PlvlAgg"] = 1.0


def _draw_from_tm_ergodic(agent, tm_d, rng):
    """Draw (mNrm, Mrkv, aNrm, ages, log_pLvl) from TM ergodic."""
    erg = tm_d.get("cohort_ergodic", tm_d.get("ergodic"))
    grid = tm_d["dist_mGrid"]
    J = agent.num_base_MrkvStates
    M = len(grid)
    N = agent.AgentCount

    flat_probs = erg.flatten()
    flat_probs /= np.sum(flat_probs)
    bins = rng.choice(len(flat_probs), size=N, p=flat_probs)
    agent_j = bins // M
    agent_mNrm = grid[bins % M]

    sol = agent.solution[0]
    agent_aNrm = np.zeros(N)
    for j in range(J):
        mask = agent_j == j
        if np.any(mask):
            c = sol.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
            agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)

    L = agent.LivPrb[0][0]
    T_ag = agent.T_age
    age_probs = np.array([L ** (k - 1) for k in range(1, T_ag + 1)])
    age_probs /= np.sum(age_probs)
    ages = rng.choice(T_ag, size=N, p=age_probs) + 1

    pLogMean = agent.pLogInitMean
    pLogStd = getattr(agent, "pLogInitStd", getattr(agent, "pLvlInitStd", 0.0))
    PermShkDstn_0 = agent.IncShkDstn_base[0][0]
    log_ps = np.log(PermShkDstn_0.atoms[0])
    ps_var = np.dot(PermShkDstn_0.pmv, log_ps ** 2) - np.dot(PermShkDstn_0.pmv, log_ps) ** 2
    g_lvl = effective_pLvl_growth(agent, getattr(agent, "Urate_normal", 0.0))
    eff_emp = effective_perm_shock_periods_for_t_age(
        ages, agent, getattr(agent, "Urate_normal", 0.0))

    log_pLvl = rng.normal(pLogMean, pLogStd, N)
    log_pLvl += ages * np.log(g_lvl)
    log_pLvl += eff_emp * (-ps_var / 2.0)
    log_pLvl += rng.normal(0, np.sqrt(ps_var * eff_emp))

    return agent_mNrm, agent_j, agent_aNrm, ages, log_pLvl


def init_independent(economy, tm_data):
    """Method A: independent pLvl draw."""
    agent = economy.agents[0]
    economy.reset()
    _prep_agent(agent)

    rng = np.random.RandomState(agent.seed)
    mNrm, j, aNrm, ages, log_pLvl = _draw_from_tm_ergodic(agent, tm_data[0], rng)

    agent.state_now["aNrm"][:] = aNrm
    agent.state_now["pLvl"][:] = np.exp(log_pLvl)
    agent.shocks["Mrkv"][:] = j
    if hasattr(agent, "t_age") and agent.t_age is not None:
        agent.t_age[:] = ages


def init_correlated(economy, tm_data):
    """Method B: rank-reversal within each Mrkv state."""
    agent = economy.agents[0]
    economy.reset()
    _prep_agent(agent)

    rng = np.random.RandomState(agent.seed)
    mNrm, j_arr, aNrm, ages, log_pLvl = _draw_from_tm_ergodic(agent, tm_data[0], rng)

    J = agent.num_base_MrkvStates
    for j in range(J):
        mask = j_arr == j
        n_j = np.sum(mask)
        if n_j < 2:
            continue
        idx = np.where(mask)[0]
        order_m = np.argsort(mNrm[idx])       # ascending mNrm
        order_p = np.argsort(-log_pLvl[idx])   # descending pLvl
        # Reorder: agent with rank-k mNrm gets rank-k (descending) pLvl
        reordered_log_pLvl = log_pLvl[idx[order_p]]
        log_pLvl[idx[order_m]] = reordered_log_pLvl

    agent.state_now["aNrm"][:] = aNrm
    agent.state_now["pLvl"][:] = np.exp(log_pLvl)
    agent.shocks["Mrkv"][:] = j_arr
    if hasattr(agent, "t_age") and agent.t_age is not None:
        agent.t_age[:] = ages


def init_cold_start(economy, burn_in=400):
    """Method C: standard cold start."""
    agent = economy.agents[0]
    economy.reset()
    _prep_agent(agent)
    for _ in range(burn_in):
        agent.sim_one_period()


# ──────────────────────────────────────────────────────────────────────
# Experiments
# ──────────────────────────────────────────────────────────────────────

def experiment_1_ergodic_ground_truth():
    """Measure the true within-type ergodic from a long cold-start."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 1: Ground-truth ergodic (single HS type, cold-start)")
    print("=" * 70)

    N = 50000
    eco, bd, agent = setup_single_hs(AgentCount=N, seed=12345)
    print(f"  DiscFac = {agent.DiscFac:.4f}")
    print(f"  Urate_normal = {agent.Urate_normal}")
    print(f"  PermGroFac = {agent.PermGroFac[0][0]}")
    print(f"  pLogInitMean = {agent.pLogInitMean:.4f}")
    print(f"  AgentCount = {N}")

    # Long burn-in
    print(f"\n  Running cold-start with 1000-period burn-in...")
    t0 = time.time()
    init_cold_start(eco, burn_in=1000)
    stats_1000 = cross_section_stats(agent)
    print(f"  Done in {time.time()-t0:.1f}s")

    print(f"\n  --- Ergodic cross-section stats (burn-in=1000) ---")
    for k, v in stats_1000.items():
        print(f"    {k:20s} = {v:.6f}")

    # Also measure after 500 and 2000 to check stability
    for extra in [500]:
        for _ in range(extra):
            agent.sim_one_period()
        stats_extra = cross_section_stats(agent)
        total_bi = 1000 + extra
        print(f"\n  --- After {total_bi} total burn-in periods ---")
        print(f"    AggC_pc      = {stats_extra['AggC_pc']:.6f}  "
              f"(vs 1000: {100*(stats_extra['AggC_pc']-stats_1000['AggC_pc'])/stats_1000['AggC_pc']:+.3f}%)")
        print(f"    Corr(m,p)    = {stats_extra['Corr_m_p']:.6f}")
        print(f"    Cov(c,p)     = {stats_extra['Cov_c_p']:.6f}")
        print(f"    E[pLvl]      = {stats_extra['E_pLvl']:.4f}")

    return stats_1000


def experiment_2_tm_grid_convergence():
    """TM grid convergence for single HS type."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 2: TM grid convergence (single HS type)")
    print("=" * 70)

    eco, bd, agent = setup_single_hs(AgentCount=1000, seed=0)
    m_counts = [20, 30, 50, 75, 100, 150, 200, 300]

    ref_tm = run_experiment_tm(eco, shock_type="base", dist_aGrid_count=300, neutral_measure=True)
    ref_pc = np.mean(ref_tm["AggCons"]) / agent.AgentCount

    print(f"\n  TM reference (mCount=300): AggCons_pc = {ref_pc:.6f}")
    print(f"\n  {'mCount':>8} {'AggC_pc':>12} {'vs ref %':>10} {'Time':>8}")
    print("  " + "-" * 42)

    for mc in m_counts:
        t0 = time.time()
        r = run_experiment_tm(eco, shock_type="base", dist_aGrid_count=mc, neutral_measure=True)
        pc = np.mean(r["AggCons"]) / agent.AgentCount
        err = 100 * (pc - ref_pc) / ref_pc
        print(f"  {mc:>8d} {pc:>12.6f} {err:>+9.4f}% {time.time()-t0:>7.1f}s")

    return ref_pc


def experiment_3_mc_convergence(ergodic_stats, tm_ref_pc):
    """MC agent count + warmup sweep for single HS type."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 3: MC convergence sweep (single HS type)")
    print("=" * 70)

    agent_counts = [5000, 10000, 20000, 50000, 100000]
    n_seeds = 5
    warmup = 24

    print(f"\n  TM reference AggC_pc:  {tm_ref_pc:.6f}")
    print(f"  Cold-start AggC_pc:    {ergodic_stats['AggC_pc']:.6f}")
    print(f"  Warmup = {warmup}")
    print(f"  Seeds per agent count = {n_seeds}")

    print(f"\n  {'N':>8} {'mean_pc':>10} {'SE':>8} {'vs TM %':>9} {'vs cold%':>9} "
          f"{'Corr(m,p)':>10} {'Time':>7}")
    print("  " + "-" * 70)

    for N in agent_counts:
        t0 = time.time()
        pcs = []
        corrs = []
        for s in range(n_seeds):
            eco, bd, agent = setup_single_hs(AgentCount=N, seed=s * 137)
            tm_d = compute_baseline_tm_data(eco, dist_aGrid_count=100, neutral_measure=True, verbose=False)
            init_independent(eco, tm_d)
            for _ in range(warmup):
                agent.sim_one_period()
            st = cross_section_stats(agent)
            C = run_base_experiment(eco, bd, n_periods=20)
            pcs.append(float(np.mean(C)))
            corrs.append(st["Corr_m_p"])

        mean_pc = np.mean(pcs)
        se_pc = np.std(pcs) / np.sqrt(n_seeds)
        err_tm = 100 * (mean_pc - tm_ref_pc) / tm_ref_pc
        err_cold = 100 * (mean_pc - ergodic_stats["AggC_pc"]) / ergodic_stats["AggC_pc"]
        mean_corr = np.mean(corrs)
        elapsed = time.time() - t0
        print(f"  {N:>8d} {mean_pc:>10.4f} {se_pc:>8.4f} {err_tm:>+8.3f}% "
              f"{err_cold:>+8.3f}% {mean_corr:>10.4f} {elapsed:>6.1f}s")


def experiment_4_warmup_sweep(ergodic_stats, tm_ref_pc):
    """Warmup duration sweep with covariance tracking."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 4: Warmup sweep with covariance tracking (single HS type)")
    print("=" * 70)

    N = 50000
    warmups = [0, 4, 8, 16, 24, 48, 100, 200, 400]

    print(f"\n  AgentCount = {N}")
    print(f"  TM reference AggC_pc = {tm_ref_pc:.6f}")
    print(f"  Cold-start targets: AggC_pc={ergodic_stats['AggC_pc']:.4f}, "
          f"Corr(m,p)={ergodic_stats['Corr_m_p']:.4f}, "
          f"Cov(c,p)={ergodic_stats['Cov_c_p']:.6f}")

    print(f"\n  {'warmup':>7} {'AggC_pc':>10} {'vs TM%':>8} {'Corr(m,p)':>10} "
          f"{'Cov(c,p)':>10} {'E[pLvl]':>8} {'Time':>6}")
    print("  " + "-" * 65)

    eco_base, bd_base, agent_base = setup_single_hs(AgentCount=N, seed=42)
    tm_d = compute_baseline_tm_data(eco_base, dist_aGrid_count=100, neutral_measure=True)

    for wu in warmups:
        t0 = time.time()
        eco, bd, agent = setup_single_hs(AgentCount=N, seed=42)
        tm_d_w = compute_baseline_tm_data(eco, dist_aGrid_count=100, neutral_measure=True, verbose=False)
        init_independent(eco, tm_d_w)
        for _ in range(wu):
            agent.sim_one_period()

        st = cross_section_stats(agent)
        C = run_base_experiment(eco, bd, n_periods=20)
        pc = float(np.mean(C))
        err = 100 * (pc - tm_ref_pc) / tm_ref_pc
        elapsed = time.time() - t0

        print(f"  {wu:>7d} {pc:>10.4f} {err:>+7.3f}% {st['Corr_m_p']:>10.4f} "
              f"{st['Cov_c_p']:>10.6f} {st['E_pLvl']:>8.2f} {elapsed:>5.1f}s")


def experiment_5_correlated_vs_independent(ergodic_stats, tm_ref_pc):
    """Compare correlated vs independent init, tracking covariance evolution."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 5: Correlated vs independent init (single HS type)")
    print("=" * 70)

    N = 50000
    N_WARMUP = 200

    eco_A, bd_A, ag_A = setup_single_hs(AgentCount=N, seed=42)
    tm_A = compute_baseline_tm_data(eco_A, dist_aGrid_count=100, neutral_measure=True)
    init_independent(eco_A, tm_A)

    eco_B, bd_B, ag_B = setup_single_hs(AgentCount=N, seed=42)
    tm_B = compute_baseline_tm_data(eco_B, dist_aGrid_count=100, neutral_measure=True, verbose=False)
    init_correlated(eco_B, tm_B)

    print(f"\n  AgentCount = {N}, warmup periods = {N_WARMUP}")
    print(f"  Cold-start targets: Corr(m,p)={ergodic_stats['Corr_m_p']:.4f}, "
          f"Cov(c,p)={ergodic_stats['Cov_c_p']:.6f}")

    header = (f"  {'t':>4} {'AggC_A':>9} {'AggC_B':>9} "
              f"{'Corr_A':>8} {'Corr_B':>8} "
              f"{'Cov_A':>9} {'Cov_B':>9}")
    print(f"\n{header}")
    print("  " + "-" * (len(header) - 2))

    print_at = {0, 1, 2, 4, 8, 16, 24, 48, 80, 100, 150, 200}
    for t in range(N_WARMUP + 1):
        if t in print_at:
            sA = cross_section_stats(ag_A)
            sB = cross_section_stats(ag_B)
            print(f"  {t:>4d} {sA['AggC_pc']:>9.4f} {sB['AggC_pc']:>9.4f} "
                  f"{sA['Corr_m_p']:>8.4f} {sB['Corr_m_p']:>8.4f} "
                  f"{sA['Cov_c_p']:>9.6f} {sB['Cov_c_p']:>9.6f}")
        if t < N_WARMUP:
            ag_A.sim_one_period()
            ag_B.sim_one_period()

    # Final AggCons from base experiment
    C_A = run_base_experiment(eco_A, bd_A, n_periods=20)
    C_B = run_base_experiment(eco_B, bd_B, n_periods=20)
    pc_A = float(np.mean(C_A))
    pc_B = float(np.mean(C_B))
    print(f"\n  Post-{N_WARMUP}wu base experiment AggC_pc:")
    print(f"    Method A (indep):      {pc_A:.4f} (vs TM: {100*(pc_A-tm_ref_pc)/tm_ref_pc:+.3f}%)")
    print(f"    Method B (correlated): {pc_B:.4f} (vs TM: {100*(pc_B-tm_ref_pc)/tm_ref_pc:+.3f}%)")


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    t_total = time.time()

    ergodic_stats = experiment_1_ergodic_ground_truth()
    tm_ref_pc = experiment_2_tm_grid_convergence()
    experiment_3_mc_convergence(ergodic_stats, tm_ref_pc)
    experiment_4_warmup_sweep(ergodic_stats, tm_ref_pc)
    experiment_5_correlated_vs_independent(ergodic_stats, tm_ref_pc)

    print(f"\n{'='*70}")
    print(f"Total elapsed: {time.time()-t_total:.0f}s ({(time.time()-t_total)/60:.1f} min)")
    print(f"{'='*70}")
