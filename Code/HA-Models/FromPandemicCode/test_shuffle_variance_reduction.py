"""Measure MC seed-to-seed variance reduction from enabling shuffle flags.

Runs the HAFiscal single-college-type recessionUI AD experiment across
multiple seeds, with four configurations:

  (1) baseline:        mc_shuffle=False, income_shuffle=False
  (2) mc_shuffle only: mc_shuffle=True,  income_shuffle=False
  (3) income only:     mc_shuffle=False, income_shuffle=True
  (4) both:            mc_shuffle=True,  income_shuffle=True

For each config, reports seed-to-seed mean and std of the UI AD
multiplier.  If the sub-RNG-isolated shuffle machinery works as
expected, configs (2) and (4) should show dramatically lower
seed-to-seed SD than config (1) — that's the whole point of doing
this: at paper-N it's impossible to get tight-enough MC estimates
of the UI multiplier without CRN.
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
# Setup: single college type, 3-quarter recession
# ============================================================
print("=" * 60)
print("HAFiscal shuffle variance-reduction test")
print("=" * 60)

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
BaseType_template.AgentCount = 1  # placeholder for solve
AggEco_template.solve()

act_T = AggEco_template.act_T
base_dict_agg = deepcopy(base_dict)
Rfree = BaseType_template.Rfree[0]

# 3-quarter recession
rec_path = (
    list(np.arange(1, AggEco_template.num_experiment_periods + 1) * 2) + [0] * 20
)
for t in range(3):
    rec_path[t] = rec_path[t] + 1


# ============================================================
# MC helper: one full run (baseline + recessionUI AD) at fixed seed
# ============================================================
def run_mc_once(seed, N_mc, mc_shuffle, income_shuffle):
    """Run one full MC: baseline + recessionUI AD at given seed/flags.

    Returns the UI AD multiplier (NPV_C_AD / NPV_Y_noAD) and the
    treatment effect (NPV_C_AD - NPV_C_base).
    """
    eco_mc = deepcopy(AggEco_template)
    for a in eco_mc.agents:
        a.AgentCount = N_mc
        a.seed = seed
        a.mc_shuffle = bool(mc_shuffle)
        a.income_shuffle = bool(income_shuffle)
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

    # MC baseline
    mc_base = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
    eco_mc.store_baseline(mc_base["AggCons"])

    # MC non-AD recessionUI (to get the fixed denominator NPV_Y_noAD)
    eco_mc_ui_noAD = deepcopy(eco_mc)
    eco_mc_ui_noAD.switch_shock_type("recessionUI")
    eco_mc_ui_noAD.solve()
    d_ui = base_dict_agg.copy()
    d_ui.update(recession_UI_changes)
    d_ui["EconomyMrkv_init"] = rec_path
    mc_noAD = eco_mc_ui_noAD.run_experiment(**d_ui, Full_Output=True)

    # MC AD: solve_ad_recession + final experiment
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

    # Multipliers: canonical formula uses NPV_AggIncome from noAD
    npv_base_C = calculate_NPV(np.array(mc_base["AggCons"]), act_T, Rfree)[-1]
    npv_noAD_C = calculate_NPV(np.array(mc_noAD["AggCons"]), act_T, Rfree)[-1]
    npv_noAD_Y = calculate_NPV(np.array(mc_noAD["AggIncome"]), act_T, Rfree)[-1]
    npv_AD_C = calculate_NPV(np.array(mc_AD["AggCons"]), act_T, Rfree)[-1]

    te_noAD = npv_noAD_C - npv_base_C
    te_AD = npv_AD_C - npv_base_C
    mult_noAD = te_noAD / (npv_noAD_Y - npv_base_C) if npv_noAD_Y != npv_base_C else np.nan
    mult_AD = te_AD / (npv_noAD_Y - npv_base_C) if npv_noAD_Y != npv_base_C else np.nan

    return {
        "te_noAD": te_noAD,
        "te_AD": te_AD,
        "mult_noAD": mult_noAD,
        "mult_AD": mult_AD,
        "ratio": mult_AD / mult_noAD if mult_noAD != 0 else np.nan,
    }


# ============================================================
# Sweep: 4 seeds × 4 configs at N_mc = 4000
# ============================================================
N_mc = 4000
n_seeds = 4
configs = [
    ("baseline (no shuffle)", False, False),
    ("mc_shuffle only", True, False),
    ("income_shuffle only", False, True),
    ("both shuffles", True, True),
]

print(f"\nN={N_mc}, {n_seeds} seeds per config, single college type\n")

results = {}
for label, mc_sh, inc_sh in configs:
    print(f"--- {label} ---")
    t0 = time()
    runs = []
    for s_idx in range(n_seeds):
        seed = 42000 + s_idx * 17
        r = run_mc_once(seed, N_mc, mc_sh, inc_sh)
        runs.append(r)
        print(
            f"    seed={seed}: te_AD={r['te_AD']:.2f}, mult_AD={r['mult_AD']:.4f}, "
            f"ratio={r['ratio']:.4f}"
        )
    results[label] = runs
    print(f"    ({time() - t0:.0f}s)")

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 70)
print("SEED-TO-SEED VARIANCE SUMMARY (UI AD treatment effect, single HS type)")
print("=" * 70)
print(
    f"  {'config':<25s}  {'mean(te_AD)':>12s}  {'std(te_AD)':>12s}  "
    f"{'mean(ratio)':>12s}  {'std(ratio)':>12s}"
)
print("  " + "-" * 66)
for label, _, _ in configs:
    runs = results[label]
    tes = np.array([r["te_AD"] for r in runs])
    ratios = np.array([r["ratio"] for r in runs])
    print(
        f"  {label:<25s}  {tes.mean():12.2f}  {tes.std():12.2f}  "
        f"{ratios.mean():12.4f}  {ratios.std():12.4f}"
    )

print("\nVariance reduction factors (baseline → shuffled):")
base_runs = results["baseline (no shuffle)"]
base_te_var = np.var([r["te_AD"] for r in base_runs])
base_ratio_var = np.var([r["ratio"] for r in base_runs])
for label, _, _ in configs[1:]:
    runs = results[label]
    te_var = np.var([r["te_AD"] for r in runs])
    ratio_var = np.var([r["ratio"] for r in runs])
    te_red = base_te_var / max(te_var, 1e-30)
    r_red = base_ratio_var / max(ratio_var, 1e-30)
    print(f"  {label:<25s}  te_AD: {te_red:8.1f}x   ratio: {r_red:8.1f}x")
