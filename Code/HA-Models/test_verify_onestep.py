"""Validation gate for the de-biased one-step reuse gate — thread-2 component 4.

The gate the build plan requires GREEN before the de-biasing may be trusted. It decides
SOUNDNESS empirically on exact residual sequences for linear multi-mode contractions (a
faithful model of EGM near its fixed point), independent of the real solver.

The 2026-06-22 run settled the design: the de-biasing G ≈ r₁/(1−L) is a SOUND gate with a
KNOWN modulus L (rigorously conservative — never false-passes, even small gaps, in one step),
and a gross-gap SCREEN only with an ESTIMATED modulus (a small spectral gap under-states λ_max
at finite k). The two blocks below prove exactly that.

Required cases (build plan §4):
  (a) ACCEPT a 9th-digit-equivalent reuse (G ~ 0);
  (b) CATCH a BUG-047-scale gap (G ~ 6%) the NAIVE gate FALSE-PASSES;
  (c) the modulus estimate's behaviour over k.
"""
from __future__ import annotations

import math

import pytest

import verify_onestep as vo

# College GIC-cap atom: the slowest contraction modulus, L = Þ/R ≈ 0.99 (the binding case).
L_DOM = 0.99
SOLVE_TOL = 1e-3            # the AD-loop convergence tolerance the naive gate would use


def _residuals(moduli, amps, k):
    """Exact consecutive step-residual norms for a linear multi-mode contraction.

    Error e_n = Σ_i amps_i · moduli_i^n along orthonormal modes; the backward step residual is
    r_n = ||e_n − e_{n-1}|| = sqrt(Σ_i (amps_i · moduli_i^{n-1} · (moduli_i − 1))^2). EGM is
    linear near x*, so this is the exact residual its contraction produces."""
    out = []
    for n in range(1, k + 1):
        s = 0.0
        for lam, c in zip(moduli, amps):
            comp = c * (lam ** (n - 1)) * (lam - 1.0)
            s += comp * comp
        out.append(math.sqrt(s))
    return out


# ======================================================================================= #
# BLOCK 1 — the KNOWN-modulus gate: the SOUND, rigorously-conservative path.
# ======================================================================================= #
def test_known_a_accepts_ninth_digit_reuse():
    r = _residuals([L_DOM], [1e-9], k=2)                      # a 1e-9 gap
    accept, est = vo.onestep_gate(r, tol=1e-4, modulus=L_DOM)
    assert accept is True and est["G_est"] < 1e-4


def test_known_a_accepts_at_floor():
    accept, est = vo.onestep_gate([1e-13, 1e-13], tol=1e-6, modulus=L_DOM)
    assert accept is True and est["at_floor"] and est["G_est"] == 0.0


def test_known_b_catches_what_naive_false_passes():
    """THE HEADLINE: a 6% regime gap that the naive raw-residual gate false-passes."""
    r = _residuals([L_DOM], [0.06], k=1)                      # ONE step is enough with known L
    assert vo.naive_gap(r) < SOLVE_TOL                        # naive FALSE-PASSES at the solve tol
    accept, est = vo.onestep_gate(r, tol=SOLVE_TOL, modulus=L_DOM)
    assert accept is False                                    # de-biased CATCHES it
    assert est["G_est"] == pytest.approx(0.06, abs=1e-9)


def test_known_catches_small_half_percent_gap():
    """The sibling plan's worry — a SMALL (0.5%) discretionary-flip gap — is caught too."""
    r = _residuals([L_DOM], [0.005], k=1)
    assert vo.naive_gap(r) < SOLVE_TOL                        # raw r1 = 5e-5 < 1e-3: naive passes
    accept, est = vo.onestep_gate(r, tol=SOLVE_TOL, modulus=L_DOM)
    assert accept is False and est["G_est"] == pytest.approx(0.005, abs=1e-9)


@pytest.mark.parametrize("L", [0.90, 0.95, 0.99, 0.995, 0.999])
@pytest.mark.parametrize("G", [0.005, 0.02, 0.06, 0.10])
def test_known_recovers_gap_single_mode(L, G):
    r = _residuals([L], [G], k=1)
    est = vo.estimate_contraction_gap(r, modulus=L)
    assert est["G_est"] == pytest.approx(G, rel=1e-9)


def test_known_rigorously_conservative_adversarial():
    """With a known modulus, G_est >= the dangerous slow-mode gap for EVERY spectrum (so the
    gate NEVER false-passes) — including arbitrary harmless fast-mode content. This is the
    property the estimated-modulus fallback does NOT have."""
    violations = []
    for G_slow in (0.005, 0.06):
        for fast_lam in (0.0, 0.1, 0.3, 0.5, 0.8, 0.95):
            for fast_amp in (0.0, 0.01, 0.1, 1.0, 10.0, 100.0):
                for k in (1, 2, 4):
                    r = _residuals([L_DOM, fast_lam], [G_slow, fast_amp], k=k)
                    accept, est = vo.onestep_gate(r, tol=SOLVE_TOL, modulus=L_DOM)
                    # rigorous: estimate >= true dangerous gap, AND the gate rejects it
                    if est["G_est"] < G_slow - 1e-12 or accept:
                        violations.append((G_slow, fast_lam, fast_amp, k, est["G_est"]))
    assert not violations, f"{len(violations)} conservativeness violation(s): {violations[:5]}"


# ======================================================================================= #
# BLOCK 2 — the ESTIMATED-modulus fallback: a gross-gap SCREEN, with its limitation.
# ======================================================================================= #
def test_estimated_b_catches_bug047_single_mode():
    r = _residuals([L_DOM], [0.06], k=4)
    accept, est = vo.onestep_gate(r, tol=SOLVE_TOL)            # no modulus -> estimate it
    assert accept is False
    assert est["G_est"] == pytest.approx(0.06, abs=5e-3)
    assert est["L_est"] == pytest.approx(L_DOM, abs=5e-3)
    assert est["source"] == "estimated"


def test_estimated_brute_no_false_pass_large_gap():
    """The fallback still REJECTS every 6%-scale gap at the solve tolerance (the under-stated
    G_est is ~0.01-0.06, all >> 1e-3) — it is a usable gross-gap screen."""
    false_passes = []
    for fast_lam in (0.0, 0.1, 0.3, 0.5, 0.8, 0.95):
        for fast_amp in (0.0, 0.01, 0.1, 1.0, 10.0, 100.0):
            for k in (2, 4, 6):
                r = _residuals([L_DOM, fast_lam], [0.06, fast_amp], k=k)
                accept, _ = vo.onestep_gate(r, tol=SOLVE_TOL)
                if accept:
                    false_passes.append((fast_lam, fast_amp, k))
    assert not false_passes, f"{len(false_passes)} false-pass(es): {false_passes[:5]}"


@pytest.mark.parametrize("k", [2, 4, 6, 10, 15])
def test_estimated_modulus_climbs_to_dominant_only_slowly(k):
    r = _residuals([L_DOM, 0.5], [0.06, 0.06], k=k)
    est = vo.estimate_contraction_gap(r)
    assert est["L_est"] <= L_DOM + 1e-9                       # never exceeds the dominant
    # converges to λ_max only at HIGH k: a large fast STEP-factor (|0.5-1|=0.5 vs |0.99-1|=
    # 0.01) keeps the residual fast-dominated for ~7 steps, so the max-ratio estimate is far
    # below λ_max until k~15 — exactly why the estimated path is NOT a rigorous gate.
    if k <= 4:
        assert est["L_est"] < 0.7                            # badly under-states at low k
    if k >= 15:
        assert est["L_est"] == pytest.approx(L_DOM, abs=0.02)  # only now near the dominant


def test_estimated_fallback_screens_small_gaps_but_is_not_rigorous():
    """The estimated fallback empirically catches even a 0.5% gap across a spectrum grid (the
    fast mode INFLATES r_1, which compensates for the under-stated L_est), so it is a usable
    SCREEN. But it is NOT a rigorous bound — L_est can be far below λ_max at low k — which is
    why the KNOWN-modulus path is the sound gate. (Contrast: BLOCK 1 proves the known path is
    rigorously conservative on this same grid.)"""
    false_passes = []
    for fast_lam in (0.0, 0.3, 0.5, 0.7, 0.9, 0.95):
        for fast_amp in (0.0, 0.01, 0.1, 1.0, 10.0):
            for k in (2, 3, 4, 6):
                r = _residuals([L_DOM, fast_lam], [0.005, fast_amp], k=k)
                accept, _ = vo.onestep_gate(r, tol=SOLVE_TOL)
                if accept:
                    false_passes.append((fast_lam, fast_amp, k))
    assert not false_passes, f"fallback false-passed a 0.5% gap: {false_passes[:5]}"
    # ...yet the estimate itself is not rigorous: at low k it badly under-states the modulus.
    est = vo.estimate_contraction_gap(_residuals([L_DOM, 0.5], [0.06, 0.06], k=4))
    assert est["L_est"] < 0.7 < L_DOM


# ======================================================================================= #
# guards
# ======================================================================================= #
def test_not_contracting_rejected():
    accept, est = vo.onestep_gate([1e-4, 2e-4, 4e-4], tol=SOLVE_TOL)   # residuals GROWING
    assert accept is False and est["G_est"] == float("inf") and est["contracting"] is False


def test_modulus_out_of_range_raises():
    with pytest.raises(ValueError):
        vo.debiased_gap(6e-4, 1.0)
    with pytest.raises(ValueError):
        vo.debiased_gap(6e-4, -0.1)


def test_estimate_needs_two_residuals_without_modulus():
    with pytest.raises(ValueError):
        vo.estimate_contraction_gap([1e-4])              # need 2 to estimate the modulus
    # but ONE residual is fine WITH a known modulus
    assert vo.estimate_contraction_gap([6e-4], modulus=L_DOM)["G_est"] == pytest.approx(0.06)


def test_negative_residual_rejected():
    with pytest.raises(ValueError):
        vo.estimate_contraction_gap([1e-4, -1e-5])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
