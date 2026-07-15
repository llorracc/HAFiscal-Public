"""
Unit tests for the ESC interpretation parameter on the experiment stack:
build_experiment_period_tm_a (33.8) and propagate_experiment_tm_a (33.9).

Per Phase 0.4 of plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md.

Scope (per cheat-sheet 33.8 / 33.9):
- 33.8 is mostly a dispatch wrapper around _build_period_tm_a; the only
  ESC-specific change is threading the `interpretation` parameter to the
  kernel call.
- 33.9 contains no interpretation-specific arithmetic of its own (per
  cheat-sheet, the (eq:check-level-decomp) formula is interpretation-
  shared by construction). The ESC change is threading `interpretation`
  through to the 5 internal calls to 33.8 and 33.7.

Tests at the unit level focus on the parameter validation and threading.
End-to-end behavior validation requires a full agent + economy setup
and is deferred to Phase 0.6 (smoke) and Phase 1 (convergence).

Tests:
  1. test_experiment_period_tm_a_invalid_interpretation_via_kernel
     - When 33.8 is called with interpretation='FOO', the underlying
       _build_period_tm_a raises ValueError (the validation in 33.4
       catches it; we just verify the parameter threads correctly).
  2. test_experiment_period_tm_a_default_interpretation_is_CDC
     - Default behavior matches explicit CDC (regression check that
       33.8's signature change didn't break callers).
  3. test_propagate_experiment_tm_a_invalid_interpretation_raises
     - 33.9 has its own front-line validation; verify it raises.

Run via: pytest Code/HA-Models/FromPandemicCode/test_experiment_stack_esc.py
"""

import os
import sys
import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from tm_methods import (
    build_experiment_period_tm_a,
    propagate_experiment_tm_a,
)
from HARK.distributions import DiscreteDistribution


class _MinimalExperimentAgent:
    """Minimal fake agent compatible with build_experiment_period_tm_a's
    attribute requirements. Single macro state, single micro state."""
    def __init__(self):
        # J_micro = 1, single macro state
        self.num_base_MrkvStates = 1

        def cfunc_half(m_flat, Cratio_flat):
            return 0.5 * m_flat

        class _Sol:
            cFunc = [cfunc_half]
        self.solution = [_Sol()]

        # Single macro state: 1 cFunc, 1 IncShkDstn, 1 CondMrkvArray
        pmv = np.array([1.0])
        psi = np.array([1.0])
        xi = np.array([1.0])
        self.IncShkDstn = [[DiscreteDistribution(pmv, [psi, xi])]]
        self.CondMrkvArrays = [np.array([[1.0]])]

        self.Rfree = [1.04]
        self.PermGroFac = [[1.0]]
        self.LivPrb = [[0.99]]
        self.T_age = None
        self.Splurge = 0.25


def test_experiment_period_tm_a_invalid_interpretation_via_kernel():
    """build_experiment_period_tm_a passes `interpretation` to
    _build_period_tm_a; an invalid value should ultimately raise ValueError
    (caught by 33.4's validation when the kernel call fires)."""
    agent = _MinimalExperimentAgent()
    dist_aGrid = np.array([0.0, 1.0, 2.0, 4.0])

    with pytest.raises(ValueError, match="interpretation must be 'CDC' or 'ESC'"):
        build_experiment_period_tm_a(
            agent, macro_curr=0, dist_aGrid=dist_aGrid,
            interpretation='FOO',
        )


def test_experiment_period_tm_a_default_interpretation_is_CDC():
    """Omitting the `interpretation` kwarg should give byte-identical TM
    to interpretation='CDC' explicitly (regression check)."""
    agent = _MinimalExperimentAgent()
    dist_aGrid = np.array([0.0, 1.0, 2.0, 4.0, 8.0])

    TM_default, _, _ = build_experiment_period_tm_a(
        agent, macro_curr=0, dist_aGrid=dist_aGrid,
    )
    TM_explicit_cdc, _, _ = build_experiment_period_tm_a(
        agent, macro_curr=0, dist_aGrid=dist_aGrid,
        interpretation='CDC',
    )
    diff = (TM_default - TM_explicit_cdc).toarray()
    assert np.max(np.abs(diff)) < 1e-15


def test_experiment_period_tm_a_esc_differs_from_cdc():
    """With Splurge > 0, ESC should produce a different TM from CDC
    (since the asset rule differs). This indirectly verifies that the
    `interpretation` parameter actually threads through to the kernel
    rather than being silently ignored."""
    agent = _MinimalExperimentAgent()
    dist_aGrid = np.array([0.0, 1.0, 2.0, 4.0, 8.0])

    TM_cdc, _, _ = build_experiment_period_tm_a(
        agent, macro_curr=0, dist_aGrid=dist_aGrid,
        interpretation='CDC',
    )
    TM_esc, _, _ = build_experiment_period_tm_a(
        agent, macro_curr=0, dist_aGrid=dist_aGrid,
        interpretation='ESC',
    )
    diff = (TM_cdc - TM_esc).toarray()
    assert np.max(np.abs(diff)) > 1e-6, (
        "Splurge=0.25, ESC and CDC TMs must differ. If equal, the "
        "interpretation parameter may not be threading to the kernel."
    )


def test_propagate_experiment_tm_a_invalid_interpretation_raises():
    """propagate_experiment_tm_a (33.9) has its own front-line validation."""
    # Minimal arguments — we only need enough to reach the validation guard
    # at the start of the function. baseline_ergodic, EconomyMrkv_init don't
    # need to be valid since validation runs first.
    with pytest.raises(ValueError, match="interpretation must be 'CDC' or 'ESC'"):
        propagate_experiment_tm_a(
            agent=None,
            baseline_ergodic=None,
            EconomyMrkv_init=[],
            dist_aGrid=np.array([0.0, 1.0]),
            E_pLvl=1.0,
            interpretation='BOGUS',
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
