"""Unit test for BUG-041 fix: TM-a cfunc_offset MC vs TM convention.

Verifies that the new `_cratio_for_period` helper returns the right value
under both 'mc' (default) and 'tm' (legacy) modes, at boundary t=0 and at t>0.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_cratio_for_period_mc_mode():
    """At t>0, MC mode returns Cratio_path[t-1] (one-period lag)."""
    import tm_methods
    Cratio_path = [1.020, 0.992, 0.989, 0.987, 0.985]
    # At t=0, both modes return Cratio_path[0]
    assert tm_methods._cratio_for_period(Cratio_path, 0, 'mc') == 1.020
    # At t=1, MC mode returns Cratio_path[0]
    assert tm_methods._cratio_for_period(Cratio_path, 1, 'mc') == 1.020
    # At t=2, MC mode returns Cratio_path[1]
    assert tm_methods._cratio_for_period(Cratio_path, 2, 'mc') == 0.992
    # At t=4, MC mode returns Cratio_path[3]
    assert tm_methods._cratio_for_period(Cratio_path, 4, 'mc') == 0.987


def test_cratio_for_period_tm_mode():
    """TM mode returns Cratio_path[t] (no lag, pre-fix legacy behavior)."""
    import tm_methods
    Cratio_path = [1.020, 0.992, 0.989, 0.987, 0.985]
    assert tm_methods._cratio_for_period(Cratio_path, 0, 'tm') == 1.020
    assert tm_methods._cratio_for_period(Cratio_path, 1, 'tm') == 0.992
    assert tm_methods._cratio_for_period(Cratio_path, 2, 'tm') == 0.989
    assert tm_methods._cratio_for_period(Cratio_path, 4, 'tm') == 0.985


def test_default_is_mc():
    """Default _HAFISCAL_TM_CFUNC_OFFSET should be 'mc' (matches QE)."""
    import tm_methods
    # The default is 'mc' unless env var is set to something else
    # When run without HAFISCAL_TM_CFUNC_OFFSET env, default should be 'mc'
    if 'HAFISCAL_TM_CFUNC_OFFSET' not in os.environ:
        assert tm_methods._HAFISCAL_TM_CFUNC_OFFSET == 'mc'


def test_propagate_signatures_have_cfunc_offset():
    """The 4 plumbed-through functions should accept cfunc_offset parameter."""
    import inspect
    import tm_methods

    for fname in ('propagate_experiment_tm', 'propagate_experiment_tm_a',
                  'run_ad_tm', 'run_experiment_tm_nonbase'):
        f = getattr(tm_methods, fname)
        sig = inspect.signature(f)
        assert 'cfunc_offset' in sig.parameters, \
            f"{fname} missing cfunc_offset parameter"


if __name__ == '__main__':
    test_cratio_for_period_mc_mode()
    test_cratio_for_period_tm_mode()
    test_default_is_mc()
    test_propagate_signatures_have_cfunc_offset()
    print("All unit tests passed.")
