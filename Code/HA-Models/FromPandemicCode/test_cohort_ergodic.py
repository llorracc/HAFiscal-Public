"""
Proof of concept: per-age-cohort TM ergodic.

Instead of one distribution with effective death rate, maintain T_age
separate distributions (one per cohort). Forced death removes cohort
T_age exactly (the oldest, wealthiest agents). This should close the
~2% mean aNrm gap between TM and MC burn-in.

Compare:
  1. Standard TM ergodic (effective death rate, single distribution)
  2. Per-cohort TM ergodic (exact forced death)
  3. MC burn-in (ground truth)
"""

import os, sys, numpy as np
from time import time
from copy import deepcopy
import scipy.sparse as sp

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())
os.environ['MPLBACKEND'] = 'Agg'

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import (
    build_tm_agg_fiscal, find_ergodic_distribution,
    _build_period_tm, _make_newborn_dist, _solve_markov_ergodic,
    _effective_LivPrb,
)

# ============================================================
# Setup (college type)
# ============================================================
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, *_rest] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')
UBspell_normal = _rest[2]
num_experiment_periods = _rest[6]

J = 4
MCOUNT = 50

BaseType = AggFiscalType(**init_college)
BaseType.cycles = 0
BaseType.AgentCount = 200000
BaseType.DiscFac = DiscFacDstns[2].atoms[0][0]
AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

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
LivPrb = BaseType.LivPrb[0][0]
T_age = BaseType.T_age
PermGroFac_arr = np.asarray(BaseType.PermGroFac[0][:J], dtype=np.float64)
Rfree_arr = np.asarray(BaseType.Rfree[:J], dtype=np.float64)
LivPrb_arr = np.asarray(BaseType.LivPrb[0][:J], dtype=np.float64)

IncShkDstn_list = [BaseType.IncShkDstn_base[0][j] for j in range(J)]
micro_trans = BaseType.CondMrkvArrays[0]
markov_ergodic = _solve_markov_ergodic(micro_trans)
# NewBornDist is built after we have dist_mGrid (from build_tm_agg_fiscal)
NewBornDist = None  # placeholder, built below

# Build cFuncs for aNrm computation
cFuncs = [sol.cFunc[j] for j in range(J)]

print(f"T_age={T_age}, LivPrb={LivPrb:.6f}, J={J}, mCount={MCOUNT}")

# ============================================================
# Method 1: Standard TM ergodic (effective death rate)
# ============================================================
print("\n--- Method 1: Standard TM (effective death rate) ---")
t0 = time()
tm_std = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
ergodic_std = find_ergodic_distribution(tm_std['TranMatrix'])
dist_mGrid = tm_std['dist_mGrid']
M = len(dist_mGrid)

mean_aNrm_std = 0.0
mean_mNrm_std = 0.0
for j in range(J):
    d_j = ergodic_std[j*M:(j+1)*M]
    aPol_j = np.maximum(dist_mGrid - cFuncs[j](dist_mGrid, np.ones(M)), 0.0)
    mean_aNrm_std += np.dot(aPol_j, d_j)
    mean_mNrm_std += np.dot(dist_mGrid, d_j)
print(f"  mean aNrm = {mean_aNrm_std:.6f}")
print(f"  mean mNrm = {mean_mNrm_std:.6f}")
print(f"  time: {time()-t0:.2f}s")

# ============================================================
# Method 2: Per-cohort TM ergodic (exact forced death)
# ============================================================
print(f"\n--- Method 2: Per-cohort TM (T_age={T_age} cohorts) ---")
t0 = time()

# Build TM WITHOUT death (LivPrb=1 for all states)
# This TM just does: consume → save → transition → income
# No death/rebirth channel.
M_loc = MCOUNT  # use same grid size

# Build aPol from solution
aPol_2d = np.empty((J, M), dtype=np.float64)
for j in range(J):
    cPol_j = cFuncs[j](dist_mGrid, np.ones(M))
    aPol_2d[j, :] = np.maximum(dist_mGrid - cPol_j, 0.0)

# Newborn distribution (on the mNrm grid)
nb = _make_newborn_dist(dist_mGrid, IncShkDstn_list, markov_ergodic)

# LivPrb = 1 (no death in the TM itself — we handle death externally via cohorts)
LivPrb_nodeath = np.ones(J, dtype=np.float64)

TM_nodeath = _build_period_tm(
    dist_mGrid, aPol_2d, IncShkDstn_list, micro_trans,
    Rfree_arr, PermGroFac_arr, LivPrb_nodeath, nb,
    neutral_measure=False,
)

# Convert to dense for fast repeated multiply (small matrix)
if sp.issparse(TM_nodeath):
    TM_dense = TM_nodeath.toarray()
else:
    TM_dense = np.asarray(TM_nodeath)

# Iterate cohorts:
# cohort_0 = newborn distribution
# cohort_k = LivPrb * TM_nodeath @ cohort_{k-1}  (random death thins each cohort)
# cohort at age T_age is removed entirely (forced death)
# Ergodic = sum of all cohorts, normalized

cohorts = np.zeros((T_age, M * J))
cohorts[0] = nb.copy()

for k in range(1, T_age):
    # Survive random death, then transition
    cohorts[k] = LivPrb * (TM_dense @ cohorts[k-1])

# Aggregate
ergodic_cohort = np.sum(cohorts, axis=0)
ergodic_cohort = np.maximum(ergodic_cohort, 0.0)
ergodic_cohort /= np.sum(ergodic_cohort)

mean_aNrm_cohort = 0.0
mean_mNrm_cohort = 0.0
for j in range(J):
    d_j = ergodic_cohort[j*M:(j+1)*M]
    aPol_j = np.maximum(dist_mGrid - cFuncs[j](dist_mGrid, np.ones(M)), 0.0)
    mean_aNrm_cohort += np.dot(aPol_j, d_j)
    mean_mNrm_cohort += np.dot(dist_mGrid, d_j)

t_cohort = time() - t0
print(f"  mean aNrm = {mean_aNrm_cohort:.6f}")
print(f"  mean mNrm = {mean_mNrm_cohort:.6f}")
print(f"  time: {t_cohort:.2f}s")

# Per-state detail
print(f"\n  Per-state (cohort ergodic):")
for j in range(J):
    d_j = ergodic_cohort[j*M:(j+1)*M]
    frac = np.sum(d_j)
    mean_m = np.dot(dist_mGrid, d_j) / max(frac, 1e-30)
    aPol_j = np.maximum(dist_mGrid - cFuncs[j](dist_mGrid, np.ones(M)), 0.0)
    mean_a = np.dot(aPol_j, d_j) / max(frac, 1e-30)
    print(f"    State {j}: frac={frac:.6f}, mean_mNrm={mean_m:.4f}, mean_aNrm={mean_a:.4f}")

# ============================================================
# Method 3: MC burn-in (ground truth)
# ============================================================
print(f"\n--- Method 3: MC burn-in (400 periods, N={BaseType.AgentCount}) ---")
t0 = time()

eco_bi = deepcopy(AggEco)
a_bi = eco_bi.agents[0]
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
bi_Mrkv = a_bi.shocks['Mrkv'] % J
mean_aNrm_bi = np.mean(bi_aNrm)

# Compute mNrm for burn-in agents (need to run one more step)
# Actually, state_now has aNrm from end of last period.
# mNrm would require the next period's income draw.
# Instead, just report aNrm.

t_bi = time() - t0
print(f"  mean aNrm = {mean_aNrm_bi:.6f}")
print(f"  time: {t_bi:.2f}s")

print(f"\n  Per-state (MC burn-in):")
for j in range(J):
    mask = bi_Mrkv == j
    if np.sum(mask) > 0:
        print(f"    State {j}: frac={np.mean(mask):.6f}, mean_aNrm={np.mean(bi_aNrm[mask]):.4f}")

# ============================================================
# Summary
# ============================================================
print(f"\n{'=' * 60}")
print(f"SUMMARY: mean aNrm comparison")
print(f"{'=' * 60}")
print(f"  Standard TM (eff. death): {mean_aNrm_std:.6f}")
print(f"  Per-cohort TM:            {mean_aNrm_cohort:.6f}")
print(f"  MC burn-in:               {mean_aNrm_bi:.6f}")
print(f"")
print(f"  Gap std TM vs MC:    {(mean_aNrm_std - mean_aNrm_bi) / mean_aNrm_bi * 100:+.2f}%")
print(f"  Gap cohort TM vs MC: {(mean_aNrm_cohort - mean_aNrm_bi) / mean_aNrm_bi * 100:+.2f}%")
print(f"  Improvement:         {abs(mean_aNrm_std - mean_aNrm_bi) - abs(mean_aNrm_cohort - mean_aNrm_bi):.6f}")

# Also check: does grid resolution matter?
print(f"\n--- Grid resolution sweep (per-cohort) ---")
for mc in [50, 100, 200]:
    tm_g = build_tm_agg_fiscal(BaseType, mCount=mc, Cratio=1.0)
    grid_g = tm_g['dist_mGrid']
    M_g = len(grid_g)
    aPol_g = np.empty((J, M_g))
    for j in range(J):
        aPol_g[j] = np.maximum(grid_g - cFuncs[j](grid_g, np.ones(M_g)), 0.0)
    IncShkDstn_g = [BaseType.IncShkDstn_base[0][j] for j in range(J)]
    nb_g = _make_newborn_dist(grid_g, IncShkDstn_g, markov_ergodic)
    TM_g = _build_period_tm(grid_g, aPol_g, IncShkDstn_g, micro_trans,
                             Rfree_arr, PermGroFac_arr, np.ones(J), nb_g)
    if sp.issparse(TM_g):
        TM_g = TM_g.toarray()
    cohorts_g = np.zeros((T_age, M_g * J))
    cohorts_g[0] = nb_g
    for k in range(1, T_age):
        cohorts_g[k] = LivPrb * (TM_g @ cohorts_g[k-1])
    erg_g = np.sum(cohorts_g, axis=0)
    erg_g /= np.sum(erg_g)
    mean_a_g = sum(np.dot(np.maximum(grid_g - cFuncs[j](grid_g, np.ones(M_g)), 0.0),
                          erg_g[j*M_g:(j+1)*M_g]) for j in range(J))
    gap = (mean_a_g - mean_aNrm_bi) / mean_aNrm_bi * 100
    print(f"  mCount={mc:4d}: mean_aNrm={mean_a_g:.6f}, gap vs MC={gap:+.2f}%")
