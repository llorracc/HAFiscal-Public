"""
Targeted test: apply mNrm shifts for income changes to BOTH baseline
and UI micro transitions consistently, then compare treatment effects.

The hypothesis: the consumption gap comes from agents in state 2 who
under normal transitions go to state 3 (TranShk drops 0.7→0.5) but
under UI stay in state 2 (TranShk stays 0.7). This +0.2 mNrm shift
affects ~0.33% of agents but accounts for the entire non-splurge gap.
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
from tm_methods import (
    build_tm_agg_fiscal, find_ergodic_distribution,
    build_experiment_period_tm, compute_analytical_mean_pLvl,
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

tm_data = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
dist_mGrid = tm_data['dist_mGrid']
M = len(dist_mGrid)
ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20

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

print(f"Micro transition matrices:")
print(f"Normal:\n{micro_normal}")
print(f"\nUI:\n{micro_ui_mat}")
print(f"\nE_TranShk per state: {E_TranShk}")


def apply_micro_with_income_shift(dist, micro_trans, M, dist_mGrid, E_TranShk):
    """
    Apply micro transition AND shift mNrm for the income change
    when agents switch states.

    For mass moving from state j to state j':
      new_mNrm = old_mNrm + (E_TranShk[j'] - E_TranShk[j])

    For deterministic-income states (unemployed), this is exact.
    For stochastic-income states (employed, E_TranShk=1.0), this
    is an approximation (shifts by the mean).
    """
    J_loc = micro_trans.shape[0]
    new_dist = np.zeros_like(dist)

    for j_src in range(J_loc):
        src_slice = dist[j_src * M : (j_src + 1) * M]
        if np.sum(src_slice) < 1e-30:
            continue

        for j_dst in range(J_loc):
            prob = micro_trans[j_src, j_dst]
            if prob < 1e-15:
                continue

            contributing_mass = prob * src_slice
            delta = E_TranShk[j_dst] - E_TranShk[j_src]

            if abs(delta) < 1e-12:
                # No shift needed
                new_dist[j_dst * M : (j_dst + 1) * M] += contributing_mass
            else:
                # Shift mNrm by delta via interpolation
                shifted_grid = dist_mGrid + delta
                shifted_mass = np.interp(dist_mGrid, shifted_grid, contributing_mass,
                                          left=0.0, right=0.0)
                # Preserve total mass
                total_orig = np.sum(contributing_mass)
                total_shifted = np.sum(shifted_mass)
                if total_shifted > 1e-30:
                    shifted_mass *= total_orig / total_shifted
                new_dist[j_dst * M : (j_dst + 1) * M] += shifted_mass

    s = np.sum(new_dist)
    if s > 0:
        new_dist /= s
    return new_dist


def decompose(dist, cPol, E_TranShk, Splurge, J, M):
    fracs = np.array([np.sum(dist[j*M:(j+1)*M]) for j in range(J)])
    C_nrm = sum(np.dot(cPol[j], dist[j*M:(j+1)*M]) for j in range(J))
    income = np.dot(fracs, E_TranShk)
    ns = (1 - Splurge) * C_nrm
    sp = Splurge * income
    return ns, sp, ns + sp, fracs


# ============================================================
# Apply all approaches consistently to BOTH baseline and UI
# ============================================================

# 1. No micro transition
ns_b0, sp_b0, t_b0, _ = decompose(ergodic, cPol_base, E_TranShk, Splurge, J, M)
ns_u0, sp_u0, t_u0, _ = decompose(ergodic, cPol_ui, E_TranShk, Splurge, J, M)

# 2. Mixing micro transition (current _apply_micro_transition)
from tm_methods import _apply_micro_transition
dist_b_mix = _apply_micro_transition(ergodic.copy(), micro_normal, M)
dist_u_mix = _apply_micro_transition(ergodic.copy(), micro_ui_mat, M)
ns_b1, sp_b1, t_b1, _ = decompose(dist_b_mix, cPol_base, E_TranShk, Splurge, J, M)
ns_u1, sp_u1, t_u1, _ = decompose(dist_u_mix, cPol_ui, E_TranShk, Splurge, J, M)

# 3. Micro transition WITH income-based mNrm shift (applied to BOTH)
dist_b_shift = apply_micro_with_income_shift(ergodic.copy(), micro_normal, M, dist_mGrid, E_TranShk)
dist_u_shift = apply_micro_with_income_shift(ergodic.copy(), micro_ui_mat, M, dist_mGrid, E_TranShk)
ns_b2, sp_b2, t_b2, fr_b2 = decompose(dist_b_shift, cPol_base, E_TranShk, Splurge, J, M)
ns_u2, sp_u2, t_u2, fr_u2 = decompose(dist_u_shift, cPol_ui, E_TranShk, Splurge, J, M)

# MC reference
from time import time
base_dict_agg = deepcopy(base_dict)
print("\nRunning MC...")
t0 = time()
def run_mc(shock_type, changes, path, seed=42):
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
    if shock_type == 'base':
        return base_r
    eco_x = deepcopy(eco); eco_x.switch_shock_type(shock_type); eco_x.solve()
    d = base_dict_agg.copy(); d.update(changes); d['EconomyMrkv_init'] = path
    return eco_x.run_experiment(**d, Full_Output=True)

mc_b = run_mc('base', {}, [0]*act_T)
mc_u = run_mc('UI', UI_changes, ui_path)
print(f"MC done in {time()-t0:.0f}s")

mc_b_cNrm = mc_b['cNrm_all'][0]; mc_b_TranShk = mc_b['TranShk_all'][0]
mc_u_cNrm = mc_u['cNrm_all'][0]; mc_u_TranShk = mc_u['TranShk_all'][0]
mc_ns_b = (1-Splurge)*np.mean(mc_b_cNrm); mc_sp_b = Splurge*np.mean(mc_b_TranShk)
mc_ns_u = (1-Splurge)*np.mean(mc_u_cNrm); mc_sp_u = Splurge*np.mean(mc_u_TranShk)

# Results
print(f"\n{'='*80}")
print(f"TREATMENT EFFECT DECOMPOSITION (all in normalized per-agent units)")
print(f"{'='*80}")
print(f"\n{'Approach':<25s}  {'TE_nonspl':>12s}  {'TE_spl':>10s}  {'TE_total':>10s}  {'err%':>7s}")
print("-" * 75)

mc_te = (mc_ns_u + mc_sp_u) - (mc_ns_b + mc_sp_b)
for name, ns_b, sp_b, ns_u, sp_u in [
    ("MC", mc_ns_b, mc_sp_b, mc_ns_u, mc_sp_u),
    ("TM no micro", ns_b0, sp_b0, ns_u0, sp_u0),
    ("TM mixing μ", ns_b1, sp_b1, ns_u1, sp_u1),
    ("TM shift μ (BOTH)", ns_b2, sp_b2, ns_u2, sp_u2),
]:
    te_ns = ns_u - ns_b
    te_sp = sp_u - sp_b
    te = te_ns + te_sp
    err = (te - mc_te) / mc_te * 100 if name != "MC" else 0.0
    print(f"{name:<25s}  {te_ns:12.8f}  {te_sp:10.8f}  {te:10.8f}  {err:+6.1f}%")

# Check: per-state mean mNrm for shifted distributions
print(f"\nPer-state mean mNrm after shifted micro transition:")
print(f"  State  ergodic   base_shift  UI_shift")
for j in range(J):
    erg_m = np.dot(dist_mGrid, ergodic[j*M:(j+1)*M]) / max(np.sum(ergodic[j*M:(j+1)*M]), 1e-30)
    bs_m = np.dot(dist_mGrid, dist_b_shift[j*M:(j+1)*M]) / max(np.sum(dist_b_shift[j*M:(j+1)*M]), 1e-30)
    us_m = np.dot(dist_mGrid, dist_u_shift[j*M:(j+1)*M]) / max(np.sum(dist_u_shift[j*M:(j+1)*M]), 1e-30)
    print(f"  [{j}]   {erg_m:8.4f}    {bs_m:8.4f}    {us_m:8.4f}")

print(f"\n  Fracs: base_shift={fr_b2}, UI_shift={fr_u2}")
