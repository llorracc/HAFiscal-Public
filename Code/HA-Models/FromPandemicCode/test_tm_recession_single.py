"""
Step 1 validation: TM vs MC for a single-length recession experiment.

Tests time-varying TM propagation and initial unemployment shock adaptation.
Runs both TM and MC versions of a 1-quarter recession and compares
per-period AggCons and AggIncome.
"""

import sys
import os
import numpy as np
from copy import deepcopy
from time import time

sys.argv = ['test_tm_recession_single']

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from HARK.distributions import DiscreteDistribution
from tm_methods import (
    run_experiment_tm_nonbase, compute_baseline_tm_data, calculate_NPV,
    build_tm_agg_fiscal, find_ergodic_distribution, compute_analytical_mean_pLvl,
)

# ============================================================
# 1. Load parameters
# ============================================================
print("=" * 70, flush=True)
print("Step 1: Single-recession TM vs MC validation", flush=True)
print("=" * 70, flush=True)

params = return_parameters(Parametrization='Baseline', OutputFor='_Main.py')
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes, Check_changes,
 recession_Check_changes] = params

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
        EmployedIncShkDstn_tax.atoms[0][1] = EmployedIncShkDstn_tax.atoms[0][1] * ThisType.TaxCutIncFactor
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


# Build EconomyMrkv_init for a 1-quarter recession
EconomyMrkv_init_1q = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * 20
EconomyMrkv_init_1q[0] += 1  # first period is recession (odd)
act_T = len(EconomyMrkv_init_1q)

print(f"\nEconomyMrkv_init (1q recession, first 10): {EconomyMrkv_init_1q[:10]}...", flush=True)
print(f"act_T = {act_T}", flush=True)

# ============================================================
# 2. Shared setup: create economy, base solve, burn-in
# ============================================================
print("\n" + "=" * 70, flush=True)
print("Setting up economy (base solve + burn-in)", flush=True)
print("=" * 70, flush=True)

econ = AggregateDemandEconomy(**init_ADEconomy)
econ.act_T = act_T
_, TypeList = make_type_list(BaseTypeList_init, econ)
econ.agents = TypeList
for agent in TypeList:
    agent.get_economy_data(econ)

t0 = time()
econ.solve()
print(f"  Base solve: {time()-t0:.1f}s", flush=True)

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

# Extract MC-derived E[pLvl] from burn-in for apples-to-apples comparison
mc_E_pLvl = [np.mean(agent.state_now['pLvl']) for agent in econ.agents]
print(f"  MC E[pLvl] (sample): dropout={mc_E_pLvl[0]:.2f}, "
      f"HS={mc_E_pLvl[7]:.2f}, college={mc_E_pLvl[14]:.2f}", flush=True)

# Compute baseline TM data WHILE agents are in base config, using MC E[pLvl]
print("  Computing baseline TM ergodic distributions...", flush=True)
t0 = time()
baseline_tm_data = compute_baseline_tm_data(econ, mCount=200,
                                             mc_E_pLvl=mc_E_pLvl, verbose=True)
print(f"  Baseline TM data: {time()-t0:.1f}s", flush=True)

econ.save_state()
econ.switch_to_counterfactual_mode("base")
econ.make_idiosyncratic_shock_histories()

# ============================================================
# 3. Switch to recession and solve (shared cost)
# ============================================================
print("\n" + "=" * 70, flush=True)
print("Switching to recession and solving", flush=True)
print("=" * 70, flush=True)

econ.switch_shock_type("recession")
t0 = time()
econ.solve()
recession_solve_time = time() - t0
print(f"  Recession solve (168 states): {recession_solve_time:.1f}s", flush=True)

# ============================================================
# 4. MC experiment
# ============================================================
print("\n" + "=" * 70, flush=True)
print("Running MC recession experiment", flush=True)
print("=" * 70, flush=True)

recession_dict = deepcopy(base_dict)
recession_dict.update(recession_changes)
recession_dict['EconomyMrkv_init'] = EconomyMrkv_init_1q

t0 = time()
mc_results = econ.run_experiment(**recession_dict, Full_Output=True)
mc_time = time() - t0
print(f"  MC experiment: {mc_time:.1f}s", flush=True)

# ============================================================
# 5. TM experiment
# ============================================================
print("\n" + "=" * 70, flush=True)
print("Running TM recession experiment", flush=True)
print("=" * 70, flush=True)

t0 = time()
tm_results = run_experiment_tm_nonbase(
    econ, shock_type="recession",
    EconomyMrkv_init=EconomyMrkv_init_1q,
    baseline_tm_data=baseline_tm_data,
    mCount=200, Cratio=1.0, verbose=True,
)
tm_time = time() - t0
print(f"  TM propagation: {tm_time:.1f}s", flush=True)

# ============================================================
# 6. Comparison
# ============================================================
print("\n" + "=" * 70, flush=True)
print("COMPARISON: TM vs MC (1-quarter recession)", flush=True)
print("=" * 70, flush=True)

MC_C = mc_results['AggCons'][:act_T]
MC_Y = mc_results['AggIncome'][:act_T]
TM_C = tm_results['AggCons']
TM_Y = tm_results['AggIncome']

print(f"\n  Per-period AggCons comparison:", flush=True)
print(f"  {'Period':>6} {'MC':>14} {'TM':>14} {'TM/MC':>10} {'%diff':>8}", flush=True)
print(f"  {'-'*56}", flush=True)
for t in range(min(act_T, 30)):
    ratio = TM_C[t] / MC_C[t] if MC_C[t] != 0 else float('nan')
    pct = (ratio - 1.0) * 100
    marker = " <--" if abs(pct) > 5.0 else ""
    print(f"  {t:>6} {MC_C[t]:>14.2f} {TM_C[t]:>14.2f} {ratio:>10.6f} {pct:>7.2f}%{marker}", flush=True)

print(f"\n  Summary statistics:", flush=True)
ratios_C = TM_C / np.where(MC_C != 0, MC_C, 1.0)
ratios_Y = TM_Y / np.where(MC_Y != 0, MC_Y, 1.0)
print(f"    AggCons  TM/MC: mean={np.mean(ratios_C):.6f} "
      f"min={np.min(ratios_C):.6f} max={np.max(ratios_C):.6f}", flush=True)
print(f"    AggIncome TM/MC: mean={np.mean(ratios_Y):.6f} "
      f"min={np.min(ratios_Y):.6f} max={np.max(ratios_Y):.6f}", flush=True)

max_dev = np.max(np.abs(ratios_C - 1.0)) * 100
mean_dev = np.mean(np.abs(ratios_C - 1.0)) * 100
print(f"    Max |TM/MC - 1|: {max_dev:.2f}%", flush=True)
print(f"    Mean |TM/MC - 1|: {mean_dev:.2f}%", flush=True)

npv_ratio = tm_results['NPV_AggCons'][-1] / mc_results['NPV_AggCons'][act_T - 1]
print(f"\n  NPV AggCons ratio: {npv_ratio:.6f}", flush=True)

gate_pass = max_dev < 5.0
print(f"\n  GATE (max deviation < 5%): {'PASS' if gate_pass else 'FAIL'} ({max_dev:.2f}%)", flush=True)

print(f"\n  Timing:", flush=True)
print(f"    Recession solve: {recession_solve_time:.1f}s (shared)", flush=True)
print(f"    TM propagation: {tm_time:.1f}s", flush=True)
print(f"    MC experiment:  {mc_time:.1f}s", flush=True)

print("\n" + "=" * 70, flush=True)
print("Done!", flush=True)
print("=" * 70, flush=True)
