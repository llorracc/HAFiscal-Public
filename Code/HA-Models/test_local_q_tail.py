"""V0 unit tests for local_q_tail (plans/20260722_local-two-secant-tail-q_plan.md)."""
import numpy as np
import pytest

import local_q_tail as lqt


MPC, H = 0.0054, 196.85


def synth(Q, m_top=590.0, n=60, A=0.5, drifty=0.0):
    """Solved-knot synth: gap = A*((x)/(x_top))**-(Q + drifty*ln(x/x_top))."""
    m = np.geomspace(0.5, m_top, n)
    x = m + H
    expo = Q + drifty * np.log(x / x[-1])
    gap = A * (x / x[-1]) ** (-expo)
    c = MPC * x - gap
    return m, c


def setup_function(_):
    lqt.reset_diagnostics()


def test_exact_powerlaw_recovery():
    for Q in (0.39, 0.56, 1.37):
        m, c = synth(Q)
        r = lqt.local_q_from_knots(m, c, H, MPC)
        assert r["ok"], r["reason"]
        assert abs(r["Q"] - Q) < 1e-8
        assert abs(r["Q1"] - r["Q2"]) < 1e-8
        assert abs(r["drift"]) < 1e-8
        assert r["drift_window"] == "interior"


def test_drift_detected_with_sign():
    # exponent RISING in x (drifty>0 makes expo smaller below the top => Q2 > Q1).
    # The synth drift is UNIFORM in ln(x), so the interior windows (F5: final
    # knot excluded) measure the same signed rate the legacy top windows did.
    m, c = synth(0.6, drifty=0.3)
    r = lqt.local_q_from_knots(m, c, H, MPC)
    assert r["ok"]
    assert r["drift"] > 0.25
    m, c = synth(0.6, drifty=-0.3)
    r = lqt.local_q_from_knots(m, c, H, MPC)
    assert r["drift"] < -0.25


def test_endpoint_noise_excluded_from_drift():
    # F5 (2026-07-23): the DIAGNOSTIC drift must come from windows that exclude
    # the final knot, so pure endpoint noise moves the attach Q (most-local
    # upper secant, endpoint included — by design) but NOT the drift advisory.
    m, c = synth(0.6)
    r_clean = lqt.local_q_from_knots(m, c, H, MPC)
    c_noisy = c.copy()
    gap_top = MPC * (m[-1] + H) - c[-1]
    c_noisy[-1] += 0.10 * gap_top  # shrink the top gap 10% — endpoint-only noise
    r_noisy = lqt.local_q_from_knots(m, c_noisy, H, MPC)
    assert r_noisy["ok"] and r_noisy["drift_window"] == "interior"
    # attach Q (endpoint-inclusive upper secant) responds to the endpoint ...
    assert abs(r_noisy["Q"] - r_clean["Q"]) > 0.05
    # ... but the interior-window drift does not (identical to the clean case)
    assert abs(r_noisy["drift"] - r_clean["drift"]) < 1e-12
    # and the legacy top-window drift WOULD have been contaminated:
    legacy_contamination = abs((r_noisy["Q2"] - r_noisy["Q1"]) - (r_clean["Q2"] - r_clean["Q1"]))
    assert legacy_contamination > 0.05


def test_three_knots_fall_back_to_legacy_top_drift():
    # With only 3 usable knots there is no interior triple; the diagnostic
    # falls back to the legacy endpoint-inclusive (Q2-Q1)/e-fold drift.
    m, c = synth(0.6, n=3)
    r = lqt.local_q_from_knots(m, c, H, MPC)
    assert r["ok"]
    assert r["drift_window"] == "legacy-top"
    x3 = m + H
    lx = np.log(x3)
    expected = (r["Q2"] - r["Q1"]) / (0.5 * (lx[-1] - lx[0]))
    assert abs(r["drift"] - expected) < 1e-12


def test_infeasible_span_falls_back():
    # legacy-scale top: m_top=40 << h — no (x+h) leverage
    m, c = synth(0.6, m_top=40.0)
    with pytest.warns(UserWarning, match="falling back"):
        r = lqt.local_q_from_knots(m, c, H, MPC)
    assert not r["ok"]
    assert "span" in r["reason"]
    assert lqt.DIAG["n_fallback"] == 1


def test_negative_gap_falls_back():
    m, c = synth(0.6)
    c = c + 2.0  # push consumption above the PF line
    with pytest.warns(UserWarning, match="falling back"):
        r = lqt.local_q_from_knots(m, c, H, MPC)
    assert not r["ok"]


def test_drift_advisory_fires_on_stable_plateau_one_shot():
    # 2026-07-23 wart fix: the advisory keys on per-invocation ROUNDS and fires
    # only once the round-worst is stable (±10%) for >= 3 consecutive rounds —
    # the converged plateau — never on a transient iterate.
    import warnings as w
    m, c = synth(0.6, drifty=0.4)
    for _ in range(3):   # rounds 1–3: exceeding, but stability count < 3 → silent
        lqt.begin_round()
        r = lqt.local_q_from_knots(m, c, H, MPC)
        assert r["ok"] and abs(r["drift"]) > 0.05
        with w.catch_warnings():
            w.simplefilter("error")
            lqt.maybe_warn_drift(tol=0.05)
    lqt.begin_round()
    lqt.local_q_from_knots(m, c, H, MPC)
    with pytest.warns(UserWarning, match="converged plateau"):
        lqt.maybe_warn_drift(tol=0.05)   # round 4: stable ≥ 3 → fires
    lqt.begin_round()
    lqt.local_q_from_knots(m, c, H, MPC)
    with w.catch_warnings():
        w.simplefilter("error")
        lqt.maybe_warn_drift(tol=0.05)   # one-shot: silent afterwards


def test_transient_drift_never_warns():
    # High drift on early rounds that then DROPS to a clean plateau (the real
    # EGM pattern that produced the wart) must never warn.
    import warnings as w
    m_hi, c_hi = synth(0.6, drifty=0.4)
    m_lo, c_lo = synth(0.6)   # drift ≈ 0
    with w.catch_warnings():
        w.simplefilter("error")
        for _ in range(2):     # transient: exceeding but not yet 3-stable
            lqt.begin_round()
            lqt.local_q_from_knots(m_hi, c_hi, H, MPC)
            lqt.maybe_warn_drift(tol=0.05)
        for _ in range(6):     # converged plateau BELOW tolerance
            lqt.begin_round()
            lqt.local_q_from_knots(m_lo, c_lo, H, MPC)
            lqt.maybe_warn_drift(tol=0.05)


def test_quiet_below_tolerance():
    m, c = synth(0.6)
    lqt.local_q_from_knots(m, c, H, MPC)
    import warnings as w
    with w.catch_warnings():
        w.simplefilter("error")
        lqt.maybe_warn_drift(tol=0.05)
