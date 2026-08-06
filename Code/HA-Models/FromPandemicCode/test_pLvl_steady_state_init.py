"""Tests for the analytic pLvl steady-state init.

Covers ``tm_methods.sample_pLvl_steady_state`` /
``tm_methods.pLvl_steady_state_moments`` / ``tm_methods._pLvl_mixture_components``
(employed-only marginal, HAFISCAL_MC_PLVL_INIT=analytic_employed) and the
unemployment-aware ``_pLvl_markov_mixture_components`` /
``compute_log_p_moments_exact`` path (HAFISCAL_MC_PLVL_INIT=analytic_markov,
the default). See
conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md.

A lightweight synthetic agent carries exactly the attributes the mixture math
reads, so these tests are fast and don't require a full economy solve.
"""
import os
import sys
import types

import numpy as np
import pytest

_THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS)
sys.path.insert(0, os.path.dirname(_THIS))

from tm_methods import (  # noqa: E402
    _pLvl_markov_mixture_components,
    _pLvl_markov_moment_recursion,
    _pLvl_mixture_components,
    compute_log_p_moments_exact,
    compute_pLvl_distribution,
    pLvl_steady_state_moments,
    sample_pLvl_conditional_markov,
    sample_pLvl_steady_state,
)


def _make_agent(*, G_emp=1.01, G_unemp=1.0, LivPrb=0.99, T_age=200,
                pLogInitMean=0.0, pLogInitStd=0.3, log_psi=0.1, Urate=0.05):
    """Synthetic agent with the attributes the pLvl mixture math reads.

    A symmetric 2-point perm-shock distribution at log_psi = ±a gives an
    exact Var[log psi] = a**2 (so the analytic variance is known).
    """
    a = log_psi
    dstn = types.SimpleNamespace(
        atoms=[np.array([np.exp(-a), np.exp(a)])],
        pmv=np.array([0.5, 0.5]),
    )
    return types.SimpleNamespace(
        LivPrb=[[LivPrb]],
        T_age=T_age,
        PermGroFac=[np.array([G_emp, G_unemp])],
        pLogInitMean=pLogInitMean,
        pLogInitStd=pLogInitStd,
        IncShkDstn=[[dstn]],
        perm_shocks_during_unemployment=False,
        Urate_normal=Urate,
    )


def test_moments_match_stratified_sample():
    agent = _make_agent()
    rng = np.random.RandomState(0)
    N = 200_000
    p = sample_pLvl_steady_state(agent, N, rng,
                                 employed_only=True, method="stratified")
    m = pLvl_steady_state_moments(agent, employed_only=True)

    logp = np.log(p)
    assert np.mean(logp) == pytest.approx(m["E_logp"], abs=2e-3)
    assert np.var(logp) == pytest.approx(m["Var_logp"], rel=2e-2)
    # E[p] is heavy-tailed; stratified inversion still tracks it closely.
    assert np.mean(p) == pytest.approx(m["E_p"], rel=3e-2)


def test_moments_match_compute_pLvl_distribution():
    """The closed-form moments must agree with the independent binned-density
    discretization in compute_pLvl_distribution (pins the shared component math
    / refactor)."""
    agent = _make_agent()
    grid, w = compute_pLvl_distribution(agent, n_points=8192, unemployment_rate=0.0)
    Ep_binned = float(np.dot(w, grid))
    m = pLvl_steady_state_moments(agent, employed_only=True)
    assert Ep_binned == pytest.approx(m["E_p"], rel=1e-2)


def test_n_distinct_values():
    agent = _make_agent()
    rng = np.random.RandomState(1)
    N = 5000
    p = sample_pLvl_steady_state(agent, N, rng,
                                 employed_only=True, method="stratified")
    assert p.shape == (N,)
    assert len(np.unique(p)) == N  # stratified quantiles -> all distinct


def test_returned_order_is_permuted():
    """Stratified quantiles are monotone; the returned array must be shuffled
    (so pLvl attaches to agents independently of their (j, aNrm) draw)."""
    agent = _make_agent()
    rng = np.random.RandomState(2)
    N = 5000
    p = sample_pLvl_steady_state(agent, N, rng,
                                 employed_only=True, method="stratified")
    assert not np.all(np.diff(p) >= 0)        # not sorted ascending
    assert not np.all(np.diff(p) <= 0)        # not sorted descending


def test_same_multiset_different_order():
    """Two RNGs give the same stratified value multiset but different orders."""
    agent = _make_agent()
    N = 4000
    p1 = sample_pLvl_steady_state(agent, N, np.random.RandomState(3),
                                  employed_only=True, method="stratified")
    p2 = sample_pLvl_steady_state(agent, N, np.random.RandomState(4),
                                  employed_only=True, method="stratified")
    np.testing.assert_allclose(np.sort(p1), np.sort(p2), rtol=0, atol=0)
    assert not np.array_equal(p1, p2)


def _Ep(agent, u):
    w, mu, sig = _pLvl_mixture_components(agent, u)
    return float(np.sum(w * np.exp(mu + sig ** 2 / 2.0)))


def test_employed_only_raises_growth():
    """With G_unemp < G_emp, the employed-only mixture (u=0) has strictly higher
    E[p] than one that blends in an explicit positive unemployment rate (which
    lowers per-period permanent-income growth)."""
    agent = _make_agent(G_emp=1.01, G_unemp=1.0)
    assert _Ep(agent, 0.0) > _Ep(agent, 0.05)


def test_employed_only_uses_zero_unemployment():
    """employed_only=True must equal an explicit unemployment_rate=0.0, and must
    differ from the realistic explicit-Urate blend (lower growth -> lower E[p])."""
    agent = _make_agent(Urate=0.05)
    m_emp = pLvl_steady_state_moments(agent, employed_only=True)
    assert m_emp["E_p"] == pytest.approx(_Ep(agent, 0.0), rel=0, abs=0)
    assert m_emp["E_p"] > _Ep(agent, agent.Urate_normal)


def test_random_method_distinct_and_in_range():
    agent = _make_agent()
    rng = np.random.RandomState(5)
    N = 5000
    p = sample_pLvl_steady_state(agent, N, rng,
                                 employed_only=True, method="random")
    assert p.shape == (N,)
    assert np.all(p > 0)
    # random draws should also be (almost surely) all distinct
    assert len(np.unique(p)) == N


def test_invalid_method_raises():
    agent = _make_agent()
    rng = np.random.RandomState(6)
    with pytest.raises(ValueError):
        sample_pLvl_steady_state(agent, 100, rng, method="bogus")


# ----------------------------------------------------------------------------
# Unemployment-aware (analytic_markov) path
# ----------------------------------------------------------------------------


def _make_markov_agent(*, G_emp=1.01, G_unemp=1.0, LivPrb=0.99, T_age=200,
                       pLogInitMean=0.0, pLogInitStd=0.3, log_psi=0.1,
                       p_eu=0.05, p_ue=0.5):
    """Synthetic agent for the full Markov (with-unemployment) recursion.

    A 2-state base chain (employed j=0, unemployed j=1) with employed perm
    shocks (symmetric ±log_psi, exact Var=log_psi**2) and no unemployed shock
    (PermShk=1). The stationary u is set by (p_eu, p_ue).
    """
    a = log_psi
    d_emp = types.SimpleNamespace(
        atoms=[np.array([np.exp(-a), np.exp(a)])], pmv=np.array([0.5, 0.5]))
    d_un = types.SimpleNamespace(atoms=[np.array([1.0])], pmv=np.array([1.0]))
    Mrkv = np.array([[1.0 - p_eu, p_eu], [p_ue, 1.0 - p_ue]])
    return types.SimpleNamespace(
        LivPrb=[[LivPrb]], T_age=T_age,
        PermGroFac=[np.array([G_emp, G_unemp])],
        pLogInitMean=pLogInitMean, pLogInitStd=pLogInitStd,
        IncShkDstn=[[d_emp, d_un]],
        num_base_MrkvStates=2,
        MrkvArray=[Mrkv],
    )


def test_markov_mixture_reproduces_exact_moments():
    """The per-(age,state) markov mixture must reproduce the exact recursion's
    mean/var of log p to machine precision (that is the whole point — it is a
    moment-exact Gaussian mixture of compute_log_p_moments_exact)."""
    agent = _make_markov_agent()
    exact = compute_log_p_moments_exact(agent)
    w, mu, sig = _pLvl_markov_mixture_components(agent)
    assert w.sum() == pytest.approx(1.0, abs=1e-12)
    mean = float(np.sum(w * mu))
    var = float(np.sum(w * (sig ** 2 + mu ** 2)) - mean ** 2)
    assert mean == pytest.approx(exact["mean_log_p_exact"], abs=1e-10)
    assert var == pytest.approx(exact["var_log_p_exact"], abs=1e-10)


def test_markov_moments_helper_matches_exact():
    agent = _make_markov_agent()
    exact = compute_log_p_moments_exact(agent)
    m = pLvl_steady_state_moments(agent, pLvl_dist="markov")
    assert m["E_logp"] == pytest.approx(exact["mean_log_p_exact"], abs=1e-10)
    assert m["Var_logp"] == pytest.approx(exact["var_log_p_exact"], abs=1e-10)
    assert m["E_p"] > 0.0 and m["Var_p"] > 0.0


def test_markov_sampler_matches_moments():
    agent = _make_markov_agent()
    exact = compute_log_p_moments_exact(agent)
    rng = np.random.RandomState(0)
    N = 200_000
    p = sample_pLvl_steady_state(agent, N, rng,
                                 pLvl_dist="markov", method="stratified")
    logp = np.log(p)
    assert np.mean(logp) == pytest.approx(exact["mean_log_p_exact"], abs=3e-3)
    assert np.var(logp) == pytest.approx(exact["var_log_p_exact"], rel=2e-2)


def test_markov_sampler_distinct_and_permuted():
    agent = _make_markov_agent()
    rng = np.random.RandomState(1)
    N = 5000
    p = sample_pLvl_steady_state(agent, N, rng,
                                 pLvl_dist="markov", method="stratified")
    assert p.shape == (N,)
    assert len(np.unique(p)) == N
    assert not np.all(np.diff(p) >= 0)
    assert not np.all(np.diff(p) <= 0)


def test_pLvl_dist_overrides_employed_only():
    """pLvl_dist takes precedence over the legacy employed_only switch."""
    agent = _make_markov_agent()
    w_m, mu_m, _ = _pLvl_markov_mixture_components(agent)
    m_markov = pLvl_steady_state_moments(agent, employed_only=True,
                                         pLvl_dist="markov")
    exact = compute_log_p_moments_exact(agent)
    assert m_markov["E_logp"] == pytest.approx(exact["mean_log_p_exact"], abs=1e-10)


def test_invalid_pLvl_dist_raises():
    agent = _make_markov_agent()
    rng = np.random.RandomState(7)
    with pytest.raises(ValueError):
        sample_pLvl_steady_state(agent, 100, rng, pLvl_dist="bogus")


# --------------------------------------------------------------------------
# Conditional (per-(age,state)) markov seed: sample_pLvl_conditional_markov
# --------------------------------------------------------------------------

def _draw_ages_states_from_recursion(agent, N, rng):
    """Draw (age, state) from the recursion's TRUE joint weights
    w_{n,j} = age_prb(n)·π_{n,j}. ages returned in HARK's 1..T_age convention."""
    age_prbs, pi_arr, _m, _v = _pLvl_markov_moment_recursion(agent)
    T, J = pi_arr.shape
    joint = (age_prbs[:, None] * pi_arr).ravel()
    joint /= joint.sum()
    flat = rng.choice(T * J, size=N, p=joint)
    n_idx = flat // J
    j_idx = flat % J
    return (n_idx + 1).astype(int), j_idx.astype(int)


def test_conditional_markov_shape_and_positive():
    agent = _make_markov_agent()
    rng = np.random.RandomState(0)
    N = 5000
    ages = rng.randint(1, agent.T_age + 1, size=N)
    states = rng.randint(0, agent.num_base_MrkvStates, size=N)
    p = sample_pLvl_conditional_markov(agent, ages, states, rng)
    assert p.shape == (N,)
    assert np.all(p > 0.0)
    assert np.all(np.isfinite(p))


def test_conditional_markov_aggregate_matches_exact():
    """If (age,state) are drawn from the recursion's own joint, the conditional
    per-cell pLvl draw must reproduce the exact aggregate mean/var of log p —
    i.e. conditioning preserves the marginal that analytic_markov targets."""
    agent = _make_markov_agent()
    exact = compute_log_p_moments_exact(agent)
    rng = np.random.RandomState(1)
    N = 400_000
    ages, states = _draw_ages_states_from_recursion(agent, N, rng)
    p = sample_pLvl_conditional_markov(agent, ages, states, rng)
    logp = np.log(p)
    assert np.mean(logp) == pytest.approx(exact["mean_log_p_exact"], abs=3e-3)
    assert np.var(logp) == pytest.approx(exact["var_log_p_exact"], rel=2e-2)


def test_conditional_markov_correlates_with_age_and_state():
    """The whole point: conditional draws depend on (age,state). With G_emp>1,
    older employed agents have a higher mean log p than younger ones, and (with
    no unemployed growth) employed agents differ from unemployed agents."""
    agent = _make_markov_agent(G_emp=1.02, G_unemp=1.0)
    rng = np.random.RandomState(2)
    N = 100_000
    young = np.full(N, 1, dtype=int)
    old = np.full(N, agent.T_age, dtype=int)
    emp = np.zeros(N, dtype=int)
    p_young = sample_pLvl_conditional_markov(agent, young, emp, rng)
    p_old = sample_pLvl_conditional_markov(agent, old, emp, rng)
    # Older employed cohort has substantially higher mean log p.
    assert np.mean(np.log(p_old)) > np.mean(np.log(p_young)) + 0.5


def test_conditional_markov_is_deterministic_given_rng():
    agent = _make_markov_agent()
    ages = np.array([1, 5, 20, 50, 100])
    states = np.array([0, 1, 0, 1, 0])
    p1 = sample_pLvl_conditional_markov(agent, ages, states,
                                        np.random.RandomState(9))
    p2 = sample_pLvl_conditional_markov(agent, ages, states,
                                        np.random.RandomState(9))
    assert np.array_equal(p1, p2)


def test_conditional_markov_stratified_beats_random_noise():
    """Within a single (age,state) cell, stratification must reproduce the
    cell's log-p mean/var far more tightly than independent normal draws."""
    agent = _make_markov_agent()
    age_prbs, pi_arr, m_arr, v_arr = _pLvl_markov_moment_recursion(agent)
    n0, j0 = 40, 0  # an employed, mid-age cell
    mu = m_arr[n0, j0] / pi_arr[n0, j0]
    var = v_arr[n0, j0] / pi_arr[n0, j0] - mu ** 2
    N = 2000
    ages = np.full(N, n0 + 1, dtype=int)   # age = n+1
    states = np.full(N, j0, dtype=int)
    rng = np.random.RandomState(0)
    p_strat = sample_pLvl_conditional_markov(agent, ages, states, rng,
                                             method="stratified")
    p_rand = sample_pLvl_conditional_markov(agent, ages, states, rng,
                                            method="random")
    err_strat = abs(np.var(np.log(p_strat)) - var)
    err_rand = abs(np.var(np.log(p_rand)) - var)
    # stratified within-cell variance error is an order of magnitude smaller
    assert err_strat < err_rand
    assert err_strat < 0.01 * var
    assert np.mean(np.log(p_strat)) == pytest.approx(mu, abs=1e-6)


def test_conditional_markov_stratified_still_matches_aggregate():
    """Stratified within-cell draw still reproduces the exact aggregate
    mean/var when (age,state) come from the recursion's own joint."""
    agent = _make_markov_agent()
    exact = compute_log_p_moments_exact(agent)
    rng = np.random.RandomState(3)
    N = 400_000
    ages, states = _draw_ages_states_from_recursion(agent, N, rng)
    p = sample_pLvl_conditional_markov(agent, ages, states, rng,
                                       method="stratified")
    logp = np.log(p)
    assert np.mean(logp) == pytest.approx(exact["mean_log_p_exact"], abs=3e-3)
    assert np.var(logp) == pytest.approx(exact["var_log_p_exact"], rel=1e-2)
