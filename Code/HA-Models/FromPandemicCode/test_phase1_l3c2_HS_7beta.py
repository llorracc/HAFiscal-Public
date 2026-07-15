"""
Phase 1 L3c.b2: HS cohort with FULL 7-atom DiscFac distribution.

Per user direction: extends L3a/b/c (which were 1 type per cohort) to
exercise the within-cohort β-heterogeneity that the L3a-c stack didn't
test. This is intermediate between L3c (3 cohorts × 1 type each) and L3d
(3 cohorts × 7 atoms each = 21 types).

Configuration: 1 HS cohort × 7 β atoms (DiscFacDstns[1]).
N escalation: start at N=5k. If unified gate (rel_gap ≤ 1% AND rel_SE
≤ 1%) passes, declare success. If not, escalate to N=10k, 25k, 50k,
125k. HALT criteria as in L3b.

Per cascade-gating: only escalate on clean pass.

Test:
  test_l3c2_HS_7beta_cascade — single function that does the escalation
  internally and asserts the gate passes at SOME N. Reports the trajectory.

Run via:
  pytest Code/HA-Models/FromPandemicCode/test_phase1_l3c2_HS_7beta.py -v -s
"""

import os
import sys
import time
import numpy as np
import pytest
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

# CLAUDE.md: patch sys.argv before importing EstimParameters.
_SAVED_ARGV = sys.argv
sys.argv = ['test_phase1_l3c2_HS_7beta']

from EstimParameters import (
    init_highschool, init_ADEconomy, UBspell_normal,
    DiscFacDstns, DiscFacCount, AgentCountTotal, data_EducShares,
)
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from tm_methods import (
    build_tm_agg_fiscal_a,
    compute_type_aggregates_tm_a,
    find_ergodic_distribution,
)
from HARK.distributions import DiscreteDistribution

from test_phase1_l3a import _run_mc_HS_simple, _assert_cross_method_pass

sys.argv = _SAVED_ARGV


def _build_HS_7beta_typelist():
    """Build 7 HS AggFiscalType instances, each with its own DiscFac atom.

    Returns list of 7 solved agents, plus the corresponding pmv weights.
    """
    init = deepcopy(init_highschool)
    base = AggFiscalType(**init)
    base.cycles = 0
    economy = AggregateDemandEconomy(**init_ADEconomy)
    base.get_economy_data(economy)
    IncomeDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([base.IncUnemp])]
    )
    IncomeDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([base.IncUnempNoBenefits])]
    )
    base.IncShkDstn = [
        [base.IncShkDstn[0]]
        + [IncomeDstn_unemp] * UBspell_normal
        + [IncomeDstn_unemp_nobenefits]
    ]
    base.IncShkDstn_base = base.IncShkDstn

    # HS DiscFac distribution (7 atoms)
    discfac_dstn = DiscFacDstns[1]
    pmv = discfac_dstn.pmv
    atoms = discfac_dstn.atoms[0]
    print()
    print(f"  HS β atoms: {atoms.tolist()}")
    print(f"  HS pmv:     {pmv.tolist()}")

    typelist = []
    for b_idx in range(DiscFacCount):
        agent = deepcopy(base)
        agent.DiscFac = float(atoms[b_idx])
        agent.solve()
        typelist.append(agent)

    return typelist, pmv


@pytest.fixture(scope='module')
def HS_7type():
    """Build + solve 7 HS types (one per β atom). Module-scoped: solve cost paid once."""
    print()
    print(f"  L3c.b2: building + solving 7 HS β-atom types...")
    t0 = time.time()
    typelist, pmv = _build_HS_7beta_typelist()
    print(f"  L3c.b2: 7 types solved in {time.time()-t0:.1f}s")
    return typelist, pmv


def _compute_TM_7beta(typelist, pmv, a_grid_size=200):
    """Aggregate K/Y across 7 β atoms using TM:
        K/Y_pop = Σ pmv[b] · A_nrm_b / Σ pmv[b] · Income_nrm_b
    """
    A_sum = 0.0
    Y_sum = 0.0
    for b_idx, agent in enumerate(typelist):
        tm_data = build_tm_agg_fiscal_a(agent, aCount=a_grid_size, interpretation='CDC')
        ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
        agg = compute_type_aggregates_tm_a(agent, tm_data, ergodic, interpretation='CDC')
        A_sum += pmv[b_idx] * agg['A_nrm']
        Y_sum += pmv[b_idx] * agg['Income_nrm']
    return A_sum / Y_sum if Y_sum > 0 else float('nan')


def _compute_MC_7beta(typelist, pmv, N_total, seed, T_sim=600, T_burnin=400):
    """Run MC on the 7-type ensemble; aggregate K/Y by weighting each type's
    moments by pmv[b].

    N_total is the population agent count; per-type AgentCount = floor(N_total · pmv[b]).
    """
    A_total_weighted = 0.0
    Y_total_weighted = 0.0
    for b_idx, agent_template in enumerate(typelist):
        N_b = int(np.floor(N_total * pmv[b_idx]))
        if N_b == 0:
            continue
        moments = _run_mc_HS_simple(
            agent_template, N=N_b, seed=seed,
            T_sim=T_sim, T_burnin=T_burnin,
        )
        # _run_mc_HS_simple returns mean_aNrm and mean_TranShk (normalized).
        # Population aggregation: weight by pmv[b] (the type's population share).
        A_total_weighted += pmv[b_idx] * moments['mean_aNrm']
        Y_total_weighted += pmv[b_idx] * moments['mean_TranShk']
    return A_total_weighted / Y_total_weighted if Y_total_weighted > 0 else float('nan')


def test_l3c2_HS_7beta_cascade(HS_7type):
    """Escalate N until the unified gate passes (rel_gap ≤ 1% AND rel_SE ≤ 1%)
    OR the test reaches N=125k without passing (HALT)."""
    typelist, pmv = HS_7type

    # TM reference (deterministic; only depends on a-grid)
    print()
    t0 = time.time()
    tm_K = _compute_TM_7beta(typelist, pmv, a_grid_size=200)
    print(f"  L3c.b2 TM-7β  K/Y = {tm_K:.5f}  (a-grid=200; computed in {time.time()-t0:.1f}s)")

    # MC escalation
    n_seeds = 5
    N_schedule = [5000, 10000, 25000, 50000, 125000]
    passed_at = None
    last_mc_mean = None
    last_mc_se = None

    for N in N_schedule:
        t0 = time.time()
        mc_Ks = []
        for s in range(n_seeds):
            mc_Ks.append(_compute_MC_7beta(typelist, pmv, N_total=N, seed=s))
        mc_mean = float(np.mean(mc_Ks))
        mc_se = float(np.std(mc_Ks) / np.sqrt(n_seeds))
        rel_gap = abs(mc_mean - tm_K) / max(abs(mc_mean), 1e-12)
        rel_se = mc_se / max(abs(mc_mean), 1e-12)
        elapsed = time.time() - t0
        last_mc_mean = mc_mean
        last_mc_se = mc_se

        gate_ok = (rel_gap <= 0.01) and (rel_se <= 0.01)
        marker = '✅ GATE PASS' if gate_ok else '─ continuing'
        print(f"  L3c.b2 MC-7β  N={N:>6d}  MC={mc_mean:.5f}  SE={mc_se:.5f}  "
              f"rel_gap={rel_gap:.4%}  rel_SE={rel_se:.4%}  ({elapsed:.0f}s)  {marker}")

        if gate_ok:
            passed_at = N
            break

    print()
    print(f"  L3c.b2 SUMMARY  TM K/Y = {tm_K:.5f}")
    if passed_at is not None:
        print(f"                  Gate passed at N={passed_at}; MC={last_mc_mean:.5f}, SE={last_mc_se:.5f}")
    else:
        print(f"                  Gate NOT passed by N={N_schedule[-1]}; HALT.")

    _assert_cross_method_pass(
        mc_mean=last_mc_mean, mc_se=last_mc_se, tm_value=tm_K,
        eps_gap=0.01, eps_se=0.01,
        label=f'L3c.b2 HS-7β cascade (N={passed_at or N_schedule[-1]}, n_seeds={n_seeds})',
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
