"""Test: half-step TM for both base and UI, with MC comparison."""
import os, sys, numpy as np
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
    compute_baseline_tm_data, propagate_experiment_tm,
    compute_analytical_mean_pLvl, run_experiment_tm_nonbase,
)

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

N = 500000
J = num_base_MrkvStates

BaseType = AggFiscalType(**init_highschool)
BaseType.cycles = 0
BaseType.AgentCount = N
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]
AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

IncShkDstn_unemp = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])
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
ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20

# TM baseline data (includes base_aPol)
bl_data = compute_baseline_tm_data(AggEco, mCount=50, verbose=False)
bd = bl_data[0]

# BASE propagation with half-step
base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
r_base = propagate_experiment_tm(
    base_agent, bd['ergodic'], [0]*act_T, bd['dist_mGrid'],
    bd['E_pLvl'], Cratio=1.0, act_T=act_T,
    base_aPol=bd['base_aPol'])  # ← pass base_aPol!

# UI propagation with half-step
eco_ui = deepcopy(AggEco)
eco_ui.switch_shock_type("UI")
eco_ui.solve()
r_ui = propagate_experiment_tm(
    eco_ui.agents[0], bd['ergodic'], ui_path, bd['dist_mGrid'],
    bd['E_pLvl'], Cratio=1.0, act_T=act_T, shock_type='UI',
    base_aPol=bd['base_aPol'])  # ← pass base_aPol!

tm_cons_TE = (r_ui['AggCons'][0] - r_base['AggCons'][0]) / N
tm_income_TE = (r_ui['AggIncome'][0] - r_base['AggIncome'][0]) / N
print(f"TM (half-step both): cons_TE={tm_cons_TE:.8f}, income_TE={tm_income_TE:.8f}")

# MC reference (3 seeds)
mc_cons_tes = []
mc_income_tes = []
for seed in range(3):
    eco = deepcopy(AggEco)
    for a in eco.agents:
        a.AgentCount = N; a.seed = seed*1000; a.get_economy_data(eco)
    eco.solve(); eco.reset()
    for a in eco.agents:
        a.initialize_sim(); a.AggDemandFac=1.0; a.RfreeNow=1.0; a.CaggNow=1.0
    eco.make_history(); eco.save_state()
    eco.switch_to_counterfactual_mode("base")
    eco.act_T = act_T
    for a in eco.agents:
        a.T_sim = act_T; a.EconomyMrkvNow_hist = [0]*act_T
    eco.make_idiosyncratic_shock_histories()
    base_r = eco.run_experiment(**base_dict_agg, Full_Output=True)
    eco.store_baseline(base_r['AggCons'])
    eco_x = deepcopy(eco); eco_x.switch_shock_type('UI'); eco_x.solve()
    d = base_dict_agg.copy(); d.update(UI_changes); d['EconomyMrkv_init'] = ui_path
    ui_r = eco_x.run_experiment(**d, Full_Output=True)
    N_act = sum(a.AgentCount for a in eco.agents)
    mc_cons_tes.append((ui_r['AggCons'][0] - base_r['AggCons'][0]) / N_act)
    mc_income_tes.append((ui_r['AggIncome'][0] - base_r['AggIncome'][0]) / N_act)

mc_cons = np.mean(mc_cons_tes)
mc_income = np.mean(mc_income_tes)
print(f"MC (3 seeds):        cons_TE={mc_cons:.8f}, income_TE={mc_income:.8f}")
print(f"Gap (TM-MC)/MC:      cons={((tm_cons_TE-mc_cons)/mc_cons)*100:+.2f}%, income={((tm_income_TE-mc_income)/mc_income)*100:+.2f}%")

# Per-period comparison
print(f"\n  t   TM_cons_TE     TM_income_TE")
for t in range(5):
    c = (r_ui['AggCons'][t] - r_base['AggCons'][t]) / N
    y = (r_ui['AggIncome'][t] - r_base['AggIncome'][t]) / N
    print(f"  {t}   {c:12.8f}   {y:12.8f}")
