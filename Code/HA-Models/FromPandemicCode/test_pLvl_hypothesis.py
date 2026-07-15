"""
Test: does the consumption gap come from pLvl heterogeneity?

The TM computes cons = E[pLvl] * sum(cPol * dist), treating all agents
as having the same pLvl. MC computes cons = sum(cFunc(mNrm_i) * pLvl_i),
which captures the correlation between pLvl and (mNrm, micro_state).

Test: recompute MC consumption using uniform pLvl (= E[pLvl]).
If the MC consumption TE drops to match TM, the gap is from pLvl.
"""

import os
import sys
import numpy as np
from copy import deepcopy

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import compute_analytical_mean_pLvl

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

J = num_base_MrkvStates
N = 500000

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
E_pLvl = compute_analytical_mean_pLvl(BaseType)
ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20

print(f"E[pLvl] = {E_pLvl:.4f}, Splurge = {Splurge:.4f}, N = {N}")

def run_mc_decomposed(shock_type, changes_dict, path, seed=0):
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
        r = base_r
    else:
        eco_x = deepcopy(eco)
        eco_x.switch_shock_type(shock_type)
        eco_x.solve()
        d = base_dict_agg.copy()
        d.update(changes_dict)
        d['EconomyMrkv_init'] = path
        r = eco_x.run_experiment(**d, Full_Output=True)

    return r

# Run MC
print("Running MC...")
from time import time
t0 = time()
mc_base = run_mc_decomposed('base', base_dict, [0]*act_T, seed=42)
mc_ui = run_mc_decomposed('UI', UI_changes, ui_path, seed=42)
print(f"MC done in {time()-t0:.0f}s")

N_act = N  # single type

# Period 0 data
for label, r in [("Base", mc_base), ("UI", mc_ui)]:
    pLvl = r['pLvl_all'][0]
    cNrm = r['cNrm_all'][0]
    TranShk = r['TranShk_all'][0]
    mNrm = r['mNrm_all'][0]
    Mrkv = r['Mrkv_hist'][0]
    micro = Mrkv % J

    # Standard MC consumption (per-cap)
    cLvl_splurge = (1 - Splurge) * cNrm * pLvl + Splurge * TranShk * pLvl
    mc_cons = np.sum(cLvl_splurge) / N_act

    # "Uniform pLvl" consumption: replace each agent's pLvl with E[pLvl]
    cLvl_uniform = (1 - Splurge) * cNrm * E_pLvl + Splurge * TranShk * E_pLvl
    mc_cons_uniform = np.sum(cLvl_uniform) / N_act

    # "Per-state E[pLvl]" consumption: use mean pLvl within each state
    cLvl_per_state = np.zeros_like(cLvl_splurge)
    for j in range(J):
        mask = micro == j
        if np.sum(mask) > 0:
            E_pLvl_j = np.mean(pLvl[mask])
            cLvl_per_state[mask] = (1 - Splurge) * cNrm[mask] * E_pLvl_j + Splurge * TranShk[mask] * E_pLvl_j
    mc_cons_per_state = np.sum(cLvl_per_state) / N_act

    print(f"\n{label}:")
    print(f"  MC cons (actual pLvl):      {mc_cons:.6f}")
    print(f"  MC cons (uniform E[pLvl]):  {mc_cons_uniform:.6f}")
    print(f"  MC cons (per-state E[pLvl]):{mc_cons_per_state:.6f}")

    # Per-state pLvl statistics
    print(f"  Per-state E[pLvl]:")
    for j in range(J):
        mask = micro == j
        if np.sum(mask) > 10:
            print(f"    State {j}: E[pLvl]={np.mean(pLvl[mask]):.4f}, "
                  f"std={np.std(pLvl[mask]):.4f}, n={np.sum(mask)}")

# Treatment effects
base_pLvl = mc_base['pLvl_all'][0]
base_cNrm = mc_base['cNrm_all'][0]
base_TranShk = mc_base['TranShk_all'][0]
ui_pLvl = mc_ui['pLvl_all'][0]
ui_cNrm = mc_ui['cNrm_all'][0]
ui_TranShk = mc_ui['TranShk_all'][0]

# Standard TE
mc_te_actual = (np.sum((1-Splurge)*ui_cNrm*ui_pLvl + Splurge*ui_TranShk*ui_pLvl) -
                np.sum((1-Splurge)*base_cNrm*base_pLvl + Splurge*base_TranShk*base_pLvl)) / N_act

# Uniform pLvl TE
mc_te_uniform = (np.sum((1-Splurge)*ui_cNrm*E_pLvl + Splurge*ui_TranShk*E_pLvl) -
                 np.sum((1-Splurge)*base_cNrm*E_pLvl + Splurge*base_TranShk*E_pLvl)) / N_act

# Simplified: factor out E_pLvl
mc_te_nrm = (np.mean((1-Splurge)*ui_cNrm + Splurge*ui_TranShk) -
             np.mean((1-Splurge)*base_cNrm + Splurge*base_TranShk))
mc_te_from_nrm = mc_te_nrm * E_pLvl

print(f"\n{'='*70}")
print(f"TREATMENT EFFECTS")
print(f"{'='*70}")
print(f"  MC TE (actual pLvl):     {mc_te_actual:.6f}")
print(f"  MC TE (uniform E[pLvl]): {mc_te_uniform:.6f}")
print(f"  MC TE (nrm * E[pLvl]):   {mc_te_from_nrm:.6f}")
print(f"  TM TE (reference):       ~0.015401")
print(f"\n  If 'uniform' ≈ TM: gap is from pLvl heterogeneity")
print(f"  If 'uniform' ≈ MC actual: pLvl heterogeneity doesn't matter")
