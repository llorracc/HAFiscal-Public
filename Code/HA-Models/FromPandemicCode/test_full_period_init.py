"""
Test: does running one full TM period before computing aggregates
close the consumption gap?

Instead of applying a micro-only transition to the ergodic, run
one full TM period (consumption + savings + income + micro transition)
and then compute period-0 aggregates from the resulting distribution.
"""

import os
import sys
import numpy as np
from copy import deepcopy
from time import time

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
    build_experiment_period_tm, compute_period_aggregates_tm,
    compute_analytical_mean_pLvl, _apply_micro_transition,
)
import scipy.sparse as sp

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
base_dict_agg = deepcopy(base_dict)
Splurge = BaseType.Splurge
E_pLvl = compute_analytical_mean_pLvl(BaseType)
E_TranShk = np.array([1.0, 0.7, 0.7, 0.5])
ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20

# Build ergodic
tm_data = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
dist_mGrid = tm_data['dist_mGrid']
M = len(dist_mGrid)

# Solve base and UI agents
base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()

eco_ui = deepcopy(AggEco)
eco_ui.switch_shock_type("UI")
eco_ui.solve()
ui_agent = eco_ui.agents[0]

# ============================================================
# Approach: Run one full TM period from the ergodic, THEN compute
# period-0 aggregates from the resulting distribution
# ============================================================

# For baseline: ergodic → full TM period (base, macro 0→0) → dist_1_base
# Then compute aggregates from dist_1_base using base cPol at macro 0
TM_base, cPol_base = build_experiment_period_tm(
    base_agent, 0, 0, dist_mGrid, Cratio=1.0)

# For UI: ergodic → full TM period (UI, macro 0→ui_path[0]) → dist_1_ui
# Wait — the ergodic is under base config (macro 0). The first experiment
# period transitions from the base ergodic to the UI macro state.
# MC does: base burn-in → save state → switch to UI → hit_with_recession_shock
# The "hit" applies micro transitions at macro=ui_path[0], then income at that state.
# So the full TM period should go from base macro 0 to UI macro ui_path[0].
#
# But build_experiment_period_tm uses the agent's current CondMrkvArrays.
# For base→UI transition, we need the UI agent's structure.
# macro_t=0 means we use cFunc from macro 0 of UI solution.
# macro_next=ui_path[0] means we use CondMrkvArrays[ui_path[0]] and IncShkDstn at ui_path[0].

# Actually, the MC baseline at period 0 works like this:
# - Agents have saved state from burn-in (which ran under base config)
# - run_experiment("base") calls update_mrkv_array("base"), solve, initialize_sim
# - hit_with_recession_shock("base") builds shock history under base CondMrkvArrays
# - Period 0: agents get base income, consume with base cFunc
#
# And MC UI at period 0:
# - Same saved state
# - run_experiment("UI") calls update_mrkv_array("UI"), solve, initialize_sim
# - hit_with_recession_shock("UI") builds shock history under UI CondMrkvArrays
# - Period 0: agents get UI income (based on UI Mrkv), consume with UI cFunc
#
# The key: MC period 0 consumption uses the EXPERIMENT cFunc (base or UI),
# and income from the EXPERIMENT Mrkv. The saved state provides bNrm.
#
# In TM terms: the ergodic represents the saved state's mNrm distribution.
# At period 0, we need to:
# 1. "Undo" the income embedded in the ergodic's mNrm (subtract old TranShk)
# 2. Apply the experiment's micro transition
# 3. Add the experiment's income (new TranShk)
# 4. Compute consumption from experiment cFunc
#
# Steps 1-3 are exactly what a full TM period does (consume, save, transition,
# get income). So running one full TM period from the ergodic should produce
# the correct period-0 distribution.
#
# But there's a subtlety: the full TM period ALSO applies consumption and
# savings, changing the distribution. We want to start from the saved state
# (aNrm distribution), not the post-consumption distribution.
#
# Actually, the ergodic is over mNrm = bNrm + TranShk. The saved state
# has aNrm. The relationship is: mNrm = aNrm * R/(G*PermShk) + TranShk.
# Running a full TM period from mNrm consumes, saves (back to aNrm),
# then computes new mNrm. This is ONE PERIOD of dynamics.
#
# The MC's period 0 starts from saved aNrm, gets new income → new mNrm,
# then consumes. So MC period 0 = (saved aNrm → new mNrm → consume).
# The TM's full period = (ergodic mNrm → consume → save → new mNrm).
# These are OFFSET by half a period.
#
# So running one full TM period from ergodic gives us the distribution
# at the START of period 1, not period 0. For period 0, we need the
# distribution at the start of period 0, which IS the ergodic (with
# the experiment's micro transition applied for the state labels).
#
# Hmm, this is the fundamental timing issue. Let me think again...

# Actually, let me reconsider. In MC:
# - Saved state has aNrm (end of last burn-in period)
# - Period 0 of experiment: get_shocks reads Mrkv[0], PermShk[0], TranShk[0]
# - get_states: bNrm = aNrm * Rfree, mNrm = bNrm + TranShk[0]
# - cNrm = cFunc(mNrm) based on perceived Mrkv
# - aNrm_new = mNrm - cNrm
#
# In TM ergodic:
# - dist over (mNrm, micro_state) represents the steady state
# - mNrm already includes income from the current state
# - This IS the distribution at the start of a period (after receiving income)
#
# So the ergodic = distribution at start of period (with income included).
# MC period 0 = distribution at start of period 0 (with NEW income included).
#
# The difference: ergodic has income from the steady-state Mrkv, while
# MC period 0 has income from the experiment's Mrkv[0].
#
# For the baseline experiment, these are the same (both use base CondMrkvArrays).
# For the UI experiment, the Mrkv[0] differs (UI CondMrkvArrays at macro ui_path[0]).
#
# So the correct period-0 distribution for UI should have:
# - The same aNrm distribution as the ergodic (saved state)
# - Income from the UI Mrkv[0] (which depends on the UI micro transition)
#
# To get this, I need to:
# 1. Extract aNrm from the ergodic: aNrm = mNrm - cFunc(mNrm) [but this is
#    the CONSUMPTION at the current period, not the income]
#
# Actually no. The ergodic mNrm = bNrm + TranShk. And bNrm = aNrm_prev * R/(G*PermShk).
# The aNrm_prev is from the previous period's savings. I can't easily extract it.
#
# Alternative approach: just run one full TM period under BASE config from the
# ergodic to get dist_after_one_base_period. This should equal the ergodic
# (since it's the fixed point). Then run one full TM period under UI config
# from the ergodic. The consumption at this period uses UI cFunc, and the
# resulting distribution has UI income. Compare the consumption.

print("=" * 70)
print("TEST: Full TM period from ergodic")
print("=" * 70)

# Full TM period under base config (should reproduce ergodic)
TM_base_00, cPol_base_0 = build_experiment_period_tm(
    base_agent, 0, 0, dist_mGrid, Cratio=1.0)

# Compute period aggregates from ergodic using base cPol
IncShkDstn_base_0 = [base_agent.IncShkDstn[0][j] for j in range(J)]
agg_base = compute_period_aggregates_tm(
    ergodic, cPol_base_0, dist_mGrid, IncShkDstn_base_0, Splurge)

# Transition ergodic by one base period
dist_after_base = TM_base_00 @ ergodic
if sp.issparse(dist_after_base):
    dist_after_base = np.asarray(dist_after_base).flatten()
dist_after_base = np.maximum(dist_after_base, 0.0)
dist_after_base /= np.sum(dist_after_base)

# Compute aggregates from transitioned distribution
agg_base_after = compute_period_aggregates_tm(
    dist_after_base, cPol_base_0, dist_mGrid, IncShkDstn_base_0, Splurge)

print(f"\nBase: ergodic is fixed point check:")
print(f"  C_splurge_nrm (from ergodic):     {agg_base['C_splurge_nrm']:.8f}")
print(f"  C_splurge_nrm (after 1 TM period):{agg_base_after['C_splurge_nrm']:.8f}")
print(f"  Difference: {agg_base_after['C_splurge_nrm'] - agg_base['C_splurge_nrm']:.2e}")

# Now: UI experiment
# MC at period 0: agents have saved-state aNrm, get UI Mrkv, consume with UI cFunc
# TM approach: use ergodic as starting distribution, compute aggregates with UI cFunc

# Approach A: ergodic + micro-only transition + UI cPol (current BUG-013 fix)
micro_normal = base_agent.CondMrkvArrays[0]
micro_ui_mat = ui_agent.CondMrkvArrays[ui_path[0]]

dist_ui_micro = _apply_micro_transition(ergodic.copy(), micro_ui_mat, M)
_, cPol_ui_0 = build_experiment_period_tm(
    ui_agent, ui_path[0], ui_path[1], dist_mGrid, Cratio=1.0)
IncShkDstn_ui_0 = [ui_agent.IncShkDstn[0][ui_path[0] * J + j] for j in range(J)]
agg_ui_micro = compute_period_aggregates_tm(
    dist_ui_micro, cPol_ui_0, dist_mGrid, IncShkDstn_ui_0, Splurge)

# Approach B: Run one full TM period under BASE config from ergodic,
# then compute aggregates using UI cPol and UI IncShkDstn.
# The idea: the full base TM period reproduces the ergodic (fixed point).
# So dist_after_base ≈ ergodic. This doesn't help.

# Approach C: Run one full TM period under UI config from ergodic.
# This transitions the ergodic through: consume(UI cFunc) → save → UI income → UI micro transition.
# The consumption AT this period uses UI cFunc at ergodic mNrm. The resulting
# distribution has the correct UI income and micro states.
TM_ui_0, cPol_ui_period = build_experiment_period_tm(
    ui_agent, ui_path[0], ui_path[1], dist_mGrid, Cratio=1.0)

# Consumption from ergodic using UI cPol (this is what current propagate does)
agg_ui_from_ergodic = compute_period_aggregates_tm(
    ergodic, cPol_ui_period, dist_mGrid, IncShkDstn_ui_0, Splurge)

# Now transition ergodic by one UI period and compute from THAT distribution
dist_after_ui = TM_ui_0 @ ergodic
if sp.issparse(dist_after_ui):
    dist_after_ui = np.asarray(dist_after_ui).flatten()
dist_after_ui = np.maximum(dist_after_ui, 0.0)
dist_after_ui /= np.sum(dist_after_ui)

agg_ui_after = compute_period_aggregates_tm(
    dist_after_ui, cPol_ui_period, dist_mGrid, IncShkDstn_ui_0, Splurge)

# Approach D: Use ergodic directly with no micro transition
agg_ui_no_micro = compute_period_aggregates_tm(
    ergodic, cPol_ui_period, dist_mGrid, IncShkDstn_ui_0, Splurge)

# Compute TEs
te_micro = (agg_ui_micro['C_splurge_nrm'] - agg_base['C_splurge_nrm']) * E_pLvl
te_after_ui = (agg_ui_after['C_splurge_nrm'] - agg_base_after['C_splurge_nrm']) * E_pLvl
te_ergodic_ui = (agg_ui_from_ergodic['C_splurge_nrm'] - agg_base['C_splurge_nrm']) * E_pLvl
te_no_micro = (agg_ui_no_micro['C_splurge_nrm'] - agg_base['C_splurge_nrm']) * E_pLvl

# MC reference
print(f"\nRunning MC reference (N={N}, 3 seeds)...")
mc_tes = []
for seed in range(3):
    eco = deepcopy(AggEco)
    for a in eco.agents:
        a.AgentCount = N; a.seed = seed * 1000; a.get_economy_data(eco)
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
    mc_tes.append((ui_r['AggCons'][0] - base_r['AggCons'][0]) / N_act)
mc_ref = np.mean(mc_tes)

print(f"\n{'='*70}")
print(f"RESULTS: Period-0 Consumption TE (levels, per-cap)")
print(f"{'='*70}")
print(f"  MC reference:                        {mc_ref:.6f}")
print(f"  TM micro-only transition (current):  {te_micro:.6f}  ({(te_micro-mc_ref)/mc_ref*100:+.1f}%)")
print(f"  TM no micro transition:              {te_no_micro:.6f}  ({(te_no_micro-mc_ref)/mc_ref*100:+.1f}%)")
print(f"  TM ergodic+UI cPol (same as no micro):{te_ergodic_ui:.6f}")
print(f"  TM after 1 full UI period:           {te_after_ui:.6f}  ({(te_after_ui-mc_ref)/mc_ref*100:+.1f}%)")

# Per-state analysis of dist_after_ui
print(f"\nPer-state mean mNrm:")
print(f"  State  ergodic   after_base  after_UI  after_micro_only")
for j in range(J):
    erg = np.dot(dist_mGrid, ergodic[j*M:(j+1)*M]) / max(np.sum(ergodic[j*M:(j+1)*M]), 1e-30)
    ab = np.dot(dist_mGrid, dist_after_base[j*M:(j+1)*M]) / max(np.sum(dist_after_base[j*M:(j+1)*M]), 1e-30)
    au = np.dot(dist_mGrid, dist_after_ui[j*M:(j+1)*M]) / max(np.sum(dist_after_ui[j*M:(j+1)*M]), 1e-30)
    am = np.dot(dist_mGrid, dist_ui_micro[j*M:(j+1)*M]) / max(np.sum(dist_ui_micro[j*M:(j+1)*M]), 1e-30)
    print(f"  [{j}]   {erg:8.4f}    {ab:8.4f}    {au:8.4f}    {am:8.4f}")

print(f"\nPer-state fracs:")
print(f"  State  ergodic   after_base  after_UI  after_micro_only")
for j in range(J):
    fe = np.sum(ergodic[j*M:(j+1)*M])
    fb = np.sum(dist_after_base[j*M:(j+1)*M])
    fu = np.sum(dist_after_ui[j*M:(j+1)*M])
    fm = np.sum(dist_ui_micro[j*M:(j+1)*M])
    print(f"  [{j}]   {fe:.6f}    {fb:.6f}    {fu:.6f}    {fm:.6f}")
