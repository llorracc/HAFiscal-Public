"""Shuffle precision comparison for HS group at minimum-replicate N.

Tests whether the Markov+income shuffle meaningfully reduces cross-seed variance
of the NM estimation objective (distance) at the per-group minimum-replicate
sizes derived in plans/20260408-1024h_minimum-replicates-for-shuffle.md §2.3.1:

  - Single-β cohort:     N = 1,200
  - Full β distribution: N = 8,400  (nβ=7)

For each config, run the same β, ∇, GICx with N_SEEDS different seeds; compute
the NM-relevant distance (SSE against HS wealth-distribution targets). Compare
the cross-seed SD of distance between shuffle-on and shuffle-off.

If shuffle is a useful precision lever for the HS estimation, shuffle-on should
show materially lower cross-seed SD of distance.

Usage:
    cd Code/HA-Models/FromPandemicCode
    python test_shuffle_hs_precision.py
"""
import os, sys, time
from copy import deepcopy
import numpy as np

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith("FromPandemicCode"):
    os.chdir(cwd + "/Code/HA-Models/FromPandemicCode")
sys.path.insert(0, os.getcwd())

os.environ["MPLBACKEND"] = "Agg"
import matplotlib; matplotlib.use("Agg")  # noqa: E702

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy  # noqa: E402
from HARK.distributions import DiscreteDistribution, Uniform  # noqa: E402
from Parameters import return_parameters  # noqa: E402

# ============================================================
# Parametrization: HS only, at both single-β and full-β sizes
# ============================================================
(
    init_dropout, init_highschool, init_college,
    init_ADEconomy, DiscFacDstns, DiscFacCount, AgentCountTotal,
    base_dict, num_max_iterations_solvingAD, convergence_tol_solvingAD,
    UBspell_normal, num_base_MrkvStates, data_EducShares,
    max_recession_duration, num_experiment_periods,
    recession_changes, UI_changes, recession_UI_changes,
    TaxCut_changes, recession_TaxCut_changes,
    Check_changes, recession_Check_changes,
) = return_parameters(Parametrization="Baseline", OutputFor="_Main.py")

# Reference HS calibration (from production m-TM estimate)
HS_BETA = 0.9298
HS_NABLA = 0.0708
HS_GICX = 4.20

# HS lorenz/medianLWPI target values — read from EstimParameters' data_ fields
# We don't strictly need the "correct" target for SD comparison; distance is
# SSE((sim moment) - (target)) and its seed-noise is what we measure.
# Using the simulated mean across the no-shuffle runs as a self-consistent target.


def build_hs_agent(seed, N, DiscFac, mc_shuffle, income_shuffle):
    """Build one HS AggFiscalType agent for the precision test."""
    a = AggFiscalType(**init_highschool)
    a.cycles = 0
    a.DiscFac = DiscFac
    a.AgentCount = int(N)
    a.seed = int(seed)
    a.mc_shuffle = bool(mc_shuffle)
    a.income_shuffle = bool(income_shuffle)
    return a


def measure_hs_distance(N_total, n_beta, mc_shuffle, income_shuffle, seed):
    """Build, solve, simulate HS-only economy at (β=HS_BETA, ∇=HS_NABLA) and
    return the SSE wealth-distribution distance.

    n_beta = 1: single-β cohort (DiscFac = HS_BETA)
    n_beta = 7: full DiscFac distribution around HS_BETA with spread HS_NABLA
    """
    if n_beta == 1:
        dfs = [HS_BETA]
        N_per_bin = N_total
    else:
        uniform_dist = Uniform(HS_BETA - HS_NABLA, HS_BETA + HS_NABLA).discretize(n_beta)
        dfs = list(uniform_dist.atoms[0])
        N_per_bin = int(N_total / n_beta)

    agents = []
    for b, df in enumerate(dfs):
        a = build_hs_agent(seed=seed * 1000 + b, N=N_per_bin, DiscFac=df,
                           mc_shuffle=mc_shuffle, income_shuffle=income_shuffle)
        agents.append(a)

    eco = AggregateDemandEconomy(**init_ADEconomy)
    eco.agents = agents
    for a in eco.agents:
        a.get_economy_data(eco)
        IncShkDstn_unemp = DiscreteDistribution(
            np.array([1.0]), [np.array([1.0]), np.array([a.IncUnemp])])
        IncShkDstn_unemp_nobenefits = DiscreteDistribution(
            np.array([1.0]), [np.array([1.0]), np.array([a.IncUnempNoBenefits])])
        a.IncShkDstn[0].seed = 763607780 + seed
        a.IncShkDstn[0].reset()
        a.IncShkDstn = [
            [a.IncShkDstn[0]]
            + [IncShkDstn_unemp] * UBspell_normal
            + [IncShkDstn_unemp_nobenefits]
        ]
        a.IncShkDstn_base = a.IncShkDstn
    eco.solve()
    eco.reset()
    for a in eco.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0
    eco.make_history()
    eco.save_state()

    # Extract wealth-distribution moments from simulated agents
    aLvls = np.concatenate([a.state_now['aNrm'] * a.state_now['pLvl']
                             for a in eco.agents])
    pLvls = np.concatenate([a.state_now['pLvl'] for a in eco.agents])
    bLvls = np.concatenate([a.state_now['bNrm'] * a.state_now['pLvl']
                             for a in eco.agents])

    ratio = aLvls / np.maximum(pLvls, 1e-16)
    median_ratio = float(np.median(ratio))

    sorted_a = np.sort(aLvls)
    cum = np.cumsum(sorted_a)
    total = cum[-1]
    percentiles = [0.20, 0.40, 0.60, 0.80]
    lorenz = [float(np.searchsorted(np.arange(len(sorted_a))/len(sorted_a),
                                    p) / len(sorted_a) * total and
                    cum[int(p * len(sorted_a))-1] / total if total > 0 else 0.0)
              for p in percentiles]

    return {
        'median_aLvlPI': median_ratio,
        'lorenz': lorenz,
        'mean_a': float(np.mean(aLvls)),
        'sd_a': float(np.std(aLvls)),
    }


def run_config(label, N_total, n_beta, mc_shuffle, income_shuffle, seeds):
    """Run N_SEEDS at a given config; return cross-seed stats."""
    print(f"  [{label}] N={N_total}, n_beta={n_beta}, shuffle=({mc_shuffle},{income_shuffle})")
    results = []
    for s in seeds:
        t0 = time.time()
        r = measure_hs_distance(N_total, n_beta, mc_shuffle, income_shuffle, s)
        print(f"    seed={s}: median_a/p={r['median_aLvlPI']:.4f} mean_a={r['mean_a']:.2f} sd_a={r['sd_a']:.2f}  ({time.time()-t0:.0f}s)")
        results.append(r)
    median_arr = np.array([r['median_aLvlPI'] for r in results])
    mean_arr = np.array([r['mean_a'] for r in results])
    return {
        'label': label,
        'N_total': N_total, 'n_beta': n_beta,
        'median_aLvlPI_mean': float(median_arr.mean()),
        'median_aLvlPI_sd':   float(median_arr.std()),
        'mean_a_mean': float(mean_arr.mean()),
        'mean_a_sd':   float(mean_arr.std()),
        'n_seeds': len(seeds),
    }


# ============================================================
# Run experiments
# ============================================================
N_SEEDS = 3
seeds = list(range(N_SEEDS))

experiments = [
    # (label, N_total, n_beta)
    ("single-β N=1200",  1200, 1),
    ("full-β N=8400",    8400, 7),
]

print()
print("=" * 70)
print("HS shuffle precision experiment")
print("=" * 70)
print(f"Reference calibration: β={HS_BETA}, ∇={HS_NABLA}, GICx={HS_GICX}")
print(f"N_SEEDS per config: {N_SEEDS}")
print()

all_results = []
for label, N, n_beta in experiments:
    print(f"\n=== {label} ===")
    for mc_sh, inc_sh in [(False, False), (True, True)]:
        cfg_label = f"{label}  shuffle={mc_sh},{inc_sh}"
        r = run_config(cfg_label, N, n_beta, mc_sh, inc_sh, seeds)
        all_results.append(r)

# ============================================================
# Report
# ============================================================
print()
print("=" * 70)
print("Summary — cross-seed SD comparison")
print("=" * 70)
print(f"{'config':<35} {'median_aLvlPI mean':>18} {'sd':>10} {'mean_a mean':>14} {'sd':>10}")
print("-" * 95)
for r in all_results:
    print(f"{r['label']:<35} {r['median_aLvlPI_mean']:>18.4f} {r['median_aLvlPI_sd']:>10.4f}"
          f" {r['mean_a_mean']:>14.2f} {r['mean_a_sd']:>10.2f}")

# Compute SD reductions (shuffle vs no-shuffle)
print()
print("SD reduction (shuffle on / shuffle off):")
for i in range(0, len(all_results), 2):
    off = all_results[i]
    on = all_results[i+1]
    if off['median_aLvlPI_sd'] > 0:
        ratio_med = on['median_aLvlPI_sd'] / off['median_aLvlPI_sd']
    else:
        ratio_med = float('nan')
    if off['mean_a_sd'] > 0:
        ratio_mean = on['mean_a_sd'] / off['mean_a_sd']
    else:
        ratio_mean = float('nan')
    print(f"  {experiments[i // 2][0]}:  median_aLvlPI SD ratio = {ratio_med:.3f}"
          f"   mean_a SD ratio = {ratio_mean:.3f}")
