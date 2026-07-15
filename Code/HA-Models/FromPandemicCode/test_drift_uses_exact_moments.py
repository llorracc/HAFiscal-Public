"""Regression tests for the 2026-05-06 wiring of compute_log_p_moments_exact
into the drift pass/fail logic.

The exact Markov-chain log(p) moments replace the legacy (1-u) lognormal-mixture
single-Gaussian-per-cohort approximation as the analytical reference for drift
checks. The Config B threshold loosening (max(threshold*4, 0.12)) is removed
because the analytical reference is no longer biased.
"""

import sys
sys.argv = ['pytest', '1.01', '2.0', '0.7', '0.5']

import numpy as np
import pytest


def _baseline_dicts():
    """Common moments dicts: zero in everything except log(p)."""
    tma = {
        'mean_log_a': 0.0, 'var_log_a': 1.0, 'mass_at_zero': 0.5,
        'pct_aNrm_25': 0.1, 'pct_aNrm_50': 1.0, 'pct_aNrm_75': 5.0,
        'lorenz_p20': 0.0, 'lorenz_p40': 0.5, 'lorenz_p60': 2.0, 'lorenz_p80': 10.0,
        'mean_aNrm': 1.0, 'var_aNrm': 1.0,
        # Legacy (1-u) approximation: D-cohort case where approx overestimates
        # var log(p) by +4.6% rel and shifts mean by ~5e-3.
        'mean_log_p': 1.909488,
        'var_log_p': 0.229345,
        # NEW exact Markov-chain moments
        'mean_log_p_exact': 1.914746,
        'var_log_p_exact': 0.219229,
    }
    mc = {
        'mean_log_a': 0.0, 'var_log_a': 1.0, 'mass_at_zero': 0.5,
        'pct_aNrm_25': 0.1, 'pct_aNrm_50': 1.0, 'pct_aNrm_75': 5.0,
        'lorenz_p20': 0.0, 'lorenz_p40': 0.5, 'lorenz_p60': 2.0, 'lorenz_p80': 10.0,
        'mean_aNrm': 1.0, 'var_aNrm': 1.0,
        # MC empirical at N=100k matches EXACT (validated 2026-05-06)
        'mean_log_p': 1.914621,
        'var_log_p': 0.218814,
    }
    return tma, mc


def test_measure_drift_prefers_exact_when_present():
    from _tm_a_drift import measure_drift
    tma, mc = _baseline_dicts()
    d = measure_drift(tma, mc)
    # MC vs EXACT: residuals close to zero (within sampling noise)
    assert abs(d['mean_log_p_abs']) < 1e-3, f"mean drift {d['mean_log_p_abs']} should be ~0 vs EXACT"
    assert abs(d['var_log_p_rel']) < 1e-2, f"var drift {d['var_log_p_rel']} should be ~0 vs EXACT"


def test_measure_drift_falls_back_to_legacy_when_exact_absent():
    from _tm_a_drift import measure_drift
    tma, mc = _baseline_dicts()
    tma_legacy = {k: v for k, v in tma.items() if not k.endswith('_exact')}
    d = measure_drift(tma_legacy, mc)
    # MC vs LEGACY APPROX: shows the +5e-3 mean bias and -4.6% var bias
    assert abs(d['mean_log_p_abs'] - 0.005) < 1e-3, f"backward-compat mean drift {d['mean_log_p_abs']}"
    assert abs(d['var_log_p_rel'] + 0.046) < 5e-3, f"backward-compat var drift {d['var_log_p_rel']}"


def test_assess_passes_under_tight_threshold_config_b():
    """With exact moments, Config B (perm_shocks=off) passes tight 0.03 threshold."""
    from _tm_a_drift import measure_drift, assess_and_report

    tma, mc = _baseline_dicts()
    d = measure_drift(tma, mc)

    class Stub: pass
    agent = Stub()
    agent.perm_shocks_during_unemployment = False  # Config B (QE-matching)
    ok = assess_and_report(d, threshold=0.03, hard_fail=False,
                           agent=agent, label='test_cfgB')
    assert ok, "Config B should PASS at tight 0.03 threshold with exact moments"


def test_assess_fails_when_residual_actually_exceeds_threshold():
    """Sanity: large residual still triggers FAIL."""
    from _tm_a_drift import measure_drift, assess_and_report

    tma, mc = _baseline_dicts()
    # Inject a big drift in MC
    mc['var_log_p'] = tma['var_log_p_exact'] * 1.10  # +10% rel drift
    d = measure_drift(tma, mc)
    class Stub: pass
    agent = Stub()
    agent.perm_shocks_during_unemployment = False
    ok = assess_and_report(d, threshold=0.03, hard_fail=False,
                           agent=agent, label='test_fail')
    assert not ok, "10% var drift should FAIL at 0.03 threshold (was previously hidden by 0.12 loosening)"


# ---------------------------------------------------------------------------
# N-aware pLvl-moment band (calibrated 2026-06-13). The pLvl drift is finite-
# population noise of a near-unit-root process around a systematic warmup
# transient, so a fixed 0.03 spuriously fails at production N. The band is
# center ± z·scale/√N (default z=3.090 ⇒ ≈0.2% false-fail under correct calibration).
# ---------------------------------------------------------------------------

def _clean_drift(mean_log_p_abs=0.0, var_log_p_rel=0.0):
    """A drift dict with everything benign except the two pLvl moments."""
    d = {f"lorenz_p{q}_abs_pp": 0.0 for q in (20, 40, 60, 80)}
    d.update({
        "mean_log_p_abs": mean_log_p_abs, "var_log_p_rel": var_log_p_rel,
        "pct_aNrm_25_rel": 0.0, "pct_aNrm_50_rel": 0.0, "pct_aNrm_75_rel": 0.0,
        "mean_log_a_abs": 0.0, "var_log_a_rel": 0.0, "mass_at_zero_abs": 0.0,
        "mc_mass_at_zero": 0.0, "tma_mass_at_zero": 0.0,
    })
    return d


def _agent(N):
    class Stub: pass
    a = Stub(); a.AgentCount = N
    return a


def test_pLvl_band_scales_as_one_over_sqrtN():
    from _tm_a_drift import _pLvl_drift_band, _PLVL_VAR_DRIFT_CENTER, \
        _PLVL_VAR_DRIFT_SCALE, _PLVL_DRIFT_Z
    lo1, hi1 = _pLvl_drift_band(_PLVL_VAR_DRIFT_CENTER, _PLVL_VAR_DRIFT_SCALE, 1500, _PLVL_DRIFT_Z)
    lo4, hi4 = _pLvl_drift_band(_PLVL_VAR_DRIFT_CENTER, _PLVL_VAR_DRIFT_SCALE, 6000, _PLVL_DRIFT_Z)
    half1 = (hi1 - lo1) / 2.0
    half4 = (hi4 - lo4) / 2.0
    # 4x N → half-width shrinks by ~2x (1/sqrt(4))
    assert half4 == pytest.approx(half1 / 2.0, rel=1e-6)
    # both bands centered on the systematic var-drift center
    assert (lo1 + hi1) / 2.0 == pytest.approx(_PLVL_VAR_DRIFT_CENTER, abs=1e-9)


def test_naware_passes_systematic_overshoot():
    """The +0.073 var / +0.024 mean systematic overshoot is INSIDE the N-aware
    band at production N (it would FAIL the legacy fixed 0.03 threshold — see
    test_naware_off_restores_fixed_threshold)."""
    from _tm_a_drift import assess_and_report
    d = _clean_drift(mean_log_p_abs=0.024, var_log_p_rel=0.073)
    assert assess_and_report(d, hard_fail=False, agent=_agent(1500), label='naware_ok')


def test_naware_fails_gross_miscalibration():
    from _tm_a_drift import assess_and_report
    d = _clean_drift(mean_log_p_abs=0.024, var_log_p_rel=0.40)  # +40% var
    assert not assess_and_report(d, hard_fail=False, agent=_agent(1500),
                                 label='gross')


def test_naware_small_N_band_is_wide(monkeypatch):
    """Dropout-sized cohort (N≈465): wide band tolerates larger noise."""
    from _tm_a_drift import assess_and_report
    d = _clean_drift(mean_log_p_abs=-0.0069, var_log_p_rel=-0.0363)  # real dropout values
    assert assess_and_report(d, hard_fail=False, agent=_agent(465), label='dropout')


def test_naware_off_restores_fixed_threshold(monkeypatch):
    from _tm_a_drift import assess_and_report
    monkeypatch.setenv("HAFISCAL_DRIFT_PLVL_NAWARE", "0")
    d = _clean_drift(mean_log_p_abs=0.024, var_log_p_rel=0.073)
    # legacy fixed 0.03: var +0.073 exceeds → FAIL
    assert not assess_and_report(d, threshold=0.03, hard_fail=False,
                                 agent=_agent(1500), label='legacy')


def test_naware_requires_agentcount():
    """Without AgentCount the band can't be formed → fixed-threshold fallback."""
    from _tm_a_drift import assess_and_report
    class Stub: pass
    d = _clean_drift(mean_log_p_abs=0.024, var_log_p_rel=0.073)
    # No AgentCount → fixed 0.03 path → var +0.073 FAILS
    assert not assess_and_report(d, threshold=0.03, hard_fail=False,
                                 agent=Stub(), label='no_N')
