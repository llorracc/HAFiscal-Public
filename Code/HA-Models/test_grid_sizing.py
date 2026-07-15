"""Unit tests for grid_sizing.py — endogenous asset-grid maxima.

Pure/fast (no agent construction): validates the formulas against the 2026-06-24 measured values
(prompts_local/2026-06-24_grid-sizing-experiments-journal.md) and the floor guards. Run:
    pytest Code/HA-Models/test_grid_sizing.py
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grid_sizing as gs

# College GIC-cap atom, real ESC calibration (E1)
R, RHO, LIV = 1.01, 2.0, 1.0 - 1.0 / 160.0
BETA_CAP = {0: 1.00268, 1: 1.00464, 2: 1.00537}   # Dropout / HS / College
GAMMA = {0: 1.00355, 1: 1.00453, 2: 1.004895}
EINV = 1.003004
H_EMP = {0: 151.4, 1: 181.0, 2: 195.1}            # measured employed-state human wealth
MPCMIN = {0: 0.00675, 1: 0.00578, 2: 0.00542}     # measured


def test_factors_recover_measured_college():
    pf = gs.patience_factors(R, BETA_CAP[2], RHO, LIV, GAMMA[2], EINV)
    assert pf.MPCmin == pytest.approx(0.00542, abs=5e-5)
    assert pf.gap_RAW == pytest.approx(0.00349, abs=5e-5)
    assert pf.gap_MOD == pytest.approx(0.00050, abs=5e-5)
    assert pf.omega == pytest.approx(-0.001145, abs=5e-5)


def test_gap_mod_pinned_by_gicfactor_across_groups():
    # gap_RAW, gap_MOD are identical across groups (pinned by theGICfactor), per E1.
    gaps = [gs.patience_factors(R, BETA_CAP[e], RHO, LIV, GAMMA[e], EINV) for e in (0, 1, 2)]
    assert all(g.gap_MOD == pytest.approx(0.00050, abs=1e-4) for g in gaps)
    assert all(g.gap_RAW == pytest.approx(0.00349, abs=1e-4) for g in gaps)


def test_mpcmin_recovers_per_group():
    for e in (0, 1, 2):
        pf = gs.patience_factors(R, BETA_CAP[e], RHO, LIV, GAMMA[e], EINV)
        assert pf.MPCmin == pytest.approx(MPCMIN[e], abs=5e-5)


def test_solve_grid_recovers_e3_college():
    # E3: College needs ~228-256 for 1% tail accuracy (capped at the TM grid).
    sg = gs.solve_grid_aMax(R, BETA_CAP[2], RHO, LIV, tm_cap=1300.0)
    assert 200.0 <= sg <= 300.0


def test_solve_grid_monotone_in_patience():
    # More patient (higher beta -> lower MPCmin) -> larger solve grid.
    sg = [gs.solve_grid_aMax(R, BETA_CAP[e], RHO, LIV) for e in (0, 1, 2)]
    assert sg[0] < sg[1] < sg[2]   # Dropout < HS < College


def test_solve_grid_capped_at_tm():
    big = gs.solve_grid_aMax(R, BETA_CAP[2], RHO, LIV)         # ~256
    capped = gs.solve_grid_aMax(R, BETA_CAP[2], RHO, LIV, tm_cap=100.0)
    assert capped == 100.0 and big > 100.0


def test_solve_grid_count_preserves_density():
    # No extension -> count unchanged.
    assert gs.solve_grid_count(40.0, aXtraMin=0.001, legacy_aMax=40.0, legacy_count=48) == 48
    assert gs.solve_grid_count(30.0, aXtraMin=0.001, legacy_aMax=40.0, legacy_count=48) == 48
    # Extension 40->240 scales count by the ln-range ratio (~1.17 -> 56-57) to hold near-0 density.
    c240 = gs.solve_grid_count(240.0, aXtraMin=0.001, legacy_aMax=40.0, legacy_count=48)
    assert 56 <= c240 <= 57
    # Monotone in aMax (more reach -> more points to hold density). Dropout/HS/College = 56/57/57.
    cs = [gs.solve_grid_count(m, aXtraMin=0.001, legacy_aMax=40.0, legacy_count=48) for m in (205.0, 240.0, 256.0)]
    assert cs[0] <= cs[1] <= cs[2]


def test_tm_grid_recovers_production():
    # phi=6.5 (College binding) -> 1300 = production_aMax after round-100.
    assert gs.tm_grid_aMax(H_EMP[2]) == 1300.0
    # conservative phi=7.5 over-sizes (never undersizes), still finite.
    assert gs.tm_grid_aMax(H_EMP[2], phi=gs.TM_PHI_CONSERVATIVE) >= 1300.0


def test_pareto_form_matches():
    # x_min ~ 57, zeta ~ 3 -> 1300 (the structurally-honest Pareto form).
    assert gs.pareto_tail_aMax(57.0, 3.0) == pytest.approx(1300.0, abs=100.0)


def test_ric_guard_raises():
    # A very patient atom (beta=1.05) violates the RIC -> MPCmin<=0 -> raise.
    with pytest.raises(ValueError, match="RIC"):
        gs.solve_grid_aMax(R, 1.05, RHO, LIV)


def test_fhwc_holds():
    assert gs.fhwc_holds(1.01, 1.004895) is True    # College Γ<R
    assert gs.fhwc_holds(1.01, 1.01) is False        # Γ=R boundary
    assert gs.fhwc_holds(1.01, 1.05) is False         # Γ>R
    Pi = np.array([[0.9, 0.1], [0.5, 0.5]])
    assert gs.fhwc_holds(1.01, 1.004895, Pi) is True  # Markov: rho(Pi*G/R) < 1


def test_fhwc_nonfinite_falls_back_negative_raises():
    # Non-finite h = FHWC failure -> the owner's large-constant fallback (not a raise).
    import warnings as _w
    with _w.catch_warnings():
        _w.simplefilter("ignore")
        assert gs.tm_grid_aMax(float("inf")) == gs.FHWC_FALLBACK_AMAX
        assert gs.tm_grid_aMax(float("nan")) == gs.FHWC_FALLBACK_AMAX
        # solve_grid_aMax with FHWC failing (Γ>R) also falls back
        assert gs.solve_grid_aMax(1.01, 0.99, RHO, LIV, PermGroFac=1.05) == gs.FHWC_FALLBACK_AMAX
    # Negative h is a genuine error (broken (I-W) solve), not FHWC -> still raises.
    with pytest.raises(ValueError):
        gs.tm_grid_aMax(-1.0)
    # FHWC holds (College) -> normal sizing, fallback not triggered.
    assert gs.solve_grid_aMax(R, BETA_CAP[2], RHO, LIV, PermGroFac=GAMMA[2], tm_cap=1300.0) > 200.0


def test_fhwc_gap_threshold():
    # The FHWC CONDITIONING GAP (owner-agreed 2026-06-24) makes fhwc_holds STRICTER: the trip-wire is
    # rho(W) < 1/(1+gap), not rho(W) < 1. An atom with G/R in (1/(1+gap), 1) passes the bare FHWC
    # (gap=0) but is rejected with the default gap. Default FHWC_GAP=0.005 -> threshold 1/1.005.
    assert gs.FHWC_GAP == 0.005
    thresh = 1.0 / (1.0 + gs.FHWC_GAP)
    R0 = 1.0
    assert gs.fhwc_holds(R0, thresh - 1e-4) is True          # comfortably inside -> finite
    G_in_gap = R0 * (thresh + 1e-4)                          # G/R within the gap, still < 1
    assert (G_in_gap / R0) < 1.0                             # bare FHWC would hold
    assert gs.fhwc_holds(R0, G_in_gap) is False              # default gap rejects (ill-conditioned)
    assert gs.fhwc_holds(R0, G_in_gap, fhwc_gap=0.0) is True  # gap=0 recovers the bare FHWC


def test_human_wealth_gap_returns_nan_and_conditioning():
    # solve_markov_human_wealth returns NaN inside the conditioning gap (so the PF-decay caller falls
    # back), while gap=0 returns a finite-but-large (ill-conditioned) h ~ 1/(1-spectral_radius).
    from mom_bounds import solve_markov_human_wealth, FHWC_GAP
    M = np.array([[1.0]]); E = np.array([1.0]); R1 = np.array([1.0])
    G_in = np.array([1.0 / (1.0 + FHWC_GAP) + 2e-4])        # spectral_radius within (thresh, 1)
    import warnings as _w
    with _w.catch_warnings():
        _w.simplefilter("ignore")
        h_default = solve_markov_human_wealth(M, R1, E, PermGroFac_by_state=G_in)
        h_nogap = solve_markov_human_wealth(M, R1, E, PermGroFac_by_state=G_in, fhwc_gap=0.0)
    assert np.all(np.isnan(h_default))                      # default gap -> NaN -> caller falls back
    assert np.all(np.isfinite(h_nogap)) and h_nogap[0] > 100.0  # bare FHWC -> large/ill-conditioned


def test_human_wealth_per_group_distinct_and_beta_independent():
    # Per-group bound (owner ruling): each education group's h comes from ITS OWN Gamma; h is
    # Gamma/R-driven, NOT a single global Gamma_max, and structurally cannot depend on beta (beta is
    # not an argument to the human-wealth solve -- it drives MPCmin, not h). Regression lock.
    from mom_bounds import solve_markov_human_wealth
    M = np.array([[1.0]]); E = np.array([1.0]); R1 = np.array([R])
    hs = [solve_markov_human_wealth(M, R1, E, PermGroFac_by_state=np.array([GAMMA[e]]))[0]
          for e in (0, 1, 2)]
    assert hs[0] < hs[1] < hs[2]                            # increasing in own Gamma
    assert len({round(x, 6) for x in hs}) == 3             # three DISTINCT bounds, not one global
    assert solve_markov_human_wealth(M, R1, E, PermGroFac_by_state=np.array([GAMMA[2]]))[0] == hs[2]


def test_zeta_guard_raises():
    with pytest.raises(ValueError):
        gs.pareto_tail_aMax(57.0, -1.0)


def test_kesten_zeta_approx_three():
    # A lognormal-ish 2-point perm shock around the College GIC-cap raw growth-patience -> zeta ~ 3.
    pf = gs.patience_factors(R, BETA_CAP[2], RHO, LIV, GAMMA[2], EINV)
    # crude symmetric perm shock with E[psi]=1, small variance (PermShkStd^2 = 0.003)
    sd = math.sqrt(0.003)
    psi = np.array([math.exp(-sd), math.exp(sd)])
    psi = psi / np.dot(np.array([0.5, 0.5]), psi)   # renormalize E[psi]=1
    z = gs.kesten_zeta(pf.GPFacRaw_Liv, psi, np.array([0.5, 0.5]), LivPrb=LIV)
    assert 1.5 < z < 6.0   # finite mean, in the right ballpark (measured ~3)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
