"""
Cross-CFunc diagnostic: determine whether TM-MC AD gap comes from
CFunc training divergence or from consumption computation divergence.

Strategy:
1. Train CFunc independently with TM and MC
2. Run MC with TM's CFunc (cross-CFunc test)
3. Compare treatment effects

If MC-with-TM-CFunc matches TM → gap is in CFunc training
If MC-with-TM-CFunc matches MC → gap is in consumption computation
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

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy, CRule
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import (
    compute_baseline_tm_data, propagate_experiment_tm,
    run_experiment_tm_nonbase, run_ad_tm, calculate_NPV,
)

# ============================================================
# Setup (same as test_glp2)
# ============================================================
print("=" * 60)
print("Cross-CFunc diagnostic: TM vs MC AD gap isolation")
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

BaseType = AggFiscalType(**init_college)
BaseType.cycles = 0
BaseType.DiscFac = DiscFacDstns[2].atoms[0][0]

AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

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
BaseType.AgentCount = 1

print("Solving...")
AggEco.solve()

act_T = AggEco.act_T
base_dict_agg = deepcopy(base_dict)
Rfree = BaseType.Rfree[0]
ADelasticity = AggEco.demand_ADelasticity

# 3-quarter recession path
rec_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20
for t in range(3):
    rec_path[t] = rec_path[t] + 1

N_mc = 80000

# ============================================================
# Step 1: TM baseline + CFunc training
# ============================================================
print("\n--- Step 1: TM baseline + AD CFunc training ---")
mCount = 100
bl_data = compute_baseline_tm_data(AggEco, mCount=mCount, verbose=False)
bd = bl_data[0]

base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
tm_base = propagate_experiment_tm(
    base_agent, bd['ergodic'], [0]*act_T, bd['dist_mGrid'],
    bd['E_pLvl'], act_T=act_T, base_aPol=bd['base_aPol'])
AggCons_baseline_tm = np.array(tm_base['AggCons'])

# TM non-AD
eco_tm_ui = deepcopy(AggEco)
eco_tm_ui.switch_shock_type('recessionUI')
eco_tm_ui.solve()
tm_noAD = run_experiment_tm_nonbase(
    eco_tm_ui, 'recessionUI', rec_path, bl_data, mCount=mCount, verbose=False)

# TM AD — trains CFunc
eco_tm_ad = deepcopy(AggEco)
eco_tm_ad.switch_shock_type('recessionUI')
eco_tm_ad.solve()
tm_AD = run_ad_tm(
    eco_tm_ad, 'recessionUI', rec_path,
    bl_data, AggCons_baseline_tm,
    ADelasticity=ADelasticity,
    num_max_iterations=10,
    convergence_tol=0.004,
    mCount=mCount,
    verbose=True,
)

# Extract TM CFunc intercepts (from eco_tm_ad which was mutated by run_ad_tm)
tm_CFunc = eco_tm_ad.CFunc
dim = len(tm_CFunc)
print(f"\n  TM CFunc dimension: {dim}x{dim}")
print("  TM CFunc intercepts (unique macro transitions):")
seen = set()
for i in range(dim):
    for j in range(dim):
        ic = tm_CFunc[i][j].intercept
        if abs(ic - 1.0) > 1e-6:
            macro_i, macro_j = i // J, j // J
            key = (macro_i, macro_j)
            if key not in seen:
                seen.add(key)
                print(f"    MacroCFunc[{macro_i}][{macro_j}]: intercept={ic:.8f}")

# TM treatment effects
npv_base_C = calculate_NPV(AggCons_baseline_tm, act_T, Rfree)[-1]
tm_te_noAD = tm_noAD['NPV_AggCons'][-1] - npv_base_C
tm_te_AD = tm_AD['NPV_AggCons'][-1] - npv_base_C
tm_ratio = tm_te_AD / tm_te_noAD if tm_te_noAD != 0 else float('nan')
print(f"\n  TM TE noAD = {tm_te_noAD:.6f}")
print(f"  TM TE AD   = {tm_te_AD:.6f}")
print(f"  TM AD/noAD = {tm_ratio:.4f}")

# ============================================================
# Step 2: MC baseline + independent CFunc training
# ============================================================
print("\n--- Step 2: MC baseline + independent AD CFunc training ---")

def setup_mc_economy(seed=42000):
    """Set up MC economy from scratch with burn-in."""
    eco = deepcopy(AggEco)
    for a in eco.agents:
        a.AgentCount = N_mc
        a.seed = seed
        a.get_economy_data(eco)
    eco.solve()
    eco.reset()
    for a in eco.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0
    eco.make_history()
    eco.save_state()
    eco.switch_to_counterfactual_mode("base")
    eco.act_T = act_T
    for a in eco.agents:
        a.T_sim = act_T
        a.EconomyMrkvNow_hist = [0] * act_T
    eco.make_idiosyncratic_shock_histories()
    return eco

eco_mc = setup_mc_economy()

# MC baseline
mc_base = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
eco_mc.store_baseline(mc_base['AggCons'])

# MC non-AD recessionUI
eco_mc_ui_noAD = deepcopy(eco_mc)
eco_mc_ui_noAD.switch_shock_type('recessionUI')
eco_mc_ui_noAD.solve()
d_ui = base_dict_agg.copy()
d_ui.update(recession_UI_changes)
d_ui['EconomyMrkv_init'] = rec_path
mc_noAD = eco_mc_ui_noAD.run_experiment(**d_ui, Full_Output=True)
mc_npv_base_C = calculate_NPV(np.array(mc_base['AggCons']), act_T, Rfree)[-1]
mc_te_noAD = calculate_NPV(np.array(mc_noAD['AggCons']), act_T, Rfree)[-1] - mc_npv_base_C
print(f"  MC TE noAD = {mc_te_noAD:.6f}")

# MC AD with INDEPENDENT CFunc training
eco_mc_ad_indep = deepcopy(eco_mc)
eco_mc_ad_indep.switch_shock_type('recessionUI')
eco_mc_ad_indep.solve_ad_recession(
    num_max_iterations=num_max_iterations_solvingAD,
    convergence_cutoff=convergence_tol_solvingAD,
    shock_type='recessionUI',
    name='recessionUI')

# Extract MC CFunc intercepts — only unique macro-level transitions
mc_CFunc = eco_mc_ad_indep.CFunc
print("\n  MC CFunc intercepts (unique macro transitions):")
seen = set()
for i in range(len(mc_CFunc)):
    for j in range(len(mc_CFunc)):
        ic = mc_CFunc[i][j].intercept
        sl = mc_CFunc[i][j].slope
        macro_i, macro_j = i // J, j // J
        if abs(ic - 1.0) > 1e-6 or abs(sl) > 1e-6:
            key = (macro_i, macro_j)
            if key not in seen:
                seen.add(key)
                print(f"    MacroCFunc[{macro_i}][{macro_j}]: intercept={ic:.8f}")

# Compare TM vs MC CFunc intercepts
print("\n  CFunc intercept comparison (TM vs MC):")
for i in range(min(len(tm_CFunc), len(mc_CFunc))):
    for j in range(min(len(tm_CFunc), len(mc_CFunc))):
        tm_ic = tm_CFunc[i][j].intercept
        mc_ic = mc_CFunc[i][j].intercept
        if abs(tm_ic - 1.0) > 1e-6:
            macro_i, macro_j = i // J, j // J
            key = (macro_i, macro_j, i % J, j % J)
            if key[2] == 0 and key[3] == 0:  # only first micro pair
                diff_pct = (mc_ic - tm_ic) / tm_ic * 100
                print(f"    MacroCFunc[{macro_i}][{macro_j}]: TM={tm_ic:.8f}, MC={mc_ic:.8f}, diff={diff_pct:+.4f}%")

# MC AD final experiment with independent CFunc
eco_mc_ad_indep.switch_shock_type('recessionUI')
eco_mc_ad_indep.restore_ADsolution(name='recessionUI')
mc_AD_indep = eco_mc_ad_indep.run_experiment(**d_ui, Full_Output=True)
mc_npv_base_ad = calculate_NPV(np.array(eco_mc_ad_indep.base_AggCons), act_T, Rfree)[-1]
mc_te_AD_indep = calculate_NPV(np.array(mc_AD_indep['AggCons']), act_T, Rfree)[-1] - mc_npv_base_ad
mc_ratio_indep = mc_te_AD_indep / mc_te_noAD if mc_te_noAD != 0 else float('nan')
print(f"\n  MC TE AD (indep CFunc) = {mc_te_AD_indep:.6f}")
print(f"  MC AD/noAD (indep)     = {mc_ratio_indep:.4f}")

# ============================================================
# Step 3: CROSS-CFUNC TEST — MC with TM's CFunc
# ============================================================
print("\n--- Step 3: MC with TM-trained CFunc ---")

eco_mc_cross = deepcopy(eco_mc)
eco_mc_cross.switch_shock_type('recessionUI')

# Apply TM's CFunc to MC economy — must solve agents under this CFunc
eco_mc_cross.CFunc = deepcopy(tm_CFunc)
eco_mc_cross.ADelasticity = ADelasticity
# CRITICAL: refresh ADFunc lambda — deepcopy doesn't rebind `self` in closures
eco_mc_cross.ADFunc = lambda C, RecState: C**(RecState*eco_mc_cross.ADelasticity)
eco_mc_cross.update()
eco_mc_cross.CFunc = deepcopy(tm_CFunc)  # update() resets CFunc to flat, restore
for a in eco_mc_cross.agents:
    a.CFunc = eco_mc_cross.CFunc
    a.get_economy_data(eco_mc_cross)
    a.solve()  # solve individual agent under TM's CFunc

# Verify CFunc is set
print(f"  CFunc[0][12].intercept = {eco_mc_cross.CFunc[0][12].intercept:.8f} (expect {tm_CFunc[0][12].intercept:.8f})")
print(f"  ADelasticity = {eco_mc_cross.ADelasticity}")

# Check sow_init ADF
rec_first = d_ui['EconomyMrkv_init'][0]
sow_cratio = eco_mc_cross.CFunc[0][rec_first * J].intercept
sow_RecState = rec_first % 2 == 1
sow_adf = eco_mc_cross.ADFunc(sow_cratio, sow_RecState)
print(f"  sow_init Cratio should be: {sow_cratio:.8f}")
print(f"  sow_init ADF should be: {sow_adf:.8f}")

mc_AD_cross = eco_mc_cross.run_experiment(**d_ui, Full_Output=True)
mc_te_AD_cross = calculate_NPV(np.array(mc_AD_cross['AggCons']), act_T, Rfree)[-1] - mc_npv_base_C
mc_ratio_cross = mc_te_AD_cross / mc_te_noAD if mc_te_noAD != 0 else float('nan')
print(f"  MC TE AD (TM CFunc)    = {mc_te_AD_cross:.6f}")
print(f"  MC AD/noAD (TM CFunc)  = {mc_ratio_cross:.4f}")

# Also extract ADF history from cross run
adf_hist = np.array(eco_mc_cross.history['AggDemandFac'])
cratio_hist_cross = np.array(mc_AD_cross.get('Cratio_hist', [1.0]*act_T))
print(f"\n  ADF history (cross, first 8):    {adf_hist[:8]}")
print(f"  Cratio hist (cross, first 8):    {cratio_hist_cross[:8]}")
print(f"  TM eval_Cratio (first 8):        {np.array(tm_AD['Cratio_hist'][:8])}")

# Step 4 skipped — dimension mismatch with CFunc from different economy
tm_ratio_cross = float('nan')
tm_te_noAD_val = float('nan')
tm_te_AD_cross_val = float('nan')

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 60)
print("CROSS-CFUNC SUMMARY")
print("=" * 60)
print(f"  {'Configuration':35s}  {'TE noAD':>12s}  {'TE AD':>12s}  {'AD/noAD':>10s}")
print("  " + "-" * 72)
print(f"  {'TM (own CFunc)':35s}  {tm_te_noAD:12.4f}  {tm_te_AD:12.4f}  {tm_ratio:10.4f}")
print(f"  {'MC (own CFunc)':35s}  {mc_te_noAD:12.1f}  {mc_te_AD_indep:12.1f}  {mc_ratio_indep:10.4f}")
print(f"  {'MC (TM CFunc)':35s}  {mc_te_noAD:12.1f}  {mc_te_AD_cross:12.1f}  {mc_ratio_cross:10.4f}")
if not np.isnan(tm_ratio_cross):
    print(f"  {'TM (MC CFunc, skip Phase 1)':35s}  {tm_te_noAD_val:12.4f}  {tm_te_AD_cross_val:12.4f}  {tm_ratio_cross:10.4f}")
print()
print("Interpretation:")
if abs(mc_ratio_cross - tm_ratio) < abs(mc_ratio_cross - mc_ratio_indep):
    print("  MC-with-TM-CFunc ≈ TM → Gap is in CFunc TRAINING")
    print("  (TM and MC train different CFunc, causing the amplification gap)")
else:
    print("  MC-with-TM-CFunc ≈ MC → Gap is in CONSUMPTION COMPUTATION")
    print("  (TM and MC compute different consumption for the same CFunc)")
