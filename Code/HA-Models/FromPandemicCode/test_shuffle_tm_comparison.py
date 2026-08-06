"""Compare shuffled MC to TM at the same parameters.

Runs TM once (deterministic) and MC several times across seeds with
``mc_shuffle=True, income_shuffle=True``, then reports whether the
MC mean agrees with TM within MC sampling error.
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
from tm_methods import (  # noqa: E402
    calculate_NPV,
    compute_baseline_tm_data,
    propagate_experiment_tm,
    run_experiment_tm_nonbase,
    run_ad_tm,
)

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


def build_template():
    BaseType = AggFiscalType(**init_college)
    BaseType.cycles = 0
    BaseType.DiscFac = DiscFacDstns[2].atoms[0][0]

    AggEco = AggregateDemandEconomy(**init_ADEconomy)
    BaseType.get_economy_data(AggEco)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])]
    )
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])],
    )
    BaseType.IncShkDstn[0].seed = 763607780
    BaseType.IncShkDstn[0].reset()
    EmployedIncShkDstn = deepcopy(BaseType.IncShkDstn[0])
    BaseType.IncShkDstn = [
        [BaseType.IncShkDstn[0]]
        + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]
    ]
    BaseType.IncShkDstn_base = BaseType.IncShkDstn
    IncShkDstn_recession = [
        BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))
    ]
    BaseType.IncShkDstn_recession = IncShkDstn_recession
    BaseType.IncShkDstn_recessionUI = IncShkDstn_recession
    EmployedIncShkDstn.atoms[0][1] = (
        EmployedIncShkDstn.atoms[0][1] * BaseType.TaxCutIncFactor
    )
    TaxCutStatesIncShkDstn = (
        [EmployedIncShkDstn]
        + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]
    )
    IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
    for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
        IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
    BaseType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
    BaseType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

    AggEco.agents = [BaseType]
    BaseType.AgentCount = 1
    AggEco.solve()
    return AggEco, BaseType


AggEco_template, BaseType_template = build_template()
act_T = AggEco_template.act_T
base_dict_agg = deepcopy(base_dict)
Rfree = BaseType_template.Rfree[0]
ADelasticity = AggEco_template.demand_ADelasticity

rec_path = (
    list(np.arange(1, AggEco_template.num_experiment_periods + 1) * 2) + [0] * 20
)
for t in range(3):
    rec_path[t] = rec_path[t] + 1

# ============================================================
# TM reference (single deterministic run)
# ============================================================
print("=" * 60)
print("TM reference (dist_aGrid_count=100)")
print("=" * 60)
t0 = time()
dist_aGrid_count = 100
bl_data = compute_baseline_tm_data(AggEco_template, dist_aGrid_count=dist_aGrid_count, verbose=False)
bd = bl_data[0]

base_agent = deepcopy(BaseType_template)
base_agent.update_mrkv_array("base")
base_agent.solve()
tm_base = propagate_experiment_tm(
    base_agent,
    bd["ergodic"],
    [0] * act_T,
    bd["dist_mGrid"],
    bd["E_pLvl"],
    act_T=act_T,
    base_aPol=bd["base_aPol"],
)
AggCons_baseline_tm = np.array(tm_base["AggCons"])

eco_tm_ui = deepcopy(AggEco_template)
eco_tm_ui.switch_shock_type("recessionUI")
eco_tm_ui.solve()
tm_noAD = run_experiment_tm_nonbase(
    eco_tm_ui, "recessionUI", rec_path, bl_data, mCount=dist_aGrid_count, verbose=False
)

eco_tm_ad = deepcopy(AggEco_template)
eco_tm_ad.switch_shock_type("recessionUI")
eco_tm_ad.solve()
tm_AD = run_ad_tm(
    eco_tm_ad,
    "recessionUI",
    rec_path,
    bl_data,
    AggCons_baseline_tm,
    ADelasticity=ADelasticity,
    num_max_iterations=10,
    convergence_tol=0.004,
    mCount=dist_aGrid_count,
    verbose=False,
)

npv_base_C_tm = calculate_NPV(AggCons_baseline_tm, act_T, Rfree)[-1]
npv_noAD_Y_tm = tm_noAD["NPV_AggIncome"][-1]
tm_te_noAD = tm_noAD["NPV_AggCons"][-1] - npv_base_C_tm
tm_te_AD = tm_AD["NPV_AggCons"][-1] - npv_base_C_tm
tm_mult_noAD = tm_te_noAD / (npv_noAD_Y_tm - npv_base_C_tm)
tm_mult_AD = tm_te_AD / (npv_noAD_Y_tm - npv_base_C_tm)
tm_ratio = tm_mult_AD / tm_mult_noAD
print(f"TM te_noAD={tm_te_noAD:.4f}  te_AD={tm_te_AD:.4f}  ratio={tm_ratio:.4f}")
print(f"TM computed in {time() - t0:.0f}s")


# ============================================================
# MC: both shuffles, 8 seeds
# ============================================================
def run_mc_once(
    seed, N_mc, mc_shuffle, income_shuffle,
    init_shuffle=False, markov_shuffle=False, death_shuffle=False,
    stratify_by_wealth=False,
):
    eco_mc = deepcopy(AggEco_template)
    for a in eco_mc.agents:
        a.AgentCount = N_mc
        a.seed = seed
        a.mc_shuffle = bool(mc_shuffle)
        a.income_shuffle = bool(income_shuffle)
        a.init_shuffle = bool(init_shuffle)
        a.markov_shuffle = bool(markov_shuffle)
        a.death_shuffle = bool(death_shuffle)
        a.stratify_by_wealth = bool(stratify_by_wealth)
        a.get_economy_data(eco_mc)
    eco_mc.solve()
    eco_mc.reset()
    for a in eco_mc.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0
    eco_mc.make_history()
    # Capture post-burn-in wealth BEFORE save_state /
    # make_idiosyncratic_shock_histories clobbers state_now['aNrm'] back
    # to the degenerate newborn value.  _hit_with_recession_shock_shuffled
    # reads this attribute as the sort_key for stratify_by_wealth.
    for a in eco_mc.agents:
        a._burnin_aNrm = np.asarray(a.state_now["aNrm"], dtype=float).copy()
    eco_mc.save_state()
    eco_mc.switch_to_counterfactual_mode("base")
    eco_mc.act_T = act_T
    for a in eco_mc.agents:
        a.T_sim = act_T
        a.EconomyMrkvNow_hist = [0] * act_T
    eco_mc.make_idiosyncratic_shock_histories()

    mc_base = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
    eco_mc.store_baseline(mc_base["AggCons"])

    eco_mc_ui_noAD = deepcopy(eco_mc)
    eco_mc_ui_noAD.switch_shock_type("recessionUI")
    eco_mc_ui_noAD.solve()
    d_ui = base_dict_agg.copy()
    d_ui.update(recession_UI_changes)
    d_ui["EconomyMrkv_init"] = rec_path
    mc_noAD = eco_mc_ui_noAD.run_experiment(**d_ui, Full_Output=True)

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

    npv_base_C = calculate_NPV(np.array(mc_base["AggCons"]), act_T, Rfree)[-1]
    npv_noAD_C = calculate_NPV(np.array(mc_noAD["AggCons"]), act_T, Rfree)[-1]
    npv_noAD_Y = calculate_NPV(np.array(mc_noAD["AggIncome"]), act_T, Rfree)[-1]
    npv_AD_C = calculate_NPV(np.array(mc_AD["AggCons"]), act_T, Rfree)[-1]

    te_noAD = npv_noAD_C - npv_base_C
    te_AD = npv_AD_C - npv_base_C
    denom = npv_noAD_Y - npv_base_C
    mult_noAD = te_noAD / denom if denom != 0 else np.nan
    mult_AD = te_AD / denom if denom != 0 else np.nan
    ratio = mult_AD / mult_noAD if mult_noAD != 0 else np.nan
    return te_noAD, te_AD, mult_noAD, mult_AD, ratio


print("\n" + "=" * 60)
print("MC with ONLY mc_shuffle + income_shuffle (no burn-in shuffles)")
print("N=3675, 8 seeds")
print("=" * 60)
t0 = time()
N_mc = 49 * 15 * 5
n_seeds = 8
results = []
for s_idx in range(n_seeds):
    seed = 42000 + s_idx * 17
    r = run_mc_once(
        seed, N_mc,
        mc_shuffle=True,
        income_shuffle=True,
        init_shuffle=False,
        markov_shuffle=False,
        death_shuffle=False,
        stratify_by_wealth=False,
    )
    results.append(r)
    print(
        f"  seed={seed}: te_noAD={r[0]:+9.2f}  te_AD={r[1]:+9.2f}  "
        f"mult_AD={r[3]:+.4f}  ratio={r[4]:.4f}"
    )

te_noAD_arr = np.array([r[0] for r in results])
te_AD_arr = np.array([r[1] for r in results])
mult_noAD_arr = np.array([r[2] for r in results])
mult_AD_arr = np.array([r[3] for r in results])
ratio_arr = np.array([r[4] for r in results])

print(f"\nMC (8 seeds, N={N_mc}):")
print(
    f"  te_noAD:    mean={te_noAD_arr.mean():+9.2f}  std={te_noAD_arr.std():9.2f}  "
    f"SE_mean={te_noAD_arr.std() / np.sqrt(n_seeds):9.2f}"
)
print(
    f"  te_AD:      mean={te_AD_arr.mean():+9.2f}  std={te_AD_arr.std():9.2f}  "
    f"SE_mean={te_AD_arr.std() / np.sqrt(n_seeds):9.2f}"
)
print(
    f"  mult_AD:    mean={mult_AD_arr.mean():+.4f}  std={mult_AD_arr.std():.4f}  "
    f"SE_mean={mult_AD_arr.std() / np.sqrt(n_seeds):.4f}"
)
print(
    f"  ratio:      mean={ratio_arr.mean():.4f}  std={ratio_arr.std():.4f}  "
    f"SE_mean={ratio_arr.std() / np.sqrt(n_seeds):.4f}"
)
print(f"\nMC total time: {time() - t0:.0f}s")

print("\n" + "=" * 60)
print("TM vs MC comparison")
print("=" * 60)
print(f"  TM ratio:                {tm_ratio:.4f}")
print(f"  MC ratio (mean ± SE):    {ratio_arr.mean():.4f} ± {ratio_arr.std() / np.sqrt(n_seeds):.4f}")
diff = abs(ratio_arr.mean() - tm_ratio)
nsigma = diff / (ratio_arr.std() / np.sqrt(n_seeds)) if ratio_arr.std() > 0 else np.inf
print(f"  Difference:              {diff:.4f}  ({nsigma:.1f}σ)")
