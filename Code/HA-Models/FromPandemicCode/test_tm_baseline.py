"""
End-to-end TM vs MC validation for HAFiscal baseline experiment.

Replicates the Simulate.py setup, runs both TM and MC versions of
run_experiment(shock_type="base"), and compares outputs.
"""

import sys
import os
import numpy as np
from copy import deepcopy
from time import time

sys.argv = ['test_tm_baseline']

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from HARK.distributions import DiscreteDistribution
from tm_methods import (
    run_experiment_tm,
    build_tm_agg_fiscal,
    find_ergodic_distribution,
    compute_type_aggregates_tm,
    compute_analytical_mean_pLvl,
)


# ============================================================
# 1. Load parameters
# ============================================================
print("=" * 70)
print("Loading parameters")
print("=" * 70)

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes, Check_changes,
 recession_Check_changes] = return_parameters(
    Parametrization='Baseline', OutputFor='_Main.py'
)

# ============================================================
# 2. Create agent types (replicate Simulate.py lines 88-155)
# ============================================================
print("\n" + "=" * 70)
print("Creating agent types")
print("=" * 70)

num_types = 3
BaseTypeList_init = [init_dropout, init_highschool, init_college]

def make_type_list(base_inits, economy):
    """Create BaseTypeList and TypeList following Simulate.py exactly."""
    BaseTypeList = []
    for init_params in base_inits:
        bt = AggFiscalType(**init_params)
        bt.cycles = 0
        BaseTypeList.append(bt)

    for bt in BaseTypeList:
        bt.get_economy_data(economy)

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

        IncShkDstn_recession = [ThisType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
        ThisType.IncShkDstn_recession = IncShkDstn_recession
        ThisType.IncShkDstn_recessionUI = IncShkDstn_recession

        EmployedIncShkDstn_tax = deepcopy(EmployedIncShkDstn)
        # BUG-023 fix: was `EmployedIncShkDstn_tax.atoms[0][1] = EmployedIncShkDstn_tax.atoms[0][1] * ThisType.TaxCutIncFactor`
        # which mutated one PermShk atom; the intended behavior is to
        # rescale every joint atom's TranShk component (atoms[1]).
        # See BUGS_private/HAFiscal_BUG-023_taxcut_atoms_typo.md.
        EmployedIncShkDstn_tax.atoms = (
            np.asarray(EmployedIncShkDstn_tax.atoms[0], dtype=np.float64),
            np.asarray(EmployedIncShkDstn_tax.atoms[1], dtype=np.float64) * ThisType.TaxCutIncFactor,
        )
        TaxCutStatesIncShkDstn = [EmployedIncShkDstn_tax] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]
        IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
        for idx in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
            IncShkDstn_recessionTaxCut[0][idx] = TaxCutStatesIncShkDstn[np.mod(idx, 4)]
        ThisType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
        ThisType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

    TypeList = []
    n = 0
    for e in range(num_types):
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

    return BaseTypeList, TypeList


# ============================================================
# 3. TM baseline experiment
# ============================================================
print("\n" + "=" * 70)
print("Running TM baseline experiment")
print("=" * 70)

econ_tm = AggregateDemandEconomy(**init_ADEconomy)
_, TypeList_tm = make_type_list(BaseTypeList_init, econ_tm)
econ_tm.agents = TypeList_tm

t0 = time()
tm_results = run_experiment_tm(econ_tm, shock_type="base", dist_aGrid_count=200, verbose=True)
tm_time = time() - t0
print(f"  TM total time: {tm_time:.2f}s")
print(f"  TM AggCons (constant): {tm_results['AggCons'][0]:.4f}")

# Validate E[pLvl] by comparing with analytical formula
print("\n  Analytical E[pLvl] per type:")
edu_names = ['Dropout', 'HighSchool', 'College']
for i, tr in enumerate(tm_results['_type_results']):
    edu = edu_names[i // DiscFacCount]
    agent = TypeList_tm[i]
    print(f"    {i:>2} {edu:>10} beta={agent.DiscFac:.4f} "
          f"N={agent.AgentCount:>5} E[pLvl]={tr['E_pLvl']:>8.2f} "
          f"C_spl_nrm={tr['agg']['C_splurge_nrm']:.6f} "
          f"mMax={tr['tm_data']['mMax']:.0f}")

# ============================================================
# 4. MC baseline experiment (following Simulate.py flow)
# ============================================================
print("\n" + "=" * 70)
print("Running MC baseline experiment")
print("=" * 70)

econ_mc = AggregateDemandEconomy(**init_ADEconomy)
_, TypeList_mc = make_type_list(BaseTypeList_init, econ_mc)
econ_mc.agents = TypeList_mc
for agent in TypeList_mc:
    agent.get_economy_data(econ_mc)

t0 = time()
econ_mc.solve()
print(f"  Economy solve: {time()-t0:.2f}s")

econ_mc.reset()
for agent in econ_mc.agents:
    agent.initialize_sim()
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0

t0_burnin = time()
econ_mc.make_history()
print(f"  Burn-in ({econ_mc.act_T} periods): {time()-t0_burnin:.2f}s")

econ_mc.save_state()
econ_mc.switch_to_counterfactual_mode("base")
econ_mc.make_idiosyncratic_shock_histories()

t0_exp = time()
mc_results = econ_mc.run_experiment(**base_dict, Full_Output=True)
mc_exp_time = time() - t0_exp
mc_total_time = time() - t0
print(f"  Baseline experiment ({econ_mc.act_T} periods): {mc_exp_time:.2f}s")
print(f"  MC total time (solve+burnin+experiment): {mc_total_time:.2f}s")

# ============================================================
# 5. Comparison
# ============================================================
print("\n" + "=" * 70)
print("COMPARISON: TM vs MC")
print("=" * 70)

MC_AggCons = mc_results['AggCons']
MC_AggIncome = mc_results['AggIncome']

mc_mean_C = np.mean(MC_AggCons)
mc_std_C = np.std(MC_AggCons)
mc_mean_Y = np.mean(MC_AggIncome)

# ---- A. Normalized comparison (no pLvl scaling needed) ----
print(f"\n  A. Normalized comparison (E[cNrm] — pure TM vs MC):")
print(f"  {'Type':>4} {'Edu':>10} {'Beta':>8} {'TM C_spl':>12} "
      f"{'MC E[cNrm]':>12} {'Ratio':>10}")
print(f"  {'-'*60}")
for i, (mc_agent, tr) in enumerate(zip(TypeList_mc, tm_results['_type_results'])):
    edu = edu_names[i // DiscFacCount]
    mc_cNrm = np.mean(mc_agent.history['cNrm'])
    ratio = tr['agg']['C_nrm'] / mc_cNrm if mc_cNrm > 0 else float('nan')
    print(f"  {i:>4} {edu:>10} {mc_agent.DiscFac:>8.4f} "
          f"{tr['agg']['C_nrm']:>12.6f} {mc_cNrm:>12.6f} {ratio:>10.6f}")

# ---- B. Level comparison using MC E[pLvl] for scaling ----
print(f"\n  B. Level comparison (TM with MC E[pLvl] scaling):")

TM_AggCons_mc_scaled = 0.0
for i, (mc_agent, tr) in enumerate(zip(TypeList_mc, tm_results['_type_results'])):
    mc_mean_pLvl = np.mean(mc_agent.history['pLvl'])
    TM_AggCons_mc_scaled += tr['agg']['C_splurge_nrm'] * mc_mean_pLvl * mc_agent.AgentCount

TM_AggIncome_mc_scaled = 0.0
for i, (mc_agent, tr) in enumerate(zip(TypeList_mc, tm_results['_type_results'])):
    mc_mean_pLvl = np.mean(mc_agent.history['pLvl'])
    TM_AggIncome_mc_scaled += tr['agg']['Income_nrm'] * mc_mean_pLvl * mc_agent.AgentCount

print(f"\n  {'Metric':<35} {'TM (MC pLvl)':>15} {'MC mean':>15} {'Ratio':>10}")
print(f"  {'-'*75}")
print(f"  {'AggCons':<35} {TM_AggCons_mc_scaled:>15.4f} {mc_mean_C:>15.4f} "
      f"{TM_AggCons_mc_scaled/mc_mean_C:>10.6f}")
print(f"  {'AggIncome':<35} {TM_AggIncome_mc_scaled:>15.4f} {mc_mean_Y:>15.4f} "
      f"{TM_AggIncome_mc_scaled/mc_mean_Y:>10.6f}")
print(f"  MC AggCons std: {mc_std_C:.4f} (CV = {mc_std_C/mc_mean_C*100:.3f}%)")
print(f"  TM-MC error:    {abs(TM_AggCons_mc_scaled/mc_mean_C - 1)*100:.3f}% "
      f"({'within' if abs(TM_AggCons_mc_scaled/mc_mean_C - 1) < mc_std_C/mc_mean_C else 'outside'} "
      f"MC noise)")

# ---- C. Per-type level comparison ----
print(f"\n  C. Per-type level consumption (MC E[pLvl] scaling):")
print(f"  {'Type':>4} {'Edu':>10} {'Beta':>8} {'TM C_lvl':>14} {'MC C_lvl':>14} {'Ratio':>10}")
print(f"  {'-'*64}")
for i, (mc_agent, tr) in enumerate(zip(TypeList_mc, tm_results['_type_results'])):
    edu = edu_names[i // DiscFacCount]
    mc_mean_pLvl = np.mean(mc_agent.history['pLvl'])
    tm_C_lvl = tr['agg']['C_splurge_nrm'] * mc_mean_pLvl * mc_agent.AgentCount
    mc_C_lvl = np.mean(np.sum(mc_agent.history['cLvl_splurge'], axis=1))
    ratio = tm_C_lvl / mc_C_lvl if mc_C_lvl > 0 else float('nan')
    print(f"  {i:>4} {edu:>10} {mc_agent.DiscFac:>8.4f} "
          f"{tm_C_lvl:>14.4f} {mc_C_lvl:>14.4f} {ratio:>10.6f}")

# ---- D. NPV comparison ----
# Construct TM AggCons/AggIncome arrays for NPV
T_exp = econ_mc.act_T
Rfree = TypeList_mc[0].Rfree[0]
TM_AggCons_arr = np.full(T_exp, TM_AggCons_mc_scaled)
TM_AggIncome_arr = np.full(T_exp, TM_AggIncome_mc_scaled)

def calculate_NPV(X, Periods, R):
    NPV = np.zeros(Periods)
    discount = np.array([1.0 / R**t for t in range(Periods)])
    for t in range(Periods):
        NPV[t] = np.sum(X[:t+1] * discount[:t+1])
    return NPV

TM_NPV_AggCons = calculate_NPV(TM_AggCons_arr, T_exp, Rfree)
TM_NPV_AggIncome = calculate_NPV(TM_AggIncome_arr, T_exp, Rfree)

print(f"\n  D. NPV Comparison (period {T_exp}):")
print(f"    NPV_AggCons TM:   {TM_NPV_AggCons[-1]:>15.4f}")
print(f"    NPV_AggCons MC:   {mc_results['NPV_AggCons'][-1]:>15.4f}")
print(f"    Ratio:             {TM_NPV_AggCons[-1]/mc_results['NPV_AggCons'][-1]:>15.6f}")

print(f"\n  Timing:")
print(f"    TM (solve+TM):  {tm_time:>8.2f}s")
print(f"    MC total:        {mc_total_time:>8.2f}s")
print(f"    Speedup:         {mc_total_time/tm_time:>8.1f}x")

print("\n" + "=" * 70)
print("Done!")
print("=" * 70)
