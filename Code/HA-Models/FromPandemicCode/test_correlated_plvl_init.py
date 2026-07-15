"""
Test correlated pLvl initialization for MC agents.

The standard TM→MC initialization draws (mNrm, Mrkv) from the TM ergodic
and pLvl independently.  But in the true ergodic, Cov(c(mNrm), pLvl) < 0
because a large recent PermShk simultaneously raises pLvl and lowers mNrm.
The independent draw zeroes out this covariance, biasing AggCons upward.

This script compares three initialization methods:
  A. Independent pLvl draw (current approach)
  B. Rank-reversal correlated pLvl draw (within each Mrkv state,
     pair lowest mNrm with highest pLvl)
  C. Cold-start with long burn-in (ground truth)

For each method, we track during warmup:
  - AggCons_pc (per-capita aggregate consumption)
  - Cov(cNrm, pLvl)  cross-sectional covariance
  - Corr(mNrm, pLvl)  cross-sectional correlation
  - E[pLvl]
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


def setup_economy(AgentCountTotal=10000, seed_offset=0):
    params = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
    (init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
     DiscFacCount, _AgentCountTotal, base_dict, num_max_iterations_solvingAD,
     convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_recession_duration, num_experiment_periods,
     *_rest) = params

    BaseTypeList = []
    for init in [init_dropout, init_highschool, init_college]:
        agent = AggFiscalType(**init)
        agent.cycles = 0
        BaseTypeList.append(agent)

    economy = AggregateDemandEconomy(**init_ADEconomy)
    for agent in BaseTypeList:
        agent.get_economy_data(economy)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseTypeList[0].IncUnemp])],
    )
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseTypeList[0].IncUnempNoBenefits])],
    )

    for bt in BaseTypeList:
        bt.IncShkDstn[0].seed = 763607780
        bt.IncShkDstn[0].reset()
        bt.IncShkDstn = [[bt.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
        bt.IncShkDstn_base = bt.IncShkDstn

    TypeList = []
    n = 0
    for e in range(3):
        for b in range(DiscFacCount):
            DiscFac = DiscFacDstns[e].atoms[0][b]
            AgentCount = int(np.floor(AgentCountTotal * data_EducShares[e] * DiscFacDstns[e].pmv[b]))
            AgentCount = max(AgentCount, 1)
            ThisType = deepcopy(BaseTypeList[e])
            ThisType.AgentCount = AgentCount
            ThisType.DiscFac = DiscFac
            ThisType.seed = n + seed_offset
            TypeList.append(ThisType)
            n += 1

    economy.agents = TypeList
    economy.solve()
    return economy, base_dict


def _draw_ages_and_base_log_plvl(agent, rng, N):
    """Draw ages and compute the base (uncorrelated) log(pLvl) for each agent."""
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

    return ages, log_pLvl


def init_mc_independent(economy, tm_data):
    """Method A: standard independent pLvl draw."""
    economy.reset()
    for agent in economy.agents:
        agent.initialize_sim()
        agent.AggDemandFac = 1.0
        agent.RfreeNow = 1.0
        agent.CaggNow = 1.0

    for i, agent in enumerate(economy.agents):
        bd_i = tm_data[i]
        erg = bd_i.get("cohort_ergodic", bd_i.get("ergodic"))
        grid = bd_i["dist_mGrid"]
        J_i = agent.num_base_MrkvStates
        M_i = len(grid)

        rng_i = np.random.RandomState(agent.seed)
        N_i = agent.AgentCount
        flat_probs = erg / np.sum(erg)

        bins = rng_i.choice(len(flat_probs), size=N_i, p=flat_probs)
        agent_j = bins // M_i
        agent_mNrm = grid[bins % M_i]

        sol_i = agent.solution[0]
        agent_aNrm = np.zeros(N_i)
        for j in range(J_i):
            mask = agent_j == j
            if np.any(mask):
                c = sol_i.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
                agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)

        ages, log_pLvl = _draw_ages_and_base_log_plvl(agent, rng_i, N_i)

        agent.state_now["aNrm"][:] = agent_aNrm
        agent.state_now["pLvl"][:] = np.exp(log_pLvl)
        agent.shocks["Mrkv"][:] = agent_j
        if hasattr(agent, "t_age") and agent.t_age is not None:
            agent.t_age[:] = ages
        agent.Cratio = 1.0
        agent.state_now["PlvlAgg"] = 1.0


def init_mc_correlated(economy, tm_data):
    """Method B: rank-reversal correlated pLvl draw.

    Within each Mrkv state, agents with the lowest mNrm get the highest pLvl
    and vice versa.  This creates the negative (mNrm, pLvl) correlation that
    exists in the true ergodic.
    """
    economy.reset()
    for agent in economy.agents:
        agent.initialize_sim()
        agent.AggDemandFac = 1.0
        agent.RfreeNow = 1.0
        agent.CaggNow = 1.0

    for i, agent in enumerate(economy.agents):
        bd_i = tm_data[i]
        erg = bd_i.get("cohort_ergodic", bd_i.get("ergodic"))
        grid = bd_i["dist_mGrid"]
        J_i = agent.num_base_MrkvStates
        M_i = len(grid)

        rng_i = np.random.RandomState(agent.seed)
        N_i = agent.AgentCount
        flat_probs = erg / np.sum(erg)

        bins = rng_i.choice(len(flat_probs), size=N_i, p=flat_probs)
        agent_j = bins // M_i
        agent_mNrm = grid[bins % M_i]

        sol_i = agent.solution[0]
        agent_aNrm = np.zeros(N_i)
        for j in range(J_i):
            mask = agent_j == j
            if np.any(mask):
                c = sol_i.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
                agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)

        ages, log_pLvl = _draw_ages_and_base_log_plvl(agent, rng_i, N_i)

        # Rank-reversal: within each Mrkv state, pair ascending mNrm
        # with descending pLvl to create negative correlation.
        for j in range(J_i):
            mask = agent_j == j
            if np.sum(mask) < 2:
                continue
            idx = np.where(mask)[0]
            mNrm_rank = np.argsort(agent_mNrm[idx])
            pLvl_rank = np.argsort(-log_pLvl[idx])  # descending
            log_pLvl[idx[mNrm_rank]] = log_pLvl[idx[pLvl_rank]]

        agent.state_now["aNrm"][:] = agent_aNrm
        agent.state_now["pLvl"][:] = np.exp(log_pLvl)
        agent.shocks["Mrkv"][:] = agent_j
        if hasattr(agent, "t_age") and agent.t_age is not None:
            agent.t_age[:] = ages
        agent.Cratio = 1.0
        agent.state_now["PlvlAgg"] = 1.0


def init_mc_cold(economy, burn_in=400):
    """Method C: standard cold start with long burn-in."""
    economy.reset()
    for agent in economy.agents:
        agent.initialize_sim()
        agent.AggDemandFac = 1.0
        agent.RfreeNow = 1.0
        agent.CaggNow = 1.0
        agent.Cratio = 1.0
        agent.state_now["PlvlAgg"] = 1.0
    for _ in range(burn_in):
        for agent in economy.agents:
            agent.sim_one_period()


def measure_cross_section(economy):
    """Measure cross-sectional statistics of the current agent distribution."""
    all_cNrm = []
    all_mNrm = []
    all_pLvl = []

    for agent in economy.agents:
        pLvl = agent.state_now["pLvl"]
        mNrm = agent.state_now.get("mNrm")
        if mNrm is None:
            aNrm = agent.state_now.get("aNrm", np.zeros(agent.AgentCount))
            mNrm = aNrm

        J = agent.num_base_MrkvStates
        Mrkv = agent.shocks.get("Mrkv", np.zeros(agent.AgentCount, dtype=int))
        sol = agent.solution[0]
        cNrm = np.zeros(agent.AgentCount)
        for j in range(J):
            mask = Mrkv == j
            if np.any(mask):
                cNrm[mask] = sol.cFunc[j](mNrm[mask], np.ones(np.sum(mask)))

        all_cNrm.append(cNrm)
        all_mNrm.append(mNrm)
        all_pLvl.append(pLvl)

    cNrm_all = np.concatenate(all_cNrm)
    mNrm_all = np.concatenate(all_mNrm)
    pLvl_all = np.concatenate(all_pLvl)

    N = len(cNrm_all)
    AggC_pc = np.mean(cNrm_all * pLvl_all)
    E_cNrm = np.mean(cNrm_all)
    E_pLvl = np.mean(pLvl_all)
    Cov_c_p = np.mean(cNrm_all * pLvl_all) - E_cNrm * E_pLvl
    Corr_m_p = np.corrcoef(mNrm_all, pLvl_all)[0, 1]
    Corr_logm_logp = np.corrcoef(
        np.log(np.maximum(mNrm_all, 1e-15)),
        np.log(np.maximum(pLvl_all, 1e-15))
    )[0, 1]

    return {
        "AggC_pc": AggC_pc,
        "E_cNrm": E_cNrm,
        "E_pLvl": E_pLvl,
        "Cov_c_p": Cov_c_p,
        "Corr_m_p": Corr_m_p,
        "Corr_logm_logp": Corr_logm_logp,
    }


def warmup_with_tracking(economy, n_warmup, measure_every=1):
    """Run warmup periods, measuring cross-section stats at intervals."""
    trajectory = [measure_cross_section(economy)]  # t=0 (before any warmup)

    for t in range(1, n_warmup + 1):
        for agent in economy.agents:
            agent.sim_one_period()
        if t % measure_every == 0 or t == n_warmup:
            trajectory.append(measure_cross_section(economy))

    return trajectory


def run_base_experiment(economy, base_dict, n_periods=20):
    """Run base experiment and return per-capita AggCons."""
    economy.save_state()
    economy.switch_to_counterfactual_mode("base")
    economy.make_idiosyncratic_shock_histories()
    bd = deepcopy(base_dict)
    res = economy.run_experiment(**bd, Full_Output=True)
    N_total = sum(a.AgentCount for a in economy.agents)
    return np.mean(res["AggCons"][:n_periods]) / N_total


if __name__ == "__main__":
    t_start = time.time()
    N_AGENTS = 20000
    N_WARMUP = 100
    MEASURE_EVERY = 1

    print("=" * 78)
    print("Correlated pLvl initialization: (mNrm, pLvl) covariance tracking")
    print("=" * 78)

    # --- Setup and TM reference ---
    eco_ref, bd_ref = setup_economy(AgentCountTotal=N_AGENTS)
    tm_data = compute_baseline_tm_data(eco_ref, mCount=100, neutral_measure=True)
    base_tm = run_experiment_tm(eco_ref, shock_type="base", mCount=100, neutral_measure=True)
    N_total = sum(a.AgentCount for a in eco_ref.agents)
    tm_pc = np.mean(base_tm["AggCons"]) / N_total
    print(f"\nTM reference: AggCons_pc = {tm_pc:.6f}")

    # --- Method C: Cold-start reference ---
    print(f"\nMethod C: cold-start (400-period burn-in)...")
    t0 = time.time()
    eco_C, bd_C = setup_economy(AgentCountTotal=N_AGENTS, seed_offset=777)
    init_mc_cold(eco_C, burn_in=400)
    stats_C = measure_cross_section(eco_C)
    AggC_cold = run_base_experiment(eco_C, bd_C)
    print(f"  AggC_pc = {AggC_cold:.6f} (vs TM: {100*(AggC_cold-tm_pc)/tm_pc:+.3f}%)")
    print(f"  Cov(cNrm,pLvl) = {stats_C['Cov_c_p']:.4f}")
    print(f"  Corr(mNrm,pLvl) = {stats_C['Corr_m_p']:.4f}")
    print(f"  Corr(log m, log p) = {stats_C['Corr_logm_logp']:.4f}")
    print(f"  E[pLvl] = {stats_C['E_pLvl']:.4f}")
    print(f"  [{time.time()-t0:.1f}s]")

    target_cov = stats_C["Cov_c_p"]
    target_corr_m_p = stats_C["Corr_m_p"]

    # --- Method A: Independent pLvl draw + warmup tracking ---
    print(f"\nMethod A: independent pLvl draw, tracking {N_WARMUP} warmup periods...")
    t0 = time.time()
    eco_A, bd_A = setup_economy(AgentCountTotal=N_AGENTS, seed_offset=42)
    tm_A = compute_baseline_tm_data(eco_A, mCount=100, neutral_measure=True)
    init_mc_independent(eco_A, tm_A)
    traj_A = warmup_with_tracking(eco_A, N_WARMUP, MEASURE_EVERY)
    AggC_A = run_base_experiment(eco_A, bd_A)
    print(f"  Post-warmup AggC_pc = {AggC_A:.6f} (vs TM: {100*(AggC_A-tm_pc)/tm_pc:+.3f}%)")
    print(f"  [{time.time()-t0:.1f}s]")

    # --- Method B: Rank-reversal correlated pLvl + warmup tracking ---
    print(f"\nMethod B: rank-reversal correlated pLvl, tracking {N_WARMUP} warmup periods...")
    t0 = time.time()
    eco_B, bd_B = setup_economy(AgentCountTotal=N_AGENTS, seed_offset=42)
    tm_B = compute_baseline_tm_data(eco_B, mCount=100, neutral_measure=True)
    init_mc_correlated(eco_B, tm_B)
    traj_B = warmup_with_tracking(eco_B, N_WARMUP, MEASURE_EVERY)
    AggC_B = run_base_experiment(eco_B, bd_B)
    print(f"  Post-warmup AggC_pc = {AggC_B:.6f} (vs TM: {100*(AggC_B-tm_pc)/tm_pc:+.3f}%)")
    print(f"  [{time.time()-t0:.1f}s]")

    # --- Print trajectory comparison ---
    print(f"\n{'':=<78}")
    print("Warmup trajectory: AggC_pc and Cov(cNrm, pLvl)")
    print(f"{'':=<78}")
    print(f"  Cold-start targets: AggC_pc={AggC_cold:.4f}, "
          f"Cov(c,p)={target_cov:.4f}, Corr(m,p)={target_corr_m_p:.4f}")
    print(f"  TM target: AggC_pc={tm_pc:.4f}")

    header = (f"{'t':>4}  {'AggC_A':>9} {'AggC_B':>9} "
              f"{'Cov_A':>9} {'Cov_B':>9} "
              f"{'Corr_A':>8} {'Corr_B':>8} "
              f"{'E[p]_A':>8} {'E[p]_B':>8}")
    print(f"\n{header}")
    print("-" * len(header))

    # Print at selected intervals
    print_at = set([0, 1, 2, 3, 4, 5, 8, 12, 16, 24, 32, 48, 64, 80, 100])
    for idx in range(len(traj_A)):
        t = idx * MEASURE_EVERY if idx > 0 else 0
        if t not in print_at:
            continue
        sA = traj_A[idx]
        sB = traj_B[idx]
        print(f"{t:>4d}  "
              f"{sA['AggC_pc']:>9.4f} {sB['AggC_pc']:>9.4f} "
              f"{sA['Cov_c_p']:>9.4f} {sB['Cov_c_p']:>9.4f} "
              f"{sA['Corr_m_p']:>8.4f} {sB['Corr_m_p']:>8.4f} "
              f"{sA['E_pLvl']:>8.2f} {sB['E_pLvl']:>8.2f}")

    # Final summary
    print(f"\n{'':=<78}")
    print("Summary")
    print(f"{'':=<78}")
    print(f"  TM reference AggC_pc:          {tm_pc:.6f}")
    print(f"  Cold-start AggC_pc:            {AggC_cold:.6f}  ({100*(AggC_cold-tm_pc)/tm_pc:+.3f}%)")
    print(f"  Method A (indep, {N_WARMUP}wu):       {AggC_A:.6f}  ({100*(AggC_A-tm_pc)/tm_pc:+.3f}%)")
    print(f"  Method B (correlated, {N_WARMUP}wu):   {AggC_B:.6f}  ({100*(AggC_B-tm_pc)/tm_pc:+.3f}%)")
    print(f"\n  Cold-start Cov(c,p):           {target_cov:.4f}")
    print(f"  Method A Cov(c,p) at t=0:      {traj_A[0]['Cov_c_p']:.4f}")
    print(f"  Method A Cov(c,p) at t={N_WARMUP}:    {traj_A[-1]['Cov_c_p']:.4f}")
    print(f"  Method B Cov(c,p) at t=0:      {traj_B[0]['Cov_c_p']:.4f}")
    print(f"  Method B Cov(c,p) at t={N_WARMUP}:    {traj_B[-1]['Cov_c_p']:.4f}")

    print(f"\n  Total elapsed: {time.time()-t_start:.0f}s ({(time.time()-t_start)/60:.1f} min)")
