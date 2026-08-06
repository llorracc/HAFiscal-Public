"""Quick verify: does init_TM_base @ ergodic = ergodic?"""
import os, sys, numpy as np
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
    compute_baseline_tm_data, propagate_experiment_tm,
    build_tm_agg_fiscal, find_ergodic_distribution,
    _build_period_tm, _effective_LivPrb, _solve_markov_ergodic,
    _make_newborn_dist, compute_period_aggregates_tm,
    build_experiment_period_tm,
)

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, *_] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

BaseType = AggFiscalType(**init_highschool)
BaseType.cycles = 0
BaseType.AgentCount = 10000
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]
AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

IncShkDstn_unemp = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])
BaseType.IncShkDstn[0].seed = 763607780
BaseType.IncShkDstn[0].reset()
EmployedIncShkDstn = deepcopy(BaseType.IncShkDstn[0])
BaseType.IncShkDstn = [[BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * 2 + [IncShkDstn_unemp_nobenefits]]
BaseType.IncShkDstn_base = BaseType.IncShkDstn

AggEco.agents = [BaseType]
AggEco.solve()

J = BaseType.num_base_MrkvStates
MCOUNT = 50

# Build ergodic and base_aPol
bl_data = compute_baseline_tm_data(AggEco, dist_aGrid_count=MCOUNT, verbose=False)
bd = bl_data[0]
ergodic = bd['ergodic']
dist_mGrid = bd['dist_mGrid']
base_aPol = bd['base_aPol']
M = len(dist_mGrid)

# Build init_TM with base aPol + base transition
base_agent = AggEco.agents[0]
IncShkDstn_init = [base_agent.IncShkDstn[0][j] for j in range(J)]
micro_trans = base_agent.CondMrkvArrays[0]
Rfree_arr = np.asarray(base_agent.Rfree[:J], dtype=np.float64)
PermGroFac_arr = np.asarray(base_agent.PermGroFac[0][:J], dtype=np.float64)
LivPrb_arr = np.asarray(base_agent.LivPrb[0][:J], dtype=np.float64)
T_age = getattr(base_agent, 'T_age', None)
LivPrb_arr = _effective_LivPrb(LivPrb_arr, T_age)
markov_ergodic = _solve_markov_ergodic(micro_trans)
NewBornDist = _make_newborn_dist(dist_mGrid, IncShkDstn_init, markov_ergodic)

import scipy.sparse as sp
init_TM = _build_period_tm(dist_mGrid, base_aPol, IncShkDstn_init, micro_trans,
                            Rfree_arr, PermGroFac_arr, LivPrb_arr, NewBornDist)

# Apply to ergodic
result = init_TM @ ergodic
if sp.issparse(result):
    result = np.asarray(result).flatten()
result = np.maximum(result, 0.0)
result /= np.sum(result)

# Compare
diff = result - ergodic
print(f"max|init_TM @ ergodic - ergodic| = {np.max(np.abs(diff)):.6e}")
print(f"L1 diff: {np.sum(np.abs(diff)):.6e}")
print(f"Is ergodic a fixed point of init_TM? {'YES' if np.max(np.abs(diff)) < 1e-10 else 'NO — investigate!'}")

# Per-state comparison
for j in range(J):
    erg_j = ergodic[j*M:(j+1)*M]
    res_j = result[j*M:(j+1)*M]
    frac_erg = np.sum(erg_j)
    frac_res = np.sum(res_j)
    mean_erg = np.dot(dist_mGrid, erg_j) / max(frac_erg, 1e-30)
    mean_res = np.dot(dist_mGrid, res_j) / max(frac_res, 1e-30)
    print(f"  State {j}: frac {frac_erg:.6f}→{frac_res:.6f}, mean_mNrm {mean_erg:.6f}→{mean_res:.6f}")

# Also test: propagate base with base_aPol
act_T = AggEco.act_T
r_with = propagate_experiment_tm(base_agent, ergodic, [0]*act_T, dist_mGrid,
                                  bd['E_pLvl'], act_T=act_T, base_aPol=base_aPol)
r_without = propagate_experiment_tm(base_agent, ergodic, [0]*act_T, dist_mGrid,
                                     bd['E_pLvl'], act_T=act_T)
N = base_agent.AgentCount
print(f"\nBase propagation comparison:")
print(f"  With base_aPol:    AggCons[0]/N = {r_with['AggCons'][0]/N:.8f}")
print(f"  Without base_aPol: AggCons[0]/N = {r_without['AggCons'][0]/N:.8f}")
print(f"  Diff: {(r_with['AggCons'][0] - r_without['AggCons'][0])/N:.8e}")
