"""
Test: Does the mNrm-shift fix in _apply_micro_transition close the
~21% consumption TE gap between TM and MC for UI?

Key insight: the previous fix attempt (diagnose_cons_gap.py TEST D) only
shifted the UI distribution, but the error is in the BASE distribution:
state 2 → state 3 has ΔTranShk = 0.5 - 0.7 = -0.2, and the TM was
keeping mNrm at the too-high state-2 value.  Both base and UI must be
shifted.

Also tests with identical cFuncs (base cFunc for both) to eliminate
that as a variable.
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
    build_tm_agg_fiscal,
    find_ergodic_distribution,
    _apply_micro_transition,
    build_experiment_period_tm,
    compute_period_aggregates_tm,
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

N = 500000
J = num_base_MrkvStates
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
ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20

# E[TranShk] per micro state
E_TranShk = np.zeros(J)
for j in range(J):
    d = BaseType.IncShkDstn_base[0][j]
    E_TranShk[j] = np.dot(d.pmv, d.atoms[1])

print(f"J={J}, Splurge={Splurge:.4f}, E_pLvl={E_pLvl:.4f}, N={N}")
print(f"E[TranShk] per state: {E_TranShk}")
print(f"ΔTranShk for state 2→3: {E_TranShk[3] - E_TranShk[2]:.4f}")
print(f"ΔTranShk for state 1→2: {E_TranShk[2] - E_TranShk[1]:.4f}")
print(f"ΔTranShk for state 1→1: {E_TranShk[1] - E_TranShk[1]:.4f}")

# ============================================================
# TM with mNrm shift (via propagate_experiment_tm, which now shifts)
# ============================================================
print("\n" + "=" * 70)
print("TEST 1: Full propagate_experiment_tm (with mNrm shift fix)")
print("=" * 70)

t0 = time()
baseline_tm_data = compute_baseline_tm_data(AggEco, dist_aGrid_count=MCOUNT, verbose=False)
bd0 = baseline_tm_data[0]

# Baseline propagation (base agent, base path)
base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
tm_base = propagate_experiment_tm(
    base_agent, bd0['ergodic'], [0]*act_T, bd0['dist_mGrid'],
    bd0['E_pLvl'], Cratio=1.0, act_T=act_T)

# UI propagation (UI agent, UI path)
eco_ui = deepcopy(AggEco)
eco_ui.switch_shock_type("UI")
eco_ui.solve()
ui_agent = eco_ui.agents[0]
tm_ui = propagate_experiment_tm(
    ui_agent, bd0['ergodic'], ui_path, bd0['dist_mGrid'],
    bd0['E_pLvl'], Cratio=1.0, act_T=act_T, shock_type='UI')

tm_income_TE = (tm_ui['AggIncome'][0] - tm_base['AggIncome'][0]) / N
tm_cons_TE = (tm_ui['AggCons'][0] - tm_base['AggCons'][0]) / N
print(f"TM Income TE (per-cap):  {tm_income_TE:.8f}")
print(f"TM Cons TE (per-cap):    {tm_cons_TE:.8f}")
print(f"TM wall time: {time()-t0:.1f}s")

# ============================================================
# TEST 2: Manual step-by-step with identical cFuncs
# ============================================================
print("\n" + "=" * 70)
print("TEST 2: Manual computation with BASE cFunc for both (identical cFuncs)")
print("=" * 70)

ergodic = bd0['ergodic']
dist_mGrid = bd0['dist_mGrid']
M = len(dist_mGrid)

# Get base micro transitions
micro_normal = base_agent.CondMrkvArrays[0]

# Get UI micro transitions
micro_ui_mat = ui_agent.CondMrkvArrays[ui_path[0]]

# Apply micro transitions WITH mNrm shift to both
dist_base = _apply_micro_transition(ergodic.copy(), micro_normal, M,
                                     dist_mGrid=dist_mGrid,
                                     E_TranShk=E_TranShk)
dist_ui = _apply_micro_transition(ergodic.copy(), micro_ui_mat, M,
                                   dist_mGrid=dist_mGrid,
                                   E_TranShk=E_TranShk)

# WITHOUT shift for comparison
dist_base_noshift = _apply_micro_transition(ergodic.copy(), micro_normal, M)
dist_ui_noshift = _apply_micro_transition(ergodic.copy(), micro_ui_mat, M)

# Use BASE cFunc for both (identical cFuncs)
_, cPol_base = build_experiment_period_tm(base_agent, 0, 0, dist_mGrid, Cratio=1.0)

# Compute consumption TE with shift, using identical cFuncs
fracs_base = np.array([np.sum(dist_base[j*M:(j+1)*M]) for j in range(J)])
fracs_ui = np.array([np.sum(dist_ui[j*M:(j+1)*M]) for j in range(J)])
C_nrm_base = sum(np.dot(cPol_base[j], dist_base[j*M:(j+1)*M]) for j in range(J))
C_nrm_ui = sum(np.dot(cPol_base[j], dist_ui[j*M:(j+1)*M]) for j in range(J))
splurge_base = Splurge * np.dot(fracs_base, E_TranShk)
splurge_ui = Splurge * np.dot(fracs_ui, E_TranShk)
cons_base_shifted = (1-Splurge) * C_nrm_base + splurge_base
cons_ui_shifted = (1-Splurge) * C_nrm_ui + splurge_ui
cons_TE_shifted_same_cfunc = (cons_ui_shifted - cons_base_shifted) * E_pLvl

# Without shift, same cFuncs
fracs_base_ns = np.array([np.sum(dist_base_noshift[j*M:(j+1)*M]) for j in range(J)])
fracs_ui_ns = np.array([np.sum(dist_ui_noshift[j*M:(j+1)*M]) for j in range(J)])
C_nrm_base_ns = sum(np.dot(cPol_base[j], dist_base_noshift[j*M:(j+1)*M]) for j in range(J))
C_nrm_ui_ns = sum(np.dot(cPol_base[j], dist_ui_noshift[j*M:(j+1)*M]) for j in range(J))
splurge_base_ns = Splurge * np.dot(fracs_base_ns, E_TranShk)
splurge_ui_ns = Splurge * np.dot(fracs_ui_ns, E_TranShk)
cons_base_ns = (1-Splurge) * C_nrm_base_ns + splurge_base_ns
cons_ui_ns = (1-Splurge) * C_nrm_ui_ns + splurge_ui_ns
cons_TE_noshift_same_cfunc = (cons_ui_ns - cons_base_ns) * E_pLvl

print(f"\nWith mNrm shift, identical cFuncs:")
print(f"  Cons TE (levels, per-cap): {cons_TE_shifted_same_cfunc:.8f}")
print(f"Without mNrm shift, identical cFuncs:")
print(f"  Cons TE (levels, per-cap): {cons_TE_noshift_same_cfunc:.8f}")

# Per-state mean mNrm comparison
print(f"\nPer-state mean mNrm (shifted vs unshifted):")
print(f"  State  shifted_base  unshifted_base  shifted_UI  unshifted_UI  delta_shift")
for j in range(J):
    db_s = dist_base[j*M:(j+1)*M]
    db_n = dist_base_noshift[j*M:(j+1)*M]
    du_s = dist_ui[j*M:(j+1)*M]
    du_n = dist_ui_noshift[j*M:(j+1)*M]
    m_bs = np.dot(dist_mGrid, db_s) / max(np.sum(db_s), 1e-30)
    m_bn = np.dot(dist_mGrid, db_n) / max(np.sum(db_n), 1e-30)
    m_us = np.dot(dist_mGrid, du_s) / max(np.sum(du_s), 1e-30)
    m_un = np.dot(dist_mGrid, du_n) / max(np.sum(du_n), 1e-30)
    print(f"  [{j}]     {m_bs:8.4f}       {m_bn:8.4f}       {m_us:8.4f}      {m_un:8.4f}      {m_bs-m_bn:+.4f}/{m_us-m_un:+.4f}")

# ============================================================
# MC reference
# ============================================================
print("\n" + "=" * 70)
print("TEST 3: MC reference (3 seeds)")
print("=" * 70)

NUM_SEEDS = 3

def run_mc_ui_experiment(seed):
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
    income_te = (ui_r['AggIncome'][0] - base_r['AggIncome'][0]) / N_act
    cons_te = (ui_r['AggCons'][0] - base_r['AggCons'][0]) / N_act
    return income_te, cons_te

mc_income_tes = []
mc_cons_tes = []
for s in range(NUM_SEEDS):
    t0 = time()
    ite, cte = run_mc_ui_experiment(s)
    mc_income_tes.append(ite)
    mc_cons_tes.append(cte)
    print(f"  Seed {s}: income_TE={ite:.8f}, cons_TE={cte:.8f}  ({time()-t0:.0f}s)")

mc_income_TE = np.mean(mc_income_tes)
mc_cons_TE = np.mean(mc_cons_tes)

# ============================================================
# Summary comparison
# ============================================================
print("\n" + "=" * 70)
print("SUMMARY: Period-0 UI Treatment Effects (per-cap, levels)")
print("=" * 70)

print(f"\n  {'Method':<45s}  {'Income TE':>12s}  {'Cons TE':>12s}  {'Cons gap vs MC':>14s}")
print(f"  {'-'*45}  {'-'*12}  {'-'*12}  {'-'*14}")
print(f"  {'MC reference (mean of ' + str(NUM_SEEDS) + ' seeds)':<45s}  {mc_income_TE:12.8f}  {mc_cons_TE:12.8f}  {'—':>14s}")
print(f"  {'TM with mNrm shift (propagate_experiment_tm)':<45s}  {tm_income_TE:12.8f}  {tm_cons_TE:12.8f}  {(tm_cons_TE - mc_cons_TE)/mc_cons_TE*100:+13.1f}%")
print(f"  {'TM shift + identical cFuncs (manual)':<45s}  {'—':>12s}  {cons_TE_shifted_same_cfunc:12.8f}  {(cons_TE_shifted_same_cfunc - mc_cons_TE)/mc_cons_TE*100:+13.1f}%")
print(f"  {'TM NO shift + identical cFuncs (manual)':<45s}  {'—':>12s}  {cons_TE_noshift_same_cfunc:12.8f}  {(cons_TE_noshift_same_cfunc - mc_cons_TE)/mc_cons_TE*100:+13.1f}%")

# Also show per-period for first 5 periods
print(f"\n  Per-period TM treatment effects (first 5):")
print(f"  {'t':>3s}  {'TM_Income_TE':>14s}  {'TM_Cons_TE':>14s}")
for t in range(min(5, act_T)):
    te_y = (tm_ui['AggIncome'][t] - tm_base['AggIncome'][t]) / N
    te_c = (tm_ui['AggCons'][t] - tm_base['AggCons'][t]) / N
    print(f"  {t:3d}  {te_y:14.8f}  {te_c:14.8f}")

print("\nDone.")
