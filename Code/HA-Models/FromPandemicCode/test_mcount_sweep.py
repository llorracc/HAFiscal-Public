"""
dist_aGrid_count (né mCount) sweep: test whether TM's AD amplification ratio converges with grid resolution.
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
)

# Setup (same as test_glp2)
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

# 3-quarter recession
rec_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20
for t in range(3):
    rec_path[t] = rec_path[t] + 1

print(f"\n{'dist_aGrid_count':>16s}  {'TE_noAD':>12s}  {'TE_AD':>12s}  {'AD/noAD':>10s}  {'time':>6s}")
print("-" * 55)

for dist_aGrid_count in [50, 100, 200, 400, 800]:
    t0 = time()
    bl_data = compute_baseline_tm_data(AggEco, dist_aGrid_count=dist_aGrid_count, verbose=False)
    bd = bl_data[0]

    base_agent = deepcopy(BaseType)
    base_agent.update_mrkv_array("base")
    base_agent.solve()
    tm_base = propagate_experiment_tm(
        base_agent, bd['ergodic'], [0]*act_T, bd['dist_mGrid'],
        bd['E_pLvl'], act_T=act_T, base_aPol=bd['base_aPol'])
    AggCons_baseline = np.array(tm_base['AggCons'])

    eco_ui = deepcopy(AggEco)
    eco_ui.switch_shock_type('recessionUI')
    eco_ui.solve()
    tm_noAD = run_experiment_tm_nonbase(
        eco_ui, 'recessionUI', rec_path, bl_data, mCount=dist_aGrid_count, verbose=False)

    eco_ad = deepcopy(AggEco)
    eco_ad.switch_shock_type('recessionUI')
    eco_ad.solve()
    tm_AD = run_ad_tm(
        eco_ad, 'recessionUI', rec_path,
        bl_data, AggCons_baseline,
        ADelasticity=ADelasticity,
        num_max_iterations=10,
        convergence_tol=0.004,
        mCount=dist_aGrid_count,
        verbose=False,
    )

    npv_base_C = calculate_NPV(AggCons_baseline, act_T, Rfree)[-1]
    te_noAD = tm_noAD['NPV_AggCons'][-1] - npv_base_C
    te_AD = tm_AD['NPV_AggCons'][-1] - npv_base_C
    ratio = te_AD / te_noAD if te_noAD != 0 else float('nan')
    elapsed = time() - t0

    print(f"{dist_aGrid_count:16d}  {te_noAD:12.6f}  {te_AD:12.6f}  {ratio:10.4f}  {elapsed:5.0f}s")

print(f"\nMC ground truth AD/noAD ≈ 1.36 (from N=80000)")
