"""
Three-way comparison of E[c(m) * p] for a single agent type:

  (a) MC:  mean(cNrm_i * pLvl_i) from simulation
  (b) 2D TM:  integral c(m) * p * f(m,p,j) dm dp  (direct)
  (c) Neutral-measure 1D TM:  E_Q[c(m)] * E[p]  (Harmenberg)

All three should agree (within their respective approximation errors).
"""

import sys
import numpy as np
from copy import deepcopy
from time import time
import scipy.sparse as sp

sys.argv = ['test_threeway']

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from HARK.distributions import DiscreteDistribution
from HARK.utilities import jump_to_grid_1D, jump_to_grid_2D, make_grid_exp_mult
from tm_methods import (
    build_tm_agg_fiscal, find_ergodic_distribution,
    compute_analytical_mean_pLvl, _build_period_tm, _make_newborn_dist,
)

# ============================================================
# Setup: one agent type, base solved
# ============================================================
print("=" * 70, flush=True)
print("Three-way E[c*p] comparison", flush=True)
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

bt = AggFiscalType(**init_highschool)
bt.cycles = 0
bt.get_economy_data(econ)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([bt.IncUnemp])]
)
IncShkDstn_unemp_nb = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([bt.IncUnempNoBenefits])]
)
EmployedIncShkDstn = deepcopy(bt.IncShkDstn[0])
bt.IncShkDstn = [
    [EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal
    + [IncShkDstn_unemp_nb]
]
bt.IncShkDstn_base = bt.IncShkDstn

mid_b = DiscFacCount // 2
bt.DiscFac = DiscFacDstns[1].atoms[0][mid_b]
bt.AgentCount = 50000
bt.seed = 42

econ.agents = [bt]
bt.get_economy_data(econ)

print(f"Agent: HighSchool, beta={bt.DiscFac:.4f}, N={bt.AgentCount}", flush=True)
print(f"PermGroFac = {bt.PermGroFac[0][0]:.6f}", flush=True)

t0 = time()
econ.solve()
print(f"Solve: {time()-t0:.1f}s", flush=True)

J = bt.num_base_MrkvStates
sol = bt.solution[0]

# ============================================================
# (a) Monte Carlo
# ============================================================
print(f"\n--- (a) Monte Carlo ---", flush=True)

econ.reset()
bt.initialize_sim()
bt.AggDemandFac = 1.0
bt.RfreeNow = 1.0
bt.CaggNow = 1.0

t0 = time()
econ.make_history()
print(f"Burn-in: {time()-t0:.1f}s", flush=True)

econ.save_state()
econ.switch_to_counterfactual_mode("base")
econ.make_idiosyncratic_shock_histories()
mc_results = econ.run_experiment(**base_dict, Full_Output=True)

mc_cNrm = bt.history['cNrm']       # (T, N)
mc_pLvl = bt.history['pLvl']       # (T, N)
mc_cLvl = mc_cNrm * mc_pLvl        # cLvl = cNrm * pLvl

MC_E_cNrm = np.mean(mc_cNrm)
MC_E_pLvl = np.mean(mc_pLvl)
MC_E_cLvl = np.mean(mc_cLvl)
MC_E_cNrm_times_E_pLvl = MC_E_cNrm * MC_E_pLvl

print(f"  MC E[cNrm]          = {MC_E_cNrm:.8f}", flush=True)
print(f"  MC E[pLvl]          = {MC_E_pLvl:.4f}", flush=True)
print(f"  MC E[cNrm]*E[pLvl]  = {MC_E_cNrm_times_E_pLvl:.6f}", flush=True)
print(f"  MC E[cNrm*pLvl]     = {MC_E_cLvl:.6f}  <-- TRUE level aggregate", flush=True)
print(f"  Ratio (independence assumption): {MC_E_cNrm_times_E_pLvl / MC_E_cLvl:.6f}"
      f"  (!=1 proves cov<0)", flush=True)
print(f"  cov(cNrm, pLvl)     = {MC_E_cLvl - MC_E_cNrm_times_E_pLvl:.6f}", flush=True)

# ============================================================
# (c) Neutral-measure 1D TM  (before 2D, since it's simpler)
# ============================================================
print(f"\n--- (c) Neutral-measure 1D TM ---", flush=True)

mCount_1d = 200
mMin = 0.001
mMax = 50.0
mFac = 3
dist_mGrid = make_grid_exp_mult(ming=mMin, maxg=mMax, ng=mCount_1d, timestonest=mFac)
M = len(dist_mGrid)

# Evaluate policies
cPol = []
aPol_2d = np.empty((J, M), dtype=np.float64)
for j in range(J):
    cPol_j = sol.cFunc[j](dist_mGrid, 1.0 * np.ones_like(dist_mGrid))
    aPol_j = np.maximum(dist_mGrid - cPol_j, 0.0)
    cPol.append(cPol_j)
    aPol_2d[j, :] = aPol_j

MrkvArray = bt.MrkvArray[0]
Rfree_arr = np.asarray(bt.Rfree[:J], dtype=np.float64)
PermGroFac_arr = np.asarray(bt.PermGroFac[0][:J], dtype=np.float64)
LivPrb_arr = np.asarray(bt.LivPrb[0][:J], dtype=np.float64)

# Actual-measure TM (existing code)
markov_erg = np.linalg.lstsq(
    np.vstack([MrkvArray.T - np.eye(J), np.ones(J)]),
    np.append(np.zeros(J), 1.0), rcond=None
)[0]

IncShkDstn_list = [bt.IncShkDstn[0][jp] for jp in range(J)]
NewBornDist_actual = _make_newborn_dist(dist_mGrid, IncShkDstn_list, markov_erg)
TM_actual = _build_period_tm(
    dist_mGrid, aPol_2d, IncShkDstn_list, MrkvArray,
    Rfree_arr, PermGroFac_arr, LivPrb_arr, NewBornDist_actual,
)
erg_actual = find_ergodic_distribution(TM_actual)

E_cNrm_actual = 0.0
for j in range(J):
    dstn_j = erg_actual[j * M : (j + 1) * M]
    E_cNrm_actual += np.dot(cPol[j], dstn_j)

# Neutral-measure TM: reweight shock probs by perm_shk
IncShkDstn_neutral = []
for jp in range(J):
    d = bt.IncShkDstn[0][jp]
    perm_shks = d.atoms[0]
    neutral_pmv = d.pmv * perm_shks
    s = np.sum(neutral_pmv)
    if s > 0:
        neutral_pmv = neutral_pmv / s
    IncShkDstn_neutral.append(
        DiscreteDistribution(neutral_pmv, [d.atoms[0], d.atoms[1]])
    )

NewBornDist_neutral = _make_newborn_dist(dist_mGrid, IncShkDstn_neutral, markov_erg)
TM_neutral = _build_period_tm(
    dist_mGrid, aPol_2d, IncShkDstn_neutral, MrkvArray,
    Rfree_arr, PermGroFac_arr, LivPrb_arr, NewBornDist_neutral,
)
erg_neutral = find_ergodic_distribution(TM_neutral)

E_star_cNrm = 0.0
for j in range(J):
    dstn_j = erg_neutral[j * M : (j + 1) * M]
    E_star_cNrm += np.dot(cPol[j], dstn_j)

# Verify E*[1/psi] ~ 1
d_emp = IncShkDstn_neutral[0]
E_star_inv_psi = np.sum(d_emp.pmv / d_emp.atoms[0])
print(f"  E*[1/psi] = {E_star_inv_psi:.8f}  (should be ~1.0)", flush=True)

# Column sum checks
col_sums_actual = TM_actual.sum(axis=0)
col_sums_neutral = TM_neutral.sum(axis=0)
print(f"  Actual TM col sums: min={col_sums_actual.min():.12f} max={col_sums_actual.max():.12f}", flush=True)
print(f"  Neutral TM col sums: min={col_sums_neutral.min():.12f} max={col_sums_neutral.max():.12f}", flush=True)

E_pLvl_analytical = compute_analytical_mean_pLvl(bt)

print(f"\n  E[cNrm] (actual measure)  = {E_cNrm_actual:.8f}", flush=True)
print(f"  E*[cNrm] (neutral measure) = {E_star_cNrm:.8f}", flush=True)
print(f"  Ratio E*/E = {E_star_cNrm / E_cNrm_actual:.8f}  (<1 confirms cov<0)", flush=True)

NM_E_cLvl = E_star_cNrm * E_pLvl_analytical
print(f"\n  E*[cNrm] * E_analytical[pLvl] = {NM_E_cLvl:.6f}", flush=True)
print(f"  E_analytical[pLvl] = {E_pLvl_analytical:.4f}", flush=True)

# Also try with MC E[pLvl] for comparison
NM_E_cLvl_mc = E_star_cNrm * MC_E_pLvl
print(f"  E*[cNrm] * MC_E[pLvl]        = {NM_E_cLvl_mc:.6f}", flush=True)

# ============================================================
# (b) 2D TM
# ============================================================
print(f"\n--- (b) 2D TM ---", flush=True)

mCount_2d = 50
pCount = 25

dist_mGrid_2d = make_grid_exp_mult(ming=mMin, maxg=mMax, ng=mCount_2d, timestonest=mFac)
M2 = len(dist_mGrid_2d)

# p-grid: log-spaced covering the ergodic pLvl range
# Initial pLvl ~ LogN(2.407, 0.42), with PermGroFac=1.00453, lifetime ~160 quarters
# Ergodic pLvl has log-std ~1.0, log-mean ~3.0. Use 3-sigma range.
log_p_center = np.log(MC_E_pLvl)
log_p_std = 1.0
p_lo = np.exp(log_p_center - 3.0 * log_p_std)
p_hi = np.exp(log_p_center + 3.0 * log_p_std)
dist_pGrid = np.exp(np.linspace(np.log(p_lo), np.log(p_hi), pCount))
P2 = len(dist_pGrid)
MP2 = M2 * P2
N_states = MP2 * J

print(f"  m-grid: {M2} pts, p-grid: {P2} pts, J={J}", flush=True)
print(f"  Total states: {N_states}", flush=True)
print(f"  p-grid range: [{dist_pGrid[0]:.4f}, {dist_pGrid[-1]:.4f}]", flush=True)

# Evaluate policies on 2D m-grid (policy depends on m only, not p)
cPol_2d = []
aPol_2d_for2d = []
for j in range(J):
    c_j = sol.cFunc[j](dist_mGrid_2d, 1.0 * np.ones_like(dist_mGrid_2d))
    a_j = np.maximum(dist_mGrid_2d - c_j, 0.0)
    cPol_2d.append(c_j)
    aPol_2d_for2d.append(a_j)

# Newborn 2D distribution:
# Newborn p ~ LogNormal(pLvlInitMean, pLvlInitStd), a=0, m = theta (tran shock)
pLogInitMean = bt.pLogInitMean
pLogInitStd = bt.pLogInitStd
n_newborn_pts = 50
from scipy.stats import lognorm
p_newborn_pts = lognorm.ppf(
    np.linspace(0.02, 0.98, n_newborn_pts),
    s=pLogInitStd, scale=np.exp(pLogInitMean)
)
p_newborn_prbs = np.ones(n_newborn_pts) / n_newborn_pts

NewBornDist_2d = np.zeros(N_states)
for jp in range(J):
    d_jp = bt.IncShkDstn[0][jp]
    tran_shks_jp = d_jp.atoms[1]
    shk_prbs_jp = d_jp.pmv
    n_shk = len(shk_prbs_jp)

    m_newborn = np.tile(tran_shks_jp, n_newborn_pts)
    p_newborn = np.repeat(p_newborn_pts, n_shk)
    w_newborn = np.repeat(p_newborn_prbs, n_shk) * np.tile(shk_prbs_jp, n_newborn_pts)

    lottery_nb = jump_to_grid_2D(m_newborn, p_newborn, w_newborn, dist_mGrid_2d, dist_pGrid)
    NewBornDist_2d[jp * MP2 : (jp + 1) * MP2] = markov_erg[jp] * lottery_nb

s = np.sum(NewBornDist_2d)
if s > 0:
    NewBornDist_2d /= s

# Build 2D TM using sparse COO format
t0 = time()
rows_list = []
cols_list = []
data_list = []
n_src_done = 0
n_src_total = J * M2 * P2

for j in range(J):
    LivPrb_j = LivPrb_arr[j]
    death_prb = 1.0 - LivPrb_j
    nb_nz_idx = np.nonzero(NewBornDist_2d > 1e-18)[0]
    nb_nz_val = NewBornDist_2d[nb_nz_idx]

    for i in range(M2):
        for k in range(P2):
            src_idx = j * MP2 + i * P2 + k

            # Death/rebirth contribution
            rows_list.append(nb_nz_idx)
            cols_list.append(np.full(len(nb_nz_idx), src_idx, dtype=np.int64))
            data_list.append(death_prb * nb_nz_val)

            # Survival contributions
            for jp in range(J):
                markov_prob = MrkvArray[j, jp]
                if markov_prob < 1e-15:
                    continue

                d_jp = bt.IncShkDstn[0][jp]
                bNext_i = Rfree_arr[jp] * aPol_2d_for2d[j][i]
                perm_shks = d_jp.atoms[0]
                tran_shks = d_jp.atoms[1]
                shk_prbs = d_jp.pmv

                mNext_shks = bNext_i / (perm_shks * PermGroFac_arr[jp]) + tran_shks
                pNext_shks = dist_pGrid[k] * perm_shks * PermGroFac_arr[jp]

                lottery_2d = jump_to_grid_2D(
                    mNext_shks, pNext_shks, shk_prbs, dist_mGrid_2d, dist_pGrid
                )

                nz = np.nonzero(lottery_2d > 1e-18)[0]
                if len(nz) > 0:
                    dst_flat = jp * MP2 + nz
                    rows_list.append(dst_flat)
                    cols_list.append(np.full(len(nz), src_idx, dtype=np.int64))
                    data_list.append(markov_prob * LivPrb_j * lottery_2d[nz])

            n_src_done += 1
            if n_src_done % 500 == 0:
                print(f"    {n_src_done}/{n_src_total} sources processed...",
                      flush=True)

all_rows = np.concatenate(rows_list)
all_cols = np.concatenate(cols_list)
all_data = np.concatenate(data_list)

TM_2d = sp.csc_matrix(
    (all_data, (all_rows, all_cols)),
    shape=(N_states, N_states)
)
TM_2d.sum_duplicates()
build_time = time() - t0
print(f"  2D TM built in {build_time:.1f}s", flush=True)
print(f"  Nonzeros: {TM_2d.nnz}", flush=True)

# Column sums
col_sums_2d = np.array(TM_2d.sum(axis=0)).flatten()
print(f"  Column sums: min={col_sums_2d.min():.8f} max={col_sums_2d.max():.8f}", flush=True)

# Ergodic distribution (power iteration on sparse)
t0 = time()
v = np.ones(N_states) / N_states
for it in range(5000):
    v_new = TM_2d @ v
    v_new = np.maximum(v_new, 0.0)
    s = v_new.sum()
    if s > 0:
        v_new /= s
    diff = np.max(np.abs(v_new - v))
    v = v_new
    if diff < 1e-12:
        break
erg_2d = v
print(f"  Ergodic found in {it+1} iterations, {time()-t0:.1f}s", flush=True)

# Compute level aggregate directly: E[c*p] = sum_j sum_i sum_k c(m_i)*p_k*f(m_i,p_k,j)
E_cLvl_2d = 0.0
E_cNrm_2d = 0.0
E_pLvl_2d = 0.0
for j in range(J):
    block = erg_2d[j * MP2 : (j + 1) * MP2].reshape(M2, P2)
    m_marginal = block.sum(axis=1)
    E_cNrm_2d += np.dot(cPol_2d[j], m_marginal)
    E_cLvl_2d += np.dot(cPol_2d[j], block @ dist_pGrid)
    E_pLvl_2d += np.sum(block @ dist_pGrid)

print(f"  2D E[cNrm]     = {E_cNrm_2d:.8f}", flush=True)
print(f"  2D E[pLvl]     = {E_pLvl_2d:.4f}", flush=True)
print(f"  2D E[c*p]      = {E_cLvl_2d:.6f}  <-- direct level aggregate", flush=True)

# ============================================================
# Comparison
# ============================================================
print(f"\n{'='*70}", flush=True)
print(f"THREE-WAY COMPARISON: E[c(m) * p]", flush=True)
print(f"{'='*70}", flush=True)

print(f"\n  {'Method':<45} {'E[c*p]':>12} {'vs MC':>10}", flush=True)
print(f"  {'-'*67}", flush=True)

print(f"  {'(a) MC: mean(cNrm*pLvl)':<45} {MC_E_cLvl:>12.6f} {'---':>10}", flush=True)

ratio_nm_anal = NM_E_cLvl / MC_E_cLvl
print(f"  {'(c) Neutral 1D: E*[c]*E_anal[p]':<45} {NM_E_cLvl:>12.6f} "
      f"{ratio_nm_anal:>10.6f}", flush=True)

ratio_nm_mc = NM_E_cLvl_mc / MC_E_cLvl
print(f"  {'(c) Neutral 1D: E*[c]*MC_E[p]':<45} {NM_E_cLvl_mc:>12.6f} "
      f"{ratio_nm_mc:>10.6f}", flush=True)

ratio_2d = E_cLvl_2d / MC_E_cLvl
print(f"  {'(b) 2D TM: direct integral':<45} {E_cLvl_2d:>12.6f} "
      f"{ratio_2d:>10.6f}", flush=True)

wrong_val = E_cNrm_actual * MC_E_pLvl
ratio_wrong = wrong_val / MC_E_cLvl
print(f"  {'(WRONG) E[c]*E[p] (independence)':<45} {wrong_val:>12.6f} "
      f"{ratio_wrong:>10.6f}", flush=True)

print(f"\n  Key diagnostic:", flush=True)
print(f"    cov(cNrm, pLvl) / E[pLvl] = {(MC_E_cLvl - MC_E_cNrm_times_E_pLvl)/MC_E_pLvl:.8f}", flush=True)
print(f"    E*[cNrm] - E[cNrm]         = {E_star_cNrm - E_cNrm_actual:.8f}", flush=True)
print(f"    (these should be approximately equal)", flush=True)

print(f"\n{'='*70}", flush=True)
print(f"Done!", flush=True)
print(f"{'='*70}", flush=True)
