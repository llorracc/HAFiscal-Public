"""
Simplest test of the pLvl factorization hypothesis.

The TM computes: AggCons = N * E[pLvl] * C_nrm
The MC computes: AggCons = sum( cNrm_i * pLvl_i )

These differ when Cov(cNrm, pLvl) != 0.

Test: run MC, then compute the TE three ways:
1. Real MC:     TE = sum(cLvl_UI_i) - sum(cLvl_base_i)           (what MC does)
2. Factored:    TE = E[pLvl] * [sum(cNrm_UI_i) - sum(cNrm_base_i)]  (what TM does)
3. MC-pLvl:     TE = mean(pLvl_MC) * [sum(cNrm_UI_i) - sum(cNrm_base_i)]

If (2) matches TM and (1) != (2), the gap is from pLvl factorization.
"""

import os
import sys
import numpy as np
from time import time
from copy import deepcopy

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import (
    compute_baseline_tm_data,
    propagate_experiment_tm,
    compute_analytical_mean_pLvl,
)

# ============================================================
# Setup
# ============================================================
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

N = 1000000
J = num_base_MrkvStates

BaseType = AggFiscalType(**init_highschool)
BaseType.cycles = 0
BaseType.AgentCount = N
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

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
AggEco.solve()
act_T = AggEco.act_T
base_dict_agg = deepcopy(base_dict)
Splurge = BaseType.Splurge
E_pLvl_analytical = compute_analytical_mean_pLvl(BaseType)

ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20

print(f"N={N}, Splurge={Splurge:.4f}, E_pLvl_analytical={E_pLvl_analytical:.4f}")

# ============================================================
# TM reference
# ============================================================
print("\n--- TM ---")
t0 = time()
bl_data = compute_baseline_tm_data(AggEco, dist_aGrid_count=50, verbose=False)
bd = bl_data[0]
base_a = deepcopy(BaseType)
base_a.update_mrkv_array("base")
base_a.solve()
r_base_tm = propagate_experiment_tm(
    base_a, bd['ergodic'], [0]*act_T, bd['dist_mGrid'],
    bd['E_pLvl'], Cratio=1.0, act_T=act_T)
eco_u = deepcopy(AggEco)
eco_u.switch_shock_type("UI")
eco_u.solve()
r_ui_tm = propagate_experiment_tm(
    eco_u.agents[0], bd['ergodic'], ui_path, bd['dist_mGrid'],
    bd['E_pLvl'], Cratio=1.0, act_T=act_T, shock_type='UI')
tm_cons_TE = (r_ui_tm['AggCons'][0] - r_base_tm['AggCons'][0]) / N
tm_income_TE = (r_ui_tm['AggIncome'][0] - r_base_tm['AggIncome'][0]) / N
print(f"  TM cons TE:   {tm_cons_TE:.8f}")
print(f"  TM income TE: {tm_income_TE:.8f}")
print(f"  TM time: {time()-t0:.0f}s")

# ============================================================
# MC — extract per-agent data at period 0
# ============================================================
print("\n--- MC ---")

def run_mc_full(shock_type, changes_dict, path, seed=0):
    eco = deepcopy(AggEco)
    for a in eco.agents:
        a.AgentCount = N
        a.seed = seed * 1000
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

    base_r = eco.run_experiment(**base_dict_agg, Full_Output=True)
    eco.store_baseline(base_r['AggCons'])

    if shock_type == 'base':
        return eco, base_r

    eco_x = deepcopy(eco)
    eco_x.switch_shock_type(shock_type)
    eco_x.solve()
    d = base_dict_agg.copy()
    d.update(changes_dict)
    d['EconomyMrkv_init'] = path
    shock_r = eco_x.run_experiment(**d, Full_Output=True)
    return eco_x, shock_r

t0 = time()
# Run base
eco_base, base_r = run_mc_full('base', {}, [0]*act_T, seed=42)
# Run UI (from same burn-in)
eco_ui_mc, ui_r = run_mc_full('UI', UI_changes, ui_path, seed=42)
print(f"  MC time: {time()-t0:.0f}s")

# Extract period-0 per-agent data
pLvl_base = base_r['pLvl_all'][0]
cNrm_base = base_r['cNrm_all'][0]
TranShk_base = base_r['TranShk_all'][0] if 'TranShk_all' in base_r else eco_base.agents[0].shock_history['TranShk'][0]
mrkv_base = base_r.get('Mrkv_hist', [eco_base.agents[0].shock_history['Mrkv']])[0]

pLvl_ui = ui_r['pLvl_all'][0]
cNrm_ui = ui_r['cNrm_all'][0]
TranShk_ui = ui_r['TranShk_all'][0] if 'TranShk_all' in ui_r else eco_ui_mc.agents[0].shock_history['TranShk'][0]
mrkv_ui = ui_r.get('Mrkv_hist', [eco_ui_mc.agents[0].shock_history['Mrkv']])[0]

N_act = N  # single type

# MC's empirical mean pLvl
mean_pLvl_base = np.mean(pLvl_base)
mean_pLvl_ui = np.mean(pLvl_ui)

print(f"\n  E[pLvl] analytical: {E_pLvl_analytical:.6f}")
print(f"  E[pLvl] MC base:    {mean_pLvl_base:.6f}")
print(f"  E[pLvl] MC UI:      {mean_pLvl_ui:.6f}")
print(f"  Ratio MC/analytical: {mean_pLvl_base / E_pLvl_analytical:.6f}")

# Per-state E[pLvl]
micro_base = mrkv_base % J
micro_ui = mrkv_ui % J
print(f"\n  Per-state E[pLvl] (MC base, period 0):")
for j in range(J):
    mask = micro_base == j
    if np.sum(mask) > 0:
        print(f"    State {j}: E[pLvl]={np.mean(pLvl_base[mask]):.6f}, "
              f"frac={np.mean(mask):.6f}, n={np.sum(mask)}")

# ============================================================
# Compute TE three ways
# ============================================================
print("\n" + "=" * 70)
print("TREATMENT EFFECT DECOMPOSITION")
print("=" * 70)

# 1. Real MC: sum(cLvl_i)
# cLvl = (1-S)*cNrm*pLvl + S*TranShk*pLvl
cLvl_base = (1.0 - Splurge) * cNrm_base * pLvl_base + Splurge * TranShk_base * pLvl_base
cLvl_ui = (1.0 - Splurge) * cNrm_ui * pLvl_ui + Splurge * TranShk_ui * pLvl_ui
mc_real_TE = (np.sum(cLvl_ui) - np.sum(cLvl_base)) / N_act

# 2. Factored with analytical E[pLvl]: E_pLvl * sum(cNrm + S/(1-S)*TranShk)
# Total normalized consumption = (1-S)*cNrm + S*TranShk
cTot_nrm_base = (1.0 - Splurge) * cNrm_base + Splurge * TranShk_base
cTot_nrm_ui = (1.0 - Splurge) * cNrm_ui + Splurge * TranShk_ui
factored_analytical_TE = E_pLvl_analytical * (np.mean(cTot_nrm_ui) - np.mean(cTot_nrm_base))

# 3. Factored with MC's empirical E[pLvl]
# Use average of base and UI pLvl (they should be very similar)
mean_pLvl_avg = 0.5 * (mean_pLvl_base + mean_pLvl_ui)
factored_mc_pLvl_TE = mean_pLvl_avg * (np.mean(cTot_nrm_ui) - np.mean(cTot_nrm_base))

# 4. Per-agent factored: replace each pLvl_i with E[pLvl]
cLvl_base_uniform = (1.0 - Splurge) * cNrm_base * E_pLvl_analytical + Splurge * TranShk_base * E_pLvl_analytical
cLvl_ui_uniform = (1.0 - Splurge) * cNrm_ui * E_pLvl_analytical + Splurge * TranShk_ui * E_pLvl_analytical
mc_uniform_pLvl_TE = (np.sum(cLvl_ui_uniform) - np.sum(cLvl_base_uniform)) / N_act

print(f"\n  Method                          Cons TE      gap vs TM")
print(f"  {'—'*60}")
print(f"  TM (mCount=50):                 {tm_cons_TE:.8f}  reference")
print(f"  MC real (sum cLvl_i):            {mc_real_TE:.8f}  {(mc_real_TE - tm_cons_TE)/tm_cons_TE*100:+.2f}%")
print(f"  MC uniform pLvl (E_pLvl*cNrm):  {mc_uniform_pLvl_TE:.8f}  {(mc_uniform_pLvl_TE - tm_cons_TE)/tm_cons_TE*100:+.2f}%")
print(f"  Factored (E_pLvl_anal * ΔcNrm): {factored_analytical_TE:.8f}  {(factored_analytical_TE - tm_cons_TE)/tm_cons_TE*100:+.2f}%")
print(f"  Factored (E_pLvl_MC * ΔcNrm):   {factored_mc_pLvl_TE:.8f}  {(factored_mc_pLvl_TE - tm_cons_TE)/tm_cons_TE*100:+.2f}%")

# Decompose the pLvl factorization error
cov_term = mc_real_TE - factored_mc_pLvl_TE
print(f"\n  Cov(pLvl, Δc) contribution:     {cov_term:.8f}")
print(f"  As fraction of MC TE:            {cov_term/mc_real_TE*100:.2f}%")
print(f"  E[pLvl] scaling contribution:    {(factored_analytical_TE - factored_mc_pLvl_TE):.8f}")

# Also decompose into splurge and non-splurge
splurge_base = Splurge * TranShk_base * pLvl_base
splurge_ui = Splurge * TranShk_ui * pLvl_ui
nonsplurge_base = (1.0 - Splurge) * cNrm_base * pLvl_base
nonsplurge_ui = (1.0 - Splurge) * cNrm_ui * pLvl_ui

splurge_TE = (np.sum(splurge_ui) - np.sum(splurge_base)) / N_act
nonsplurge_TE = (np.sum(nonsplurge_ui) - np.sum(nonsplurge_base)) / N_act

splurge_base_unif = Splurge * TranShk_base * E_pLvl_analytical
splurge_ui_unif = Splurge * TranShk_ui * E_pLvl_analytical
nonsplurge_base_unif = (1.0 - Splurge) * cNrm_base * E_pLvl_analytical
nonsplurge_ui_unif = (1.0 - Splurge) * cNrm_ui * E_pLvl_analytical

splurge_TE_unif = (np.sum(splurge_ui_unif) - np.sum(splurge_base_unif)) / N_act
nonsplurge_TE_unif = (np.sum(nonsplurge_ui_unif) - np.sum(nonsplurge_base_unif)) / N_act

print(f"\n  Component breakdown:")
print(f"  {'Component':<20s}  {'real pLvl':>12s}  {'uniform pLvl':>12s}  {'Cov contrib':>12s}")
print(f"  {'Splurge':<20s}  {splurge_TE:12.8f}  {splurge_TE_unif:12.8f}  {splurge_TE - splurge_TE_unif:12.8f}")
print(f"  {'Non-splurge':<20s}  {nonsplurge_TE:12.8f}  {nonsplurge_TE_unif:12.8f}  {nonsplurge_TE - nonsplurge_TE_unif:12.8f}")
print(f"  {'Total':<20s}  {mc_real_TE:12.8f}  {mc_uniform_pLvl_TE:12.8f}  {cov_term:12.8f}")

print("\nDone.")
