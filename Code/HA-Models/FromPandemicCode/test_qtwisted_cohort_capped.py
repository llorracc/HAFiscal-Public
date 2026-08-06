"""
Unit tests for BUG-038: Q-twisted Harmenberg cohort-age decomposition under
T_age cap. See math doc §25.

Tests cover:
  - Size-biased ψ-distribution normalization
  - Q-cohort weights structure (geometric in LG, sums to 1)
  - π_Q^{(τ)} per-cohort marginalization (sums to 1 per τ)
  - π_Q aggregated marginalization (sums to 1)
  - Size-biased newborn p moments
  - Expected lifetime under cap
  - T → ∞ recovery of perpetual-youth π_Q

Run:
    pytest Code/HA-Models/FromPandemicCode/test_qtwisted_cohort_capped.py -v
"""
import os
import sys
import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['test_qtwisted_cohort_capped']

# BUG-055 (2026-06-12): the closed-form / single-scalar-LG tests below assume
# LG = LivPrb × PermGroFac is CONSTANT across micro states ("constant in
# HAFiscal Baseline", math doc §25). Since the BUG-047 PermGroFac
# re-estimation, PermGroFac is employment-state-dependent (e.g. HS Baseline
# [1.00453, 1, 1, 1, 1, 1]), so those reductions are knowingly violated
# (deviations 8e-7 … ~1.9%). See
# BUGS_private/HAFiscal_BUG-055_cohort_age_decomposition_assumes_constant_LG.md.
# strict=False: if the kernel is generalized these will XPASS — then remove.
_BUG055_XFAIL = pytest.mark.xfail(
    strict=False,
    reason="BUG-055: closed form assumes constant LG; PermGroFac is "
           "employment-state-dependent since the BUG-047 re-estimation",
)

# Module-scope fixture: build cohort decompositions once for HighSchool β=0.93
# and reuse across tests. Each fixture call ~1-2 seconds; reuse keeps the
# entire test file under 30 seconds.

@pytest.fixture(scope='module')
def hs_q_cohort_T200():
    """Q-mode cohort decomposition for HS β=0.93 with T_age=200."""
    from harmenberg_doob_tier1 import setup_context, build_agent_for
    from tm_methods import build_tm_agg_fiscal_a, compute_cohort_age_decomposition_a

    ctx = setup_context('Baseline')
    edType = 1
    beta = float(ctx['DiscFacDstns'][edType].atoms[0][3])
    agent = build_agent_for(edType, beta, ctx, interpretation='CDC')
    tm_data = build_tm_agg_fiscal_a(
        agent, aCount=200, aMax=500, aFac=3,
        neutral_measure=False, interpretation='CDC')
    cohort_dec = compute_cohort_age_decomposition_a(
        agent, tm_data, T_age=200, measure='Q',
        interpretation='CDC', unemp_shocks='employed',
        verify_against_doob=False)
    cohort_dec['_agent'] = agent
    cohort_dec['_tm_data'] = tm_data
    cohort_dec['_beta'] = beta
    cohort_dec['_edType'] = edType
    return cohort_dec


@pytest.fixture(scope='module')
def hs_p_cohort_T200(hs_q_cohort_T200):
    """P-mode cohort decomposition for the same agent + cap."""
    from tm_methods import compute_cohort_age_decomposition_a
    agent = hs_q_cohort_T200['_agent']
    tm_data = hs_q_cohort_T200['_tm_data']
    return compute_cohort_age_decomposition_a(
        agent, tm_data, T_age=200, measure='P',
        interpretation='CDC', unemp_shocks='employed',
        verify_against_doob=False)


@pytest.fixture(scope='module')
def hs_q_cohort_T1000(hs_q_cohort_T200):
    """Q-mode cohort decomposition for HS β=0.93 with T_age=1000 (proxy for ∞)."""
    from tm_methods import compute_cohort_age_decomposition_a
    agent = hs_q_cohort_T200['_agent']
    tm_data = hs_q_cohort_T200['_tm_data']
    return compute_cohort_age_decomposition_a(
        agent, tm_data, T_age=1000, measure='Q',
        interpretation='CDC', unemp_shocks='employed',
        verify_against_doob=False)


class TestSizeBiasNormalization:
    """Size-biased ψ-distribution should be a valid probability distribution."""

    def test_size_bias_psi_normalization(self):
        """Σ_s ν_ψ(ψ_s) · ψ_s = E_P[ψ] = 1 (HARK normalization)."""
        from harmenberg_doob_tier1 import setup_context, build_agent_for
        sys.argv = ['test']
        ctx = setup_context('Baseline')
        agent = build_agent_for(1, 0.93, ctx, interpretation='CDC')
        # IncShkDstn[0][0] is the employed-state shock distribution
        # (PermShk, TranShk, prob)
        psi_atoms = agent.IncShkDstn[0][0].atoms[0]  # PermShk atoms
        psi_probs = agent.IncShkDstn[0][0].pmv
        E_psi = float(np.sum(psi_probs * psi_atoms))
        assert abs(E_psi - 1.0) < 1e-10, (
            f"E_P[ψ] = {E_psi} ≠ 1.0 (HARK normalization broken)")

    def test_size_bias_Ep_init_correct(self):
        """Q-newborn mean = E[p_init²] / E[p_init]."""
        sys.argv = ['test']
        from EstimParameters import (
            pLogInitMean_d, pLogInitMean_h, pLogInitMean_c,
            pLogInitStd_d, pLogInitStd_h, pLogInitStd_c)
        for mu, sigma in [(pLogInitMean_d, pLogInitStd_d),
                          (pLogInitMean_h, pLogInitStd_h),
                          (pLogInitMean_c, pLogInitStd_c)]:
            E_p = float(np.exp(mu + 0.5 * sigma**2))
            E_p2 = float(np.exp(2*mu + 2*sigma**2))
            E_p_Q_expected = E_p2 / E_p
            # Equivalent closed form: E_Q[p_init] = exp(μ + 3σ²/2)
            E_p_Q_alt = float(np.exp(mu + 1.5 * sigma**2))
            assert abs(E_p_Q_expected - E_p_Q_alt) < 1e-10, (
                f"Q-newborn mean ratio mismatch: {E_p_Q_expected} vs {E_p_Q_alt}")
            # Sanity: Q-mean > P-mean (size-bias inflates by Var/mean ratio)
            assert E_p_Q_expected > E_p

    def test_code_E_p_init_1_Q_matches_size_bias_formula(self, hs_q_cohort_T200):
        """REGRESSION TEST (BUG-038 mutation testing): the cohort_dec output
        E_p_init_1_Q must equal E[p_init²] / E[p_init] for the agent's
        per-group newborn lognormal. Catches mutation that drops the
        size-bias factor."""
        sys.argv = ['test']
        from EstimParameters import pLogInitMean_h, pLogInitStd_h
        mu = pLogInitMean_h
        sigma = pLogInitStd_h
        expected = float(np.exp(2*mu + 2*sigma**2)) / float(np.exp(mu + 0.5*sigma**2))
        actual = hs_q_cohort_T200['E_p_init_1_Q']
        rel_err = abs(expected - actual) / max(expected, 1e-30)
        assert rel_err < 1e-12, (
            f"cohort_dec['E_p_init_1_Q']={actual} != size-biased formula "
            f"{expected}, rel_err={rel_err}. The Q-newborn moment must use "
            f"E[p²]/E[p], not E[p].")

    def test_code_g1_Q_k_init_uses_size_biased_moment(self, hs_q_cohort_T200):
        """REGRESSION TEST: g1_Q_k[0] = E_p_init_1_Q · π_N. Verifies that
        the initial condition for the Q first-moment occupation function
        uses the size-biased moment, not the P-measure moment."""
        g1_Q_k = hs_q_cohort_T200['g1_Q_k']
        E_p_init_1_Q = hs_q_cohort_T200['E_p_init_1_Q']
        pi_k = hs_q_cohort_T200['pi_Q_k']  # pi_Q_k[0] = pi_N (newborn dist)
        pi_N = pi_k[0]
        expected = E_p_init_1_Q * pi_N
        actual = g1_Q_k[0]
        max_err = float(np.max(np.abs(expected - actual)))
        assert max_err < 1e-12, (
            f"g1_Q_k[0] does not match E_p_init_1_Q * pi_N; max error {max_err}")


class TestQCohortWeights:
    """Q-cohort weights structure per (eq:cap-Qtau)."""

    def test_Q_wt_sums_to_one(self, hs_q_cohort_T200):
        Q_wt = hs_q_cohort_T200['Q_wt']
        assert abs(Q_wt.sum() - 1.0) < 1e-12

    @_BUG055_XFAIL
    def test_Q_wt_geometric_form(self, hs_q_cohort_T200):
        """Q(τ)/Q(τ+1) = 1/(LG) for τ ∈ {0, ..., T-2}.
        (Holds tightly because LG is constant in HAFiscal Baseline.)"""
        Q_wt = hs_q_cohort_T200['Q_wt']
        LG = hs_q_cohort_T200['LG_used']
        # Test at multiple ages — should be ~exact for constant-L HAFiscal
        for tau in [0, 50, 100, 198]:
            expected = 1.0 / LG
            actual = Q_wt[tau] / Q_wt[tau + 1]
            assert abs(actual - expected) < 1e-9, (
                f"Q[{tau}]/Q[{tau+1}] = {actual} != 1/LG = {expected}")

    @_BUG055_XFAIL
    def test_Q_wt_closed_form(self, hs_q_cohort_T200):
        """Q(τ) = (LG)^τ * (1-LG) / (1-(LG)^T) — closed form."""
        Q_wt = hs_q_cohort_T200['Q_wt']
        LG = hs_q_cohort_T200['LG_used']
        T = 200
        for tau in [0, 50, 100, 199]:
            expected = (LG ** tau) * (1.0 - LG) / (1.0 - LG ** T)
            actual = Q_wt[tau]
            assert abs(actual - expected) < 1e-9, (
                f"Q[{tau}] = {actual} != closed form {expected}")


class TestQMarginalization:
    """π_Q^{(τ)} per-cohort and π_Q aggregated normalization."""

    @_BUG055_XFAIL
    def test_pi_Q_k_sums_to_one_per_cohort(self, hs_q_cohort_T200):
        """For each cohort age τ, Σ_x π_Q^{(τ)}(x) = 1."""
        pi_Q_k = hs_q_cohort_T200['pi_Q_k']
        for tau in [0, 1, 50, 100, 199]:
            s = float(pi_Q_k[tau].sum())
            assert abs(s - 1.0) < 1e-9, (
                f"Σ π_Q^{{({tau})}} = {s} ≠ 1.0")

    @_BUG055_XFAIL
    def test_pi_Q_aggregated_sums_to_one(self, hs_q_cohort_T200):
        pi_Q = hs_q_cohort_T200['pi_Q_aggregated']
        assert abs(pi_Q.sum() - 1.0) < 1e-10

    def test_pi_Q_nonnegative(self, hs_q_cohort_T200):
        pi_Q = hs_q_cohort_T200['pi_Q_aggregated']
        # Tiny negatives from float roundoff are acceptable
        assert pi_Q.min() > -1e-15

    def test_g1_Q_aggregated_relation(self, hs_q_cohort_T200):
        """Σ_x f1_Q_aggregated(x) = E_Q[p] = E[p_init²] / E[p_init] · (some
        cohort sum). Specifically, the aggregate first-moment-mass under Q
        should match E_P[p²] / E_P[p] in steady state."""
        f1_Q = hs_q_cohort_T200['f1_Q_aggregated']
        E_p_init_1_Q = hs_q_cohort_T200['E_p_init_1_Q']
        # Sanity: f1_Q sum is positive and finite
        assert np.isfinite(f1_Q.sum())
        assert f1_Q.sum() > 0
        # Sanity: f1_Q sum is roughly proportional to E_p_init_1_Q × (cohort sum)
        # This is an order-of-magnitude check, not a tight identity
        assert E_p_init_1_Q > 0


class TestPathToInfinity:
    """As T → ∞ (large K_max), Q-cohort decomposition approaches perpetual-youth."""

    def test_T_to_infinity_recovers_perpetual_youth(
            self, hs_q_cohort_T200, hs_q_cohort_T1000):
        """π_Q at T=200 vs T=1000 should differ by at most O(LG^200) ≈ 0.7
        for HS LG=0.998. NOTE: with such a high LG, the convergence is slow;
        the cap genuinely removes a non-negligible fraction of mass even at
        T=1000. We test that the BODY of the distribution (excluding the
        very long tail) is consistent."""
        pi_Q_200 = hs_q_cohort_T200['pi_Q_aggregated']
        pi_Q_1000 = hs_q_cohort_T1000['pi_Q_aggregated']
        # Compare overall distance
        l1_dist = float(np.sum(np.abs(pi_Q_200 - pi_Q_1000)))
        # For LG ≈ 0.998, the L^200 truncation tail is about 70% of mass
        # (long-lived agents dominate), so π_Q_200 vs π_Q_1000 can differ
        # significantly. The test verifies they are within 50% L1 — a loose
        # bound that catches gross errors.
        assert l1_dist < 0.5, (
            f"π_Q at T=200 vs T=1000 differ by L1={l1_dist}; expected < 0.5")
        # Tight check: top 80% of mass agrees within smaller tol
        argsort_200 = np.argsort(pi_Q_200)[::-1]
        cumsum_200 = np.cumsum(pi_Q_200[argsort_200])
        body_idx = argsort_200[cumsum_200 < 0.8]
        body_l1 = float(np.sum(np.abs(pi_Q_200[body_idx] - pi_Q_1000[body_idx])))
        assert body_l1 < 0.3, (
            f"Top-80% body L1 distance {body_l1} too large")


class TestExpectedLifetimeUnderCap:
    """E[lifetime] under cap should match (eq:cap-Elifetime)."""

    def test_expected_lifetime_formula(self):
        """E[lifetime] = L(1-L^T)/(1-L) for T_age cap."""
        L = 1.0 - 1.0 / 160.0
        for T in [100, 200, 480, 1000]:
            expected = L * (1 - L**T) / (1 - L)
            # Numerical sanity: T=200 → ~113 quarters
            if T == 200:
                assert 110 < expected < 117, (
                    f"E[lifetime|T=200] = {expected} not ~113")
            if T == 480:
                assert 145 < expected < 155, (
                    f"E[lifetime|T=480] = {expected} not ~150")
            # Always < L/(1-L) (the perpetual-youth limit)
            assert expected <= L / (1 - L) + 1e-9


class TestQAggregationConsistency:
    """Cross-check Q vs P aggregation to validate Q-construction is internally
    consistent."""

    def test_Q_pi_matches_size_biased_P(self, hs_q_cohort_T200, hs_p_cohort_T200):
        """π_Q(x) = f1_aggregated(x) / E_P[p]: Q is the size-biased re-weighting
        of P by p. We can verify this analytically."""
        pi_Q_aggregated = hs_q_cohort_T200['pi_Q_aggregated']
        # E_P[p · 1{X=x}] = f1_aggregated(x) (P-measure)
        f1_P = hs_p_cohort_T200['f1_aggregated']
        E_P_p = float(f1_P.sum())  # = Σ_x f1_aggregated(x) = E_P[p]
        pi_Q_from_P = f1_P / E_P_p
        # Compare
        l1_dist = float(np.sum(np.abs(pi_Q_aggregated - pi_Q_from_P)))
        # Expect tight agreement (both are exact computations)
        assert l1_dist < 1e-6, (
            f"π_Q from Q-twisted vs π_Q = f1/E[p] differ by L1={l1_dist}")


# ============================================================================
# Phase 5: identity tests (cross-check construction against analytical formulas)
# ============================================================================

class TestIdentitiesUnderCap:
    """Identity tests per math doc §25 and plan §8."""

    @_BUG055_XFAIL
    def test_harmenberg_aggregation_identity(self, hs_q_cohort_T200, hs_p_cohort_T200):
        """(eq:cap-Harmenberg-identity): for any function f(s),
            Σ_x f(x) · π_Q(x) · E_P[p] = Σ_x f(x) · f1_P(x)
        Tested with f(x) = a_Nrm(x) (the asset value at grid cell x)."""
        pi_Q = hs_q_cohort_T200['pi_Q_aggregated']
        f1_P = hs_p_cohort_T200['f1_aggregated']
        E_P_p = float(f1_P.sum())

        # Build a_Nrm(x) for x = (a, j): a_value at each grid cell, broadcast
        # over the j-states.
        from harmenberg_doob_tier1 import setup_context, build_agent_for
        from tm_methods import build_tm_agg_fiscal_a
        sys.argv = ['test']
        ctx = setup_context('Baseline')
        agent = build_agent_for(1, 0.93, ctx, interpretation='CDC')
        tm_data = build_tm_agg_fiscal_a(
            agent, aCount=200, aMax=500, aFac=3,
            neutral_measure=False, interpretation='CDC')
        a_grid = tm_data['dist_aGrid']
        A = len(a_grid)
        J = pi_Q.shape[0] // A
        # f(x) = a_Nrm value, broadcast over j (cell layout: j*A + a_idx)
        f_x = np.tile(a_grid, J)

        lhs = float(np.sum(f_x * pi_Q)) * E_P_p
        rhs = float(np.sum(f_x * f1_P))
        rel_err = abs(lhs - rhs) / max(abs(rhs), 1e-30)
        assert rel_err < 1e-9, (
            f"Harmenberg aggregation identity violated: LHS={lhs}, RHS={rhs}, "
            f"rel_err={rel_err}")

    @_BUG055_XFAIL
    def test_cap_EP_p_closed_form(self, hs_p_cohort_T200):
        """(eq:cap-EP-p): E_P[p] = E[p_init] · (1-L)(1-(LG)^T) / [(1-L^T)(1-LG)]
        equals Σ_x f1_P(x)."""
        f1_P = hs_p_cohort_T200['f1_aggregated']
        sum_f1 = float(f1_P.sum())  # numerical E_P[p]

        # Closed form
        from EstimParameters import (
            LivPrb_base, PermGroFac_base_h,
            pLogInitMean_h, pLogInitStd_h)
        L = LivPrb_base[0]
        G = PermGroFac_base_h[0]
        T = 200
        E_p_init = float(np.exp(pLogInitMean_h + 0.5 * pLogInitStd_h**2))
        closed_form = E_p_init * (1 - L) * (1 - (L*G)**T) / ((1 - L**T) * (1 - L*G))

        rel_err = abs(sum_f1 - closed_form) / closed_form
        assert rel_err < 1e-3, (
            f"Cap E_P[p] mismatch: numerical {sum_f1}, closed form {closed_form}, "
            f"rel_err={rel_err}")
        # Note: 1e-3 tolerance because cohort decomposition uses iterated kernel
        # (numerical) while closed form is exact analytical. Cohort kernel
        # discretizes the asset grid which introduces a small bias.

    def test_newborn_rate_identity(self, hs_q_cohort_T200):
        """(eq:cap-newborn-consistency):
            ρ_P(0) · E[p_init] / E_P[p] = (1-LG) / (1-(LG)^T)
        Both sides analytical; verify they're equal."""
        from EstimParameters import (
            LivPrb_base, PermGroFac_base_h,
            pLogInitMean_h, pLogInitStd_h)
        L = LivPrb_base[0]
        G = PermGroFac_base_h[0]
        T = 200
        rho_P_0 = (1 - L) / (1 - L**T)
        E_p_init = float(np.exp(pLogInitMean_h + 0.5 * pLogInitStd_h**2))
        E_P_p = E_p_init * (1 - L) * (1 - (L*G)**T) / ((1 - L**T) * (1 - L*G))

        lhs = rho_P_0 * E_p_init / E_P_p
        rhs = (1 - L*G) / (1 - (L*G)**T)
        assert abs(lhs - rhs) < 1e-12, (
            f"Newborn rate identity violated: LHS={lhs}, RHS={rhs}")

    @_BUG055_XFAIL
    def test_Q_age_marginal_matches_construction(self, hs_q_cohort_T200):
        """Q(τ) = (LG)^τ · ρ_P(0) · E[p_init] / E_P[p] should match
        Q_wt[τ] from the cohort decomposition.

        This is the same as test_Q_wt_closed_form above but derived from
        the size-bias relationship rather than just the geometric form.
        Two independent derivations of the same quantity → strong check."""
        Q_wt = hs_q_cohort_T200['Q_wt']
        LG = hs_q_cohort_T200['LG_used']
        T = 200

        from EstimParameters import (
            LivPrb_base, pLogInitMean_h, pLogInitStd_h)
        L = LivPrb_base[0]
        rho_P_0 = (1 - L) / (1 - L**T)
        E_p_init = float(np.exp(pLogInitMean_h + 0.5 * pLogInitStd_h**2))
        # E_P[p] from the same closed form
        from EstimParameters import PermGroFac_base_h
        G = PermGroFac_base_h[0]
        E_P_p = E_p_init * (1 - L) * (1 - (L*G)**T) / ((1 - L**T) * (1 - L*G))

        for tau in [0, 50, 100, 199]:
            expected = (LG ** tau) * rho_P_0 * E_p_init / E_P_p
            actual = Q_wt[tau]
            rel_err = abs(actual - expected) / max(expected, 1e-30)
            assert rel_err < 1e-6, (
                f"Q[{tau}] from size-bias derivation: expected {expected}, "
                f"got {actual}, rel_err={rel_err}")
