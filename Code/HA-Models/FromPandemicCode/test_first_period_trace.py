"""
Trace exactly what happens in the first period of MC vs TM, starting
from the same TM ergodic distribution.

For TM: TM @ ergodic = ergodic (by definition).
For MC: sample agents from ergodic, sim_one_period, compare.

This pinpoints WHERE the MC diverges from TM in the first step.
"""

import os, sys, numpy as np
from copy import deepcopy

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())
os.environ['MPLBACKEND'] = 'Agg'

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from income_process_sst import effective_perm_shock_periods_for_t_age, effective_pLvl_growth, effective_perm_shock_variance_periods
from tm_methods import (
    compute_baseline_tm_data, build_tm_agg_fiscal, find_ergodic_distribution,
)

# Setup (college type, same as GLP-1)
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, *_rest] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')
UBspell_normal = _rest[2]
num_experiment_periods = _rest[6]

N = 200000  # large for low noise
J = 4
MCOUNT = 50

BaseType = AggFiscalType(**init_college)
BaseType.cycles = 0
BaseType.AgentCount = N
BaseType.DiscFac = DiscFacDstns[2].atoms[0][0]
AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

# IncShkDstn setup
IncShkDstn_unemp = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])
BaseType.IncShkDstn[0].seed = 763607780
BaseType.IncShkDstn[0].reset()
BaseType.IncShkDstn = [[BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
BaseType.IncShkDstn_base = BaseType.IncShkDstn
IncShkDstn_recession = [BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
BaseType.IncShkDstn_recession = IncShkDstn_recession
BaseType.IncShkDstn_recessionUI = IncShkDstn_recession
BaseType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)
EmployedIncShkDstn = deepcopy(BaseType.IncShkDstn[0][0])
EmployedIncShkDstn.atoms[0][1] = EmployedIncShkDstn.atoms[0][1] * BaseType.TaxCutIncFactor
TaxCutStatesIncShkDstn = [EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]
IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
for i in range(2*J, 18*J):
    IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
BaseType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut

AggEco.agents = [BaseType]
AggEco.solve()

sol = BaseType.solution[0]
cFuncs = [sol.cFunc[j] for j in range(J)]

# TM ergodic
bl = compute_baseline_tm_data(AggEco, mCount=MCOUNT, verbose=False)
bd = bl[0]
ergodic = bd['ergodic']
dist_mGrid = bd['dist_mGrid']
M = len(dist_mGrid)

# ============================================================
# TM: What does the ergodic look like?
# ============================================================
print("=" * 70)
print("TM ERGODIC (mCount=50)")
print("=" * 70)

for j in range(J):
    d_j = ergodic[j*M:(j+1)*M]
    frac = np.sum(d_j)
    mean_m = np.dot(dist_mGrid, d_j) / max(frac, 1e-30)
    # Compute mean aNrm from TM: aNrm = mNrm - cFunc(mNrm) evaluated on grid
    aPol_j = np.maximum(dist_mGrid - cFuncs[j](dist_mGrid, np.ones(M)), 0.0)
    mean_a = np.dot(aPol_j, d_j) / max(frac, 1e-30)
    print(f"  State {j}: frac={frac:.6f}, mean_mNrm={mean_m:.4f}, mean_aNrm(TM)={mean_a:.4f}")

# Overall TM mean aNrm
total_mean_a_tm = 0.0
for j in range(J):
    d_j = ergodic[j*M:(j+1)*M]
    aPol_j = np.maximum(dist_mGrid - cFuncs[j](dist_mGrid, np.ones(M)), 0.0)
    total_mean_a_tm += np.dot(aPol_j, d_j)
print(f"  Overall TM mean aNrm: {total_mean_a_tm:.4f}")

# ============================================================
# MC: Sample agents, check initial aNrm, then one period
# ============================================================
print("\n" + "=" * 70)
print("MC: SAMPLE FROM ERGODIC AND TRACE FIRST PERIOD")
print("=" * 70)

rng = np.random.RandomState(42)
flat_probs = ergodic / np.sum(ergodic)
bins = rng.choice(len(flat_probs), size=N, p=flat_probs)
mc_j = bins // M
mc_m_idx = bins % M
mc_mNrm = dist_mGrid[mc_m_idx].copy()

# Add within-cell noise
for i in range(N):
    idx = mc_m_idx[i]
    if idx < M - 1:
        lo, hi = dist_mGrid[idx], dist_mGrid[idx + 1]
    else:
        lo, hi = dist_mGrid[idx], dist_mGrid[idx] * 1.01
    mc_mNrm[i] = rng.uniform(lo, hi)

# Compute aNrm = mNrm - cFunc(mNrm) for each agent
mc_aNrm = np.zeros(N)
mc_cNrm = np.zeros(N)
for j in range(J):
    mask = mc_j == j
    if np.any(mask):
        c = cFuncs[j](mc_mNrm[mask], np.ones(np.sum(mask)))
        mc_cNrm[mask] = c
        mc_aNrm[mask] = np.maximum(mc_mNrm[mask] - c, 0.0)

print(f"\n  Initial MC (sampled from TM ergodic, N={N}):")
print(f"    mean mNrm: {np.mean(mc_mNrm):.6f}")
print(f"    mean cNrm: {np.mean(mc_cNrm):.6f}")
print(f"    mean aNrm: {np.mean(mc_aNrm):.6f}")
print(f"    TM aNrm:   {total_mean_a_tm:.6f}")
print(f"    Gap:        {(np.mean(mc_aNrm) - total_mean_a_tm) / total_mean_a_tm * 100:+.2f}%")

# Check: aNrm without within-cell noise (exact grid points)
mc_aNrm_exact = np.zeros(N)
mc_mNrm_exact = dist_mGrid[mc_m_idx]
for j in range(J):
    mask = mc_j == j
    if np.any(mask):
        c = cFuncs[j](mc_mNrm_exact[mask], np.ones(np.sum(mask)))
        mc_aNrm_exact[mask] = np.maximum(mc_mNrm_exact[mask] - c, 0.0)
print(f"    mean aNrm (no noise, exact grid): {np.mean(mc_aNrm_exact):.6f}")
print(f"    Gap vs TM:  {(np.mean(mc_aNrm_exact) - total_mean_a_tm) / total_mean_a_tm * 100:+.2f}%")

# ============================================================
# MC: Inject and run ONE period, inspect each sub-step
# ============================================================
print(f"\n  Injecting into MC agent and running 1 period...")

# pLvl setup (simplified: use E[pLvl] for all, since we're tracing mNrm/aNrm)
LivPrb = BaseType.LivPrb[0][0]
T_age = BaseType.T_age
age_probs = np.array([LivPrb**(k-1) for k in range(1, T_age + 1)])
age_probs /= np.sum(age_probs)
mc_ages = rng.choice(T_age, size=N, p=age_probs) + 1

pLogInitMean = BaseType.pLogInitMean
pLogInitStd = getattr(BaseType, 'pLogInitStd', 0.0)
PermShkDstn = BaseType.IncShkDstn_base[0][0]
log_ps = np.log(PermShkDstn.atoms[0])
ps_var = np.dot(PermShkDstn.pmv, log_ps**2) - np.dot(PermShkDstn.pmv, log_ps)**2
g_lvl = effective_pLvl_growth(BaseType, getattr(BaseType, 'Urate_normal', 0.0))
eff_perm = effective_perm_shock_periods_for_t_age(
    mc_ages, BaseType, getattr(BaseType, 'Urate_normal', 0.0))
log_pLvl = rng.normal(pLogInitMean, pLogInitStd, N) + mc_ages * np.log(g_lvl) + eff_perm * (-ps_var/2) + rng.normal(0, np.sqrt(ps_var * eff_perm))
mc_pLvl = np.exp(log_pLvl)

eco = deepcopy(AggEco)
a = eco.agents[0]
a.AgentCount = N
a.seed = 0
eco.solve()
eco.reset()
a.initialize_sim()

# Inject
a.state_now['aNrm'][:] = mc_aNrm
a.state_now['pLvl'][:] = mc_pLvl
a.shocks['Mrkv'][:] = mc_j
if hasattr(a, 't_age') and a.t_age is not None:
    a.t_age[:] = mc_ages
a.AggDemandFac = 1.0
a.RfreeNow = 1.0
a.CaggNow = 1.0
a.Cratio = 1.0
a.state_now['PlvlAgg'] = 1.0

# Record pre-period state
pre_aNrm = a.state_now['aNrm'].copy()
pre_pLvl = a.state_now['pLvl'].copy()
pre_Mrkv = a.shocks['Mrkv'].copy()
pre_t_age = a.t_age.copy() if hasattr(a, 't_age') and a.t_age is not None else None

print(f"    Pre-period:  mean aNrm={np.mean(pre_aNrm):.6f}, mean pLvl={np.mean(pre_pLvl):.4f}")

# Run one period
a.sim_one_period()

# Record post-period state
post_aNrm = a.state_now['aNrm'].copy()
post_pLvl = a.state_now['pLvl'].copy()
post_Mrkv = a.shocks['Mrkv'].copy()
post_mNrm = a.state_now['mNrm'].copy() if 'mNrm' in a.state_now else None
post_cNrm = a.state_now.get('cNrm', a.controls.get('cNrm', None))
if post_cNrm is None and 'cNrm' in dir(a):
    post_cNrm = a.cNrm
post_t_age = a.t_age.copy() if hasattr(a, 't_age') and a.t_age is not None else None

print(f"    Post-period: mean aNrm={np.mean(post_aNrm):.6f}, mean pLvl={np.mean(post_pLvl):.4f}")
if post_mNrm is not None:
    print(f"    Post mNrm:   {np.mean(post_mNrm):.6f}")

# ============================================================
# Diagnose: what happened during the period?
# ============================================================
print(f"\n  --- Diagnosing the first period ---")

# 1. Deaths: how many agents died?
if pre_t_age is not None and post_t_age is not None:
    # Agents that were reborn have t_age = 1
    newborn = post_t_age == 1
    n_newborn = np.sum(newborn)
    # Some of these were already t_age=1 (they aged from 0)
    # Actually in HARK, newborns get t_age=0 then incremented to 1
    # Deaths: t_age >= T_age at start of period
    would_die_age = pre_t_age >= T_age
    n_die_age = np.sum(would_die_age)
    # Random deaths: ~(1-LivPrb) of survivors
    n_random_death_expected = int((N - n_die_age) * (1 - LivPrb))
    print(f"  Deaths: {n_die_age} forced (t_age >= {T_age}), ~{n_random_death_expected} random expected")
    print(f"  Newborns (t_age==1): {n_newborn}")

    # What are newborn aNrm values?
    if n_newborn > 0:
        nb_aNrm = post_aNrm[newborn]
        nb_pLvl = post_pLvl[newborn]
        print(f"  Newborn mean aNrm: {np.mean(nb_aNrm):.6f}")
        print(f"  Newborn mean pLvl: {np.mean(nb_pLvl):.6f}")
        # Survivor mean aNrm
        surv = ~newborn
        print(f"  Survivor mean aNrm: {np.mean(post_aNrm[surv]):.6f}")
        print(f"  Survivor mean pLvl: {np.mean(post_pLvl[surv]):.6f}")

# 2. Per-state breakdown
print(f"\n  Per-state after one period:")
micro_post = post_Mrkv % J
micro_pre = pre_Mrkv % J
for j in range(J):
    mask = micro_post == j
    frac = np.mean(mask)
    if np.sum(mask) > 0:
        mean_a = np.mean(post_aNrm[mask])
    else:
        mean_a = 0
    print(f"    State {j}: frac={frac:.6f}, mean_aNrm={mean_a:.4f}")

# 3. Compare with burn-in MC at same N
print(f"\n  --- Burn-in MC reference ---")
eco_bi = deepcopy(AggEco)
a_bi = eco_bi.agents[0]
a_bi.AgentCount = N
a_bi.seed = 0
a_bi.get_economy_data(eco_bi)
eco_bi.solve()
eco_bi.reset()
a_bi.initialize_sim()
a_bi.AggDemandFac = 1.0
a_bi.RfreeNow = 1.0
a_bi.CaggNow = 1.0
eco_bi.make_history()

bi_aNrm = a_bi.state_now['aNrm']
bi_pLvl = a_bi.state_now['pLvl']
bi_Mrkv = a_bi.shocks['Mrkv'] % J
print(f"  Burn-in mean aNrm: {np.mean(bi_aNrm):.6f}")
print(f"  Burn-in mean pLvl: {np.mean(bi_pLvl):.6f}")
for j in range(J):
    mask = bi_Mrkv == j
    if np.sum(mask) > 0:
        print(f"    State {j}: frac={np.mean(mask):.6f}, mean_aNrm={np.mean(bi_aNrm[mask]):.4f}")

# 4. Grid resolution test: does higher mCount change the TM ergodic mean aNrm?
print(f"\n  --- TM ergodic mean aNrm at different mCount ---")
for mc in [50, 100, 200, 400]:
    tm = build_tm_agg_fiscal(BaseType, mCount=mc, Cratio=1.0)
    erg = find_ergodic_distribution(tm['TranMatrix'])
    grid = tm['dist_mGrid']
    m_loc = len(grid)
    total_a = 0.0
    for j in range(J):
        d_j = erg[j*m_loc:(j+1)*m_loc]
        aPol_j = np.maximum(grid - cFuncs[j](grid, np.ones(m_loc)), 0.0)
        total_a += np.dot(aPol_j, d_j)
    print(f"    mCount={mc:4d}: mean_aNrm = {total_a:.6f}")

print(f"\n  Burn-in MC mean aNrm = {np.mean(bi_aNrm):.6f}")
print(f"  If TM converges to burn-in value, grid discretization is the cause.")
print(f"  If TM converges to a different value, something else differs.")
