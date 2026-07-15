"""
GLP-1 convergence sweep: how many MC agents (N) and TM grid points (mCount)
are needed for <1% treatment effect error?

Single college type, point discount factor, fixed 3-quarter recession,
no AD.  Uses a high-resolution TM (mCount=400) as the reference.

Reports max relative error across UI, TaxCut, Check treatment effects
(both AggCons and AggIncome) for each (N, mCount) pair.
"""

import os, sys, numpy as np
from time import time
from copy import deepcopy

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())

os.environ['MPLBACKEND'] = 'Agg'
import matplotlib; matplotlib.use('Agg')

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import (
    compute_baseline_tm_data, propagate_experiment_tm,
    run_experiment_tm_nonbase, calculate_NPV,
)

# ============================================================
# Setup (same as GLP-1: single college type, point beta)
# ============================================================
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

J = num_base_MrkvStates

# Single college type
BaseType = AggFiscalType(**init_college)
BaseType.cycles = 0
BaseType.DiscFac = DiscFacDstns[2].atoms[0][0]  # point estimate

AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

# Set up IncShkDstn (same as Simulate.py)
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
BaseType.AgentCount = 1  # placeholder for solve

t0_total = time()
print("Solving...", flush=True)
AggEco.solve()
t_solve = time() - t0_total
print(f"Solve: {t_solve:.1f}s")

act_T = AggEco.act_T
base_dict_agg = deepcopy(base_dict)
Rfree = BaseType.Rfree[0]

# Experiment paths
ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20
# Fixed 3-quarter recession path
rec_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20
for t in range(3):
    rec_path[t] = rec_path[t] + 1

SHOCKS_NO_REC = ['UI', 'TaxCut', 'Check']
SHOCKS_REC = ['recessionUI', 'recessionTaxCut', 'recessionCheck']
SHOCK_CHANGES = {
    'UI': UI_changes, 'TaxCut': TaxCut_changes, 'Check': Check_changes,
    'recessionUI': recession_UI_changes,
    'recessionTaxCut': recession_TaxCut_changes,
    'recessionCheck': recession_Check_changes,
}

def get_path(shock):
    if shock.startswith('recession'):
        return rec_path
    return ui_path

# ============================================================
# TM reference (mCount=400)
# ============================================================
print("\n--- TM reference (mCount=400) ---", flush=True)
t0 = time()
bl_ref = compute_baseline_tm_data(AggEco, mCount=400, verbose=False)
bd_ref = bl_ref[0]

# Base propagation
base_a = deepcopy(BaseType)
base_a.update_mrkv_array("base")
base_a.solve()
tm_base_ref = propagate_experiment_tm(
    base_a, bd_ref['ergodic'], [0]*act_T, bd_ref['dist_mGrid'],
    bd_ref['E_pLvl'], act_T=act_T, base_aPol=bd_ref['base_aPol'])

# Each experiment
tm_ref = {}
for shock in SHOCKS_NO_REC + SHOCKS_REC:
    eco_s = deepcopy(AggEco)
    eco_s.switch_shock_type(shock)
    eco_s.solve()
    path = get_path(shock)
    res = run_experiment_tm_nonbase(eco_s, shock, path, bl_ref, mCount=400, verbose=False)
    # Treatment effect: NPV(experiment - base)
    npv_c = calculate_NPV(np.array(res['AggCons']) - np.array(tm_base_ref['AggCons']), act_T, Rfree)[-1]
    npv_y = calculate_NPV(np.array(res['AggIncome']) - np.array(tm_base_ref['AggIncome']), act_T, Rfree)[-1]
    tm_ref[shock] = {'npv_c': npv_c, 'npv_y': npv_y}
    print(f"  {shock:20s} NPV_C_TE={npv_c:.4f}, NPV_Y_TE={npv_y:.4f}")
print(f"  Reference computed in {time()-t0:.1f}s")

# ============================================================
# TM grid sweep
# ============================================================
print("\n--- TM grid convergence ---")
print(f"  {'mCount':>8s}  {'max_rel_err_C':>14s}  {'max_rel_err_Y':>14s}  {'time':>6s}")
print("  " + "-" * 50)

for mcount in [100, 50, 25]:
    t0 = time()
    bl = compute_baseline_tm_data(AggEco, mCount=mcount, verbose=False)
    bd = bl[0]
    base_a2 = deepcopy(BaseType)
    base_a2.update_mrkv_array("base")
    base_a2.solve()
    tm_base = propagate_experiment_tm(
        base_a2, bd['ergodic'], [0]*act_T, bd['dist_mGrid'],
        bd['E_pLvl'], act_T=act_T, base_aPol=bd['base_aPol'])

    max_err_c, max_err_y = 0, 0
    for shock in SHOCKS_NO_REC + SHOCKS_REC:
        eco_s = deepcopy(AggEco)
        eco_s.switch_shock_type(shock)
        eco_s.solve()
        path = get_path(shock)
        res = run_experiment_tm_nonbase(eco_s, shock, path, bl, mCount=mcount, verbose=False)
        npv_c = calculate_NPV(np.array(res['AggCons']) - np.array(tm_base['AggCons']), act_T, Rfree)[-1]
        npv_y = calculate_NPV(np.array(res['AggIncome']) - np.array(tm_base['AggIncome']), act_T, Rfree)[-1]
        ref = tm_ref[shock]
        if abs(ref['npv_c']) > 1e-10:
            err_c = abs(npv_c - ref['npv_c']) / abs(ref['npv_c'])
            max_err_c = max(max_err_c, err_c)
        if abs(ref['npv_y']) > 1e-10:
            err_y = abs(npv_y - ref['npv_y']) / abs(ref['npv_y'])
            max_err_y = max(max_err_y, err_y)
    elapsed = time() - t0
    print(f"  {mcount:8d}  {max_err_c*100:13.2f}%  {max_err_y*100:13.2f}%  {elapsed:5.1f}s")

# ============================================================
# MC sweep
# ============================================================
NUM_SEEDS = 3

def run_mc_all_experiments(N_agents, seed):
    """Run all experiments for one MC seed, return NPV treatment effects."""
    eco = deepcopy(AggEco)
    for a in eco.agents:
        a.AgentCount = N_agents
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

    # Baseline
    base_r = eco.run_experiment(**base_dict_agg, Full_Output=True)
    eco.store_baseline(base_r['AggCons'])

    results = {}
    for shock in SHOCKS_NO_REC + SHOCKS_REC:
        eco_x = deepcopy(eco)
        eco_x.switch_shock_type(shock)
        eco_x.solve()
        d = base_dict_agg.copy()
        d.update(SHOCK_CHANGES[shock])
        d['EconomyMrkv_init'] = get_path(shock)
        shock_r = eco_x.run_experiment(**d, Full_Output=True)
        N_act = sum(a.AgentCount for a in eco.agents)
        npv_c = calculate_NPV(np.array(shock_r['AggCons']) - np.array(base_r['AggCons']), act_T, Rfree)[-1] / N_act
        npv_y = calculate_NPV(np.array(shock_r['AggIncome']) - np.array(base_r['AggIncome']), act_T, Rfree)[-1] / N_act
        results[shock] = {'npv_c': npv_c, 'npv_y': npv_y}
    return results

# Normalize TM reference to per-capita
N_ref = BaseType.AgentCount  # =1 for GLP-1
tm_ref_pc = {s: {'npv_c': tm_ref[s]['npv_c']/N_ref, 'npv_y': tm_ref[s]['npv_y']/N_ref} for s in tm_ref}

print(f"\n--- MC convergence (vs TM mCount=400 reference) ---")
print(f"  {'N':>10s}  {'seeds':>5s}  {'max_rel_err_C':>14s}  {'max_rel_err_Y':>14s}  {'time':>7s}")
print("  " + "-" * 55)

mc_results_by_N = {}
for N_agents in [80000, 20000]:
    t0 = time()
    all_seed_results = []
    for s in range(NUM_SEEDS):
        all_seed_results.append(run_mc_all_experiments(N_agents, seed=s))

    # Average across seeds
    max_err_c, max_err_y = 0, 0
    per_shock = {}
    for shock in SHOCKS_NO_REC + SHOCKS_REC:
        mean_c = np.mean([r[shock]['npv_c'] for r in all_seed_results])
        mean_y = np.mean([r[shock]['npv_y'] for r in all_seed_results])
        std_c = np.std([r[shock]['npv_c'] for r in all_seed_results], ddof=1)
        ref = tm_ref_pc[shock]
        if abs(ref['npv_c']) > 1e-10:
            err_c = abs(mean_c - ref['npv_c']) / abs(ref['npv_c'])
            max_err_c = max(max_err_c, err_c)
        if abs(ref['npv_y']) > 1e-10:
            err_y = abs(mean_y - ref['npv_y']) / abs(ref['npv_y'])
            max_err_y = max(max_err_y, err_y)
        per_shock[shock] = {'mean_c': mean_c, 'std_c': std_c, 'mean_y': mean_y,
                            'err_c': err_c if abs(ref['npv_c']) > 1e-10 else 0}

    elapsed = time() - t0
    print(f"  {N_agents:10d}  {NUM_SEEDS:5d}  {max_err_c*100:13.2f}%  {max_err_y*100:13.2f}%  {elapsed:6.0f}s")
    mc_results_by_N[N_agents] = {'max_err_c': max_err_c, 'max_err_y': max_err_y, 'per_shock': per_shock}

# Check if we need more MC points
worst_N = max(mc_results_by_N.keys())
worst_err = mc_results_by_N[worst_N]['max_err_c']
best_N = min(mc_results_by_N.keys())
best_err = mc_results_by_N[best_N]['max_err_c']

# MC error scales as 1/sqrt(N). If best_err > 1%, estimate N needed.
if best_err > 0.01:
    # err ~ C / sqrt(N) => N_needed = N_current * (err_current / 0.01)^2
    N_guess = int(best_N * (best_err / 0.01)**2)
    print(f"\n  N={best_N} gives {best_err*100:.1f}% error.")
    print(f"  Extrapolating: need N ≈ {N_guess:,} for 1% error (1/√N scaling)")
    if N_guess <= 500000:
        print(f"  Running N={N_guess}...", flush=True)
        t0 = time()
        all_seed_results = []
        for s in range(NUM_SEEDS):
            all_seed_results.append(run_mc_all_experiments(N_guess, seed=s))
        max_err_c, max_err_y = 0, 0
        for shock in SHOCKS_NO_REC + SHOCKS_REC:
            mean_c = np.mean([r[shock]['npv_c'] for r in all_seed_results])
            mean_y = np.mean([r[shock]['npv_y'] for r in all_seed_results])
            ref = tm_ref_pc[shock]
            if abs(ref['npv_c']) > 1e-10:
                max_err_c = max(max_err_c, abs(mean_c - ref['npv_c']) / abs(ref['npv_c']))
            if abs(ref['npv_y']) > 1e-10:
                max_err_y = max(max_err_y, abs(mean_y - ref['npv_y']) / abs(ref['npv_y']))
        elapsed = time() - t0
        print(f"  {N_guess:10d}  {NUM_SEEDS:5d}  {max_err_c*100:13.2f}%  {max_err_y*100:13.2f}%  {elapsed:6.0f}s")

# ============================================================
# Per-shock detail for the largest MC
# ============================================================
print(f"\n--- Per-shock detail (MC N=80K vs TM mCount=400) ---")
print(f"  {'shock':>20s}  {'TM ref NPV_C':>12s}  {'MC NPV_C':>12s}  {'rel_err_C':>10s}  {'MC std_C':>10s}")
print("  " + "-" * 70)
ps = mc_results_by_N[80000]['per_shock']
for shock in SHOCKS_NO_REC + SHOCKS_REC:
    ref = tm_ref_pc[shock]
    mc = ps[shock]
    print(f"  {shock:>20s}  {ref['npv_c']:12.4f}  {mc['mean_c']:12.4f}  {mc['err_c']*100:9.2f}%  {mc['std_c']:10.4f}")

print(f"\nTotal time: {time()-t0_total:.0f}s ({(time()-t0_total)/60:.1f} min)")
