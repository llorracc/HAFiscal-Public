"""Compare single-seed output with and without stratify_by_wealth."""
import os, sys, numpy as np
from copy import deepcopy
from time import time

sys.argv = sys.argv[:1]
os.environ["MPLBACKEND"] = "Agg"
import matplotlib; matplotlib.use("Agg")

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import calculate_NPV

(init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes) = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

BaseType = AggFiscalType(**init_college)
BaseType.cycles = 0
BaseType.DiscFac = DiscFacDstns[2].atoms[0][0]
AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

IncShkDstn_unemp = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])
BaseType.IncShkDstn[0].seed = 763607780
BaseType.IncShkDstn[0].reset()
BaseType.IncShkDstn = [[BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
BaseType.IncShkDstn_base = BaseType.IncShkDstn
BaseType.IncShkDstn_recession = [BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
BaseType.IncShkDstn_recessionUI = BaseType.IncShkDstn_recession
BaseType.IncShkDstn_recessionTaxCut = deepcopy(BaseType.IncShkDstn_recession)
BaseType.IncShkDstn_recessionCheck = deepcopy(BaseType.IncShkDstn_recession)
AggEco.agents = [BaseType]
BaseType.AgentCount = 1
AggEco.solve()

act_T = AggEco.act_T
base_dict_agg = deepcopy(base_dict)
Rfree = BaseType.Rfree[0]

rec_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20
for t in range(3):
    rec_path[t] = rec_path[t] + 1


def run_one(seed, N_mc, stratify):
    eco_mc = deepcopy(AggEco)
    for a in eco_mc.agents:
        a.AgentCount = N_mc
        a.seed = seed
        a.mc_shuffle = True
        a.income_shuffle = True
        a.init_shuffle = True
        a.markov_shuffle = True
        a.death_shuffle = True
        a.stratify_by_wealth = stratify
        a.get_economy_data(eco_mc)
    eco_mc.solve()
    eco_mc.reset()
    for a in eco_mc.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0
    eco_mc.make_history()
    for a in eco_mc.agents:
        a._burnin_aNrm = np.asarray(a.state_now['aNrm'], dtype=float).copy()
    eco_mc.save_state()
    eco_mc.switch_to_counterfactual_mode('base')
    eco_mc.act_T = act_T
    for a in eco_mc.agents:
        a.T_sim = act_T
        a.EconomyMrkvNow_hist = [0] * act_T
    eco_mc.make_idiosyncratic_shock_histories()

    mc_base = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
    eco_mc.store_baseline(mc_base['AggCons'])

    eco_ui = deepcopy(eco_mc)
    eco_ui.switch_shock_type('recessionUI')
    eco_ui.solve()
    d_ui = base_dict_agg.copy()
    d_ui.update(recession_UI_changes)
    d_ui['EconomyMrkv_init'] = rec_path
    mc_noAD = eco_ui.run_experiment(**d_ui, Full_Output=True)

    npv_base_C = calculate_NPV(np.array(mc_base['AggCons']), act_T, Rfree)[-1]
    npv_noAD_C = calculate_NPV(np.array(mc_noAD['AggCons']), act_T, Rfree)[-1]

    # Return the FULL Mrkv history so we can compare directly
    mrkv_hist = np.asarray(mc_noAD['Mrkv_hist'])
    te_noAD = npv_noAD_C - npv_base_C
    return te_noAD, mrkv_hist, mc_noAD


print("Running seed=42000 with stratify_by_wealth=False...")
t0 = time()
te_off, mrkv_off, mc_off = run_one(42000, 49*15*5, stratify=False)
print(f"  te_noAD = {te_off:.2f}  ({time()-t0:.0f}s)")

print("Running seed=42000 with stratify_by_wealth=True...")
t0 = time()
te_on, mrkv_on, mc_on = run_one(42000, 49*15*5, stratify=True)
print(f"  te_noAD = {te_on:.2f}  ({time()-t0:.0f}s)")

print()
print(f"te_noAD_off = {te_off:.2f}")
print(f"te_noAD_on  = {te_on:.2f}")
print(f"Identical te_noAD? {np.isclose(te_off, te_on)}")
print()
print(f"Markov histories identical? {np.array_equal(mrkv_off, mrkv_on)}")
if not np.array_equal(mrkv_off, mrkv_on):
    n_diff = int(np.sum(mrkv_off != mrkv_on))
    print(f"  Mrkv_hist differs at {n_diff} (t, agent) cells out of {mrkv_off.size}")
else:
    print("  Sort_key is being IGNORED — this is the bug")
print()
print(f"aNrm histories identical? {np.array_equal(np.asarray(mc_off['aNrm_all']), np.asarray(mc_on['aNrm_all']))}")
