"""
Phase 0.6 smoke test: TM-a ESC kernel end-to-end via direct invocation.

Builds an AggFiscalType using the real init_dropout/init_highschool/
init_college dicts from EstimParameters, solves the agent, then calls the
TM-a chain (build_tm_agg_fiscal_a → ergodic → compute_type_aggregates_tm_a)
under both CDC (default) and ESC interpretations.

Verifies:
  1. No crash under either interpretation.
  2. Outputs are finite and physically reasonable (positive A_nrm, etc.).
  3. CDC vs ESC differences are in the expected direction (lower A_nrm
     under ESC by factor (1-ς), per cheat-sheet 33.6 implementation).
  4. The CDC-vs-ESC kernel TMs are not byte-identical (confirms the
     interpretation parameter actually flows through).
  5. The Splurge=0 sanity: under Splurge=0, CDC and ESC must give
     identical aggregates (the (1-ς) factor becomes 1).

This test does NOT exercise:
  - The full production pipeline (Simulate.py / AggFiscalMAIN_reduced.py /
    propagate_experiment_tm_a). Since this was written, the kernel
    `interpretation` threading LANDED via BUG-051 (2026-06-05) and the
    a-indexed production wiring is governed by
    plans/20260610_post_merge_canonicalize_default_solution.md (do_all
    Step-5a a-indexed, 2026-06-11) — but the production Simulate.py dispatch
    itself remains interpretation-independent (it propagates only the
    `tm_a_indexed` flag; kernels read the agent attribute).
  - Phase 1 convergence (MC↔TM) — that's the sub-plan deliverable.

Setup uses Highschool init (smaller than dropout, faster solve). Total
runtime: ~30-60 sec (dominated by the agent solve).
"""

import os
import sys
import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

# CLAUDE.md: patch sys.argv before importing EstimParameters.
_SAVED_ARGV = sys.argv
sys.argv = ['test_esc_tm_kernel_smoke']

from copy import deepcopy
from EstimParameters import (
    init_highschool, init_ADEconomy, UBspell_normal,
)
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from tm_methods import (
    build_tm_agg_fiscal_a,
    compute_type_aggregates_tm_a,
    find_ergodic_distribution,
)
from HARK.distributions import DiscreteDistribution

sys.argv = _SAVED_ARGV


# Module-level fixture: build the agent once (slow), then run multiple tests.
# Pytest scope='module' means the agent is shared across all tests in this
# file but the AggFiscalType solve only happens once.

@pytest.fixture(scope='module')
def solved_agent():
    """Build + solve a Highschool AggFiscalType. Used by all tests below."""
    init = deepcopy(init_highschool)
    agent = AggFiscalType(**init)
    agent.cycles = 0
    economy = AggregateDemandEconomy(**init_ADEconomy)
    agent.get_economy_data(economy)

    # Replicate the IncShkDstn setup that estim_phase2_tm_a.py does.
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


def _run_kernel_chain(agent, interpretation):
    """Build TM, solve ergodic, compute aggregates under given interpretation."""
    # BUG-051 matched-pair fix: callers exercise this helper with both 'CDC'
    # and 'ESC' explicitly within one process. build_tm_agg_fiscal_a validates
    # its explicit interpretation against HAFISCAL_INTERPRETATION, so set the
    # env to match THIS arm before the kernel calls and restore the prior value
    # in a finally so arms don't leak into each other. The guard is NOT
    # weakened. (No monkeypatch fixture is in scope here, so use os.environ +
    # finally restore.)
    _prev_interp = os.environ.get('HAFISCAL_INTERPRETATION')
    os.environ['HAFISCAL_INTERPRETATION'] = interpretation
    try:
        tm_data = build_tm_agg_fiscal_a(
            agent, aCount=80, interpretation=interpretation,
        )
        ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
        aggregates = compute_type_aggregates_tm_a(
            agent, tm_data, ergodic, interpretation=interpretation,
        )
    finally:
        if _prev_interp is None:
            os.environ.pop('HAFISCAL_INTERPRETATION', None)
        else:
            os.environ['HAFISCAL_INTERPRETATION'] = _prev_interp
    return tm_data, ergodic, aggregates


# -----------------------------------------------------------------------
# Smoke tests
# -----------------------------------------------------------------------

def test_smoke_CDC_runs_without_crash(solved_agent):
    """CDC chain runs end-to-end and returns finite outputs."""
    tm_data, ergodic, agg = _run_kernel_chain(solved_agent, interpretation='CDC')

    assert tm_data['TranMatrix'].shape[0] > 0, "TM is empty"
    assert np.isfinite(ergodic).all(), "Ergodic has NaN/Inf"
    assert abs(ergodic.sum() - 1.0) < 1e-6, f"Ergodic doesn't sum to 1: {ergodic.sum()}"
    for k, v in agg.items():
        if isinstance(v, (int, float)):
            assert np.isfinite(v), f"Aggregate {k} = {v} not finite"
    assert agg['A_nrm'] > 0, f"A_nrm should be positive, got {agg['A_nrm']}"
    assert agg['C_splurge_nrm'] > 0, f"C_splurge_nrm should be positive, got {agg['C_splurge_nrm']}"
    assert agg['Income_nrm'] > 0, f"Income_nrm should be positive, got {agg['Income_nrm']}"


def test_smoke_ESC_runs_without_crash(solved_agent):
    """ESC chain runs end-to-end and returns finite outputs."""
    tm_data, ergodic, agg = _run_kernel_chain(solved_agent, interpretation='ESC')

    assert tm_data['TranMatrix'].shape[0] > 0
    assert np.isfinite(ergodic).all()
    assert abs(ergodic.sum() - 1.0) < 1e-6
    for k, v in agg.items():
        if isinstance(v, (int, float)):
            assert np.isfinite(v), f"ESC aggregate {k} = {v} not finite"
    assert agg['A_nrm'] > 0, f"ESC A_nrm should be positive, got {agg['A_nrm']}"
    assert agg['C_splurge_nrm'] > 0
    assert agg['Income_nrm'] > 0


def test_smoke_ESC_A_nrm_lower_than_CDC_by_one_minus_splurge(solved_agent):
    """Per cheat-sheet 33.6: ESC A_nrm = (1-ς) * CDC A_nrm.

    This is THE structural difference 33.6 introduces between the two
    interpretations. Note: this checks that the (1-ς) rescaling happens
    inside compute_type_aggregates_tm_a; the underlying TM ergodic
    distributions may differ, since the kernels evolve assets differently
    under each interpretation. So we don't expect A_nrm_ESC = (1-ς)*A_nrm_CDC
    EXACTLY (the underlying ergodic differs); we expect the qualitative
    result that A_nrm_ESC < A_nrm_CDC by approximately the (1-ς) factor."""
    Splurge = float(solved_agent.Splurge)

    _, _, agg_cdc = _run_kernel_chain(solved_agent, interpretation='CDC')
    _, _, agg_esc = _run_kernel_chain(solved_agent, interpretation='ESC')

    assert agg_esc['A_nrm'] < agg_cdc['A_nrm'], (
        f"ESC A_nrm ({agg_esc['A_nrm']:.4f}) should be lower than CDC A_nrm "
        f"({agg_cdc['A_nrm']:.4f}) since ESC household wealth = (1-ς)·a_opt"
    )

    # Ratio should be in plausible range. Strict (1-ς) holds only when
    # ergodic E[a] is the same — but here the kernels evolve a differently
    # (CDC: drains splurger from a; ESC: doesn't), so E[a_ESC] > E[a_CDC]
    # at the kernel level; then ESC multiplies by (1-ς) to get household
    # wealth. Net result: A_nrm_ESC could be roughly comparable in magnitude
    # to A_nrm_CDC, depending on how much the kernel-level E[a] increases
    # under ESC. Just verify ratio is in 'sane' range — say between 0.5
    # and 1.0 (i.e., ESC household wealth is somewhat smaller but not
    # vanishing).
    ratio = agg_esc['A_nrm'] / agg_cdc['A_nrm']
    assert 0.5 < ratio < 1.0, (
        f"A_nrm_ESC / A_nrm_CDC = {ratio:.4f} should be in (0.5, 1.0); "
        f"check whether the (1-ς) ESC factor is being applied correctly "
        f"and how much the underlying ergodic shifts between interpretations"
    )


def test_smoke_TMs_differ_between_CDC_and_ESC(solved_agent):
    """Confirm interpretation parameter actually flows to the kernel
    (TMs must differ at Splurge > 0)."""
    tm_cdc, _, _ = _run_kernel_chain(solved_agent, interpretation='CDC')
    tm_esc, _, _ = _run_kernel_chain(solved_agent, interpretation='ESC')

    diff = (tm_cdc['TranMatrix'] - tm_esc['TranMatrix']).toarray()
    max_diff = np.max(np.abs(diff))
    assert max_diff > 1e-6, (
        f"At Splurge>0, CDC and ESC TMs must differ. max diff = {max_diff}. "
        f"If equal, the interpretation parameter is not threading correctly."
    )


def test_smoke_Splurge_zero_makes_CDC_and_ESC_aggregates_match(solved_agent):
    """At Splurge=0, the (1-ς) factor becomes 1 AND the CDC c_actual blending
    reduces to c*(m), making CDC and ESC kernels analytically equivalent.
    So the aggregates should match exactly."""
    # Save original Splurge and override to 0
    original_splurge = solved_agent.Splurge
    solved_agent.Splurge = 0.0
    try:
        _, _, agg_cdc = _run_kernel_chain(solved_agent, interpretation='CDC')
        _, _, agg_esc = _run_kernel_chain(solved_agent, interpretation='ESC')

        for k in ('A_nrm', 'C_nrm', 'C_splurge_nrm', 'Income_nrm'):
            cdc_v = agg_cdc[k]
            esc_v = agg_esc[k]
            assert abs(cdc_v - esc_v) < 1e-10 * max(abs(cdc_v), 1.0), (
                f"At Splurge=0, {k} should match: CDC={cdc_v}, ESC={esc_v}"
            )
    finally:
        solved_agent.Splurge = original_splurge


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
