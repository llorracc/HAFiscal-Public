"""
Test: does a fraction-only micro transition close the consumption gap?

Instead of mixing mNrm distributions between states (current behavior),
just rescale each state's total mass to match the post-transition fractions
while preserving the within-state mNrm shape.
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
    build_tm_agg_fiscal, find_ergodic_distribution,
    _apply_micro_transition, build_experiment_period_tm,
    compute_analytical_mean_pLvl,
)

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
MCOUNT = 200

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
Splurge = BaseType.Splurge
E_pLvl = compute_analytical_mean_pLvl(BaseType)
E_TranShk = np.array([1.0, 0.7, 0.7, 0.5])
ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20

# Build ergodic
tm_data = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
dist_mGrid = tm_data['dist_mGrid']
M = len(dist_mGrid)

# Agents and cPol
base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
_, cPol_base = build_experiment_period_tm(base_agent, 0, 0, dist_mGrid, Cratio=1.0)

eco_ui = deepcopy(AggEco)
eco_ui.switch_shock_type("UI")
eco_ui.solve()
ui_agent = eco_ui.agents[0]
_, cPol_ui = build_experiment_period_tm(ui_agent, ui_path[0], ui_path[1], dist_mGrid, Cratio=1.0)

micro_normal = base_agent.CondMrkvArrays[0]
micro_ui_mat = ui_agent.CondMrkvArrays[ui_path[0]]


def apply_fraction_only_transition(dist, micro_trans, M):
    """Rescale state masses without mixing mNrm distributions."""
    J_loc = micro_trans.shape[0]
    old_fracs = np.array([np.sum(dist[j*M:(j+1)*M]) for j in range(J_loc)])
    new_fracs = micro_trans.T @ old_fracs
    new_dist = dist.copy()
    for j in range(J_loc):
        if old_fracs[j] > 1e-30:
            new_dist[j*M:(j+1)*M] *= new_fracs[j] / old_fracs[j]
        elif new_fracs[j] > 1e-30:
            # State was empty, give it uniform mass (shouldn't happen in practice)
            new_dist[j*M:(j+1)*M] = new_fracs[j] / M
    s = np.sum(new_dist)
    if s > 0:
        new_dist /= s
    return new_dist


def compute_cons(dist, cPol, fracs, Splurge, E_TranShk):
    """Compute total normalized consumption from distribution."""
    J_loc = len(cPol)
    C_nrm = sum(np.dot(cPol[j], dist[j*M:(j+1)*M]) for j in range(J_loc))
    income = np.dot(fracs, E_TranShk)
    return (1 - Splurge) * C_nrm + Splurge * income


# ============================================================
# Three approaches to the micro transition
# ============================================================

print("=" * 70)
print("THREE APPROACHES TO INITIAL MICRO TRANSITION")
print("=" * 70)

approaches = {}

# Approach 1: Current (mixing) micro transition
dist_base_mix = _apply_micro_transition(ergodic.copy(), micro_normal, M)
dist_ui_mix = _apply_micro_transition(ergodic.copy(), micro_ui_mat, M)
fracs_base_mix = np.array([np.sum(dist_base_mix[j*M:(j+1)*M]) for j in range(J)])
fracs_ui_mix = np.array([np.sum(dist_ui_mix[j*M:(j+1)*M]) for j in range(J)])
cons_base_mix = compute_cons(dist_base_mix, cPol_base, fracs_base_mix, Splurge, E_TranShk)
cons_ui_mix = compute_cons(dist_ui_mix, cPol_ui, fracs_ui_mix, Splurge, E_TranShk)
approaches['mixing'] = (cons_ui_mix - cons_base_mix) * E_pLvl

# Approach 2: Fraction-only micro transition
dist_base_frac = apply_fraction_only_transition(ergodic.copy(), micro_normal, M)
dist_ui_frac = apply_fraction_only_transition(ergodic.copy(), micro_ui_mat, M)
fracs_base_frac = np.array([np.sum(dist_base_frac[j*M:(j+1)*M]) for j in range(J)])
fracs_ui_frac = np.array([np.sum(dist_ui_frac[j*M:(j+1)*M]) for j in range(J)])
cons_base_frac = compute_cons(dist_base_frac, cPol_base, fracs_base_frac, Splurge, E_TranShk)
cons_ui_frac = compute_cons(dist_ui_frac, cPol_ui, fracs_ui_frac, Splurge, E_TranShk)
approaches['fraction_only'] = (cons_ui_frac - cons_base_frac) * E_pLvl

# Approach 3: No micro transition at all (raw ergodic)
fracs_erg = np.array([np.sum(ergodic[j*M:(j+1)*M]) for j in range(J)])
cons_base_erg = compute_cons(ergodic.copy(), cPol_base, fracs_erg, Splurge, E_TranShk)
cons_ui_erg = compute_cons(ergodic.copy(), cPol_ui, fracs_erg, Splurge, E_TranShk)
approaches['no_transition'] = (cons_ui_erg - cons_base_erg) * E_pLvl

# MC reference
print(f"\nRunning MC (N={N}, 3 seeds)...")
base_dict_agg = deepcopy(base_dict)
mc_cons_tes = []
for seed in range(3):
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
    eco_x = deepcopy(eco)
    eco_x.switch_shock_type('UI')
    eco_x.solve()
    d = base_dict_agg.copy()
    d.update(UI_changes)
    d['EconomyMrkv_init'] = ui_path
    ui_r = eco_x.run_experiment(**d, Full_Output=True)
    N_act = sum(a.AgentCount for a in eco.agents)
    mc_cons_tes.append((ui_r['AggCons'][0] - base_r['AggCons'][0]) / N_act)
    print(f"  Seed {seed}: cons TE = {mc_cons_tes[-1]:.6f}")

mc_ref = np.mean(mc_cons_tes)

# Results
print(f"\n{'='*70}")
print(f"RESULTS: Consumption TE (levels, per-cap)")
print(f"{'='*70}")
print(f"  MC reference (3 seeds):    {mc_ref:.6f}")
print(f"  TM mixing transition:      {approaches['mixing']:.6f}  (err: {(approaches['mixing']-mc_ref)/mc_ref*100:+.1f}%)")
print(f"  TM fraction-only:          {approaches['fraction_only']:.6f}  (err: {(approaches['fraction_only']-mc_ref)/mc_ref*100:+.1f}%)")
print(f"  TM no transition:          {approaches['no_transition']:.6f}  (err: {(approaches['no_transition']-mc_ref)/mc_ref*100:+.1f}%)")

# Also check: per-state mean mNrm for fraction-only
print(f"\nPer-state mean mNrm:")
print(f"  State  ergodic   mixing_base  mixing_UI  frac_base  frac_UI")
for j in range(J):
    erg_m = np.dot(dist_mGrid, ergodic[j*M:(j+1)*M]) / max(np.sum(ergodic[j*M:(j+1)*M]), 1e-30)
    mix_b = np.dot(dist_mGrid, dist_base_mix[j*M:(j+1)*M]) / max(np.sum(dist_base_mix[j*M:(j+1)*M]), 1e-30)
    mix_u = np.dot(dist_mGrid, dist_ui_mix[j*M:(j+1)*M]) / max(np.sum(dist_ui_mix[j*M:(j+1)*M]), 1e-30)
    frac_b = np.dot(dist_mGrid, dist_base_frac[j*M:(j+1)*M]) / max(np.sum(dist_base_frac[j*M:(j+1)*M]), 1e-30)
    frac_u = np.dot(dist_mGrid, dist_ui_frac[j*M:(j+1)*M]) / max(np.sum(dist_ui_frac[j*M:(j+1)*M]), 1e-30)
    print(f"  [{j}]   {erg_m:8.4f}    {mix_b:8.4f}   {mix_u:8.4f}    {frac_b:8.4f}   {frac_u:8.4f}")

# Verify fractions are the same for both approaches
print(f"\nMicro fracs (should match between mixing and fraction-only):")
print(f"  mixing base:  {fracs_base_mix}")
print(f"  frac base:    {fracs_base_frac}")
print(f"  mixing UI:    {fracs_ui_mix}")
print(f"  frac UI:      {fracs_ui_frac}")
