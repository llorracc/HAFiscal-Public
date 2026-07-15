"""Diagnose the source of HAFiscal's residual UI-ratio seed variance.

Hypothesis: the outlier seeds (ratio ≈ 2.3 when TM gives ≈ 1.22) come
from finite-N cross-section effects on the population of agents who
end up in state 3 (unemployed, no benefits) during the recession.
Specifically, MPC varies dramatically with wealth near the
borrowing constraint, so the per-seed wealth composition of the
affected set determines the per-seed treatment-effect magnitude.

For each of several seeds, this script runs the MC experiment with
all shuffle flags active and extracts:
  - N_affected: number of agents ever in state 3 (NoB) during the experiment
  - E[aNrm at t=0 | affected]
  - E[aNrm at time of first entering state 3 | affected]
  - Std of both of the above
  - Sample quantiles of wealth within the affected set

Then it correlates these with the seed's te_noAD / te_AD / ratio.
If outlier ratios correlate with outlier affected-set wealth moments,
the hypothesis is confirmed and post-burn-in wealth normalization
is the right fix.
"""
import os
import sys
import numpy as np
from copy import deepcopy
from time import time

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith("FromPandemicCode"):
    os.chdir(cwd + "/Code/HA-Models/FromPandemicCode")
sys.path.insert(0, os.getcwd())

os.environ["MPLBACKEND"] = "Agg"
import matplotlib  # noqa: E402

matplotlib.use("Agg")

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy  # noqa: E402
from HARK.distributions import DiscreteDistribution  # noqa: E402
from Parameters import return_parameters  # noqa: E402
from tm_methods import calculate_NPV  # noqa: E402

# ============================================================
# Setup
# ============================================================
(
    init_dropout,
    init_highschool,
    init_college,
    init_ADEconomy,
    DiscFacDstns,
    DiscFacCount,
    AgentCountTotal,
    base_dict,
    num_max_iterations_solvingAD,
    convergence_tol_solvingAD,
    UBspell_normal,
    num_base_MrkvStates,
    data_EducShares,
    max_recession_duration,
    num_experiment_periods,
    recession_changes,
    UI_changes,
    recession_UI_changes,
    TaxCut_changes,
    recession_TaxCut_changes,
    Check_changes,
    recession_Check_changes,
) = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")

J = num_base_MrkvStates
NOBENEFITS_STATE = J - 1  # last micro state

BaseType_template = AggFiscalType(**init_college)
BaseType_template.cycles = 0
BaseType_template.DiscFac = DiscFacDstns[2].atoms[0][0]

AggEco_template = AggregateDemandEconomy(**init_ADEconomy)
BaseType_template.get_economy_data(AggEco_template)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType_template.IncUnemp])]
)
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]),
    [np.array([1.0]), np.array([BaseType_template.IncUnempNoBenefits])],
)
BaseType_template.IncShkDstn[0].seed = 763607780
BaseType_template.IncShkDstn[0].reset()
EmployedIncShkDstn = deepcopy(BaseType_template.IncShkDstn[0])
BaseType_template.IncShkDstn = [
    [BaseType_template.IncShkDstn[0]]
    + [IncShkDstn_unemp] * UBspell_normal
    + [IncShkDstn_unemp_nobenefits]
]
BaseType_template.IncShkDstn_base = BaseType_template.IncShkDstn
IncShkDstn_recession = [
    BaseType_template.IncShkDstn[0] * (2 * (num_experiment_periods + 1))
]
BaseType_template.IncShkDstn_recession = IncShkDstn_recession
BaseType_template.IncShkDstn_recessionUI = IncShkDstn_recession
EmployedIncShkDstn.atoms[0][1] = (
    EmployedIncShkDstn.atoms[0][1] * BaseType_template.TaxCutIncFactor
)
TaxCutStatesIncShkDstn = (
    [EmployedIncShkDstn]
    + [IncShkDstn_unemp] * UBspell_normal
    + [IncShkDstn_unemp_nobenefits]
)
IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
    IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
BaseType_template.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
BaseType_template.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

AggEco_template.agents = [BaseType_template]
BaseType_template.AgentCount = 1
AggEco_template.solve()

act_T = AggEco_template.act_T
base_dict_agg = deepcopy(base_dict)
Rfree = BaseType_template.Rfree[0]

rec_path = (
    list(np.arange(1, AggEco_template.num_experiment_periods + 1) * 2) + [0] * 20
)
for t in range(3):
    rec_path[t] = rec_path[t] + 1


# ============================================================
# Diagnostic MC run
# ============================================================
def run_mc_with_diagnosis(seed, N_mc):
    """Run one full MC and return both outcome metrics AND affected-set diagnostics."""
    eco_mc = deepcopy(AggEco_template)
    for a in eco_mc.agents:
        a.AgentCount = N_mc
        a.seed = seed
        a.mc_shuffle = True
        a.income_shuffle = True
        a.init_shuffle = True
        a.markov_shuffle = True
        a.death_shuffle = True
        a.get_economy_data(eco_mc)
    eco_mc.solve()
    eco_mc.reset()
    for a in eco_mc.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0
    eco_mc.make_history()
    eco_mc.save_state()
    eco_mc.switch_to_counterfactual_mode("base")
    eco_mc.act_T = act_T
    for a in eco_mc.agents:
        a.T_sim = act_T
        a.EconomyMrkvNow_hist = [0] * act_T
    eco_mc.make_idiosyncratic_shock_histories()

    # Baseline
    mc_base = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
    eco_mc.store_baseline(mc_base["AggCons"])

    # recessionUI (no AD)
    eco_mc_ui = deepcopy(eco_mc)
    eco_mc_ui.switch_shock_type("recessionUI")
    eco_mc_ui.solve()
    d_ui = base_dict_agg.copy()
    d_ui.update(recession_UI_changes)
    d_ui["EconomyMrkv_init"] = rec_path
    mc_noAD = eco_mc_ui.run_experiment(**d_ui, Full_Output=True)

    # recessionUI (with AD) — train then final experiment
    eco_mc_ad = deepcopy(eco_mc)
    eco_mc_ad.switch_shock_type("recessionUI")
    eco_mc_ad.solve_ad_recession(
        num_max_iterations=num_max_iterations_solvingAD,
        convergence_cutoff=convergence_tol_solvingAD,
        shock_type="recessionUI",
        name="recessionUI",
    )
    eco_mc_ad.switch_shock_type("recessionUI")
    eco_mc_ad.restore_ADsolution(name="recessionUI")
    mc_AD = eco_mc_ad.run_experiment(**d_ui, Full_Output=True)

    # ---- Outcome metrics ----
    npv_base_C = calculate_NPV(np.array(mc_base["AggCons"]), act_T, Rfree)[-1]
    npv_noAD_C = calculate_NPV(np.array(mc_noAD["AggCons"]), act_T, Rfree)[-1]
    npv_noAD_Y = calculate_NPV(np.array(mc_noAD["AggIncome"]), act_T, Rfree)[-1]
    npv_AD_C = calculate_NPV(np.array(mc_AD["AggCons"]), act_T, Rfree)[-1]

    te_noAD = npv_noAD_C - npv_base_C
    te_AD = npv_AD_C - npv_base_C
    denom = npv_noAD_Y - npv_base_C
    mult_AD = te_AD / denom if denom != 0 else np.nan
    mult_noAD = te_noAD / denom if denom != 0 else np.nan
    ratio = mult_AD / mult_noAD if mult_noAD != 0 else np.nan

    # ---- Affected-set diagnosis (from recessionUI noAD run) ----
    # Mrkv_hist shape: (T_sim, N_agents). Value = macro*J + micro.
    Mrkv_hist = np.asarray(mc_noAD["Mrkv_hist"])  # (T, N)
    aNrm_all = np.asarray(mc_noAD["aNrm_all"])  # (T, N)
    pLvl_all = np.asarray(mc_noAD["pLvl_all"])  # (T, N)
    cNrm_all = np.asarray(mc_noAD["cNrm_all"])  # (T, N)
    N_total = Mrkv_hist.shape[1]

    # Micro state for every (t, i)
    micro_state = Mrkv_hist % J
    # "Affected" = ever in state NOBENEFITS_STATE at any t
    ever_nobenefits = np.any(micro_state == NOBENEFITS_STATE, axis=0)  # (N,)
    N_affected = int(np.sum(ever_nobenefits))

    # Wealth at t=0 for affected agents
    aNrm_t0 = aNrm_all[0, :]
    pLvl_t0 = pLvl_all[0, :]
    aff_aNrm_t0 = aNrm_t0[ever_nobenefits]
    aff_pLvl_t0 = pLvl_t0[ever_nobenefits]

    # Wealth at the period each affected agent FIRST enters state 3
    t_first_nob = np.full(N_total, -1, dtype=int)
    for i in np.where(ever_nobenefits)[0]:
        idx = np.where(micro_state[:, i] == NOBENEFITS_STATE)[0]
        t_first_nob[i] = int(idx[0])

    # Gather the per-agent wealth at first entry
    aNrm_at_entry = np.array(
        [
            aNrm_all[t_first_nob[i], i] if ever_nobenefits[i] else np.nan
            for i in range(N_total)
        ]
    )
    aff_aNrm_entry = aNrm_at_entry[ever_nobenefits]

    # Also compute cumulative consumption by the affected set under noAD,
    # as a sanity check on where the treatment effect signal lives
    aff_cNrm_mean_over_time = np.mean(cNrm_all[:, ever_nobenefits])

    return {
        "te_noAD": te_noAD,
        "te_AD": te_AD,
        "mult_noAD": mult_noAD,
        "mult_AD": mult_AD,
        "ratio": ratio,
        # Affected-set diagnostics
        "N_affected": N_affected,
        "N_total": N_total,
        "aNrm_t0_mean": float(np.mean(aff_aNrm_t0)) if N_affected > 0 else np.nan,
        "aNrm_t0_std": float(np.std(aff_aNrm_t0)) if N_affected > 0 else np.nan,
        "aNrm_t0_p10": float(np.percentile(aff_aNrm_t0, 10)) if N_affected > 0 else np.nan,
        "aNrm_t0_p50": float(np.percentile(aff_aNrm_t0, 50)) if N_affected > 0 else np.nan,
        "aNrm_entry_mean": float(np.mean(aff_aNrm_entry)) if N_affected > 0 else np.nan,
        "aNrm_entry_p10": float(np.percentile(aff_aNrm_entry, 10)) if N_affected > 0 else np.nan,
        "aNrm_entry_p50": float(np.percentile(aff_aNrm_entry, 50)) if N_affected > 0 else np.nan,
        "pLvl_affected_mean": float(np.mean(aff_pLvl_t0)) if N_affected > 0 else np.nan,
        "cNrm_affected_mean": float(aff_cNrm_mean_over_time),
    }


# ============================================================
# Sweep
# ============================================================
N_mc = 49 * 15 * 5  # 3675 — clean replicate for joint shock AND init dstns
n_seeds = 8

print("=" * 60)
print("HAFiscal UI-ratio variance diagnosis")
print(f"N={N_mc}, all 5 shuffle flags on, {n_seeds} seeds")
print("=" * 60)

all_rows = []
t0 = time()
for s_idx in range(n_seeds):
    seed = 42000 + s_idx * 17
    print(f"  running seed={seed}...", flush=True)
    r = run_mc_with_diagnosis(seed, N_mc)
    r["seed"] = seed
    all_rows.append(r)
print(f"  total {time() - t0:.0f}s")

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 100)
print("PER-SEED RESULTS")
print("=" * 100)
print(
    f"{'seed':>6s} {'ratio':>8s} {'te_noAD':>10s} {'te_AD':>10s} "
    f"{'N_aff':>6s} {'aN_t0_μ':>9s} {'aN_t0_σ':>9s} "
    f"{'aN_ent_μ':>9s} {'aN_ent_p10':>10s} {'aN_ent_p50':>10s}"
)
print("-" * 100)
for r in sorted(all_rows, key=lambda r: r["ratio"]):
    print(
        f"{r['seed']:>6d} {r['ratio']:>8.4f} {r['te_noAD']:>10.1f} {r['te_AD']:>10.1f} "
        f"{r['N_affected']:>6d} {r['aNrm_t0_mean']:>9.4f} {r['aNrm_t0_std']:>9.4f} "
        f"{r['aNrm_entry_mean']:>9.4f} {r['aNrm_entry_p10']:>10.4f} {r['aNrm_entry_p50']:>10.4f}"
    )

# Correlations with ratio outlier-ness
import numpy as np
ratios = np.array([r["ratio"] for r in all_rows])
te_noADs = np.array([r["te_noAD"] for r in all_rows])
N_affs = np.array([r["N_affected"] for r in all_rows])
aN_t0_means = np.array([r["aNrm_t0_mean"] for r in all_rows])
aN_entry_means = np.array([r["aNrm_entry_mean"] for r in all_rows])
aN_entry_p10 = np.array([r["aNrm_entry_p10"] for r in all_rows])
aN_entry_p50 = np.array([r["aNrm_entry_p50"] for r in all_rows])

print("\n" + "=" * 60)
print("CORRELATIONS with seed ratio")
print("=" * 60)
for name, arr in [
    ("N_affected", N_affs),
    ("aN_t0_mean", aN_t0_means),
    ("aN_entry_mean", aN_entry_means),
    ("aN_entry_p10", aN_entry_p10),
    ("aN_entry_p50", aN_entry_p50),
    ("te_noAD", te_noADs),
]:
    if np.std(arr) > 0:
        corr = np.corrcoef(ratios, arr)[0, 1]
        print(f"  corr(ratio, {name:<18s}) = {corr:+.4f}")
    else:
        print(f"  corr(ratio, {name:<18s}) = N/A (zero variance)")

# Identify outliers vs non-outliers
ratio_median = np.median(ratios)
ratio_mad = np.median(np.abs(ratios - ratio_median))
is_outlier = np.abs(ratios - ratio_median) > 3 * ratio_mad
n_out = int(np.sum(is_outlier))
print(f"\nOutlier seeds (|ratio - median| > 3 × MAD): {n_out} / {n_seeds}")
if n_out > 0 and n_out < n_seeds:
    print("  Outliers:    ", [r["seed"] for r, o in zip(all_rows, is_outlier) if o])
    print("  Non-outliers:", [r["seed"] for r, o in zip(all_rows, is_outlier) if not o])
    # Compare affected-set moments
    aff_out = np.array([r["aNrm_entry_mean"] for r, o in zip(all_rows, is_outlier) if o])
    aff_in = np.array(
        [r["aNrm_entry_mean"] for r, o in zip(all_rows, is_outlier) if not o]
    )
    N_out = np.array([r["N_affected"] for r, o in zip(all_rows, is_outlier) if o])
    N_in = np.array([r["N_affected"] for r, o in zip(all_rows, is_outlier) if not o])
    print(f"  N_affected outliers: {N_out}")
    print(f"  N_affected normal:   {N_in}")
    print(
        f"  aN_entry_mean outliers: μ={np.mean(aff_out):.4f} σ={np.std(aff_out):.4f}"
    )
    print(
        f"  aN_entry_mean normal:   μ={np.mean(aff_in):.4f} σ={np.std(aff_in):.4f}"
    )
