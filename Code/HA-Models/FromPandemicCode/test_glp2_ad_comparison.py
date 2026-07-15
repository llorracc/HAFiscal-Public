"""
GLP-2 AD comparison harness: runs both TM AD and MC AD on a minimal problem
to diagnose zero-amplification in TM AD.

Single college type, point discount factor, fixed 3-quarter recession,
Reduced_Run parametrization.

Sections:
  1. Setup (shared)
  2. TM baseline + non-AD
  3. TM AD (should show amplification after Channel A fix)
  4. Unit diagnostic: one-period AggDemandFac effect
  5. MC AD ground truth (80K agents)
  6. Comparison table
"""

import os, sys, numpy as np
from time import time
from copy import deepcopy

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())

os.environ['MPLBACKEND'] = 'Agg'
import matplotlib; matplotlib.use('Agg')

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import (
    compute_baseline_tm_data, propagate_experiment_tm,
    run_experiment_tm_nonbase, run_ad_tm, calculate_NPV,
    build_experiment_period_tm, compute_period_aggregates_tm,
    _scaled_employed_joint_inc_dstn,
)

# ============================================================
# 1. Setup (single college type, point beta, Reduced_Run)
# ============================================================
print("=" * 60)
print("GLP-2: TM AD vs MC AD comparison")
print("=" * 60)

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

J = num_base_MrkvStates

# Single college type
BaseType = AggFiscalType(**init_college)
BaseType.cycles = 0
BaseType.DiscFac = DiscFacDstns[2].atoms[0][0]  # point estimate

AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

# Set up IncShkDstn (same as Simulate.py / GLP-1)
IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])
BaseType.IncShkDstn[0].seed = 763607780
BaseType.IncShkDstn[0].reset()
EmployedIncShkDstn = deepcopy(BaseType.IncShkDstn[0])
BaseType.IncShkDstn = [[BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
BaseType.IncShkDstn_base = BaseType.IncShkDstn
IncShkDstn_recession = [BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
BaseType.IncShkDstn_recession = IncShkDstn_recession
BaseType.IncShkDstn_recessionUI = IncShkDstn_recession
EmployedIncShkDstn.atoms[0][1] = EmployedIncShkDstn.atoms[0][1] * BaseType.TaxCutIncFactor
TaxCutStatesIncShkDstn = [EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]
IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
    IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
BaseType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
BaseType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

AggEco.agents = [BaseType]
BaseType.AgentCount = 1  # placeholder for solve

t0_total = time()
print("Solving...", flush=True)
AggEco.solve()
t_solve = time() - t0_total
print(f"Solve: {t_solve:.1f}s")

act_T = AggEco.act_T
base_dict_agg = deepcopy(base_dict)
Rfree = BaseType.Rfree[0]
ADelasticity = AggEco.demand_ADelasticity

# Fixed 3-quarter recession path
rec_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20
for t in range(3):
    rec_path[t] = rec_path[t] + 1

# ============================================================
# 2. TM baseline + non-AD
# ============================================================
print("\n--- TM baseline ---")
t0 = time()
mCount = 100
bl_data = compute_baseline_tm_data(AggEco, mCount=mCount, verbose=True)
bd = bl_data[0]

# Base propagation (Cratio=1, macro=0)
base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
tm_base = propagate_experiment_tm(
    base_agent, bd['ergodic'], [0] * act_T, bd['dist_mGrid'],
    bd['E_pLvl'], act_T=act_T, base_aPol=bd['base_aPol'])
AggCons_baseline = np.array(tm_base['AggCons'])

print(f"  Baseline AggCons mean = {np.mean(AggCons_baseline):.6f}")
print(f"  Baseline computed in {time()-t0:.1f}s")

# Non-AD recessionUI experiment
print("\n--- TM non-AD (recessionUI) ---")
t0 = time()
eco_ui = deepcopy(AggEco)
eco_ui.switch_shock_type('recessionUI')
eco_ui.solve()
tm_noAD = run_experiment_tm_nonbase(
    eco_ui, 'recessionUI', rec_path, bl_data, mCount=mCount, verbose=True)
npv_noAD_C = tm_noAD['NPV_AggCons'][-1]
npv_noAD_Y = tm_noAD['NPV_AggIncome'][-1]
npv_base_C = calculate_NPV(AggCons_baseline, act_T, Rfree)[-1]
npv_base_Y = calculate_NPV(np.array(tm_base['AggIncome']), act_T, Rfree)[-1]
mult_noAD = npv_noAD_C / npv_noAD_Y if npv_noAD_Y != 0 else float('nan')
print(f"  Non-AD: NPV_C={npv_noAD_C:.6f}, NPV_Y={npv_noAD_Y:.6f}, multiplier={mult_noAD:.4f}")
print(f"  Non-AD computed in {time()-t0:.1f}s")

# ============================================================
# 3. TM AD (recessionUI)
# ============================================================
print(f"\n--- TM AD (recessionUI, ADelasticity={ADelasticity}) ---")
t0 = time()
# Re-create the economy for AD (need fresh shock-typed copy)
eco_ad = deepcopy(AggEco)
eco_ad.switch_shock_type('recessionUI')
eco_ad.solve()
tm_AD = run_ad_tm(
    eco_ad, 'recessionUI', rec_path,
    bl_data, AggCons_baseline,
    ADelasticity=ADelasticity,
    num_max_iterations=10,
    convergence_tol=0.004,
    mCount=mCount,
    verbose=True,
)
npv_AD_C = tm_AD['NPV_AggCons'][-1]
npv_AD_Y = tm_AD['NPV_AggIncome'][-1]
mult_AD = npv_AD_C / npv_AD_Y if npv_AD_Y != 0 else float('nan')
Cratio_path_AD = tm_AD['Cratio_hist']
print(f"  AD: NPV_C={npv_AD_C:.6f}, NPV_Y={npv_AD_Y:.6f}, multiplier={mult_AD:.4f}")
print(f"  AD/non-AD ratio = {mult_AD/mult_noAD:.4f}" if mult_noAD != 0 else "  AD/non-AD ratio = N/A")
print(f"  Cratio path: mean={np.mean(Cratio_path_AD):.6f}, "
      f"min={np.min(Cratio_path_AD):.6f}, max={np.max(Cratio_path_AD):.6f}")
print(f"  Cratio first 8: {Cratio_path_AD[:8]}")
print(f"  TM AD computed in {time()-t0:.1f}s")

# ============================================================
# 4. Unit diagnostic: one-period AggDemandFac effect
# ============================================================
print("\n--- Unit diagnostic: AggDemandFac on one period ---")
# At Cratio=1.05 in a recession state (odd macro), AggDemandFac = 1.05^0.3 ≈ 1.0148
# Compare consumption with vs without income scaling

test_Cratio = 1.05
test_macro = 1  # odd = recession
RecState = test_macro % 2
AggDemandFac_test = test_Cratio ** (ADelasticity * RecState)
print(f"  Cratio={test_Cratio}, macro={test_macro}, RecState={RecState}")
print(f"  AggDemandFac = {test_Cratio}^({ADelasticity}*{RecState}) = {AggDemandFac_test:.6f}")

# Build one period with and without income scaling
eco_diag = deepcopy(AggEco)
eco_diag.switch_shock_type('recessionUI')
eco_diag.solve()
agent_diag = eco_diag.agents[0]
dist_mGrid = bd['dist_mGrid']
dist = bd['ergodic'].copy()

macro_next = 2  # next period after macro=1

# Without scaling
TM_no, cPol_no = build_experiment_period_tm(
    agent_diag, test_macro, macro_next, dist_mGrid, test_Cratio,
    employed_tran_shk_scale=1.0)
IncShkDstn_no = [agent_diag.IncShkDstn[0][test_macro * J + j] for j in range(J)]
agg_no = compute_period_aggregates_tm(dist, cPol_no, dist_mGrid, IncShkDstn_no, agent_diag.Splurge)

# With scaling (Channel A)
TM_yes, cPol_yes = build_experiment_period_tm(
    agent_diag, test_macro, macro_next, dist_mGrid, test_Cratio,
    employed_tran_shk_scale=1.0,
    ad_tran_shk_scale=AggDemandFac_test)
IncShkDstn_yes = [agent_diag.IncShkDstn[0][test_macro * J + j] for j in range(J)]
# Scale IncShkDstn for aggregates too
IncShkDstn_yes_scaled = [_scaled_employed_joint_inc_dstn(d, AggDemandFac_test) for d in IncShkDstn_yes]
agg_yes = compute_period_aggregates_tm(dist, cPol_yes, dist_mGrid, IncShkDstn_yes_scaled, agent_diag.Splurge,
                                        AggDemandFac=AggDemandFac_test)

print(f"  Without scaling: C_nrm={agg_no['C_splurge_nrm']:.6f}, Y_nrm={agg_no['Income_nrm']:.6f}")
print(f"  With scaling:    C_nrm={agg_yes['C_splurge_nrm']:.6f}, Y_nrm={agg_yes['Income_nrm']:.6f}")
pct_C = (agg_yes['C_splurge_nrm'] / agg_no['C_splurge_nrm'] - 1) * 100
pct_Y = (agg_yes['Income_nrm'] / agg_no['Income_nrm'] - 1) * 100
print(f"  Delta: C={pct_C:+.3f}%, Y={pct_Y:+.3f}%")

# ============================================================
# 5. MC AD ground truth (recessionUI)
# ============================================================
print(f"\n--- MC AD ground truth (recessionUI, N=80000) ---")
t0 = time()
N_mc = 80000

# --- MC non-AD first ---
eco_mc = deepcopy(AggEco)
for a in eco_mc.agents:
    a.AgentCount = N_mc
    a.seed = 42000
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
eco_mc.store_baseline(mc_base['AggCons'])

# MC non-AD recessionUI
eco_mc_ui = deepcopy(eco_mc)
eco_mc_ui.switch_shock_type('recessionUI')
eco_mc_ui.solve()
d_ui = base_dict_agg.copy()
d_ui.update(recession_UI_changes)
d_ui['EconomyMrkv_init'] = rec_path
mc_noAD_ui = eco_mc_ui.run_experiment(**d_ui, Full_Output=True)
N_act = sum(a.AgentCount for a in eco_mc.agents)
mc_npv_noAD_C = calculate_NPV(np.array(mc_noAD_ui['AggCons']), act_T, Rfree)[-1]
mc_npv_noAD_Y = calculate_NPV(np.array(mc_noAD_ui['AggIncome']), act_T, Rfree)[-1]
mc_mult_noAD = mc_npv_noAD_C / mc_npv_noAD_Y if mc_npv_noAD_Y != 0 else float('nan')
print(f"  MC non-AD: multiplier={mc_mult_noAD:.4f} (N={N_mc})")
print(f"  MC non-AD computed in {time()-t0:.1f}s")

# --- MC AD ---
print("  Running MC AD...", flush=True)
t0_ad = time()
eco_mc_ad = deepcopy(AggEco)
for a in eco_mc_ad.agents:
    a.AgentCount = N_mc
    a.seed = 42000
    a.get_economy_data(eco_mc_ad)

# Must do full burn-in before solve_ad_recession (needs save_state)
eco_mc_ad.solve()
eco_mc_ad.reset()
for a in eco_mc_ad.agents:
    a.initialize_sim()
    a.AggDemandFac = 1.0
    a.RfreeNow = 1.0
    a.CaggNow = 1.0
eco_mc_ad.make_history()
eco_mc_ad.save_state()
eco_mc_ad.switch_to_counterfactual_mode("base")
eco_mc_ad.act_T = act_T
for a in eco_mc_ad.agents:
    a.T_sim = act_T
    a.EconomyMrkvNow_hist = [0] * act_T
eco_mc_ad.make_idiosyncratic_shock_histories()

# Run baseline first (needed for AD convergence reference)
mc_base_ad = eco_mc_ad.run_experiment(**base_dict_agg, Full_Output=True)
eco_mc_ad.store_baseline(mc_base_ad['AggCons'])

# Now switch to recessionUI and run AD iteration
eco_mc_ad.switch_shock_type('recessionUI')
eco_mc_ad.solve_ad_recession(
    num_max_iterations=num_max_iterations_solvingAD,
    convergence_cutoff=convergence_tol_solvingAD,
    shock_type='recessionUI')

# Final experiment with converged CFunc
d_ad = base_dict_agg.copy()
d_ad.update(recession_UI_changes)
d_ad['EconomyMrkv_init'] = rec_path
mc_AD_ui = eco_mc_ad.run_experiment(**d_ad, Full_Output=True)
mc_npv_AD_C = calculate_NPV(np.array(mc_AD_ui['AggCons']), act_T, Rfree)[-1]
mc_npv_AD_Y = calculate_NPV(np.array(mc_AD_ui['AggIncome']), act_T, Rfree)[-1]
mc_mult_AD = mc_npv_AD_C / mc_npv_AD_Y if mc_npv_AD_Y != 0 else float('nan')
mc_Cratio = np.array(mc_AD_ui.get('Cratio_hist', [1.0]*act_T))
print(f"  MC AD: multiplier={mc_mult_AD:.4f}")
print(f"  MC AD/non-AD ratio = {mc_mult_AD/mc_mult_noAD:.4f}" if mc_mult_noAD != 0 else "  MC AD/non-AD ratio = N/A")
print(f"  MC AD computed in {time()-t0_ad:.1f}s")

# ============================================================
# 6. Comparison table
# ============================================================
print("\n" + "=" * 60)
print("COMPARISON: recessionUI")
print("=" * 60)
print(f"  {'':20s}  {'non-AD mult':>12s}  {'AD mult':>12s}  {'AD/non-AD':>10s}")
print("  " + "-" * 56)
tm_ratio = mult_AD / mult_noAD if mult_noAD != 0 else float('nan')
mc_ratio = mc_mult_AD / mc_mult_noAD if mc_mult_noAD != 0 else float('nan')
print(f"  {'TM':20s}  {mult_noAD:12.4f}  {mult_AD:12.4f}  {tm_ratio:10.4f}")
print(f"  {'MC (N=80K)':20s}  {mc_mult_noAD:12.4f}  {mc_mult_AD:12.4f}  {mc_ratio:10.4f}")

print(f"\n  TM Cratio path (first 8): {Cratio_path_AD[:8]}")
print(f"  MC Cratio path (first 8): {mc_Cratio[:8]}")

# NPV treatment effects (absolute magnitudes) — better metric than C/Y ratio
tm_te_C = npv_AD_C - npv_base_C
tm_te_Y = npv_AD_Y - npv_base_Y
tm_te_C_noAD = npv_noAD_C - npv_base_C
tm_te_Y_noAD = npv_noAD_Y - npv_base_Y

# MC treatment effects
mc_npv_base_C = calculate_NPV(np.array(mc_base['AggCons']), act_T, Rfree)[-1]
mc_npv_base_Y = calculate_NPV(np.array(mc_base['AggIncome']), act_T, Rfree)[-1]
mc_te_C_noAD = mc_npv_noAD_C - mc_npv_base_C
mc_te_Y_noAD = mc_npv_noAD_Y - mc_npv_base_Y
mc_npv_base_ad_C = calculate_NPV(np.array(mc_base_ad['AggCons']), act_T, Rfree)[-1]
mc_npv_base_ad_Y = calculate_NPV(np.array(mc_base_ad['AggIncome']), act_T, Rfree)[-1]
mc_te_C_AD = mc_npv_AD_C - mc_npv_base_ad_C
mc_te_Y_AD = mc_npv_AD_Y - mc_npv_base_ad_Y

print(f"\n  NPV Treatment Effects (experiment - baseline):")
print(f"  {'':20s}  {'TE_C noAD':>12s}  {'TE_C AD':>12s}  {'AD/noAD':>10s}")
print("  " + "-" * 56)
tm_te_ratio = tm_te_C / tm_te_C_noAD if tm_te_C_noAD != 0 else float('nan')
mc_te_ratio = mc_te_C_AD / mc_te_C_noAD if mc_te_C_noAD != 0 else float('nan')
print(f"  {'TM':20s}  {tm_te_C_noAD:12.4f}  {tm_te_C:12.4f}  {tm_te_ratio:10.4f}")
print(f"  {'MC (N=80K)':20s}  {mc_te_C_noAD:12.4f}  {mc_te_C_AD:12.4f}  {mc_te_ratio:10.4f}")

print(f"\n  Target: TM AD treatment effect > 1.05x non-AD")
print(f"  Result: TM TE ratio = {tm_te_ratio:.4f} {'PASS' if tm_te_ratio > 1.05 else 'CHECK'}")
print(f"  MC TE ratio = {mc_te_ratio:.4f} (ground truth)")

print(f"\nTotal time: {time()-t0_total:.0f}s ({(time()-t0_total)/60:.1f} min)")
