"""
Phase 1 deep investigation: burn-in convergence and TM→MC initialization mismatch.

Questions:
1. How does MC per-capita AggCons evolve as a function of burn-in/warmup periods?
2. What causes the gap between the TM ergodic and the MC initial distribution?
3. Can the initialization be improved to eliminate/reduce burn-in?

Key insight: The TM ergodic is a 1D distribution over mNrm (or joint over 
(mNrm, Mrkv)). The MC needs a joint distribution over (mNrm, pLvl, Mrkv, age).
The current initialization:
  - Draws (mNrm, Mrkv) from the TM ergodic  [exact]
  - Draws age from the geometric survival distribution  [exact for perpetual youth]
  - Draws pLvl conditioned on age  [approximate: lognormal with Jensen correction]
  - Converts mNrm → aNrm via cFunc(mNrm)  [deterministic given mNrm and Mrkv]

Potential sources of mismatch:
  (a) mNrm sampled on exact TM grid points (no jitter between grid points)
  (b) pLvl distribution is lognormal conditional on age, but the true ergodic
      pLvl has additional dependence on employment history
  (c) No joint (mNrm, pLvl) dependence: mNrm and pLvl drawn independently,
      but in the true ergodic they have weak correlation (Cov(m,p) ≠ 0)
  (d) Markov state fractions from TM ergodic may not match the unemployment
      rate embedded in the pLvl construction
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


def setup_economy_simple(AgentCountTotal=5000, seed_offset=0):
    """Minimal economy setup for burn-in testing."""
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

    for bt in BaseTypeList:
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


def tm_init_mc(economy, tm_data, warmup=0):
    """Initialize MC from TM ergodic, run `warmup` periods, return state."""
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

        L = agent.LivPrb[0][0]
        T_ag = agent.T_age
        age_probs = np.array([L ** (k - 1) for k in range(1, T_ag + 1)])
        age_probs /= np.sum(age_probs)
        agent_ages = rng_i.choice(T_ag, size=N_i, p=age_probs) + 1

        pLogMean = agent.pLogInitMean
        pLogStd = getattr(agent, "pLogInitStd", getattr(agent, "pLvlInitStd", 0.0))
        PermShkDstn_0 = agent.IncShkDstn_base[0][0]
        log_ps = np.log(PermShkDstn_0.atoms[0])
        ps_var = np.dot(PermShkDstn_0.pmv, log_ps ** 2) - np.dot(PermShkDstn_0.pmv, log_ps) ** 2
        g_lvl = effective_pLvl_growth(agent, getattr(agent, "Urate_normal", 0.0))
        effective_emp_periods = effective_perm_shock_periods_for_t_age(
            agent_ages, agent, getattr(agent, "Urate_normal", 0.0))
        log_pLvl = rng_i.normal(pLogMean, pLogStd, N_i)
        log_pLvl += agent_ages * np.log(g_lvl)
        log_pLvl += effective_emp_periods * (-ps_var / 2.0)
        log_pLvl += rng_i.normal(0, np.sqrt(ps_var * effective_emp_periods))
        agent_pLvl = np.exp(log_pLvl)

        agent.state_now["aNrm"][:] = agent_aNrm
        agent.state_now["pLvl"][:] = agent_pLvl
        agent.shocks["Mrkv"][:] = agent_j
        if hasattr(agent, "t_age") and agent.t_age is not None:
            agent.t_age[:] = agent_ages
        agent.Cratio = 1.0
        agent.state_now["PlvlAgg"] = 1.0

    for _t in range(warmup):
        for agent in economy.agents:
            agent.sim_one_period()


def cold_start_mc(economy, burn_in_periods):
    """Standard HARK initialize_sim + long burn-in."""
    economy.reset()
    for agent in economy.agents:
        agent.initialize_sim()
        agent.AggDemandFac = 1.0
        agent.RfreeNow = 1.0
        agent.CaggNow = 1.0
        agent.Cratio = 1.0
        agent.state_now["PlvlAgg"] = 1.0
    for _t in range(burn_in_periods):
        for agent in economy.agents:
            agent.sim_one_period()


def measure_agg_cons_pc(economy, base_dict, n_periods=20):
    """Run n_periods of base experiment and return per-period per-capita AggCons."""
    economy.save_state()
    economy.switch_to_counterfactual_mode("base")
    economy.make_idiosyncratic_shock_histories()
    bd = deepcopy(base_dict)
    res = economy.run_experiment(**bd, Full_Output=True)
    N_total = sum(a.AgentCount for a in economy.agents)
    return res["AggCons"][:n_periods] / N_total


def measure_distribution_stats(economy):
    """Measure cross-sectional distribution statistics after current state."""
    stats = {}
    all_mNrm = []
    all_pLvl = []
    all_cNrm = []

    for agent in economy.agents:
        mNrm = agent.state_now.get("mNrm")
        if mNrm is None:
            aNrm = agent.state_now.get("aNrm", np.zeros(agent.AgentCount))
            pLvl = agent.state_now.get("pLvl", np.ones(agent.AgentCount))
            all_pLvl.append(pLvl)
            continue

        pLvl = agent.state_now["pLvl"]
        all_mNrm.append(mNrm)
        all_pLvl.append(pLvl)

    if all_mNrm:
        mNrm_all = np.concatenate(all_mNrm)
        stats["E_mNrm"] = float(np.mean(mNrm_all))
        stats["SD_mNrm"] = float(np.std(mNrm_all))
        stats["median_mNrm"] = float(np.median(mNrm_all))

    pLvl_all = np.concatenate(all_pLvl)
    stats["E_pLvl"] = float(np.mean(pLvl_all))
    stats["SD_pLvl"] = float(np.std(pLvl_all))
    stats["E_log_pLvl"] = float(np.mean(np.log(np.maximum(pLvl_all, 1e-15))))
    stats["SD_log_pLvl"] = float(np.std(np.log(np.maximum(pLvl_all, 1e-15))))

    return stats


# ─── Experiment 1: Burn-in sweep ─────────────────────────────────────

def experiment_burnin_sweep():
    """Test how AggCons_pc evolves with different warmup lengths after TM init."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 1: Burn-in / warmup sweep after TM initialization")
    print("=" * 70)

    warmup_values = [0, 4, 8, 16, 24, 48, 100, 200]
    N_agents = 10000

    economy, base_dict = setup_economy_simple(AgentCountTotal=N_agents)
    tm_data = compute_baseline_tm_data(economy, dist_aGrid_count=100, neutral_measure=True)

    # TM reference
    base_tm = run_experiment_tm(economy, shock_type="base", dist_aGrid_count=100, neutral_measure=True)
    N_total = sum(a.AgentCount for a in economy.agents)
    tm_AggCons_pc = np.mean(base_tm["AggCons"]) / N_total
    print(f"\nTM reference (mCount=100): AggCons_pc = {tm_AggCons_pc:.6f}")

    # Cold-start reference (long burn-in, no TM init)
    print("\nCold-start (act_T=400 burn-in, no TM init)...")
    t0 = time.time()
    eco_cold, bd_cold = setup_economy_simple(AgentCountTotal=N_agents, seed_offset=999)
    cold_start_mc(eco_cold, burn_in_periods=400)
    C_cold = measure_agg_cons_pc(eco_cold, bd_cold, n_periods=20)
    cold_AggCons_pc = float(np.mean(C_cold))
    print(f"  Cold-start AggCons_pc = {cold_AggCons_pc:.6f} "
          f"(vs TM: {100*(cold_AggCons_pc - tm_AggCons_pc)/tm_AggCons_pc:+.3f}%) "
          f"[{time.time()-t0:.1f}s]")

    # TM-init with varying warmup
    print(f"\n{'Warmup':>8} {'AggC_pc':>12} {'vs TM %':>10} {'vs Cold %':>10} "
          f"{'E[mNrm]':>10} {'E[pLvl]':>10} {'Time':>8}")
    print("-" * 75)

    results = []
    for wu in warmup_values:
        t0 = time.time()
        eco_w, bd_w = setup_economy_simple(AgentCountTotal=N_agents, seed_offset=42)
        tm_data_w = compute_baseline_tm_data(eco_w, dist_aGrid_count=100, neutral_measure=True)
        tm_init_mc(eco_w, tm_data_w, warmup=wu)
        dist_stats = measure_distribution_stats(eco_w)
        C_w = measure_agg_cons_pc(eco_w, bd_w, n_periods=20)
        AggC_pc = float(np.mean(C_w))
        elapsed = time.time() - t0

        err_tm = 100 * (AggC_pc - tm_AggCons_pc) / tm_AggCons_pc
        err_cold = 100 * (AggC_pc - cold_AggCons_pc) / cold_AggCons_pc

        results.append({
            "warmup": wu, "AggC_pc": AggC_pc, "err_tm": err_tm,
            "dist_stats": dist_stats, "C_series": C_w,
        })

        E_mNrm = dist_stats.get("E_mNrm", float("nan"))
        E_pLvl = dist_stats.get("E_pLvl", float("nan"))
        print(f"{wu:>8d} {AggC_pc:>12.6f} {err_tm:>+9.3f}% {err_cold:>+9.3f}% "
              f"{E_mNrm:>10.4f} {E_pLvl:>10.2f} {elapsed:>7.1f}s")

    # Show per-period evolution for warmup=0 and warmup=24
    print("\n--- Per-period AggCons_pc (first 20 periods of base experiment) ---")
    for r in results:
        if r["warmup"] in (0, 8, 24, 100):
            series = r["C_series"]
            wu = r["warmup"]
            vals = " ".join(f"{v:.4f}" for v in series[:10])
            print(f"  warmup={wu:>3d}: {vals} ...")

    return results, tm_AggCons_pc, cold_AggCons_pc


# ─── Experiment 2: Diagnose the initialization mismatch ──────────────

def experiment_init_mismatch():
    """Compare the TM ergodic distribution with the MC initial distribution
    to understand the sources of mismatch."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 2: TM-to-MC initialization mismatch diagnosis")
    print("=" * 70)

    N_agents = 20000
    economy, base_dict = setup_economy_simple(AgentCountTotal=N_agents)
    tm_data = compute_baseline_tm_data(economy, dist_aGrid_count=100, neutral_measure=True)

    # TM ergodic stats (per type)
    print("\n--- TM ergodic distribution stats ---")
    for i, (bd, agent) in enumerate(zip(tm_data, economy.agents)):
        erg = bd.get("cohort_ergodic", bd.get("ergodic"))
        grid = bd["dist_mGrid"]
        J = agent.num_base_MrkvStates
        M = len(grid)
        erg_flat = erg.flatten()

        E_mNrm_tm = np.dot(erg_flat, np.tile(grid, J))
        E_m2 = np.dot(erg_flat, np.tile(grid ** 2, J))
        SD_mNrm_tm = np.sqrt(E_m2 - E_mNrm_tm ** 2)

        # Markov state fractions
        mrkv_fracs = [np.sum(erg_flat[j * M:(j + 1) * M]) for j in range(J)]
        E_pLvl_tm = bd["E_pLvl"]

        print(f"  Type {i} (DiscFac={agent.DiscFac:.4f}, N={agent.AgentCount}): "
              f"E[mNrm]={E_mNrm_tm:.4f}, SD[mNrm]={SD_mNrm_tm:.4f}, "
              f"E[pLvl]={E_pLvl_tm:.2f}, Mrkv fracs={[f'{f:.3f}' for f in mrkv_fracs]}")

    # MC initial distribution (warmup=0)
    print("\n--- MC initial distribution (TM-init, warmup=0) ---")
    eco_0, _ = setup_economy_simple(AgentCountTotal=N_agents, seed_offset=42)
    tm_data_0 = compute_baseline_tm_data(eco_0, dist_aGrid_count=100, neutral_measure=True)
    tm_init_mc(eco_0, tm_data_0, warmup=0)

    for i, agent in enumerate(eco_0.agents):
        mNrm = agent.state_now.get("mNrm")
        aNrm = agent.state_now.get("aNrm", np.zeros(agent.AgentCount))
        pLvl = agent.state_now["pLvl"]
        Mrkv = agent.shocks["Mrkv"]
        J = agent.num_base_MrkvStates

        if mNrm is None:
            # After TM init, state_now has aNrm, not mNrm (mNrm is computed during sim)
            # Approximate mNrm = aNrm * R / (G * perm_shk) + TranShk
            # But at init time, no shocks have been drawn yet. mNrm is what we set it to.
            # Actually the TM init sets aNrm via cFunc(mNrm), so we can invert:
            # The grid we sampled from IS the mNrm values
            mNrm = aNrm  # Placeholder — see below

        mrkv_fracs_mc = [np.mean(Mrkv == j) for j in range(J)]
        E_pLvl_mc = float(np.mean(pLvl))
        E_pLvl_tm = tm_data_0[i]["E_pLvl"]

        print(f"  Type {i}: E[pLvl_MC]={E_pLvl_mc:.2f} (TM analytical={E_pLvl_tm:.2f}, "
              f"gap={100*(E_pLvl_mc-E_pLvl_tm)/E_pLvl_tm:+.2f}%), "
              f"Mrkv fracs MC={[f'{f:.3f}' for f in mrkv_fracs_mc]}")

    # Key diagnostic: the pLvl mismatch
    print("\n--- pLvl distribution diagnostic ---")
    print("The TM uses an analytical E[pLvl] based on the perpetual-youth formula:")
    print("  E[pLvl] = (1-L) / (1 - L*G) * exp(pLogInitMean)")
    print("adjusted for unemployment rate. The MC draws pLvl from a lognormal")
    print("conditioned on age, which may have a different mean due to:")
    print("  (a) Discretization of the permanent shock distribution")
    print("  (b) Jensen's inequality correction in log space")
    print("  (c) The lognormal assumption itself (true distribution is mixture)")
    print("  (d) Independence assumption (mNrm ⊥ pLvl)")

    for i, agent in enumerate(eco_0.agents):
        pLvl = agent.state_now["pLvl"]
        E_pLvl_mc = float(np.mean(pLvl))
        E_pLvl_tm = tm_data_0[i]["E_pLvl"]

        L = agent.LivPrb[0][0]
        g_lvl = effective_pLvl_growth(agent, getattr(agent, "Urate_normal", 0.0))
        PermShkDstn_0 = agent.IncShkDstn_base[0][0]
        log_ps = np.log(PermShkDstn_0.atoms[0])
        ps_var = np.dot(PermShkDstn_0.pmv, log_ps ** 2) - np.dot(PermShkDstn_0.pmv, log_ps) ** 2

        # Analytical E[pLvl] for perpetual youth (SST effective growth)
        E_analytical = np.exp(agent.pLogInitMean) * (1.0 - L) / (1.0 - L * g_lvl)

        print(f"\n  Type {i}:")
        print(f"    LivPrb={L:.5f}, g_lvl={g_lvl:.6f}, ps_var={ps_var:.6f}")
        print(f"    E[pLvl] analytical (no unemp adj) = {E_analytical:.2f}")
        print(f"    E[pLvl] TM (with unemp adj)       = {E_pLvl_tm:.2f}")
        print(f"    E[pLvl] MC sample                  = {E_pLvl_mc:.2f}")
        print(f"    MC/TM ratio = {E_pLvl_mc/E_pLvl_tm:.4f}")


# ─── Experiment 3: MC agent count sweep ──────────────────────────────

def experiment_agentcount_sweep():
    """Test convergence as N grows, with fixed warmup."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 3: MC agent count sweep (fixed warmup=24)")
    print("=" * 70)

    agent_counts = [500, 1000, 2000, 5000, 10000, 20000, 50000]
    n_seeds = 3
    warmup = 24

    # TM reference
    eco_ref, bd_ref = setup_economy_simple(AgentCountTotal=1000)
    base_tm = run_experiment_tm(eco_ref, shock_type="base", dist_aGrid_count=100, neutral_measure=True)
    N_ref = sum(a.AgentCount for a in eco_ref.agents)
    tm_pc = np.mean(base_tm["AggCons"]) / N_ref
    print(f"\nTM reference: AggCons_pc = {tm_pc:.6f}")

    print(f"\n{'N_agents':>10} {'Seeds':>6} {'AggC_pc':>12} {'SE':>10} {'vs TM %':>10} {'Time':>8}")
    print("-" * 60)

    for N in agent_counts:
        t0 = time.time()
        seed_vals = []
        for s in range(n_seeds):
            eco_s, bd_s = setup_economy_simple(AgentCountTotal=N, seed_offset=s * 100)
            tm_d = compute_baseline_tm_data(eco_s, dist_aGrid_count=100, neutral_measure=True, verbose=False)
            tm_init_mc(eco_s, tm_d, warmup=warmup)
            C_s = measure_agg_cons_pc(eco_s, bd_s, n_periods=20)
            seed_vals.append(float(np.mean(C_s)))

        mean_pc = np.mean(seed_vals)
        se_pc = np.std(seed_vals) / np.sqrt(n_seeds) if n_seeds > 1 else 0
        err = 100 * (mean_pc - tm_pc) / tm_pc
        elapsed = time.time() - t0
        print(f"{N:>10d} {n_seeds:>6d} {mean_pc:>12.6f} {se_pc:>10.6f} {err:>+9.3f}% {elapsed:>7.1f}s")


# ─── Experiment 4: TM grid sweep ────────────────────────────────────

def experiment_tm_grid_sweep():
    """Test TM convergence with different mCount values."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 4: TM grid convergence sweep")
    print("=" * 70)

    m_counts = [20, 30, 50, 75, 100, 150, 200]

    eco, bd = setup_economy_simple(AgentCountTotal=1000)

    # Reference: finest grid
    base_ref = run_experiment_tm(eco, shock_type="base", dist_aGrid_count=200, neutral_measure=True)
    N_ref = sum(a.AgentCount for a in eco.agents)
    ref_pc = np.mean(base_ref["AggCons"]) / N_ref

    print(f"\nTM reference (mCount=200): AggCons_pc = {ref_pc:.6f}")
    print(f"\n{'mCount':>8} {'AggC_pc':>12} {'vs ref %':>10} {'Time':>8}")
    print("-" * 42)

    for mc in m_counts:
        t0 = time.time()
        base_r = run_experiment_tm(eco, shock_type="base", dist_aGrid_count=mc, neutral_measure=True)
        pc = np.mean(base_r["AggCons"]) / N_ref
        err = 100 * (pc - ref_pc) / ref_pc
        elapsed = time.time() - t0
        print(f"{mc:>8d} {pc:>12.6f} {err:>+9.4f}% {elapsed:>7.1f}s")


# ─── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    t_total = time.time()

    results_burnin, tm_ref, cold_ref = experiment_burnin_sweep()
    experiment_init_mismatch()
    experiment_agentcount_sweep()
    experiment_tm_grid_sweep()

    print(f"\n{'='*70}")
    print(f"Total elapsed: {time.time()-t_total:.0f}s ({(time.time()-t_total)/60:.1f} min)")
    print(f"{'='*70}")
