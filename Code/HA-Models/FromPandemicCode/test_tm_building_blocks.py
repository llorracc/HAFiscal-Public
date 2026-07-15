"""
Elementary validation of TM experiment building blocks.

These tests use ONLY the base-solved agents (4 Markov states, ~23s solve).
No recession solve needed. Tests that the new experiment functions reproduce
the baseline results when given baseline inputs.

Tests:
  A. build_experiment_period_tm with base args == build_tm_agg_fiscal
  B. propagate with constant base path reproduces ergodic steady state
  C. adapt_initial_distribution shifts mass correctly
  D. compute_period_aggregates_tm matches compute_type_aggregates_tm
"""

import sys
import numpy as np
from copy import deepcopy
from time import time

sys.argv = ['test_tm_building_blocks']

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from HARK.distributions import DiscreteDistribution
from tm_methods import (
    build_tm_agg_fiscal, find_ergodic_distribution, compute_type_aggregates_tm,
    compute_analytical_mean_pLvl, _build_period_tm, _make_newborn_dist,
    _solve_markov_ergodic, build_experiment_period_tm,
    adapt_initial_distribution, compute_period_aggregates_tm,
    propagate_experiment_tm, compute_baseline_tm_data,
)

# ============================================================
# Setup: load params, create ONE agent, base solve
# ============================================================
print("=" * 70, flush=True)
print("Elementary TM building block tests", flush=True)
print("=" * 70, flush=True)

params = return_parameters(Parametrization='Baseline', OutputFor='_Main.py')
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes, Check_changes,
 recession_Check_changes] = params

econ = AggregateDemandEconomy(**init_ADEconomy)

# Create just 3 base types (one per education)
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
    ThisType.IncShkDstn = [[EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
    ThisType.IncShkDstn_base = ThisType.IncShkDstn

# Use 3 types with different betas from each education group
TypeList = []
for e in range(3):
    mid_b = DiscFacCount // 2
    DiscFac = DiscFacDstns[e].atoms[0][mid_b]
    AgentCount = int(np.floor(
        AgentCountTotal * data_EducShares[e] * DiscFacDstns[e].pmv[mid_b]
    ))
    ThisType = deepcopy(BaseTypeList[e])
    ThisType.AgentCount = AgentCount
    ThisType.DiscFac = DiscFac
    ThisType.seed = e
    TypeList.append(ThisType)

econ.agents = TypeList
for agent in TypeList:
    agent.get_economy_data(econ)

print("Solving base model (4 states)...", flush=True)
t0 = time()
econ.solve()
print(f"  Solve: {time()-t0:.1f}s", flush=True)

n_pass = 0
n_fail = 0

def check(name, condition, detail=""):
    global n_pass, n_fail
    status = "PASS" if condition else "FAIL"
    if not condition:
        n_fail += 1
    else:
        n_pass += 1
    print(f"  [{status}] {name}" + (f"  ({detail})" if detail else ""), flush=True)


# ============================================================
# Test A: build_experiment_period_tm reproduces build_tm_agg_fiscal
#         when using base configuration (macro_t=0, macro_next=0)
# ============================================================
print("\n" + "-" * 60, flush=True)
print("Test A: experiment TM builder == baseline TM builder", flush=True)
print("-" * 60, flush=True)

agent = TypeList[1]  # middle education type

# Build baseline TM
tm_base = build_tm_agg_fiscal(agent, mCount=100, Cratio=1.0)
TM_baseline = tm_base['TranMatrix']
dist_mGrid = tm_base['dist_mGrid']

# Build experiment TM with base args: macro_t=0, macro_next=0
# For base config, CondMrkvArrays[0] should be the micro transition matrix
# and IncShkDstn[0][0..3] should be the income shock distributions
TM_exp, cPol_exp = build_experiment_period_tm(
    agent, macro_t=0, macro_next=0, dist_mGrid=dist_mGrid, Cratio=1.0,
)

max_diff = np.max(np.abs(TM_exp - TM_baseline))
check("TM matrices match",
      max_diff < 1e-10,
      f"max|diff|={max_diff:.2e}")

# Check column sums
col_sums_base = TM_baseline.sum(axis=0)
col_sums_exp = TM_exp.sum(axis=0)
check("Baseline TM column sums ~1",
      np.max(np.abs(col_sums_base - 1.0)) < 1e-10,
      f"max deviation from 1: {np.max(np.abs(col_sums_base - 1.0)):.2e}")
check("Experiment TM column sums ~1",
      np.max(np.abs(col_sums_exp - 1.0)) < 1e-10,
      f"max deviation from 1: {np.max(np.abs(col_sums_exp - 1.0)):.2e}")

# Also check that cPol_exp matches baseline cPol
for j in range(agent.num_base_MrkvStates):
    diff_j = np.max(np.abs(np.array(cPol_exp[j]) - np.array(tm_base['cPol'][j])))
    check(f"cPol[{j}] matches",
          diff_j < 1e-10,
          f"max|diff|={diff_j:.2e}")


# ============================================================
# Test B: propagate with constant base path == ergodic steady state
# ============================================================
print("\n" + "-" * 60, flush=True)
print("Test B: propagate with base path reproduces ergodic", flush=True)
print("-" * 60, flush=True)

ergodic = find_ergodic_distribution(TM_baseline)
agg_ergodic = compute_type_aggregates_tm(agent, tm_base, ergodic)
E_pLvl = compute_analytical_mean_pLvl(agent)

# Propagate for 20 periods with EconomyMrkv_init = [0, 0, 0, ...]
base_path = [0] * 20
result_prop = propagate_experiment_tm(
    agent, ergodic, base_path, dist_mGrid,
    E_pLvl, Cratio=1.0, act_T=20,
)

# The aggregates should be constant and match the ergodic values
scale = agent.AgentCount * E_pLvl
ergodic_C = scale * agg_ergodic['C_splurge_nrm']
ergodic_Y = scale * agg_ergodic['Income_nrm']

C_series = result_prop['AggCons']
Y_series = result_prop['AggIncome']

check("AggCons[0] matches ergodic",
      abs(C_series[0] / ergodic_C - 1.0) < 0.001,
      f"ratio={C_series[0]/ergodic_C:.8f}")

check("AggCons is constant across periods",
      np.std(C_series) / np.mean(C_series) < 0.001,
      f"CV={np.std(C_series)/np.mean(C_series)*100:.4f}%")

check("AggIncome[0] matches ergodic",
      abs(Y_series[0] / ergodic_Y - 1.0) < 0.001,
      f"ratio={Y_series[0]/ergodic_Y:.8f}")

for t in [0, 5, 10, 19]:
    ratio = C_series[t] / ergodic_C
    print(f"    t={t:>2}: AggCons={C_series[t]:.4f}  ergodic={ergodic_C:.4f}  ratio={ratio:.8f}", flush=True)


# ============================================================
# Test C: adapt_initial_distribution shifts mass correctly
# ============================================================
print("\n" + "-" * 60, flush=True)
print("Test C: adapt_initial_distribution", flush=True)
print("-" * 60, flush=True)

M = len(dist_mGrid)
J = agent.num_base_MrkvStates

# Check baseline state fractions
fracs_before = np.array([np.sum(ergodic[j*M:(j+1)*M]) for j in range(J)])
print(f"    Baseline state fracs: {fracs_before}", flush=True)
print(f"    Employment rate: {fracs_before[0]:.4f}", flush=True)

# Adapt for no recession (macro_state=0, even = normal)
dist_normal = adapt_initial_distribution(ergodic, agent, 0, dist_mGrid)
fracs_normal = np.array([np.sum(dist_normal[j*M:(j+1)*M]) for j in range(J)])
check("No recession: distribution unchanged",
      np.max(np.abs(dist_normal - ergodic)) < 1e-15,
      f"max|diff|={np.max(np.abs(dist_normal - ergodic)):.2e}")

# Adapt for recession (macro_state=1, odd = recession)
dist_rec = adapt_initial_distribution(ergodic, agent, 1, dist_mGrid)
fracs_rec = np.array([np.sum(dist_rec[j*M:(j+1)*M]) for j in range(J)])
print(f"    Recession state fracs: {fracs_rec}", flush=True)

check("Recession: employed fraction decreases",
      fracs_rec[0] < fracs_before[0],
      f"{fracs_rec[0]:.4f} < {fracs_before[0]:.4f}")

check("Recession: unemployment fraction increases",
      fracs_rec[1] > fracs_before[1],
      f"{fracs_rec[1]:.4f} > {fracs_before[1]:.4f}")

check("Recession: total mass = 1",
      abs(np.sum(dist_rec) - 1.0) < 1e-12,
      f"sum={np.sum(dist_rec):.15f}")

# Check that the unemployment rate matches the target
target_Urate = agent.Urate_recession
actual_unemp = 1.0 - fracs_rec[0]
check("Recession: unemployment matches target",
      abs(actual_unemp - target_Urate) < 0.01,
      f"actual={actual_unemp:.4f} target={target_Urate:.4f}")


# ============================================================
# Test D: compute_period_aggregates_tm matches compute_type_aggregates_tm
# ============================================================
print("\n" + "-" * 60, flush=True)
print("Test D: period aggregates match type aggregates", flush=True)
print("-" * 60, flush=True)

IncShkDstn_base = [agent.IncShkDstn[0][j] for j in range(J)]
period_agg = compute_period_aggregates_tm(
    ergodic, tm_base['cPol'], dist_mGrid, IncShkDstn_base, agent.Splurge,
)

check("C_splurge_nrm matches",
      abs(period_agg['C_splurge_nrm'] / agg_ergodic['C_splurge_nrm'] - 1.0) < 1e-10,
      f"ratio={period_agg['C_splurge_nrm']/agg_ergodic['C_splurge_nrm']:.12f}")

check("Income_nrm matches",
      abs(period_agg['Income_nrm'] / agg_ergodic['Income_nrm'] - 1.0) < 1e-10,
      f"ratio={period_agg['Income_nrm']/agg_ergodic['Income_nrm']:.12f}")


# ============================================================
# Test E: E[pLvl] scaling — analytical vs MC-derived
#   Full 21-type economy with MC burn-in to check scaling
# ============================================================
print("\n" + "-" * 60, flush=True)
print("Test E: E[pLvl] scaling (full economy, MC burn-in)", flush=True)
print("-" * 60, flush=True)

# Build full 21-type economy
econ_full = AggregateDemandEconomy(**init_ADEconomy)
BaseTypeList_full = []
for init_params in [init_dropout, init_highschool, init_college]:
    bt = AggFiscalType(**init_params)
    bt.cycles = 0
    BaseTypeList_full.append(bt)
for bt in BaseTypeList_full:
    bt.get_economy_data(econ_full)

IncShkDstn_unemp_f = DiscreteDistribution(
    np.array([1.0]),
    [np.array([1.0]), np.array([BaseTypeList_full[0].IncUnemp])]
)
IncShkDstn_unemp_nb_f = DiscreteDistribution(
    np.array([1.0]),
    [np.array([1.0]), np.array([BaseTypeList_full[0].IncUnempNoBenefits])]
)
for ThisType in BaseTypeList_full:
    EmployedIncShkDstn = deepcopy(ThisType.IncShkDstn[0])
    ThisType.IncShkDstn = [[EmployedIncShkDstn] + [IncShkDstn_unemp_f] * UBspell_normal + [IncShkDstn_unemp_nb_f]]
    ThisType.IncShkDstn_base = ThisType.IncShkDstn

TypeList_full = []
n = 0
for e in range(3):
    for b in range(DiscFacCount):
        DiscFac_b = DiscFacDstns[e].atoms[0][b]
        AgentCount_b = int(np.floor(
            AgentCountTotal * data_EducShares[e] * DiscFacDstns[e].pmv[b]
        ))
        ThisType = deepcopy(BaseTypeList_full[e])
        ThisType.AgentCount = AgentCount_b
        ThisType.DiscFac = DiscFac_b
        ThisType.seed = n
        TypeList_full.append(ThisType)
        n += 1

econ_full.agents = TypeList_full
for ag in TypeList_full:
    ag.get_economy_data(econ_full)

t0 = time()
econ_full.solve()
print(f"  Full solve: {time()-t0:.1f}s", flush=True)

# MC burn-in
econ_full.reset()
for ag in econ_full.agents:
    ag.initialize_sim()
    ag.AggDemandFac = 1.0
    ag.RfreeNow = 1.0
    ag.CaggNow = 1.0
t0 = time()
econ_full.make_history()
print(f"  MC burn-in: {time()-t0:.1f}s", flush=True)

# Compare analytical vs MC E[pLvl] for each type
print(f"\n  {'Type':>4} {'Edu':>10} {'Beta':>8} {'Analytical':>12} {'MC':>12} {'Ratio':>10}", flush=True)
edu_names = ['Dropout', 'HS', 'College']
mc_E_pLvl_list = []
analytical_E_pLvl_list = []
for i, ag in enumerate(TypeList_full):
    edu = edu_names[i // DiscFacCount]
    E_pLvl_analytical = compute_analytical_mean_pLvl(ag)
    E_pLvl_mc = np.mean(ag.state_now['pLvl'])
    analytical_E_pLvl_list.append(E_pLvl_analytical)
    mc_E_pLvl_list.append(E_pLvl_mc)
    ratio = E_pLvl_analytical / E_pLvl_mc
    if i % 7 in [0, 3, 6]:  # sample
        print(f"  {i:>4} {edu:>10} {ag.DiscFac:>8.4f} "
              f"{E_pLvl_analytical:>12.2f} {E_pLvl_mc:>12.2f} {ratio:>10.4f}", flush=True)

# Run MC base experiment for comparison
econ_full.save_state()
econ_full.switch_to_counterfactual_mode("base")
econ_full.make_idiosyncratic_shock_histories()

from Parameters import return_parameters as rp2
params2 = rp2(Parametrization='Baseline', OutputFor='_Main.py')
base_dict_full = params2[7]
mc_base = econ_full.run_experiment(**base_dict_full, Full_Output=True)
MC_AggCons = np.mean(mc_base['AggCons'])
print(f"  MC base AggCons (mean): {MC_AggCons:.2f}", flush=True)

# Compute TM aggregates with both analytical and MC E[pLvl]
AggCons_analytical = 0.0
AggCons_mc_scaled = 0.0
for i, ag in enumerate(TypeList_full):
    tm_data_i = build_tm_agg_fiscal(ag, mCount=100, Cratio=1.0)
    erg_i = find_ergodic_distribution(tm_data_i['TranMatrix'])
    agg_i = compute_type_aggregates_tm(ag, tm_data_i, erg_i)

    AggCons_analytical += ag.AgentCount * analytical_E_pLvl_list[i] * agg_i['C_splurge_nrm']
    AggCons_mc_scaled += ag.AgentCount * mc_E_pLvl_list[i] * agg_i['C_splurge_nrm']

ratio_analytical = AggCons_analytical / MC_AggCons
ratio_mc_scaled = AggCons_mc_scaled / MC_AggCons
print(f"\n  MC AggCons (direct):                {MC_AggCons:>14.2f}", flush=True)
print(f"  TM AggCons (analytical E[pLvl]):    {AggCons_analytical:>14.2f}  "
      f"ratio={ratio_analytical:.4f}", flush=True)
print(f"  TM AggCons (MC E[pLvl]):            {AggCons_mc_scaled:>14.2f}  "
      f"ratio={ratio_mc_scaled:.4f}", flush=True)

check("TM with MC E[pLvl] matches MC AggCons within 3%",
      abs(ratio_mc_scaled - 1.0) < 0.03,
      f"ratio={ratio_mc_scaled:.6f}, error={abs(ratio_mc_scaled-1.0)*100:.3f}%")

check("Analytical E[pLvl] is systematically higher than MC",
      ratio_analytical > 1.1,
      f"ratio={ratio_analytical:.4f} (known convergence issue)")


# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 70, flush=True)
print(f"RESULTS: {n_pass} passed, {n_fail} failed", flush=True)
if n_fail == 0:
    print("All elementary tests passed — experiment building blocks are correct.", flush=True)
else:
    print("FAILURES DETECTED — fix before proceeding to recession experiments.", flush=True)
print("=" * 70, flush=True)
