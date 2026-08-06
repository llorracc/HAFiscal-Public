"""
Convergence study: verify that analytical E[pLvl] and TM E[cNrm] converge
to MC values as we increase MC agents and TM grid density.

Uses one agent type (HighSchool, middle beta) for speed.
"""

import sys
import numpy as np
from copy import deepcopy
from time import time

sys.argv = ['test_convergence']

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from HARK.distributions import DiscreteDistribution
from tm_methods import (
    compute_analytical_mean_pLvl, build_tm_agg_fiscal,
    find_ergodic_distribution,
)

params = return_parameters(Parametrization='Baseline', OutputFor='_Main.py')
init_hs = params[1]
UBspell_normal = params[10]
DiscFacDstns = params[4]
DiscFacCount = params[5]
base_dict = params[7]

def make_agent(AgentCount, seed=42):
    econ = AggregateDemandEconomy(**params[3])
    bt = AggFiscalType(**init_hs)
    bt.cycles = 0
    bt.get_economy_data(econ)
    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([bt.IncUnemp])])
    IncShkDstn_unemp_nb = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([bt.IncUnempNoBenefits])])
    EmployedIncShkDstn = deepcopy(bt.IncShkDstn[0])
    bt.IncShkDstn = [
        [EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nb]
    ]
    bt.IncShkDstn_base = bt.IncShkDstn
    mid_b = DiscFacCount // 2
    bt.DiscFac = DiscFacDstns[1].atoms[0][mid_b]
    bt.AgentCount = AgentCount
    bt.seed = seed
    econ.agents = [bt]
    bt.get_economy_data(econ)
    return econ, bt

print("=" * 70)
print("CONVERGENCE STUDY: HighSchool, middle beta")
print("=" * 70)

# Analytical E[pLvl] (deterministic, no grid involved)
econ_tmp, bt_tmp = make_agent(100)
econ_tmp.solve()
E_pLvl_analytical = compute_analytical_mean_pLvl(bt_tmp)
print("Analytical E[pLvl] = {:.6f}".format(E_pLvl_analytical))
print("  (deterministic: depends only on LivPrb, PermGroFac, pLogInit*, T_age)")
print()

# ============================================================
# Part 1: MC convergence of E[pLvl]
# ============================================================
print("--- Part 1: MC E[pLvl] convergence (burn-in = T_sim = 400) ---")
print("{:>10s} {:>12s} {:>10s} {:>8s} {:>8s}".format(
    "N_agents", "MC E[pLvl]", "Err%", "SE", "Time"))
print("-" * 55)

for N in [5000, 20000, 100000, 500000]:
    econ, bt = make_agent(N)
    econ.solve()
    econ.reset()
    bt.initialize_sim()
    bt.AggDemandFac = 1.0; bt.RfreeNow = 1.0; bt.CaggNow = 1.0
    t0 = time()
    econ.make_history()
    elapsed = time() - t0

    pLvl_cross = bt.state_now['pLvl']
    mc_mean = np.mean(pLvl_cross)
    mc_se = np.std(pLvl_cross) / np.sqrt(N)
    err = (mc_mean / E_pLvl_analytical - 1.0) * 100

    print("{:>10d} {:>12.4f} {:>10.2f}% {:>8.4f} {:>7.1f}s".format(
        N, mc_mean, err, mc_se, elapsed))

# ============================================================
# Part 2: Burn-in convergence
# ============================================================
print()
print("--- Part 2: Burn-in convergence (N=100000, vary T_sim) ---")
print("{:>8s} {:>12s} {:>10s}".format("T_sim", "MC E[pLvl]", "Err%"))
print("-" * 35)

N_fixed = 100000
for T_sim_override in [100, 200, 400, 800, 1600]:
    econ, bt = make_agent(N_fixed)
    bt.T_sim = T_sim_override
    econ.solve()
    econ.reset()
    bt.initialize_sim()
    bt.AggDemandFac = 1.0; bt.RfreeNow = 1.0; bt.CaggNow = 1.0
    t0 = time()
    econ.make_history()
    elapsed = time() - t0

    mc_mean = np.mean(bt.state_now['pLvl'])
    err = (mc_mean / E_pLvl_analytical - 1.0) * 100
    print("{:>8d} {:>12.4f} {:>10.2f}%  ({:.1f}s)".format(
        T_sim_override, mc_mean, err, elapsed))

# ============================================================
# Part 3: TM grid convergence for E[cNrm]
# ============================================================
print()
print("--- Part 3: TM E[cNrm] grid convergence ---")

# Reference MC E[cNrm] with large sample
econ_ref, bt_ref = make_agent(500000, seed=99)
econ_ref.solve()
econ_ref.reset()
bt_ref.initialize_sim()
bt_ref.AggDemandFac = 1.0; bt_ref.RfreeNow = 1.0; bt_ref.CaggNow = 1.0
econ_ref.make_history()
econ_ref.save_state()
econ_ref.switch_to_counterfactual_mode("base")
econ_ref.make_idiosyncratic_shock_histories()
mc_ref = econ_ref.run_experiment(**base_dict, Full_Output=True)

mc_cNrm_ref = np.mean(bt_ref.history['cNrm'])
mc_pLvl_ref = np.mean(bt_ref.history['pLvl'])
mc_cLvl_ref = np.mean(bt_ref.history['cNrm'] * bt_ref.history['pLvl'])

print("MC reference (N=500k):")
print("  E[cNrm] = {:.8f}".format(mc_cNrm_ref))
print("  E[pLvl] = {:.4f}".format(mc_pLvl_ref))
print("  E[cLvl] = {:.6f}".format(mc_cLvl_ref))
print()

J = bt_ref.MrkvArray[0].shape[0]
print("{:>8s} {:>12s} {:>10s} {:>12s} {:>10s} {:>8s}".format(
    "mCount", "TM E[cNrm]", "cNrm Err%",
    "TM E*[c]*Ep", "cLvl Err%", "nnz"))
print("-" * 70)

for mCount in [50, 100, 200, 400, 800]:
    econ_tm, bt_tm = make_agent(100)
    econ_tm.solve()

    # Actual measure for E[cNrm]
    tm_actual = build_tm_agg_fiscal(bt_tm, mCount=mCount, neutral_measure=False)
    erg_actual = find_ergodic_distribution(tm_actual['TranMatrix'])
    M = len(tm_actual['dist_mGrid'])
    E_cNrm_actual = sum(
        np.dot(tm_actual['cPol'][j], erg_actual[j*M:(j+1)*M])
        for j in range(J)
    )

    # Neutral measure for E[cLvl]
    tm_neutral = build_tm_agg_fiscal(bt_tm, mCount=mCount, neutral_measure=True)
    erg_neutral = find_ergodic_distribution(tm_neutral['TranMatrix'])
    E_star_cNrm = sum(
        np.dot(tm_neutral['cPol'][j], erg_neutral[j*M:(j+1)*M])
        for j in range(J)
    )
    E_cLvl_tm = E_star_cNrm * E_pLvl_analytical

    err_cNrm = (E_cNrm_actual / mc_cNrm_ref - 1.0) * 100
    err_cLvl = (E_cLvl_tm / mc_cLvl_ref - 1.0) * 100

    print("{:>8d} {:>12.8f} {:>10.4f}% {:>12.6f} {:>10.4f}% {:>8d}".format(
        mCount, E_cNrm_actual, err_cNrm, E_cLvl_tm, err_cLvl,
        tm_actual['TranMatrix'].nnz))

print()
print("=" * 70)
print("Done!")
print("=" * 70)
