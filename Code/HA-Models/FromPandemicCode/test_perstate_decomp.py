"""
Per-state decomposition: where exactly does the ~3% normalized
consumption TE gap arise?

For each micro state j, compare:
- MC's mean cNrm, mean mNrm, fraction, TranShk contribution
- TM's distribution-weighted mean cNrm, mean mNrm, fraction

This pinpoints which state/transition contributes the gap.
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
MCOUNT = 50
Splurge = None

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
Splurge = BaseType.Splurge
E_pLvl = compute_analytical_mean_pLvl(BaseType)
ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20

E_TranShk = np.zeros(J)
for j in range(J):
    d = BaseType.IncShkDstn_base[0][j]
    E_TranShk[j] = np.dot(d.pmv, d.atoms[1])

print(f"N={N}, Splurge={Splurge:.4f}, E_pLvl={E_pLvl:.4f}")

# ============================================================
# TM: per-state distributions after micro transition
# ============================================================
print("\n--- TM per-state details ---")

tm_data = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
dist_mGrid = tm_data['dist_mGrid']
M = len(dist_mGrid)

# Get micro transitions
base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
micro_normal = base_agent.CondMrkvArrays[0]

eco_ui = deepcopy(AggEco)
eco_ui.switch_shock_type("UI")
eco_ui.solve()
ui_agent = eco_ui.agents[0]
micro_ui = ui_agent.CondMrkvArrays[ui_path[0]]

# Apply micro transitions with mNrm shift
dist_base = _apply_micro_transition(ergodic.copy(), micro_normal, M,
                                     dist_mGrid=dist_mGrid, E_TranShk=E_TranShk)
dist_ui = _apply_micro_transition(ergodic.copy(), micro_ui, M,
                                   dist_mGrid=dist_mGrid, E_TranShk=E_TranShk)

# Get cPols
_, cPol_base = build_experiment_period_tm(base_agent, 0, 0, dist_mGrid, Cratio=1.0)
_, cPol_ui = build_experiment_period_tm(ui_agent, ui_path[0], ui_path[1], dist_mGrid, Cratio=1.0)

# Per-state TM statistics
print(f"\n  {'State':>5s}  {'frac_base':>10s}  {'frac_UI':>10s}  {'mean_mNrm_b':>12s}  {'mean_mNrm_u':>12s}  {'mean_cNrm_b':>12s}  {'mean_cNrm_u':>12s}")
tm_C_nrm_base_j = np.zeros(J)
tm_C_nrm_ui_j = np.zeros(J)
tm_frac_base = np.zeros(J)
tm_frac_ui = np.zeros(J)
for j in range(J):
    db = dist_base[j*M:(j+1)*M]
    du = dist_ui[j*M:(j+1)*M]
    fb = np.sum(db)
    fu = np.sum(du)
    tm_frac_base[j] = fb
    tm_frac_ui[j] = fu
    mean_m_b = np.dot(dist_mGrid, db) / max(fb, 1e-30)
    mean_m_u = np.dot(dist_mGrid, du) / max(fu, 1e-30)
    c_b = np.dot(cPol_base[j], db)
    c_u = np.dot(cPol_ui[j], du)
    tm_C_nrm_base_j[j] = c_b
    tm_C_nrm_ui_j[j] = c_u
    mean_c_b = c_b / max(fb, 1e-30)
    mean_c_u = c_u / max(fu, 1e-30)
    print(f"  [{j:1d}]    {fb:10.6f}  {fu:10.6f}  {mean_m_b:12.6f}  {mean_m_u:12.6f}  {mean_c_b:12.6f}  {mean_c_u:12.6f}")

# TM total normalized TE
tm_nonsplurge_TE_nrm = (1-Splurge) * (sum(tm_C_nrm_ui_j) - sum(tm_C_nrm_base_j))
tm_splurge_TE_nrm = Splurge * (np.dot(tm_frac_ui, E_TranShk) - np.dot(tm_frac_base, E_TranShk))
tm_total_TE_nrm = tm_nonsplurge_TE_nrm + tm_splurge_TE_nrm
print(f"\n  TM normalized TE: nonsplurge={tm_nonsplurge_TE_nrm:.8f}, splurge={tm_splurge_TE_nrm:.8f}, total={tm_total_TE_nrm:.8f}")
print(f"  TM levels TE:     {tm_total_TE_nrm * E_pLvl:.8f}")

# ============================================================
# MC: per-state details at period 0
# ============================================================
print("\n--- MC per-state details ---")

def setup_and_run(seed=42):
    """Run base+UI from same burn-in, return per-agent period-0 data."""
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

    # Base experiment
    base_r = eco.run_experiment(**base_dict_agg, Full_Output=True)
    eco.store_baseline(base_r['AggCons'])

    # UI experiment from same saved state
    eco_x = deepcopy(eco)
    eco_x.switch_shock_type('UI')
    eco_x.solve()
    d = base_dict_agg.copy()
    d.update(UI_changes)
    d['EconomyMrkv_init'] = ui_path
    ui_r = eco_x.run_experiment(**d, Full_Output=True)

    return base_r, ui_r

t0 = time()
base_r, ui_r = setup_and_run(seed=42)
print(f"  MC time: {time()-t0:.0f}s")

# Extract period-0 data
cNrm_b = base_r['cNrm_all'][0]
cNrm_u = ui_r['cNrm_all'][0]
mNrm_b = base_r['mNrm_all'][0]
mNrm_u = ui_r['mNrm_all'][0]
pLvl_b = base_r['pLvl_all'][0]
pLvl_u = ui_r['pLvl_all'][0]
TranShk_b = base_r.get('TranShk_all', [None])[0]
TranShk_u = ui_r.get('TranShk_all', [None])[0]
if TranShk_b is None:
    TranShk_b = np.ones(N)  # fallback
    TranShk_u = np.ones(N)

mrkv_b = base_r.get('Mrkv_hist', [None])[0]
mrkv_u = ui_r.get('Mrkv_hist', [None])[0]
if mrkv_b is None:
    # Try shock_history
    mrkv_b = np.zeros(N, dtype=int)
    mrkv_u = np.zeros(N, dtype=int)

micro_b = mrkv_b % J
micro_u = mrkv_u % J

# Per-state MC statistics
print(f"\n  {'State':>5s}  {'frac_base':>10s}  {'frac_UI':>10s}  {'mean_mNrm_b':>12s}  {'mean_mNrm_u':>12s}  {'mean_cNrm_b':>12s}  {'mean_cNrm_u':>12s}")
mc_frac_base = np.zeros(J)
mc_frac_ui = np.zeros(J)
mc_mean_mNrm_b = np.zeros(J)
mc_mean_mNrm_u = np.zeros(J)
mc_mean_cNrm_b = np.zeros(J)
mc_mean_cNrm_u = np.zeros(J)
for j in range(J):
    mask_b = micro_b == j
    mask_u = micro_u == j
    fb = np.mean(mask_b)
    fu = np.mean(mask_u)
    mc_frac_base[j] = fb
    mc_frac_ui[j] = fu
    m_b = np.mean(mNrm_b[mask_b]) if np.sum(mask_b) > 0 else 0
    m_u = np.mean(mNrm_u[mask_u]) if np.sum(mask_u) > 0 else 0
    c_b = np.mean(cNrm_b[mask_b]) if np.sum(mask_b) > 0 else 0
    c_u = np.mean(cNrm_u[mask_u]) if np.sum(mask_u) > 0 else 0
    mc_mean_mNrm_b[j] = m_b
    mc_mean_mNrm_u[j] = m_u
    mc_mean_cNrm_b[j] = c_b
    mc_mean_cNrm_u[j] = c_u
    print(f"  [{j:1d}]    {fb:10.6f}  {fu:10.6f}  {m_b:12.6f}  {m_u:12.6f}  {c_b:12.6f}  {c_u:12.6f}")

# MC normalized TE
mc_nonsplurge = (1-Splurge) * (np.mean(cNrm_u) - np.mean(cNrm_b))
mc_splurge = Splurge * (np.mean(TranShk_u) - np.mean(TranShk_b))
mc_total_nrm = mc_nonsplurge + mc_splurge
print(f"\n  MC normalized TE: nonsplurge={mc_nonsplurge:.8f}, splurge={mc_splurge:.8f}, total={mc_total_nrm:.8f}")
print(f"  MC levels TE:     {mc_total_nrm * E_pLvl:.8f}")

# ============================================================
# Direct comparison
# ============================================================
print("\n" + "=" * 70)
print("DIRECT COMPARISON: TM vs MC per-state")
print("=" * 70)

print(f"\n  Fractions:")
print(f"  {'State':>5s}  {'TM_base':>10s}  {'MC_base':>10s}  {'diff':>10s}  {'TM_UI':>10s}  {'MC_UI':>10s}  {'diff':>10s}")
for j in range(J):
    print(f"  [{j:1d}]    {tm_frac_base[j]:10.6f}  {mc_frac_base[j]:10.6f}  {tm_frac_base[j]-mc_frac_base[j]:+10.6f}  "
          f"{tm_frac_ui[j]:10.6f}  {mc_frac_ui[j]:10.6f}  {tm_frac_ui[j]-mc_frac_ui[j]:+10.6f}")

print(f"\n  Mean mNrm:")
print(f"  {'State':>5s}  {'TM_base':>10s}  {'MC_base':>10s}  {'diff':>10s}  {'TM_UI':>10s}  {'MC_UI':>10s}  {'diff':>10s}")
tm_mean_mNrm_b = np.zeros(J)
tm_mean_mNrm_u = np.zeros(J)
for j in range(J):
    db = dist_base[j*M:(j+1)*M]
    du = dist_ui[j*M:(j+1)*M]
    tm_mb = np.dot(dist_mGrid, db) / max(np.sum(db), 1e-30)
    tm_mu = np.dot(dist_mGrid, du) / max(np.sum(du), 1e-30)
    tm_mean_mNrm_b[j] = tm_mb
    tm_mean_mNrm_u[j] = tm_mu
    print(f"  [{j:1d}]    {tm_mb:10.4f}  {mc_mean_mNrm_b[j]:10.4f}  {tm_mb-mc_mean_mNrm_b[j]:+10.4f}  "
          f"{tm_mu:10.4f}  {mc_mean_mNrm_u[j]:10.4f}  {tm_mu-mc_mean_mNrm_u[j]:+10.4f}")

print(f"\n  Mean cNrm (per state, conditional):")
print(f"  {'State':>5s}  {'TM_base':>10s}  {'MC_base':>10s}  {'diff':>10s}  {'TM_UI':>10s}  {'MC_UI':>10s}  {'diff':>10s}")
for j in range(J):
    db = dist_base[j*M:(j+1)*M]
    du = dist_ui[j*M:(j+1)*M]
    fb = max(np.sum(db), 1e-30)
    fu = max(np.sum(du), 1e-30)
    tm_cb = np.dot(cPol_base[j], db) / fb
    tm_cu = np.dot(cPol_ui[j], du) / fu
    print(f"  [{j:1d}]    {tm_cb:10.6f}  {mc_mean_cNrm_b[j]:10.6f}  {tm_cb-mc_mean_cNrm_b[j]:+10.6f}  "
          f"{tm_cu:10.6f}  {mc_mean_cNrm_u[j]:10.6f}  {tm_cu-mc_mean_cNrm_u[j]:+10.6f}")

# Per-state contribution to the non-splurge TE
print(f"\n  Per-state non-splurge contribution to TE:")
print(f"  {'State':>5s}  {'TM contrib':>12s}  {'MC contrib':>12s}  {'diff':>12s}")
total_tm = 0.0
total_mc = 0.0
for j in range(J):
    db = dist_base[j*M:(j+1)*M]
    du = dist_ui[j*M:(j+1)*M]
    # TM: (1-S) * [dot(cPol_ui[j], du) - dot(cPol_base[j], db)]
    tm_j = (1-Splurge) * (np.dot(cPol_ui[j], du) - np.dot(cPol_base[j], db))
    # MC: (1-S) * [sum(cNrm_u[mask_u]) - sum(cNrm_b[mask_b])] / N
    mask_b = micro_b == j
    mask_u = micro_u == j
    mc_j = (1-Splurge) * (np.sum(cNrm_u[mask_u]) - np.sum(cNrm_b[mask_b])) / N
    total_tm += tm_j
    total_mc += mc_j
    print(f"  [{j:1d}]    {tm_j:12.8f}  {mc_j:12.8f}  {tm_j-mc_j:+12.8f}")
print(f"  Total  {total_tm:12.8f}  {total_mc:12.8f}  {total_tm-total_mc:+12.8f}")

# Same for splurge
print(f"\n  Per-state splurge contribution to TE:")
total_tm_s = 0.0
total_mc_s = 0.0
for j in range(J):
    tm_s_j = Splurge * (tm_frac_ui[j] * E_TranShk[j] - tm_frac_base[j] * E_TranShk[j])
    mask_b = micro_b == j
    mask_u = micro_u == j
    mc_s_j = Splurge * (np.sum(TranShk_u[mask_u]) - np.sum(TranShk_b[mask_b])) / N
    total_tm_s += tm_s_j
    total_mc_s += mc_s_j
    print(f"  [{j:1d}]    {tm_s_j:12.8f}  {mc_s_j:12.8f}  {tm_s_j-mc_s_j:+12.8f}")
print(f"  Total  {total_tm_s:12.8f}  {total_mc_s:12.8f}  {total_tm_s-total_mc_s:+12.8f}")

print(f"\n  Overall TE (nrm):  TM={total_tm+total_tm_s:.8f}  MC={total_mc+total_mc_s:.8f}")
print(f"  Gap: {(total_tm+total_tm_s)-(total_mc+total_mc_s):+.8f}  ({((total_tm+total_tm_s)-(total_mc+total_mc_s))/(total_mc+total_mc_s)*100:+.2f}%)")

# ============================================================
# Check: are agents paired between experiments?
# ============================================================
print(f"\n--- Agent pairing check ---")
# In a perfectly paired experiment, agents in state 0 in BOTH experiments
# should have identical mNrm (same transition, same shocks)
both_state0 = (micro_b == 0) & (micro_u == 0)
print(f"  Agents in state 0 in both: {np.sum(both_state0)} / {N}")
if np.sum(both_state0) > 0:
    mNrm_diff = mNrm_u[both_state0] - mNrm_b[both_state0]
    cNrm_diff = cNrm_u[both_state0] - cNrm_b[both_state0]
    print(f"  max|ΔmNrm|: {np.max(np.abs(mNrm_diff)):.6e}")
    print(f"  max|ΔcNrm|: {np.max(np.abs(cNrm_diff)):.6e}")
    print(f"  → If these are ~0, experiments are properly paired")

# Agents that diverge: same burn-in state but different experiment state
diverge = micro_b != micro_u
print(f"  Agents that diverge: {np.sum(diverge)} / {N}")
if np.sum(diverge) > 0:
    # Their contribution to the TE
    nonsplurge_diverge = (1-Splurge) * (np.sum(cNrm_u[diverge]) - np.sum(cNrm_b[diverge])) / N
    splurge_diverge = Splurge * (np.sum(TranShk_u[diverge]) - np.sum(TranShk_b[diverge])) / N
    total_diverge = nonsplurge_diverge + splurge_diverge
    print(f"  TE from divergent agents: {total_diverge:.8f}")
    print(f"  TE from non-divergent:    {mc_total_nrm - total_diverge:.8f}")
    print(f"  (should be ~0 if properly paired)")

print("\nDone.")
