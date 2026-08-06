"""Unit tests for per_atom_alpha (Component A of the R-c x R-d program).

Fast pure-numpy/scipy tests (<1 s total, single-threaded): no model builds,
no TM construction, no objective evaluations.

Validation anchors (plans/20260726_dist-grid-top-scoping_plan.md +
conclusions_private/2026-06-16_gic-inside-vs-outside-individual-target-vs-
tm-ergodic.md): the GIC-cap College atom ledger must give a Kesten root near
the lognormal-caricature value ~1.70, mortality must thin the tail
(d alpha / d LivPrb < 0), LivPrb=1 must raise (positive log-drift), and the
measured-slope estimator must recover a synthetic pure-Pareto exponent.
"""

import numpy as np
import pytest

from per_atom_alpha import (
    atom_alpha,
    atom_dist_top,
    equiprobable_mean_one_lognormal,
    kesten_alpha,
    measured_alpha,
)

# --- GIC-cap College atom ledger (the module docstring's disambiguation) ----
BETA_CAP = 1.00537        # gic_capped_beta for College under BUG-053
RFREE = 1.01
CRRA = 2.0
GAMMA_COLLEGE = 1.00490   # quarterly College PermGroFac
LIVPRB = 1.0 - 1.0 / 160.0  # 40-year working life, quarterly
SIGMA_PSI_SQ = 0.003      # var(log psi), mean-one lognormal caricature

PSI_ATOMS, PSI_PMV = equiprobable_mean_one_lognormal(SIGMA_PSI_SQ, 7)
LEDGER = (BETA_CAP, RFREE, CRRA, GAMMA_COLLEGE, LIVPRB, PSI_ATOMS, PSI_PMV)


def _pareto_sample(alpha_true, n, a_min=1.0):
    """Deterministic equal-weight quantile discretization of Pareto(alpha).

    a_i = a_min*(1-u_i)^(-1/alpha) at bin midpoints u_i = (i+0.5)/n, so the
    empirical ccdf at a_i is (1 - i/n) -- within O(1/(n*(1-u))) of the true
    (1 - u_i).  Deterministic (no RNG) so the recovery tolerance is a real
    bound, not a seed lottery.
    """
    u = (np.arange(n) + 0.5) / n
    a = a_min * (1.0 - u) ** (-1.0 / alpha_true)
    w = np.full(n, 1.0 / n)
    return a, w


# --------------------------------------------------------------------------
# kesten_alpha
# --------------------------------------------------------------------------

def test_cap_atom_ledger_root_in_bracket():
    """Ledger root must land in [1.55, 1.90] (caricature ~1.70).

    The 7-point equiprobable discretization keeps ~93% of the lognormal's
    log-variance, pushing the root a little above the exact-lognormal 1.70;
    measured value 1.779.  The root must also actually solve the condition.
    """
    alpha = kesten_alpha(*LEDGER)
    assert 1.55 <= alpha <= 1.90, alpha
    # plug back: LivPrb * E[(Thorn/psi)^alpha] = 1 with Thorn on beta*LivPrb
    thorn = (RFREE * BETA_CAP * LIVPRB) ** (1.0 / CRRA) / GAMMA_COLLEGE
    resid = LIVPRB * np.sum(PSI_PMV * (thorn / PSI_ATOMS) ** alpha) - 1.0
    assert abs(resid) < 1e-10, resid


def test_cap_atom_ledger_fine_discretization_matches_caricature():
    """201-point equiprobable psi -> root ~= the exact-lognormal 1.70."""
    atoms, pmv = equiprobable_mean_one_lognormal(SIGMA_PSI_SQ, 201)
    alpha = kesten_alpha(BETA_CAP, RFREE, CRRA, GAMMA_COLLEGE, LIVPRB,
                         atoms, pmv)
    assert 1.60 <= alpha <= 1.80, alpha


def test_naive_thorn_reading_pinned():
    """Disambiguation pin: LivPrb OUTSIDE the CRRA root gives ~1.10, not ~1.70.

    The brief's spelled formula Thorn=(R*beta)^(1/CRRA)/Gamma cannot reproduce
    the documented caricature on its own ledger; DiscFacEff = beta*LivPrb
    inside the root (the default) is what does.  Pin both so the discrepancy
    stays visible if anyone flips the default.
    """
    alpha_naive = kesten_alpha(*LEDGER, mortality_in_discount=False)
    assert 0.90 <= alpha_naive <= 1.30, alpha_naive
    assert alpha_naive < kesten_alpha(*LEDGER)  # naive Thorn is larger -> fatter tail


def test_alpha_monotone_decreasing_in_livprb():
    """d alpha / d LivPrb < 0.

    Analytic sign, checked before coding: more mortality = smaller L = thinner
    tail = LARGER alpha, so alpha must RISE as LivPrb FALLS.  Both channels
    agree: (i) the outer L multiplies f(alpha) down, requiring more convexity
    (larger alpha) to reach 1; (ii) the inner L lowers Thorn (less effective
    patience -> flatter savings), again thinning the tail.  Measured span:
    alpha ~ 4.7 at L=0.985 down to ~0.25 at L=0.999.
    """
    livprbs = [0.985, 0.99, LIVPRB, 0.9975, 0.999]
    alphas = [
        kesten_alpha(BETA_CAP, RFREE, CRRA, GAMMA_COLLEGE, L,
                     PSI_ATOMS, PSI_PMV)
        for L in livprbs
    ]
    for a_lo_L, a_hi_L in zip(alphas, alphas[1:]):
        assert a_lo_L > a_hi_L, (livprbs, alphas)


def test_livprb_one_raises_positive_drift():
    """L=1 on the cap-atom ledger: positive log-drift, no positive root.

    Mortality is the ENTIRE tail stabilizer for the cap atom (ledger: Jensen
    +0.30% vs impatience -0.037%); without culling the survivors accumulate
    without bound and the Kesten condition has no positive root.
    """
    with pytest.raises(ValueError, match="LivPrb=1.*LOG-DRIFT|LOG-DRIFT"):
        kesten_alpha(BETA_CAP, RFREE, CRRA, GAMMA_COLLEGE, 1.0,
                     PSI_ATOMS, PSI_PMV)


def test_livprb_one_classic_kesten_has_root():
    """L=1 with downward drift + spread: the classic mortality-free Kesten
    regime DOES have a root (the L=1 failure above is drift-specific).

    beta=0.95 makes log(Thorn) ~= -0.031 against E[-log psi] ~= +0.023 from
    the var=0.05 spread: drift ~= -0.007 < 0, while max(Thorn/psi) ~= 1.4 > 1,
    so the condition dips below 1 and re-crosses at alpha ~= 0.3.
    """
    atoms, pmv = equiprobable_mean_one_lognormal(0.05, 7)  # wide psi spread
    alpha = kesten_alpha(0.95, RFREE, CRRA, 1.01, 1.0, atoms, pmv)
    assert alpha > 0.0
    thorn = (RFREE * 0.95) ** (1.0 / CRRA) / 1.01
    assert np.log(thorn) - float(pmv @ np.log(atoms)) < 0  # drift really down
    resid = np.sum(pmv * (thorn / atoms) ** alpha) - 1.0
    assert abs(resid) < 1e-10, resid


def test_subcritical_raises():
    """Strong downward drift with no growth event (max Thorn/psi <= 1):
    tail thinner than any power law -> ValueError naming the regime."""
    with pytest.raises(ValueError, match="SUBCRITICAL"):
        kesten_alpha(0.96, RFREE, CRRA, GAMMA_COLLEGE, LIVPRB,
                     np.array([1.0]), np.array([1.0]))


def test_input_validation():
    with pytest.raises(ValueError, match="LivPrb"):
        kesten_alpha(BETA_CAP, RFREE, CRRA, GAMMA_COLLEGE, 1.5,
                     PSI_ATOMS, PSI_PMV)
    with pytest.raises(ValueError, match="positive"):
        kesten_alpha(BETA_CAP, RFREE, CRRA, GAMMA_COLLEGE, LIVPRB,
                     np.array([1.0, -0.5]), np.array([0.5, 0.5]))


# --------------------------------------------------------------------------
# measured_alpha
# --------------------------------------------------------------------------

def test_measured_alpha_recovers_pareto():
    """Synthetic pure-Pareto(1.6) sample: slope recovery within 5% (brief's
    tolerance; the deterministic quantile construction gets ~1%)."""
    alpha_true = 1.6
    a, w = _pareto_sample(alpha_true, 20_000)
    alpha_hat = measured_alpha(a, w, 2.0, 50.0)
    assert abs(alpha_hat - alpha_true) / alpha_true <= 0.05, alpha_hat


def test_measured_alpha_weight_invariance():
    """Unnormalized weights must give the identical slope (ccdf is built on
    normalized weights internally)."""
    a, w = _pareto_sample(2.2, 5_000)
    assert measured_alpha(a, w, 2.0, 20.0) == pytest.approx(
        measured_alpha(a, 7.3 * w, 2.0, 20.0), rel=1e-12)


def test_measured_alpha_thin_window_raises():
    a, w = _pareto_sample(1.6, 1_000)
    with pytest.raises(ValueError, match="too thin"):
        measured_alpha(a, w, 1e6, 2e6)  # window beyond the sample: 0 knots
    with pytest.raises(ValueError, match="lo"):
        measured_alpha(a, w, 50.0, 2.0)  # inverted window


# --------------------------------------------------------------------------
# atom_alpha resolver (standing rule: measured primary, kesten prior/fallback)
# --------------------------------------------------------------------------

def test_atom_alpha_measured_primary():
    a, w = _pareto_sample(1.6, 20_000)
    alpha, source = atom_alpha(*LEDGER, a=a, w=w, lo=2.0, hi=50.0)
    assert source == "measured"
    assert alpha == pytest.approx(measured_alpha(a, w, 2.0, 50.0), rel=1e-12)


def test_atom_alpha_kesten_prior_without_sample():
    alpha, source = atom_alpha(*LEDGER)
    assert source == "kesten-prior"
    assert alpha == pytest.approx(kesten_alpha(*LEDGER), rel=1e-12)


def test_atom_alpha_falls_back_on_empty_window():
    a, w = _pareto_sample(1.6, 1_000)
    alpha, source = atom_alpha(*LEDGER, a=a, w=w, lo=1e6, hi=2e6)
    assert source.startswith("kesten-fallback(")
    assert alpha == pytest.approx(kesten_alpha(*LEDGER), rel=1e-12)


def test_atom_alpha_both_routes_failing_raises():
    a, w = _pareto_sample(1.6, 1_000)
    with pytest.raises(ValueError, match="both routes failed"):
        # empty window AND L=1 positive-drift ledger: no route left
        atom_alpha(BETA_CAP, RFREE, CRRA, GAMMA_COLLEGE, 1.0,
                   PSI_ATOMS, PSI_PMV, a=a, w=w, lo=1e6, hi=2e6)


# --------------------------------------------------------------------------
# atom_dist_top (R-b wealth-quantile law)
# --------------------------------------------------------------------------

def test_atom_dist_top_closed_form_anchors():
    # X = (C/eps)^(1/(alpha-1)): exact hand-checkable anchors
    assert atom_dist_top(2.0, 1.0, 0.01) == pytest.approx(100.0)
    assert atom_dist_top(3.0, 4.0, 0.01) == pytest.approx(20.0)


def test_atom_dist_top_monotonicities():
    """Tighter budget -> taller top; fatter tail (alpha closer to 1) -> taller
    top.  Both are the plan's qualitative laws (halving eps costs ~4-10x in
    top at deep-tail exponents)."""
    tops_eps = [atom_dist_top(1.5, 0.05, e) for e in (0.04, 0.02, 0.01)]
    assert tops_eps[0] < tops_eps[1] < tops_eps[2]
    tops_alpha = [atom_dist_top(al, 0.05, 0.02) for al in (1.3, 1.5, 2.17)]
    assert tops_alpha[0] > tops_alpha[1] > tops_alpha[2]


def test_atom_dist_top_guards():
    with pytest.raises(ValueError, match="alpha > 1"):
        atom_dist_top(1.0, 0.05, 0.02)  # infinite-mean tail: no finite top
    with pytest.raises(ValueError, match="alpha > 1"):
        atom_dist_top(0.9, 0.05, 0.02)
    with pytest.raises(ValueError, match="eps"):
        atom_dist_top(1.5, 0.05, 0.0)
    with pytest.raises(ValueError, match="C_calib"):
        atom_dist_top(1.5, -1.0, 0.02)


# --------------------------------------------------------------------------
# equiprobable helper
# --------------------------------------------------------------------------

def test_equiprobable_mean_one_exact():
    for n in (2, 7, 51):
        atoms, pmv = equiprobable_mean_one_lognormal(SIGMA_PSI_SQ, n)
        assert atoms.shape == (n,) and pmv.shape == (n,)
        assert float(pmv @ atoms) == pytest.approx(1.0, abs=1e-12)  # E[psi]=1
        assert np.all(np.diff(atoms) > 0)  # strictly increasing atoms
    atoms, pmv = equiprobable_mean_one_lognormal(0.0, 3)  # degenerate spread
    assert np.allclose(atoms, 1.0) and float(pmv.sum()) == pytest.approx(1.0)
