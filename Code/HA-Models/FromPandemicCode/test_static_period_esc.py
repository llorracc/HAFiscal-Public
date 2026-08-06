"""
Unit tests for the ESC interpretation branches of the static-period ESC
stack: build_tm_agg_fiscal_a (33.5), compute_type_aggregates_tm_a (33.6),
compute_period_aggregates_tm_a (33.7).

Per Phase 0.3 of plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md.

Tests:

  1. test_invalid_interpretation_raises_in_aggregator
     - compute_type_aggregates_tm_a with interpretation='FOO' raises.
  2. test_invalid_interpretation_raises_in_period_aggregator
     - compute_period_aggregates_tm_a with interpretation='FOO' raises.

  3. test_aggregator_default_interpretation_is_CDC
     - Omitting `interpretation` in compute_type_aggregates_tm_a gives
       the same result as interpretation='CDC' (regression check).

  4. test_period_aggregator_default_interpretation_is_CDC
     - Same regression check for compute_period_aggregates_tm_a.

  5. test_aggregator_A_nrm_rescaling_under_ESC
     - A_nrm under ESC = (1-Splurge) * A_nrm under CDC, holding all other
       inputs fixed. This is the only numerical difference 33.6 introduces
       between the two interpretations (per cheat-sheet 33.6 spec).

  6. test_period_aggregator_C_splurge_nrm_interpretation_shared
     - C_splurge_nrm formula (1-ς)*c* + ς*xi is interpretation-shared per
       the cheat-sheet 33.7 verification note. Verify that the function's
       numerical output is identical for CDC and ESC (since the formula
       is shared and there's no A_nrm in the period aggregator).

This file does NOT test build_tm_agg_fiscal_a directly (it's mostly a
dispatch wrapper around _build_period_tm_a, which is tested in
test_build_period_tm_a_esc.py); the threading of `interpretation`
through it is exercised indirectly here via test 5.

Run via: pytest Code/HA-Models/FromPandemicCode/test_static_period_esc.py
"""

import os
import sys
import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from tm_methods import (
    _build_period_tm_a,
    _make_newborn_dist_a,
    _solve_markov_ergodic,
    compute_type_aggregates_tm_a,
    compute_period_aggregates_tm_a,
)
from HARK.distributions import DiscreteDistribution


def _make_minimal_kernel_inputs():
    """Reusable: minimal valid input set for kernel calls. J=1."""
    A = 8
    dist_aGrid = np.array([0.0, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0])

    def cfunc_half(m_flat, Cratio_flat):
        return 0.5 * m_flat
    cFuncs = [cfunc_half]

    pmv = np.array([0.25, 0.5, 0.25])
    psi = np.array([0.9, 1.0, 1.1])
    xi = np.array([0.5, 1.0, 1.5])
    IncShkDstn_list = [DiscreteDistribution(pmv, [psi, xi])]

    micro_trans = np.array([[1.0]])
    Rfree_arr = np.array([1.04])
    PermGroFac_arr = np.array([1.0])
    LivPrb_arr = np.array([0.99])

    NewBornDist = np.zeros(A)
    NewBornDist[0] = 1.0

    return dict(
        dist_aGrid=dist_aGrid, cFuncs=cFuncs,
        IncShkDstn_list=IncShkDstn_list,
        micro_trans=micro_trans,
        Rfree_arr=Rfree_arr, PermGroFac_arr=PermGroFac_arr,
        LivPrb_arr=LivPrb_arr, NewBornDist=NewBornDist,
    )


class _MinimalAgent:
    """Minimal fake agent compatible with compute_type_aggregates_tm_a's
    attribute requirements. Avoids the heavy AggFiscalType setup."""
    def __init__(self, MrkvArray, Splurge, Rfree, PermGroFac, sol):
        self.MrkvArray = [MrkvArray]
        self.Splurge = Splurge
        self.Rfree = Rfree
        self.PermGroFac = [PermGroFac]
        self.solution = [sol]


class _MinimalSolution:
    def __init__(self, cFuncs):
        self.cFunc = cFuncs


def _build_minimal_tm_data(Splurge, interpretation='CDC'):
    """Build a minimal tm_data dict that compute_type_aggregates_tm_a expects.
    Returns (tm_data, ergodic_distr, agent)."""
    inputs = _make_minimal_kernel_inputs()
    TM = _build_period_tm_a(
        Splurge=Splurge, **inputs, interpretation=interpretation,
    )

    # Find ergodic distribution (column-stochastic TM; ergodic is left eig of TM with eigval=1).
    # Equivalently, right eig of TM with eigval=1.
    A = len(inputs['dist_aGrid'])
    J = inputs['micro_trans'].shape[0]
    N = A * J

    # Power iteration
    p = np.ones(N) / N
    for _ in range(2000):
        p_new = TM @ p
        p_new = p_new / p_new.sum()
        if np.max(np.abs(p_new - p)) < 1e-12:
            break
        p = p_new

    tm_data = {
        'TranMatrix': TM,
        'dist_aGrid': inputs['dist_aGrid'],
        'markov_ergodic': np.array([1.0]),
        'aMax': inputs['dist_aGrid'][-1],
        'IncShkDstn_list': inputs['IncShkDstn_list'],
        'Cratio': 1.0,
    }

    sol = _MinimalSolution(inputs['cFuncs'])
    agent = _MinimalAgent(
        MrkvArray=inputs['micro_trans'],
        Splurge=Splurge,
        Rfree=inputs['Rfree_arr'].tolist(),
        PermGroFac=inputs['PermGroFac_arr'].tolist(),
        sol=sol,
    )

    return tm_data, p, agent


# -----------------------------------------------------------------------
# Tests for compute_type_aggregates_tm_a (33.6)
# -----------------------------------------------------------------------

def test_invalid_interpretation_raises_in_aggregator():
    """compute_type_aggregates_tm_a with bogus interpretation raises ValueError."""
    tm_data, ergodic, agent = _build_minimal_tm_data(Splurge=0.25)
    with pytest.raises(ValueError, match="interpretation must be 'CDC' or 'ESC'"):
        compute_type_aggregates_tm_a(agent, tm_data, ergodic, interpretation='FOO')


def test_aggregator_default_interpretation_is_CDC():
    """Omitting `interpretation` in compute_type_aggregates_tm_a gives the
    same result as interpretation='CDC' explicitly."""
    tm_data, ergodic, agent = _build_minimal_tm_data(Splurge=0.25)

    res_default = compute_type_aggregates_tm_a(agent, tm_data, ergodic)
    res_explicit_cdc = compute_type_aggregates_tm_a(
        agent, tm_data, ergodic, interpretation='CDC'
    )
    for k in ('C_nrm', 'A_nrm', 'C_splurge_nrm', 'Income_nrm'):
        assert abs(res_default[k] - res_explicit_cdc[k]) < 1e-15, \
            f"Key {k}: default={res_default[k]}, explicit CDC={res_explicit_cdc[k]}"


def test_aggregator_A_nrm_rescaling_under_ESC():
    """A_nrm under ESC must equal (1-ς) * A_nrm under CDC, holding all other
    inputs fixed (since the kernel a-grid is the same under both, only the
    semantic interpretation of household wealth differs).

    Per cheat-sheet 33.6: under ESC, household wealth = (1-ς)·E[a_opt] per
    (eq:assets-ESC) + (eq:conv1-ESC). Under CDC, household wealth = E[a_tot].
    The kernel computes E[a] in both cases; the function applies the (1-ς)
    factor for ESC."""
    Splurge = 0.25
    tm_data, ergodic, agent = _build_minimal_tm_data(Splurge=Splurge)

    res_cdc = compute_type_aggregates_tm_a(
        agent, tm_data, ergodic, interpretation='CDC'
    )
    res_esc = compute_type_aggregates_tm_a(
        agent, tm_data, ergodic, interpretation='ESC'
    )

    expected_esc_A = (1.0 - Splurge) * res_cdc['A_nrm']
    assert abs(res_esc['A_nrm'] - expected_esc_A) < 1e-15, (
        f"ESC A_nrm should be (1-ς)·CDC A_nrm = {expected_esc_A:.10f}, "
        f"got {res_esc['A_nrm']:.10f}"
    )
    # Other aggregates are interpretation-shared: should match CDC exactly
    for k in ('C_nrm', 'C_splurge_nrm', 'Income_nrm'):
        assert abs(res_cdc[k] - res_esc[k]) < 1e-15, \
            f"{k} should be interpretation-shared: CDC={res_cdc[k]}, ESC={res_esc[k]}"


def test_aggregator_A_nrm_equal_at_splurge_zero():
    """At Splurge=0, the (1-ς) factor becomes 1, so ESC A_nrm should equal
    CDC A_nrm exactly. This is the analytical-symmetry sanity check from
    why_TM_a_kernel.md §10 debugging guide #6 applied to the aggregator."""
    tm_data, ergodic, agent = _build_minimal_tm_data(Splurge=0.0)

    res_cdc = compute_type_aggregates_tm_a(
        agent, tm_data, ergodic, interpretation='CDC'
    )
    res_esc = compute_type_aggregates_tm_a(
        agent, tm_data, ergodic, interpretation='ESC'
    )
    assert abs(res_esc['A_nrm'] - res_cdc['A_nrm']) < 1e-15, \
        f"At Splurge=0, ESC A_nrm should equal CDC A_nrm"


# -----------------------------------------------------------------------
# Tests for compute_period_aggregates_tm_a (33.7)
# -----------------------------------------------------------------------

def test_invalid_interpretation_raises_in_period_aggregator():
    """compute_period_aggregates_tm_a with bogus interpretation raises."""
    inputs = _make_minimal_kernel_inputs()
    A = len(inputs['dist_aGrid'])
    J = inputs['micro_trans'].shape[0]
    dist = np.ones(A * J) / (A * J)

    with pytest.raises(ValueError, match="interpretation must be 'CDC' or 'ESC'"):
        compute_period_aggregates_tm_a(
            dist=dist, dist_aGrid=inputs['dist_aGrid'],
            cFuncs=inputs['cFuncs'],
            IncShkDstn_list=inputs['IncShkDstn_list'],
            micro_trans=inputs['micro_trans'],
            Rfree_arr=inputs['Rfree_arr'],
            PermGroFac_arr=inputs['PermGroFac_arr'],
            Splurge=0.25, interpretation='FOO',
        )


def test_period_aggregator_default_interpretation_is_CDC():
    """Omitting `interpretation` in compute_period_aggregates_tm_a gives the
    same result as interpretation='CDC' explicitly."""
    inputs = _make_minimal_kernel_inputs()
    A = len(inputs['dist_aGrid'])
    J = inputs['micro_trans'].shape[0]
    dist = np.ones(A * J) / (A * J)

    common = dict(
        dist=dist, dist_aGrid=inputs['dist_aGrid'],
        cFuncs=inputs['cFuncs'],
        IncShkDstn_list=inputs['IncShkDstn_list'],
        micro_trans=inputs['micro_trans'],
        Rfree_arr=inputs['Rfree_arr'],
        PermGroFac_arr=inputs['PermGroFac_arr'],
        Splurge=0.25,
    )
    res_default = compute_period_aggregates_tm_a(**common)
    res_explicit_cdc = compute_period_aggregates_tm_a(**common, interpretation='CDC')
    for k in ('C_nrm', 'C_splurge_nrm', 'Income_nrm'):
        assert abs(res_default[k] - res_explicit_cdc[k]) < 1e-15, \
            f"Key {k} differs: default={res_default[k]}, explicit CDC={res_explicit_cdc[k]}"


def test_period_aggregator_C_splurge_nrm_interpretation_shared():
    """The c_actual formula (1-ς)*c* + ς*xi_eff is interpretation-shared
    NUMERICALLY (per cheat-sheet 33.7 verification note: under CDC it
    represents household-bargain consumption; under ESC it represents the
    sum of optimizer c*(m_opt) and splurger ς*xi from separate ledgers;
    same numerical value either way).

    Verify: compute_period_aggregates_tm_a returns identical C_nrm,
    C_splurge_nrm, Income_nrm for CDC and ESC."""
    inputs = _make_minimal_kernel_inputs()
    A = len(inputs['dist_aGrid'])
    J = inputs['micro_trans'].shape[0]
    dist = np.ones(A * J) / (A * J)

    common = dict(
        dist=dist, dist_aGrid=inputs['dist_aGrid'],
        cFuncs=inputs['cFuncs'],
        IncShkDstn_list=inputs['IncShkDstn_list'],
        micro_trans=inputs['micro_trans'],
        Rfree_arr=inputs['Rfree_arr'],
        PermGroFac_arr=inputs['PermGroFac_arr'],
        Splurge=0.25,
    )
    res_cdc = compute_period_aggregates_tm_a(**common, interpretation='CDC')
    res_esc = compute_period_aggregates_tm_a(**common, interpretation='ESC')

    for k in ('C_nrm', 'C_splurge_nrm', 'Income_nrm'):
        assert abs(res_cdc[k] - res_esc[k]) < 1e-15, \
            f"{k} should be interpretation-shared: CDC={res_cdc[k]}, ESC={res_esc[k]}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
