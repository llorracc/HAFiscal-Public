"""
Convergence test: does the ~2-3% UI consumption TE gap close with
more MC agents and finer TM grids?

Single education type (highschool). Tests:
1. TM grid convergence: mCount = 50, 100, 200, 400, 800
2. MC convergence: N = 100K, 500K, 1M with 5 seeds each
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
# Setup (single type: highschool)
# ============================================================
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

print("=" * 70)
print("UI CONSUMPTION TE CONVERGENCE TEST")
print("  Single type (highschool), 1 discount factor")
print("=" * 70)

# ============================================================
# Part 1: TM grid convergence
# ============================================================
print("\n--- TM grid convergence ---")
print(f"{'mCount':>8s}  {'Income TE':>12s}  {'Cons TE':>12s}  {'Time':>8s}")
print("-" * 50)

tm_results = {}
for mcount in [50, 100, 200, 400, 800]:
    t0 = time()
    bl_data = compute_baseline_tm_data(AggEco, mCount=mcount, verbose=False)
    bd = bl_data[0]

    # Baseline
    base_a = deepcopy(BaseType)
    base_a.update_mrkv_array("base")
    base_a.solve()
    N_ref = base_a.AgentCount
    r_base = propagate_experiment_tm(
        base_a, bd['ergodic'], [0]*act_T, bd['dist_mGrid'],
        bd['E_pLvl'], Cratio=1.0, act_T=act_T)

    # UI
    eco_u = deepcopy(AggEco)
    eco_u.switch_shock_type("UI")
    eco_u.solve()
    r_ui = propagate_experiment_tm(
        eco_u.agents[0], bd['ergodic'], ui_path, bd['dist_mGrid'],
        bd['E_pLvl'], Cratio=1.0, act_T=act_T, shock_type='UI')

    te_y = (r_ui['AggIncome'][0] - r_base['AggIncome'][0]) / N_ref
    te_c = (r_ui['AggCons'][0] - r_base['AggCons'][0]) / N_ref
    elapsed = time() - t0
    print(f"{mcount:8d}  {te_y:12.8f}  {te_c:12.8f}  {elapsed:7.1f}s")
    tm_results[mcount] = {'income_te': te_y, 'cons_te': te_c}

# Richardson extrapolation: if error ~ 1/M^2, use M=400 and M=800
te_400 = tm_results[400]['cons_te']
te_800 = tm_results[800]['cons_te']
te_extrap = te_800 + (te_800 - te_400) / 3  # assuming quadratic convergence
print(f"\nRichardson extrapolation (M→∞): cons_TE ≈ {te_extrap:.8f}")
print(f"TM converged value (M=800):     cons_TE = {te_800:.8f}")

# ============================================================
# Part 2: MC convergence
# ============================================================
print("\n--- MC convergence ---")

NUM_SEEDS = 5

def run_mc_ui(N_agents, seed):
    eco = deepcopy(AggEco)
    for a in eco.agents:
        a.AgentCount = N_agents
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

    eco_x = deepcopy(eco)
    eco_x.switch_shock_type('UI')
    eco_x.solve()
    d = base_dict_agg.copy()
    d.update(UI_changes)
    d['EconomyMrkv_init'] = ui_path
    ui_r = eco_x.run_experiment(**d, Full_Output=True)

    N_act = sum(a.AgentCount for a in eco.agents)
    return {
        'income_te': (ui_r['AggIncome'][0] - base_r['AggIncome'][0]) / N_act,
        'cons_te': (ui_r['AggCons'][0] - base_r['AggCons'][0]) / N_act,
    }

print(f"{'N':>10s}  {'Seeds':>5s}  {'Cons TE mean':>12s}  {'Cons TE std':>12s}  "
      f"{'StdErr of mean':>14s}  {'Income TE':>12s}  {'Time':>8s}")
print("-" * 90)

mc_results = {}
for N_agents in [100000, 500000, 1000000]:
    t0 = time()
    results = []
    for s in range(NUM_SEEDS):
        results.append(run_mc_ui(N_agents, seed=s))

    cons_tes = [r['cons_te'] for r in results]
    income_tes = [r['income_te'] for r in results]
    mean_c = np.mean(cons_tes)
    std_c = np.std(cons_tes, ddof=1)
    stderr_c = std_c / np.sqrt(NUM_SEEDS)
    mean_y = np.mean(income_tes)
    elapsed = time() - t0

    print(f"{N_agents:10d}  {NUM_SEEDS:5d}  {mean_c:12.8f}  {std_c:12.8f}  "
          f"{stderr_c:14.8f}  {mean_y:12.8f}  {elapsed:7.0f}s")
    mc_results[N_agents] = {
        'cons_te_mean': mean_c, 'cons_te_std': std_c,
        'cons_te_stderr': stderr_c, 'income_te_mean': mean_y,
    }

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 70)
print("CONVERGENCE SUMMARY")
print("=" * 70)

tm_ref = tm_results[800]['cons_te']
mc_best = mc_results[max(mc_results.keys())]

print(f"\n  TM (M=800):      cons_TE = {tm_ref:.8f}")
print(f"  TM (extrap M→∞): cons_TE ≈ {te_extrap:.8f}")
print(f"  MC (N={max(mc_results.keys())}, {NUM_SEEDS} seeds):")
print(f"    cons_TE mean   = {mc_best['cons_te_mean']:.8f}")
print(f"    cons_TE stderr = {mc_best['cons_te_stderr']:.8f}")
print(f"    95% CI: [{mc_best['cons_te_mean'] - 1.96*mc_best['cons_te_stderr']:.8f}, "
      f"{mc_best['cons_te_mean'] + 1.96*mc_best['cons_te_stderr']:.8f}]")

gap = tm_ref - mc_best['cons_te_mean']
gap_in_se = gap / mc_best['cons_te_stderr'] if mc_best['cons_te_stderr'] > 0 else float('inf')
print(f"\n  Gap (TM - MC):   {gap:.8f}  ({gap/mc_best['cons_te_mean']*100:+.2f}%)")
print(f"  Gap in SE units: {gap_in_se:.1f}")
print(f"  (|gap| < 2 SE → consistent with MC noise)")

print("\nDone.")
