"""
Unit tests for the ESC interpretation branch of `_build_period_tm_a`
in tm_methods.py.

Per Phase 0.2 of plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md:
verify that adding `interpretation='ESC'` to `_build_period_tm_a` produces
the ESC asset rule `a_next = m - c*(m)` (no splurge blending), while
`interpretation='CDC'` (the default) preserves the byte-identical CDC
behavior.

Tests:

  1. test_invalid_interpretation_raises
     - interpretation='FOO' raises ValueError.

  2. test_default_interpretation_is_CDC
     - omitting the interpretation kwarg gives byte-identical TM to
       interpretation='CDC' (regression: pre-existing call sites unaffected).

  3. test_esc_drops_splurge_blending_in_assets
     - Construct a small kernel with Splurge > 0 and a non-trivial xi
       distribution. Verify that the CDC and ESC TMs differ exactly where
       the asset-rule formulas differ.
     - Specifically: under ESC, c_actual = c*(m); under CDC, c_actual =
       (1-ς)*c*(m) + ς*xi. Compute one source-cell's column and verify
       the lottery weights land at different a_next positions consistent
       with these formulas.

  4. test_splurge_zero_makes_CDC_and_ESC_identical
     - With Splurge=0, both interpretations give a_next = m - c*(m).
       So the TMs should be byte-identical.

Cheap smoke (~few seconds total). Not in the production estimation path;
run via: pytest Code/HA-Models/FromPandemicCode/test_build_period_tm_a_esc.py
"""

import os
import sys
import numpy as np
import pytest

# Locate FromPandemicCode on sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from tm_methods import _build_period_tm_a
from HARK.distributions import DiscreteDistribution


def _make_minimal_inputs(seed=0):
    """Construct a minimal valid input set for _build_period_tm_a.

    Single Markov state (J=1), small a-grid (A=8), simple income shock
    distribution (3 atoms). Returns a dict of all kwargs.
    """
    rng = np.random.default_rng(seed)

    A = 8
    J = 1
    dist_aGrid = np.array([0.0, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0])

    # Simple cFunc: c(m, Cratio) = 0.5 * m (consumes half of resources).
    # Returns a list of length J of callables matching tm_methods's expected
    # signature `cFunc(mNrm_flat, Cratio_flat)`.
    def cfunc_half(m_flat, Cratio_flat):
        return 0.5 * m_flat
    cFuncs = [cfunc_half]

    # Income shock distribution: 3 atoms with psi (perm) and xi (tran)
    pmv = np.array([0.25, 0.5, 0.25])
    psi = np.array([0.9, 1.0, 1.1])      # permanent shock
    xi = np.array([0.5, 1.0, 1.5])       # transitory shock
    IncShkDstn_list = [
        DiscreteDistribution(pmv, [psi, xi])
    ]

    # Markov micro transition: J=1, so identity
    micro_trans = np.array([[1.0]])

    # Vital rates (J,)
    Rfree_arr = np.array([1.04])
    PermGroFac_arr = np.array([1.0])
    LivPrb_arr = np.array([0.99])

    # Newborn distribution: A*J = 8 entries; mass at a=0
    NewBornDist = np.zeros(A * J)
    NewBornDist[0] = 1.0

    return dict(
        dist_aGrid=dist_aGrid,
        cFuncs=cFuncs,
        IncShkDstn_list=IncShkDstn_list,
        micro_trans=micro_trans,
        Rfree_arr=Rfree_arr,
        PermGroFac_arr=PermGroFac_arr,
        LivPrb_arr=LivPrb_arr,
        NewBornDist=NewBornDist,
    )


def test_invalid_interpretation_raises():
    """interpretation='FOO' should raise ValueError before any computation."""
    inputs = _make_minimal_inputs()
    with pytest.raises(ValueError, match="interpretation must be 'CDC' or 'ESC'"):
        _build_period_tm_a(Splurge=0.25, interpretation='FOO', **inputs)


def test_default_interpretation_is_CDC():
    """Omitting the interpretation kwarg must give the same TM as
    interpretation='CDC' explicitly. Regression check: pre-existing call
    sites (which don't pass interpretation) get byte-identical CDC behavior."""
    inputs = _make_minimal_inputs()

    tm_default = _build_period_tm_a(Splurge=0.25, **inputs)
    tm_explicit_cdc = _build_period_tm_a(Splurge=0.25, interpretation='CDC', **inputs)

    diff = (tm_default - tm_explicit_cdc).toarray()
    assert np.max(np.abs(diff)) < 1e-15, \
        f"Default differs from explicit CDC by max {np.max(np.abs(diff))}"


def test_splurge_zero_makes_CDC_and_ESC_identical():
    """With Splurge=0, both interpretations give a_next = m - c*(m), so the
    TMs must be byte-identical. This is the analytical-symmetry sanity
    check from why_TM_a_kernel.md §10 debugging guide #6."""
    inputs = _make_minimal_inputs()

    tm_cdc = _build_period_tm_a(Splurge=0.0, interpretation='CDC', **inputs)
    tm_esc = _build_period_tm_a(Splurge=0.0, interpretation='ESC', **inputs)

    diff = (tm_cdc - tm_esc).toarray()
    assert np.max(np.abs(diff)) < 1e-15, \
        f"At Splurge=0, CDC and ESC TMs should match; max diff = {np.max(np.abs(diff))}"


def test_esc_drops_splurge_blending_in_assets():
    """With Splurge > 0, CDC and ESC TMs must differ.

    Under CDC: c_actual = (1-ς)·c*(m) + ς·xi, so a_next depends on xi.
    Under ESC: c_actual = c*(m),               so a_next is deterministic in m.

    With cfunc_half(m) = 0.5·m and Splurge=0.25, for a source (a, xi) pair:
      m_next = R·a/(Γψ) + xi
      CDC: c_actual = 0.75·0.5·m_next + 0.25·xi = 0.375·m_next + 0.25·xi
           a_next^CDC = m_next - c_actual = 0.625·m_next - 0.25·xi
      ESC: c_actual = 0.5·m_next
           a_next^ESC = 0.5·m_next

    For typical (m_next, xi), these differ. So the TMs must differ.

    We just check that the TMs are not byte-identical (we don't pin exact
    numerical values; that's pin-test territory). The ESC-vs-CDC numerical
    difference is the subject of Phase 1 convergence testing."""
    inputs = _make_minimal_inputs()

    tm_cdc = _build_period_tm_a(Splurge=0.25, interpretation='CDC', **inputs)
    tm_esc = _build_period_tm_a(Splurge=0.25, interpretation='ESC', **inputs)

    diff = (tm_cdc - tm_esc).toarray()
    max_diff = np.max(np.abs(diff))
    assert max_diff > 1e-6, \
        (f"At Splurge=0.25, CDC and ESC TMs must differ (asset rules differ); "
         f"observed max diff = {max_diff}. If this is below threshold, the "
         f"ESC branch in _build_period_tm_a may not be active.")


def test_esc_a_next_matches_cFunc_only_formula():
    """Direct numerical check: ESC's a_next for a single (a, xi) pair
    matches the formula a_next = m - cFunc(m) (no splurge term).

    Setup: J=1, single source asset a=4.0, single xi=1.0, deterministic
    income (perm shock = 1.0). Let cFunc = 0.5*m.
        m = R·a + xi = 1.04·4 + 1 = 5.16
        a_next^ESC = m - 0.5·m = 0.5·m = 2.58
        a_next^CDC = m - (0.75·0.5·m + 0.25·xi) = 0.625·m - 0.25·xi = 3.225 - 0.25 = 2.975
    The TM should put nonzero mass on these distinct a_next values."""
    A = 8
    J = 1
    dist_aGrid = np.array([0.0, 1.0, 2.0, 2.58, 2.975, 4.0, 8.0, 16.0])
    # Note dist_aGrid contains 2.58 and 2.975 exactly so we can read off
    # the lottery weights directly without interpolation rounding.

    def cfunc_half(m_flat, Cratio_flat):
        return 0.5 * m_flat
    cFuncs = [cfunc_half]

    # Single-atom income distribution (psi=1, xi=1, prob=1)
    pmv = np.array([1.0])
    psi = np.array([1.0])
    xi = np.array([1.0])
    IncShkDstn_list = [DiscreteDistribution(pmv, [psi, xi])]

    micro_trans = np.array([[1.0]])
    Rfree_arr = np.array([1.04])
    PermGroFac_arr = np.array([1.0])
    LivPrb_arr = np.array([1.0])  # no death so kernel only writes survivor mass
    NewBornDist = np.zeros(A * J)
    NewBornDist[0] = 1.0

    common = dict(
        dist_aGrid=dist_aGrid,
        cFuncs=cFuncs, IncShkDstn_list=IncShkDstn_list,
        micro_trans=micro_trans, Rfree_arr=Rfree_arr,
        PermGroFac_arr=PermGroFac_arr, LivPrb_arr=LivPrb_arr,
        NewBornDist=NewBornDist,
    )

    tm_cdc = _build_period_tm_a(Splurge=0.25, interpretation='CDC', **common)
    tm_esc = _build_period_tm_a(Splurge=0.25, interpretation='ESC', **common)

    # Source: (a, j) = (4.0, 0); index in dist_aGrid is 5
    src_idx = 5
    # Expected a_next under each interpretation
    a_next_esc_expected = 2.58   # a-grid index 3
    a_next_cdc_expected = 2.975  # a-grid index 4

    # Read out the destination column for this source
    col_cdc = tm_cdc.toarray()[:, src_idx]
    col_esc = tm_esc.toarray()[:, src_idx]

    # Under ESC, mass should land at index 3 (a=2.58)
    assert col_esc[3] > 0.99, \
        f"ESC: expected mass ~1.0 at a_next index 3 (a=2.58), got {col_esc[3]}"
    # Under CDC, mass should land at index 4 (a=2.975)
    assert col_cdc[4] > 0.99, \
        f"CDC: expected mass ~1.0 at a_next index 4 (a=2.975), got {col_cdc[4]}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
