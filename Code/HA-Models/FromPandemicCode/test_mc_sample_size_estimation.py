"""Estimate MC sample sizes needed for 2% and 1% SE on the UI AD ratio.

Runs MC at multiple N values (clean replicates of 49), measures
seed-to-seed std of the UI AD amplification ratio, and extrapolates
the relationship std ∝ 1/√N to project the N required for target SEs.

Configuration: mc_shuffle=True, income_shuffle=True (the minimal
configuration that matches TM at large N). No burn-in shuffles
(init_shuffle, markov_shuffle, death_shuffle all False) since those
were shown to increase rather than decrease bias.

Output: a table suitable for inclusion in a methods appendix.
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
import matplotlib

matplotlib.use("Agg")

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import (
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
    init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
    DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
    convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
    data_EducShares, max_recession_duration, num_experiment_periods,
    recession_changes, UI_changes, recession_UI_changes,
    TaxCut_changes, recession_TaxCut_changes,
    Check_changes, recession_Check_changes,
) = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")

J = num_base_MrkvStates

BaseType_template = AggFiscalType(**init_college)
BaseType_template.cycles = 0
BaseType_template.DiscFac = DiscFacDstns[2].atoms[0][0]

AggEco_template = AggregateDemandEconomy(**init_ADEconomy)
BaseType_template.get_economy_data(AggEco_template)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType_template.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType_template.IncUnempNoBenefits])])
BaseType_template.IncShkDstn[0].seed = 763607780
BaseType_template.IncShkDstn[0].reset()
EmployedIncShkDstn = deepcopy(BaseType_template.IncShkDstn[0])
BaseType_template.IncShkDstn = [
    [BaseType_template.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal
    + [IncShkDstn_unemp_nobenefits]]
BaseType_template.IncShkDstn_base = BaseType_template.IncShkDstn
IncShkDstn_recession = [BaseType_template.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
BaseType_template.IncShkDstn_recession = IncShkDstn_recession
BaseType_template.IncShkDstn_recessionUI = IncShkDstn_recession
EmployedIncShkDstn.atoms[0][1] *= BaseType_template.TaxCutIncFactor
TaxCutStatesIncShkDstn = (
    [EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits])
IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates):
    IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
BaseType_template.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
BaseType_template.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

AggEco_template.agents = [BaseType_template]
BaseType_template.AgentCount = 1
AggEco_template.solve()

act_T = AggEco_template.act_T
base_dict_agg = deepcopy(base_dict)
Rfree = BaseType_template.Rfree[0]
ADelasticity = AggEco_template.demand_ADelasticity

rec_path = list(np.arange(1, AggEco_template.num_experiment_periods + 1) * 2) + [0] * 20
for t in range(3):
    rec_path[t] = rec_path[t] + 1


# ============================================================
# TM reference
# ============================================================
print("Computing TM reference (mCount=200)...")
t0_tm = time()
mCount = 200
bl_data = compute_baseline_tm_data(AggEco_template, mCount=mCount, verbose=False)
bd = bl_data[0]
base_agent = deepcopy(BaseType_template)
base_agent.update_mrkv_array("base")
base_agent.solve()
tm_base = propagate_experiment_tm(
    base_agent, bd["ergodic"], [0] * act_T, bd["dist_mGrid"],
    bd["E_pLvl"], act_T=act_T, base_aPol=bd["base_aPol"])
AggCons_baseline_tm = np.array(tm_base["AggCons"])

eco_tm_ui = deepcopy(AggEco_template)
eco_tm_ui.switch_shock_type("recessionUI")
eco_tm_ui.solve()
tm_noAD = run_experiment_tm_nonbase(
    eco_tm_ui, "recessionUI", rec_path, bl_data, mCount=mCount, verbose=False)

eco_tm_ad = deepcopy(AggEco_template)
eco_tm_ad.switch_shock_type("recessionUI")
eco_tm_ad.solve()
tm_AD = run_ad_tm(
    eco_tm_ad, "recessionUI", rec_path, bl_data, AggCons_baseline_tm,
    ADelasticity=ADelasticity, num_max_iterations=10,
    convergence_tol=0.004, mCount=mCount, verbose=False)

npv_base_C_tm = calculate_NPV(AggCons_baseline_tm, act_T, Rfree)[-1]
npv_noAD_Y_tm = tm_noAD["NPV_AggIncome"][-1]
tm_te_noAD = tm_noAD["NPV_AggCons"][-1] - npv_base_C_tm
tm_te_AD = tm_AD["NPV_AggCons"][-1] - npv_base_C_tm
tm_mult_noAD = tm_te_noAD / (npv_noAD_Y_tm - npv_base_C_tm)
tm_mult_AD = tm_te_AD / (npv_noAD_Y_tm - npv_base_C_tm)
tm_ratio = tm_mult_AD / tm_mult_noAD
print(f"TM ratio (mCount={mCount}): {tm_ratio:.4f}")
print(f"TM computed in {time() - t0_tm:.0f}s")


# ============================================================
# MC helper
# ============================================================
def run_mc_once(seed, N_mc):
    eco_mc = deepcopy(AggEco_template)
    for a in eco_mc.agents:
        a.AgentCount = N_mc
        a.seed = seed
        a.mc_shuffle = True
        a.income_shuffle = True
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

    mc_base = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
    eco_mc.store_baseline(mc_base["AggCons"])

    eco_ui = deepcopy(eco_mc)
    eco_ui.switch_shock_type("recessionUI")
    eco_ui.solve()
    d_ui = base_dict_agg.copy()
    d_ui.update(recession_UI_changes)
    d_ui["EconomyMrkv_init"] = rec_path
    mc_noAD = eco_ui.run_experiment(**d_ui, Full_Output=True)

    eco_ad = deepcopy(eco_mc)
    eco_ad.switch_shock_type("recessionUI")
    eco_ad.solve_ad_recession(
        num_max_iterations=num_max_iterations_solvingAD,
        convergence_cutoff=convergence_tol_solvingAD,
        shock_type="recessionUI", name="recessionUI")
    eco_ad.switch_shock_type("recessionUI")
    eco_ad.restore_ADsolution(name="recessionUI")
    mc_AD = eco_ad.run_experiment(**d_ui, Full_Output=True)

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
    return ratio


# ============================================================
# N sweep
# ============================================================
# N values as multiples of 49 (clean replicate for 7x7 joint
# employed shock distribution). Logarithmically spaced from
# ~2000 to ~20000.
N_values = [49 * k for k in [40, 80, 160, 320]]
# = [1960, 3920, 7840, 15680]

n_seeds_per_N = 8
seed_base = 42000
seed_step = 17

print("\n" + "=" * 70)
print("MC SAMPLE SIZE SWEEP")
print(f"Config: mc_shuffle=True, income_shuffle=True (2 flags)")
print(f"Seeds per N: {n_seeds_per_N}")
print(f"TM reference ratio: {tm_ratio:.4f}")
print("=" * 70)

results = {}
for N_mc in N_values:
    print(f"\n--- N = {N_mc} (49 × {N_mc // 49}) ---")
    t0 = time()
    ratios = []
    for s_idx in range(n_seeds_per_N):
        seed = seed_base + s_idx * seed_step
        r = run_mc_once(seed, N_mc)
        ratios.append(r)
        print(f"    seed={seed}: ratio={r:.4f}")
    ratios = np.array(ratios)
    elapsed = time() - t0
    results[N_mc] = {
        "ratios": ratios,
        "mean": float(ratios.mean()),
        "std": float(ratios.std()),
        "se_mean": float(ratios.std() / np.sqrt(n_seeds_per_N)),
        "elapsed": elapsed,
    }
    print(
        f"    mean={ratios.mean():.4f}, std={ratios.std():.4f}, "
        f"SE_mean={ratios.std() / np.sqrt(n_seeds_per_N):.4f}, "
        f"time={elapsed:.0f}s"
    )


# ============================================================
# Fit std ∝ 1/√N and extrapolate
# ============================================================
Ns = np.array(sorted(results.keys()))
stds = np.array([results[n]["std"] for n in Ns])
means = np.array([results[n]["mean"] for n in Ns])

# Fit: std = C / sqrt(N)
# In log space: log(std) = log(C) - 0.5 * log(N)
valid = stds > 0
if valid.sum() >= 2:
    log_N = np.log(Ns[valid])
    log_std = np.log(stds[valid])
    # Fit log(std) = a + b * log(N)
    coeffs = np.polyfit(log_N, log_std, 1)
    b_fit = coeffs[0]
    C_fit = np.exp(coeffs[1])
    # Theoretical: b = -0.5 for std ∝ 1/√N
    print(f"\nFit: std ≈ {C_fit:.2f} / N^{-b_fit:.3f}")
    print(f"  (theoretical exponent for 1/√N: 0.500)")
else:
    b_fit = -0.5
    C_fit = stds[0] * np.sqrt(Ns[0]) if len(stds) > 0 else 1.0
    print(f"\nInsufficient data for fit; using C = {C_fit:.2f}")


def N_for_target_se(target_se, C, b):
    """Solve C / N^(-b) = target_se for N."""
    return (C / target_se) ** (1.0 / (-b))


N_2pct = N_for_target_se(0.02, C_fit, b_fit)
N_1pct = N_for_target_se(0.01, C_fit, b_fit)

# For single-seed: SE = std. For k seeds: SE = std / sqrt(k).
# Report both "N per seed for k-seed average" and "single large N".

print("\n" + "=" * 70)
print("PROJECTED SAMPLE SIZES FOR TARGET STANDARD ERRORS")
print("=" * 70)
print(f"\nModel: single college type, 3-quarter recession, recessionUI AD")
print(f"TM reference ratio: {tm_ratio:.4f}")
print(f"Empirical fit: std(ratio) ≈ {C_fit:.2f} / N^{-b_fit:.3f}")
print(f"  (theoretical 1/√N exponent: 0.500)")
print()
print(f"{'Target SE':>12s}  {'N (1 seed)':>12s}  {'N (4 seeds)':>12s}  {'N (16 seeds)':>13s}  {'Wall-clock est.':>16s}")
print("-" * 70)
for target, label in [(0.02, "2%"), (0.01, "1%")]:
    N_1 = int(np.ceil(N_for_target_se(target, C_fit, b_fit)))
    N_4 = int(np.ceil(N_for_target_se(target * 2, C_fit, b_fit)))  # SE = std/2
    N_16 = int(np.ceil(N_for_target_se(target * 4, C_fit, b_fit)))  # SE = std/4
    # Rough wall-clock: ~100s per 4000 agents per seed, scaling linearly
    wc_1 = N_1 / 4000 * 100
    wc_4 = N_4 / 4000 * 100 * 4
    wc_16 = N_16 / 4000 * 100 * 16
    print(
        f"  SE = {label:>3s}    {N_1:>12,d}  {N_4:>12,d}  {N_16:>13,d}  "
        f"{'~' + str(int(wc_1 / 3600)) + 'h (1 seed)':>16s}"
    )

print()
print("For comparison:")
print(f"  TM at mCount=200: ratio = {tm_ratio:.4f} (deterministic, ~50s)")
print(f"  Paper uses 21 types × {max_recession_duration} recession durations × 4 shock types")
print(f"  → multiply single-type N by 21 for full-model MC agent count")
print(f"  → multiply wall-clock by {max_recession_duration} × 4 for all experiments")


# ============================================================
# Summary table for the document
# ============================================================
print("\n\n" + "=" * 70)
print("EMPIRICAL DATA TABLE (for methods appendix)")
print("=" * 70)
print()
print(f"{'N':>8s}  {'k':>4s}  {'mean(ratio)':>12s}  {'std(ratio)':>12s}  "
      f"{'SE_mean':>10s}  {'vs TM (σ)':>10s}  {'wall-clock':>12s}")
print("-" * 75)
for N_mc in Ns:
    r = results[N_mc]
    diff_sigma = abs(r["mean"] - tm_ratio) / r["se_mean"] if r["se_mean"] > 0 else np.inf
    wc_str = f"{r['elapsed']:.0f}s" if r["elapsed"] < 3600 else f"{r['elapsed']/3600:.1f}h"
    print(
        f"{N_mc:>8d}  {n_seeds_per_N:>4d}  {r['mean']:>12.4f}  {r['std']:>12.4f}  "
        f"{r['se_mean']:>10.4f}  {diff_sigma:>10.1f}  {wc_str:>12s}"
    )
print(f"{'TM':>8s}  {'—':>4s}  {tm_ratio:>12.4f}  {'0':>12s}  {'0':>10s}  {'—':>10s}  {'~50s':>12s}")
print()
print(f"Fit: std(ratio) = {C_fit:.2f} / N^{{{-b_fit:.3f}}}")
print(f"Projected N for SE = 2%: {int(N_2pct):,d} agents (single seed)")
print(f"Projected N for SE = 1%: {int(N_1pct):,d} agents (single seed)")
print()
print("Notes:")
print("- Single college type with point discount factor (HAFiscal Reduced_Run)")
print("- 3-quarter recession, recessionUI policy, AD feedback (κ=0.3)")
print("- mc_shuffle=True, income_shuffle=True for variance reduction")
print("- Ratio = NPV(ΔC_AD) / NPV(ΔC_noAD), the AD amplification factor")
print(f"- TM reference: ratio = {tm_ratio:.4f} at mCount=200 (converged to 4 decimal places)")
print("- Full HAFiscal model has 21 types; multiply N by 21 for total agent count")
