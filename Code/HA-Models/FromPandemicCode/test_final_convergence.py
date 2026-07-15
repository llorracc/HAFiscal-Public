"""
Definitive convergence test with the half-step TM fix.

Confirms that MC cons_TE → TM cons_TE as N → ∞.
Both base and UI use the half-step approach (base_aPol passed).
Single education type, mCount=50 (grid-converged).
"""
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
)

# Setup
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

J = num_base_MrkvStates
BaseType = AggFiscalType(**init_highschool)
BaseType.cycles = 0
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
# BUG-023 fix: was `EmployedIncShkDstn.atoms[0][1] = EmployedIncShkDstn.atoms[0][1] * BaseType.TaxCutIncFactor`
# which mutated one PermShk atom; the intended behavior is to
# rescale every joint atom's TranShk component (atoms[1]).
# See BUGS_private/HAFiscal_BUG-023_taxcut_atoms_typo.md.
EmployedIncShkDstn.atoms = (
    np.asarray(EmployedIncShkDstn.atoms[0], dtype=np.float64),
    np.asarray(EmployedIncShkDstn.atoms[1], dtype=np.float64) * BaseType.TaxCutIncFactor,
)
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

# ── TM reference (half-step, mCount=50) ──
bl_data = compute_baseline_tm_data(AggEco, mCount=50, verbose=False)
bd = bl_data[0]

base_a = deepcopy(BaseType)
base_a.update_mrkv_array("base")
base_a.solve()
r_base_tm = propagate_experiment_tm(
    base_a, bd['ergodic'], [0]*act_T, bd['dist_mGrid'],
    bd['E_pLvl'], act_T=act_T, base_aPol=bd['base_aPol'])

eco_u = deepcopy(AggEco)
eco_u.switch_shock_type("UI")
eco_u.solve()
r_ui_tm = propagate_experiment_tm(
    eco_u.agents[0], bd['ergodic'], ui_path, bd['dist_mGrid'],
    bd['E_pLvl'], act_T=act_T, shock_type='UI', base_aPol=bd['base_aPol'])

N_ref = BaseType.AgentCount
tm_cons_TE = (r_ui_tm['AggCons'][0] - r_base_tm['AggCons'][0]) / N_ref
tm_income_TE = (r_ui_tm['AggIncome'][0] - r_base_tm['AggIncome'][0]) / N_ref

print("=" * 75)
print("DEFINITIVE CONVERGENCE TEST: Half-Step TM vs MC")
print("  Single type (highschool), mCount=50 (grid-converged)")
print("=" * 75)
print(f"\n  TM reference: cons_TE = {tm_cons_TE:.8f}, income_TE = {tm_income_TE:.8f}")

# ── MC convergence sweep ──
NUM_SEEDS = 5

def run_mc_ui(N_agents, seed):
    eco = deepcopy(AggEco)
    for a in eco.agents:
        a.AgentCount = N_agents; a.seed = seed * 1000; a.get_economy_data(eco)
    eco.solve(); eco.reset()
    for a in eco.agents:
        a.initialize_sim(); a.AggDemandFac = 1.0; a.RfreeNow = 1.0; a.CaggNow = 1.0
    eco.make_history(); eco.save_state()
    eco.switch_to_counterfactual_mode("base")
    eco.act_T = act_T
    for a in eco.agents:
        a.T_sim = act_T; a.EconomyMrkvNow_hist = [0] * act_T
    eco.make_idiosyncratic_shock_histories()
    base_r = eco.run_experiment(**base_dict_agg, Full_Output=True)
    eco.store_baseline(base_r['AggCons'])
    eco_x = deepcopy(eco); eco_x.switch_shock_type('UI'); eco_x.solve()
    d = base_dict_agg.copy(); d.update(UI_changes); d['EconomyMrkv_init'] = ui_path
    ui_r = eco_x.run_experiment(**d, Full_Output=True)
    N_act = sum(a.AgentCount for a in eco.agents)
    return ((ui_r['AggIncome'][0] - base_r['AggIncome'][0]) / N_act,
            (ui_r['AggCons'][0] - base_r['AggCons'][0]) / N_act)

print(f"\n  {'N':>10s}  {'Seeds':>5s}  {'MC cons_TE':>12s}  {'stderr':>10s}  "
      f"{'gap vs TM':>10s}  {'gap/SE':>8s}  {'MC inc_TE':>12s}  {'time':>7s}")
print("  " + "-" * 85)

for N_agents in [200000, 500000, 1000000]:
    t0 = time()
    ites, ctes = [], []
    for s in range(NUM_SEEDS):
        ite, cte = run_mc_ui(N_agents, seed=s)
        ites.append(ite); ctes.append(cte)
    elapsed = time() - t0
    mc_c = np.mean(ctes)
    mc_c_std = np.std(ctes, ddof=1)
    mc_c_se = mc_c_std / np.sqrt(NUM_SEEDS)
    mc_y = np.mean(ites)
    gap = tm_cons_TE - mc_c
    gap_se = gap / mc_c_se if mc_c_se > 0 else float('inf')
    print(f"  {N_agents:10d}  {NUM_SEEDS:5d}  {mc_c:12.8f}  {mc_c_se:10.8f}  "
          f"{gap:+10.6f}  {gap_se:+7.1f}σ  {mc_y:12.8f}  {elapsed:6.0f}s")

print(f"\n  TM cons_TE = {tm_cons_TE:.8f} (half-step, mCount=50)")
print(f"  Prediction: |gap/SE| < 2 at large N (consistent with sampling noise)")
print(f"\n  TM income_TE = {tm_income_TE:.8f}")
