"""
Micro-step validation of TM vs MC, carefully separating pNrm and pLvl.

Each test isolates one potential source of error. Tests run on a single
agent type first, then aggregate, all using the cheap base solve only.

Step 1: Normalized quantities (no pLvl involved)
  1a. TM ergodic state fractions vs MC state fractions
  1b. TM E[cNrm] vs MC E[cNrm]    (pure normalized consumption)
  1c. TM E[TranShk|state] vs MC E[TranShk|state]  (income)

Step 2: pLvl analysis
  2a. MC: is cNrm independent of pLvl? Check E[cNrm*pLvl] vs E[cNrm]*E[pLvl]
  2b. Analytical E[pLvl] vs MC E[pLvl]
  2c. Level consumption: TM E[cNrm]*MC_E[pLvl] vs MC E[cLvl]

Step 3: Splurge-adjusted consumption
  3a. TM C_splurge_nrm vs MC splurge-adjusted normalized consumption

Step 4: Full economy aggregate (21 types)
  4a. Repeat of Step 1b, 2c, 3a summed across all 21 types
"""

import sys
import numpy as np
from copy import deepcopy
from time import time

sys.argv = ['test_tm_microsteps']

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from HARK.distributions import DiscreteDistribution
from tm_methods import (
    build_tm_agg_fiscal, find_ergodic_distribution,
    compute_type_aggregates_tm, compute_analytical_mean_pLvl,
)

# ============================================================
# Setup
# ============================================================
print("=" * 70, flush=True)
print("TM vs MC micro-step validation", flush=True)
print("=" * 70, flush=True)

params = return_parameters(Parametrization='Baseline', OutputFor='_Main.py')
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes, Check_changes,
 recession_Check_changes] = params

n_pass = 0
n_fail = 0
def check(name, condition, detail=""):
    global n_pass, n_fail
    if condition:
        n_pass += 1
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""), flush=True)
    else:
        n_fail += 1
        print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""), flush=True)


def setup_economy_and_types():
    """Create economy with all 21 types, following Simulate.py exactly."""
    econ = AggregateDemandEconomy(**init_ADEconomy)
    BaseTypeList = []
    for init_params in [init_dropout, init_highschool, init_college]:
        bt = AggFiscalType(**init_params)
        bt.cycles = 0
        BaseTypeList.append(bt)

    for bt in BaseTypeList:
        bt.get_economy_data(econ)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseTypeList[0].IncUnemp])]
    )
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseTypeList[0].IncUnempNoBenefits])]
    )

    for ThisType in BaseTypeList:
        EmployedIncShkDstn = deepcopy(ThisType.IncShkDstn[0])
        ThisType.IncShkDstn = [
            [EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal
            + [IncShkDstn_unemp_nobenefits]
        ]
        ThisType.IncShkDstn_base = ThisType.IncShkDstn

    TypeList = []
    n = 0
    for e in range(3):
        for b in range(DiscFacCount):
            DiscFac = DiscFacDstns[e].atoms[0][b]
            AgentCount = int(np.floor(
                AgentCountTotal * data_EducShares[e] * DiscFacDstns[e].pmv[b]
            ))
            ThisType = deepcopy(BaseTypeList[e])
            ThisType.AgentCount = AgentCount
            ThisType.DiscFac = DiscFac
            ThisType.seed = n
            TypeList.append(ThisType)
            n += 1

    econ.agents = TypeList
    for agent in TypeList:
        agent.get_economy_data(econ)
    return econ, TypeList


econ, TypeList = setup_economy_and_types()

print("Solving (base, 4 states)...", flush=True)
t0 = time()
econ.solve()
print(f"  Solve: {time()-t0:.1f}s", flush=True)

# MC burn-in
econ.reset()
for agent in econ.agents:
    agent.initialize_sim()
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0

t0 = time()
econ.make_history()
print(f"  Burn-in: {time()-t0:.1f}s", flush=True)

# Run MC base experiment to get tracked histories
econ.save_state()
econ.switch_to_counterfactual_mode("base")
econ.make_idiosyncratic_shock_histories()
mc_results = econ.run_experiment(**base_dict, Full_Output=True)
print(f"  MC base experiment done", flush=True)

# ============================================================
# Step 1: Single type, normalized quantities only
# ============================================================
# Pick the middle-beta dropout (type 3) as our test type
test_idx = 3
agent = TypeList[test_idx]
edu_names = ['Dropout'] * 7 + ['HS'] * 7 + ['College'] * 7
print(f"\n{'='*70}", flush=True)
print(f"Step 1: Single type ({edu_names[test_idx]}, beta={agent.DiscFac:.4f}, "
      f"N={agent.AgentCount})", flush=True)
print(f"{'='*70}", flush=True)

# Build TM for this single type
tm_data = build_tm_agg_fiscal(agent, mCount=200, Cratio=1.0)
ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
dist_mGrid = tm_data['dist_mGrid']
M = len(dist_mGrid)
J = agent.num_base_MrkvStates

# --- 1a: State fractions ---
print(f"\n  --- 1a: Markov state fractions ---", flush=True)

# TM state fractions from ergodic
tm_fracs = np.array([np.sum(ergodic[j*M:(j+1)*M]) for j in range(J)])

# MC state fractions from experiment history
mc_mrkv = agent.shock_history['Mrkv']  # shape (T, N)
mc_fracs = np.zeros(J)
for j in range(J):
    mc_fracs[j] = np.mean(mc_mrkv == j)

state_labels = ['Emp', f'Unemp(1)', f'Unemp(2-{UBspell_normal})', 'Unemp(exhaust)']
print(f"  {'State':<20} {'TM':>10} {'MC':>10} {'Ratio':>10}", flush=True)
for j in range(J):
    label = state_labels[j] if j < len(state_labels) else f'State {j}'
    ratio = tm_fracs[j] / mc_fracs[j] if mc_fracs[j] > 0 else float('nan')
    print(f"  {label:<20} {tm_fracs[j]:>10.6f} {mc_fracs[j]:>10.6f} {ratio:>10.4f}", flush=True)

check("State fractions: employed within 2%",
      abs(tm_fracs[0] / mc_fracs[0] - 1.0) < 0.02,
      f"TM={tm_fracs[0]:.6f} MC={mc_fracs[0]:.6f}")

# --- 1b: E[cNrm] ---
print(f"\n  --- 1b: E[cNrm] (normalized consumption) ---", flush=True)

# TM: E[cNrm] from ergodic distribution
tm_cNrm = 0.0
for j in range(J):
    dstn_j = ergodic[j*M:(j+1)*M]
    tm_cNrm += np.dot(tm_data['cPol'][j], dstn_j)

# MC: E[cNrm] from experiment history
mc_cNrm_history = agent.history['cNrm']  # shape (T, N)
mc_cNrm = np.mean(mc_cNrm_history)

ratio_cNrm = tm_cNrm / mc_cNrm
print(f"  TM E[cNrm] = {tm_cNrm:.8f}", flush=True)
print(f"  MC E[cNrm] = {mc_cNrm:.8f}", flush=True)
print(f"  Ratio = {ratio_cNrm:.8f}  (error = {abs(ratio_cNrm-1)*100:.4f}%)", flush=True)

check("E[cNrm] within 2%",
      abs(ratio_cNrm - 1.0) < 0.02,
      f"error={abs(ratio_cNrm-1)*100:.4f}%")

# --- 1c: E[TranShk | state] ---
print(f"\n  --- 1c: Income (E[TranShk * AggDemandFac] by state) ---", flush=True)

# TM: theoretical E[TranShk] per state
tm_E_TranShk = np.zeros(J)
for j in range(J):
    d = agent.IncShkDstn[0][j]
    tm_E_TranShk[j] = np.dot(d.pmv, d.atoms[1])

# MC: empirical E[TranShk | state]
mc_transhk = agent.shock_history['TranShk']
mc_E_TranShk = np.zeros(J)
for j in range(J):
    mask = (mc_mrkv == j)
    if np.sum(mask) > 0:
        mc_E_TranShk[j] = np.mean(mc_transhk[mask])

for j in range(J):
    label = state_labels[j] if j < len(state_labels) else f'State {j}'
    ratio = tm_E_TranShk[j] / mc_E_TranShk[j] if mc_E_TranShk[j] > 0 else float('nan')
    print(f"  {label:<20} TM={tm_E_TranShk[j]:>10.6f}  MC={mc_E_TranShk[j]:>10.6f}  "
          f"ratio={ratio:.6f}", flush=True)

# Weighted income_nrm
tm_income_nrm = np.dot(tm_fracs, tm_E_TranShk)
mc_income_nrm = np.mean(mc_transhk)  # since AggDemandFac=1 in base
ratio_income = tm_income_nrm / mc_income_nrm
print(f"  Weighted income_nrm: TM={tm_income_nrm:.8f} MC={mc_income_nrm:.8f} "
      f"ratio={ratio_income:.8f}", flush=True)

check("Income_nrm within 2%",
      abs(ratio_income - 1.0) < 0.02,
      f"error={abs(ratio_income-1)*100:.4f}%")


# ============================================================
# Step 2: pLvl analysis (single type)
# ============================================================
print(f"\n{'='*70}", flush=True)
print(f"Step 2: pLvl analysis (single type)", flush=True)
print(f"{'='*70}", flush=True)

# --- 2a: Independence of cNrm and pLvl ---
print(f"\n  --- 2a: Is cNrm independent of pLvl? ---", flush=True)

mc_pLvl_history = agent.history['pLvl']  # shape (T, N)
mc_cLvl_history = agent.history['cLvl']  # cLvl = cNrm * pLvl

mc_E_cLvl = np.mean(mc_cLvl_history)
mc_E_cNrm_times_E_pLvl = np.mean(mc_cNrm_history) * np.mean(mc_pLvl_history)
independence_ratio = mc_E_cLvl / mc_E_cNrm_times_E_pLvl

print(f"  MC E[cNrm * pLvl] = E[cLvl] = {mc_E_cLvl:.6f}", flush=True)
print(f"  MC E[cNrm] * E[pLvl]         = {mc_E_cNrm_times_E_pLvl:.6f}", flush=True)
print(f"  Ratio (=1 if independent)     = {independence_ratio:.8f}", flush=True)
print(f"  Deviation from independence   = {abs(independence_ratio-1)*100:.4f}%", flush=True)

check("cNrm and pLvl approximately independent (within 5%)",
      abs(independence_ratio - 1.0) < 0.05,
      f"deviation={abs(independence_ratio-1)*100:.4f}%")

# --- 2b: Analytical vs MC E[pLvl] ---
print(f"\n  --- 2b: E[pLvl] comparison ---", flush=True)

E_pLvl_analytical = compute_analytical_mean_pLvl(agent)
E_pLvl_mc = np.mean(mc_pLvl_history)
E_pLvl_state_now = np.mean(agent.state_now['pLvl']) if agent.state_now.get('pLvl') is not None else float('nan')

print(f"  Analytical E[pLvl]    = {E_pLvl_analytical:.4f}", flush=True)
print(f"  MC E[pLvl] (history)  = {E_pLvl_mc:.4f}", flush=True)
print(f"  MC E[pLvl] (state_now)= {E_pLvl_state_now:.4f}", flush=True)
print(f"  Analytical/MC ratio   = {E_pLvl_analytical/E_pLvl_mc:.4f}", flush=True)
print(f"  (This ratio > 1 is the known burn-in convergence issue)", flush=True)

check("Analytical E[pLvl] > MC E[pLvl] (known issue)",
      E_pLvl_analytical > E_pLvl_mc,
      f"analytical={E_pLvl_analytical:.4f} MC={E_pLvl_mc:.4f}")

# --- 2c: Level consumption ---
print(f"\n  --- 2c: Level consumption comparison ---", flush=True)

# TM level consumption using MC E[pLvl]
tm_cLvl_mc_scaled = tm_cNrm * E_pLvl_mc
# MC level consumption
mc_mean_cLvl = mc_E_cLvl

ratio_cLvl = tm_cLvl_mc_scaled / mc_mean_cLvl
print(f"  TM E[cNrm] * MC_E[pLvl] = {tm_cLvl_mc_scaled:.6f}", flush=True)
print(f"  MC E[cLvl]               = {mc_mean_cLvl:.6f}", flush=True)
print(f"  Ratio                    = {ratio_cLvl:.8f}  "
      f"(error = {abs(ratio_cLvl-1)*100:.4f}%)", flush=True)

check("Level consumption (TM with MC pLvl) within 3%",
      abs(ratio_cLvl - 1.0) < 0.03,
      f"error={abs(ratio_cLvl-1)*100:.4f}%")


# ============================================================
# Step 3: Splurge-adjusted consumption (single type)
# ============================================================
print(f"\n{'='*70}", flush=True)
print(f"Step 3: Splurge-adjusted consumption", flush=True)
print(f"{'='*70}", flush=True)

Splurge = agent.Splurge

# TM splurge-adjusted normalized consumption
tm_C_splurge_nrm = (1.0 - Splurge) * tm_cNrm + Splurge * tm_income_nrm

# MC splurge-adjusted: cLvl_splurge = (1-Splurge)*cNrm*pLvl + Splurge*pLvl*TranShk
# Normalized: cNrm_splurge = (1-Splurge)*cNrm + Splurge*TranShk
mc_cNrm_splurge = np.mean(
    (1.0 - Splurge) * mc_cNrm_history + Splurge * mc_transhk
)

ratio_splurge = tm_C_splurge_nrm / mc_cNrm_splurge
print(f"  TM C_splurge_nrm = {tm_C_splurge_nrm:.8f}", flush=True)
print(f"  MC C_splurge_nrm = {mc_cNrm_splurge:.8f}", flush=True)
print(f"  Ratio            = {ratio_splurge:.8f}  "
      f"(error = {abs(ratio_splurge-1)*100:.4f}%)", flush=True)

check("Splurge-adjusted nrm consumption within 2%",
      abs(ratio_splurge - 1.0) < 0.02,
      f"error={abs(ratio_splurge-1)*100:.4f}%")


# ============================================================
# Step 4: Full economy aggregates (21 types)
# ============================================================
print(f"\n{'='*70}", flush=True)
print(f"Step 4: Full economy (21 types) aggregate comparison", flush=True)
print(f"{'='*70}", flush=True)

# MC aggregates from run_experiment
MC_AggCons = np.mean(mc_results['AggCons'])
MC_AggIncome = np.mean(mc_results['AggIncome'])

# Compute TM aggregates using both analytical and MC E[pLvl]
TM_AggCons_analytical = 0.0
TM_AggCons_mc_pLvl = 0.0
TM_AggIncome_mc_pLvl = 0.0
TM_AggCons_nrm_total = 0.0  # unnormalized but unscaled (for checking)

print(f"\n  Per-type breakdown (TM nrm vs MC nrm):", flush=True)
print(f"  {'Type':>4} {'Edu':>8} {'Beta':>8} {'TM_cNrm':>10} {'MC_cNrm':>10} "
      f"{'Ratio':>8} {'MC_pLvl':>10} {'Anl_pLvl':>10}", flush=True)

for i, ag in enumerate(TypeList):
    edu = edu_names[i]
    tm_i = build_tm_agg_fiscal(ag, mCount=200, Cratio=1.0)
    erg_i = find_ergodic_distribution(tm_i['TranMatrix'])
    agg_i = compute_type_aggregates_tm(ag, tm_i, erg_i)

    mc_cNrm_i = np.mean(ag.history['cNrm'])
    mc_pLvl_i = np.mean(ag.history['pLvl'])
    anl_pLvl_i = compute_analytical_mean_pLvl(ag)

    ratio_i = agg_i['C_nrm'] / mc_cNrm_i if mc_cNrm_i > 0 else float('nan')
    print(f"  {i:>4} {edu:>8} {ag.DiscFac:>8.4f} {agg_i['C_nrm']:>10.6f} "
          f"{mc_cNrm_i:>10.6f} {ratio_i:>8.4f} {mc_pLvl_i:>10.2f} "
          f"{anl_pLvl_i:>10.2f}", flush=True)

    TM_AggCons_analytical += ag.AgentCount * anl_pLvl_i * agg_i['C_splurge_nrm']
    TM_AggCons_mc_pLvl += ag.AgentCount * mc_pLvl_i * agg_i['C_splurge_nrm']
    TM_AggIncome_mc_pLvl += ag.AgentCount * mc_pLvl_i * agg_i['Income_nrm']

print(f"\n  Economy-wide aggregates:", flush=True)
print(f"  {'Metric':<35} {'Value':>15} {'MC ref':>15} {'Ratio':>10}", flush=True)
print(f"  {'-'*75}", flush=True)

r_anl = TM_AggCons_analytical / MC_AggCons
r_mc = TM_AggCons_mc_pLvl / MC_AggCons
r_inc = TM_AggIncome_mc_pLvl / MC_AggIncome

print(f"  {'TM AggCons (analytical pLvl)':<35} {TM_AggCons_analytical:>15.2f} "
      f"{MC_AggCons:>15.2f} {r_anl:>10.4f}", flush=True)
print(f"  {'TM AggCons (MC pLvl)':<35} {TM_AggCons_mc_pLvl:>15.2f} "
      f"{MC_AggCons:>15.2f} {r_mc:>10.4f}", flush=True)
print(f"  {'TM AggIncome (MC pLvl)':<35} {TM_AggIncome_mc_pLvl:>15.2f} "
      f"{MC_AggIncome:>15.2f} {r_inc:>10.4f}", flush=True)

print(f"\n  Key result:", flush=True)
print(f"    Analytical pLvl scaling error: {abs(r_anl-1)*100:.2f}%", flush=True)
print(f"    MC pLvl scaling error:         {abs(r_mc-1)*100:.2f}%", flush=True)

check("TM AggCons (MC pLvl) within 3% of MC",
      abs(r_mc - 1.0) < 0.03,
      f"error={abs(r_mc-1)*100:.3f}%")

check("TM AggIncome (MC pLvl) within 3% of MC",
      abs(r_inc - 1.0) < 0.03,
      f"error={abs(r_inc-1)*100:.3f}%")


# ============================================================
# Summary
# ============================================================
print(f"\n{'='*70}", flush=True)
print(f"RESULTS: {n_pass} passed, {n_fail} failed", flush=True)
if n_fail == 0:
    print("All micro-step tests passed.", flush=True)
else:
    print("FAILURES — investigate before proceeding.", flush=True)
print(f"{'='*70}", flush=True)
