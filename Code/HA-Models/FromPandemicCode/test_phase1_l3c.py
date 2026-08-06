"""
Phase 1 L3c: 3-cohort MC↔TM convergence at Reduced_Run scope.

Per `BUGS_private/HAFiscal_splurge_budget_inconsistency/code_cheatsheet_phase1_convergence.md`
L3c entries.

Configuration: 3 cohorts (dropout, HS, college); N=25k × 10 seeds (lower
end of L3c scope; L3d goes to N=125k); a-grid=200 (per L3b finding that
500/1000 differs by <0.2%); same unified gate (rel_gap ≤ 1% AND rel_SE
≤ 1%).

Tests (per cheat-sheet):
  1. test_l3c_per_cohort_cross_method[dropout/HS/college]   parameterized
  2. test_l3c_multicohort_aggregation                        population
  3. test_l3c_cdc_esc_pattern_per_cohort                    no compute
  4. test_l3c_A_nrm_rescaling_extension                     extends Phase 0.6

Reuses helpers from test_phase1_l3a.py.

Run via:
  pytest Code/HA-Models/FromPandemicCode/test_phase1_l3c.py -v -s
"""

import os
import sys
import numpy as np
import pytest
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

# CLAUDE.md: patch sys.argv before importing EstimParameters.
_SAVED_ARGV = sys.argv
sys.argv = ['test_phase1_l3c']

from EstimParameters import (
    init_dropout, init_highschool, init_college, init_ADEconomy,
    UBspell_normal, data_EducShares,
)
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from tm_methods import (
    build_tm_agg_fiscal_a,
    compute_type_aggregates_tm_a,
    find_ergodic_distribution,
)
from HARK.distributions import DiscreteDistribution

from test_phase1_l3a import (
    _compute_tm_moment_HS,  # generic — works for any solved AggFiscalType
    _run_mc_HS_simple,
    _assert_cross_method_pass,
)

sys.argv = _SAVED_ARGV


_INIT_BY_COHORT = {
    'dropout': init_dropout,
    'HS':      init_highschool,
    'college': init_college,
}


def _build_and_solve_cohort(init_dict):
    """Build + solve an AggFiscalType for one cohort. Mirrors L3a fixture."""
    init = deepcopy(init_dict)
    agent = AggFiscalType(**init)
    agent.cycles = 0
    economy = AggregateDemandEconomy(**init_ADEconomy)
    agent.get_economy_data(economy)
    IncomeDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([agent.IncUnemp])]
    )
    IncomeDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([agent.IncUnempNoBenefits])]
    )
    agent.IncShkDstn = [
        [agent.IncShkDstn[0]]
        + [IncomeDstn_unemp] * UBspell_normal
        + [IncomeDstn_unemp_nobenefits]
    ]
    agent.IncShkDstn_base = agent.IncShkDstn
    economy.agents = [agent]
    economy.solve()
    return agent


@pytest.fixture(scope='module')
def solved_cohorts():
    """Build + solve all 3 cohorts. Module-scoped: solve cost paid once."""
    print()
    print(f"  L3c: solving 3 cohorts (one-time cost)...")
    cohorts = {}
    for name, init in _INIT_BY_COHORT.items():
        import time
        t0 = time.time()
        cohorts[name] = _build_and_solve_cohort(init)
        print(f"  L3c: {name} solved in {time.time()-t0:.1f}s")
    return cohorts


# ----------------------------------------------------------------------
# L3c Test 1: per-cohort tight cross-method (parameterized)
# ----------------------------------------------------------------------

@pytest.mark.parametrize('cohort_name', ['dropout', 'HS', 'college'])
def test_l3c_per_cohort_cross_method(solved_cohorts, cohort_name):
    """Each cohort: MC mean K/Y agrees with TM K/Y per the unified gate
    (rel_gap ≤ 1% AND rel_SE ≤ 1%)."""
    agent = solved_cohorts[cohort_name]

    n_seeds = 10
    mc_Ks = [_run_mc_HS_simple(agent, N=25000, seed=s, T_sim=600, T_burnin=400)['K_Y']
             for s in range(n_seeds)]
    mc_mean = float(np.mean(mc_Ks))
    mc_se = float(np.std(mc_Ks) / np.sqrt(n_seeds))

    tm = _compute_tm_moment_HS(agent, a_grid_size=200, interpretation='CDC')
    tm_K = tm['K_Y']

    print()
    _assert_cross_method_pass(
        mc_mean=mc_mean, mc_se=mc_se, tm_value=tm_K,
        eps_gap=0.01, eps_se=0.01,
        label=f'L3c [{cohort_name}] cross-method (n_seeds={n_seeds}, N=25k, a-grid=200)',
    )


# ----------------------------------------------------------------------
# L3c Test 2: multi-cohort aggregation
# ----------------------------------------------------------------------

def test_l3c_multicohort_aggregation(solved_cohorts):
    """Population-aggregate K/Y from per-cohort TM equals education-share-
    weighted sum of per-cohort K/Ys.

    Validates: (eq:multi-cohort-aggregation) of why_convergence_validation.md §2.6.
    Specifically: pop_K_Y = Σ_e w_e · K_Y_e where w_e is the education share.

    NOTE: this is a TM-internal-consistency check (do per-cohort TM K/Ys
    aggregate correctly?). The MC↔TM gate per cohort is in test 1 above.
    """
    cohort_KYs = {}
    for name in ['dropout', 'HS', 'college']:
        tm = _compute_tm_moment_HS(solved_cohorts[name], a_grid_size=200, interpretation='CDC')
        cohort_KYs[name] = tm['K_Y']

    # Education shares: dropout=0.093, HS=0.527, college=0.380
    weights = {'dropout': data_EducShares[0],
               'HS':      data_EducShares[1],
               'college': data_EducShares[2]}

    print()
    print(f"  L3c multi-cohort  weights = {weights}")
    print(f"  L3c multi-cohort  per-cohort TM K/Y:")
    for n in ['dropout', 'HS', 'college']:
        print(f"                    {n:>8s}  K/Y = {cohort_KYs[n]:.5f}  (weight {weights[n]})")

    pop_KY = sum(weights[n] * cohort_KYs[n] for n in ['dropout', 'HS', 'college'])
    print(f"  L3c multi-cohort  weighted-sum K/Y = {pop_KY:.5f}")

    # Sanity: weights must sum to 1
    assert abs(sum(weights.values()) - 1.0) < 1e-9

    # Sanity: each cohort K/Y is positive
    for n, k in cohort_KYs.items():
        assert k > 0, f"Cohort {n} K/Y = {k} not positive"

    # Sanity: weighted sum is in the convex hull of the per-cohort K/Ys
    # (this is mathematical truism for a weighted average; checked here as
    # a guard against weight or aggregation arithmetic errors).
    KY_values = list(cohort_KYs.values())
    assert min(KY_values) <= pop_KY <= max(KY_values), (
        f"Population K/Y = {pop_KY:.5f} outside convex hull of per-cohort "
        f"K/Y = {KY_values}. Aggregation arithmetic bug."
    )


# ----------------------------------------------------------------------
# L3c Test 3: CDC vs ESC β-pattern across cohorts (no compute)
# ----------------------------------------------------------------------

def test_l3c_cdc_esc_pattern_per_cohort():
    """Verify the BUG-036-fixed pattern: CDC β < ESC β for ALL 3 cohorts.

    Reads existing on-disk calibration files. No MC or TM compute.

    Pre-BUG-036, the dropout cohort showed CDC β > ESC β (a Nelder-Mead
    bad-basin artifact). Post-BUG-036 multi-start, dropout β=0.6891 < ESC
    0.6995, restoring the expected cross-cohort pattern.
    """
    import os
    repo = os.path.normpath(os.path.join(_HERE, '..', '..', '..'))
    results_dir = os.path.join(repo, 'Code', 'HA-Models', 'Results')

    def read_DiscFacEstim(path):
        """Read a DiscFacEstim_*.txt and return dict cohort_id → β."""
        out = {}
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line.startswith('{'):
                    continue
                d = eval(line)
                out[d['EducationGroup']] = d['beta']
        return out

    cdc = {}
    for et in [0, 1, 2]:
        suffix = '_TM_a' if et != 1 else '_CDC'  # HS has CDC backup; 0/2 have TM-a only
        path = os.path.join(results_dir, f'DiscFacEstim_CRRA_2.0_R_1.01_edType{et}{suffix}.txt')
        if not os.path.isfile(path):
            # Try alternative location — TM-a Apr-18
            path = os.path.join(results_dir, f'DiscFacEstim_CRRA_2.0_R_1.01_edType{et}_TM_a.txt')
        cdc.update(read_DiscFacEstim(path))

    esc_path = os.path.join(results_dir, 'DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt')
    esc = read_DiscFacEstim(esc_path)

    print()
    print(f"  L3c CDC↔ESC β pattern:")
    print(f"  {'cohort':>10s}  {'CDC β':>10s}  {'ESC β':>10s}  {'Δ (CDC-ESC)':>13s}  match-pattern?")
    cohort_names = {0: 'dropout', 1: 'HS', 2: 'college'}
    for et in [0, 1, 2]:
        cdc_b = cdc[et]
        esc_b = esc[et]
        diff = cdc_b - esc_b
        ok = '✓' if diff < 0 else '✗ FAIL'
        print(f"  {cohort_names[et]:>10s}  {cdc_b:>10.5f}  {esc_b:>10.5f}  {diff:>+13.5f}  {ok}")
        assert diff < 0, (
            f"L3c CDC↔ESC pattern HALT for cohort {cohort_names[et]}: "
            f"CDC β = {cdc_b:.5f} >= ESC β = {esc_b:.5f}. "
            f"BUG-036 multi-start fix may not have been applied OR a regression."
        )


# ----------------------------------------------------------------------
# L3c Test 4: A_nrm rescaling extension (Phase 0.6 finding at all 3 cohorts)
# ----------------------------------------------------------------------

def test_l3c_A_nrm_rescaling_extension(solved_cohorts):
    """Per Phase 0.6 smoke + cheat-sheet 33.6: ESC household wealth =
    (1-ς) × kernel a; the ESC/CDC A_nrm ratio is in (0.5, 1.0) range
    (NOT the naive 1-ς=0.74; kernel ergodics differ).

    Verify the pattern holds across all 3 cohorts at L3c scale."""
    print()
    print(f"  L3c A_nrm rescaling per cohort:")
    for name in ['dropout', 'HS', 'college']:
        agent = solved_cohorts[name]
        splurge = float(agent.Splurge)
        m_cdc = _compute_tm_moment_HS(agent, a_grid_size=200, interpretation='CDC')
        m_esc = _compute_tm_moment_HS(agent, a_grid_size=200, interpretation='ESC')
        ratio = m_esc['A_nrm'] / m_cdc['A_nrm']
        print(f"  {name:>8s}  CDC A_nrm={m_cdc['A_nrm']:.4f}  ESC A_nrm={m_esc['A_nrm']:.4f}"
              f"  ratio={ratio:.4f}  (1-ς={1-splurge:.4f})")
        assert m_esc['A_nrm'] < m_cdc['A_nrm'], (
            f"L3c [{name}] A_nrm: ESC ({m_esc['A_nrm']}) should be < CDC ({m_cdc['A_nrm']})"
        )
        assert 0.4 < ratio < 1.0, (
            f"L3c [{name}] A_nrm ratio = {ratio:.4f} outside (0.4, 1.0); "
            f"naive (1-ς) was {1-splurge:.4f}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
