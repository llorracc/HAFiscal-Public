"""
Transition Matrix (TM) methods for HAFiscal agents.

Harmenberg neutral measure (Q) for p-linear aggregation:
    E_P[p * f(m)] = E_P[p] * E_Q[f(m)]
    — BST ApndxHarKmenberg, Theorem 1 ("Harmenberg's Method")
    — Harmenberg (2021), JEDynCon 129, 104185
    — math-derive-harm (neutral-identity) in
      history/20260331-mathematical-derivations-harmenberg.md
Output classification (Type A/B/C) for reduced reproduce:
    history/20260402-reduced-run-harmenberg-output-type-map.md
Uncorrected 1D pitfall (physical m-marginal * E[p] ≠ E_P[p*f(m)]):
    Code/HA-Models/Harmenberg-Four-Way-Comparison.ipynb §8j

Provides TM-based alternatives to Monte Carlo simulation for computing
aggregate consumption, income, and other steady-state statistics.

Math reference (shorthand "math-derive"):
    history/20260331-mathematical-derivations-TM-MC-convergence.md
Appendix reference (shorthand "math-derive-appendix"):
    history/20260331-mathematical-derivations-appendix.md
"""

import numpy as np
import os as _os
import time as _time
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from copy import deepcopy
from scipy.stats import norm as _norm
from HARK.utilities import jump_to_grid_1D, make_grid_exp_mult

from income_process_sst import effective_pLvl_growth, effective_perm_shock_variance_periods

# Interpretation single source (BUG-051): resolve/validate the CDC-vs-ESC
# matched-pair regime. The HA-Models dir holds _interpretation.py; ensure it's
# on sys.path (it is at ../ relative to FromPandemicCode), mirroring
# estim_phase2_tm_a.py's import-site pattern.
import sys as _sys_interp
_ha_root_interp = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), '..'))
if _ha_root_interp not in _sys_interp.path:
    _sys_interp.path.insert(0, _ha_root_interp)
from _interpretation import get_interpretation, assert_interpretation

# HAFISCAL_TM_MCOUNT: override the default TM distribution-grid size. On the
# production a-indexed path this is `dist_aGrid_count` (owner ruling 2026-07-25:
# the code parameter was renamed from the M-era `mCount`, which lied about its
# object; the FLAG spelling is retained by owner ruling). On the legacy
# m-indexed kernel (`build_tm_agg_fiscal`) it is the honest `mCount`.
# Used by D-6 to test whether refining the TM aggregation grid (NOT the solver
# grid) shrinks the MC-vs-TM-a multiplier residual. See memory
# project_mc_tm_newborn_timing_asymmetry.md and
# project_mc_tm_bias_decomposition.md.
_HAFISCAL_TM_MCOUNT_DEFAULT = int(_os.environ.get('HAFISCAL_TM_MCOUNT', 50))
if 'HAFISCAL_TM_MCOUNT' in _os.environ:
    print(f'[tm-mcount-override] HAFISCAL_TM_MCOUNT → default dist_aGrid_count '
          f'(legacy m-kernel mCount) = {_HAFISCAL_TM_MCOUNT_DEFAULT}')

# HAFISCAL_TM_AD_TIMING: override TM-a's ad_timing for diagnostic tests.
# 'lagged' (default, matches MC's QE convention): RecState[s-1] for ADF[s]
# 'contemporaneous': RecState[s] for ADF[s] (diagnostic only, see BUG-030)
_HAFISCAL_TM_AD_TIMING = _os.environ.get('HAFISCAL_TM_AD_TIMING', 'lagged').lower()
if 'HAFISCAL_TM_AD_TIMING' in _os.environ:
    print(f'[tm-ad-timing-override] HAFISCAL_TM_AD_TIMING = {_HAFISCAL_TM_AD_TIMING!r}')

# HAFISCAL_TM_CFUNC_OFFSET: which Cratio_path index to use for ADF/cFunc lookup
# at period t (BUG-041 fix; see BUGS_private/HAFiscal_BUG-041_TM_CFunc_cell_offset_one_period.md).
# 'mc' (default, matches QE-published MC convention): use Cratio_path[t-1] for
#      ADF and cFunc-state lookup at period t (one-period lag). At t=0 uses
#      Cratio_path[0] (matches MC's mill_rule special-case for Shk_idx=0).
# 'tm' (legacy TM-a convention; pre-BUG-041 behavior): use Cratio_path[t] for
#      ADF and cFunc-state lookup at period t (no lag). Kept for byte-identical
#      reproduction of pre-fix TM-a output.
_HAFISCAL_TM_CFUNC_OFFSET = _os.environ.get('HAFISCAL_TM_CFUNC_OFFSET', 'mc').lower()
if _HAFISCAL_TM_CFUNC_OFFSET not in ('mc', 'tm'):
    raise ValueError(
        f"HAFISCAL_TM_CFUNC_OFFSET must be 'mc' or 'tm', got "
        f"{_HAFISCAL_TM_CFUNC_OFFSET!r}"
    )
if 'HAFISCAL_TM_CFUNC_OFFSET' in _os.environ:
    print(f'[tm-cfunc-offset-override] HAFISCAL_TM_CFUNC_OFFSET = {_HAFISCAL_TM_CFUNC_OFFSET!r}')
# Full registry of all HAFISCAL_* env flags: Code/HA-Models/docs/ENV_FLAGS.md


def _cratio_for_period(Cratio_path, t, cfunc_offset):
    """Return the scalar Cratio used at period t for ADF and cFunc-state lookup.

    Implements BUG-041 fix. See module-level _HAFISCAL_TM_CFUNC_OFFSET docstring.
    """
    if cfunc_offset == 'mc' and t > 0:
        return float(Cratio_path[t - 1])
    return float(Cratio_path[t])


def compute_E_pLvl_exact(agent, unemployment_rate=None):
    """
    Exact E[pLvl] under HARK's Markov-chain employment.

    Replaces the (1-u) population-weighted-arithmetic-mean growth approximation
    in ``compute_analytical_mean_pLvl`` for the moment-only use case (TM
    aggregation). Uses matrix-iteration recursion analogous to
    ``compute_log_p_moments_exact`` but tracking E[p^1] under Markov-chain
    employment dynamics — exact, no (1-u) collapse, no iid-Bernoulli assumption.

    The (1-u) formula is exact only under iid-Bernoulli employment (where
    `g_eff^n = ((1-u)G+u)^n = E[Π G_t]` by the binomial theorem). Under HAFiscal's
    Markov chain employment (persistent emp→emp transitions ~0.97), the iid
    assumption is violated and the (1-u) approximation introduces a small bias
    that propagates into all TM-aggregate quantities.

    Per-state vector recursion:
      m_n^j  = E[1{j_n=j} · p_n]
      m_{n+1}^{j'} = κ_{j'} · (M^T · m_n)_{j'}
      where κ_j = G_j · E_P[ψ_j]  (per-state per-period growth multiplier)

    Initial (n=0, post-deterministic newborn growth, BUG-003 convention):
      π_0^j = birth_fracs[j]
      m_0^j = π_0^j · E[p_init] · G_j

    Cohort-aggregated under ergodic age distribution π_n^age:
      E[p] = Σ_n π_n^age · Σ_j m_n^j
    """
    LivPrb = agent.LivPrb[0][0]
    # None (HAFISCAL_T_AGE=none) => tolerance-truncated geometric age chain,
    # NOT the legacy 400 bound (which silently discarded ~8% of survivors).
    T_age = effective_age_chain_length(agent.LivPrb[0][0], getattr(agent, 'T_age', 400))

    pLogInitMean = getattr(agent, 'pLogInitMean', getattr(agent, 'pLvlInitMean', 0.0))
    pLogInitStd = getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0))
    E_pLvl_init = np.exp(pLogInitMean + 0.5 * pLogInitStd ** 2)

    J = int(agent.num_base_MrkvStates)
    MrkvBase = np.asarray(agent.MrkvArray[0], dtype=float)[:J, :J]
    PermGroFac_arr = np.asarray(agent.PermGroFac[0], dtype=float)[:J]

    # Per-state E_P[ψ]: integrates the per-state IncShkDstn (employed: mean-1
    # lognormal → E[ψ]=1; unemployed under perm_shocks=off: ψ=1 deterministic;
    # unemployed under perm_shocks=on: lognormal with E[ψ]=1).
    E_psi = np.ones(J)
    for j in range(J):
        d_j = agent.IncShkDstn[0][j]
        psi_j = np.asarray(d_j.atoms[0], dtype=float)
        probs_j = np.asarray(d_j.pmv, dtype=float)
        E_psi[j] = float(np.dot(probs_j, psi_j))

    # Per-state per-period growth multiplier
    kappa = PermGroFac_arr * E_psi

    # Birth-state distribution: ergodic stationary of MrkvBase
    eigvals, eigvecs = np.linalg.eig(MrkvBase.T)
    idx = int(np.argmin(np.abs(eigvals - 1.0)))
    birth_fracs = np.abs(eigvecs[:, idx].real)
    birth_fracs /= birth_fracs.sum()

    # Ergodic age distribution: π_n^age ∝ L^n
    L = LivPrb
    T = int(T_age)
    log_age_prbs = (
        np.log(max(1.0 - L, 1e-300))
        - np.log(max(1.0 - L ** T, 1e-300))
        + np.arange(T) * np.log(max(L, 1e-300))
    )
    age_prbs = np.exp(log_age_prbs)
    age_prbs /= age_prbs.sum()

    # Initial state (n=0): first growth applied (deterministic, no shock per BUG-003)
    pi_n = birth_fracs.copy()
    m_n = pi_n * (E_pLvl_init * PermGroFac_arr)

    # Accumulate cohort-aggregated E[p]
    E_pLvl = age_prbs[0] * float(m_n.sum())

    Mt = MrkvBase.T
    for n in range(1, T):
        m_next = kappa * (Mt @ m_n)
        E_pLvl += age_prbs[n] * float(m_next.sum())
        m_n = m_next

    return float(E_pLvl)


def compute_analytical_mean_pLvl(agent, unemployment_rate=None):
    """
    Compute the analytical E[pLvl] in the stationary cross-section.

    Dispatches to ``compute_E_pLvl_exact`` (Markov-chain matrix-iteration,
    default since 2026-05-06) unless ``HAFISCAL_E_PLVL_MODE=approx`` is set,
    in which case falls back to the (1-u) iid-Bernoulli approximation
    (kept for backward-compat / diagnostic comparison).

    --- Legacy (1-u) approximation, kept below for env-var fallback: ---

    In HARK's sim_one_period, t_age is incremented at the END of the period
    (after get_mortality, get_shocks, get_states, ...).  Newborns start at
    t_age=0 during the period and reach t_age=1 in state_now.  Agents die
    when sim_death checks t_age >= T_age at the START of the next period.
    So the observable t_age in state_now ranges from 1 to T_age.

    We model this as an age Markov chain with T_age states (0..T_age-1),
    where state k corresponds to t_age = k+1 in state_now and has had
    (k+1) applications of PermGroFac:

      E[pLvl | state k] = E[pLvl_init] * g^(k+1)

    where g = (1-u)*G + u is the population-average growth rate accounting
    for the fraction u of unemployed agents whose pLvl does not grow.
    When unemployment_rate is None, g = G (backward-compatible).

    Note: the MC (with HARK's default initialization) has a ~1% bias due to
    cohort echo effects from non-ergodic age initialization; this formula
    gives the true ergodic value.
    """
    _mode = _os.environ.get('HAFISCAL_E_PLVL_MODE', 'exact').lower()
    if _mode == 'exact':
        return compute_E_pLvl_exact(agent, unemployment_rate=unemployment_rate)
    elif _mode != 'approx':
        raise ValueError(
            f"HAFISCAL_E_PLVL_MODE={_mode!r} not recognized. "
            "Valid: 'exact' (default, Markov-chain matrix-iteration) or "
            "'approx' (legacy (1-u) iid-Bernoulli)."
        )
    LivPrb = agent.LivPrb[0][0]
    # SST: g from per-state PermGroFac (see income_process_sst.effective_pLvl_growth)
    g = effective_pLvl_growth(agent, unemployment_rate)

    pLogInitMean = getattr(agent, 'pLogInitMean', getattr(agent, 'pLvlInitMean', 0.0))
    pLogInitStd = getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0))
    # See math-derive-appendix (E-p-init): E[p_init] = exp(mu + sigma^2/2)
    E_pLvl_init = np.exp(pLogInitMean + 0.5 * pLogInitStd**2)

    # None (HAFISCAL_T_AGE=none) => tolerance-truncated geometric age chain,
    # NOT the legacy 400 bound (which silently discarded ~8% of survivors).
    T_age = effective_age_chain_length(agent.LivPrb[0][0], getattr(agent, 'T_age', 400))

    if agent.T_cycle == 1:
        # See math-derive (E-pLvl) and (age-dist):
        # E[pLvl] = E_init * g * C_norm * sum_{k=0}^{T-1} (L*g)^k
        T = T_age
        Lg = LivPrb * g
        if abs(Lg - 1.0) < 1e-12:
            geo_sum = float(T)
        else:
            geo_sum = (1.0 - Lg**T) / (1.0 - Lg)
        C_norm = (1.0 - LivPrb) / (1.0 - LivPrb**T)
        E_pLvl = E_pLvl_init * g * C_norm * geo_sum
    else:
        T = agent.T_cycle
        LivPrb_array = [agent.LivPrb[t][0] for t in range(T)]

        AgeMarkov = np.zeros((T + 1, T + 1))
        for t in range(T):
            p = LivPrb_array[t]
            AgeMarkov[t, t + 1] = p
            AgeMarkov[t, 0] = 1.0 - p
        AgeMarkov[T, 0] = 1.0

        AgeMarkovT = AgeMarkov.T
        vals, vecs = np.linalg.eig(AgeMarkovT)
        idx = np.argmin(np.abs(np.abs(vals) - 1.0))
        age_prbs = np.real(vecs[:, idx])
        age_prbs = np.maximum(age_prbs, 0.0)
        age_prbs /= age_prbs.sum()

        growth_factors = np.array([g**t for t in range(T + 1)])
        E_pLvl = E_pLvl_init * g * np.dot(age_prbs, growth_factors)

    return E_pLvl


def _pLvl_mixture_components(agent, unemployment_rate=None):
    """(age_prbs, mu_k, sigma_k) of the ergodic pLvl lognormal mixture.

    The ergodic pLvl distribution is a mixture of lognormals, one per age
    cohort k=0,...,T_age-1: log(pLvl | age=k) ~ N(mu_k, sigma_k^2), weighted by
    the truncated-geometric ergodic age distribution pi(k) ∝ LivPrb^k. This is
    the single source of the component math (so the discrete density in
    ``compute_pLvl_distribution``, the steady-state sampler, and the closed-form
    moments cannot drift apart). Conventions:
      - BUG-003: the newborn's first growth step is deterministic, so a cohort
        with HARK t_age = k+1 has accumulated k stochastic permanent shocks
        (growth uses (k+1)·log g; variance uses k·sigma_psi^2).
      - BUG-019: when perm shocks don't fire during unemployment, variance
        accrues only over employed periods (the (1-u) scaling in
        ``effective_perm_shock_variance_periods``).
    Pass unemployment_rate=0.0 for the EMPLOYED-ONLY mixture. NOTE: None is NOT
    employed-only — it falls back to agent.Urate_normal.
    See conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md.
    """
    LivPrb = agent.LivPrb[0][0]
    log_g = np.log(effective_pLvl_growth(agent, unemployment_rate))

    pLogInitMean = getattr(agent, 'pLogInitMean', getattr(agent, 'pLvlInitMean', 0.0))
    pLogInitStd = getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0))

    # None (HAFISCAL_T_AGE=none) => tolerance-truncated geometric age chain,
    # NOT the legacy 400 bound (which silently discarded ~8% of survivors).
    T_age = effective_age_chain_length(agent.LivPrb[0][0], getattr(agent, 'T_age', 400))

    sigma_psi_sq = _get_perm_shock_var(agent)

    # See math-derive (age-dist): pi(k) = (1-L)/(1-L^T) * L^k
    L = LivPrb
    T = T_age
    log_age_prbs = np.log(1.0 - L) - np.log(1.0 - L**T) + np.arange(T) * np.log(L)
    age_prbs = np.exp(log_age_prbs)
    age_prbs /= age_prbs.sum()

    # See math-derive-appendix (pLvl-cohort): per-cohort lognormal params.
    ks = np.arange(T)
    eff_shock_periods = effective_perm_shock_variance_periods(
        ks, agent, unemployment_rate)
    mu_k = pLogInitMean + (ks + 1) * log_g - eff_shock_periods * sigma_psi_sq / 2.0
    var_k = pLogInitStd**2 + eff_shock_periods * sigma_psi_sq
    sigma_k = np.sqrt(var_k)
    return age_prbs, mu_k, sigma_k


def compute_pLvl_distribution(agent, n_points=200, unemployment_rate=None):
    """
    Compute a discrete approximation of the ergodic pLvl distribution.

    The distribution is a mixture of lognormals, one per age cohort:
      log(pLvl | age=k) ~ N(mu_k, sigma_k^2)
    where k=0,...,T_age-1, weighted by the ergodic age distribution.

    At age state k the agent has had (k+1) applications of PermGroFac.
    With the newborn fix (BUG-003), the first application is deterministic
    (no idiosyncratic shock), so there are k periods of accumulated
    permanent-shock variance.

    When unemployment_rate is provided, the per-period growth rate is
    g = (1-u)*G + u instead of G, correcting for the fraction u of
    agents whose pLvl doesn't grow while unemployed.

    Parameters
    ----------
    agent : AggFiscalType
    n_points : int
        Number of grid points for the discrete approximation.
    unemployment_rate : float or None
        Ergodic unemployment rate. When None, uses G (backward-compatible).

    Returns
    -------
    pLvl_grid : np.ndarray, shape (n_points,)
        Grid of pLvl values.
    weights : np.ndarray, shape (n_points,)
        Probability weights summing to 1.
    """
    age_prbs, mu_k, sigma_k = _pLvl_mixture_components(agent, unemployment_rate)
    T = len(age_prbs)

    # Determine grid bounds in log-pLvl space (cover 0.1% to 99.9%)
    log_lo = np.min(mu_k - 4.0 * sigma_k)
    log_hi = np.max(mu_k + 4.0 * sigma_k)
    log_p_grid = np.linspace(log_lo, log_hi, n_points)
    dp = log_p_grid[1] - log_p_grid[0]

    # Evaluate mixture density in log space:
    #   f(y) = sum_k age_prbs[k] * Normal(y; mu_k, sigma_k^2)
    density = np.zeros(n_points)
    for k in range(T):
        if age_prbs[k] < 1e-15:
            continue
        density += age_prbs[k] * _norm.pdf(log_p_grid, mu_k[k], sigma_k[k])

    weights = density * dp
    total = weights.sum()
    if total > 0:
        weights /= total

    pLvl_grid = np.exp(log_p_grid)
    return pLvl_grid, weights


def _get_perm_shock_var(agent):
    """Extract Var[log(PermShk)] from the employed IncShkDstn."""
    d = agent.IncShkDstn[0][0]  # employed state distribution
    perm_shks = d.atoms[0]
    log_psi = np.log(perm_shks)
    E_log = np.dot(d.pmv, log_psi)
    E_log2 = np.dot(d.pmv, log_psi**2)
    return E_log2 - E_log**2


def _pLvl_components_select(agent, *, employed_only=True, pLvl_dist=None):
    """Return ``(weights, mu, sigma)`` mixture components for the requested
    ergodic pLvl distribution.

    ``pLvl_dist`` (takes precedence over ``employed_only`` when given):
      - ``'employed'``: employed-only lognormal-per-age mixture (no
        unemployment) — ``_pLvl_mixture_components(agent, 0.0)``.
      - ``'blended'``: legacy per-age mixture with the stationary u folded into
        growth/variance — ``_pLvl_mixture_components(agent, None)``.
      - ``'markov'``: unemployment-aware per-(age,state) Gaussian mixture from
        the exact Markov recursion — ``_pLvl_markov_mixture_components(agent)``.

    When ``pLvl_dist is None`` the legacy ``employed_only`` switch maps to
    ``'employed'`` (True) or ``'blended'`` (False), preserving prior behavior.
    """
    if pLvl_dist is None:
        pLvl_dist = 'employed' if employed_only else 'blended'
    if pLvl_dist == 'employed':
        return _pLvl_mixture_components(agent, 0.0)
    if pLvl_dist == 'blended':
        return _pLvl_mixture_components(agent, None)
    if pLvl_dist == 'markov':
        return _pLvl_markov_mixture_components(agent)
    raise ValueError(
        f"pLvl_dist={pLvl_dist!r} invalid; expected 'employed', 'blended', "
        "or 'markov'.")


def sample_pLvl_steady_state(agent, N, rng, *, employed_only=True,
                             pLvl_dist=None, method="stratified", n_grid=4096):
    """Draw ``N`` pLvl values approximating the ergodic pLvl steady-state.

    Used to seed the MC cross-section's permanent-income marginal at (an
    approximation to) its steady state, alongside the TM-a (j, aNrm) seed.

    ``pLvl_dist`` selects which ergodic distribution to sample ('employed',
    'blended', or the unemployment-aware 'markov'); see
    ``_pLvl_components_select``. When ``pLvl_dist is None`` (default),
    ``employed_only=True`` forces the EMPLOYED-ONLY mixture of
    conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md
    (G_emp growth, employed perm-shock variance, every age period employed).

    ``method``:
      - ``'stratified'`` (default): invert the exact mixture CDF at the
        stratified quantiles (i-0.5)/N. Low discretization error (O(1/N) vs the
        O(1/sqrt(N)) of random draws) and N distinct values that reproduce the
        analytic distribution. The returned array is then randomly permuted so
        the values attach to MC agents independently of their (j, aNrm) draw
        (the pLvl ⊥ aNrm modeling assumption).
      - ``'random'``: N inverse-CDF draws at ``rng.uniform()`` (literal random
        sampling; higher cross-sectional noise).

    Returns ``pLvl`` of shape (N,), in random order.
    """
    age_prbs, mu_k, sigma_k = _pLvl_components_select(
        agent, employed_only=employed_only, pLvl_dist=pLvl_dist)

    # Exact mixture CDF F(x) = sum_k w_k * Phi((x-mu_k)/sigma_k) on a fine
    # log-pLvl grid, then invert by monotone interpolation.
    sig = np.maximum(sigma_k, 1e-12)
    log_lo = float(np.min(mu_k - 8.0 * sig))
    log_hi = float(np.max(mu_k + 8.0 * sig))
    xs = np.linspace(log_lo, log_hi, int(n_grid))
    cdf = np.zeros_like(xs)
    for w, m, s in zip(age_prbs, mu_k, sig):
        if w > 1e-15:
            cdf += w * _norm.cdf(xs, m, s)
    cdf /= cdf[-1]  # normalize away the (tiny) tail truncation -> top == 1

    if method == "stratified":
        q = (np.arange(N) + 0.5) / N
    elif method == "random":
        q = rng.uniform(size=N)
    else:
        raise ValueError(
            f"sample_pLvl_steady_state: method={method!r} invalid; "
            "expected 'stratified' or 'random'.")

    log_p = np.interp(q, cdf, xs)
    pLvl = np.exp(log_p)
    return pLvl[rng.permutation(N)]


def pLvl_steady_state_moments(agent, *, employed_only=True, pLvl_dist=None):
    """Closed-form (E[p], Var[p], E[log p], Var[log p]) of the ergodic pLvl
    mixture.

    ``pLvl_dist`` selects the distribution ('employed' | 'blended' | 'markov';
    see ``_pLvl_components_select``); ``employed_only`` is the legacy switch used
    when ``pLvl_dist is None``. For ``'markov'`` the (E[log p], Var[log p])
    returned here equal ``compute_log_p_moments_exact`` by construction.

    Mirrors §6 of conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md
    using the exact mixture components (so it matches the sampler's source and
    the BUG-003/019 conventions). Returns a dict.
    """
    w, mu, sig = _pLvl_components_select(
        agent, employed_only=employed_only, pLvl_dist=pLvl_dist)
    v = sig ** 2
    Ep = float(np.sum(w * np.exp(mu + v / 2.0)))
    Ep2 = float(np.sum(w * np.exp(2.0 * mu + 2.0 * v)))
    Elogp = float(np.sum(w * mu))
    Elogp2 = float(np.sum(w * (v + mu ** 2)))
    return {
        "E_p": Ep,
        "Var_p": Ep2 - Ep ** 2,
        "E_logp": Elogp,
        "Var_logp": Elogp2 - Elogp ** 2,
    }


def _pLvl_markov_moment_recursion(agent):
    """Per-(age, state) first/second log-pLvl moments under the full Markov
    employment chain (unemployment-aware).

    Returns ``(age_prbs, pi_arr, m_arr, v_arr)`` where ``age_prbs`` has shape
    ``(T_age,)`` (ergodic age distribution) and ``pi_arr``/``m_arr``/``v_arr``
    have shape ``(T_age, J)`` with, for cohort age n and base employment state j:

      pi_arr[n, j] = Pr(state at age n = j)
      m_arr[n, j]  = E[1{state_n = j} · log p_n]
      v_arr[n, j]  = E[1{state_n = j} · (log p_n)²]

    These are exactly the quantities ``compute_log_p_moments_exact`` aggregates
    (it sums over j and age-weights). Exposing the full arrays lets the MC
    seed (``_pLvl_markov_mixture_components``) build a per-(age,state) Gaussian
    mixture that reproduces the exact mean/variance while accounting for the
    unemployment process (per-state growth, per-state shock variance, BUG-003
    deterministic-newborn convention). The recursion uses the agent's
    ``MrkvArray`` directly, which already encodes the stationary u.
    See conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md
    (with-unemployment section).
    """
    LivPrb = agent.LivPrb[0][0]
    # None (HAFISCAL_T_AGE=none) => tolerance-truncated geometric age chain,
    # NOT the legacy 400 bound (which silently discarded ~8% of survivors).
    T_age = effective_age_chain_length(agent.LivPrb[0][0], getattr(agent, 'T_age', 400))

    pLogInitMean = getattr(agent, 'pLogInitMean', getattr(agent, 'pLvlInitMean', 0.0))
    pLogInitStd = getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0))

    J = int(agent.num_base_MrkvStates)
    MrkvBase = np.asarray(agent.MrkvArray[0], dtype=float)[:J, :J]
    PermGroFac_arr = np.asarray(agent.PermGroFac[0], dtype=float)[:J]

    # Per-state log-shock moments from agent.IncShkDstn[0][j]
    mu_psi = np.zeros(J)
    var_psi = np.zeros(J)
    for j in range(J):
        d_j = agent.IncShkDstn[0][j]
        psi_j = np.asarray(d_j.atoms[0], dtype=float)
        probs_j = np.asarray(d_j.pmv, dtype=float)
        log_psi = np.log(psi_j)
        E1 = float(np.dot(probs_j, log_psi))
        E2 = float(np.dot(probs_j, log_psi ** 2))
        mu_psi[j] = E1
        var_psi[j] = E2 - E1 ** 2

    log_G = np.log(PermGroFac_arr)
    delta = log_G + mu_psi  # deterministic mean shift entering state j

    # Birth distribution = ergodic stationary of MrkvBase
    eigvals, eigvecs = np.linalg.eig(MrkvBase.T)
    idx = int(np.argmin(np.abs(eigvals - 1.0)))
    birth_fracs = np.abs(eigvecs[:, idx].real)
    birth_fracs /= birth_fracs.sum()

    # Ergodic age distribution: π_n^age ∝ L^n, n=0,...,T_age-1
    L = LivPrb
    T = int(T_age)
    log_age_prbs = (
        np.log(max(1.0 - L, 1e-300))
        - np.log(max(1.0 - L ** T, 1e-300))
        + np.arange(T) * np.log(max(L, 1e-300))
    )
    age_prbs = np.exp(log_age_prbs)
    age_prbs /= age_prbs.sum()

    pi_arr = np.zeros((T, J))
    m_arr = np.zeros((T, J))
    v_arr = np.zeros((T, J))

    # Initial state (n=0): newborn first growth applied deterministically
    pi_n = birth_fracs.copy()
    log_p0_mean_per_state = pLogInitMean + log_G  # length J
    m_n = pi_n * log_p0_mean_per_state
    v_n = pi_n * (log_p0_mean_per_state ** 2 + pLogInitStd ** 2)
    pi_arr[0] = pi_n
    m_arr[0] = m_n
    v_arr[0] = v_n

    Mt = MrkvBase.T
    for n in range(1, T):
        pi_next = Mt @ pi_n
        m_M = Mt @ m_n
        v_M = Mt @ v_n
        m_next = m_M + delta * pi_next
        v_next = v_M + 2.0 * delta * m_M + (delta ** 2 + var_psi) * pi_next

        pi_arr[n] = pi_next
        m_arr[n] = m_next
        v_arr[n] = v_next

        pi_n = pi_next
        m_n = m_next
        v_n = v_next

    return age_prbs, pi_arr, m_arr, v_arr


def _pLvl_markov_mixture_components(agent):
    """(weights, mu, sigma) of the unemployment-aware ergodic pLvl mixture.

    One Gaussian per non-negligible (age n, base employment state j) cell of the
    exact Markov recursion (``_pLvl_markov_moment_recursion``):

      weight w_{n,j} = age_prb(n) · π_n^j
      mean   μ_{n,j} = m_n^j / π_n^j
      var    σ²_{n,j} = v_n^j / π_n^j − μ_{n,j}²

    By construction the aggregate first two moments of log p equal
    ``compute_log_p_moments_exact`` (Σ w·μ = E[log p];
    Σ w·(σ²+μ²) = E[(log p)²]) — i.e. this is the correct, unemployment-aware
    distribution to first/second moments (a moment-exact Gaussian mixture).
    Same ``(weights, mu, sigma)`` contract as ``_pLvl_mixture_components`` so it
    plugs into the same sampler / moment helpers.
    See conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md.
    """
    age_prbs, pi_arr, m_arr, v_arr = _pLvl_markov_moment_recursion(agent)
    T, J = pi_arr.shape

    weights = []
    mus = []
    sigmas = []
    for n in range(T):
        ap = age_prbs[n]
        if ap < 1e-15:
            continue
        for j in range(J):
            pij = pi_arr[n, j]
            w = ap * pij
            if pij <= 1e-300 or w < 1e-18:
                continue
            mean = m_arr[n, j] / pij
            var = v_arr[n, j] / pij - mean ** 2
            if not np.isfinite(mean) or not np.isfinite(var):
                continue
            weights.append(w)
            mus.append(mean)
            sigmas.append(np.sqrt(max(var, 0.0)))

    weights = np.asarray(weights, dtype=float)
    mus = np.asarray(mus, dtype=float)
    sigmas = np.asarray(sigmas, dtype=float)
    weights /= weights.sum()
    return weights, mus, sigmas


def sample_pLvl_conditional_markov(agent, ages, states, rng, *,
                                   method="stratified"):
    """Per-agent pLvl drawn from its OWN (age, employment-state) cell of the
    exact Markov recursion — so the seeded pLvl is correlated with each agent's
    age and base Mrkv state at init, instead of the pooled marginal that
    ``sample_pLvl_steady_state(..., pLvl_dist='markov')`` produces (which
    attaches pLvl independently of age/state and so needs a long warmup to
    re-establish the correlation, producing the var(log p) overshoot).

    For an agent at age k (1..T_age) in base employment state j, log(pLvl) is
    drawn from ``N(μ_{n,j}, σ_{n,j})`` where ``n = k-1`` indexes the recursion's
    age axis and

        μ_{n,j}  = m_arr[n,j] / π_arr[n,j]
        σ²_{n,j} = v_arr[n,j] / π_arr[n,j] − μ_{n,j}²

    are the per-cell first/second log-pLvl moments from
    ``_pLvl_markov_moment_recursion`` (the same cells
    ``_pLvl_markov_mixture_components`` pools into a marginal). Because the
    agents' (age, state) are already seeded at their stationary cross-section
    (geometric ages; TM-a ergodic states), the aggregate pLvl marginal still
    matches the Markov-recursion moments — up to the small extent the MC's
    age⊥state seeding differs from the recursion's age–state coupling, which is
    negligible for the fast-mixing employment chain.

    NOTE: this conditions pLvl on (age, state) ONLY. pLvl remains independent of
    aNrm *within* a state — the within-state a–p correlation is the TM-ap joint,
    which is NOT modeled here.

    Parameters
    ----------
    agent : AggFiscalType
    ages : array_like of int, shape (N,)
        Agent ages in HARK's 1..T_age convention (as built by the MC init).
    states : array_like of int, shape (N,)
        Base employment-state indices (0..J-1), i.e. ``agent.shocks['Mrkv']``.
    rng : np.random.RandomState
    method : {'stratified', 'random'}
        ``'stratified'`` (default): within each (age, state) cell, the cell's
        ``k`` agents are placed at the stratified standard-normal quantiles
        ``Φ⁻¹((i+0.5)/k)`` (then shuffled within the cell), so the cell's
        empirical mean/var match ``(μ, σ²)`` with ``O(1/k)`` error instead of
        the ``O(1/√k)`` sampling noise of independent normal draws. The within-
        cell shuffle keeps ``pLvl ⊥ aNrm`` *within* the cell. ``'random'``:
        independent ``rng.normal(μ_i, σ_i)`` per agent (legacy; noisier).

    Returns
    -------
    np.ndarray, shape (N,): per-agent pLvl levels.
    See conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md.
    """
    age_prbs, pi_arr, m_arr, v_arr = _pLvl_markov_moment_recursion(agent)
    T, J = pi_arr.shape

    with np.errstate(divide='ignore', invalid='ignore'):
        mu_cell = np.where(pi_arr > 1e-300, m_arr / pi_arr, 0.0)
        ex2_cell = np.where(pi_arr > 1e-300, v_arr / pi_arr, 0.0)
    var_cell = np.maximum(ex2_cell - mu_cell ** 2, 0.0)
    sigma_cell = np.sqrt(var_cell)

    # age k (1..T_age) → recursion index n = k-1, clamped into [0, T-1].
    n_idx = np.clip(np.asarray(ages, dtype=int) - 1, 0, T - 1)
    j_idx = np.clip(np.asarray(states, dtype=int), 0, J - 1)

    mu_i = mu_cell[n_idx, j_idx]
    sigma_i = sigma_cell[n_idx, j_idx]
    N = mu_i.shape[0]

    if method == "random":
        z = rng.normal(size=N)
    elif method == "stratified":
        # Stratify the standard-normal draw WITHIN each (age,state) cell so the
        # cell-conditional mean/var are reproduced with O(1/k) error (not the
        # O(1/√k) noise of independent draws). Shuffle within the cell so the
        # quantile order does not induce a spurious pLvl–aNrm correlation.
        z = np.empty(N)
        cell = n_idx.astype(np.int64) * J + j_idx
        order = np.argsort(cell, kind="stable")
        cell_sorted = cell[order]
        boundaries = np.flatnonzero(np.diff(cell_sorted)) + 1
        for grp in np.split(np.arange(N), boundaries):
            k = grp.size
            if k == 0:
                continue
            zq = _norm.ppf((np.arange(k) + 0.5) / k)
            rng.shuffle(zq)
            z[order[grp]] = zq
    else:
        raise ValueError(
            f"sample_pLvl_conditional_markov: method={method!r} invalid; "
            "expected 'stratified' or 'random'.")

    log_pLvl = mu_i + sigma_i * z
    return np.exp(log_pLvl)


def compute_log_p_moments_exact(agent, unemployment_rate=None):
    """
    Exact mean and variance of log(pLvl) under HARK's Markov-chain employment.

    Replaces the (1-u) lognormal-mixture approximation in
    ``compute_pLvl_distribution`` for the moment-only use case (drift checks).
    Tracks per-state moments via matrix-iteration recursion:

      π_n^j  = Pr(state at age n = j)
      m_n^j  = E[1{j_n=j} · log p_n]
      v_n^j  = E[1{j_n=j} · (log p_n)²]

    Recursions, with δ_{j'} = log(G_{j'}) + μ_ψ^{j'} the deterministic mean
    shift entering state j' and σ_ψ²(j') the per-state log-shock variance:

      π_{n+1}^{j'}  = Σ_j M_{j,j'} · π_n^j
      m_{n+1}^{j'}  = (Mᵀ · m_n)_{j'} + δ_{j'} · π_{n+1}^{j'}
      v_{n+1}^{j'}  = (Mᵀ · v_n)_{j'} + 2·δ_{j'}·(Mᵀ · m_n)_{j'}
                      + (δ_{j'}² + σ_ψ²(j')) · π_{n+1}^{j'}

    Initial (post-deterministic newborn growth, BUG-003 convention):
      π_0^j = birth_fracs[j]
      m_0^j = π_0^j · (pLogInitMean + log(G_j))
      v_0^j = π_0^j · ((pLogInitMean + log(G_j))² + pLogInitStd²)

    Cohort-aggregated under ergodic age distribution π_n^age:
      E[log p]    = Σ_n π_n^age · Σ_j m_n^j
      E[(log p)²] = Σ_n π_n^age · Σ_j v_n^j
      Var[log p]  = E[(log p)²] − (E[log p])²

    Parameters
    ----------
    agent : AggFiscalType
    unemployment_rate : float or None
        Currently unused — placeholder for API symmetry with
        ``compute_pLvl_distribution``. The recursion uses the agent's
        ``MrkvArray`` directly, which already encodes the stationary u.

    Returns
    -------
    dict with keys 'mean_log_p_exact' and 'var_log_p_exact'.
    """
    age_prbs, pi_arr, m_arr, v_arr = _pLvl_markov_moment_recursion(agent)
    T = len(age_prbs)

    # Cohort-aggregate exactly as before (incremental float sums, n=0..T-1,
    # ``float(<row>.sum())`` per step) so the scalar output is bit-identical to
    # the pre-refactor implementation.
    E_logp = age_prbs[0] * float(m_arr[0].sum())
    E_logp2 = age_prbs[0] * float(v_arr[0].sum())
    for n in range(1, T):
        E_logp += age_prbs[n] * float(m_arr[n].sum())
        E_logp2 += age_prbs[n] * float(v_arr[n].sum())

    var_logp = E_logp2 - E_logp ** 2
    return {
        "mean_log_p_exact": float(E_logp),
        "var_log_p_exact": float(var_logp),
    }


def compute_pLvl_distribution_Q(agent, p_powers, n_points=200, unemployment_rate=None):
    """
    Compute E_Q[p_Q^k] for each k in p_powers under the Harmenberg neutral measure.

    Uses the **exact binomial formula** (no lognormal-mixture approximation):

        E_Q[p^k | age=n] = E[p_init^k] * Lambda_Q(k)^{n+1}

    where Lambda_Q(k) = u + (1-u) * E_Q[(G*psi)^k] is the per-period
    multiplicative factor for E[p^k], accounting for independent employment
    each period with probability (1-u).  The age-weighted sum uses the
    same ergodic age distribution as ``compute_pLvl_distribution``.

    BUG-020: needed so that ``compute_kernels`` with a Q-ergodic uses
    Q-consistent E[p^k] values.

    Returns dict {k: E_Q[p_Q^k]} for each k in p_powers, plus key 0.0
    for E_Q[log(p_Q)] (computed via a lognormal-mixture fallback).
    """
    LivPrb = agent.LivPrb[0][0]
    # None (HAFISCAL_T_AGE=none) => tolerance-truncated geometric age chain,
    # NOT the legacy 400 bound (which silently discarded ~8% of survivors).
    T_age = effective_age_chain_length(agent.LivPrb[0][0], getattr(agent, 'T_age', 400))
    pLogInitMean = getattr(agent, 'pLogInitMean', getattr(agent, 'pLvlInitMean', 0.0))
    pLogInitStd = getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0))
    u = float(unemployment_rate) if unemployment_rate is not None else 0.0

    # Q-measure shock distribution (employed state)
    d_P = agent.IncShkDstn[0][0]
    perm_shks = np.asarray(d_P.atoms[0], dtype=float)
    probs_P = np.asarray(d_P.pmv, dtype=float)
    q_probs = probs_P * perm_shks
    q_probs /= q_probs.sum()

    G_emp = float(np.asarray(agent.PermGroFac[0], dtype=float)[0])

    # Age distribution (same as P — mortality is measure-independent)
    L = LivPrb; T = T_age
    age_prbs = np.exp(np.log(1.0 - L) - np.log(1.0 - L**T) + np.arange(T) * np.log(L))
    age_prbs /= age_prbs.sum()

    # E[p_init^k] for lognormal init: exp(k*mu + k^2*sigma^2/2)
    def _E_pinit_k(k):
        return np.exp(k * pLogInitMean + k**2 * pLogInitStd**2 / 2.0)

    # Markov-chain exact formula for E_Q[p^k]:
    # At each period, agent transitions j -> j' and p multiplies by (G_{j'}*psi_{j'})^k.
    # Track v_j(n) = E[p^k | in state j at age n] via matrix iteration:
    #   v(n+1) = diag(alpha) @ MrkvBase^T @ v(n)
    # where alpha_j = E_Q[(G_j * psi_j)^k].
    J = int(agent.num_base_MrkvStates)
    MrkvBase = np.asarray(agent.MrkvArray[0], dtype=float)[:J, :J]
    PermGroFac_arr = np.asarray(agent.PermGroFac[0], dtype=float)[:J]

    # Ergodic micro-state fractions for birth distribution
    ss = np.linalg.eig(MrkvBase.T)
    idx = np.argmin(np.abs(ss[0] - 1.0))
    birth_fracs = np.abs(ss[1][:, idx].real)
    birth_fracs /= birth_fracs.sum()

    result = {}
    for k in p_powers:
        kf = float(k)
        # alpha_j = E_Q[(G_j * psi_j)^k] per micro state
        alpha = np.ones(J, dtype=float)
        for j in range(J):
            d_j = agent.IncShkDstn[0][j]
            psi_j = np.asarray(d_j.atoms[0], dtype=float)
            probs_j = np.asarray(d_j.pmv, dtype=float)
            q_j = probs_j * psi_j; q_j /= q_j.sum()
            alpha[j] = float(np.sum(q_j * (PermGroFac_arr[j] * psi_j) ** kf))

        # Transition matrix for E[p^k]: M = diag(alpha) @ MrkvBase^T
        M_pk = np.diag(alpha) @ MrkvBase.T

        # Initial: v_j(0) = E[p_init^k] * birth_fracs[j]
        v = _E_pinit_k(kf) * birth_fracs.copy()

        # Iterate and accumulate age-weighted sum
        # Age n means n+1 applications of growth, so v starts after first step
        E_pk = 0.0
        for n in range(T):
            v = M_pk @ v  # one more period of growth
            E_pk += age_prbs[n] * float(v.sum())

        result[kf] = E_pk

    # E[log p] for CRRA=1: use Q log-space moments (lognormal-mixture fallback)
    E_Q_log_psi = float(np.dot(q_probs, np.log(perm_shks)))
    sigma_psi_sq_Q = float(np.dot(q_probs, np.log(perm_shks)**2)) - E_Q_log_psi**2
    log_g_eff_Q = (1.0 - u) * (np.log(G_emp) + E_Q_log_psi)
    eff_k = (1.0 - u) * np.arange(T)
    mu_k = pLogInitMean + (np.arange(T) + 1) * log_g_eff_Q - eff_k * sigma_psi_sq_Q / 2.0
    result[0.0] = float(np.sum(age_prbs * mu_k))

    return result


# ================================================================
# Core TM building blocks
# ================================================================

def effective_age_chain_length(LivPrb, T_age, tol=1e-9):
    """Length of the age chain the pLvl/age-distribution helpers should use.

    Capped model (T_age an int): the chain is exactly T_age states — unchanged.
    Uncapped (T_age is None, HAFISCAL_T_AGE=none): ages are geometric-unbounded;
    truncate where the surviving mass drops below `tol`:
        T_eff = ceil(ln(tol)/ln(LivPrb))   (~3300 at LivPrb=1-1/160, tol=1e-9)
    The old hardcoded `if T_age is None: T_age = 400` fallback discarded
    LivPrb^400 ~= 8.1% of survivor mass — fine when None never occurred in
    production, wrong once the cap is genuinely removed (owner decision
    2026-07-26: the QE-era cap kills 28.5% of each cohort at the wall and was
    never documented in the paper; see plans/20260726_dist-grid-top-scoping_plan.md
    addendum + BUGS_private/HAFiscal_BUG-038_T_age_cap_removal.md).
    These recursions cost ~0.003% of a run at length 200, so ~17x longer is
    still negligible.
    """
    if T_age is not None:
        return int(T_age)
    L = float(LivPrb)
    if not (0.0 < L < 1.0):
        return 400  # degenerate survival; keep the legacy bound
    import math
    return max(400, int(math.ceil(math.log(tol) / math.log(L))))


def _effective_LivPrb(LivPrb_arr, T_age):
    """
    Adjust survival probabilities to account for forced death at T_age.

    See math-derive-appendix (L-eff): L_eff = (L - L^T) / (1 - L^T).

    In the MC, agents face random death at rate (1-L) per period AND forced
    death when t_age reaches T_age. The TM has no explicit age tracking, so
    we replace L with an effective survival probability that yields the same
    ergodic turnover rate:

        D_eff = (1-L) / (1-L^T_age)
        L_eff = 1 - D_eff = (L - L^T_age) / (1 - L^T_age)

    This is exact for the total death/rebirth flow. It is an approximation
    for the *composition* of dying agents (in the MC, T_age-boundary deaths
    come from a specific age cohort), but that second-order effect is small
    since the boundary cohort is only ~0.3% of the population.

    If T_age is None (no age limit), LivPrb_arr is returned unchanged.
    """
    if T_age is None:
        return LivPrb_arr
    out = np.empty_like(LivPrb_arr)
    for i, L in enumerate(LivPrb_arr):
        LT = L ** T_age
        if abs(1.0 - LT) < 1e-14:
            out[i] = 1.0 - 1.0 / T_age
        else:
            out[i] = (L - LT) / (1.0 - LT)
    return out


def _propagate_state_fracs(state_fracs, micro_trans, LivPrb_arr, T_age):
    """
    Propagate standard-measure state fractions through one period.

    See math-derive-harm (std-frac-recurrence).

    Used under the Harmenberg neutral measure to track actual P(state j)
    separately from the p-weighted distribution — the Q-distribution's
    state fractions are theoretically identical (math-derive-harm
    (Q-P-frac-equal)) but we track them separately for robustness.

    Parameters
    ----------
    state_fracs : np.ndarray, shape (J,)
        Current standard P(state j).
    micro_trans : np.ndarray, shape (J, J)
        Markov transition matrix for micro states (row j → col k).
    LivPrb_arr : np.ndarray, shape (J,)
        Raw survival probabilities per micro state.
    T_age : int or None

    Returns
    -------
    np.ndarray, shape (J,) — updated state fractions summing to 1.
    """
    LivPrb_eff = _effective_LivPrb(LivPrb_arr, T_age)
    J = len(state_fracs)
    delta_eff = 1.0 - np.mean(LivPrb_eff)
    erg = _solve_markov_ergodic(micro_trans)
    # Survivors transition; newborns enter at ergodic fractions
    new_fracs = np.zeros(J)
    for k in range(J):
        for j in range(J):
            new_fracs[k] += state_fracs[j] * LivPrb_eff[j] * micro_trans[j, k]
        new_fracs[k] += delta_eff * erg[k]
    s = np.sum(new_fracs)
    if s > 0:
        new_fracs /= s
    return new_fracs


def _make_newborn_dist(dist_mGrid, IncShkDstn_list, markov_weights):
    """
    Build newborn distribution across (m, j) states.

    Parameters
    ----------
    dist_mGrid : np.ndarray, shape (M,)
    IncShkDstn_list : list of J DiscreteDistributions (destination states)
    markov_weights : np.ndarray, shape (J,) — fraction of newborns entering each state

    Returns
    -------
    np.ndarray, shape (M*J,), sums to 1.
    """
    M = len(dist_mGrid)
    J = len(IncShkDstn_list)
    NewBornDist = np.zeros(M * J)
    for jp in range(J):
        dstn_jp = IncShkDstn_list[jp]
        tran_shks_jp = dstn_jp.atoms[1]
        shk_prbs_jp = dstn_jp.pmv
        newborn_1d = jump_to_grid_1D(tran_shks_jp, shk_prbs_jp, dist_mGrid)
        NewBornDist[jp * M : (jp + 1) * M] = markov_weights[jp] * newborn_1d
    s = np.sum(NewBornDist)
    if s > 0:
        NewBornDist /= s
    return NewBornDist


def _to_neutral_measure(IncShkDstn_list):
    """
    Reweight shock distributions for the Harmenberg neutral measure.

    See math-derive-harm (Q-def), (Q-simplified), (Q-reweight-emp),
    (Q-reweight-unemp).

    Under the neutral measure Q, probabilities are reweighted by the permanent
    shock: q_s = p_s * psi_s / sum(p * psi). This ensures that
    E_P[c(m) * p] = E_Q[c(m)] * E_P[p] exactly — see math-derive-harm
    (neutral-identity).

    For unemployed states with degenerate psi=1, this is a no-op —
    see math-derive-harm (Q-reweight-unemp).
    """
    from HARK.distributions import DiscreteDistribution
    neutral_list = []
    for d in IncShkDstn_list:
        perm_shks = d.atoms[0]
        neutral_pmv = d.pmv * perm_shks
        s = np.sum(neutral_pmv)
        if s > 0:
            neutral_pmv = neutral_pmv / s
        neutral_list.append(
            DiscreteDistribution(neutral_pmv, [d.atoms[0], d.atoms[1]])
        )
    return neutral_list


def _build_period_tm(dist_mGrid, aPol_2d, IncShkDstn_list, micro_trans,
                     Rfree_arr, PermGroFac_arr, LivPrb_arr, NewBornDist,
                     neutral_measure=False):
    """
    Build a (M*J) x (M*J) column-stochastic transition matrix for one period.

    This is the core workhorse used by both the baseline (ergodic) builder and
    the experiment (time-varying) builder.

    Parameters
    ----------
    dist_mGrid : np.ndarray, shape (M,)
        Normalized market resources grid.
    aPol_2d : np.ndarray, shape (J, M)
        End-of-period asset policy for each source Markov state.
    IncShkDstn_list : list of J DiscreteDistributions
        Income shock distribution for each *destination* Markov state.
    micro_trans : np.ndarray, shape (J, J)
        Markov transition matrix (micro_trans[j, jp] = P(j -> jp)).
    Rfree_arr : np.ndarray, shape (J,)
        Risk-free rate for each destination state.
    PermGroFac_arr : np.ndarray, shape (J,)
        Permanent income growth factor for each destination state.
    LivPrb_arr : np.ndarray, shape (J,)
        Survival probability for each source state.
    NewBornDist : np.ndarray, shape (M*J,)
        Distribution of newborn agents across (m, j) states (sums to 1).
    neutral_measure : bool
        If True, reweight shock probabilities by perm_shk (Harmenberg neutral
        measure).  See math-derive-harm (TM-Q-entry), (Q-ergodic).
        The ergodic distribution under this TM gives E_Q[f(m)]
        such that E_P[f(m)*p] = E_Q[f(m)] * E_P[p] exactly.

    Returns
    -------
    scipy.sparse.csc_matrix, shape (M*J, M*J), column-stochastic.
    """
    # See math-derive-harm (TM-Q-entry): replace p_s with q_s in shock weights
    if neutral_measure:
        IncShkDstn_list = _to_neutral_measure(IncShkDstn_list)

    M = len(dist_mGrid)
    J = aPol_2d.shape[0]
    N = M * J

    rows_list = []
    cols_list = []
    data_list = []

    nb_nz_idx = np.nonzero(NewBornDist > 1e-18)[0]
    nb_nz_val = NewBornDist[nb_nz_idx]
    n_nb = len(nb_nz_idx)

    src_range_M = np.arange(M, dtype=np.int64)

    for j in range(J):
        LivPrb_j = LivPrb_arr[j]
        death_prb = 1.0 - LivPrb_j
        col_offset = j * M

        # Death/rebirth: all M source columns in block j get the same
        # newborn pattern, weighted by death_prb.  Vectorized over i.
        if n_nb > 0 and death_prb > 1e-18:
            src_cols = np.repeat(src_range_M + col_offset, n_nb)
            dst_rows = np.tile(nb_nz_idx, M)
            vals = np.tile(death_prb * nb_nz_val, M)
            rows_list.append(dst_rows)
            cols_list.append(src_cols)
            data_list.append(vals)

        # Survival: vectorize over all M source grid points per (j, jp) pair
        for jp in range(J):
            markov_prob = micro_trans[j, jp]
            if markov_prob < 1e-15:
                continue

            dstn_jp = IncShkDstn_list[jp]
            shk_prbs = dstn_jp.pmv
            perm_shks = dstn_jp.atoms[0]
            tran_shks = dstn_jp.atoms[1]
            S = len(shk_prbs)

            bNext = Rfree_arr[jp] * aPol_2d[j, :]                     # (M,)
            inv_pG = 1.0 / (perm_shks * PermGroFac_arr[jp])           # (S,)
            mNext = bNext[:, None] * inv_pG[None, :] + tran_shks[None, :]  # (M, S)
            mNext_flat = mNext.ravel()                                 # (M*S,)

            # Batch linear interpolation onto dist_mGrid
            idx = np.searchsorted(dist_mGrid, mNext_flat, side='right') - 1
            below = mNext_flat <= dist_mGrid[0]
            above = mNext_flat >= dist_mGrid[-1]
            idx = np.clip(idx, 0, M - 2)

            lower_idx = idx
            upper_idx = idx + 1
            grid_lo = dist_mGrid[lower_idx]
            grid_hi = dist_mGrid[upper_idx]
            span = grid_hi - grid_lo
            span[span < 1e-30] = 1.0
            upper_wt = (mNext_flat - grid_lo) / span
            upper_wt = np.clip(upper_wt, 0.0, 1.0)
            lower_wt = 1.0 - upper_wt

            lower_idx[below] = 0;  upper_idx[below] = 0
            lower_wt[below] = 1.0; upper_wt[below] = 0.0
            lower_idx[above] = M - 1; upper_idx[above] = M - 1
            lower_wt[above] = 1.0;    upper_wt[above] = 0.0

            # Weight = markov_prob * LivPrb * shock_prob for each (i, s) pair
            wt = markov_prob * LivPrb_j * np.tile(shk_prbs, M)        # (M*S,)
            src_cols = np.repeat(src_range_M + col_offset, S)          # (M*S,)

            # Lower grid point contributions
            vals_lo = wt * lower_wt
            mask_lo = vals_lo > 1e-18
            if np.any(mask_lo):
                rows_list.append(jp * M + lower_idx[mask_lo])
                cols_list.append(src_cols[mask_lo])
                data_list.append(vals_lo[mask_lo])

            # Upper grid point contributions
            vals_hi = wt * upper_wt
            mask_hi = vals_hi > 1e-18
            if np.any(mask_hi):
                rows_list.append(jp * M + upper_idx[mask_hi])
                cols_list.append(src_cols[mask_hi])
                data_list.append(vals_hi[mask_hi])

    all_rows = np.concatenate(rows_list)
    all_cols = np.concatenate(cols_list)
    all_data = np.concatenate(data_list)

    TranMatrix = sp.csc_matrix(
        (all_data, (all_rows, all_cols)), shape=(N, N)
    )
    TranMatrix.sum_duplicates()
    return TranMatrix


def build_tm_agg_fiscal(agent, mCount=_HAFISCAL_TM_MCOUNT_DEFAULT, mMin=0.001, mMax=None, mFac=3,
                        Cratio=1.0, neutral_measure=False):
    """
    Build the (M*J) x (M*J) transition matrix for an AggFiscalType agent.

    Handles HAFiscal-specific features:
    - 2D cFunc (fixed at given Cratio)
    - Per-Markov-state shock distributions
    - Adaptive mMax based on agent's asset holding potential

    Returns
    -------
    dict with keys: TranMatrix, dist_mGrid, cPol, aPol, markov_ergodic
    """
    MrkvArray = agent.MrkvArray[0]
    J = MrkvArray.shape[0]

    Rfree_arr = np.asarray(agent.Rfree[:J], dtype=np.float64)
    PermGroFac_arr = np.asarray(agent.PermGroFac[0][:J], dtype=np.float64)
    LivPrb_arr = np.asarray(agent.LivPrb[0][:J], dtype=np.float64)
    T_age = getattr(agent, 'T_age', None)
    LivPrb_arr = _effective_LivPrb(LivPrb_arr, T_age)

    if mMax is None:
        mMax = 50.0

    dist_mGrid = make_grid_exp_mult(
        ming=mMin, maxg=mMax, ng=mCount, timestonest=mFac,
    )
    M = len(dist_mGrid)

    # Evaluate consumption policy at fixed Cratio
    sol = agent.solution[0]
    cPol = []
    aPol = []
    aPol_2d = np.empty((J, M), dtype=np.float64)
    for j in range(J):
        cPol_j = sol.cFunc[j](dist_mGrid, Cratio * np.ones_like(dist_mGrid))
        aPol_j = dist_mGrid - cPol_j
        aPol_j = np.maximum(aPol_j, 0.0)
        cPol.append(cPol_j)
        aPol.append(aPol_j)
        aPol_2d[j, :] = aPol_j

    # Markov stationary distribution (for newborn allocation)
    P = MrkvArray.T
    n = P.shape[0]
    A_mat = np.vstack([P - np.eye(n), np.ones(n)])
    b_vec = np.zeros(n + 1)
    b_vec[-1] = 1.0
    markov_ergodic, _, _, _ = np.linalg.lstsq(A_mat, b_vec, rcond=None)

    IncShkDstn_list = [agent.IncShkDstn[0][jp] for jp in range(J)]

    # See math-derive-harm (Q-newborn): newborn dist uses Q-reweighted shocks
    nb_dstn = _to_neutral_measure(IncShkDstn_list) if neutral_measure else IncShkDstn_list
    NewBornDist = _make_newborn_dist(dist_mGrid, nb_dstn, markov_ergodic)
    TranMatrix = _build_period_tm(
        dist_mGrid, aPol_2d, IncShkDstn_list, MrkvArray,
        Rfree_arr, PermGroFac_arr, LivPrb_arr, NewBornDist,
        neutral_measure=neutral_measure,
    )

    # Per-cohort ergodic: T_age separate distributions, one per age cohort.
    # This eliminates the effective death rate approximation (BUG-007) by
    # removing the oldest (wealthiest) cohort exactly, instead of applying
    # death uniformly across mNrm.
    cohort_ergodic = None
    if T_age is not None and T_age > 0:
        raw_LivPrb = np.asarray(agent.LivPrb[0][:J], dtype=np.float64)
        L_scalar = raw_LivPrb[0]  # same for all micro states in HAFiscal

        # Build TM without death (LivPrb=1): consume → save → transition → income
        TM_nodeath = _build_period_tm(
            dist_mGrid, aPol_2d, IncShkDstn_list, MrkvArray,
            Rfree_arr, PermGroFac_arr, np.ones(J, dtype=np.float64),
            NewBornDist, neutral_measure=neutral_measure,
        )
        if sp.issparse(TM_nodeath):
            TM_nd = TM_nodeath.toarray()
        else:
            TM_nd = np.asarray(TM_nodeath)

        # Iterate cohorts: cohort_k = LivPrb * TM_nodeath @ cohort_{k-1}
        cohorts = np.zeros((T_age, M * J))
        cohorts[0] = NewBornDist.copy()
        for k in range(1, T_age):
            cohorts[k] = L_scalar * (TM_nd @ cohorts[k - 1])

        cohort_ergodic = np.sum(cohorts, axis=0)
        cohort_ergodic = np.maximum(cohort_ergodic, 0.0)
        s = np.sum(cohort_ergodic)
        if s > 0:
            cohort_ergodic /= s

    return {
        'TranMatrix': TranMatrix,
        'dist_mGrid': dist_mGrid,
        'cPol': cPol,
        'aPol': aPol,
        'markov_ergodic': markov_ergodic,
        'mMax': mMax,
        'cohort_ergodic': cohort_ergodic,
    }


def find_ergodic_distribution(TranMatrix, method='power', tol=1e-12, max_iter=5000):
    """
    Find the ergodic distribution of a column-stochastic transition matrix.

    See math-derive Section 4 (TM-agg context): the ergodic distribution
    pi^* satisfies T @ pi^* = pi^* and underpins E[c(m,z)] computation.

    Accepts both dense np.ndarray and scipy.sparse matrices.
    Uses power iteration by default (robust for all column-stochastic matrices).

    WHY A STATIONARY pi^* EXISTS EVEN AT THE GIC EDGE (read with `_build_period_tm_a`)
    --------------------------------------------------------------------------------
    `TranMatrix` (built by `_build_period_tm_a`) includes the death→newborn reset
    `+ (1 − L_eff(j))·NewBornDist`, so it is column-stochastic and mass-conserving.
    That reset is what makes pi^* exist: each period ≈(1−L) of the mass is killed
    and re-injected at a=0, which regularizes the chain even when the most-patient
    atom has NO individual buffer-stock target (its individual GPF_in > 1; see the
    "WHICH GIC IS THIS" comment in `FromPandemicCode/EstimParameters.py`). Formally,
    pi^* exists iff the *population* condition holds — Carroll BufferStockTheory
    eq. 42's GPF_out = (Rβ)^(1/ρ)·LivPrb·E[ψ⁻¹]/Γ < 1 — which is exactly what the
    GIC-shave (`gic_capped_beta`, theGICfactor = 0.9995) enforces. So MC and TM both
    reset on death and compute the SAME stationary cross-section; "no individual
    target" does NOT mean "no ergodic distribution".

    Two caveats this existence argument does NOT cover:
      * If GPF_out ≥ 1 (shave disabled / theGICfactor raised past the boundary), no
        stationary distribution exists; power iteration drifts mass to the top grid
        point (`dist_aGrid_max`, the distribution-grid top) and the result is a
        truncation artifact, not pi^*. Only finite-horizon MC is meaningful in that
        regime.
      * Even with GPF_out < 1, a most-patient atom with GPF_in > 1 has a FAT upper
        tail cut off only by mortality, so `dist_aGrid_max` must be tall enough to
        contain it (the (1−1e-4) ergodic aNrm quantile; see
        `adaptive_grid_tm.production_dist_aGrid_max`, which is sized by exactly this
        GIC-edge atom). Too-low dist_aGrid_max biases pi^*.
    Full write-up: conclusions_private/2026-06-16_gic-inside-vs-outside-individual-target-vs-tm-ergodic.md
    """
    N = TranMatrix.shape[0]

    if method == 'power':
        v = np.ones(N) / N
        for it in range(max_iter):
            v_new = TranMatrix @ v
            if sp.issparse(v_new):
                v_new = np.asarray(v_new).flatten()
            v_new = np.maximum(v_new, 0.0)
            s = v_new.sum()
            if s > 0:
                v_new /= s
            diff = np.max(np.abs(v_new - v))
            v = v_new
            if diff < tol:
                break
        return v
    else:
        if not sp.issparse(TranMatrix):
            TranMatrix = sp.csc_matrix(TranMatrix)
        eigenvalues, eigenvectors = spla.eigs(
            TranMatrix, v0=np.ones(N), k=1, which="LM"
        )
        ergodic_distr = eigenvectors[:, 0].real
        if np.sum(ergodic_distr) < 0:
            ergodic_distr = -ergodic_distr
        ergodic_distr = np.maximum(ergodic_distr, 0.0)
        if ergodic_distr.sum() > 0:
            ergodic_distr /= ergodic_distr.sum()
        else:
            return find_ergodic_distribution(TranMatrix, method='power')
        return ergodic_distr


def compute_type_aggregates_tm(agent, tm_data, ergodic_distr):
    """
    Compute per-type aggregate consumption and income using TM ergodic distribution.

    See math-derive (TM-agg) and (splurge) for the normalized aggregation
    formulas: C_nrm = (1-S)*sum_j int c(m,j) dpi_j(m) + S*sum_j pi_j*E[theta_j].

    Returns dict with: C_nrm, A_nrm, C_splurge_nrm, state_fractions,
    E_TranShk_by_state, and the full ergodic distribution.
    """
    dist_mGrid = tm_data['dist_mGrid']
    cPol = tm_data['cPol']
    aPol = tm_data['aPol']
    M = len(dist_mGrid)
    J = agent.MrkvArray[0].shape[0]
    Splurge = agent.Splurge

    C_nrm = 0.0
    A_nrm = 0.0
    state_fractions = np.zeros(J)
    for j in range(J):
        dstn_j = ergodic_distr[j * M : (j + 1) * M]
        state_fractions[j] = np.sum(dstn_j)
        C_nrm += np.dot(cPol[j], dstn_j)
        A_nrm += np.dot(aPol[j], dstn_j)

    E_TranShk = np.zeros(J)
    for j in range(J):
        d = agent.IncShkDstn[0][j]
        E_TranShk[j] = np.dot(d.pmv, d.atoms[1])

    # See math-derive (splurge): c_nrm = (1-S)*c_policy + S*E[theta]
    splurge_term = Splurge * np.dot(state_fractions, E_TranShk)
    C_splurge_nrm = (1.0 - Splurge) * C_nrm + splurge_term

    Income_nrm = np.dot(state_fractions, E_TranShk)

    return {
        'C_nrm': C_nrm,
        'A_nrm': A_nrm,
        'C_splurge_nrm': C_splurge_nrm,
        'Income_nrm': Income_nrm,
        'state_fractions': state_fractions,
        'E_TranShk': E_TranShk,
    }


def compute_kernels(
    agent,
    tm_data,
    ergodic,
    p_powers,
    CRRA,
    n_p_points=200,
    include_splurge=True,
    IncShkDstn_override=None,
    E_pk_override=None,
):
    """
    Covariance kernels for expectations of the form E[p^k * (Phi*X_related)^k] approximated as
    E[p^k] * sum_{m,j} pi(m,j) * kappa_k(a(m,j), j).

    Matches ``verify_four_methods_agreement.mean_marginal_utility_tm_kernel`` for
    k = -CRRA (marginal utility of splurge consumption).

    For k = 1 - CRRA (CRRA != 1), applies felicity scaling 1/(1-CRRA) so ``estimate``
    matches ``Welfare.py`` felicity expectation for u(c) with c = p_{t-1} * Phi * X.

    **CRRA ≠ 1 — felicity power in the inner loop.** For every requested power ``k``,
    the shock sum accumulates ``Phi**k * X**k``. When ``k = 1 - rho``, that is
    ``Phi**(1-rho) * X**(1-rho)``; the divisor ``1/(1-rho)`` is applied only when
    forming ``estimate``. This matches CRRA felicity because
    ``u(c) = (p * Phi * X)**(1-rho) / (1-rho)`` factors as
    ``p**(1-rho) * [Phi**(1-rho) * X**(1-rho)] / (1-rho)`` with ``p`` at ``t-1``.

    Parameters
    ----------
    agent : AggFiscalType (solved)
    tm_data : dict from build_tm_agg_fiscal
    ergodic : np.ndarray, shape (M*J,)
    p_powers : sequence of float
        Typical CRRA != 1: ``(-CRRA, 1.0 - CRRA)``. Ignored when CRRA == 1 (see below).
    CRRA : float
    n_p_points : int
        Discrete grid size for ``compute_pLvl_distribution`` (E[p^k] factors).
        Ignored when ``E_pk_override`` is provided.
    include_splurge : bool
        If True, X = (1-S)*c(m') + S*theta; else X = c(m').
    IncShkDstn_override : list of DiscreteDistribution or None
        If provided, the kernel loop uses these shock distributions instead of
        ``agent.IncShkDstn[0]`` (P-measure).  Pass Q-reweighted distributions
        (e.g. from ``_to_neutral_measure``) to compute a genuine Q-measure
        kernel; see BUG-020.
    E_pk_override : dict {float: float} or None
        If provided, maps each power k to a pre-computed E[p^k].  Use this
        to supply Q-measure moments when the kernel operates under a Q-ergodic.

    Returns
    -------
    dict
        Keys are float ``k`` for each requested power (CRRA != 1), each mapping to::

            {'estimate': float, 'E_pk': float, 'kappa_sum': float,
             'is_felicity': bool}

        When ``CRRA == 1``, returns keys ``-1.0`` (E[u'] with u' = 1/c) and ``0.0``
        (E[log c] with c = p * Phi * X), each with the same sub-dict shape and
        ``is_felicity`` True only for key ``0.0``.
    """
    dist_mGrid = tm_data["dist_mGrid"]
    M = len(dist_mGrid)
    J = int(agent.num_base_MrkvStates)
    erg = np.asarray(ergodic, dtype=float).ravel()
    if erg.size != M * J:
        raise ValueError(f"ergodic length {erg.size} != M*J={M * J}")
    s = erg.sum()
    if s <= 0 or not np.isfinite(s):
        return {}
    erg = erg / s
    erg2 = erg.reshape(J, M)

    u_rate = float(1.0 - np.sum(erg2[0, :]))

    sol = agent.solution[0]
    Splurge = float(agent.Splurge)
    Rfree = float(np.asarray(agent.Rfree).ravel()[0])
    PermGroFac = np.asarray(agent.PermGroFac[0], dtype=float)[:J]
    MrkvBase = np.asarray(agent.MrkvArray[0], dtype=float)[:J, :J]
    # BUG-020 fix: use overridden shocks (Q-reweighted) when provided,
    # otherwise default to P-measure shocks.
    IncShkDstn = IncShkDstn_override if IncShkDstn_override is not None else agent.IncShkDstn[0]
    rho = float(CRRA)

    c_nrm = np.empty((J, M), dtype=np.float64)
    a_nrm = np.empty((J, M), dtype=np.float64)
    for j in range(J):
        c_nrm[j, :] = sol.cFunc[j](dist_mGrid, np.ones(M, dtype=np.float64))
        a_nrm[j, :] = dist_mGrid - c_nrm[j, :]

    # --- log utility (CRRA == 1): u' = 1/c, u = log(c) ---
    if abs(rho - 1.0) < 1e-12:
        if E_pk_override is not None and -1.0 in E_pk_override:
            E_inv_p = float(E_pk_override[-1.0])
        else:
            p_grid, p_w = compute_pLvl_distribution(
                agent, n_points=int(n_p_points), unemployment_rate=u_rate)
            E_inv_p = float(np.sum(p_w / np.maximum(p_grid, 1e-16)))
        if E_pk_override is not None and 0.0 in E_pk_override:
            E_log_p = float(E_pk_override[0.0])
        else:
            if 'p_grid' not in dir():
                p_grid, p_w = compute_pLvl_distribution(
                    agent, n_points=int(n_p_points), unemployment_rate=u_rate)
            E_log_p = float(np.sum(p_w * np.log(np.maximum(p_grid, 1e-16))))

        kappa_inv = 0.0
        kappa_log = 0.0
        for j_old in range(J):
            for i in range(M):
                a_i = float(a_nrm[j_old, i])
                w_i = float(erg2[j_old, i])
                if w_i < 1e-20:
                    continue
                acc_inv = 0.0
                acc_log = 0.0
                for j_new in range(J):
                    tp = float(MrkvBase[j_old, j_new])
                    if tp < 1e-15:
                        continue
                    G_n = float(PermGroFac[j_new])
                    d_n = IncShkDstn[j_new]
                    for s_idx in range(len(d_n.pmv)):
                        psi_s = float(d_n.atoms[0][s_idx])
                        th_s = float(d_n.atoms[1][s_idx])
                        pr_s = float(d_n.pmv[s_idx])
                        Phi = G_n * psi_s
                        m_next = (a_i * Rfree / Phi + th_s) if a_i > 0 else th_s
                        c_next = float(sol.cFunc[j_new](m_next, 1.0))
                        if include_splurge:
                            X_next = max((1.0 - Splurge) * c_next + Splurge * th_s, 1e-16)
                        else:
                            X_next = max(c_next, 1e-16)
                        acc_inv += tp * pr_s / max(Phi * X_next, 1e-16)
                        acc_log += tp * pr_s * (
                            np.log(max(Phi, 1e-16)) + np.log(X_next)
                        )
                kappa_inv += w_i * acc_inv
                kappa_log += w_i * acc_log

        est_up = E_inv_p * kappa_inv
        est_fel = E_log_p + kappa_log
        return {
            -1.0: {
                "estimate": est_up,
                "E_pk": E_inv_p,
                "kappa_sum": kappa_inv,
                "is_felicity": False,
            },
            0.0: {
                "estimate": est_fel,
                "E_pk": E_log_p,
                "kappa_sum": kappa_log,
                "is_felicity": True,
            },
        }

    # --- CRRA != 1: power kernels ---
    powers = tuple(float(k) for k in sorted(set(float(x) for x in p_powers)))
    # BUG-020 fix: use overridden E[p^k] when provided (Q-measure moments).
    if E_pk_override is not None:
        E_pk = {k: float(E_pk_override[k]) for k in powers if k in E_pk_override}
        # Fall back to P-measure for any powers not in the override
        missing = [k for k in powers if k not in E_pk]
        if missing:
            p_grid, p_w = compute_pLvl_distribution(
                agent, n_points=int(n_p_points), unemployment_rate=u_rate)
            for k in missing:
                E_pk[k] = float(np.sum(p_w * (p_grid ** k)))
    else:
        p_grid, p_w = compute_pLvl_distribution(
            agent, n_points=int(n_p_points), unemployment_rate=u_rate)
        E_pk = {k: float(np.sum(p_w * (p_grid ** k))) for k in powers}
    kappa_sums = {k: 0.0 for k in powers}

    for j_old in range(J):
        for i in range(M):
            a_i = float(a_nrm[j_old, i])
            w_i = float(erg2[j_old, i])
            if w_i < 1e-20:
                continue
            acc = {k: 0.0 for k in powers}
            for j_new in range(J):
                tp = float(MrkvBase[j_old, j_new])
                if tp < 1e-15:
                    continue
                G_n = float(PermGroFac[j_new])
                d_n = IncShkDstn[j_new]
                for s_idx in range(len(d_n.pmv)):
                    psi_s = float(d_n.atoms[0][s_idx])
                    th_s = float(d_n.atoms[1][s_idx])
                    pr_s = float(d_n.pmv[s_idx])
                    Phi = G_n * psi_s
                    m_next = (a_i * Rfree / Phi + th_s) if a_i > 0 else th_s
                    c_next = float(sol.cFunc[j_new](m_next, 1.0))
                    if include_splurge:
                        X_next = max((1.0 - Splurge) * c_next + Splurge * th_s, 1e-16)
                    else:
                        X_next = max(c_next, 1e-16)
                    for k in powers:
                        acc[k] += tp * pr_s * (Phi ** k) * (X_next ** k)
            for k in powers:
                kappa_sums[k] += w_i * acc[k]

    out = {}
    k_fel = 1.0 - rho
    for k in powers:
        raw = E_pk[k] * kappa_sums[k]
        is_fel = abs(k - k_fel) < 1e-10
        if is_fel:
            est = raw / (1.0 - rho)
        else:
            est = raw
        out[float(k)] = {
            "estimate": est,
            "E_pk": E_pk[k],
            "kappa_sum": kappa_sums[k],
            "is_felicity": is_fel,
        }
    return out


def run_experiment_tm(economy, shock_type="base", dist_aGrid_count=None, Cratio=1.0,
                      neutral_measure=False, verbose=True,
                      compute_welfare=False, kernel_n_p_points=120,
                      mCount=None):
    """
    TM-based replacement for AggregateDemandEconomy.run_experiment().

    For the baseline experiment (shock_type="base"), the distribution is
    stationary: AggCons and AggIncome are constant over act_T periods.

    Parameters
    ----------
    economy : AggregateDemandEconomy
        The economy object with solved agents.
    shock_type : str
        Currently only "base" is supported.
    dist_aGrid_count : int or None, default None
        Number of distribution-grid points for the TM (owner ruling
        2026-07-25: on the production a-indexed path this sizes the
        a-indexed distribution grid — it is handed to
        ``build_tm_agg_fiscal_a(aCount=...)``; on the legacy m-indexed
        dispatch it sizes that kernel's honest ``mCount``).
        None => ``HAFISCAL_TM_MCOUNT`` env default (flag spelling retained
        by owner ruling), else 50.
    Cratio : float
        Aggregate consumption ratio (1.0 for baseline).
    verbose : bool
        Print progress.
    compute_welfare : bool
        If True, attach kernel-based per-capita ``mean_uprime_kernel`` and
        ``mean_felicity_kernel`` (same splurge timing as ``Welfare.py`` / Gatekeeper).
    kernel_n_p_points : int
        Grid size for ``compute_pLvl_distribution`` inside ``compute_kernels``.
    mCount : int or None, default None
        DEPRECATED alias for ``dist_aGrid_count`` (one deprecation cycle,
        same pattern as the ``aMax``→``dist_aGrid_max`` rename). Warns on
        use; ignored when ``dist_aGrid_count`` is given.

    Returns
    -------
    dict matching run_experiment output format:
        NPV_AggIncome, NPV_AggCons, AggIncome, AggCons, Cratio_hist
        Optional: mean_uprime_kernel, mean_felicity_kernel, _kernel_by_type
    """
    # Deprecated-alias shim (owner ruling 2026-07-25, grid-name cleanup phase
    # 2): the a-indexed TM distribution-grid size is `dist_aGrid_count`; the
    # M-era `mCount` spelling is accepted for one deprecation cycle.
    if mCount is not None:
        import warnings as _warnings_dep
        _warnings_dep.warn(
            "run_experiment_tm(mCount=...) is deprecated; pass "
            "dist_aGrid_count=... instead (owner ruling 2026-07-25: on the "
            "production a-indexed TM path this parameter sizes the a-indexed "
            "distribution grid, not an m-grid). Behavior unchanged.",
            DeprecationWarning, stacklevel=2)
        if dist_aGrid_count is None:
            dist_aGrid_count = mCount
    if dist_aGrid_count is None:
        dist_aGrid_count = _HAFISCAL_TM_MCOUNT_DEFAULT

    if shock_type != "base":
        raise NotImplementedError(
            f"TM run_experiment not yet implemented for shock_type='{shock_type}'. "
            f"Only 'base' is supported."
        )

    act_T = economy.act_T
    agents = economy.agents
    Rfree = agents[0].Rfree[0]

    if verbose:
        print(f"  TM run_experiment: {len(agents)} agents, {act_T} periods, "
              f"dist_aGrid_count={dist_aGrid_count}")

    # Phase 1: Build TM and find ergodic distribution for each type
    type_results = []
    for i, agent in enumerate(agents):
        agent.update_mrkv_array("base")
        agent.solve()

        use_a = getattr(agent, 'tm_a_indexed', False)
        interp = getattr(agent, 'interpretation', 'CDC')
        if use_a:
            tm_data = build_tm_agg_fiscal_a(agent, aCount=dist_aGrid_count, Cratio=Cratio,
                                            neutral_measure=neutral_measure,
                                            interpretation=interp)
        else:
            # Legacy m-indexed kernel: its mCount is the honest m-grid size.
            tm_data = build_tm_agg_fiscal(agent, mCount=dist_aGrid_count, Cratio=Cratio,
                                          neutral_measure=neutral_measure)
        ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
        if use_a:
            agg = compute_type_aggregates_tm_a(agent, tm_data, ergodic,
                                               neutral_measure=neutral_measure,
                                               interpretation=interp)
        else:
            agg = compute_type_aggregates_tm(agent, tm_data, ergodic)

        # See math-derive (E-pLvl) with (g-base): E[p] with unemployment correction
        grid_key = 'dist_aGrid' if use_a else 'dist_mGrid'
        M_i = len(tm_data[grid_key])
        u_erg_i = 1.0 - np.sum(ergodic[:M_i])
        E_pLvl = compute_analytical_mean_pLvl(agent, unemployment_rate=u_erg_i)

        type_results.append({
            'tm_data': tm_data,
            'agg': agg,
            'E_pLvl': E_pLvl,
            'AgentCount': agent.AgentCount,
            'pop_rescale_factor': getattr(agent, 'pop_rescale_factor', 1.0),
        })

    if verbose:
        print(f"  All {len(agents)} types processed")

    # Phase 2: See math-derive (TM-agg): C = N * E[p] * c_nrm (base: F_t=1)
    # Edu-share-respecting aggregation: under standard config, pop_rescale_factor=1
    # so this is unchanged. Under HAFISCAL_AGENTCOUNT_* override, the factor
    # corrects per-cohort weighting so aggregates respect data_EducShares.
    # See plans/20260506-1640h_edu_share_aggregation_correction.md.
    _agg_mode_tm = _os.environ.get('HAFISCAL_AGGREGATE_BY_EDU_SHARE', 'auto').lower()
    _has_co_tm = any(
        _os.environ.get(v, '').strip() != ''
        for v in ('HAFISCAL_AGENTCOUNT_D', 'HAFISCAL_AGENTCOUNT_H', 'HAFISCAL_AGENTCOUNT_C')
    )
    _apply_rescale_tm = (
        _agg_mode_tm in ('on', '1', 'true')
        or (_agg_mode_tm == 'auto' and _has_co_tm)
    )
    AggCons_ss = 0.0
    AggIncome_ss = 0.0
    for tr in type_results:
        rescale = tr['pop_rescale_factor'] if _apply_rescale_tm else 1.0
        level_scale = tr['AgentCount'] * rescale * tr['E_pLvl']
        AggCons_ss += level_scale * tr['agg']['C_splurge_nrm']
        AggIncome_ss += level_scale * tr['agg']['Income_nrm']

    # For base shock, aggregates are constant over time
    AggCons = np.full(act_T, AggCons_ss)
    AggIncome = np.full(act_T, AggIncome_ss)
    Cratio_hist = np.ones(act_T)

    # See math-derive (NPV-def): V = sum_t beta^t * X_t
    def calculate_NPV(X, Periods, R):
        NPV = np.zeros(Periods)
        discount = np.array([1.0 / R**t for t in range(Periods)])
        for t in range(Periods):
            NPV[t] = np.sum(X[:t+1] * discount[:t+1])
        return NPV

    NPV_AggCons = calculate_NPV(AggCons, act_T, Rfree)
    NPV_AggIncome = calculate_NPV(AggIncome, act_T, Rfree)

    out = {
        'NPV_AggIncome': NPV_AggIncome,
        'NPV_AggCons': NPV_AggCons,
        'AggIncome': AggIncome,
        'AggCons': AggCons,
        'Cratio_hist': Cratio_hist,
        '_type_results': type_results,  # extra: per-type details
    }

    if compute_welfare:
        # BUG-033 / Phase 3.6: compute_kernels is m-indexed. A-indexed
        # kernels are Phase 6 work; refuse here rather than silently
        # compute an inconsistent welfare measure.
        if any(getattr(a, 'tm_a_indexed', False) for a in agents):
            raise NotImplementedError(
                "compute_welfare=True is not yet supported for "
                "tm_a_indexed agents. Phase 6 will add an a-indexed "
                "welfare-kernel implementation."
            )
        total_n = sum(int(tr["AgentCount"]) for tr in type_results)
        if total_n <= 0:
            total_n = 1
        w_up = 0.0
        w_fel = 0.0
        by_type = []

        # BUG-020 fix: when neutral_measure=True, kernel must use
        # Q-reweighted shocks and Q-measure E[p^k].
        if neutral_measure:
            IncShk_Q_list = [_to_neutral_measure(a.IncShkDstn[0]) for a in agents]
        else:
            IncShk_Q_list = [None] * len(agents)

        for i, agent in enumerate(agents):
            tr = type_results[i]
            tm_data = tr["tm_data"]
            erg = find_ergodic_distribution(tm_data["TranMatrix"])
            rho = float(agent.CRRA)

            # Build measure-consistent overrides
            shk_ov = IncShk_Q_list[i]
            epk_ov = None
            if neutral_measure:
                _erg_2d = (np.asarray(erg, float).ravel() / np.sum(erg)).reshape(
                    int(agent.num_base_MrkvStates), len(tm_data["dist_mGrid"]))
                _u = float(1.0 - np.sum(_erg_2d[0, :]))
                if abs(rho - 1.0) < 1e-12:
                    epk_ov = compute_pLvl_distribution_Q(
                        agent, [-1.0], n_points=int(kernel_n_p_points), unemployment_rate=_u)
                else:
                    epk_ov = compute_pLvl_distribution_Q(
                        agent, [-rho, 1.0 - rho], n_points=int(kernel_n_p_points), unemployment_rate=_u)

            if abs(rho - 1.0) < 1e-12:
                kdict = compute_kernels(
                    agent, tm_data, erg, [], rho,
                    n_p_points=int(kernel_n_p_points), include_splurge=True,
                    IncShkDstn_override=shk_ov, E_pk_override=epk_ov,
                )
                est_up = kdict[-1.0]["estimate"]
                est_fel = kdict[0.0]["estimate"]
            else:
                kdict = compute_kernels(
                    agent, tm_data, erg, [-rho, 1.0 - rho], rho,
                    n_p_points=int(kernel_n_p_points), include_splurge=True,
                    IncShkDstn_override=shk_ov, E_pk_override=epk_ov,
                )
                est_up = kdict[float(-rho)]["estimate"]
                est_fel = kdict[float(1.0 - rho)]["estimate"]
            nc = int(tr["AgentCount"])
            w_up += nc * est_up
            w_fel += nc * est_fel
            by_type.append(
                {
                    "mean_uprime_kernel": est_up,
                    "mean_felicity_kernel": est_fel,
                    "kernels": kdict,
                }
            )
        out["mean_uprime_kernel"] = w_up / total_n
        out["mean_felicity_kernel"] = w_fel / total_n
        out["_kernel_by_type"] = by_type

    return out


# ================================================================
# Experiment (time-varying) TM methods
# ================================================================

def calculate_NPV(X, Periods, R):
    """Net present value of X[0..Periods-1] at gross rate R.
    See math-derive (NPV-def)."""
    NPV = np.zeros(Periods)
    discount = np.array([1.0 / R**t for t in range(Periods)])
    for t in range(Periods):
        NPV[t] = np.sum(X[:t+1] * discount[:t+1])
    return NPV


def _check_phase_out_scalar(E_pLvl, cutoff_start, cutoff_end):
    """Phase-out scalar for stimulus check evaluated at E[pLvl]."""
    if E_pLvl < cutoff_start:
        return 1.0
    elif E_pLvl > cutoff_end:
        return 0.0
    else:
        return 1.0 - (E_pLvl - cutoff_start) / (cutoff_end - cutoff_start)


def _check_n_buckets_env_default():
    """
    Default n_buckets for the Stimulus Check pLvl quantile bucketing.
    Overrideable via the HAFISCAL_CHECK_BUCKETS environment variable.

    Default is 50 (changed from 5 in BUG-022 fix). The previous default
    of 5 buckets produced a ~+3.9% TM-side bias on the norec-check
    multiplier because the phase-out kink at pLvl=25 falls inside one
    bucket and the bucket-mean shift grossly mis-estimates the average
    response. Empirical sweep on HS_Only --ladder smoke:

      n_buckets    TM ref mult    err vs MC
      ---------    -----------    ---------
              5         1.0100        3.34%   ← old default, biased
             20         0.9756        0.08%
             50         0.9725        0.39%   ← new default
            200         0.9718        0.46%   ← essentially converged

    50 sits at the asymptote (within 0.07% of n=200) and adds
    negligible wall-clock cost (the per-bucket TM construction is
    cheap relative to the solve, which is now cached anyway).

    See:
      - BUGS_private/HAFiscal_BUG-022_check_bucket_discretization.md
      - history/20260331-mathematical-derivations-TM-MC-convergence.md §13.5.1
      - Comparison Registry item 6c in test_asymptotic_equality_revised.py
    """
    import os as _os
    raw = _os.environ.get("HAFISCAL_CHECK_BUCKETS", "")
    try:
        n = int(raw)
        if n >= 1:
            return n
    except (TypeError, ValueError):
        pass
    return 50


def _compute_check_buckets(agent, E_pLvl=None, n_buckets=None, unemployment_rate=None):
    if n_buckets is None:
        n_buckets = _check_n_buckets_env_default()
    """
    Compute a bucketed representation of the stimulus check effect.

    To capture Jensen's inequality from the concave consumption function,
    we split the ergodic pLvl distribution into n_buckets groups.  Each bucket
    has its own mNrm_shift (for the consumption/savings policy) and
    TranShk_addition (for the income/splurge accounting), weighted by the
    bucket's probability mass.

    For the check period, the caller builds one transition matrix per bucket
    and takes their weighted average.  This correctly integrates the
    heterogeneous consumption response over pLvl.

    Parameters
    ----------
    agent : AggFiscalType
    E_pLvl : float or None
    n_buckets : int
        Number of pLvl buckets.
    unemployment_rate : float or None
        Ergodic unemployment rate, passed through to analytical E[pLvl]
        and pLvl distribution functions.

    Returns
    -------
    list of dicts, each with keys:
        'weight'           : float, probability of this bucket
        'mNrm_shift'       : np.ndarray (J_micro,)
        'TranShk_addition' : np.ndarray (J_micro,)
    """
    J_micro = agent.num_base_MrkvStates
    CheckStimLvl = agent.CheckStimLvl
    cutoff_start = agent.CheckStimLvl_PLvl_Cutoff_start
    cutoff_end = agent.CheckStimLvl_PLvl_Cutoff_end

    if E_pLvl is None:
        E_pLvl = compute_analytical_mean_pLvl(agent, unemployment_rate=unemployment_rate)

    pLvl_grid, pLvl_weights = compute_pLvl_distribution(agent, unemployment_rate=unemployment_rate)

    phase_out = np.ones_like(pLvl_grid)
    in_range = (pLvl_grid >= cutoff_start) & (pLvl_grid <= cutoff_end)
    above = pLvl_grid > cutoff_end
    phase_out[in_range] = 1.0 - (pLvl_grid[in_range] - cutoff_start) / (cutoff_end - cutoff_start)
    phase_out[above] = 0.0

    check_nrm_grid = CheckStimLvl * phase_out / pLvl_grid
    check_level_grid = CheckStimLvl * phase_out

    # E[1/PermShk] for employed micro state
    d_emp = agent.IncShkDstn[0][0]
    E_inv_perm = np.dot(d_emp.pmv, 1.0 / d_emp.atoms[0])

    # Split pLvl grid into n_buckets by cumulative weight
    cum_w = np.cumsum(pLvl_weights)
    bucket_edges = np.linspace(0.0, 1.0, n_buckets + 1)

    buckets = []
    for b in range(n_buckets):
        lo = np.searchsorted(cum_w, bucket_edges[b])
        hi = np.searchsorted(cum_w, bucket_edges[b + 1])
        if lo >= hi:
            continue
        w_b = pLvl_weights[lo:hi]
        total_w = w_b.sum()
        if total_w < 1e-15:
            continue

        E_check_nrm_b = np.dot(w_b, check_nrm_grid[lo:hi]) / total_w
        E_check_level_b = np.dot(w_b, check_level_grid[lo:hi]) / total_w
        E_pLvl_b = np.dot(w_b, pLvl_grid[lo:hi]) / total_w

        mNrm_shift = np.zeros(J_micro)
        for j in range(J_micro):
            if j == 0:
                mNrm_shift[j] = E_check_nrm_b * E_inv_perm
            else:
                mNrm_shift[j] = E_check_nrm_b

        buckets.append({
            'weight': total_w,
            'mNrm_shift': mNrm_shift,
            'E_pLvl_b': E_pLvl_b,
            'E_check_level_b': E_check_level_b,
            'E_check_nrm_b': E_check_nrm_b,  # normalized check = E[CheckStimLvl*phi(pLvl)/pLvl | bucket]
                                             # (for xi/TranShk injection, e.g. the 5D joint kernel)
        })

    # Rescale E_pLvl_b so weighted average matches analytical E_pLvl exactly.
    # Quantile boundary discretization causes sum(w_b * E_pLvl_b) != E_pLvl;
    # the ~0.004% per-period mismatch accumulates to ~3% NPV bias.
    weighted_E_pLvl = sum(b['weight'] * b['E_pLvl_b'] for b in buckets)
    if weighted_E_pLvl > 0:
        correction = E_pLvl / weighted_E_pLvl
        for b in buckets:
            b['E_pLvl_b'] *= correction

    return buckets


def _tax_cut_employed_factor(agent, macro_t, shock_type):
    """
    Returns 1.0 always — the TM no longer applies a run-time TranShk
    rescaling for the TaxCut policy. (BUG-023 follow-up.)

    HISTORY. The original comment here read: "MC applies TaxCutIncFactor
    to employed TranShk via tax_cut_multiplier in
    make_idiosyncratic_shock_histories; the discrete IncShkDstn objects
    are not rescaled on the TranShk margin (see Simulate.py atoms[0][1]
    typo)." That was a workaround for BUG-023: the agent's
    `IncShkDstn_recessionTaxCut` was constructed with a typo
    (`atoms[0][1] *= TaxCutIncFactor`, which mutates one PermShk atom)
    and the run-time call to `_scaled_employed_joint_inc_dstn(...,
    employed_tran_shk_scale=this function's return value)` applied the
    intended TranShk × TaxCutIncFactor rescaling at simulation time as
    compensation.

    With the typo fixed at construction time (BUG-023 commit), the
    agent's `IncShkDstn_recessionTaxCut` has TranShk pre-rescaled by
    TaxCutIncFactor for the tax-cut macro states. The run-time
    workaround would now DOUBLE-COUNT the rescaling: the period TM
    would evolve the m-distribution with `TranShk × TaxCutIncFactor²`
    while the cFunc was solved against `TranShk × TaxCutIncFactor`.
    That double-count was the residual ~1.1% MC↔TM gap on
    `norec-taxcut` after BUG-023 was fixed at the construction site.

    The fix is to disable the run-time rescaling. The agent's
    pre-rescaled IncShkDstn is used directly by `build_experiment_period_tm`
    and `compute_period_aggregates_tm`, which is consistent with
    MC: MC's `tran_shock_fixed_hist` is generated from the BASE
    distribution before `switch_shock_type`, and the run-time
    `tax_cut_multiplier` applies the rescaling on top. Both methods
    end up with TranShk × TaxCutIncFactor at simulation time, applied
    once.
    """
    return 1.0


def _scaled_employed_joint_inc_dstn(dstn, factor):
    """Deep-copy joint PermShk/TranShk dstn with TranShk (atoms[1]) scaled."""
    if factor == 1.0:
        return dstn
    d = deepcopy(dstn)
    at0 = np.asarray(d.atoms[0], dtype=np.float64)
    at1 = np.asarray(d.atoms[1], dtype=np.float64) * factor
    d.atoms = (at0, at1)
    return d


def build_experiment_period_tm(agent, macro_t, macro_next, dist_mGrid, Cratio=1.0,
                               neutral_measure=False, mNrm_shift=None,
                               employed_tran_shk_scale=1.0,
                               ad_tran_shk_scale=1.0):
    """
    Build a (M*J_micro) x (M*J_micro) TM for one experiment period.

    At period t the agent is in macro state macro_t; next period is macro_next.
    Only the J_micro (=num_base_MrkvStates) micro states are active at any time.

    Parameters
    ----------
    mNrm_shift : np.ndarray or None, shape (J_micro,)
        If provided, shift each micro state's effective mNrm by this amount
        when evaluating the consumption/savings policy.  Used for stimulus
        checks that add to market resources in a single period.
    ad_tran_shk_scale : float
        Aggregate demand factor applied to TranShk in ALL micro states.
        In MC, this is AggDemandFac = Cratio^(ADelasticity * RecState).
        Defaults to 1.0 (no AD scaling).
    """
    J_micro = agent.num_base_MrkvStates
    M = len(dist_mGrid)
    src_offset = macro_t * J_micro
    dst_offset = macro_next * J_micro

    sol = agent.solution[0]
    aPol_2d = np.empty((J_micro, M), dtype=np.float64)
    cPol = []
    for j in range(J_micro):
        cFunc_j = sol.cFunc[src_offset + j]
        shift_j = mNrm_shift[j] if mNrm_shift is not None else 0.0
        m_eff = dist_mGrid + shift_j
        cPol_j = cFunc_j(m_eff, Cratio * np.ones_like(m_eff))
        aPol_j = np.maximum(m_eff - cPol_j, 0.0)
        cPol.append(cPol_j)
        aPol_2d[j, :] = aPol_j

    IncShkDstn_list = []
    for jp in range(J_micro):
        raw = agent.IncShkDstn[0][dst_offset + jp]
        if jp == 0 and employed_tran_shk_scale != 1.0:
            raw = _scaled_employed_joint_inc_dstn(raw, employed_tran_shk_scale)
        IncShkDstn_list.append(raw)

    # Channel A: scale TranShk by AggDemandFac for all micro states
    if ad_tran_shk_scale != 1.0:
        IncShkDstn_list = [
            _scaled_employed_joint_inc_dstn(d, ad_tran_shk_scale)
            for d in IncShkDstn_list
        ]

    micro_trans = agent.CondMrkvArrays[macro_next]

    Rfree_arr = np.asarray(agent.Rfree[:J_micro], dtype=np.float64)
    PermGroFac_arr = np.asarray(agent.PermGroFac[0][:J_micro], dtype=np.float64)
    LivPrb_arr = np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64)
    T_age = getattr(agent, 'T_age', None)
    LivPrb_arr = _effective_LivPrb(LivPrb_arr, T_age)

    markov_ergodic_micro = _solve_markov_ergodic(micro_trans)

    # See math-derive-harm (Q-newborn), (TM-Q-entry), (Q-propagation)
    nb_dstn = _to_neutral_measure(IncShkDstn_list) if neutral_measure else IncShkDstn_list
    NewBornDist = _make_newborn_dist(dist_mGrid, nb_dstn, markov_ergodic_micro)

    TranMatrix = _build_period_tm(
        dist_mGrid, aPol_2d, IncShkDstn_list, micro_trans,
        Rfree_arr, PermGroFac_arr, LivPrb_arr, NewBornDist,
        neutral_measure=neutral_measure,
    )
    return TranMatrix, cPol


def _solve_markov_ergodic(trans_matrix):
    """Solve for the stationary distribution of a row-stochastic transition matrix."""
    P = trans_matrix.T
    n = P.shape[0]
    A_mat = np.vstack([P - np.eye(n), np.ones(n)])
    b_vec = np.zeros(n + 1)
    b_vec[-1] = 1.0
    ergodic, _, _, _ = np.linalg.lstsq(A_mat, b_vec, rcond=None)
    return ergodic


def _mc_hit_uses_recession_urate(shock_type):
    """
    True if AggFiscalModel.hit_with_recession_shock uses Urate_recession for
    the initial employment draw (before EconomyMrkvNow_hist is applied).
    """
    if shock_type is None:
        return False
    return shock_type in (
        'recession', 'recessionUI', 'recessionTaxCut', 'recessionCheck',
    )


def _compute_post_hit_urate(agent, initial_macro_state):
    """
    Analytically compute the effective unemployment rate after MC's two-step
    recession initialization: (1) hit_with_recession_shock shifts Urate to
    Urate_recession, then (2) get_micro_markv_states_guts applies the micro
    Markov transition for initial_macro_state, which partially pulls
    unemployment back toward that column's ergodic mix.

    Returns the unemployment rate after both steps, eliminating the need for
    an empirically-tuned blend factor.
    """
    J = agent.num_base_MrkvStates
    Un = float(agent.Urate_normal)
    Ur = float(agent.Urate_recession)

    # Step 1: micro-state marginal after hit_with_recession_shock.
    # Base ergodic has micro states [employed, unemp_spell_1, ..., unemp_spell_J-1]
    # with total Urate = Un.  The hit moves fraction f of employed → spell-1.
    base_mrkv = agent.MrkvArray_base[0]
    vals, vecs = np.linalg.eig(base_mrkv.T)
    idx = np.argmin(np.abs(np.abs(vals) - 1.0))
    pi_erg = np.real(vecs[:, idx])
    pi_erg = pi_erg / np.sum(pi_erg)

    f = (Ur - Un) / (1.0 - Un) if Un < 1.0 else 0.0
    pi_hit = pi_erg.copy()
    pi_hit[1] += pi_hit[0] * f
    pi_hit[0] *= (1.0 - f)

    # Step 2: apply one micro Markov transition for initial_macro_state.
    # CondMrkvArrays[i][j, k] = P(micro=k | micro_prev=j, macro=i).
    T_micro = agent.CondMrkvArrays[initial_macro_state]
    pi_post = pi_hit @ T_micro

    return 1.0 - pi_post[0]


def adapt_initial_distribution(baseline_ergodic, agent, initial_macro_state,
                               dist_mGrid, shock_type=None):
    """
    Adapt the baseline ergodic distribution to the initial experiment state.

    For recession experiments: shift probability mass from employed to unemployed
    to match the target unemployment rate, mirroring hit_with_recession_shock().

    When the initial macro state is even (expansion) and the shock type triggers
    MC's recession hit, the target Urate is computed analytically via
    _compute_post_hit_urate: hit pushes Urate to Urate_recession, then the
    micro Markov transition for that expansion column partially pulls it back.
    """
    J_micro = agent.num_base_MrkvStates
    M = len(dist_mGrid)
    dist = baseline_ergodic.copy()

    is_recession_macro = (initial_macro_state % 2 == 1)
    Un = float(agent.Urate_normal)
    Ur = float(agent.Urate_recession)
    if is_recession_macro:
        target_Urate = Ur
    elif _mc_hit_uses_recession_urate(shock_type):
        target_Urate = _compute_post_hit_urate(agent, initial_macro_state)
    else:
        target_Urate = Un
    current_Urate = agent.Urate_normal

    if target_Urate <= current_Urate:
        return dist

    employed_mass = dist[0*M : 1*M]
    total_employed = np.sum(employed_mass)
    total_pop = np.sum(dist)

    fraction_to_move = (target_Urate - current_Urate) / (1.0 - current_Urate)
    mass_to_move = fraction_to_move * total_employed

    dist[0*M : 1*M] *= (1.0 - fraction_to_move)
    dist[1*M : 2*M] += fraction_to_move * employed_mass

    s = np.sum(dist)
    if s > 0:
        dist /= s
    return dist


def compute_period_aggregates_tm(dist, cPol, dist_mGrid, IncShkDstn_list,
                                 Splurge, AggDemandFac=1.0,
                                 TranShk_addition=None):
    """
    Compute normalized consumption and income from a distribution vector.
    See math-derive (splurge) and (TM-agg).

    Works correctly for both P-measure and Q-measure (neutral) distributions:
    under Q, the policy consumption integral E_Q[c(m)] changes but the
    splurge and income terms are invariant because Q-state fractions equal
    P-state fractions exactly — see math-derive-harm (Q-P-frac-equal),
    (Q-splurge), (Q-income), (Q-full-cnrm).  On a finite grid the
    Q-marginal fractions may differ from the propagated standard fractions
    by ~O(1e-6); see propagate_experiment_tm for the separate tracking.

    Parameters
    ----------
    dist : np.ndarray, shape (M*J_micro,)
    cPol : list of J_micro arrays, each shape (M,)
    dist_mGrid : np.ndarray, shape (M,)
    IncShkDstn_list : list of J_micro shock distributions for current states
    Splurge : float
    AggDemandFac : float
    TranShk_addition : np.ndarray or None, shape (J_micro,)
        Additional transitory income per micro state (e.g. stimulus check).
        Added to E[TranShk] for splurge and income calculations.

    Returns
    -------
    dict with C_splurge_nrm, Income_nrm
    """
    M = len(dist_mGrid)
    J = len(cPol)

    C_nrm = 0.0
    state_fracs = np.zeros(J)
    E_TranShk = np.zeros(J)
    for j in range(J):
        dstn_j = dist[j * M : (j + 1) * M]
        state_fracs[j] = np.sum(dstn_j)
        C_nrm += np.dot(cPol[j], dstn_j)
        d = IncShkDstn_list[j]
        E_TranShk[j] = np.dot(d.pmv, d.atoms[1])

    E_TranShk_total = E_TranShk.copy()
    if TranShk_addition is not None:
        E_TranShk_total = E_TranShk_total + TranShk_addition

    # See math-derive (splurge): c_nrm = (1-S)*c_policy + S*E[theta]*ADF
    splurge_term = Splurge * np.dot(state_fracs, E_TranShk_total) * AggDemandFac
    C_splurge_nrm = (1.0 - Splurge) * C_nrm + splurge_term
    Income_nrm = np.dot(state_fracs, E_TranShk_total) * AggDemandFac

    return {'C_splurge_nrm': C_splurge_nrm, 'Income_nrm': Income_nrm}


def _apply_micro_transition(dist, micro_trans, M, dist_mGrid=None,
                            E_TranShk=None):
    """
    Redistribute probability mass across micro states, optionally shifting
    mNrm to reflect the destination state's income.

    Mirrors MC's ``get_micro_markv_states_guts``: agents change their micro
    (employment) state according to the row-stochastic ``micro_trans``
    matrix.  In MC, the period-0 income draw comes from the *destination*
    state, so agents who change state get a different TranShk and therefore
    a different mNrm = bNrm + TranShk.

    When ``dist_mGrid`` and ``E_TranShk`` are provided, mass moving from
    ``j_src`` to ``j_dst`` is shifted on the mNrm grid by
    ``E_TranShk[j_dst] - E_TranShk[j_src]``.  For unemployed states where
    TranShk is deterministic, this is exact.  For the employed state (where
    TranShk has a distribution), it is an approximation using the mean;
    however, employed-state transitions are typically the same in base and
    experiment, so errors cancel in the treatment effect.

    Parameters
    ----------
    dist : np.ndarray, shape (M * J_micro,)
    micro_trans : np.ndarray, shape (J_micro, J_micro), row-stochastic
    M : int, number of mNrm grid points
    dist_mGrid : np.ndarray or None, shape (M,)
        The mNrm grid.  Required when ``E_TranShk`` is provided.
    E_TranShk : np.ndarray or None, shape (J_micro,)
        Expected transitory shock per micro state.  When provided, mass
        moving between states with different E_TranShk is shifted on the
        mNrm grid accordingly.

    Returns
    -------
    new_dist : np.ndarray, shape (M * J_micro,)
    """
    J = micro_trans.shape[0]
    new_dist = np.zeros_like(dist)
    do_shift = (E_TranShk is not None and dist_mGrid is not None)
    for j_src in range(J):
        src_slice = dist[j_src * M : (j_src + 1) * M]
        for j_dst in range(J):
            prob = micro_trans[j_src, j_dst]
            if prob < 1e-15:
                continue
            contributing = prob * src_slice
            if do_shift:
                delta = E_TranShk[j_dst] - E_TranShk[j_src]
            else:
                delta = 0.0
            if abs(delta) < 1e-12:
                new_dist[j_dst * M : (j_dst + 1) * M] += contributing
            else:
                # Shift mass on the mNrm grid: an agent at mNrm = m should
                # move to mNrm = m + delta.  Equivalently, the new density
                # at grid point m equals the old density at m - delta.
                shifted = np.interp(dist_mGrid - delta, dist_mGrid,
                                    contributing, left=0.0, right=0.0)
                # Preserve total mass (interp boundary clipping can lose some)
                total_orig = np.sum(contributing)
                total_shifted = np.sum(shifted)
                if total_shifted > 1e-30:
                    shifted *= total_orig / total_shifted
                new_dist[j_dst * M : (j_dst + 1) * M] += shifted
    # Preserve normalisation
    s = np.sum(new_dist)
    if s > 0:
        new_dist /= s
    return new_dist


def propagate_experiment_tm(agent, baseline_ergodic, EconomyMrkv_init,
                            dist_mGrid, E_pLvl, Cratio=1.0, act_T=None,
                            neutral_measure=False, check_info=None,
                            shock_type=None, base_aPol=None,
                            ADelasticity=0.0, ad_timing=_HAFISCAL_TM_AD_TIMING,
                            cfunc_offset=_HAFISCAL_TM_CFUNC_OFFSET):
    """
    Propagate a single agent type through a time-varying experiment.

    Parameters
    ----------
    agent : AggFiscalType (already solved under experiment Markov structure)
    baseline_ergodic : np.ndarray, ergodic distribution over (m, micro_state)
    EconomyMrkv_init : list of macro Markov states for each period
    dist_mGrid : np.ndarray
    E_pLvl : float, expected permanent income level for this type
    Cratio : float or array-like
        Aggregate demand ratio.  Scalar (used for all periods) or 1-D array
        of length act_T (one value per period).
    act_T : int, total periods (defaults to len(EconomyMrkv_init))
    check_info : dict or None
        If provided, inject a stimulus check in the specified period.
        Keys: 'period' (int), 'buckets' (list from _compute_check_buckets).
    shock_type : str or None
        Passed to adapt_initial_distribution so recession* shocks use
        Urate_recession for the initial micro mix (matches MC
        hit_with_recession_shock even when EconomyMrkv_init[0] is even).
        If 'TaxCut' or 'recessionTaxCut', also scale employed TranShk by
        TaxCutIncFactor in the MC tax-cut window.
    base_aPol : np.ndarray or None, shape (J_micro, M)
        Baseline savings policy on the TM grid.  When provided, the period-0
        distribution is built by a half-step TM: base aPol (consumption from
        ergodic) + experiment micro transition + income draw.  This matches
        MC's period 0, where agents consumed during burn-in (base policy) and
        then received experiment income.  Without this, falls back to
        _apply_micro_transition (which incorrectly uses pre-consumption mNrm).
    ADelasticity : float
        AD feedback elasticity.  When > 0, income (TranShk) in each period
        is scaled by AggDemandFac = Cratio_t^(ADelasticity * RecState_t),
        matching MC's Channel A feedback.  Default 0.0 (no feedback).

    Returns
    -------
    dict with per-period AggCons, AggIncome arrays (un-aggregated, for this type)
    """
    if act_T is None:
        act_T = len(EconomyMrkv_init)

    # Convert scalar Cratio to per-period array
    if np.isscalar(Cratio):
        Cratio_path = np.full(act_T, float(Cratio))
    else:
        Cratio_path = np.asarray(Cratio, dtype=float)

    J_micro = agent.num_base_MrkvStates
    Splurge = agent.Splurge

    # Build the period-0 distribution by a half-step TM.
    #
    # The ergodic is a beginning-of-period (pre-consumption) distribution.
    # In MC, the experiment's period 0 starts from the burn-in's end-of-
    # period state (aNrm = mNrm - cFunc(mNrm)), then draws new income
    # from the experiment's micro transition.  The correct period-0
    # distribution is therefore:
    #   ergodic → consume (base policy) → save → SPIKE → transition → income
    #
    # CRITICAL TIMING: The unemployment spike must happen AFTER consumption,
    # not before.  In MC, agents consumed during the burn-in under their
    # burn-in Markov state (typically employed), THEN the spike changed
    # their state label.  If we spike before consumption, newly-spiked
    # agents would consume under the unemployed policy instead of the
    # employed policy, producing systematically different savings.
    # (BUG identified 2026-04-10: spiking before the half-step made
    # newly-unemployed agents save under state 1's aPol instead of
    # state 0's, overestimating their savings by ~85% and shifting
    # the post-half-step state 1 mean(m) from 0.77 to 0.80.)
    #
    # When base_aPol is provided, we build this half-step TM via
    # _build_period_tm with the base savings policy and experiment
    # transition + income.  The spike is applied AFTER the half-step.
    initial_macro = EconomyMrkv_init[0] if len(EconomyMrkv_init) > 0 else 0

    # Start from the UN-SPIKED ergodic: agents consume under their
    # burn-in Markov states (matching MC's burn-in consumption).
    dist = baseline_ergodic.copy()

    if base_aPol is not None:
        # Build half-step TM: base aPol + experiment micro transition + income
        M = len(dist_mGrid)
        dst_offset = initial_macro * J_micro
        IncShkDstn_init = []
        for jp in range(J_micro):
            IncShkDstn_init.append(agent.IncShkDstn[0][dst_offset + jp])
        # Apply TranShk scaling for tax cut experiments in the half-step.
        emp_tc_init = _tax_cut_employed_factor(agent, initial_macro, shock_type)
        if emp_tc_init != 1.0:
            IncShkDstn_init[0] = _scaled_employed_joint_inc_dstn(
                IncShkDstn_init[0], emp_tc_init)

        # Blend the unemployment spike INTO the CondMrkv for the half-step.
        #
        # MC's timing: consume(burn-in) → spike → CondMrkv → income.
        # The spike moves fraction f of state 0 → state 1 BEFORE CondMrkv.
        # This is equivalent to state-0 agents using a blended transition
        # row: (1-f)×CondMrkv[0,:] + f×CondMrkv[1,:], while consuming
        # under state 0's aPol (correct: consumption before spike).
        #
        # For states 1-3 (not affected by spike), transitions are unchanged.
        micro_trans_init = agent.CondMrkvArrays[initial_macro].copy()
        is_recession = (initial_macro % 2 == 1)
        _uses_spike = is_recession or _mc_hit_uses_recession_urate(shock_type)
        if _uses_spike:
            Un = float(agent.Urate_normal)
            Ur = float(agent.Urate_recession) if is_recession else Un
            if Ur > Un:
                spike_frac = (Ur - Un) / (1.0 - Un)
                micro_trans_init[0, :] = (
                    (1.0 - spike_frac) * agent.CondMrkvArrays[initial_macro][0, :]
                    + spike_frac * agent.CondMrkvArrays[initial_macro][1, :]
                )

        Rfree_arr = np.asarray(agent.Rfree[:J_micro], dtype=np.float64)
        PermGroFac_arr = np.asarray(agent.PermGroFac[0][:J_micro], dtype=np.float64)
        LivPrb_arr = np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64)
        T_age = getattr(agent, 'T_age', None)
        LivPrb_arr = _effective_LivPrb(LivPrb_arr, T_age)

        markov_ergodic_micro = _solve_markov_ergodic(micro_trans_init)
        nb_dstn = (_to_neutral_measure(IncShkDstn_init) if neutral_measure
                   else IncShkDstn_init)
        NewBornDist = _make_newborn_dist(dist_mGrid, nb_dstn, markov_ergodic_micro)

        init_TM = _build_period_tm(
            dist_mGrid, base_aPol, IncShkDstn_init, micro_trans_init,
            Rfree_arr, PermGroFac_arr, LivPrb_arr, NewBornDist,
            neutral_measure=neutral_measure,
        )
        dist = init_TM @ dist
        if sp.issparse(dist):
            dist = np.asarray(dist).flatten()
        dist = np.maximum(dist, 0.0)
        s = np.sum(dist)
        if s > 0:
            dist /= s
    else:
        # Fallback: simple micro transition with mNrm shift
        E_TranShk_micro = np.zeros(J_micro)
        for j in range(J_micro):
            d_j = agent.IncShkDstn[0][j]
            E_TranShk_micro[j] = np.dot(d_j.pmv, d_j.atoms[1])
        dist = _apply_micro_transition(dist, agent.CondMrkvArrays[initial_macro],
                                       len(dist_mGrid), dist_mGrid=dist_mGrid,
                                       E_TranShk=E_TranShk_micro)

    # No separate spike step needed: the spike is blended into the
    # half-step's CondMrkv (see micro_trans_init above).

    C_series = np.zeros(act_T)
    Y_series = np.zeros(act_T)

    tm_cache = {}
    bucket_carry = None

    # BUG-015 fix: track E_pLvl correction for unemployment-dependent growth.
    # See math-derive (pLvl-recurrence), (g-base), (E-p-evolution).
    # In the MC, unemployed agents get PermShk=1.0 (no growth) while employed
    # agents get PermShk=PermGroFac*random (growth at G).  The TM normalizes
    # by PermGroFac for ALL agents, so its implicit E_pLvl assumes universal
    # growth at G.  pLvl_factor tracks the ratio E[p_t]/E[p_ss].
    #
    # Exact recurrence (pLvl-recurrence): F' = (1-d)*g_rec*F + [1-(1-d)*g_base]
    # AR(1) coefficient (1-d)*g_base => half-life (half-life) ~155q.
    M_grid = len(dist_mGrid)
    u_ergodic = 1.0 - np.sum(baseline_ergodic[:M_grid])
    # SST: same g as MC/TM per-state PermGroFac (effective_pLvl_growth)
    g_base_pLvl = effective_pLvl_growth(agent, u_ergodic)
    # See math-derive-appendix (L-eff)
    _LivPrb_eff = _effective_LivPrb(
        np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64),
        getattr(agent, 'T_age', None))
    delta_eff = 1.0 - np.mean(_LivPrb_eff)
    # See math-derive (pLvl-recurrence): F_0 = 1 (start at steady state)
    pLvl_factor = 1.0

    # Under the Harmenberg neutral measure, the distribution is p-weighted,
    # so sum(dist[:M]) gives the p-weighted employment fraction, not the
    # actual P(employed).  Track standard state fractions separately for u_t.
    # See math-derive-harm (Q-state-frac), (std-frac-init), (std-frac-init-halfstep).
    if neutral_measure:
        # See math-derive-harm (std-frac-init): f_j(0) from adapted dist
        adapted_dist = adapt_initial_distribution(
            baseline_ergodic, agent,
            EconomyMrkv_init[0] if len(EconomyMrkv_init) > 0 else 0,
            dist_mGrid, shock_type=shock_type,
        )
        _std_state_fracs = np.array([
            np.sum(adapted_dist[j * M_grid:(j + 1) * M_grid])
            for j in range(J_micro)
        ])
        # See math-derive-harm (std-frac-init-halfstep): propagate through
        # the initial Markov transition if a half-step TM was applied.
        if base_aPol is not None:
            _std_state_fracs = _propagate_state_fracs(
                _std_state_fracs,
                agent.CondMrkvArrays[initial_macro],
                np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64),
                getattr(agent, 'T_age', None))
    else:
        _std_state_fracs = None

    for t in range(act_T):
        macro_t = EconomyMrkv_init[t] if t < len(EconomyMrkv_init) else 0
        macro_next = EconomyMrkv_init[t + 1] if (t + 1) < len(EconomyMrkv_init) else 0

        is_check_period = (check_info is not None and t == check_info['period'])
        emp_tc = _tax_cut_employed_factor(agent, macro_t, shock_type)
        emp_tc_next = _tax_cut_employed_factor(agent, macro_next, shock_type)
        if neutral_measure:
            # See math-derive-harm (Q-P-frac-equal), (std-frac-recurrence):
            # use standard state fractions for u_t (not the p-weighted dist).
            u_rec_t = 1.0 - _std_state_fracs[0]
        else:
            u_rec_t = 1.0 - np.sum(dist[:M_grid])

        if is_check_period:
            # Check period: build one TM per pLvl bucket, scale each by
            # its own E_pLvl_b to capture the correlation between the
            # check's normalized shift and the level scaling.
            IncShkDstn_t = [agent.IncShkDstn[0][macro_t * J_micro + j] for j in range(J_micro)]
            if emp_tc != 1.0:
                IncShkDstn_t[0] = _scaled_employed_joint_inc_dstn(IncShkDstn_t[0], emp_tc)
            N_agent = agent.AgentCount

            # Channel A: AggDemandFac for check period
            # AD-timing: see BUGS_private/HAFiscal_BUG-030_mill_rule_RecState_timing.md
            # CFunc-offset: see BUGS_private/HAFiscal_BUG-041_TM_CFunc_cell_offset_one_period.md
            Cratio_t = _cratio_for_period(Cratio_path, t, cfunc_offset)
            if ad_timing == 'lagged' and t > 0:
                macro_prev = EconomyMrkv_init[t - 1] if (t - 1) < len(EconomyMrkv_init) else 0
                RecState_t = float(macro_prev % 2 == 1)
            else:
                RecState_t = float(macro_t % 2 == 1)
            AggDemandFac_t = (Cratio_t ** (ADelasticity * RecState_t)
                              if ADelasticity > 0 else 1.0)

            # Base E_TranShk (without check) for splurge decomposition
            M = len(dist_mGrid)
            state_fracs = np.array([np.sum(dist[j*M:(j+1)*M]) for j in range(J_micro)])
            E_TranShk_base = np.array([
                np.dot(IncShkDstn_t[j].pmv, IncShkDstn_t[j].atoms[1])
                for j in range(J_micro)
            ])

            C_level_agg = 0.0
            Y_level_agg = 0.0
            dist_next_agg = np.zeros_like(dist)
            bucket_dists_next = []

            for bucket in check_info['buckets']:
                w_b = bucket['weight']
                E_pLvl_b = bucket['E_pLvl_b']
                E_check_level_b = bucket['E_check_level_b']

                TM_b, cPol_b = build_experiment_period_tm(
                    agent, macro_t, macro_next, dist_mGrid, Cratio_t,
                    neutral_measure=neutral_measure,
                    mNrm_shift=bucket['mNrm_shift'],
                    employed_tran_shk_scale=emp_tc_next,
                    ad_tran_shk_scale=AggDemandFac_t,
                )

                # See math-derive (TM-agg): C_level = N * E[p] * F_t * c_nrm
                C_nrm_b = sum(np.dot(cPol_b[j], dist[j*M:(j+1)*M]) for j in range(J_micro))
                eff_pLvl_b = E_pLvl_b * pLvl_factor
                nonsplurge_b = (1.0 - Splurge) * C_nrm_b * N_agent * eff_pLvl_b

                # Splurge from base TranShk: S * E_TranShk_base * AggDemandFac * E_pLvl_b
                splurge_base_b = Splurge * np.dot(state_fracs, E_TranShk_base) * AggDemandFac_t * N_agent * eff_pLvl_b

                # Splurge from check: S * CheckStimLvl * E[phase_out|b]
                # (pLvl cancels in the income->levels conversion)
                splurge_check_b = Splurge * E_check_level_b * N_agent

                C_level_agg += w_b * (nonsplurge_b + splurge_base_b + splurge_check_b)

                # Income: base part scales by AggDemandFac * E_pLvl_b, check part is in levels
                income_base_b = np.dot(state_fracs, E_TranShk_base) * AggDemandFac_t * N_agent * eff_pLvl_b
                income_check_b = E_check_level_b * N_agent
                Y_level_agg += w_b * (income_base_b + income_check_b)

                dist_next_b = TM_b @ dist
                if sp.issparse(dist_next_b):
                    dist_next_b = np.asarray(dist_next_b).flatten()
                dist_next_agg += w_b * dist_next_b

                # Save per-bucket next distribution for carry-forward
                dist_b_normed = np.maximum(dist_next_b, 0.0)
                s_b = np.sum(dist_b_normed)
                if s_b > 0:
                    dist_b_normed /= s_b
                bucket_dists_next.append(dist_b_normed)

            C_series[t] = C_level_agg
            Y_series[t] = Y_level_agg

            # Store per-bucket state for carry-forward at t>=1
            bucket_carry = {
                'dists': bucket_dists_next,
                'weights': [b['weight'] for b in check_info['buckets']],
                'E_pLvl_b': [b['E_pLvl_b'] for b in check_info['buckets']],
            }

            dist = np.maximum(dist_next_agg, 0.0)
            s = np.sum(dist)
            if s > 0:
                dist /= s

            # See math-derive (pLvl-recurrence): F' = (1-d)*g_rec*F + [1-(1-d)*g_base]
            g_rec_t = effective_pLvl_growth(agent, u_rec_t)
            pLvl_factor = ((1.0 - delta_eff) * g_rec_t * pLvl_factor
                           + (1.0 - (1.0 - delta_eff) * g_base_pLvl))
            if neutral_measure and _std_state_fracs is not None:
                _std_state_fracs = _propagate_state_fracs(
                    _std_state_fracs, agent.CondMrkvArrays[macro_next],
                    np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64),
                    getattr(agent, 'T_age', None))
            continue

        # AD-timing: see BUGS_private/HAFiscal_BUG-030_mill_rule_RecState_timing.md
        # CFunc-offset: see BUGS_private/HAFiscal_BUG-041_TM_CFunc_cell_offset_one_period.md
        Cratio_t = _cratio_for_period(Cratio_path, t, cfunc_offset)

        # Channel A: AggDemandFac = Cratio^(ADelasticity * RecState)
        if ad_timing == 'lagged' and t > 0:
            macro_prev = EconomyMrkv_init[t - 1] if (t - 1) < len(EconomyMrkv_init) else 0
            RecState_t = float(macro_prev % 2 == 1)
        else:
            RecState_t = float(macro_t % 2 == 1)
        AggDemandFac_t = (Cratio_t ** (ADelasticity * RecState_t)
                          if ADelasticity > 0 else 1.0)

        cache_key = (macro_t, macro_next, emp_tc_next, Cratio_t, AggDemandFac_t)
        if cache_key in tm_cache:
            TM_t, cPol_t = tm_cache[cache_key]
        else:
            TM_t, cPol_t = build_experiment_period_tm(
                agent, macro_t, macro_next, dist_mGrid, Cratio_t,
                neutral_measure=neutral_measure,
                employed_tran_shk_scale=emp_tc_next,
                ad_tran_shk_scale=AggDemandFac_t,
            )
            tm_cache[cache_key] = (TM_t, cPol_t)

        IncShkDstn_t = [agent.IncShkDstn[0][macro_t * J_micro + j] for j in range(J_micro)]
        if emp_tc != 1.0:
            IncShkDstn_t[0] = _scaled_employed_joint_inc_dstn(IncShkDstn_t[0], emp_tc)

        if bucket_carry is not None:
            # Per-bucket carry: aggregate using per-bucket E_pLvl_b to
            # preserve Cov(Δc, pLvl) from the lump-sum check.
            N_agent = agent.AgentCount
            C_level_agg = 0.0
            Y_level_agg = 0.0

            for b_idx in range(len(bucket_carry['dists'])):
                w_b = bucket_carry['weights'][b_idx]
                E_pLvl_b = bucket_carry['E_pLvl_b'][b_idx]
                dist_b = bucket_carry['dists'][b_idx]

                agg_b = compute_period_aggregates_tm(
                    dist_b, cPol_t, dist_mGrid, IncShkDstn_t, Splurge,
                    AggDemandFac=AggDemandFac_t,
                )

                # See math-derive (TM-agg): C_level = N * E[p] * F_t * c_nrm
                scale_b = N_agent * E_pLvl_b * pLvl_factor
                C_level_agg += w_b * scale_b * agg_b['C_splurge_nrm']
                Y_level_agg += w_b * scale_b * agg_b['Income_nrm']

                dist_b_next = TM_t @ dist_b
                if sp.issparse(dist_b_next):
                    dist_b_next = np.asarray(dist_b_next).flatten()
                dist_b_next = np.maximum(dist_b_next, 0.0)
                s_b = np.sum(dist_b_next)
                if s_b > 0:
                    dist_b_next /= s_b
                bucket_carry['dists'][b_idx] = dist_b_next

            C_series[t] = C_level_agg
            Y_series[t] = Y_level_agg

            dist = sum(bucket_carry['weights'][i] * bucket_carry['dists'][i]
                       for i in range(len(bucket_carry['dists'])))
            dist = np.maximum(dist, 0.0)
            s = np.sum(dist)
            if s > 0:
                dist /= s

            # See math-derive (pLvl-recurrence): F' = (1-d)*g_rec*F + [1-(1-d)*g_base]
            g_rec_t = effective_pLvl_growth(agent, u_rec_t)
            pLvl_factor = ((1.0 - delta_eff) * g_rec_t * pLvl_factor
                           + (1.0 - (1.0 - delta_eff) * g_base_pLvl))
            if neutral_measure and _std_state_fracs is not None:
                _std_state_fracs = _propagate_state_fracs(
                    _std_state_fracs, agent.CondMrkvArrays[macro_next],
                    np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64),
                    getattr(agent, 'T_age', None))
            continue

        agg_t = compute_period_aggregates_tm(
            dist, cPol_t, dist_mGrid, IncShkDstn_t, Splurge,
            AggDemandFac=AggDemandFac_t,
        )

        # See math-derive (TM-agg) / math-derive-harm (NM-agg):
        # C_level = N * E[p] * F_t * c_nrm^{P or Q}
        scale = agent.AgentCount * E_pLvl * pLvl_factor
        C_series[t] = scale * agg_t['C_splurge_nrm']
        Y_series[t] = scale * agg_t['Income_nrm']

        dist = TM_t @ dist
        if sp.issparse(dist):
            dist = np.asarray(dist).flatten()
        dist = np.maximum(dist, 0.0)
        s = np.sum(dist)
        if s > 0:
            dist /= s

        # See math-derive (pLvl-recurrence): F' = (1-d)*g_rec*F + [1-(1-d)*g_base]
        g_rec_t = effective_pLvl_growth(agent, u_rec_t)
        pLvl_factor = ((1.0 - delta_eff) * g_rec_t * pLvl_factor
                       + (1.0 - (1.0 - delta_eff) * g_base_pLvl))
        if neutral_measure and _std_state_fracs is not None:
            _std_state_fracs = _propagate_state_fracs(
                _std_state_fracs, agent.CondMrkvArrays[macro_next],
                np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64),
                getattr(agent, 'T_age', None))

    return {'AggCons': C_series, 'AggIncome': Y_series}


def unemployment_rate_for_tm_synthetic_pLvl(bd_i, agent):
    """
    Unemployment rate for ``effective_pLvl_growth`` and
    ``effective_perm_shock_variance_periods`` when drawing synthetic ``pLvl``
    next to a TM ergodic draw on ``(m,j)``.

    Uses ``bd_i['u_ergodic']`` from ``compute_baseline_tm_data`` — the mass on
    non-employed micro states implied by the **same** transition matrix as the
    ``(m,j)`` initialization — so the growth and shock-variance scaling for the
    synthetic ``p`` marginal match what TM aggregation uses for ``E[pLvl]``.
    Pair with ``income_process_sst.effective_perm_shock_periods_for_t_age`` (not
    ``t_age`` passed directly into ``effective_perm_shock_variance_periods``).
    Falls back to ``agent.Urate_normal`` when ``u_ergodic`` is absent.
    """
    u = bd_i.get("u_ergodic")
    if u is not None and np.isfinite(u):
        return float(u)
    return float(getattr(agent, "Urate_normal", 0.0))


def assert_mortality_inclusive_ergodicity(agents, warn_band=0.9996):
    """HALT when any atom violates the mortality-inclusive TM-ergodic existence
    condition (owner order 2026-07-25: halt with an error when the model is
    calibrated such that no ergodic distribution exists once mortality is
    accounted for).

    THE CONDITION: population growth-patience factor GPF_out < 1 (GIC-with-Liv,
    LivPrb OUTSIDE the 1/CRRA power — BST eq. 42; the same object the BUG-053
    cap machinery shaves to theGICfactor). GPF_out < 1 ⟺ the TM-a ergodic
    wealth distribution exists WITH finite mean, mortality included. The
    BUG-053 loader CLIPS atoms to the cap at calibration load; this guard
    VERIFIES the invariant at TM-build time so any path that bypassed the clip
    (custom beta injection, legacy flags, hand-built agents) halts here rather
    than silently building a TM whose "ergodic" has no finite mean.

    Evaluation paths:
      * EXACT (preferred): when EstimParameters is importable and the agent
        carries EducType, the invariant is beta <= gic_capped_beta(EducType, 1.0)
        — the loader's own GPF_out=1 boundary, convention-identical.
      * FALLBACK: direct formula GPF_out = (R·beta)^(1/CRRA)·LivPrb·E[1/psi]/Γ
        from the agent's own base-state IncShkDstn. Measured convention offset
        vs the loader ≈ 2e-4 (probe 2026-07-25), well inside the 5e-4 design
        margin: HALT at >= 1.0 catches every unambiguous violation; the WARN
        band [warn_band, 1.0) flags near-boundary atoms (beyond the design
        shave, or inside the convention-uncertainty zone) without halting.

    NOT policed here: finiteness of the ergodic VARIANCE — a strictly stronger
    condition the production design deliberately does not impose (measured
    2026-07-25: cap-atom ergodic tail exponent ≈2.17 over the populated range,
    variance finite in practice; asymptotic deterministic-growth root ≈1.09;
    see conclusions_private/2026-07-24_speed_deepdive_p0p1.md).

    Escape hatch (diagnostics only): HAFISCAL_SKIP_ERGODICITY_GUARD=1.
    """
    import os as _os
    import warnings as _warnings
    if _os.environ.get('HAFISCAL_SKIP_ERGODICITY_GUARD', '0') == '1':
        return
    try:
        from EstimParameters import gic_capped_beta as _exact_cap
    except Exception:
        _exact_cap = None
    problems, warns = [], []
    for i, ag in enumerate(agents):
        beta = float(ag.DiscFac)
        educ = getattr(ag, 'EducType', None)
        if _exact_cap is not None and educ is not None:
            try:
                boundary = float(_exact_cap(int(educ), 1.0))
            except Exception:
                boundary = None
            if boundary is not None:
                if beta > boundary * (1.0 + 1e-12):
                    problems.append(
                        f"agent {i}: beta={beta:.6f} EXCEEDS the GPF_out=1 "
                        f"existence boundary beta={boundary:.6f} (educ {educ}, "
                        f"exact loader convention)")
                continue
        try:
            R = ag.Rfree
            R = float(np.atleast_1d(R).ravel()[0])
            rho = float(ag.CRRA)
            L = float(np.atleast_1d(
                ag.LivPrb[0] if isinstance(ag.LivPrb, list) else ag.LivPrb
            ).ravel()[0])
            G = float(np.atleast_1d(
                ag.PermGroFac[0] if isinstance(ag.PermGroFac, list)
                else ag.PermGroFac).ravel()[0])
            d0 = ag.IncShkDstn[0]
            if isinstance(d0, (list, tuple)):
                d0 = d0[0]
            pmv = np.asarray(d0.pmv, dtype=float)
            atoms = np.asarray(d0.atoms, dtype=float)
            perm = atoms[0] if atoms.ndim == 2 else atoms
            E_inv_psi = float(np.sum(pmv / perm))
            gpf_out = (R * beta) ** (1.0 / rho) * L * E_inv_psi / G
        except Exception as exc:  # never silently pass an unevaluable atom
            _warnings.warn(
                f"ergodicity guard could not evaluate agent {i} "
                f"(beta={beta:.6f}): {exc!r} — attribute conventions unknown; "
                f"NOT halting, but verify this agent's GIC-with-Liv manually.")
            continue
        if gpf_out >= 1.0:
            problems.append(
                f"agent {i}: GPF_out={gpf_out:.6f} >= 1 "
                f"(beta={beta:.6f}, R={R:.6f}, CRRA={rho}, LivPrb={L:.6f}, "
                f"E[1/psi]={E_inv_psi:.6f}, PermGroFac={G:.6f})")
        elif gpf_out >= warn_band:
            warns.append(
                f"agent {i}: GPF_out={gpf_out:.6f} in the near-boundary band "
                f"[{warn_band}, 1.0) — beyond the BUG-053 design shave")
    if warns:
        _warnings.warn(
            "TM-ergodic near-boundary atoms (not halting): "
            + "; ".join(warns)
            + " — check the calibration against gic_capped_beta/theGICfactor.")
    if problems:
        raise RuntimeError(
            "MORTALITY-INCLUSIVE ERGODICITY VIOLATED — no finite-mean ergodic "
            "wealth distribution exists for the atom(s) below even with "
            "mortality (GIC-with-Liv / population GPF_out >= 1), so the TM-a "
            "'ergodic' would be meaningless. Recalibrate or route the atom "
            "through the BUG-053 cap (EstimParameters.gic_capped_beta; "
            "theGICfactor). Refs: BUGS_private BUG-053; "
            "conclusions_private/2026-06-16_gic-inside-vs-outside-individual-"
            "target-vs-tm-ergodic.md. Diagnostics-only bypass: "
            "HAFISCAL_SKIP_ERGODICITY_GUARD=1.\n  "
            + "\n  ".join(problems))


def compute_baseline_tm_data(economy, dist_aGrid_count=None, mc_E_pLvl=None,
                             neutral_measure=False, verbose=True,
                             q_method='cohort', mCount=None):
    """
    Pre-compute baseline ergodic distributions and E[pLvl] for all agent types.

    Must be called while agents are in base Markov configuration. The results
    can then be reused across multiple experiment runs.

    Parameters
    ----------
    economy : AggregateDemandEconomy
    dist_aGrid_count : int or None, default None
        Number of distribution-grid points (owner ruling 2026-07-25: on the
        production a-indexed path this sizes the a-indexed distribution grid
        — it is handed to ``build_tm_agg_fiscal_a(aCount=...)``; the old
        ``mCount`` name lied about its object. On the legacy m-indexed
        dispatch it sizes that kernel's honest ``mCount``.)
        None => ``HAFISCAL_TM_MCOUNT`` env default (flag spelling retained
        by owner ruling), else 50.
    mCount : int or None, default None
        DEPRECATED alias for ``dist_aGrid_count`` (one deprecation cycle,
        same pattern as the ``aMax``→``dist_aGrid_max`` rename). Warns on
        use; ignored when ``dist_aGrid_count`` is given.
    mc_E_pLvl : list of float or None
        If provided, use these MC-derived E[pLvl] values instead of the
        analytical formula. Should have one entry per agent in economy.agents.
        Recommended: np.mean(agent.state_now['pLvl']) after MC burn-in.
    neutral_measure : bool
        If True, build TM under Harmenberg neutral measure (Q-marginal).
    q_method : str, default 'cohort'
        Only used when ``neutral_measure=True`` AND ``tm_a_indexed=True``.
        Selects how the Q-marginal ergodic is computed:
        - 'cohort' (default, recommended): use
          ``compute_pi_q_via_cohort_age`` — exact Q-twisted Harmenberg
          construction per math doc §25. Truncates cohort sum at
          K_max = T_age - 1; uses raw L (no L_eff approximation).
          Default since BUG-038 Phase 8 sign-off (2026-04-30); previous
          default was 'doob'.
        - 'doob': use ``compute_doob_pi_q_a`` (Fix 4). Exact in
          perpetual youth; under T_age cap uses ``_effective_LivPrb``
          approximation (~1% L1 error at HS, ~5% at College vs cohort
          exact). Kept for backwards comparison; was the default
          before BUG-038.
        - 'bst': legacy — build TM-Q-BST and find its (biased) ergodic.
          Kept for backwards comparison.
        Has no effect when neutral_measure=False or for the m-indexed kernel
        (Doob is currently a-indexed only; m-indexed always uses 'bst').
    verbose : bool

    Returns list of dicts (one per agent) with keys:
        ergodic, dist_mGrid, E_pLvl, u_ergodic (and cohort_ergodic, base_aPol)
    """
    # Deprecated-alias shim (owner ruling 2026-07-25, grid-name cleanup phase
    # 2): the a-indexed TM distribution-grid size is `dist_aGrid_count`; the
    # M-era `mCount` spelling is accepted for one deprecation cycle.
    if mCount is not None:
        import warnings as _warnings_dep
        _warnings_dep.warn(
            "compute_baseline_tm_data(mCount=...) is deprecated; pass "
            "dist_aGrid_count=... instead (owner ruling 2026-07-25: on the "
            "production a-indexed TM path this parameter sizes the a-indexed "
            "distribution grid, not an m-grid). Behavior unchanged.",
            DeprecationWarning, stacklevel=2)
        if dist_aGrid_count is None:
            dist_aGrid_count = mCount
    if dist_aGrid_count is None:
        dist_aGrid_count = _HAFISCAL_TM_MCOUNT_DEFAULT

    if q_method not in ('doob', 'cohort', 'bst'):
        raise ValueError(
            f"q_method must be 'doob', 'cohort', or 'bst', got: {q_method!r}")
    assert_mortality_inclusive_ergodicity(economy.agents)
    baseline_data = []
    for i, agent in enumerate(economy.agents):
        use_a = getattr(agent, 'tm_a_indexed', False)
        interp = getattr(agent, 'interpretation', 'CDC')
        # Belief-consistency auto-route (2026-07-27): 'cohort' is the CAP-exact
        # Q-measure method (BUG-038: K_max = T_age-1 recursion — it REQUIRES a
        # cap); 'doob' is the perpetual-youth-exact method (its only
        # approximation was the cap's _effective_LivPrb substitution, which
        # vanishes when there is no cap). Under HAFISCAL_T_AGE=none
        # (agent.T_age is None) the default 'cohort' therefore routes to
        # 'doob' instead of raising: the default means "the exact method for
        # the world you are in", not "the cap method".
        q_method_i = q_method
        if (q_method == 'cohort' and neutral_measure
                and getattr(agent, 'T_age', None) is None):
            print(f"[tm-baseline] agent {i}: T_age=None -> q_method 'cohort' "
                  f"auto-routes to 'doob' (perpetual-youth exact)", flush=True)
            q_method_i = 'doob'
        if use_a:
            if neutral_measure and q_method_i == 'doob':
                # Doob path: build TM-P, find pi_P, then derive pi_Q^true
                # via the Doob h-transform (Fix 4). Avoids BST Theorem 1
                # bias under mortality. Under T_age cap, uses _effective_LivPrb
                # approximation (~1% L1 error vs cohort exact); see
                # math doc §25 and BUG-038 plan §11.1.
                tm_base_P = build_tm_agg_fiscal_a(agent, aCount=dist_aGrid_count, Cratio=1.0,
                                                  neutral_measure=False,
                                                  interpretation=interp)
                pi_P = find_ergodic_distribution(tm_base_P['TranMatrix'])
                doob_out = compute_doob_pi_q_a(agent, tm_base_P, pi_P,
                                               Cratio=1.0, interpretation=interp)
                tm_base = tm_base_P
                ergodic = doob_out['pi_Q_doob']
            elif neutral_measure and q_method_i == 'cohort':
                # BUG-038 cohort path: build TM-P, then compute π_Q
                # analytically via the Q-twisted cohort-age decomposition
                # truncated at K_max = T_age - 1. Exact under cap; avoids
                # both v_2 ill-conditioning and L_eff approximation.
                # Per math doc §25.6.
                tm_base_P = build_tm_agg_fiscal_a(agent, aCount=dist_aGrid_count, Cratio=1.0,
                                                  neutral_measure=False,
                                                  interpretation=interp)
                T_age_agent = getattr(agent, 'T_age', None)
                if T_age_agent is None:
                    raise ValueError(
                        "q_method='cohort' requires agent.T_age to be set "
                        "(integer); got None. Set Parameters.py T_age=200 "
                        "for production (BUG-038) or pass q_method='doob' "
                        "for the perpetual-youth code path.")
                # D-8 (2026-05-05): use 'degenerate' to match qe_fidelity's
                # ψ_unemp=1 behavior. Default 'employed' lets unemployed states
                # inherit employed shock distribution — wrong under
                # HAFISCAL_PERM_DURING_UNEMP=off. See conclusions_private/
                # 2026-05-05_mc-tm-residual-root-cause-pLvl-mrkv-conditional-bias.md
                # and memory project_mc_tm_pLvl_mrkv_conditional_bias.md.
                # Selectable via HAFISCAL_COHORT_UNEMP_SHOCKS env var (defaults
                # to 'degenerate' for production correctness).
                _unemp_shocks_mode = _os.environ.get(
                    'HAFISCAL_COHORT_UNEMP_SHOCKS', 'degenerate')
                ergodic, _ = compute_pi_q_via_cohort_age(
                    agent, tm_base_P, T_age=T_age_agent, Cratio=1.0,
                    interpretation=interp,
                    unemp_shocks=_unemp_shocks_mode)
                tm_base = tm_base_P
            else:
                tm_base = build_tm_agg_fiscal_a(agent, aCount=dist_aGrid_count, Cratio=1.0,
                                                neutral_measure=neutral_measure,
                                                interpretation=interp)
                ergodic = find_ergodic_distribution(tm_base['TranMatrix'])
            dist_aGrid = tm_base['dist_aGrid']
            A = len(dist_aGrid)
            u_ergodic_i = 1.0 - np.sum(ergodic[:A])

            if mc_E_pLvl is not None:
                E_pLvl = mc_E_pLvl[i]
            else:
                E_pLvl = compute_analytical_mean_pLvl(
                    agent, unemployment_rate=u_ergodic_i)

            baseline_data.append({
                'ergodic': ergodic,
                'cohort_ergodic': None,  # not yet implemented for a-indexed
                'dist_aGrid': dist_aGrid,
                'E_pLvl': E_pLvl,
                'u_ergodic': u_ergodic_i,
                'base_aPol': None,  # not needed under a-indexing
                'tm_a_indexed': True,
            })
        else:
            # Legacy m-indexed kernel: its mCount is the honest m-grid size.
            tm_base = build_tm_agg_fiscal(agent, mCount=dist_aGrid_count, Cratio=1.0,
                                          neutral_measure=neutral_measure)
            ergodic = find_ergodic_distribution(tm_base['TranMatrix'])
            dist_mGrid = tm_base['dist_mGrid']
            J_micro = agent.num_base_MrkvStates
            M = len(dist_mGrid)
            u_ergodic_i = 1.0 - np.sum(ergodic[:M])

            if mc_E_pLvl is not None:
                E_pLvl = mc_E_pLvl[i]
            else:
                E_pLvl = compute_analytical_mean_pLvl(
                    agent, unemployment_rate=u_ergodic_i)

            base_aPol = np.empty((J_micro, M), dtype=np.float64)
            sol = agent.solution[0]
            for j in range(J_micro):
                cFunc_j = sol.cFunc[j]
                cPol_j = cFunc_j(dist_mGrid, np.ones_like(dist_mGrid))
                base_aPol[j, :] = np.maximum(dist_mGrid - cPol_j, 0.0)

            baseline_data.append({
                'ergodic': ergodic,
                'cohort_ergodic': tm_base.get('cohort_ergodic'),
                'dist_mGrid': dist_mGrid,
                'E_pLvl': E_pLvl,
                'u_ergodic': u_ergodic_i,
                'base_aPol': base_aPol,
                'tm_a_indexed': False,
            })
        if verbose and i % 7 == 0:
            print(f"    Baseline TM type {i}: E[pLvl]={E_pLvl:.2f}")
    return baseline_data


def run_experiment_tm_nonbase(economy, shock_type, EconomyMrkv_init,
                              baseline_tm_data, mCount=_HAFISCAL_TM_MCOUNT_DEFAULT, Cratio=1.0,
                              neutral_measure=False, verbose=True,
                              ad_timing=_HAFISCAL_TM_AD_TIMING,
                              cfunc_offset=_HAFISCAL_TM_CFUNC_OFFSET,
                              compute_welfare=False):
    """
    TM-based replacement for run_experiment() for non-base shock types.

    The economy must already have switch_shock_type(shock_type) and solve()
    called before this function. baseline_tm_data is the output of
    compute_baseline_tm_data() (computed once under base Markov config).

    Parameters
    ----------
    economy : AggregateDemandEconomy
    shock_type : str
    EconomyMrkv_init : list of int, macro Markov state path
    baseline_tm_data : list of dicts from compute_baseline_tm_data()
    mCount : int
        NOT a grid sizer here — the grids come from ``baseline_tm_data``;
        this value only appears in the verbose progress line. Name kept
        unchanged in the 2026-07-25 dist_aGrid_count rename (per-site
        judgment: only params that actually size the a-grid were renamed).
    Cratio : float or array-like
        Scalar (constant for all periods) or 1-D array of length act_T.
    verbose : bool

    Returns
    -------
    dict with NPV_AggIncome, NPV_AggCons, AggIncome, AggCons, Cratio_hist
    """
    act_T = economy.act_T
    agents = economy.agents
    Rfree = agents[0].Rfree[0]

    if verbose:
        print(f"  TM experiment ({shock_type}): {len(agents)} types, "
              f"{act_T} periods, mCount={mCount}")

    AggCons = np.zeros(act_T)
    AggIncome = np.zeros(act_T)

    is_check = shock_type in ('Check', 'recessionCheck')

    # Edu-share-respecting aggregation. Under standard config, pop_rescale_factor=1
    # (no-op). Under HAFISCAL_AGENTCOUNT_* override, factor corrects per-cohort
    # weighting so aggregates respect data_EducShares.
    # See plans/20260506-1640h_edu_share_aggregation_correction.md.
    _agg_mode_xp = _os.environ.get('HAFISCAL_AGGREGATE_BY_EDU_SHARE', 'auto').lower()
    _has_co_xp = any(
        _os.environ.get(v, '').strip() != ''
        for v in ('HAFISCAL_AGENTCOUNT_D', 'HAFISCAL_AGENTCOUNT_H', 'HAFISCAL_AGENTCOUNT_C')
    )
    _apply_rescale_xp = (
        _agg_mode_xp in ('on', '1', 'true')
        or (_agg_mode_xp == 'auto' and _has_co_xp)
    )

    welfare_per_cohort = [] if compute_welfare else None

    for i, agent in enumerate(agents):
        bd = baseline_tm_data[i]

        check_info_i = None
        if is_check:
            buckets = _compute_check_buckets(agent, bd['E_pLvl'],
                                             unemployment_rate=bd.get('u_ergodic'))
            check_info_i = {
                'period': 0,
                'buckets': buckets,
            }

        use_a = bd.get('tm_a_indexed', False) \
            or getattr(agent, 'tm_a_indexed', False)
        if use_a:
            result_i = propagate_experiment_tm_a(
                agent, bd['ergodic'], EconomyMrkv_init, bd['dist_aGrid'],
                bd['E_pLvl'], Cratio=Cratio, act_T=act_T,
                neutral_measure=neutral_measure, check_info=check_info_i,
                shock_type=shock_type,
                ad_timing=ad_timing,
                cfunc_offset=cfunc_offset,
                interpretation=getattr(agent, 'interpretation', 'CDC'),
                compute_welfare=compute_welfare,
            )
        else:
            result_i = propagate_experiment_tm(
                agent, bd['ergodic'], EconomyMrkv_init, bd['dist_mGrid'],
                bd['E_pLvl'], Cratio=Cratio, act_T=act_T,
                neutral_measure=neutral_measure, check_info=check_info_i,
                shock_type=shock_type,
                base_aPol=bd.get('base_aPol'),
                ad_timing=ad_timing,
                cfunc_offset=cfunc_offset,
            )
        rescale_i = getattr(agent, 'pop_rescale_factor', 1.0) if _apply_rescale_xp else 1.0
        AggCons += rescale_i * result_i['AggCons']
        AggIncome += rescale_i * result_i['AggIncome']

        if compute_welfare and use_a:
            welfare_per_cohort.append({
                'U_nrm_series': np.asarray(result_i['U_nrm_series']).copy(),
                'MU_inv_nrm_series': np.asarray(result_i['MU_inv_nrm_series']).copy(),
                'pLvl_factor_series': np.asarray(result_i['pLvl_factor_series']).copy(),
                'welfare_CRRA': result_i['welfare_CRRA'],
                'E_pLvl_init': result_i['E_pLvl_init'],
                'AgentCount': result_i['AgentCount'],
                'pop_rescale_factor': rescale_i,
            })

        if verbose and i % 7 == 0:
            print(f"    Type {i}: done")

    if np.isscalar(Cratio):
        Cratio_hist = np.full(act_T, float(Cratio))
    else:
        Cratio_hist = np.asarray(Cratio, dtype=float).copy()
    NPV_AggCons = calculate_NPV(AggCons, act_T, Rfree)
    NPV_AggIncome = calculate_NPV(AggIncome, act_T, Rfree)

    if verbose:
        print(f"  TM experiment complete")

    out = {
        'NPV_AggIncome': NPV_AggIncome,
        'NPV_AggCons': NPV_AggCons,
        'AggIncome': AggIncome,
        'AggCons': AggCons,
        'Cratio_hist': Cratio_hist,
    }
    if compute_welfare:
        out['welfare_per_cohort'] = welfare_per_cohort
    return out


def _build_MacroCFunc_from_Cratio(Cratio_path, EconomyMrkv_init, num_experiment_periods):
    """
    Build a MacroCFunc matrix from a Cratio path, replicating the logic in
    AggregateDemandEconomy.solve_ad_recession (lines 1432-1436).

    The MacroCFunc maps (from_macro, to_macro) state transitions to the
    expected Cratio for that transition.  Each entry is a (intercept, slope)
    pair; with slope=0, the intercept is the constant expected Cratio.

    Returns
    -------
    MacroCFunc : list of lists of (intercept, slope) tuples
        Dimension: dim x dim where dim = 2*(num_experiment_periods+1).
    """
    dim = 2 * (num_experiment_periods + 1)
    # Default: identity mapping (intercept=1.0, slope=0.0)
    MacroCFunc = [[(1.0, 0.0) for _ in range(dim)] for _ in range(dim)]

    # Entry from macro=0 to macro=3 (first recession period)
    MacroCFunc[0][3] = (float(Cratio_path[0]), 0.0)

    # Transitions through experiment periods: macro 2j+3 → 2j+5
    for j in range(num_experiment_periods - 1):
        MacroCFunc[2*j + 3][2*j + 5] = (float(Cratio_path[j + 1]), 0.0)

    # Transition from last experiment period to post-experiment
    MacroCFunc[2*num_experiment_periods + 1][1] = (
        float(Cratio_path[num_experiment_periods]), 0.0)

    # Steady-state within post-experiment recession
    MacroCFunc[1][1] = (
        float(np.mean(Cratio_path[num_experiment_periods + 1:
                                   num_experiment_periods + 10])), 0.0)

    return MacroCFunc


def _cratio_path_from_seed_CFunc(CFunc, J, num_experiment_periods, act_T):
    """R6b (2026-08-03): inverse of _build_MacroCFunc_from_Cratio on the
    block representatives of a combined-level belief — recover the Cratio
    path the belief encodes along the worst-case (all-recession) path.

    Needed because run_ad_tm's iteration state is the PAIR
    (CFunc, Cratio_path): seeding the belief alone is inert — the first
    propagation uses Cratio_path, which cold-starts at ones, so the loop
    re-treads the cold trajectory (measured 2026-08-03: seeded arm still
    4 iterations, wall unchanged). The post-experiment window collapses to
    the [1][1] mean in the forward map, so its inverse is the constant
    projection — a warm START only; the first propagation regenerates the
    true tail structure and the loop still runs to its own tolerance."""
    ne = num_experiment_periods

    def _ic(i, j):
        e = CFunc[i * J][j * J]
        if isinstance(e, tuple):
            return float(e[0])
        return float(getattr(e, 'intercept', 1.0))

    C = np.ones(act_T)
    C[0] = _ic(0, 3)
    for j in range(ne - 1):
        C[j + 1] = _ic(2 * j + 3, 2 * j + 5)
    C[ne] = _ic(2 * ne + 1, 1)
    C[ne + 1:min(ne + 13, act_T)] = _ic(1, 1)
    return np.clip(C, 0.8, 1.2)


def _MacroCFunc_to_MicroCFunc(MacroCFunc, num_base_MrkvStates):
    """
    Expand macro-level CFunc to micro-level, replicating
    AggregateDemandEconomy.Macro_2_Micro_CFunc.

    Each micro state within a macro state gets the same CFunc entry.
    """
    dim = len(MacroCFunc)
    J = num_base_MrkvStates
    MicroCFunc = [[(1.0, 0.0) for _ in range(dim * J)]
                  for _ in range(dim * J)]
    for i in range(dim * J):
        for j in range(dim * J):
            MicroCFunc[i][j] = MacroCFunc[i // J][j // J]
    return MicroCFunc


def _apply_CFunc_to_economy(economy, MicroCFunc, step=1.0):
    """
    Update economy.CFunc with a damped step from old to new, then re-solve.

    Replicates the CFunc update + re-solve in solve_ad_recession (1439-1455).
    Uses the CRule class from AggFiscalModel.

    Parameters
    ----------
    economy : AggregateDemandEconomy
    MicroCFunc : list of lists of (intercept, slope) tuples
    step : float
        Damping factor (1.0 = no damping).
    """
    from AggFiscalModel import CRule

    dim = len(economy.CFunc)
    Old_CFunc = economy.CFunc
    Step_CFunc = [[CRule(1.0, 0.0) for _ in range(dim)] for _ in range(dim)]
    for ii in range(dim):
        for jj in range(dim):
            new_intercept, new_slope = MicroCFunc[ii][jj]
            Step_CFunc[ii][jj].slope = (
                Old_CFunc[ii][jj].slope + step * (new_slope - Old_CFunc[ii][jj].slope))
            Step_CFunc[ii][jj].intercept = (
                Old_CFunc[ii][jj].intercept + step * (new_intercept - Old_CFunc[ii][jj].intercept))

    economy.CFunc = Step_CFunc
    for agent in economy.agents:
        agent.CFunc = economy.CFunc
    economy.solve()


def _CFunc_convergence(economy, Old_CFunc):
    """
    Compute CFunc convergence metric, replicating
    AggregateDemandEconomy.Compare_CFunc_Convergence.
    """
    New_CFunc = economy.CFunc
    dim = len(Old_CFunc)
    DiffSlopes = np.zeros((dim, dim))
    DiffIntercepts = np.zeros((dim, dim))
    for i in range(dim):
        for j in range(dim):
            DiffSlopes[i, j] = abs(New_CFunc[i][j].slope - Old_CFunc[i][j].slope)
            DiffIntercepts[i, j] = abs(New_CFunc[i][j].intercept - Old_CFunc[i][j].intercept)
    return (np.linalg.norm(DiffSlopes)**2 + np.linalg.norm(DiffIntercepts)**2)**0.5


def run_ad_tm(economy, shock_type, EconomyMrkv_init,
              baseline_tm_data, AggCons_baseline,
              ADelasticity=0.3, num_max_iterations=10,
              convergence_tol=0.004, mCount=_HAFISCAL_TM_MCOUNT_DEFAULT,
              neutral_measure=False, verbose=True,
              skip_training=False, ad_timing=_HAFISCAL_TM_AD_TIMING,
              cfunc_offset=_HAFISCAL_TM_CFUNC_OFFSET,
              compute_welfare=False):
    """
    TM-based AD (aggregate demand) solver with belief updating.

    Matches MC's solve_ad_recession two-phase approach:

    Phase 1 — CFunc training (worst-case recession path):
      Uses all-recession macro states (all odd) to train CFunc beliefs,
      matching MC's solve_ad_recession which always iterates on the
      worst-case path. Each iteration:
        1. Run TM experiment on worst-case path → get AggCons
        2. Compute Cratio from experiment/baseline consumption ratio
        3. Build MacroCFunc from Cratio path
        4. Update CFunc beliefs (damped step) and re-solve agents
        5. Check CFunc convergence

    Phase 2 — Final evaluation (specific recession duration):
      With converged CFunc, run a single TM propagation on the actual
      EconomyMrkv_init path to get results for this recession duration.

    Parameters
    ----------
    economy : AggregateDemandEconomy
        Economy with shock_type already set and solved.
    shock_type : str
    EconomyMrkv_init : list of int
        Macro Markov state path for this recession duration (used in Phase 2).
    baseline_tm_data : list of dicts from compute_baseline_tm_data
    AggCons_baseline : np.ndarray, shape (act_T,)
        Baseline aggregate consumption (from TM base experiment).
    ADelasticity : float
        AD feedback elasticity (default 0.3).
    num_max_iterations : int
    convergence_tol : float
        Convergence criterion on CFunc total diff (matches MC's cutoff).
    mCount : int
        NOT a grid sizer — accepted for signature compatibility but unused
        in the body (the grids come from ``baseline_tm_data``). Name kept
        unchanged in the 2026-07-25 dist_aGrid_count rename (per-site
        judgment: only params that actually size the a-grid were renamed).
    neutral_measure : bool
    verbose : bool
    skip_training : bool
        If True, skip Phase 1 CFunc training and reuse the economy's current
        CFunc (assumed already converged from a prior call). This avoids
        redundant economy.solve() calls when the worst-case training path
        is identical across recession durations.

    Returns
    -------
    dict with NPV_AggIncome, NPV_AggCons, AggIncome, AggCons, Cratio_hist
    """
    act_T = economy.act_T
    agents = economy.agents
    Rfree = agents[0].Rfree[0]
    num_experiment_periods = economy.num_experiment_periods
    J = economy.num_base_MrkvStates
    step = getattr(economy, 'Cfunc_iter_stepsize', 1.0)

    is_check = shock_type in ('Check', 'recessionCheck')

    _t_phase1 = _time.time()
    if not skip_training:
        # ---- Phase 1: CFunc training on worst-case path ----
        # Worst-case recession path: all odd macro states (matches MC's
        # solve_ad_recession line 1420)
        worst_case_path = (list(np.arange(1, num_experiment_periods + 1) * 2 + 1)
                           + [1] * 12 + [0] * max(0, act_T - num_experiment_periods - 12))
        worst_case_path = worst_case_path[:act_T]

        # Reset CFunc to flat (Cratio=1 everywhere), matching MC's presolve —
        # unless an AD-belief warm seed was armed upstream (R6b/Leg-B,
        # 2026-08-03: HAFISCAL_AD_BELIEF_SEED consume in Simulate.py). The
        # seed travels in economy._ad_seed_CFunc (a payload attribute, so no
        # intermediate switch_shock_type/calc_CFunc can clobber it) and is a
        # WARM START only: the training loop below still runs to its own
        # convergence_tol (bench class 6->1 iterations at ~1e-5).
        from AggFiscalModel import CRule
        dim_CFunc = len(economy.CFunc)
        # Retained for the ad-full guard's FAIL path: the byte-certified cold
        # fallback must restart the presolve from the SAME solver state the
        # cold path starts from (references only).
        _init_solutions_tm = [a.solution for a in agents]
        # Guarded wholesale AD-converged cache, TM engine (Phase B of plan
        # 20260803-1030h; engine label "tm_a" keys these entries apart from
        # the welfare replay engine's). A HIT installs the cached belief as
        # the training start; the presolve below is the guard's fresh solve
        # (amendment-1 compare), and training iteration 1 is the map step
        # (amendment-2 threshold).
        _adf_payload = None
        _adf_guard = False
        # Iteration-limited runs (1stRoundAD: num_max_iterations=1) are a
        # DIFFERENT economic object — one damped update from flat, by
        # design. A convergence cache must never hijack them (arm-C1 gate,
        # 2026-08-03: the 1stRoundAD cells consumed the just-published
        # converged entries and the Multiplier table's first-round columns
        # went wrong). Consume only when the caller asks for convergence.
        if num_max_iterations >= 2:
            try:
                from solution_cache import load_ad_full_cache as _adf_load_tm
                _adf_payload = _adf_load_tm(economy, shock_type,
                                            engine="tm_a", verbose=verbose)
            except Exception:
                _adf_payload = None
        _seedC = getattr(economy, "_ad_seed_CFunc", None)
        _seeded_start = False
        if (_adf_payload is not None
                and len(_adf_payload.get("CFunc", [])) == dim_CFunc):
            economy.CFunc = deepcopy(_adf_payload["CFunc"])
            for agent in agents:
                agent.CFunc = economy.CFunc
            _adf_guard = True
            _seeded_start = True
            _adf_meta_tm = _adf_payload.get("meta", {}) or {}
            if verbose:
                print(f"  [ad-full] HIT {shock_type} (tm_a): guard armed "
                      f"(producer iters={_adf_meta_tm.get('iterations')}, "
                      f"final_step={_adf_meta_tm.get('final_step')})",
                      flush=True)
        elif (getattr(economy, "_ad_warm_start", False)
                and _seedC is not None and len(_seedC) == dim_CFunc):
            economy.CFunc = _seedC
            for agent in agents:
                agent.CFunc = economy.CFunc
            economy._ad_warm_start = False   # one-shot
            economy._ad_seed_CFunc = None
            _seeded_start = True
            if verbose:
                print("  AD-TM: belief seed honored (flat reset skipped; "
                      "training loop runs to its own tolerance)...")
        else:
            economy.CFunc = [[CRule(1.0, 0.0) for _ in range(dim_CFunc)]
                             for _ in range(dim_CFunc)]
            for agent in agents:
                agent.CFunc = economy.CFunc

        if verbose:
            print("  AD-TM: presolving...")
        economy.solve()

        _adf_pol_dev = None
        if _adf_guard:
            # Amendment 1: the presolve just solved FRESH policies under the
            # cached belief — compare them against the CACHED policies before
            # anything is discarded (the belief-step alone false-passes a
            # corrupted payload; gate G2 class).
            try:
                from solution_cache import compare_policies_max_rel as _adf_cmp_tm
                _adf_pol_dev = _adf_cmp_tm(agents, _adf_payload["solutions"])
            except Exception as _e_cmp_tm:
                print(f"  [ad-full] (tm_a) policy-compare errored "
                      f"({_e_cmp_tm}); treating as FAIL.", flush=True)
                _adf_pol_dev = None

        if _seeded_start:
            # R6b: the iteration state is (CFunc, Cratio_path) — seed BOTH
            # halves or the first propagation (which consumes Cratio_path,
            # not the belief) re-treads the cold trajectory.
            Cratio_path = _cratio_path_from_seed_CFunc(
                economy.CFunc, J, num_experiment_periods, act_T)
            if verbose:
                print("  AD-TM: Cratio path seeded from the belief "
                      f"(mean={np.mean(Cratio_path):.4f})...", flush=True)
        else:
            Cratio_path = np.ones(act_T)

        _tm_step_series = []   # ad-full amendment 3 -> entry meta
        for iteration in range(num_max_iterations):
            Old_CFunc = deepcopy(economy.CFunc)

            AggCons_total = np.zeros(act_T)
            AggIncome_total = np.zeros(act_T)

            for i, agent in enumerate(agents):
                bd = baseline_tm_data[i]

                check_info_i = None
                if is_check:
                    buckets = _compute_check_buckets(agent, bd['E_pLvl'],
                                                     unemployment_rate=bd.get('u_ergodic'))
                    check_info_i = {'period': 0, 'buckets': buckets}

                use_a = bd.get('tm_a_indexed', False) \
                    or getattr(agent, 'tm_a_indexed', False)
                if use_a:
                    result_i = propagate_experiment_tm_a(
                        agent, bd['ergodic'], worst_case_path,
                        bd['dist_aGrid'], bd['E_pLvl'],
                        Cratio=Cratio_path, act_T=act_T,
                        neutral_measure=neutral_measure,
                        check_info=check_info_i,
                        shock_type=shock_type,
                        ADelasticity=ADelasticity,
                        ad_timing=ad_timing,
                        cfunc_offset=cfunc_offset,
                        interpretation=getattr(agent, 'interpretation', 'CDC'),
                    )
                else:
                    result_i = propagate_experiment_tm(
                        agent, bd['ergodic'], worst_case_path,
                        bd['dist_mGrid'], bd['E_pLvl'],
                        Cratio=Cratio_path, act_T=act_T,
                        neutral_measure=neutral_measure,
                        check_info=check_info_i,
                        shock_type=shock_type,
                        base_aPol=bd.get('base_aPol'),
                        ADelasticity=ADelasticity,
                        ad_timing=ad_timing,
                        cfunc_offset=cfunc_offset,
                    )
                # Edu-share rescale (no-op under standard config).
                # See plans/20260506-1640h_edu_share_aggregation_correction.md.
                _agg_mode_at = _os.environ.get('HAFISCAL_AGGREGATE_BY_EDU_SHARE', 'auto').lower()
                _has_co_at = any(
                    _os.environ.get(v, '').strip() != ''
                    for v in ('HAFISCAL_AGENTCOUNT_D', 'HAFISCAL_AGENTCOUNT_H', 'HAFISCAL_AGENTCOUNT_C')
                )
                _apply_at = (_agg_mode_at in ('on', '1', 'true')
                             or (_agg_mode_at == 'auto' and _has_co_at))
                rescale_i = getattr(agent, 'pop_rescale_factor', 1.0) if _apply_at else 1.0
                AggCons_total += rescale_i * result_i['AggCons']
                AggIncome_total += rescale_i * result_i['AggIncome']

            Cratio_path = AggCons_total / np.maximum(AggCons_baseline, 1e-10)
            Cratio_path = np.clip(Cratio_path, 0.8, 1.2)

            MacroCFunc = _build_MacroCFunc_from_Cratio(
                Cratio_path, worst_case_path, num_experiment_periods)
            MicroCFunc = _MacroCFunc_to_MicroCFunc(MacroCFunc, J)
            _apply_CFunc_to_economy(economy, MicroCFunc, step=step)

            cfunc_diff = _CFunc_convergence(economy, Old_CFunc)
            _tm_step_series.append(float(cfunc_diff))
            if verbose:
                print(f"  AD-TM iter {iteration}: CFunc diff = {cfunc_diff:.6f}, "
                      f"mean Cratio = {np.mean(Cratio_path):.4f}, "
                      f"max|dCratio| = {np.max(np.abs(Cratio_path - 1.0)):.6f}")

            if _adf_guard and iteration == 0:
                # The owner's double-check, TM engine: iteration 1 was one
                # propagate + update + re-solve from the cached belief.
                _pfs_tm = float((_adf_payload.get("meta", {}) or {})
                                .get("final_step") or 0.0)
                _gthr_tm = max(2.0 * convergence_tol, 2.0 * _pfs_tm)
                if (cfunc_diff < _gthr_tm and _adf_pol_dev is not None
                        and _adf_pol_dev < 1e-3):
                    # PASS: discard the check's work, keep the cached pair.
                    economy.CFunc = _adf_payload["CFunc"]
                    for agent in agents:
                        agent.CFunc = economy.CFunc
                        agent.solution = None  # replaced just below
                    for agent, _sol in zip(agents, _adf_payload["solutions"]):
                        agent.solution = _sol
                        agent.get_economy_data(economy)
                    try:
                        from solution_cache import record_reuse_event as _rre_tgp
                        _rre_tgp("ad_full", "guard_pass", "exact",
                                 engine="tm_a", shock_type=shock_type,
                                 step=float(cfunc_diff),
                                 step_threshold=float(_gthr_tm),
                                 policy_dev=float(_adf_pol_dev))
                    except Exception:
                        pass
                    if verbose:
                        print(f"  [ad-full] GUARD PASS (tm_a): "
                              f"step={cfunc_diff:.3g} (thr {_gthr_tm:.3g}), "
                              f"policy_dev={_adf_pol_dev:.3g} (thr 1e-3) — "
                              f"cached state kept.", flush=True)
                    break
                try:
                    from solution_cache import record_reuse_event as _rre_tgf
                    _rre_tgf("ad_full", "guard_fail_quarantined", "exact",
                             engine="tm_a", shock_type=shock_type,
                             step=float(cfunc_diff),
                             step_threshold=float(_gthr_tm),
                             policy_dev=(None if _adf_pol_dev is None
                                         else float(_adf_pol_dev)))
                except Exception:
                    pass
                print(f"  [ad-full] GUARD FAIL (tm_a) for {shock_type}: "
                      f"step={cfunc_diff:.4g} (thr {_gthr_tm:.4g}), "
                      f"policy_dev={_adf_pol_dev} — quarantining; "
                      f"continuing with the COLD training.", flush=True)
                try:
                    from solution_cache import quarantine_ad_full_entry as _adf_q_tm
                    _adf_q_tm(economy, shock_type, engine="tm_a",
                              verbose=verbose)
                except Exception:
                    pass
                _adf_guard = False
                # FULL RESET (gate-G3 principle): identity belief, the
                # retained pre-guard solver state, a fresh flat presolve and
                # a flat Cratio path — the continuation IS the certified
                # cold training.
                economy.CFunc = [[CRule(1.0, 0.0) for _ in range(dim_CFunc)]
                                 for _ in range(dim_CFunc)]
                for agent, _s0 in zip(agents, _init_solutions_tm):
                    agent.CFunc = economy.CFunc
                    agent.solution = _s0
                if verbose:
                    print("  AD-TM: presolving (post-guard reset)...")
                economy.solve()
                Cratio_path = np.ones(act_T)
                _tm_step_series = []
                continue

            if cfunc_diff < convergence_tol:
                if verbose:
                    print(f"  AD-TM converged in {iteration + 1} iterations")
                try:
                    from solution_cache import save_ad_full_cache as _adf_save_tm
                    _adf_save_tm(economy, shock_type,
                                 step_series=_tm_step_series,
                                 tol=convergence_tol, engine="tm_a",
                                 verbose=verbose)
                except Exception:
                    pass
                break
        else:
            if verbose:
                print(f"  AD-TM WARNING: did not converge in {num_max_iterations} "
                      f"iterations (CFunc diff = {cfunc_diff:.6f})")

    if verbose and not skip_training:
        print(f"  AD-TM Phase 1 (training) wall: {_time.time() - _t_phase1:.1f}s")
    _t_phase2 = _time.time()

    # ---- Phase 2: Final evaluation on the actual EconomyMrkv_init path ----
    # Replicate MC's mill_rule: propagate Cratio forward through converged CFunc.
    # MC computes CratioNext = CFunc[from_macro*J][to_macro*J](Cratio_now),
    # which uses the trained worst-case CFunc intercepts, NOT the direct
    # consumption ratio on this specific path. This is key to producing
    # the correct AD amplification.
    eval_Cratio = np.ones(act_T)
    CFunc = economy.CFunc

    # Initial Cratio from CFunc (matches MC line 1176)
    macro_0 = EconomyMrkv_init[0]
    eval_Cratio[0] = CFunc[0][macro_0 * J].intercept

    # Forward propagation through CFunc (matches MC mill_rule line 1123)
    for t in range(act_T - 1):
        macro_now = EconomyMrkv_init[t] if t < len(EconomyMrkv_init) else 0
        macro_next = EconomyMrkv_init[t + 1] if t + 1 < len(EconomyMrkv_init) else 0
        eval_Cratio[t + 1] = CFunc[macro_now * J][macro_next * J](eval_Cratio[t])

    if verbose:
        print(f"  AD-TM Phase 2: CFunc-propagated Cratio mean={np.mean(eval_Cratio):.6f}, "
              f"min={np.min(eval_Cratio):.6f}, max={np.max(eval_Cratio):.6f}")
        print(f"  Eval Cratio first 8: {eval_Cratio[:8]}")

    # Final propagation with CFunc-derived Cratio path
    AggCons_final = np.zeros(act_T)
    AggIncome_final = np.zeros(act_T)
    welfare_per_cohort = [] if compute_welfare else None
    for i, agent in enumerate(agents):
        bd = baseline_tm_data[i]
        check_info_i = None
        if is_check:
            buckets = _compute_check_buckets(agent, bd['E_pLvl'],
                                             unemployment_rate=bd.get('u_ergodic'))
            check_info_i = {'period': 0, 'buckets': buckets}
        use_a = bd.get('tm_a_indexed', False) \
            or getattr(agent, 'tm_a_indexed', False)
        if use_a:
            result_i = propagate_experiment_tm_a(
                agent, bd['ergodic'], EconomyMrkv_init,
                bd['dist_aGrid'], bd['E_pLvl'],
                Cratio=eval_Cratio, act_T=act_T,
                neutral_measure=neutral_measure,
                check_info=check_info_i,
                shock_type=shock_type,
                ADelasticity=ADelasticity,
                ad_timing=ad_timing,
                cfunc_offset=cfunc_offset,
                interpretation=getattr(agent, 'interpretation', 'CDC'),
                compute_welfare=compute_welfare,
            )
        else:
            result_i = propagate_experiment_tm(
                agent, bd['ergodic'], EconomyMrkv_init,
                bd['dist_mGrid'], bd['E_pLvl'],
                Cratio=eval_Cratio, act_T=act_T,
                neutral_measure=neutral_measure,
                check_info=check_info_i,
                shock_type=shock_type,
                base_aPol=bd.get('base_aPol'),
                ADelasticity=ADelasticity,
                ad_timing=ad_timing,
                cfunc_offset=cfunc_offset,
            )
        # Edu-share rescale (no-op under standard config).
        # See plans/20260506-1640h_edu_share_aggregation_correction.md.
        _agg_mode_fn = _os.environ.get('HAFISCAL_AGGREGATE_BY_EDU_SHARE', 'auto').lower()
        _has_co_fn = any(
            _os.environ.get(v, '').strip() != ''
            for v in ('HAFISCAL_AGENTCOUNT_D', 'HAFISCAL_AGENTCOUNT_H', 'HAFISCAL_AGENTCOUNT_C')
        )
        _apply_fn = (_agg_mode_fn in ('on', '1', 'true')
                     or (_agg_mode_fn == 'auto' and _has_co_fn))
        rescale_i = getattr(agent, 'pop_rescale_factor', 1.0) if _apply_fn else 1.0
        AggCons_final += rescale_i * result_i['AggCons']
        AggIncome_final += rescale_i * result_i['AggIncome']

        if compute_welfare and use_a:
            welfare_per_cohort.append({
                'U_nrm_series': np.asarray(result_i['U_nrm_series']).copy(),
                'MU_inv_nrm_series': np.asarray(result_i['MU_inv_nrm_series']).copy(),
                'pLvl_factor_series': np.asarray(result_i['pLvl_factor_series']).copy(),
                'welfare_CRRA': result_i['welfare_CRRA'],
                'E_pLvl_init': result_i['E_pLvl_init'],
                'AgentCount': result_i['AgentCount'],
                'pop_rescale_factor': rescale_i,
            })

    if verbose:
        print(f"  AD-TM Phase 2 (final eval) wall: {_time.time() - _t_phase2:.1f}s")

    NPV_AggCons = calculate_NPV(AggCons_final, act_T, Rfree)
    NPV_AggIncome = calculate_NPV(AggIncome_final, act_T, Rfree)

    out = {
        'NPV_AggIncome': NPV_AggIncome,
        'NPV_AggCons': NPV_AggCons,
        'AggIncome': AggIncome_final,
        'AggCons': AggCons_final,
        'Cratio_hist': eval_Cratio,
    }
    if compute_welfare:
        out['welfare_per_cohort'] = welfare_per_cohort
    return out


# ================================================================
# a-indexed TM (BUG-033 / Phase 3 — splurge-in-budget budget-identity fix)
# ================================================================
#
# Rationale. Under splurge-in-budget (interpretation A, within-household budget),
# post-consumption savings depend on the *realized* transitory shock:
#
#     a_t = m_t - (1 - varsigma) * c*(m_t) - varsigma * xi_t.
#
# So m_t is not a sufficient state for next-period dynamics (two agents
# sharing (m_t, j_t) but with different xi_t end at different a_t). The
# m-indexed TM collapses that xi-variance, producing a 15-25% multiplier
# bias vs MC. The fix is to index the TM by (a, j_t) and integrate xi in
# the kernel-construction inner loop. The result is ONE sparse matrix
# per agent type, not N_xi matrices; the xi sum collapses internally.
#
# See BUGS_private/HAFiscal_BUG-033_tm_a_indexed_refactor.md for the
# full problem statement, design rationale, and acceptance criteria;
# plans/20260418-1136h_splurge-in-budget-a-indexed-TM.md for the per-function implementation
# plan; plans/20260418-1136h_splurge-in-budget-TM-approach-comparison.md for why a-indexed was
# chosen over (m, xi)-joint.
#
# CDC-MOD-BUG033 [section anchor]: All six functions below with the _a
# suffix (`_build_period_tm_a`, `build_tm_agg_fiscal_a`,
# `compute_type_aggregates_tm_a`, `compute_period_aggregates_tm_a`,
# `build_experiment_period_tm_a`, `propagate_experiment_tm_a`) implement
# the CDC-direction TM kernel. The asset-update inside the kernel uses
# the CDC asset rule g(a, ξ) = (R/Γ)·a + (1−ς)·[ξ − cFunc((R/Γ)·a + ξ)]
# (per (eq:budget-CDC) of models_CDC_and_ESC.md §4.2; alias (CDC-1)). An
# ESC-faithful version would build the analogous _a kernel around
# (eq:budget-ESC) (per-Optimizer accounting; the ς·ξ Splurger consumption
# stays on a separate ledger and never enters the Optimizer's a). See
# plans/20260425-2102h_cdc-implementation-map.md rows 33.4-33.9.
# The legacy m-indexed functions above (without _a suffix) pre-date the
# CDC↔ESC split and are not CDC anchors — they are broken under any
# splurge-in-budget reading per BUG-033's analysis.
#
# implements (eq:budget-CDC) and (eq:budget) (state-transition line) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
# — the (eq:budget-CDC) component is the CDC-specific asset-update inside g(a, ξ);
# the (eq:budget) component is the shared state-transition law M_{t+1} = R·A/(Γψ') + Y'.


def _a_next_checked(m_next_flat, c_actual_flat, dist_aGrid, S, jp, interpretation, Splurge):
    """Compute a_next = m' - c_actual for the TM-a kernel, HALTING on a genuinely negative value.

    a_next must be >= 0 BY CONSTRUCTION: the optimizer's policy obeys the borrowing constraint
    (c <= m for all m >= 0, with equality at the constraint), and the CDC splurge blend
    (1-varsigma)*c_star + varsigma*xi is also <= m' because xi <= m' (m' = R*a/(G*psi) + xi with the
    first term >= 0). So m' - c_actual >= 0 always. A meaningfully negative a_next therefore signals a
    BUG -- cFunc extrapolation past the grid, bad shock scaling, or a splurge mis-blend -- and must be
    reported, NOT silently clamped to 0 (an np.maximum(.,0) would corrupt the ergodic without a trace).
    Only floating-point / interpolation noise (|a_next| below ~1e-8 of the local scale) is clamped.
    """
    a_next = m_next_flat - c_actual_flat
    neg_tol = 1e-8 * (1.0 + np.abs(m_next_flat))
    viol = a_next < -neg_tol
    if viol.any():
        k = int(np.argmin(a_next))
        ai, si = divmod(k, S)
        raise ValueError(
            f"[TM-a kernel] a_next < 0 by {(-a_next[k]):.3e}: c_actual exceeds m' at source "
            f"a={dist_aGrid[ai]:.6g}, dest j'={jp}, shock atom {si}/{S} -- m'={m_next_flat[k]:.6g}, "
            f"c_actual={c_actual_flat[k]:.6g} (c - m' = {c_actual_flat[k] - m_next_flat[k]:.3e}). "
            f"c_actual <= m' must hold by construction (borrowing constraint; CDC splurge blend with "
            f"xi <= m'); a negative a_next means a bug in cFunc extrapolation, shock scaling, or the "
            f"splurge blend -- not a quantity to clamp. interpretation={interpretation!r}, "
            f"Splurge={Splurge}, {int(viol.sum())} violating (a,xi) point(s).")
    return np.maximum(a_next, 0.0)  # clamp only sub-tolerance FP/interpolation noise to exactly 0


def _build_period_tm_a(dist_aGrid, Splurge, cFuncs, IncShkDstn_list,
                       micro_trans, Rfree_arr, PermGroFac_arr, LivPrb_arr,
                       NewBornDist, Cratio=1.0, neutral_measure=False,
                       ad_tran_shk_scale=1.0, employed_tran_shk_scale=1.0,
                       TranShk_addition=None, interpretation='CDC'):
    """
    Build a (A*J) x (A*J) column-stochastic transition matrix indexed by
    (a_t, j_t), the a-indexed analogue of ``_build_period_tm``.

    The kernel is
        T[(a', j'), (a, j)]
            = L_eff(j) * MrkvArray[j, j'] * sum_{xi_k} p_{xi_k | j'}
              * lottery(a' | a_next(a, j', xi_k))
              + (1 - L_eff(j)) * NewBornDist[(a', j')]
    where

    The second term — the **death→newborn reset**, `(1 - L_eff(j)) * NewBornDist` —
    is essential, not bookkeeping: it makes T column-stochastic AND regularizes the
    chain so a stationary `pi^*` exists even when the most-patient atom has no
    individual buffer-stock target (individual GPF_in > 1). With the reset, `pi^*`
    exists iff the *population* growth-impatience condition holds, GPF_out =
    (Rβ)^(1/ρ)·LivPrb·E[ψ⁻¹]/Γ < 1 (Carroll BufferStockTheory eq. 42) — exactly the
    condition the GIC-shave imposes (see `EstimParameters.gic_capped_beta` and the
    "WHICH GIC IS THIS" comment there, and `find_ergodic_distribution` below). Drop
    this term and the kernel would be merely sub-stochastic with upward drift and no
    ergodic distribution at the edge — which is the regime where ONLY Monte Carlo
    (which also resets on death) would be valid. See
    conclusions_private/2026-06-16_gic-inside-vs-outside-individual-target-vs-tm-ergodic.md.

    where
        xi_eff  = ad_tran_shk_scale * employed_fac(j') * xi_k
                + TranShk_addition[j']
        m'      = (R[j'] / (PermGroFac[j'] * psi_k)) * a + xi_eff
        c_actual = (CDC: (1-varsigma)*cFunc[j'](m', Cratio) + varsigma*xi_eff
                   ESC: cFunc[j'](m', Cratio))
        a_next  = max(m' - c_actual, 0).

    Per ``BUGS_private/HAFiscal_splurge_budget_inconsistency/why_TM_a_kernel.md``:
    under CDC, ``a`` is household-bargain a_tot and the asset rule is
    ``(eq:budget-CDC)``; under ESC, ``a`` is per-Optimizer a_opt and the
    asset rule is ``(eq:budget-ESC)``. The splurger consumption is on a
    separate ledger under ESC and never enters this kernel's a_next.

    The xi sum is folded into the matrix during construction — we never
    materialize N_xi separate matrices.

    Parameters
    ----------
    dist_aGrid : np.ndarray, shape (A,). First entry is 0.0 (borrowing
        constraint); the newborn mass lands there deterministically.
    Splurge : float
        varsigma in eq. (4) / (5). If 0.0, reduces to the standard
        model (no splurge) and should match the m-indexed TM's implied
        a-distribution (mod grid discretization).
    cFuncs : list of J callables
        cFunc[j'](m_next_flat, Cratio_flat) -> c_star_flat. Evaluated
        inside the inner loop at joint (a, xi) points.
    IncShkDstn_list : list of J DiscreteDistributions (destination states).
    micro_trans : np.ndarray, shape (J, J), row-stochastic.
    Rfree_arr, PermGroFac_arr, LivPrb_arr : np.ndarray, shape (J,).
        LivPrb_arr is already passed through _effective_LivPrb by the
        caller.
    NewBornDist : np.ndarray, shape (A*J,). Sums to 1. Under a-indexing
        newborns enter at (a = dist_aGrid[0], j ~ markov_ergodic), so
        ``NewBornDist[j*A + 0] = markov_ergodic[j]`` and all other
        entries are zero.
    Cratio : float
        Aggregate demand ratio used as the 2nd cFunc argument. 1.0 for
        baseline builders; time-varying in experiment builders.
    neutral_measure : bool
        Reweight shock probabilities by psi (Harmenberg). Identical to
        the m-indexed convention so dist_aGrid holds an E_Q[a]-ergodic
        when True.
    ad_tran_shk_scale : float
        AD Channel A: multiplier on xi atoms for all destination states.
    employed_tran_shk_scale : float
        Tax-cut multiplier on xi atoms for destination state 0 only.
    TranShk_addition : np.ndarray (J,) or None
        Per-destination additive transitory income (stimulus check),
        added to xi AFTER scaling factors — matches the m-indexed
        convention where mNrm_shift is unscaled by ADF.
    interpretation : str, default 'CDC'
        Either 'CDC' (default; household-bargain asset rule per
        (eq:budget-CDC)) or 'ESC' (Campbell-Mankiw bound-pair, per-Optimizer
        asset rule per (eq:budget-ESC)). Default = 'CDC' preserves byte-
        identical behavior of all pre-existing call sites. ESC drops the
        splurge blending in c_actual (the splurger's varsigma*xi term is
        on a separate ledger and never enters the optimizer's a_next).

    Returns
    -------
    scipy.sparse.csc_matrix, shape (A*J, A*J), column-stochastic.
    """
    if interpretation not in ('CDC', 'ESC'):
        raise ValueError(
            f"interpretation must be 'CDC' or 'ESC', got: {interpretation!r}"
        )
    if neutral_measure:
        IncShkDstn_list = _to_neutral_measure(IncShkDstn_list)

    A = len(dist_aGrid)
    J = micro_trans.shape[0]
    N = A * J

    if TranShk_addition is None:
        TranShk_addition_arr = np.zeros(J)
    else:
        TranShk_addition_arr = np.asarray(TranShk_addition, dtype=np.float64)

    rows_list = []
    cols_list = []
    data_list = []

    nb_nz_idx = np.nonzero(NewBornDist > 1e-18)[0]
    nb_nz_val = NewBornDist[nb_nz_idx]
    n_nb = len(nb_nz_idx)

    src_range_A = np.arange(A, dtype=np.int64)

    Cratio_scalar = float(Cratio)

    for j in range(J):
        LivPrb_j = float(LivPrb_arr[j])
        death_prb = 1.0 - LivPrb_j
        col_offset = j * A

        # Death/rebirth: fraction death_prb of the mass at each source
        # (a_i, j) flows into the newborn distribution. Vectorized.
        if n_nb > 0 and death_prb > 1e-18:
            src_cols = np.repeat(src_range_A + col_offset, n_nb)
            dst_rows = np.tile(nb_nz_idx, A)
            vals = np.tile(death_prb * nb_nz_val, A)
            rows_list.append(dst_rows)
            cols_list.append(src_cols)
            data_list.append(vals)

        for jp in range(J):
            markov_prob = micro_trans[j, jp]
            if markov_prob < 1e-15:
                continue

            dstn_jp = IncShkDstn_list[jp]
            shk_prbs = dstn_jp.pmv
            perm_shks = dstn_jp.atoms[0]
            tran_shks_raw = dstn_jp.atoms[1]

            # Apply AD Channel A + per-state tax-cut scaling + additive
            # shift (check). Matches MC's TranShk construction at the
            # atom level for this destination state.
            emp_fac = employed_tran_shk_scale if jp == 0 else 1.0
            tran_shks = (ad_tran_shk_scale * emp_fac * tran_shks_raw
                         + TranShk_addition_arr[jp])
            S = len(shk_prbs)

            # m' = (R / (PermGroFac * psi)) * a + xi_eff   HARK normalization
            inv_pG = 1.0 / (perm_shks * PermGroFac_arr[jp])              # (S,)
            m_next = (Rfree_arr[jp] * dist_aGrid)[:, None] * inv_pG[None, :] \
                + tran_shks[None, :]                                       # (A, S)
            m_next_flat = m_next.ravel()                                   # (A*S,)

            # cFunc evaluated at the (a, xi) joint. 2-arg cFunc takes
            # (mNrm, Cratio) arrays.
            Cratio_flat = np.full_like(m_next_flat, Cratio_scalar)
            c_star_flat = cFuncs[jp](m_next_flat, Cratio_flat)             # (A*S,)

            # Asset-update consumption: under CDC, household-bargain blend
            # (eq:budget-CDC) of models_CDC_and_ESC.md §4.2; under ESC, just
            # the optimizer's policy consumption (eq:budget-ESC) of §5.2 — the
            # splurger's varsigma*xi consumption is on a separate ledger and
            # never enters the per-Optimizer a_next.
            xi_tile = np.tile(tran_shks, A)                                # (A*S,)
            if interpretation == 'CDC':
                c_actual_flat = (1.0 - Splurge) * c_star_flat \
                    + Splurge * xi_tile
            else:  # ESC
                c_actual_flat = c_star_flat
            a_next_flat = _a_next_checked(m_next_flat, c_actual_flat, dist_aGrid, S, jp,
                                          interpretation, Splurge)

            # Lottery onto dist_aGrid (linear interpolation).
            idx = np.searchsorted(dist_aGrid, a_next_flat, side='right') - 1
            below = a_next_flat <= dist_aGrid[0]
            above = a_next_flat >= dist_aGrid[-1]
            idx = np.clip(idx, 0, A - 2)

            lower_idx = idx
            upper_idx = idx + 1
            grid_lo = dist_aGrid[lower_idx]
            grid_hi = dist_aGrid[upper_idx]
            span = grid_hi - grid_lo
            span[span < 1e-30] = 1.0
            upper_wt = (a_next_flat - grid_lo) / span
            upper_wt = np.clip(upper_wt, 0.0, 1.0)
            lower_wt = 1.0 - upper_wt

            lower_idx[below] = 0
            upper_idx[below] = 0
            lower_wt[below] = 1.0
            upper_wt[below] = 0.0
            lower_idx[above] = A - 1
            upper_idx[above] = A - 1
            lower_wt[above] = 1.0
            upper_wt[above] = 0.0

            # (A*S,) weights, a-major / xi-minor — same layout as m_next_flat.
            wt = markov_prob * LivPrb_j * np.tile(shk_prbs, A)
            src_cols = np.repeat(src_range_A + col_offset, S)

            vals_lo = wt * lower_wt
            mask_lo = vals_lo > 1e-18
            if np.any(mask_lo):
                rows_list.append(jp * A + lower_idx[mask_lo])
                cols_list.append(src_cols[mask_lo])
                data_list.append(vals_lo[mask_lo])

            vals_hi = wt * upper_wt
            mask_hi = vals_hi > 1e-18
            if np.any(mask_hi):
                rows_list.append(jp * A + upper_idx[mask_hi])
                cols_list.append(src_cols[mask_hi])
                data_list.append(vals_hi[mask_hi])

    all_rows = np.concatenate(rows_list)
    all_cols = np.concatenate(cols_list)
    all_data = np.concatenate(data_list)

    TranMatrix = sp.csc_matrix(
        (all_data, (all_rows, all_cols)), shape=(N, N)
    )
    TranMatrix.sum_duplicates()
    return TranMatrix


def _make_newborn_dist_a(dist_aGrid, markov_weights):
    """
    Newborn distribution in (a, j) space.

    Under a-indexing, a newborn enters with zero assets; their FIRST
    period then draws (psi, xi), yielding m_1 = xi_1 and
    a_1 = m_1 - c_actual(m_1, xi_1). So the newborn dist in a-space is
    simply mass at a = dist_aGrid[0] (which equals 0 for the standard
    exp-multiple grid), with micro state j drawn from the Markov
    ergodic.
    """
    A = len(dist_aGrid)
    J = len(markov_weights)
    NewBornDist = np.zeros(A * J)
    for jp in range(J):
        # mass concentrated at the lowest a-grid point for each j
        NewBornDist[jp * A + 0] = markov_weights[jp]
    s = np.sum(NewBornDist)
    if s > 0:
        NewBornDist /= s
    return NewBornDist


def _dist_tail_state_enabled():
    """Parse HAFISCAL_DIST_TAIL_STATE (P4' tail state, scope TS-1).

    Off values {'', '0', 'off'} = today's bytes exactly (the tail_state=None
    code path is the untouched current code); on values {'1', 'on'}; any
    other value RAISES (precedent: HAFISCAL_DIST_TOP_MODE raises on unknown).
    Read at call time, never at import time.
    """
    val = _os.environ.get('HAFISCAL_DIST_TAIL_STATE', 'off').strip().lower()
    if val in ('', '0', 'off'):
        return False
    if val in ('1', 'on'):
        return True
    raise ValueError(
        f"HAFISCAL_DIST_TAIL_STATE must be one of off|0|'' (off) or on|1 "
        f"(on), got {val!r}")


def _make_newborn_dist_a_tail(dist_aGrid, markov_weights):
    """Newborn distribution in the TAIL-STATE (a, j) space, length (A+1)*J.

    Layout: index = j*(A+1) + i for grid nodes i = 0..A-1, tail T_j at
    i = A. Newborns enter at the grid bottom exactly as in
    ``_make_newborn_dist_a`` -- the tail rows carry EXACTLY ZERO mass
    (DERIVATION note section 4(b); verified V4).
    """
    A = len(dist_aGrid)
    J = len(markov_weights)
    NewBornDist = np.zeros((A + 1) * J)
    for jp in range(J):
        NewBornDist[jp * (A + 1) + 0] = markov_weights[jp]
    s = np.sum(NewBornDist)
    if s > 0:
        NewBornDist /= s
    return NewBornDist


def _build_period_tm_a_tail(dist_aGrid, Splurge, cFuncs, IncShkDstn_list,
                            micro_trans, Rfree_arr, PermGroFac_arr, LivPrb_arr,
                            NewBornDist, tail_state, Cratio=1.0,
                            interpretation='ESC'):
    """
    Tail-state variant of ``_build_period_tm_a``: a ((A+1)*J) x ((A+1)*J)
    column-stochastic TM with one analytic Pareto TAIL STATE T_j per micro
    state appended at index j*(A+1) + A (HAFISCAL_DIST_TAIL_STATE; the
    2026-07-26 DERIVATION note, sections 1-4; scope TS-1 =
    baseline-ergodic ONLY -- reachable only from ``build_tm_agg_fiscal_a``
    after its guards: Cratio=1, neutral_measure=False, ESC, uniform R and
    LivPrb across micro states).

    Column recipe (note section 4, verified exactly in V4 -- column sums 1
    to 2.2e-16 including death->newborn, T communicates, power iteration
    converges with positive finite tail mass):

    (a) ORDINARY source columns (a_i, j): identical to ``_build_period_tm_a``
        except the INFLOW REDIRECT -- the mass the lottery currently clips to
        the top node via the ``above`` mask (a_next >= dist_aGrid[-1]; the
        boundary point a=X belongs to T's Pareto support [X, inf)) goes to
        row T_{j'} instead of node A-1.  Nothing else changes.
    (b) DEATH->NEWBORN from ALL A+1 source columns of state j (including
        T_j): (1 - L_eff(j)) * NewBornDist, with NewBornDist carrying zero
        tail mass (newborns start at the grid bottom).
    (c) TAIL column T_j, survivor part: contents a ~ Pareto(alpha) on
        [X, inf); per destination j' and shock atom s with per-survivor
        multiplier

            m_s(j', s) = pat_num / (PermGroFac[j'] * psi_s),
            pat_num    = (R * beta * L_raw)^(1/CRRA)   [= (1-kappa)*R]

        (the SAME effective-growth object per_atom_alpha uses, survival
        discounting INSIDE the CRRA root per the HARK DiscFacEff = beta*L
        convention -- empirically pinned by the note's V1 EGM measurement),
        with weight w0 = L_eff(j) * Mrkv[j,j'] * p_s:

            m >= 1: T[T_j', T_j] += w0                       (all stay)
            m <  1: T[T_j', T_j] += w0 * m^alpha             (stay)
                    grid rows    += w0 * (1 - m^alpha) * landing_node_weights
                    (truncated Pareto(alpha) on [mX, X) lotteried onto the
                    grid nodes; ``dist_tail_state.landing_node_weights``)

    Column-stochasticity: ordinary columns -- the redirect moves weight
    between rows of the same column; tail column --
    (1-L) + L * sum_j' Mrkv * sum_s p_s * (m^alpha + (1-m^alpha)) = 1.

    ``tail_state`` is the dict from ``dist_tail_state.resolve_tail_alpha``
    (needs keys 'alpha', 'pat_num').

    Returns scipy.sparse.csc_matrix, shape ((A+1)*J, (A+1)*J).
    """
    if interpretation != 'ESC':
        # ESC-only where consumption enters (the interpretation guard
        # pattern): the outflow law uses the ESC asymptotic cFunc slope
        # (1 - kappa); the CDC blend (1-varsigma)*c* + varsigma*xi has a
        # DIFFERENT asymptotic slope (1 - (1-varsigma)*kappa) -- out of
        # scope TS-1, refuse (DERIVATION note section 0).
        raise ValueError(
            f"_build_period_tm_a_tail is ESC-only (HAFISCAL_DIST_TAIL_STATE "
            f"scope TS-1): the tail outflow law is derived from the ESC "
            f"asymptotic consumption slope; got interpretation="
            f"{interpretation!r}")

    # Lazy import (flag-on path only; precedent: the adaptive_grid_tm lazy
    # import in build_tm_agg_fiscal_a).
    import sys as _sys_ts
    _hamodels_ts = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _hamodels_ts not in _sys_ts.path:
        _sys_ts.path.insert(0, _hamodels_ts)
    from dist_tail_state import landing_node_weights

    A = len(dist_aGrid)
    J = micro_trans.shape[0]
    stride = A + 1
    N = stride * J
    alpha = float(tail_state['alpha'])
    pat_num = float(tail_state['pat_num'])

    if len(NewBornDist) != N:
        raise ValueError(
            f"tail-state NewBornDist must have length (A+1)*J = {N}, got "
            f"{len(NewBornDist)} (use _make_newborn_dist_a_tail)")
    _tail_rows = np.arange(J, dtype=np.int64) * stride + A
    if np.any(NewBornDist[_tail_rows] != 0.0):
        raise ValueError(
            "tail-state NewBornDist carries mass on tail rows -- newborns "
            "must start at the grid bottom (DERIVATION note section 4(b))")

    rows_list = []
    cols_list = []
    data_list = []

    nb_nz_idx = np.nonzero(NewBornDist > 1e-18)[0]
    nb_nz_val = NewBornDist[nb_nz_idx]
    n_nb = len(nb_nz_idx)

    src_range_A = np.arange(A, dtype=np.int64)
    Cratio_scalar = float(Cratio)

    for j in range(J):
        LivPrb_j = float(LivPrb_arr[j])
        death_prb = 1.0 - LivPrb_j
        col_offset = j * stride

        # (b) Death/rebirth from ALL A+1 source columns (grid nodes AND T_j).
        if n_nb > 0 and death_prb > 1e-18:
            src_cols = np.repeat(
                np.arange(stride, dtype=np.int64) + col_offset, n_nb)
            dst_rows = np.tile(nb_nz_idx, stride)
            vals = np.tile(death_prb * nb_nz_val, stride)
            rows_list.append(dst_rows)
            cols_list.append(src_cols)
            data_list.append(vals)

        for jp in range(J):
            markov_prob = micro_trans[j, jp]
            if markov_prob < 1e-15:
                continue

            dstn_jp = IncShkDstn_list[jp]
            shk_prbs = dstn_jp.pmv
            perm_shks = dstn_jp.atoms[0]
            # Baseline-only scope: no AD scaling, no per-state tax-cut
            # scaling, no TranShk_addition (guarded in build_tm_agg_fiscal_a).
            tran_shks = dstn_jp.atoms[1]
            S = len(shk_prbs)

            # ---- (a) ordinary columns: the _build_period_tm_a kernel under
            # ESC, with the above-top mass REDIRECTED to T_{jp} ----
            inv_pG = 1.0 / (perm_shks * PermGroFac_arr[jp])              # (S,)
            m_next = (Rfree_arr[jp] * dist_aGrid)[:, None] * inv_pG[None, :] \
                + tran_shks[None, :]                                       # (A, S)
            m_next_flat = m_next.ravel()                                   # (A*S,)

            Cratio_flat = np.full_like(m_next_flat, Cratio_scalar)
            c_star_flat = cFuncs[jp](m_next_flat, Cratio_flat)             # (A*S,)
            c_actual_flat = c_star_flat  # ESC (guarded above)
            a_next_flat = _a_next_checked(m_next_flat, c_actual_flat,
                                          dist_aGrid, S, jp,
                                          interpretation, Splurge)

            idx = np.searchsorted(dist_aGrid, a_next_flat, side='right') - 1
            below = a_next_flat <= dist_aGrid[0]
            # The kernel's EXISTING above mask, >= not >: the boundary point
            # a = X belongs to T's Pareto support [X, inf); the top grid node
            # keeps only lottery mass from the last interval (note dev 5).
            above = a_next_flat >= dist_aGrid[-1]
            idx = np.clip(idx, 0, A - 2)

            lower_idx = idx
            upper_idx = idx + 1
            grid_lo = dist_aGrid[lower_idx]
            grid_hi = dist_aGrid[upper_idx]
            span = grid_hi - grid_lo
            span[span < 1e-30] = 1.0
            upper_wt = (a_next_flat - grid_lo) / span
            upper_wt = np.clip(upper_wt, 0.0, 1.0)
            lower_wt = 1.0 - upper_wt

            lower_idx[below] = 0
            upper_idx[below] = 0
            lower_wt[below] = 1.0
            upper_wt[below] = 0.0

            # (A*S,) weights, a-major / xi-minor -- same layout as m_next_flat.
            wt = markov_prob * LivPrb_j * np.tile(shk_prbs, A)
            src_cols = np.repeat(src_range_A + col_offset, S)

            vals_lo = wt * lower_wt
            mask_lo = (vals_lo > 1e-18) & (~above)
            if np.any(mask_lo):
                rows_list.append(jp * stride + lower_idx[mask_lo])
                cols_list.append(src_cols[mask_lo])
                data_list.append(vals_lo[mask_lo])

            vals_hi = wt * upper_wt
            mask_hi = (vals_hi > 1e-18) & (~above)
            if np.any(mask_hi):
                rows_list.append(jp * stride + upper_idx[mask_hi])
                cols_list.append(src_cols[mask_hi])
                data_list.append(vals_hi[mask_hi])

            # INFLOW REDIRECT: the clipped-to-top mass goes to T_{jp}.
            w_above = np.where(above, wt, 0.0).reshape(A, S).sum(axis=1)  # (A,)
            nz_above = w_above > 1e-18
            if np.any(nz_above):
                rows_list.append(np.full(int(nz_above.sum()),
                                         jp * stride + A, dtype=np.int64))
                cols_list.append((src_range_A + col_offset)[nz_above])
                data_list.append(w_above[nz_above])

            # ---- (c) tail column T_j, survivor part ----
            col_T = col_offset + A
            m_atoms = pat_num / (PermGroFac_arr[jp] * perm_shks)          # (S,)
            w0 = markov_prob * LivPrb_j * shk_prbs                        # (S,)
            stay_frac = np.ones(S)
            ret_mask = m_atoms < 1.0
            stay_frac[ret_mask] = m_atoms[ret_mask] ** alpha
            ret_frac = 1.0 - stay_frac
            # Mass-conserving absorb of float-underflow returns (m so close
            # to 1 that 1 - m^alpha < 1e-12): keep the column sum EXACT by
            # counting that sliver as stay instead of feeding a degenerate
            # landing law. Production m_s values sit well away from 1.
            _tiny = ret_mask & (ret_frac < 1e-12)
            if np.any(_tiny):
                stay_frac[_tiny] = 1.0
                ret_frac[_tiny] = 0.0
                ret_mask = ret_mask & (~_tiny)
            stay_total = float(np.sum(w0 * stay_frac))
            if stay_total > 1e-18:
                rows_list.append(np.array([jp * stride + A], dtype=np.int64))
                cols_list.append(np.array([col_T], dtype=np.int64))
                data_list.append(np.array([stay_total]))
            for s in np.nonzero(ret_mask)[0]:
                ret_wt = float(w0[s]) * float(ret_frac[s])
                if ret_wt <= 1e-18:
                    continue
                node_w = landing_node_weights(alpha, float(m_atoms[s]),
                                              dist_aGrid)                 # (A,)
                vals_land = ret_wt * node_w
                nzl = vals_land > 1e-18
                if np.any(nzl):
                    rows_list.append(
                        jp * stride + np.nonzero(nzl)[0].astype(np.int64))
                    cols_list.append(
                        np.full(int(nzl.sum()), col_T, dtype=np.int64))
                    data_list.append(vals_land[nzl])

    all_rows = np.concatenate(rows_list)
    all_cols = np.concatenate(cols_list)
    all_data = np.concatenate(data_list)

    TranMatrix = sp.csc_matrix(
        (all_data, (all_rows, all_cols)), shape=(N, N)
    )
    TranMatrix.sum_duplicates()
    return TranMatrix


def _build_pk_weighted_survival_kernel_a(
        k_moment, dist_aGrid, Splurge, cFuncs, IncShkDstn_list, micro_trans,
        Rfree_arr, PermGroFac_arr, LivPrb_arr, Cratio=1.0,
        ad_tran_shk_scale=1.0, employed_tran_shk_scale=1.0,
        TranShk_addition=None, interpretation='CDC'):
    """
    Generalized k-th moment p-weighted survival kernel
    ``T_{S, p^k}[x → x'] = L_j Σ_{j',s} Mrkv[j,j'] shk_s G_{j'}^k psi_s^k
                             lottery_{x→x'}(j', s)``
    per `(eq:T-S-pk)` in history/20260331-mathematical-derivations-harmenberg.md §23.7
    (which generalizes the k=1 Doob construction in §21.6).

    Same loop structure as ``_build_period_tm_a`` but: (a) drops the birth
    / newborn contribution; (b) weights each shock realization by
    ``G_{j'}^k_moment * psi_s^k_moment`` (the per-period p^k_moment
    multiplier for survivors).

    Special cases used in cohort-age decomposition (math doc §24):
      k_moment = 0  →  T_S  (survival-only kernel; no p-weight; sub-
                      stochastic with column sum L_j)
      k_moment = 1  →  T_S,p  (Doob's kernel for w(x) = E_P[p|x])
      k_moment = 2  →  T_S,p²  (kernel for v_2(x) = E_P[p²|x])

    Returns: scipy.sparse.csc_matrix, shape (A*J, A*J), sub-stochastic
    (and not row- or column-stochastic for k_moment ≠ 0; for k_moment = 0
    column sums equal L_j ≤ 1).
    """
    if interpretation not in ('CDC', 'ESC'):
        raise ValueError(
            f"interpretation must be 'CDC' or 'ESC', got: {interpretation!r}")
    if k_moment < 0 or not float(k_moment).is_integer():
        raise ValueError(
            f"k_moment must be a non-negative integer, got: {k_moment!r}")
    k = int(k_moment)

    A = len(dist_aGrid)
    J = micro_trans.shape[0]
    N = A * J

    if TranShk_addition is None:
        TranShk_addition_arr = np.zeros(J)
    else:
        TranShk_addition_arr = np.asarray(TranShk_addition, dtype=np.float64)

    rows_list = []
    cols_list = []
    data_list = []
    src_range_A = np.arange(A, dtype=np.int64)
    Cratio_scalar = float(Cratio)

    for j in range(J):
        LivPrb_j = float(LivPrb_arr[j])
        col_offset = j * A

        for jp in range(J):
            markov_prob = float(micro_trans[j, jp])
            if markov_prob < 1e-15:
                continue
            G_jp = float(PermGroFac_arr[jp])

            dstn_jp = IncShkDstn_list[jp]
            shk_prbs = dstn_jp.pmv
            perm_shks = dstn_jp.atoms[0]
            tran_shks_raw = dstn_jp.atoms[1]
            emp_fac = employed_tran_shk_scale if jp == 0 else 1.0
            tran_shks = (ad_tran_shk_scale * emp_fac * tran_shks_raw
                         + TranShk_addition_arr[jp])
            S = len(shk_prbs)

            inv_pG = 1.0 / (perm_shks * G_jp)
            m_next = (Rfree_arr[jp] * dist_aGrid)[:, None] * inv_pG[None, :] \
                + tran_shks[None, :]
            m_next_flat = m_next.ravel()
            Cratio_flat = np.full_like(m_next_flat, Cratio_scalar)
            c_star_flat = cFuncs[jp](m_next_flat, Cratio_flat)
            xi_tile = np.tile(tran_shks, A)
            if interpretation == 'CDC':
                c_actual_flat = (1.0 - Splurge) * c_star_flat + Splurge * xi_tile
            else:
                c_actual_flat = c_star_flat
            a_next_flat = _a_next_checked(m_next_flat, c_actual_flat, dist_aGrid, S, jp,
                                          interpretation, Splurge)

            idx = np.searchsorted(dist_aGrid, a_next_flat, side='right') - 1
            below = a_next_flat <= dist_aGrid[0]
            above = a_next_flat >= dist_aGrid[-1]
            idx = np.clip(idx, 0, A - 2)
            lower_idx = idx
            upper_idx = idx + 1
            grid_lo = dist_aGrid[lower_idx]
            grid_hi = dist_aGrid[upper_idx]
            span = grid_hi - grid_lo
            span[span < 1e-30] = 1.0
            upper_wt = (a_next_flat - grid_lo) / span
            upper_wt = np.clip(upper_wt, 0.0, 1.0)
            lower_wt = 1.0 - upper_wt
            lower_idx[below] = 0; upper_idx[below] = 0
            lower_wt[below] = 1.0; upper_wt[below] = 0.0
            lower_idx[above] = A - 1; upper_idx[above] = A - 1
            lower_wt[above] = 1.0; upper_wt[above] = 0.0

            # KEY: weight each shock by G_jp^k * psi_s^k (the p^k multiplier).
            # k=0: no p-weight (T_S, survival-only).
            # k=1: G_jp * psi_s (T_S,p, Doob kernel).
            # k=2: G_jp**2 * psi_s**2 (T_S,p², for v_2 second moment).
            psi_tile = np.tile(perm_shks, A)
            shk_tile = np.tile(shk_prbs, A)
            if k == 0:
                wt = markov_prob * LivPrb_j * shk_tile
            elif k == 1:
                wt = markov_prob * LivPrb_j * shk_tile * G_jp * psi_tile
            else:
                wt = (markov_prob * LivPrb_j * shk_tile
                      * (G_jp ** k) * (psi_tile ** k))
            src_cols = np.repeat(src_range_A + col_offset, S)

            vals_lo = wt * lower_wt
            mask_lo = vals_lo > 1e-18
            if np.any(mask_lo):
                rows_list.append(jp * A + lower_idx[mask_lo])
                cols_list.append(src_cols[mask_lo])
                data_list.append(vals_lo[mask_lo])
            vals_hi = wt * upper_wt
            mask_hi = vals_hi > 1e-18
            if np.any(mask_hi):
                rows_list.append(jp * A + upper_idx[mask_hi])
                cols_list.append(src_cols[mask_hi])
                data_list.append(vals_hi[mask_hi])

    all_rows = np.concatenate(rows_list)
    all_cols = np.concatenate(cols_list)
    all_data = np.concatenate(data_list)
    T_surv_pk = sp.csc_matrix((all_data, (all_rows, all_cols)), shape=(N, N))
    T_surv_pk.sum_duplicates()
    return T_surv_pk


def _build_p_weighted_survival_kernel_a(
        dist_aGrid, Splurge, cFuncs, IncShkDstn_list, micro_trans,
        Rfree_arr, PermGroFac_arr, LivPrb_arr, Cratio=1.0,
        ad_tran_shk_scale=1.0, employed_tran_shk_scale=1.0,
        TranShk_addition=None, interpretation='CDC'):
    """
    Build T_S,p — the p-weighted survival kernel (Fix 4 / `(eq:T-S-p)` in
    history/20260331-mathematical-derivations-harmenberg.md §21.6).

    Thin backwards-compat wrapper around
    ``_build_pk_weighted_survival_kernel_a(k_moment=1, ...)``. The
    underlying generalized implementation also supports k=0 (T_S,
    survival-only) and k=2 (T_S,p², for second-moment Doob v_2).

    Used by ``compute_doob_pi_q_a`` to solve the sparse linear system
    ``(I - T_S,p) f = delta_bar * NewBornDist`` for ``f = w * pi_P``,
    yielding the true Q-marginal ``pi_Q^{true}(x) = w(x) * pi_P(x) / p_bar``
    that does NOT suffer from BST Theorem 1's mortality-induced bias.

    Returns: scipy.sparse.csc_matrix, shape (A*J, A*J), sub-stochastic.
    """
    return _build_pk_weighted_survival_kernel_a(
        1, dist_aGrid, Splurge, cFuncs, IncShkDstn_list, micro_trans,
        Rfree_arr, PermGroFac_arr, LivPrb_arr, Cratio=Cratio,
        ad_tran_shk_scale=ad_tran_shk_scale,
        employed_tran_shk_scale=employed_tran_shk_scale,
        TranShk_addition=TranShk_addition, interpretation=interpretation)


def _build_survival_only_kernel_a(
        dist_aGrid, Splurge, cFuncs, IncShkDstn_list, micro_trans,
        Rfree_arr, PermGroFac_arr, LivPrb_arr, Cratio=1.0,
        ad_tran_shk_scale=1.0, employed_tran_shk_scale=1.0,
        TranShk_addition=None, interpretation='CDC'):
    """
    Build T_S — the survival-only kernel (no p-weighting). This is the
    survival portion of the TM-P kernel built by ``_build_period_tm_a``
    with the birth contribution dropped:
        T_S[x → x'] = L_j Σ_{j',s} Mrkv[j,j'] shk_s lottery_{x→x'}(j', s)
    Per (eq:TM-P-decomp): T_P = (1 - L_j) π_N + T_S.

    Used by ``compute_cohort_age_decomposition_a`` for the cohort-age
    forward recursion (eq:cohort-fwd-prop) per math doc §24.3.

    Thin wrapper around ``_build_pk_weighted_survival_kernel_a(k_moment=0)``.
    Column sums equal L_j (sub-stochastic; deficit = mortality rate).
    """
    return _build_pk_weighted_survival_kernel_a(
        0, dist_aGrid, Splurge, cFuncs, IncShkDstn_list, micro_trans,
        Rfree_arr, PermGroFac_arr, LivPrb_arr, Cratio=Cratio,
        ad_tran_shk_scale=ad_tran_shk_scale,
        employed_tran_shk_scale=employed_tran_shk_scale,
        TranShk_addition=TranShk_addition, interpretation=interpretation)


def _build_p2_weighted_survival_kernel_a(
        dist_aGrid, Splurge, cFuncs, IncShkDstn_list, micro_trans,
        Rfree_arr, PermGroFac_arr, LivPrb_arr, Cratio=1.0,
        ad_tran_shk_scale=1.0, employed_tran_shk_scale=1.0,
        TranShk_addition=None, interpretation='CDC'):
    """
    Build T_S,p² — the second-moment p²-weighted survival kernel:
        T_S,p²[x → x'] = L_j Σ_{j',s} Mrkv[j,j'] shk_s G_{j'}² psi_s²
                          lottery_{x→x'}(j', s)
    per (eq:T-S-pk) at k=2 in math doc §23.7 / §24.4.

    Used by ``compute_cohort_age_decomposition_a`` for the cohort-conditional
    second-moment recursion (eq:cohort-moment-fwd) and by ``compute_doob_v2_a``
    for the stationary v_2(x) = E_P[p²|x] solve.

    Thin wrapper around ``_build_pk_weighted_survival_kernel_a(k_moment=2)``.
    """
    return _build_pk_weighted_survival_kernel_a(
        2, dist_aGrid, Splurge, cFuncs, IncShkDstn_list, micro_trans,
        Rfree_arr, PermGroFac_arr, LivPrb_arr, Cratio=Cratio,
        ad_tran_shk_scale=ad_tran_shk_scale,
        employed_tran_shk_scale=employed_tran_shk_scale,
        TranShk_addition=TranShk_addition, interpretation=interpretation)


def compute_doob_pi_q_a(agent, tm_data, ergodic_P, Cratio=1.0,
                        ad_tran_shk_scale=1.0, employed_tran_shk_scale=1.0,
                        TranShk_addition=None, interpretation='CDC'):
    """
    Compute the true Q-marginal ``pi_Q^{true}(a, j) = w(a, j) * pi_P(a, j) / p_bar``
    via the Fix 4 (Doob) construction, for the a-indexed TM.

    This is the **direct exact correction** for TM-Q's mortality-induced
    downward bias. See ``history/20260331-mathematical-derivations-harmenberg.md``
    §21.6 Fix 4 for derivation; ``conclusions_private/2026-04-28_fix4-doob-pi-q-beats-tm-q-empirically.md``
    for empirical verification.

    Algorithm:
      1. Build T_S,p (p-weighted survival kernel) per ``(eq:T-S-p)``.
      2. Solve sparse system ``(I - T_S,p) f = delta_bar * NewBornDist``
         per ``(eq:f-linear-system)``, where ``f = w * pi_P`` and
         ``delta_bar = sum_x pi_P(x) * (1 - L_{j(x)})`` is the aggregate
         death rate.
      3. Return ``pi_Q_doob = f / sum(f)`` per ``(eq:pi-Q-doob)``.

    Parameters
    ----------
    agent : AggFiscalType (solved)
    tm_data : dict from ``build_tm_agg_fiscal_a`` (with neutral_measure=False;
        the P-measure tm_data is what we need for delta_bar / pi_N)
    ergodic_P : (A*J,) ndarray
        TM-P ergodic distribution from ``find_ergodic_distribution(tm_data['TranMatrix'])``.
    Cratio, ad_tran_shk_scale, employed_tran_shk_scale, TranShk_addition,
    interpretation : passed through to ``_build_p_weighted_survival_kernel_a``.

    Returns
    -------
    dict with keys:
      'pi_Q_doob' : (A*J,) ndarray, true Q-marginal
      'w'         : (A*J,) ndarray, conditional E_P[p | a, j]; NaN where pi_P=0
      'p_bar'     : float, sum(f); equals E_P[p] up to a global newborn-p_init
                    scaling (not necessarily MC's absolute p_bar)
      'T_surv_p'  : sparse matrix (kept for diagnostics)
    """
    dist_aGrid = tm_data['dist_aGrid']
    A = len(dist_aGrid)
    MrkvArray = np.asarray(agent.MrkvArray[0], dtype=np.float64)
    J = MrkvArray.shape[0]
    N = A * J

    Splurge = float(agent.Splurge)
    Rfree_arr = np.asarray(agent.Rfree[:J], dtype=np.float64)
    PermGroFac_arr = np.asarray(agent.PermGroFac[0][:J], dtype=np.float64)
    LivPrb_arr_raw = np.asarray(agent.LivPrb[0][:J], dtype=np.float64)
    T_age = getattr(agent, 'T_age', None)
    LivPrb_arr = _effective_LivPrb(LivPrb_arr_raw, T_age)

    cFuncs = [agent.solution[0].cFunc[j] for j in range(J)]

    # NewBornDist on (a, j): same convention as production code.
    markov_ergodic = _solve_markov_ergodic(MrkvArray)
    NewBornDist = _make_newborn_dist_a(dist_aGrid, markov_ergodic)

    # delta_bar = sum_j (1 - L_j) * pi_P(., j)
    pi_P_2d = ergodic_P.reshape(J, A)
    delta_bar = float(np.sum([(1.0 - LivPrb_arr[j]) * np.sum(pi_P_2d[j])
                              for j in range(J)]))

    T_surv_p = _build_p_weighted_survival_kernel_a(
        dist_aGrid, Splurge, cFuncs, agent.IncShkDstn[0], MrkvArray,
        Rfree_arr, PermGroFac_arr, LivPrb_arr, Cratio=Cratio,
        ad_tran_shk_scale=ad_tran_shk_scale,
        employed_tran_shk_scale=employed_tran_shk_scale,
        TranShk_addition=TranShk_addition, interpretation=interpretation)

    # Forward evolution f_{t+1} = delta_bar * NewBornDist + T_surv_p * f_t
    # (T_surv_p is column-stochastic-style, T[dst, src], so we use it directly,
    # NOT its transpose). Stationary: (I - T_surv_p) f = delta_bar * NewBornDist.
    I_N = sp.eye(N, format='csc')
    A_mat = (I_N - T_surv_p).tocsc()
    rhs = delta_bar * NewBornDist
    f = spla.spsolve(A_mat, rhs)

    p_bar = float(np.sum(f))
    pi_Q_doob = f / p_bar

    with np.errstate(divide='ignore', invalid='ignore'):
        w = np.where(ergodic_P > 1e-30, f / np.maximum(ergodic_P, 1e-30), np.nan)

    return {
        'pi_Q_doob': pi_Q_doob,
        'w': w,
        'p_bar': p_bar,
        'T_surv_p': T_surv_p,
    }


def compute_doob_v2_a(agent, tm_data, ergodic_P, Cratio=1.0,
                      ad_tran_shk_scale=1.0, employed_tran_shk_scale=1.0,
                      TranShk_addition=None, interpretation='CDC',
                      doob_out=None):
    """
    Compute the conditional second moment v_2(x) = E_P[p² | (a, j) = x]
    via the second-moment Doob system per (eq:fk-linear-system) at k=2:

        (I - T_S,p²) f_2 = δ̄ · π_N

    where f_2(x) = v_2(x) · π_P(x) is the cohort-integrated occupation
    function. Same construction as ``compute_doob_pi_q_a`` (Fix 4) but with
    G²ψ²-weighted survival kernel ``T_S,p²`` instead of Gψ-weighted ``T_S,p``.

    See ``history/20260331-mathematical-derivations-harmenberg.md`` §23.7
    for derivation; serves as the cross-check companion to
    ``compute_cohort_age_decomposition_a`` per math doc §24.7.

    Parameters
    ----------
    agent, tm_data, ergodic_P, Cratio, ad_tran_shk_scale,
    employed_tran_shk_scale, TranShk_addition, interpretation : same as
        ``compute_doob_pi_q_a``.
    doob_out : optional dict from ``compute_doob_pi_q_a``. If provided,
        used to compute the conditional variance V(x) = v_2(x) - w(x)²
        and a 2-moment lognormal fit per (eq:cohort-lognormal-fit). If None,
        only v_2 and f_2 are returned (variance/lognormal fit omitted).

    Returns
    -------
    dict with keys:
      'f_2'              : (A*J,) ndarray, E_P[p² · 𝟙{X = x}]
      'v_2'              : (A*J,) ndarray, conditional second moment;
                           NaN where π_P = 0
      'T_surv_p2'        : sparse matrix (kept for diagnostics)
      'conditional_var'  : (A*J,) ndarray, V(x) = v_2(x) - w(x)²;
                           only if doob_out provided
      'lognormal_sigma'  : (A*J,) ndarray, σ_x for 2-moment lognormal fit;
                           only if doob_out provided
      'lognormal_mu'     : (A*J,) ndarray, μ_x for 2-moment lognormal fit;
                           only if doob_out provided
    """
    dist_aGrid = tm_data['dist_aGrid']
    A = len(dist_aGrid)
    MrkvArray = np.asarray(agent.MrkvArray[0], dtype=np.float64)
    J = MrkvArray.shape[0]
    N = A * J

    Splurge = float(agent.Splurge)
    Rfree_arr = np.asarray(agent.Rfree[:J], dtype=np.float64)
    PermGroFac_arr = np.asarray(agent.PermGroFac[0][:J], dtype=np.float64)
    LivPrb_arr_raw = np.asarray(agent.LivPrb[0][:J], dtype=np.float64)
    T_age = getattr(agent, 'T_age', None)
    LivPrb_arr = _effective_LivPrb(LivPrb_arr_raw, T_age)

    cFuncs = [agent.solution[0].cFunc[j] for j in range(J)]

    markov_ergodic = _solve_markov_ergodic(MrkvArray)
    NewBornDist = _make_newborn_dist_a(dist_aGrid, markov_ergodic)

    pi_P_2d = ergodic_P.reshape(J, A)
    delta_bar = float(np.sum([(1.0 - LivPrb_arr[j]) * np.sum(pi_P_2d[j])
                              for j in range(J)]))

    T_surv_p2 = _build_p2_weighted_survival_kernel_a(
        dist_aGrid, Splurge, cFuncs, agent.IncShkDstn[0], MrkvArray,
        Rfree_arr, PermGroFac_arr, LivPrb_arr, Cratio=Cratio,
        ad_tran_shk_scale=ad_tran_shk_scale,
        employed_tran_shk_scale=employed_tran_shk_scale,
        TranShk_addition=TranShk_addition, interpretation=interpretation)

    I_N = sp.eye(N, format='csc')
    A_mat = (I_N - T_surv_p2).tocsc()
    rhs = delta_bar * NewBornDist
    f_2 = spla.spsolve(A_mat, rhs)

    with np.errstate(divide='ignore', invalid='ignore'):
        v_2 = np.where(ergodic_P > 1e-30, f_2 / np.maximum(ergodic_P, 1e-30), np.nan)

    out = {'f_2': f_2, 'v_2': v_2, 'T_surv_p2': T_surv_p2}

    if doob_out is not None:
        w = np.asarray(doob_out['w'])
        with np.errstate(invalid='ignore'):
            cond_var = v_2 - w * w
        # 2-moment lognormal fit per (eq:cohort-lognormal-fit)
        with np.errstate(divide='ignore', invalid='ignore'):
            ratio = cond_var / (w * w)
            # Numerical safety: very small variance can produce tiny negative
            # values from float roundoff; clip to 0.
            ratio = np.where(np.isfinite(ratio), np.maximum(ratio, 0.0), np.nan)
            sigma2_log = np.log1p(ratio)
            sigma_log = np.sqrt(sigma2_log)
            mu_log = np.log(np.maximum(w, 1e-30)) - 0.5 * sigma2_log
        out['conditional_var'] = cond_var
        out['lognormal_sigma'] = sigma_log
        out['lognormal_mu'] = mu_log

    return out


def compute_cohort_age_decomposition_a(
        agent, tm_data, K_max=2000,
        Cratio=1.0, ad_tran_shk_scale=1.0, employed_tran_shk_scale=1.0,
        TranShk_addition=None, interpretation='CDC',
        unemp_shocks='employed',
        measure='P', T_age=None,
        verify_against_doob=True, doob_tol=None):
    """
    Cohort-age decomposition for joint MC initialization
    (Fix-4 successor; math doc §24, §25).

    P-mode (default): per math doc §24, computes the cohort-conditional state
    distribution π^{(ℓ)}(x) and p-moment occupation functions g_k^{(ℓ)}(x)
    for k ∈ {1, 2}.

    Q-mode (BUG-038, kwarg measure='Q' + T_age=...): per math doc §25,
    additionally computes the Q-twisted Harmenberg cohort decomposition under
    the T_age cap. Uses size-biased ψ shocks and size-biased newborn p_init.
    Replaces the L_eff-based compute_doob_pi_q_a in the heavy-tail regime
    (perpetual-youth where ρ(T_S,p²) > 1 makes v_2 ill-conditioned).

    Forward-propagates the cohort-conditional state distribution
    π^{(ℓ)}(x) and p-moment occupation functions g_k^{(ℓ)}(x) for k ∈ {1, 2}
    over cohort ages ℓ = 0, …, K_max, starting from the newborn injection
    at ℓ = 0. Per math doc §24:

        π^{(ℓ+1)}(x') = Σ_x T_S[x→x'] π^{(ℓ)}(x) / L^{(ℓ)}     (eq:cohort-fwd-prop)
        g_k^{(ℓ+1)}(x') = Σ_x T_{S,p^k}[x→x'] g_k^{(ℓ)}(x) / L^{(ℓ)}   (eq:cohort-moment-fwd)

    Initial conditions at ℓ = 0:
        π^{(0)}(x) = π_N(x)                            (newborn injection)
        g_k^{(0)}(x) = E[p_init^k] · π_N(x)             (eq:cohort-moment-init)
    where E[p_init^k] = exp(k·μ_init + ½·k²·σ_init²) for lognormal
    newborn p with `agent.pLvlInitMean = μ_init`, `agent.pLvlInitStd = σ_init`.

    Cohort weights P(K = ℓ) computed iteratively per math doc §24.6:
        P(K = ℓ+1) = L^{(ℓ)} · P(K = ℓ),  P(K = 0) inferred from sum-to-one
    For constant L_j ≡ L this reduces to the geometric (1-L)·L^ℓ.

    Stationarity cross-checks (eq:cohort-aggregate-marginal),
    (eq:cohort-aggregate-moment) verified against
    ``find_ergodic_distribution(T_P)`` and Doob outputs from
    ``compute_doob_pi_q_a`` and ``compute_doob_v2_a``.

    Parameters
    ----------
    agent : AggFiscalType (solved)
    tm_data : dict from build_tm_agg_fiscal_a (P-measure)
    K_max : int, default 2000
        Truncation of the cohort-age sum. Tail mass is approximately
        L^{K_max+1}; for L=0.99 and K_max=2000 the tail is ~10^{-9}.
    Cratio, ad_tran_shk_scale, employed_tran_shk_scale, TranShk_addition,
    interpretation : passed through to kernel builders.
    unemp_shocks : str, default 'employed' on the cohort-age-mc-init
        development branch (per user instruction 2026-04-29; see plan
        `plans/20260429-1641h_cohort-age-decomposition-mc-init.md` §1.5
        for the rationale).
        'employed' (default, testing-phase): unemployed states inherit
            the employed shock distribution. Within-cohort
            log p | (K = k) is then EXACTLY normal with parameters
            depending only on cohort age (not on j-path), making the
            2-moment lognormal fit per (k, x) cell EXACT (not an
            approximation). This modifies the model relative to
            HAFiscal production behavior — use this branch's results
            as a clean validation of the cohort-age framework, not as
            production multipliers.
        'degenerate': production-faithful — use HAFiscal's degenerate-
            shock convention for unemployed states (j ∈ {1,2,3} have
            ψ ≡ 1, ξ = const). Within-cohort log p | (K = k, X = x) is a
            mixture of lognormals over j-paths; the 2-moment lognormal
            fit per (k, x) cell is then an APPROXIMATION (averages over
            the j-path mixture).
    measure : str, default 'P'
        'P' (default, backward-compat): compute P-measure cohort decomposition only.
        'Q': also compute the Q-twisted (Harmenberg neutral measure) cohort
        decomposition per math doc §25 — adds keys `pi_Q_k`, `g1_Q_k`, `g2_Q_k`,
        `Q_wt`, `pi_Q_aggregated`, `f1_Q_aggregated`, `f2_Q_aggregated`,
        `LG_used`, `T_age_used`, `measure` to the output dict. Required for
        BUG-038's T_age-capped Q-twisted Harmenberg machinery; uses size-biased
        ψ shocks and size-biased newborn p_init moments.
    T_age : int or None, default None
        Hard cap on cohort sum (BUG-038). When not None, K_max is overridden
        by T_age - 1 (cohort sum runs τ = 0, ..., T-1). Matches the runtime
        T_age cap that force-kills agents at age T_age. When None, K_max
        controls truncation (perpetual youth).
    verify_against_doob : bool, default True
        Run the (eq:cohort-aggregate-marginal) and
        (eq:cohort-aggregate-moment) cross-checks against
        find_ergodic_distribution(T_P), compute_doob_pi_q_a, and
        compute_doob_v2_a. Recorded in the output dict.
    doob_tol : float or None
        Tolerance for cross-checks. None → max(L^{K_max+1}, 1e-10).
        Cross-check failure raises a RuntimeError.

    Returns
    -------
    dict with keys (per-cohort arrays have shape (K_max+1, A*J)):
      'pi_k'        : π^{(ℓ)}(x) — cohort-conditional (a, j) marginals
      'g1_k'        : g_1^{(ℓ)}(x) = E_P[p · 𝟙{X=x} | K = ℓ]
      'g2_k'        : g_2^{(ℓ)}(x) = E_P[p² · 𝟙{X=x} | K = ℓ]
      'cohort_wt'   : P(K = ℓ) cohort weights
      'L_avg'       : per-cohort aggregate survival rate L^{(ℓ)}
      'pi_P_aggregated' : Σ_ℓ cohort_wt[ℓ] · pi_k[ℓ]
      'f1_aggregated'   : Σ_ℓ cohort_wt[ℓ] · g1_k[ℓ]
      'f2_aggregated'   : Σ_ℓ cohort_wt[ℓ] · g2_k[ℓ]
      'mu_init', 'sigma_init', 'E_p_init_1', 'E_p_init_2' : newborn p moments
      'cross_check' : dict with verification metrics (if verify_against_doob)
    """
    if unemp_shocks not in ('degenerate', 'employed', 'perm_only'):
        raise ValueError(
            f"unemp_shocks must be 'degenerate', 'employed', or 'perm_only', "
            f"got {unemp_shocks!r}")
    if measure not in ('P', 'Q'):
        raise ValueError(
            f"measure must be 'P' or 'Q', got {measure!r}")

    # BUG-038: T_age cap overrides K_max so the cohort sum runs τ = 0..T-1
    # exactly, matching the runtime cap. See math doc §25.
    if T_age is not None:
        if T_age < 1:
            raise ValueError(f"T_age must be >= 1, got {T_age}")
        if K_max != T_age - 1 and K_max != 2000:  # 2000 is the default
            import warnings
            warnings.warn(
                f"T_age={T_age} overrides user-specified K_max={K_max}; "
                f"using K_max = T_age - 1 = {T_age - 1}.",
                RuntimeWarning, stacklevel=2)
        K_max = T_age - 1

    dist_aGrid = tm_data['dist_aGrid']
    A = len(dist_aGrid)
    MrkvArray = np.asarray(agent.MrkvArray[0], dtype=np.float64)
    J = MrkvArray.shape[0]
    N = A * J

    Splurge = float(agent.Splurge)
    Rfree_arr = np.asarray(agent.Rfree[:J], dtype=np.float64)
    PermGroFac_arr = np.asarray(agent.PermGroFac[0][:J], dtype=np.float64)
    LivPrb_arr_raw = np.asarray(agent.LivPrb[0][:J], dtype=np.float64)
    # BUG-038: when T_age is explicitly passed as kwarg, the cap is handled
    # at the cohort-sum level (truncate at K_max = T_age - 1) per math doc
    # §25. Do NOT also apply _effective_LivPrb (which is the TM-level
    # approximation) — that would double-count the cap. Only fall back to
    # _effective_LivPrb when T_age kwarg is None (legacy behavior, where
    # the cap may still be on the agent for the runtime MC).
    if T_age is not None:
        LivPrb_arr = LivPrb_arr_raw  # raw L; cap via cohort-sum truncation
    else:
        LivPrb_arr = _effective_LivPrb(
            LivPrb_arr_raw, getattr(agent, 'T_age', None))
    cFuncs = [agent.solution[0].cFunc[j] for j in range(J)]

    # Optional counterfactual: replace unemp shock distributions with
    # the employed one (diagnostic mode only; not production behavior).
    IncShkDstn_list = list(agent.IncShkDstn[0])
    if unemp_shocks == 'employed':
        for jp in range(1, J):
            IncShkDstn_list[jp] = IncShkDstn_list[0]
    elif unemp_shocks == 'perm_only':
        # Counterfactual: ψ stochastic in all states (using employed dist),
        # but ξ kept at the production unemployment income (degenerate).
        # This satisfies §24.5's "ψ iid across all states" condition exactly,
        # so the within-cohort lognormality is exact (not an approximation).
        # The MC must use the same hybrid IncShkDstn for the test to be
        # consistent — the test driver is responsible for installing it.
        from HARK.distributions import DiscreteDistribution
        employed_dist = IncShkDstn_list[0]
        psi_atoms = np.asarray(employed_dist.atoms[0], dtype=np.float64)
        xi_atoms_employed = np.asarray(employed_dist.atoms[1], dtype=np.float64)
        joint_probs = np.asarray(employed_dist.pmv, dtype=np.float64)
        # Marginalize joint employed probs over xi to get psi marginal.
        # employed_dist's atoms are stored as parallel arrays (psi_atoms[k], xi_atoms[k])
        # with joint_probs[k]. Group by unique psi_atoms and sum joint_probs to get psi marginal.
        unique_psi, inverse_idx = np.unique(psi_atoms, return_inverse=True)
        psi_marginal_probs = np.zeros_like(unique_psi)
        for k, p in enumerate(joint_probs):
            psi_marginal_probs[inverse_idx[k]] += p
        # For each unemployed state, build the hybrid (ψ_i, ξ_unemp) joint dist
        for jp in range(1, J):
            old_unemp_dist = IncShkDstn_list[jp]
            # Production unemp dist has a single atom (ξ = IncUnemp or IncUnempNoBenefits)
            xi_unemp = float(np.asarray(old_unemp_dist.atoms[1])[0])
            new_psi_atoms = unique_psi
            new_xi_atoms = np.full_like(unique_psi, xi_unemp)
            IncShkDstn_list[jp] = DiscreteDistribution(
                psi_marginal_probs.copy(),
                [new_psi_atoms.copy(), new_xi_atoms])

    # Newborn distribution and p-moments
    markov_ergodic = _solve_markov_ergodic(MrkvArray)
    pi_N = _make_newborn_dist_a(dist_aGrid, markov_ergodic)

    # Read newborn p-init parameters per AggFiscalModel.sim_birth convention
    mu_init = float(getattr(agent, 'pLvlInitMean',
                            getattr(agent, 'pLogInitMean', 0.0)))
    sigma_init = float(getattr(agent, 'pLvlInitStd',
                               getattr(agent, 'pLogInitStd', 0.0)))
    E_p_init_1 = float(np.exp(mu_init + 0.5 * sigma_init ** 2))
    E_p_init_2 = float(np.exp(2.0 * mu_init + 2.0 * sigma_init ** 2))

    # BUG-037 note: PermGroFac is used in TWO places in the kernel:
    # (i) the lottery m_next = a·R/(G·ψ) + ξ for (a, j) dynamics — this
    #     must use the actual G (not detrended), since the agent's policy
    #     c*(m) was solved with the actual G; and
    # (ii) the p^k weight per shock realization — this should use
    #      (G/PermGroFacAgg)^k for DETRENDED p moments, but using G^k for
    #      the level moments matches Doob's spsolve convention.
    # Currently kernels use G for BOTH; we POST-SCALE the cohort g_k
    # arrays below by 1/PermGroFacAgg^(k·ℓ) to convert level → detrended.
    PermGroFacAgg = float(getattr(agent, 'PermGroFacAgg', 1.0))

    # Build the three kernels
    common_args = (dist_aGrid, Splurge, cFuncs, IncShkDstn_list, MrkvArray,
                   Rfree_arr, PermGroFac_arr, LivPrb_arr)
    common_kw = dict(Cratio=Cratio,
                     ad_tran_shk_scale=ad_tran_shk_scale,
                     employed_tran_shk_scale=employed_tran_shk_scale,
                     TranShk_addition=TranShk_addition,
                     interpretation=interpretation)
    T_S = _build_survival_only_kernel_a(*common_args, **common_kw)
    T_S_p = _build_p_weighted_survival_kernel_a(*common_args, **common_kw)
    T_S_p2 = _build_p2_weighted_survival_kernel_a(*common_args, **common_kw)

    # Per-cell LivPrb_j(x) vector (broadcast L_j over a)
    LivPrb_per_cell = np.empty(N, dtype=np.float64)
    for j in range(J):
        LivPrb_per_cell[j * A:(j + 1) * A] = LivPrb_arr[j]

    # Allocate cohort-conditional arrays
    pi_k = np.zeros((K_max + 1, N), dtype=np.float64)
    g1_k = np.zeros((K_max + 1, N), dtype=np.float64)
    g2_k = np.zeros((K_max + 1, N), dtype=np.float64)
    L_avg = np.zeros(K_max + 1, dtype=np.float64)

    # Initial cohort (ℓ = 0): newborn distribution
    pi_k[0] = pi_N
    g1_k[0] = E_p_init_1 * pi_N
    g2_k[0] = E_p_init_2 * pi_N

    # Forward propagation
    for ell in range(K_max):
        L_ell = float(np.sum(LivPrb_per_cell * pi_k[ell]))
        L_avg[ell] = L_ell
        if L_ell <= 0.0:
            # No surviving mass past this cohort; remaining ages are 0
            break
        pi_k[ell + 1] = (T_S @ pi_k[ell]) / L_ell
        g1_k[ell + 1] = (T_S_p @ g1_k[ell]) / L_ell
        g2_k[ell + 1] = (T_S_p2 @ g2_k[ell]) / L_ell
    # Final L_avg[K_max] (used only for tail bookkeeping, not propagation)
    L_avg[K_max] = float(np.sum(LivPrb_per_cell * pi_k[K_max]))

    # Cohort weights: P(K = 0) = δ̄, P(K = ℓ+1) = L^{(ℓ)} · P(K = ℓ).
    # Computed via cumulative survival product, then normalized so weights
    # sum to 1 (truncation tail at K_max+1 absorbed into normalization).
    cum_surv = np.empty(K_max + 1, dtype=np.float64)
    cum_surv[0] = 1.0
    for ell in range(K_max):
        cum_surv[ell + 1] = cum_surv[ell] * L_avg[ell]
    cohort_wt = cum_surv / cum_surv.sum()

    # Aggregate to compare against TM-P / Doob
    pi_P_aggregated = (cohort_wt[:, None] * pi_k).sum(axis=0)
    f1_aggregated = (cohort_wt[:, None] * g1_k).sum(axis=0)
    f2_aggregated = (cohort_wt[:, None] * g2_k).sum(axis=0)

    # BUG-037 fix: post-scale to detrended units. The level g_k arrays
    # above represent moments under the counterfactual PlvlAgg = 1 (i.e.,
    # newborns enter at exp(μ) regardless of calendar time). The TIME-
    # INVARIANT cross-section uses DETRENDED pLvl/PlvlAgg^t; the
    # corresponding moments scale by (1/PermGroFacAgg)^(k·ℓ) per cohort
    # age ℓ. See the math derivation in math doc §24 (post-BUG-037 update).
    if abs(PermGroFacAgg - 1.0) > 1e-12:
        ell = np.arange(K_max + 1, dtype=np.float64)
        scale_g1 = PermGroFacAgg ** (-ell)        # k=1 scaling
        scale_g2 = PermGroFacAgg ** (-2.0 * ell)  # k=2 scaling
        g1_k_detrended = g1_k * scale_g1[:, None]
        g2_k_detrended = g2_k * scale_g2[:, None]
        f1_aggregated_detrended = (cohort_wt[:, None] * g1_k_detrended).sum(axis=0)
        f2_aggregated_detrended = (cohort_wt[:, None] * g2_k_detrended).sum(axis=0)
    else:
        # PermGroFacAgg = 1: detrended ≡ level
        g1_k_detrended = g1_k
        g2_k_detrended = g2_k
        f1_aggregated_detrended = f1_aggregated
        f2_aggregated_detrended = f2_aggregated

    out = {
        'pi_k': pi_k, 'g1_k': g1_k, 'g2_k': g2_k,
        'cohort_wt': cohort_wt, 'L_avg': L_avg,
        'pi_P_aggregated': pi_P_aggregated,
        'f1_aggregated': f1_aggregated,
        'f2_aggregated': f2_aggregated,
        # BUG-037 fix: detrended-pLvl quantities (recommended for MC init use)
        'g1_k_detrended': g1_k_detrended,
        'g2_k_detrended': g2_k_detrended,
        'f1_aggregated_detrended': f1_aggregated_detrended,
        'f2_aggregated_detrended': f2_aggregated_detrended,
        'PermGroFacAgg_used': PermGroFacAgg,
        'mu_init': mu_init, 'sigma_init': sigma_init,
        'E_p_init_1': E_p_init_1, 'E_p_init_2': E_p_init_2,
        'K_max': K_max,
        'T_age_used': T_age,
        'unemp_shocks': unemp_shocks,
        'measure': measure,
    }

    # BUG-038: Q-twisted Harmenberg construction per math doc §25.
    # Reuses existing P-measure kernels with index shifted by 1 per
    # (eq:cap-Q-kernel-shift): tilde T_{S,p^k} = T_{S,p^{k+1}} | P.
    if measure == 'Q':
        # Size-biased newborn moments per (eq:cap-tilde-g-init):
        #   tilde E[p_init^k] = E[p_init^{k+1}] / E[p_init]
        E_p_init_3 = float(np.exp(3.0 * mu_init + 4.5 * sigma_init ** 2))
        E_p_init_1_Q = E_p_init_2 / E_p_init_1
        E_p_init_2_Q = E_p_init_3 / E_p_init_1

        # Per-cell LG vector: L_j(x) * G_j(x). HAFiscal Baseline has uniform L
        # and uniform G under unemp_pLvl_grows_like_employed=True, so this is
        # constant (= L * G_g for the agent's group). General code below for
        # state-dependent L or G.
        LG_per_cell = np.empty(N, dtype=np.float64)
        for j in range(J):
            LG_per_cell[j * A:(j + 1) * A] = LivPrb_arr[j] * PermGroFac_arr[j]

        # Allocate Q-cohort-conditional arrays
        pi_Q_k = np.zeros((K_max + 1, N), dtype=np.float64)
        g1_Q_k = np.zeros((K_max + 1, N), dtype=np.float64)
        g2_Q_k = np.zeros((K_max + 1, N), dtype=np.float64)
        LG_avg = np.zeros(K_max + 1, dtype=np.float64)

        # Initial cohort (ℓ = 0): newborn distribution with size-biased p moments
        # per (eq:cap-tilde-g-init). Note: π_Q^{(0)}(s) = π_N(s) (newborn s
        # distribution unchanged since s_0 ⊥ p_init in HAFiscal).
        pi_Q_k[0] = pi_N
        g1_Q_k[0] = E_p_init_1_Q * pi_N
        g2_Q_k[0] = E_p_init_2_Q * pi_N

        # Forward propagation per (eq:cap-Q-kernel-shift) and §25.6.
        # Q-survivor kernel = T_S_p (P-measure first-moment kernel).
        # Q-first-moment kernel = T_S_p2 (P-measure second-moment kernel).
        # Q-second-moment kernel would need T_S_p3 (not in current code; only
        # needed for E_Q[p^2|s], which BUG-038's primary use case doesn't need).
        # For now, propagate g2_Q_k using T_S_p2 as a placeholder; flag in dict
        # that g2_Q_k is approximate (use T_S_p3 for exact second moment).
        for ell in range(K_max):
            LG_ell = float(np.sum(LG_per_cell * pi_Q_k[ell]))
            LG_avg[ell] = LG_ell
            if LG_ell <= 0.0:
                break
            pi_Q_k[ell + 1] = (T_S_p @ pi_Q_k[ell]) / LG_ell
            g1_Q_k[ell + 1] = (T_S_p2 @ g1_Q_k[ell]) / LG_ell
            # NOTE: g2_Q_k requires T_S_p3 for exact propagation per (eq:cap-Q-
            # kernel-shift) at k=2. T_S_p2 used here is a placeholder; the
            # values are NOT the true E_Q[p^2 · 1{X=x} | K=ℓ]. Flagged in
            # 'g2_Q_k_is_approximate' output key. BUG-038's primary use case
            # (replacing v_2-based π_Q computation) does NOT need g2_Q_k, so
            # this placeholder is acceptable for now.
            g2_Q_k[ell + 1] = (T_S_p2 @ g2_Q_k[ell]) / LG_ell
        LG_avg[K_max] = float(np.sum(LG_per_cell * pi_Q_k[K_max]))

        # Q-cohort weights per (eq:cap-Qtau): Q(τ) = (LG)^τ · cum normalization.
        # In HAFiscal Baseline (constant LG), this reduces to the closed-form
        # geometric (1 - LG) · (LG)^τ / (1 - (LG)^{T}) — but we compute via
        # cumulative product to handle state-dependent variations cleanly.
        cum_surv_Q = np.empty(K_max + 1, dtype=np.float64)
        cum_surv_Q[0] = 1.0
        for ell in range(K_max):
            cum_surv_Q[ell + 1] = cum_surv_Q[ell] * LG_avg[ell]
        Q_wt = cum_surv_Q / cum_surv_Q.sum()

        # Aggregate Q outputs
        pi_Q_aggregated = (Q_wt[:, None] * pi_Q_k).sum(axis=0)
        f1_Q_aggregated = (Q_wt[:, None] * g1_Q_k).sum(axis=0)
        f2_Q_aggregated = (Q_wt[:, None] * g2_Q_k).sum(axis=0)

        out.update({
            'pi_Q_k': pi_Q_k,
            'g1_Q_k': g1_Q_k,
            'g2_Q_k': g2_Q_k,
            'g2_Q_k_is_approximate': True,  # placeholder — needs T_S_p3 for exact
            'Q_wt': Q_wt,
            'LG_avg': LG_avg,
            'pi_Q_aggregated': pi_Q_aggregated,
            'f1_Q_aggregated': f1_Q_aggregated,
            'f2_Q_aggregated': f2_Q_aggregated,
            'E_p_init_1_Q': E_p_init_1_Q,
            'E_p_init_2_Q': E_p_init_2_Q,
            'LG_used': float(LivPrb_arr[0] * PermGroFac_arr[0]),  # constant in HAFiscal Baseline
        })

    # Cross-checks per math doc §24.7. Important subtlety: when
    # unemp_shocks='employed', the cohort kernels use a modified
    # IncShkDstn (unemployed states inheriting employed shocks) which is
    # a different model from `tm_data['TranMatrix']` (built from the
    # original IncShkDstn). For the cross-check to be meaningful, we
    # must build a CONSISTENT T_P with the same modification.
    if verify_against_doob:
        # Build consistent T_P matching the cohort kernels' shock structure
        T_P_consistent = _build_period_tm_a(
            dist_aGrid, Splurge, cFuncs, IncShkDstn_list, MrkvArray,
            Rfree_arr, PermGroFac_arr, LivPrb_arr, NewBornDist=pi_N,
            Cratio=Cratio, ad_tran_shk_scale=ad_tran_shk_scale,
            employed_tran_shk_scale=employed_tran_shk_scale,
            TranShk_addition=TranShk_addition, interpretation=interpretation)
        pi_P_TM = find_ergodic_distribution(T_P_consistent)

        # Truncation analysis: π_P aggregation truncates the geometric
        # series Σ_ℓ T_S^ℓ at K_max; π_Q aggregation truncates Σ_ℓ T_S,p^ℓ.
        # Since ρ(T_S,p) > ρ(T_S) (the p-weighting amplifies the spectral
        # radius by ~G·E[ψ] > 1), the f_1 series decays slower and needs
        # a looser tolerance for the same K_max. Estimate ratio of tails
        # empirically by comparing g_1^{(K_max)} vs π^{(K_max)} norms.
        if doob_tol is None:
            tail_estimate = cum_surv[K_max] / cum_surv.sum()
            doob_tol_pi = max(20.0 * tail_estimate, 1e-9)
            # f_1 series tail is ~(ρ(T_S,p) / ρ(T_S))^{K_max} times π's tail.
            # Use empirical ratio: ||g_1^{(K_max)}||_∞ / E[p_init] vs ||π^{(K_max)}||_∞.
            # Floor at K_max=0 to avoid division by zero in degenerate cases.
            ratio_g1_pi = (float(np.max(g1_k[K_max])) / E_p_init_1
                           / max(float(np.max(pi_k[K_max])), 1e-30))
            doob_tol_piQ = max(doob_tol_pi * ratio_g1_pi, 1e-7)
        else:
            doob_tol_pi = doob_tol_piQ = doob_tol

        # (eq:cohort-aggregate-marginal): pi_P_aggregated must match TM-P ergodic
        max_pi_diff = float(np.max(np.abs(pi_P_aggregated - pi_P_TM)))

        # (eq:cohort-aggregate-moment) for k=1: aggregated f1 must agree with
        # Doob's f1 UP TO THE NEWBORN-p NORMALIZATION. The Doob construction
        # in compute_doob_pi_q_a / (eq:f-linear-system) implicitly assumes
        # p_init = 1 for newborns, while the cohort framework uses the actual
        # E[p_init] = exp(μ_init + σ²_init/2). The ratio f1 / sum(f1) (i.e.,
        # π_Q^doob) is invariant to this normalization, so we cross-check
        # both the absolute scale-corrected f1 AND the π_Q^doob ratio.
        delta_bar = float(np.sum([(1.0 - LivPrb_arr[j]) * np.sum(
            ergodic_2d) for j, ergodic_2d in enumerate(pi_P_TM.reshape(J, A))]))
        I_N = sp.eye(N, format='csc')
        f1_doob_pinit1 = spla.spsolve((I_N - T_S_p).tocsc(), delta_bar * pi_N)
        # Scale Doob's f1 by E[p_init] to match cohort framework's normalization
        f1_doob = E_p_init_1 * f1_doob_pinit1
        max_f1_diff = float(np.max(np.abs(f1_aggregated - f1_doob)))

        # Also cross-check the ratio (π_Q) which is normalization-invariant
        sum_f1_cohort = float(f1_aggregated.sum())
        sum_f1_doob = float(f1_doob.sum())
        pi_Q_cohort = f1_aggregated / sum_f1_cohort if sum_f1_cohort > 0 else f1_aggregated
        pi_Q_doob = f1_doob_pinit1 / float(f1_doob_pinit1.sum())
        max_piQ_diff = float(np.max(np.abs(pi_Q_cohort - pi_Q_doob)))

        # (eq:cohort-aggregate-moment) for k=2: aggregated f2 must match
        # Doob v_2 solve via (I - T_S,p²) f_2 = δ̄ π_N (also p_init²-scaled).
        # **Caveat**: when E_P[p²] = ∞ (analytical bound L·G²·E[ψ²] ≥ 1),
        # spsolve still returns a numerical answer but it can have non-
        # physical negative values at the high-a boundary. In that case the
        # cohort-by-cohort f2_aggregated is the well-defined truncation;
        # treat the Doob v_2 cross-check as a soft warning, not a hard fail.
        f2_doob_pinit1 = spla.spsolve((I_N - T_S_p2).tocsc(), delta_bar * pi_N)
        f2_doob = E_p_init_2 * f2_doob_pinit1
        f2_doob_has_negative = bool(np.any(f2_doob_pinit1 < -1e-9))
        max_f2_diff = float(np.max(np.abs(f2_aggregated - f2_doob)))

        out['cross_check'] = {
            'max_pi_diff': max_pi_diff,
            'max_f1_diff': max_f1_diff,
            'max_piQ_diff': max_piQ_diff,
            'max_f2_diff': max_f2_diff,
            'doob_tol_pi': doob_tol_pi,
            'doob_tol_piQ': doob_tol_piQ,
            'tail_estimate': cum_surv[K_max] / cum_surv.sum(),
            'f2_doob_has_negative': f2_doob_has_negative,
            'f2_doob_min': float(f2_doob_pinit1.min()),
            'sum_f1_cohort': sum_f1_cohort,
            'sum_f1_doob': sum_f1_doob,
        }

        # Hard-fail for π and π_Q (these are well-defined under GIC
        # L·G·E[ψ] < 1 which is verified to hold for HAFiscal calibrations).
        # We use π_Q (normalization-invariant ratio) instead of f1 absolute
        # because the cohort framework uses E[p_init] in g_1^{(0)} while
        # Doob's spsolve implicitly assumes p_init=1; both produce the same
        # π_Q ratio, but f1 absolutes differ by a factor of E[p_init].
        if max_pi_diff > doob_tol_pi:
            raise RuntimeError(
                f"Cohort-age aggregation cross-check failed for pi: "
                f"max abs diff {max_pi_diff:.3e} exceeds tolerance "
                f"{doob_tol_pi:.3e}. Increase K_max (currently {K_max}) or "
                f"verify kernel build correctness.")
        if max_piQ_diff > doob_tol_piQ:
            raise RuntimeError(
                f"Cohort-age aggregation cross-check failed for pi_Q: "
                f"max abs diff {max_piQ_diff:.3e} exceeds tolerance "
                f"{doob_tol_piQ:.3e}. Increase K_max (currently {K_max}) — "
                f"f_1 series decays slower than f_pi series due to T_S,p's "
                f"larger spectral radius (need K_max ≥ "
                f"{int(np.ceil(np.log(1e-7) / np.log(0.998)))} for ~1e-7 "
                f"precision in HAFiscal HS β=0.91 calibration).")
        # f1 absolute scale is a derived check; tolerance × E[p_init] (since
        # f1 magnitudes are E[p_init] times π_P magnitudes).
        f1_tol = doob_tol_piQ * max(E_p_init_1, 1.0)
        if max_f1_diff > f1_tol:
            raise RuntimeError(
                f"Cohort-age f1 absolute scale mismatch: {max_f1_diff:.3e} "
                f"exceeds tolerance {f1_tol:.3e} (= doob_tol_piQ * E[p_init]). "
                f"This suggests the p_init scaling logic is inconsistent.")
        # Soft-warn for f2 if Doob v_2 is ill-conditioned
        if f2_doob_has_negative:
            import warnings
            warnings.warn(
                f"Doob v_2 spsolve produced negative f_2 entries (min = "
                f"{float(f2_doob_pinit1.min()):.3e}); E_P[p²] is at-or-near-"
                f"infinite for this calibration (analytical bound "
                f"L·G²·E[ψ²] ≥ 1). The cohort-by-cohort f2_aggregated "
                f"remains well-defined per finite cohort age. f2 cross-check "
                f"skipped.",
                RuntimeWarning, stacklevel=2)
        elif max_f2_diff > doob_tol_piQ:
            raise RuntimeError(
                f"Cohort-age aggregation cross-check failed for f2: "
                f"max abs diff {max_f2_diff:.3e} exceeds tolerance "
                f"{doob_tol_piQ:.3e}.")

    return out


def compute_pi_q_via_cohort_age(agent, tm_data, T_age,
                                unemp_shocks='degenerate', **kwargs):
    """
    Compute π_Q(s) analytically via cohort-age decomposition under the cap.
    Drop-in replacement for ``compute_doob_pi_q_a`` that does NOT depend on
    the heavy-tail-vulnerable v_2 fixed-point eigensolve. See math doc §25
    for derivation; (eq:cap-piQ-aggregate) for the formula.

    Parameters
    ----------
    agent : AggFiscalType (solved)
    tm_data : dict from build_tm_agg_fiscal_a (P-measure)
    T_age : int
        Hard cap (passed through to compute_cohort_age_decomposition_a;
        cohort sum truncates at K_max = T_age - 1).
    unemp_shocks : str, default 'degenerate'
        Production-faithful default — uses HAFiscal's degenerate-shock
        convention for unemployed states (matches the model that
        compute_doob_pi_q_a operates on). Use 'employed' only for the
        BUG-036 / cohort-age-mc-init counterfactual.
    **kwargs : passed to compute_cohort_age_decomposition_a (Cratio,
        ad_tran_shk_scale, employed_tran_shk_scale, TranShk_addition,
        interpretation).

    Returns
    -------
    pi_Q : (A*J,) ndarray
        Q-marginal on the (a_Nrm, j) grid, normalized to sum to 1.
    cohort_dec : dict
        Full output of compute_cohort_age_decomposition_a (measure='Q'),
        for downstream use (e.g., MC initialization or diagnostics).

    Notes
    -----
    Equivalent to ``compute_doob_pi_q_a`` in the perpetual-youth limit but
    avoids the v_2 ill-conditioning at high β. Required for BUG-038's
    T_age-capped Q-twisted Harmenberg machinery. Verified to match
    compute_doob_pi_q_a within L1 ~3e-4 at perpetual-youth limit (T_age=2000)
    when unemp_shocks='degenerate' (production-faithful).
    """
    cohort_dec = compute_cohort_age_decomposition_a(
        agent, tm_data, T_age=T_age, measure='Q',
        unemp_shocks=unemp_shocks,
        verify_against_doob=False, **kwargs)
    return cohort_dec['pi_Q_aggregated'], cohort_dec


def init_mc_from_doob_a(agent, doob_out, pi_P, dist_aGrid, N, seed,
                        p_log_std=None):
    """
    Initialize an MC agent's state so the p-weighted empirical (a, j)
    histogram matches the Doob-corrected Q-marginal at t=0 (Fix 4).

    Sampling logic (the "better" tier of Doob-init):

    1. Sample (a_i, j_i) from **π_P** (the P-marginal stationary, since each
       agent represents one physical person). NOT from π_Q — that would
       double-count heavy-p states under p-weighting.
    2. Sample p_i from a lognormal centered at w(a_i, j_i) = E_P[p | (a, j)],
       so that the p-weighted histogram has the correct conditional means.

    By construction, the empirical p-weighted histogram
       π̂_Q(x) = Σ p_i 1{(a_i,j_i)=x} / Σ p_j
    converges to π_Q^doob(x) = w(x) · π_P(x) / p̄ at t=0. This skips the
    finite-T_sim under-counting that vanilla MC suffers at high β.

    Parameters
    ----------
    agent : AggFiscalType
        Agent whose state arrays will be (re)set.
    doob_out : dict
        Output of ``compute_doob_pi_q_a`` (must contain 'w').
    pi_P : np.ndarray, shape (A*J,)
        TM-P ergodic distribution (the P-marginal of (a, j)).
    dist_aGrid : np.ndarray, shape (A,)
        Asset grid that π_P / π_Q is over.
    N : int
        Number of agents to initialize.
    seed : int
        RNG seed for reproducibility.
    p_log_std : float or None
        Log-std of the lognormal used to sample p around w(a, j). If None,
        uses ``np.sqrt(np.mean(np.asarray(agent.PermShkStd)**2))`` —
        roughly the per-period permanent-shock std. Set to 0 for a delta
        function (sample p = w(a, j) deterministically).

    Returns
    -------
    None — modifies agent.state_now in place. Caller should also set
    agent.AgentCount = N before calling agent.simulate().
    """
    pi_P = np.asarray(pi_P, dtype=float).ravel()
    w = np.asarray(doob_out['w'], dtype=float).ravel()
    A = len(dist_aGrid)
    J = len(pi_P) // A
    if len(pi_P) != A * J:
        raise ValueError(f"len(pi_P)={len(pi_P)} not equal to A*J={A*J}")

    # Sample (a, j) from pi_P, the physical-person marginal.
    rng = np.random.default_rng(seed)
    pi_P_clipped = np.maximum(pi_P, 0.0)
    pi_P_clipped /= pi_P_clipped.sum()
    flat_idx = rng.choice(len(pi_P_clipped), size=N, replace=True,
                          p=pi_P_clipped)
    j_arr = flat_idx // A
    a_idx = flat_idx % A
    a_arr = dist_aGrid[a_idx]

    # p sampled from lognormal centered at w(a, j). Where w is NaN
    # (pi_P=0 cells), fall back to overall mean of finite w values.
    w_at_pts = w[flat_idx]
    finite_mask = np.isfinite(w_at_pts) & (w_at_pts > 0)
    if not finite_mask.all():
        w_fill = float(np.nanmean(w[np.isfinite(w) & (w > 0)]))
        w_at_pts = np.where(finite_mask, w_at_pts, w_fill)

    if p_log_std is None:
        # Default: sqrt(mean PermShkStd^2). Works for HAFiscal where
        # PermShkStd is a list/array of one or more values.
        perm_std = np.asarray(agent.PermShkStd, dtype=float).ravel()
        p_log_std = float(np.sqrt(np.mean(perm_std**2)))

    if p_log_std > 0:
        # Lognormal: median = w(a,j); log-mean = log(w) - σ²/2 so that
        # E[p] = exp(log_mean + σ²/2) = w(a,j) preserves the conditional
        # mean exactly. (Standard lognormal mean-correction.)
        log_w = np.log(np.maximum(w_at_pts, 1e-30))
        log_mean = log_w - 0.5 * p_log_std**2
        p_arr = rng.lognormal(mean=log_mean, sigma=p_log_std, size=N)
    else:
        p_arr = w_at_pts.copy()

    # Write into agent's state. AggFiscalType uses MrkvNow / MrkvNowPcvd /
    # aNrm / pLvl in state_now; mirror HARK's initialize_sim() conventions.
    agent.state_now['aNrm'] = a_arr.astype(np.float64)
    agent.state_now['pLvl'] = p_arr.astype(np.float64)
    if 'MrkvNow' in agent.state_now:
        agent.state_now['MrkvNow'] = j_arr.astype(np.int64)
    if 'MrkvNowPcvd' in agent.state_now:
        agent.state_now['MrkvNowPcvd'] = j_arr.astype(np.int64)
    if hasattr(agent, 't_age'):
        agent.t_age = np.zeros(N, dtype=np.int64)
    if hasattr(agent, 't_cycle'):
        agent.t_cycle = np.zeros(N, dtype=np.int64)


def init_mc_from_cohort_age_decomposition(
        agent, cohort_dec, dist_aGrid, N, seed,
        use_detrended=True):
    """
    Initialize an MC agent's state from the cohort-age decomposition output
    per math doc §24.8 + plan `plans/20260429-1641h_cohort-age-decomposition-mc-init.md`.

    Three-step sampling per (eq:cohort-cond-dist), (eq:cohort-moment-defn),
    (eq:cohort-lognormal-fit):

    1. Cohort age K_i ~ Geometric (state-dependent if L_j varies; uses
       cohort_dec['cohort_wt'] directly), truncated at K_max.
    2. State (a_i, j_i) ~ π^{(K_i)}(·) — cohort-conditional (a, j) marginal.
    3. p_i ~ Lognormal(μ_X^{(K_i)}, σ_X^{(K_i)}) — per-cohort, per-cell
       2-moment lognormal fit:

           σ_x^{(ℓ)} = sqrt(log(1 + V_x^{(ℓ)} / M_1^{(ℓ)}(x)²))
           μ_x^{(ℓ)} = log M_1^{(ℓ)}(x) - σ_x^{(ℓ)}² / 2

       where V = M_2 - M_1², M_k = g_k / π_k.

    Compared to ``init_mc_from_doob_a`` (which uses age-INTEGRATED w(x)):
    this init samples the per-cohort lognormal *mixture* explicitly,
    eliminating the §23.6 drift mechanism that arose from collapsing the
    cohort mixture into a single lognormal.

    Parameters
    ----------
    agent : AggFiscalType
        Agent whose state arrays will be (re)set.
    cohort_dec : dict
        Output of ``compute_cohort_age_decomposition_a``.
    dist_aGrid : np.ndarray, shape (A,)
        Asset grid that pi^{(ℓ)} is over.
    N : int
        Number of agents to initialize.
    seed : int
        RNG seed for reproducibility.
    use_detrended : bool, default True
        If True (default, post-BUG-037), use the *_detrended cohort
        moment arrays — these are the time-stationary cross-section
        moments under PermGroFacAgg ≥ 1.
        If False, use the level moment arrays (pre-BUG-037 convention).

    Returns
    -------
    None — modifies agent.state_now in place. Caller should also set
    agent.AgentCount = N before calling agent.simulate().
    """
    pi_k = np.asarray(cohort_dec['pi_k'], dtype=float)
    cohort_wt = np.asarray(cohort_dec['cohort_wt'], dtype=float).ravel()
    if use_detrended:
        g1_k = np.asarray(cohort_dec['g1_k_detrended'], dtype=float)
        g2_k = np.asarray(cohort_dec['g2_k_detrended'], dtype=float)
    else:
        g1_k = np.asarray(cohort_dec['g1_k'], dtype=float)
        g2_k = np.asarray(cohort_dec['g2_k'], dtype=float)

    K_max_plus1, N_grid = pi_k.shape
    A = len(dist_aGrid)
    J = N_grid // A
    if A * J != N_grid:
        raise ValueError(f"Grid mismatch: A={A}, J={J}, A*J={A*J} ≠ N_grid={N_grid}")

    rng = np.random.default_rng(seed)

    # Step 1: sample cohort age K_i for each agent
    cohort_wt_clipped = np.maximum(cohort_wt, 0.0)
    cohort_wt_clipped /= cohort_wt_clipped.sum()
    K_arr = rng.choice(K_max_plus1, size=N, replace=True, p=cohort_wt_clipped)

    # Step 2 + 3: for each unique cohort age, batch-sample (a, j, p)
    a_arr = np.empty(N, dtype=np.float64)
    j_arr = np.empty(N, dtype=np.int64)
    p_arr = np.empty(N, dtype=np.float64)

    unique_K = np.unique(K_arr)
    for K_val in unique_K:
        mask = (K_arr == K_val)
        N_k = int(mask.sum())
        if N_k == 0:
            continue

        # Sample (a, j) from pi^{(K_val)}
        pi_at_K = pi_k[K_val]
        pi_clipped = np.maximum(pi_at_K, 0.0)
        pi_sum = pi_clipped.sum()
        if pi_sum <= 0:
            # Defensive: fallback to newborn-distribution sample
            pi_at_K = pi_k[0]
            pi_clipped = np.maximum(pi_at_K, 0.0)
            pi_sum = pi_clipped.sum()
        pi_clipped /= pi_sum
        flat_idx_k = rng.choice(N_grid, size=N_k, replace=True, p=pi_clipped)
        j_k = flat_idx_k // A
        a_idx_k = flat_idx_k % A

        # Sample p from per-cohort, per-cell lognormal
        # M_1, M_2 from g_1/g_2 / pi at the sampled cells
        M1_cells = np.where(pi_at_K[flat_idx_k] > 1e-30,
                            g1_k[K_val][flat_idx_k] / np.maximum(pi_at_K[flat_idx_k], 1e-30),
                            np.nan)
        M2_cells = np.where(pi_at_K[flat_idx_k] > 1e-30,
                            g2_k[K_val][flat_idx_k] / np.maximum(pi_at_K[flat_idx_k], 1e-30),
                            np.nan)
        # Cell-level conditional variance (Cauchy-Schwarz: clipped at 0)
        V_cells = np.maximum(M2_cells - M1_cells**2, 0.0)
        # Lognormal moment-matching per (eq:cohort-lognormal-fit)
        with np.errstate(divide='ignore', invalid='ignore'):
            ratio = V_cells / np.maximum(M1_cells**2, 1e-60)
            sigma_log_sq = np.log1p(ratio)
            sigma_log = np.sqrt(np.maximum(sigma_log_sq, 0.0))
            mu_log = np.log(np.maximum(M1_cells, 1e-30)) - 0.5 * sigma_log_sq
        # Fallback for cells where pi = 0 (M_1 = NaN): use per-cohort mean
        bad = ~np.isfinite(mu_log) | ~np.isfinite(sigma_log)
        if bad.any():
            sum_g1 = float(g1_k[K_val].sum())
            sum_pi = float(pi_clipped.sum())  # = 1 by construction
            avg_M1 = sum_g1 / max(sum_pi, 1e-30)
            mu_log_fallback = np.log(max(avg_M1, 1e-30))
            mu_log = np.where(bad, mu_log_fallback, mu_log)
            sigma_log = np.where(bad, 0.0, sigma_log)
        # Sample p: mix delta (σ=0) and lognormal cases
        delta_mask = (sigma_log < 1e-12)
        p_k = np.empty(N_k, dtype=np.float64)
        if delta_mask.any():
            p_k[delta_mask] = np.exp(mu_log[delta_mask])  # sigma=0 → p = exp(mu)
        nondelta = ~delta_mask
        if nondelta.any():
            p_k[nondelta] = rng.lognormal(
                mean=mu_log[nondelta], sigma=sigma_log[nondelta],
                size=int(nondelta.sum()))

        # Write into batch arrays
        idx_in_full = np.flatnonzero(mask)
        a_arr[idx_in_full] = dist_aGrid[a_idx_k]
        j_arr[idx_in_full] = j_k.astype(np.int64)
        p_arr[idx_in_full] = p_k

    # Write into agent's state, mirroring HARK's initialize_sim() conventions.
    agent.state_now['aNrm'] = a_arr
    agent.state_now['pLvl'] = p_arr
    if 'MrkvNow' in agent.state_now:
        agent.state_now['MrkvNow'] = j_arr
    if 'MrkvNowPcvd' in agent.state_now:
        agent.state_now['MrkvNowPcvd'] = j_arr
    # NOTE: t_age is set per-agent to the cohort age K_i (informational
    # only — HARK's mortality decision is per-period independent of t_age,
    # so this doesn't affect forward simulation, but downstream code may
    # use it to identify cohort age for diagnostics).
    if hasattr(agent, 't_age'):
        agent.t_age = K_arr.astype(np.int64)
    if hasattr(agent, 't_cycle'):
        agent.t_cycle = np.zeros(N, dtype=np.int64)


def init_mc_from_cohort_age_decomposition_qtwisted(
        agent, cohort_dec, dist_aGrid, N, seed):
    """
    Initialize an MC agent's state from the Q-twisted cohort-age decomposition
    (BUG-038, math doc §25). Sample N agents from π_Q over (s, p, τ).

    Three-step sampling:
      1. Cohort age K_i ~ Q(τ) — Q-twisted age weights, not P-weights.
      2. State (a_i, j_i) ~ π_Q^{(K_i)}(·).
      3. p_i ~ Lognormal(μ_X^Q^{(K_i)}, σ_X^Q^{(K_i)}) — per-cohort, per-cell
         2-moment lognormal fit using Q-conditional moments.

    Parameters
    ----------
    agent : AggFiscalType
    cohort_dec : dict
        Output of ``compute_cohort_age_decomposition_a`` with `measure='Q'`.
        Must contain `pi_Q_k`, `g1_Q_k`, `g2_Q_k`, `Q_wt`.
    dist_aGrid : (A,) ndarray
    N : int
    seed : int

    Returns
    -------
    None — modifies agent.state_now in place. Caller should also set
    agent.AgentCount = N before calling agent.simulate().

    Notes
    -----
    The g2_Q_k arrays are approximate (use T_S_p2 placeholder rather than
    T_S_p3; see Phase 1 docstring caveat). This affects only the per-cell
    σ in the lognormal fit; the per-cell μ (from g1_Q_k) is exact.
    Acceptable for current BUG-038 use cases. For exact second moments,
    add a T_S_p3 kernel and update Phase 1 propagation.

    For BUG-038's primary use case (replacing v_2-based π_Q computation
    in TM-a_Q machinery), this MC init is NOT needed — see
    ``compute_pi_q_via_cohort_age``. This function is for use cases
    where MC samples from π_Q are required (e.g., Harmenberg variance-
    reduction estimators).
    """
    if cohort_dec.get('measure') != 'Q':
        raise ValueError(
            "cohort_dec must come from compute_cohort_age_decomposition_a"
            "(measure='Q'). Got measure="
            f"{cohort_dec.get('measure', '<missing>')!r}.")

    pi_Q_k = np.asarray(cohort_dec['pi_Q_k'], dtype=float)
    g1_Q_k = np.asarray(cohort_dec['g1_Q_k'], dtype=float)
    g2_Q_k = np.asarray(cohort_dec['g2_Q_k'], dtype=float)
    Q_wt = np.asarray(cohort_dec['Q_wt'], dtype=float).ravel()

    K_max_plus1, N_grid = pi_Q_k.shape
    A = len(dist_aGrid)
    J = N_grid // A
    if A * J != N_grid:
        raise ValueError(
            f"Grid mismatch: A={A}, J={J}, A*J={A*J} ≠ N_grid={N_grid}")

    rng = np.random.default_rng(seed)

    # Step 1: sample cohort age K_i from Q-weights
    Q_wt_clipped = np.maximum(Q_wt, 0.0)
    Q_wt_clipped /= Q_wt_clipped.sum()
    K_arr = rng.choice(K_max_plus1, size=N, replace=True, p=Q_wt_clipped)

    a_arr = np.empty(N, dtype=np.float64)
    j_arr = np.empty(N, dtype=np.int64)
    p_arr = np.empty(N, dtype=np.float64)

    unique_K = np.unique(K_arr)
    for K_val in unique_K:
        mask = (K_arr == K_val)
        N_k = int(mask.sum())
        if N_k == 0:
            continue

        pi_at_K = pi_Q_k[K_val]
        pi_clipped = np.maximum(pi_at_K, 0.0)
        pi_sum = pi_clipped.sum()
        if pi_sum <= 0:
            pi_at_K = pi_Q_k[0]
            pi_clipped = np.maximum(pi_at_K, 0.0)
            pi_sum = pi_clipped.sum()
        pi_clipped /= pi_sum
        flat_idx_k = rng.choice(N_grid, size=N_k, replace=True, p=pi_clipped)
        j_k = flat_idx_k // A
        a_idx_k = flat_idx_k % A

        # Per-cell Q-conditional moments
        M1_cells = np.where(pi_at_K[flat_idx_k] > 1e-30,
                            g1_Q_k[K_val][flat_idx_k] / np.maximum(pi_at_K[flat_idx_k], 1e-30),
                            np.nan)
        M2_cells = np.where(pi_at_K[flat_idx_k] > 1e-30,
                            g2_Q_k[K_val][flat_idx_k] / np.maximum(pi_at_K[flat_idx_k], 1e-30),
                            np.nan)
        V_cells = np.maximum(M2_cells - M1_cells**2, 0.0)
        with np.errstate(divide='ignore', invalid='ignore'):
            ratio = V_cells / np.maximum(M1_cells**2, 1e-60)
            sigma_log_sq = np.log1p(ratio)
            sigma_log = np.sqrt(np.maximum(sigma_log_sq, 0.0))
            mu_log = np.log(np.maximum(M1_cells, 1e-30)) - 0.5 * sigma_log_sq
        bad = ~np.isfinite(mu_log) | ~np.isfinite(sigma_log)
        if bad.any():
            sum_g1 = float(g1_Q_k[K_val].sum())
            sum_pi = float(pi_clipped.sum())
            avg_M1 = sum_g1 / max(sum_pi, 1e-30)
            mu_log_fallback = np.log(max(avg_M1, 1e-30))
            mu_log = np.where(bad, mu_log_fallback, mu_log)
            sigma_log = np.where(bad, 0.0, sigma_log)
        delta_mask = (sigma_log < 1e-12)
        p_k = np.empty(N_k, dtype=np.float64)
        if delta_mask.any():
            p_k[delta_mask] = np.exp(mu_log[delta_mask])
        nondelta = ~delta_mask
        if nondelta.any():
            p_k[nondelta] = rng.lognormal(
                mean=mu_log[nondelta], sigma=sigma_log[nondelta],
                size=int(nondelta.sum()))

        idx_in_full = np.flatnonzero(mask)
        a_arr[idx_in_full] = dist_aGrid[a_idx_k]
        j_arr[idx_in_full] = j_k.astype(np.int64)
        p_arr[idx_in_full] = p_k

    agent.state_now['aNrm'] = a_arr
    agent.state_now['pLvl'] = p_arr
    if 'MrkvNow' in agent.state_now:
        agent.state_now['MrkvNow'] = j_arr
    if 'MrkvNowPcvd' in agent.state_now:
        agent.state_now['MrkvNowPcvd'] = j_arr
    if hasattr(agent, 't_age'):
        agent.t_age = K_arr.astype(np.int64)
    if hasattr(agent, 't_cycle'):
        agent.t_cycle = np.zeros(N, dtype=np.int64)


def build_tm_agg_fiscal_a(agent, aCount=200, aMin=0.0, dist_aGrid_max=None, aFac=3,
                          Cratio=1.0, neutral_measure=False,
                          interpretation=None, dist_aGrid=None, aMax=None):
    """
    a-indexed analogue of ``build_tm_agg_fiscal`` for AggFiscalType.

    Under splurge-in-budget the budget identity is a_t = m_t - c_actual(m_t, xi_t).
    Two interpretations of c_actual are supported:
      CDC (default; (eq:budget-CDC)): c_actual = (1-ς)·cFunc(m) + ς·xi
      ESC ((eq:budget-ESC)): c_actual = cFunc(m); the splurger's ς·xi consumption
        is on a separate ledger and never enters the optimizer's a_next.
    See ``BUGS_private/HAFiscal_splurge_budget_inconsistency/why_TM_a_kernel.md``
    for the state-sufficiency derivation and ``code_cheatsheet_tm_a_kernel.md``
    33.5 for the per-line implementation map.

    Returns dict with keys: TranMatrix, dist_aGrid, markov_ergodic,
    dist_aGrid_max (plus ``'aMax'``, a deprecated legacy alias key kept
    for one deprecation cycle), IncShkDstn_list, Cratio. Intentionally
    does NOT return cPol or aPol — under a-indexing there is no
    single-argument policy on a grid; aggregates are computed by
    ``compute_type_aggregates_tm_a`` which integrates over the
    post-arrival (j', xi) joint.

    HAFISCAL_DIST_TAIL_STATE (opt-in, default off = byte-identical): when on
    (scope TS-1 — baseline-ergodic + estimation read-out ONLY; requires
    Cratio=1, neutral_measure=False, ESC, uniform R/LivPrb), an analytic
    Pareto TAIL STATE T_j is appended per micro state and the TranMatrix is
    ((A+1)*J)² with layout index = j*(A+1) + i, T_j at i = A (see
    ``_build_period_tm_a_tail``). The result dict then also carries a
    ``'tail_state'`` dict (alpha, source, X, kappa, ...; or
    ``{'enabled': False, 'reason'}`` for a per-atom-disabled build). Consume
    the ergodic via ``tail_state_readout`` — the experiment/Step-5a
    propagator path refuses tail-state TMs loudly.

    Parameters
    ----------
    dist_aGrid_max : float or None, default None
        Top of the a-indexed DISTRIBUTION grid (owner ruling 2026-07-25:
        the distribution-grid top is named ``dist_aGrid_max``; the bare
        ``aMax`` spelling collided with the solve grid's ``aXtraMax``).
        None => HAFISCAL_TM_AMAX env override, else the legacy 500.0.
    aMax : float or None, default None
        DEPRECATED alias for ``dist_aGrid_max`` (one deprecation cycle,
        matching the HAFISCAL_MODE→MULTIPLIER_ENGINE precedent). Ignored
        when ``dist_aGrid_max`` is given; otherwise warns and is used.
    interpretation : str or None, default None
        Threaded through to ``_build_period_tm_a``. BUG-051 matched-pair
        guard: when None, resolved from ``get_interpretation()`` (the
        HAFISCAL_INTERPRETATION single source) — under the default/CDC env
        this yields 'CDC', preserving byte-identical behavior of all
        pre-existing call sites. When an explicit value is passed, it is
        validated against the env via ``assert_interpretation`` so a CDC
        kernel can never run silently under an ESC run (or vice versa).
    """
    # Deprecated-alias shim (owner ruling 2026-07-25): the distribution-grid
    # top is `dist_aGrid_max`; `aMax=` is accepted for one deprecation cycle.
    if aMax is not None and dist_aGrid_max is None:
        import warnings as _warnings_dep
        _warnings_dep.warn(
            "build_tm_agg_fiscal_a(aMax=...) is deprecated; pass "
            "dist_aGrid_max=... instead (owner ruling 2026-07-25: the TM "
            "distribution-grid top is dist_aGrid_max; bare aMax collided "
            "with the solve grid's aXtraMax). Behavior unchanged.",
            DeprecationWarning, stacklevel=2)
        dist_aGrid_max = aMax

    # BUG-051: resolve/validate the interpretation against the env single
    # source. None => take it from get_interpretation() (CDC by default, so
    # byte-identical to the prior hardcoded 'CDC' for unflagged/CDC runs).
    if interpretation is None:
        interpretation = get_interpretation()
    else:
        assert_interpretation(interpretation, 'build_tm_agg_fiscal_a')

    # HAFISCAL_DIST_TAIL_STATE (P4' tail state, scope TS-1: this
    # baseline-ergodic builder + the estimation read-out ONLY). Default off =
    # the untouched code path below, byte-identical. Scalar-argument guards
    # fire here, BEFORE any agent attribute is touched; the uniformity guards
    # (which need the per-state arrays) fire just after they are built.
    _tail_on = _dist_tail_state_enabled()
    if _tail_on:
        if float(Cratio) != 1.0:
            raise RuntimeError(
                f"HAFISCAL_DIST_TAIL_STATE=on requires Cratio == 1.0 "
                f"(baseline-ergodic scope TS-1; the tail outflow law is "
                f"derived at the baseline cFunc slope), got Cratio={Cratio!r}")
        if neutral_measure:
            raise RuntimeError(
                "HAFISCAL_DIST_TAIL_STATE=on requires neutral_measure=False "
                "(scope TS-1: the tail stay/landing law is derived under the "
                "standard measure)")
        if interpretation != 'ESC':
            raise RuntimeError(
                f"HAFISCAL_DIST_TAIL_STATE=on is ESC-only (scope TS-1): the "
                f"tail outflow law uses the ESC asymptotic consumption slope "
                f"(1 - kappa); the CDC blend has a different asymptotic slope "
                f"(1 - (1-varsigma)*kappa). Got interpretation="
                f"{interpretation!r}")
        # NB: a distinct os alias — later in this function `import os as _os`
        # makes `_os` function-local, so the module-level `_os` is not
        # readable here (same reason as the existing _os_amax/_os_amin).
        import os as _os_tsguard
        _tb_probe = _os_tsguard.environ.get(
            'HAFISCAL_DIST_TAIL_BUCKET', 'off').strip().lower()
        if _tb_probe not in ('off', '0', ''):
            raise RuntimeError(
                f"HAFISCAL_DIST_TAIL_STATE=on is mutually exclusive with "
                f"HAFISCAL_DIST_TAIL_BUCKET={_tb_probe!r}: both would count "
                f"the tail twice (dynamics-level tail state AND read-out "
                f"bucket). Turn one off.")

    MrkvArray = agent.MrkvArray[0]
    J = MrkvArray.shape[0]

    Rfree_arr = np.asarray(agent.Rfree[:J], dtype=np.float64)
    PermGroFac_arr = np.asarray(agent.PermGroFac[0][:J], dtype=np.float64)
    LivPrb_arr_raw = np.asarray(agent.LivPrb[0][:J], dtype=np.float64)
    T_age = getattr(agent, 'T_age', None)
    LivPrb_arr = _effective_LivPrb(LivPrb_arr_raw, T_age)

    if _tail_on:
        # Single-kappa / single-culling assumption of the tail law
        # (DERIVATION note sections 1 + 3): kappa and the split Kesten root
        # are computed from ONE (R, LivPrb) pair, so they must be uniform
        # across micro states (they are, in the production calibration).
        if not np.all(Rfree_arr == Rfree_arr[0]):
            raise RuntimeError(
                f"HAFISCAL_DIST_TAIL_STATE=on requires Rfree uniform across "
                f"micro states (single-kappa assumption), got {Rfree_arr}")
        if not np.all(LivPrb_arr_raw == LivPrb_arr_raw[0]):
            raise RuntimeError(
                f"HAFISCAL_DIST_TAIL_STATE=on requires LivPrb uniform across "
                f"micro states (single culling rate in the split Kesten "
                f"condition), got {LivPrb_arr_raw}")

    if dist_aGrid_max is None:
        # [2026-06-08] adaptive tight grid: HAFISCAL_TM_AMAX overrides the 500 default
        # (set it to the MC-simulated support * R/(G*min PermShk) for a per-parametrization
        # boundary). The 500 default below is sized for the high-beta tail and is far too
        # wide for low-beta groups (HS_Only support ~1.9), starving near-0 resolution.
        #
        # [2026-07-26] HAFISCAL_DIST_TOP_MODE (dist-grid-top scoping plan, component B —
        # plans/20260726_dist-grid-top-scoping_plan.md):
        #   'global' (DEFAULT) — today's resolution, unchanged byte-for-byte: the
        #       HAFISCAL_TM_AMAX env override, else the legacy 500.0 below. One GLOBAL
        #       top (sized offline to the GIC-cap atom; adaptive_grid_tm.
        #       production_dist_aGrid_max) for every agent.
        #   'per_atom' — resolve THIS agent's own top via adaptive_grid_tm.
        #       per_atom_dist_aGrid_max(agent): the (1-1e-4) WEALTH-weighted ergodic
        #       quantile of the atom itself (plan P2: the truncation knee is
        #       atom-specific — dropout/HS ~300-500 vs College >1300 — and wealth, not
        #       headcount, is the integrand the estimands care about). NO silent floor
        #       at the global top: per-atom means per-atom. HAFISCAL_TM_AMAX is NOT
        #       consulted in this mode (EstimParameters setdefaults it to 1300, so an
        #       env fallback would silently swallow the mode). Explicit dist_aGrid_max=
        #       callers bypass this whole block in both modes, unchanged.
        import os as _os_amax
        _dist_top_mode = _os_amax.environ.get('HAFISCAL_DIST_TOP_MODE', 'global')
        if _dist_top_mode == 'per_atom':
            import sys as _sys_amax
            import logging as _logging_amax
            _hamodels_amax = _os_amax.path.dirname(
                _os_amax.path.dirname(_os_amax.path.abspath(__file__)))
            if _hamodels_amax not in _sys_amax.path:
                _sys_amax.path.insert(0, _hamodels_amax)
            from adaptive_grid_tm import per_atom_dist_aGrid_max
            # The inner covering build passes an explicit dist_aGrid_max, so it
            # cannot re-enter this resolution (no recursion).
            dist_aGrid_max = per_atom_dist_aGrid_max(
                agent, interpretation=interpretation)
            try:
                _dfac_amax = float(np.asarray(agent.DiscFac, dtype=float).ravel()[0])
            except Exception:
                _dfac_amax = float('nan')
            _logging_amax.getLogger(__name__).debug(
                "[dist-top per_atom] DiscFac=%.6f J=%d -> dist_aGrid_max=%.1f "
                "(wealth-weighted ergodic quantile, threshold=1e-4)",
                _dfac_amax, int(MrkvArray.shape[0]), float(dist_aGrid_max))
        elif _dist_top_mode != 'global':
            raise ValueError(
                f"HAFISCAL_DIST_TOP_MODE must be 'global' or 'per_atom', got "
                f"{_dist_top_mode!r}")
        else:
            _env_amax = _os_amax.environ.get('HAFISCAL_TM_AMAX')
            if _env_amax:
                dist_aGrid_max = float(_env_amax)
    if dist_aGrid_max is None:
        # Was 50.0 before commit (next); bumped to 500.0 to remove the
        # tail-truncation bias for high-β atoms (β·Rfree near GIC). At a
        # grid top of 50 with HS β atoms ~0.99, ~38% of ergodic mass
        # concentrates at the upper grid edge → ~30% K/Y bias vs MC. At a
        # top of 500 the bias drops to <0.1%. Default aCount=200 (was 100)
        # keeps the upper grid cells from becoming too sparse with the
        # wider dist_aGrid_max. See plans/20260427-0211h_*.md and the
        # L3c.b2 diagnostic (commits 5508dde0 + 4a472687).
        dist_aGrid_max = 500.0

    # [2026-06-09] optional lower-bound override (companion to HAFISCAL_TM_AMAX).
    # Set to aNrmMin/10 from the most-impatient cohort's MC support so the SINGLE
    # global grid spans [aNrmMin/10, aNrmMax*2] across ALL cohorts/groups
    # (see Code/HA-Models/adaptive_grid_bounds.py). aMin default stays 0.0.
    import os as _os_amin
    _env_amin = _os_amin.environ.get('HAFISCAL_TM_AMIN')
    if _env_amin:
        aMin = float(_env_amin)

    # MC ⇄ TM-a Phase 3: warm-start cache (opt-in via HAFISCAL_TM_A_CACHE=1).
    # Skip the full re-build if a prior run with the same (agent config,
    # build args, HARK version, tm_methods.py commit) is on disk.
    import os as _os
    _cache_enabled = _os.environ.get('HAFISCAL_TM_A_CACHE', '0') == '1'
    # ensure-connected-TM: an externally-supplied dist_aGrid (e.g. the Alt-3 mixing grid from
    # tm_mixing_diagnostic.make_mixing_grid) is NOT described by the (aCount, aMin,
    # dist_aGrid_max, aFac) cache key, so a cached entry from a make_grid_exp_mult build would
    # be returned by mistake. Disable the cache whenever a custom grid is injected.
    if dist_aGrid is not None:
        _cache_enabled = False
    # HAFISCAL_DIST_TAIL_STATE: the _tm_a_cache cache_key does not describe
    # the tail state (an (A+1)*J matrix vs the keyed A*J build), so a stale
    # standard entry would be returned -- or a tail entry served to a
    # standard caller. Disable the warm-start cache whenever the tail is
    # active (same precedent as the custom-dist_aGrid disable above).
    if _tail_on:
        _cache_enabled = False
    _cache_key_str = None
    if _cache_enabled:
        try:
            from _tm_a_cache import cache_key, get as _cache_get
            # NOTE: _tm_a_cache.cache_key's signature FIELD keeps its legacy
            # `aMax` spelling — renaming that field would silently invalidate
            # every on-disk cache entry (out of the 2026-07-25 rename's scope).
            _cache_key_str = cache_key(
                agent, aCount=aCount, aMin=aMin, aMax=dist_aGrid_max, aFac=aFac,
                neutral_measure=neutral_measure, interpretation=interpretation,
            )
            _cached = _cache_get(_cache_key_str)
            if _cached is not None:
                # Validate shape minimally (ergodic length matches J*A)
                _A_expected = aCount
                _J = MrkvArray.shape[0]
                _expected_size = _J * _A_expected
                if (np.asarray(_cached.get('TranMatrix', np.zeros((1,1)))).shape[0]
                        == _expected_size):
                    return _cached
        except Exception as _ce:
            pass  # fall through to cold build

    _auto_grid = dist_aGrid is None
    if _auto_grid:
        dist_aGrid = make_grid_exp_mult(
            ming=aMin, maxg=dist_aGrid_max, ng=aCount, timestonest=aFac,
        )
    else:
        dist_aGrid = np.asarray(dist_aGrid, dtype=np.float64)

    sol = agent.solution[0]
    cFuncs = [sol.cFunc[j] for j in range(J)]

    IncShkDstn_list = [agent.IncShkDstn[0][jp] for jp in range(J)]

    # ensure-connected-TM grid options for the AUTO-built grid (a custom dist_aGrid= is left untouched):
    #   (1) HAFISCAL_TM_FANOUT_GRID=1 (OPT-IN): REPLACE the exp-mult grid with the top-down FAN-OUT grid
    #       built from THIS agent's own solved cFunc — step down from dist_aGrid_max by 1/s of the worst-case psi
    #       down-reach a'_lo(a) so every node has >=s accessible downward cells by construction, then
    #       hand off to a dense packing below a_handoff. aCount becomes an OUTPUT (~131 for the college
    #       cap atom at s=2/handoff=20 vs the exp-mult 200). Tunable via HAFISCAL_TM_FANOUT_S (default 2)
    #       and HAFISCAL_TM_FANOUT_HANDOFF (default 10). The fan-out grid is already connectivity-complete,
    #       so the mixing refinement is skipped.
    #       CAVEAT (2026-06-10 re-estimation gate): the default packing (handoff=10, n_lo=30) is tuned for
    #       TAIL accuracy/connectivity and UNDER-RESOLVES the low-wealth BULK — it biases bulk statistics
    #       (e.g. the college medianLWPI, which lives at a~1.1) ~3.8% low vs a 2000-node reference. The
    #       calibration target is a bulk median, so this grid is NOT a cheaper calibration grid: matching
    #       exp-mult(200)'s bulk accuracy needs n_lo~80-150 (204-274 pts, MORE than 200). Use it for
    #       TAIL-sensitive studies (upper wealth quantiles, dist_aGrid_max sizing), not the discount-factor estimation.
    #       Adoption for calibration was evaluated and REJECTED (no benefit); see
    #       conclusions_private + memory project_tm_mixing_ensure_connected.
    #   (2) else HAFISCAL_TM_MIXING_GRID=1 (DEFAULT): Alt-3 mixing refinement of the exp-mult grid —
    #       subdivide tail intervals so the local log-spacing < the discretized perm-shock log-range,
    #       guaranteeing the discretized TM MIXES. At the corrected safety=1.0 this adds 0 nodes on the
    #       production grid (a byte-identical no-op there); kept as a safety net for coarser grids.
    #       Toggle off (exact exp-mult grid): HAFISCAL_TM_MIXING_GRID=0.
    # See tm_mixing_diagnostic + plans/20260609_ensure_connected_TM_mixing.md.
    _fanout = _auto_grid and _os.environ.get('HAFISCAL_TM_FANOUT_GRID', '0') == '1'
    import warnings as _warnings
    try:
        import sys as _sys
        _hamodels = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        if _hamodels not in _sys.path:
            _sys.path.insert(0, _hamodels)
        from tm_mixing_diagnostic import (refine_grid_for_mixing, mixing_logspacing_target,
                                          make_aprime_lo, make_fanout_grid)
        _mixing_available = True
    except ImportError:
        _mixing_available = False
        # The connectivity safety net itself is missing — say so loudly rather than silently
        # building an unchecked grid (a silent pass here masks a broken install/path).
        _warnings.warn("[TM mixing] tm_mixing_diagnostic not importable — the grid connectivity "
                       "check/repair is UNAVAILABLE; building the grid unchecked.")
    if _auto_grid and _mixing_available:
        try:
            _target = mixing_logspacing_target(IncShkDstn_list)
        except ValueError:
            _target = 0.0  # no psi-mixing state (degenerate perm shock) -> xi mixes; criterion moot
        if _fanout:
            _s = float(_os.environ.get('HAFISCAL_TM_FANOUT_S', '2'))
            # handoff=10 (NOT 20): the cap-atom accuracy sweep (2026-06-10) showed handoff=20 with
            # the 30-pt packing under-resolves the low-wealth bulk (frac-below-10 off 14.7% vs a
            # 2000-node reference), while handoff=10 (154 pts) is within <=1.93% on EVERY stat
            # (E[a], median, p90, p999, mass fractions) and dominates exp-mult(200) (max 10% off).
            _hf = float(_os.environ.get('HAFISCAL_TM_FANOUT_HANDOFF', '10'))
            _aprime_lo, _ = make_aprime_lo(agent)
            dist_aGrid = make_fanout_grid(_aprime_lo, float(dist_aGrid_max), _hf, s=_s, aMin=float(aMin))
        elif _os.environ.get('HAFISCAL_TM_MIXING_GRID', '1') == '1' and _target > 0:
            _n_before = len(dist_aGrid)
            dist_aGrid, _n_added = refine_grid_for_mixing(dist_aGrid, _target)
            if _n_added:
                # Auto-repair happened: the REQUESTED grid was too coarse to mix. Tell the user —
                # a silent fix hides that their aCount under-specifies the tail (and that results
                # are computed on a larger grid than they asked for).
                _warnings.warn(
                    f"[TM mixing] requested grid (aCount={_n_before}, dist_aGrid_max={dist_aGrid_max:g}) is too coarse "
                    f"for the discretized TM to mix: tail intervals exceed the permanent-shock "
                    f"log-range {_target:.4f}, which would collapse those rows toward point masses "
                    f"(reducible/ill-conditioned ergodic). AUTO-REPAIRED by inserting {_n_added} "
                    f"geometric tail nodes -> {len(dist_aGrid)} grid points. Raise aCount (~"
                    f"{_n_before + _n_added}+) to avoid the repair, or set "
                    f"HAFISCAL_TM_MIXING_GRID=0 to disable it (NOT recommended).")
    elif (not _auto_grid) and _mixing_available:
        # Custom dist_aGrid= : never modified, but CHECK it and warn (warn-only) if it violates
        # the mixing criterion in the psi-operative region — "assumed mixing-aware" should not
        # mean "silently broken".
        try:
            _target = mixing_logspacing_target(IncShkDstn_list)
        except ValueError:
            _target = 0.0
        if _target > 0 and len(dist_aGrid) > 2:
            _lo, _hi = dist_aGrid[:-1], dist_aGrid[1:]
            _op = (_lo > 0) & (_hi < float(dist_aGrid[-1]))
            if _op.any():
                _viol = int(np.sum(np.log(_hi[_op] / _lo[_op]) > _target))
                if _viol:
                    _warnings.warn(
                        f"[TM mixing] custom dist_aGrid ({len(dist_aGrid)} pts) has {_viol} "
                        f"interior interval(s) wider than the permanent-shock log-range "
                        f"{_target:.4f} — those TM rows may collapse toward point masses. The "
                        f"custom grid is used AS GIVEN (not repaired); consider "
                        f"tm_mixing_diagnostic.refine_grid_for_mixing(grid, target).")

    markov_ergodic = _solve_markov_ergodic(MrkvArray)

    NewBornDist = _make_newborn_dist_a(dist_aGrid, markov_ergodic)

    # HAFISCAL_DIST_TAIL_STATE dispatch: resolve the atom's tail parameters
    # (the T_age-SPLIT Kesten root via per_atom_alpha; DERIVATION note
    # sections 3 + 6) and build the (A+1)*J tail-state TM when the atom
    # qualifies. A DISABLED atom (subcritical / out-of-band root) falls back
    # to the standard A*J build below; the read-out surface then verifies its
    # top-node pile is immaterial (tail_state_readout). Flag off => this
    # whole block is skipped and the call below is today's bytes.
    _tail_info = None
    if _tail_on:
        import os as _os_ts
        import sys as _sys_ts
        _hamodels_ts = _os_ts.path.dirname(
            _os_ts.path.dirname(_os_ts.path.abspath(__file__)))
        if _hamodels_ts not in _sys_ts.path:
            _sys_ts.path.insert(0, _hamodels_ts)
        from dist_tail_state import resolve_tail_alpha as _resolve_tail_alpha
        # L_eff = the value the TM ACTUALLY CULLS AT (uniform, guarded above)
        # so the split Kesten condition and the TM use the identical number.
        _tail_info = _resolve_tail_alpha(agent, L_eff=float(LivPrb_arr[0]))
        if _tail_info.get('enabled', False):
            _tail_info['X'] = float(dist_aGrid[-1])

    if _tail_info is not None and _tail_info.get('enabled', False):
        NewBornDist_tail = _make_newborn_dist_a_tail(dist_aGrid, markov_ergodic)
        TranMatrix = _build_period_tm_a_tail(
            dist_aGrid, float(agent.Splurge), cFuncs, IncShkDstn_list,
            MrkvArray, Rfree_arr, PermGroFac_arr, LivPrb_arr,
            NewBornDist_tail, _tail_info, Cratio=Cratio,
            interpretation=interpretation,
        )
    else:
        TranMatrix = _build_period_tm_a(
            dist_aGrid, float(agent.Splurge), cFuncs, IncShkDstn_list,
            MrkvArray, Rfree_arr, PermGroFac_arr, LivPrb_arr,
            NewBornDist, Cratio=Cratio, neutral_measure=neutral_measure,
            interpretation=interpretation,
        )

    _result = {
        'TranMatrix': TranMatrix,
        'dist_aGrid': dist_aGrid,
        'markov_ergodic': markov_ergodic,
        'dist_aGrid_max': dist_aGrid_max,
        'aMax': dist_aGrid_max,  # deprecated alias KEY (owner ruling 2026-07-25) — kept one cycle for downstream readers
        'IncShkDstn_list': IncShkDstn_list,
        'Cratio': Cratio,
    }
    # tail_state key ONLY when the flag is on (byte-identity of the result
    # dict on the default path): {'enabled': True, 'alpha', 'alpha_source',
    # 'X', 'kappa', 'L_eff', ...} or {'enabled': False, 'reason'}.
    if _tail_info is not None:
        _result['tail_state'] = _tail_info
    # Save to cache if enabled
    if _cache_enabled and _cache_key_str is not None:
        try:
            from _tm_a_cache import put as _cache_put
            _cache_put(_cache_key_str, _result)
        except Exception:
            pass
    return _result


def tail_state_readout(tm_data, ergodic_distr, K=None, span=None):
    """Expand a HAFISCAL_DIST_TAIL_STATE ergodic into read-out pieces.

    The ONLY sanctioned consumer surface for a tail-state ergodic (scope
    TS-1): the estimation read-out calls this instead of reshaping (J, A)
    itself. For moments only — the tail state T_j is expanded into K
    log-spaced Pareto(alpha) segments plus a closed-form terminal atom
    (``dist_tail_state.tail_readout_nodes``; exactly mean-preserving at any
    span, DERIVATION note section 5). Pooling the tail over j is
    moment-equivalent for the pooled-histogram estimands (same argument as
    the DIST_TAIL_BUCKET read-out: the estimands read only the pooled (a, w)
    histogram and a-values repeat across j).

    Parameters
    ----------
    tm_data : dict from ``build_tm_agg_fiscal_a`` — must carry the
        ``'tail_state'`` key (i.e. built with the flag on).
    ergodic_distr : the ergodic of tm_data['TranMatrix']:
        length (A+1)*J for an enabled tail, A*J for a per-atom-disabled one.
    K, span : tail read-out discretization; None => the module defaults
        (K=12, span=1000 — estimands of record are K-invariant by
        mean-exactness).

    Returns
    -------
    (erg_grid, tail_nodes, tail_weights):
      erg_grid : (J, A) ergodic over GRID nodes (tail column excluded);
      tail_nodes, tail_weights : (K+1,) read-out expansion of the pooled
        tail mass (weights sum to the pooled tail mass), or empty arrays for
        a per-atom-disabled build.

    For a DISABLED atom this verifies the §6 materiality threshold: the
    standard build's top-node pile m_top = sum_j erg[j, A-1] must be < 1e-8
    (ignored tail wealth then <= m_top·X·alpha/(alpha-1) ≈ 2.4e-5 absolute —
    0.0024% of the smallest group E[a], two orders under the tightest
    REFERENCE-1% budget). A material pile on a "no-power-tail" atom means
    the grid top sits inside the atom's BULK — a mis-sized grid, not a
    tail-law question: refuse loudly.
    """
    ts = tm_data.get('tail_state')
    if ts is None:
        raise ValueError(
            "tail_state_readout: tm_data has no 'tail_state' key — the TM "
            "was built with HAFISCAL_DIST_TAIL_STATE off; use the standard "
            "(J, A) reshape read-out for it")
    dist_aGrid = np.asarray(tm_data['dist_aGrid'])
    A = len(dist_aGrid)
    J = len(tm_data['markov_ergodic'])
    erg = np.asarray(ergodic_distr).ravel()

    if not ts.get('enabled', False):
        if erg.size != A * J:
            raise ValueError(
                f"tail_state_readout: disabled-tail ergodic must have length "
                f"A*J = {A * J}, got {erg.size}")
        erg_grid = erg.reshape(J, A)
        m_top = float(erg_grid[:, A - 1].sum())
        if m_top >= 1e-8:
            raise RuntimeError(
                f"HAFISCAL_DIST_TAIL_STATE: atom was per-atom DISABLED "
                f"({ts.get('reason', 'no reason recorded')}) yet its "
                f"standard build piles m_top={m_top:.3e} >= 1e-8 at the top "
                f"grid node — a 'no-power-tail' atom with a material pile "
                f"means dist_aGrid_max={float(dist_aGrid[-1]):.6g} sits "
                f"inside the atom's BULK (mis-sized grid, not a tail-law "
                f"question). Raise the grid top for this atom.")
        return erg_grid, np.empty(0), np.empty(0)

    if erg.size != (A + 1) * J:
        raise ValueError(
            f"tail_state_readout: tail-state ergodic must have length "
            f"(A+1)*J = {(A + 1) * J}, got {erg.size}")
    erg2 = erg.reshape(J, A + 1)
    w_T = float(erg2[:, A].sum())

    import sys as _sys_ts
    _hamodels_ts = _os.path.dirname(
        _os.path.dirname(_os.path.abspath(__file__)))
    if _hamodels_ts not in _sys_ts.path:
        _sys_ts.path.insert(0, _hamodels_ts)
    import dist_tail_state as _dts
    if K is None:
        K = _dts.READOUT_K
    if span is None:
        span = _dts.READOUT_SPAN
    tail_nodes, tail_unit_w = _dts.tail_readout_nodes(
        float(ts['alpha']), float(ts['X']), K=K, span=span)
    return erg2[:, :A], tail_nodes, w_T * tail_unit_w


def compute_type_aggregates_tm_a(agent, tm_data, ergodic_distr,
                                 neutral_measure=False,
                                 interpretation='CDC'):
    """
    a-indexed analogue of ``compute_type_aggregates_tm``.

    Aggregates over the (a, j_t) ergodic, integrating over the
    post-arrival (j_{t+1}, xi) joint. Unlike the m-indexed version,
    there is no precomputed cPol/aPol — consumption and assets are
    recovered from the kernel's integrands.

    Formulas (see ``plans/20260418-1136h_splurge-in-budget-a-indexed-TM.md`` §2):

        E[c*]           = sum_{a, j, j', xi} pi(a, j) * T_{j j'} *
                          p_{xi|j'} * c*(m', j', Cratio)
        E[c_actual]     = sum ... * [(1 - varsigma) * c*(.) + varsigma * xi]
        E[xi] per j'    = pi(j') * E_{xi|j'}[xi]
        E[a_kernel]     = sum_{a, j} pi(a, j) * a   (a is dist_aGrid value)

    Interpretation of returned A_nrm (HOUSEHOLD wealth, not raw kernel value):
        CDC: A_nrm = E[a_kernel]                — kernel a IS household a_tot,
                                                  per (eq:budget-CDC).
        ESC: A_nrm = (1-ς) * E[a_kernel]        — kernel a is per-Optimizer a_opt;
                                                  household holds (1-ς)·a_opt
                                                  (splurger holds zero), per
                                                  (eq:assets-ESC) + (eq:conv1-ESC).

    The c_actual formula `(1-ς)*c* + ς*xi` is interpretation-shared
    NUMERICALLY (under both interpretations it equals the household-total
    realized per-period consumption — CDC: weighted-average proposal;
    ESC: sum of optimizer's c*(m_opt) and splurger's ς·xi from separate
    ledgers). Same numerical value, different conceptual meaning. See
    ``BUGS_private/HAFiscal_splurge_budget_inconsistency/code_cheatsheet_tm_a_kernel.md``
    33.6 verification note.

    (No AD factor here; the baseline builder sets Cratio = 1.)

    Parameters
    ----------
    agent : AggFiscalType
    tm_data : dict, output of build_tm_agg_fiscal_a
    ergodic_distr : np.ndarray, shape (A*J,), ergodic of tm_data['TranMatrix']
    neutral_measure : bool
        If True, integrate under the Q-measure — reweight xi atoms by
        psi / E[psi] so C_splurge_nrm matches the Q-measure convention.
    interpretation : str, default 'CDC'
        Either 'CDC' or 'ESC'. Affects the A_nrm rescaling (see formula
        above). Default = 'CDC' preserves byte-identical pre-existing
        behavior. Forward-passes to nothing else (this function does not
        call _build_period_tm_a; tm_data was already built with the
        appropriate interpretation by build_tm_agg_fiscal_a).

    Returns
    -------
    dict: C_nrm, A_nrm, C_splurge_nrm, Income_nrm, state_fractions,
    E_TranShk. A_nrm is interpretation-aware; the others are not.
    """
    if interpretation not in ('CDC', 'ESC'):
        raise ValueError(
            f"interpretation must be 'CDC' or 'ESC', got: {interpretation!r}"
        )
    dist_aGrid = tm_data['dist_aGrid']
    A = len(dist_aGrid)
    MrkvArray = agent.MrkvArray[0]
    J = MrkvArray.shape[0]
    # HAFISCAL_DIST_TAIL_STATE refuse (scope TS-1): this aggregator has no
    # tail integrand — a tail-state ergodic must be consumed via
    # tail_state_readout on the estimation surface, never here. (The reshape
    # below would fail on the size anyway; make it a designed message.)
    if np.asarray(ergodic_distr).size == (A + 1) * J:
        raise RuntimeError(
            f"compute_type_aggregates_tm_a received a TAIL-STATE ergodic "
            f"(size {(A + 1) * J} = (A+1)*J — HAFISCAL_DIST_TAIL_STATE "
            f"build). Scope TS-1 restricts tail-state TMs to the "
            f"baseline-ergodic estimation read-out (tail_state_readout); "
            f"this aggregation surface is out of scope.")
    Splurge = float(agent.Splurge)
    Cratio = float(tm_data.get('Cratio', 1.0))

    IncShkDstn_list = tm_data['IncShkDstn_list']
    if neutral_measure:
        IncShkDstn_list = _to_neutral_measure(IncShkDstn_list)

    Rfree_arr = np.asarray(agent.Rfree[:J], dtype=np.float64)
    PermGroFac_arr = np.asarray(agent.PermGroFac[0][:J], dtype=np.float64)
    sol = agent.solution[0]

    # Ergodic layout: [j=0, a=0..A-1, j=1, a=0..A-1, ...] — same
    # convention as ``_build_period_tm_a``. Reshape to (J, A) for clear
    # per-state slicing.
    erg = np.asarray(ergodic_distr).reshape(J, A)
    state_fractions = erg.sum(axis=1)  # (J,)

    # E[xi] per Markov state (destination j')
    E_TranShk = np.zeros(J)
    for jp in range(J):
        d = IncShkDstn_list[jp]
        E_TranShk[jp] = np.dot(d.pmv, d.atoms[1])

    # Assets — interpretation-aware. Kernel a is household a_tot under CDC
    # and per-Optimizer a_opt under ESC; household wealth equals (1-ς)·a_opt
    # under ESC per (eq:assets-ESC) + (eq:conv1-ESC) of models_CDC_and_ESC.md.
    A_nrm_kernel = float(np.sum(erg * dist_aGrid[None, :]))
    if interpretation == 'CDC':
        A_nrm = A_nrm_kernel
    else:  # ESC
        A_nrm = (1.0 - Splurge) * A_nrm_kernel

    C_nrm = 0.0
    C_splurge_nrm = 0.0

    # Integrate over (j, j', xi). a is vectorized.
    for j in range(J):
        erg_j = erg[j, :]              # (A,)
        if erg_j.sum() <= 0.0:
            continue
        for jp in range(J):
            trans = MrkvArray[j, jp]
            if trans < 1e-15:
                continue
            dstn = IncShkDstn_list[jp]
            psi = dstn.atoms[0]        # (S,)
            xi = dstn.atoms[1]         # (S,)
            pmv = dstn.pmv             # (S,)
            S = len(pmv)

            inv_pG = 1.0 / (psi * PermGroFac_arr[jp])               # (S,)
            m_next = (Rfree_arr[jp] * dist_aGrid)[:, None] \
                * inv_pG[None, :] + xi[None, :]                     # (A, S)
            m_flat = m_next.ravel()
            c_star_flat = sol.cFunc[jp](m_flat,
                                        np.full_like(m_flat, Cratio))
            c_star = c_star_flat.reshape(A, S)                      # (A, S)
            xi_2d = np.broadcast_to(xi[None, :], (A, S))
            c_actual = (1.0 - Splurge) * c_star + Splurge * xi_2d   # (A, S)

            weights = (erg_j[:, None] * (trans * pmv[None, :]))     # (A, S)
            C_nrm += float(np.sum(weights * c_star))
            C_splurge_nrm += float(np.sum(weights * c_actual))

    # Income aggregate: weight E[xi|j'] by marginal P(j_{t+1}). Under
    # the baseline ergodic, MrkvArray @ state_fractions = state_fractions
    # (stationary), so the destination-marginal equals state_fractions.
    dest_fracs = MrkvArray.T @ state_fractions
    dest_fracs = dest_fracs / dest_fracs.sum() if dest_fracs.sum() > 0 \
        else dest_fracs
    Income_nrm = float(np.dot(dest_fracs, E_TranShk))

    return {
        'C_nrm': C_nrm,
        'A_nrm': A_nrm,
        'C_splurge_nrm': C_splurge_nrm,
        'Income_nrm': Income_nrm,
        'state_fractions': state_fractions,
        'E_TranShk': E_TranShk,
    }


def compute_period_aggregates_tm_a(dist, dist_aGrid, cFuncs, IncShkDstn_list,
                                   micro_trans, Rfree_arr, PermGroFac_arr,
                                   Splurge, Cratio=1.0, AggDemandFac=1.0,
                                   TranShk_addition=None,
                                   neutral_measure=False,
                                   interpretation='CDC',
                                   welfare_CRRA=None,
                                   _cons_cache=None, _cons_key=None):
    """
    a-indexed analogue of ``compute_period_aggregates_tm`` for the
    experiment propagator.

    Conceptually period-t aggregates. The ``dist`` is over
    (a_{t-1}, j_{t-1}) at the END of the previous period (the a-indexed
    "state"). Period-t consumption integrates over the post-arrival
    joint (j_t, psi_t, xi_t):

        m_t        = (Rfree[j_t] / (PermGroFac[j_t] * psi_t)) * a_{t-1}
                     + AggDemandFac * xi_t + TranShk_addition[j_t]
        c*         = cFuncs[j_t](m_t, Cratio)
        c_actual   = (1 - varsigma) * c* + varsigma * (effective xi_t)
        C_period  += weight * c_actual
        Y_period  += weight * (effective xi_t)

    ``effective xi_t`` = AggDemandFac * xi_t + TranShk_addition[j_t].
    Splurge applies to the effective transitory income (consistent with
    MC's ``cLvl_splurge = (1-ς) * cLvl + ς * pLvl * TranShk * ADF``).

    The c_actual formula `(1-ς)*c* + ς*xi_eff` is interpretation-shared
    NUMERICALLY: under CDC it equals (eq:total-CDC) (household-bargain
    weighted-average proposal); under ESC it equals (eq:total-ESC) (sum of
    optimizer's c* and splurger's ς·xi from separate ledgers). The
    `interpretation` parameter is currently used for input validation only;
    it does not change the numerical computation here. (The interpretation
    differs for upstream `dist` construction by `_build_period_tm_a` and
    for downstream `A_nrm` rescaling by `compute_type_aggregates_tm_a`,
    not in this function.)

    See ``BUGS_private/HAFiscal_splurge_budget_inconsistency/code_cheatsheet_tm_a_kernel.md``
    33.7 for the per-line implementation map and verification note.

    Parameters
    ----------
    dist : np.ndarray, shape (A*J,). Layout [j=0, a=0..A-1, j=1, ...].
    dist_aGrid : np.ndarray, shape (A,).
    cFuncs : list of J callables, ``cFuncs[jp](m, Cratio_arr) -> c_star``.
    IncShkDstn_list : list of J DiscreteDistributions (destination states).
    micro_trans : (J, J) row-stochastic.
    Rfree_arr, PermGroFac_arr : (J,).
    Splurge : float, varsigma.
    Cratio : float, AD consumption ratio passed as 2nd cFunc argument.
    AggDemandFac : float, scales xi atoms (AD Channel A).
    TranShk_addition : np.ndarray (J,) or None, additive transitory
        income per destination state (e.g. stimulus check).
    neutral_measure : bool, reweight xi atoms by psi / E[psi].
    interpretation : str, default 'CDC'
        'CDC' or 'ESC'. Currently used for input validation only (the
        c_actual formula is interpretation-shared per the docstring above).

    Welfare moments (added 2026-05-09): when ``welfare_CRRA`` is not None,
    additionally accumulates per-period normalized felicity and inverse-MU
    expectations, used for analytical welfare-6 computation:

        U_nrm        = E_pi(t)[u(c_actual_norm)]    where u(c) = c^(1-rho)/(1-rho)
                                                    or log(c) if rho==1
        MU_inv_nrm   = E_pi(t)[c_actual_norm^rho]   (= E[1/u'(c_actual_norm)])

    These are returned in the result dict only when welfare_CRRA is provided.
    See conclusions_private/2026-05-09_welfare6_tm_a_option_b3_math.md for the
    derivation: under CRRA, the per-agent integrand collapses such that the
    lifecycle factor pulls out as E[p_t] (Harmenberg) and the per-period
    welfare numerator factorizes (under "indep state, CRN p" approximation)
    as E[p_t] * MU_inv_base * (U_pol - U_none).

    Returns
    -------
    dict: C_nrm, C_splurge_nrm, Income_nrm, state_fracs.
        When welfare_CRRA is not None, also U_nrm, MU_inv_nrm.
    """
    if interpretation not in ('CDC', 'ESC'):
        raise ValueError(
            f"interpretation must be 'CDC' or 'ESC', got: {interpretation!r}"
        )
    # Deferred: _to_neutral_measure is ~2.3% of the run and its output is consumed
    # ONLY when a per-jp block is built. Converting lazily lets a fully cached
    # period skip it entirely.
    _nm_pending = bool(neutral_measure)
    _dstn_cell = [IncShkDstn_list]

    def _dstn_list():
        nonlocal _nm_pending
        if _nm_pending:
            _dstn_cell[0] = _to_neutral_measure(_dstn_cell[0])
            _nm_pending = False
        return _dstn_cell[0]

    A = len(dist_aGrid)
    J = micro_trans.shape[0]

    # HAFISCAL_DIST_TAIL_STATE refuse (scope TS-1): the experiment-period
    # aggregator must never see a tail-state distribution (Step-5a is
    # measured top-indifferent at 3e-5 and stays out of scope). The reshape
    # below would fail on the size anyway; make it a designed message.
    if np.asarray(dist).size == (A + 1) * J:
        raise RuntimeError(
            f"compute_period_aggregates_tm_a received a TAIL-STATE "
            f"distribution (size {(A + 1) * J} = (A+1)*J — "
            f"HAFISCAL_DIST_TAIL_STATE build). Scope TS-1 restricts "
            f"tail-state TMs to the baseline-ergodic estimation read-out; "
            f"the experiment/Step-5a propagator path is out of scope.")

    dist_2d = np.asarray(dist).reshape(J, A)
    state_fracs = dist_2d.sum(axis=1)

    if TranShk_addition is None:
        TranShk_addition = np.zeros(J)
    else:
        TranShk_addition = np.asarray(TranShk_addition, dtype=np.float64)

    C_nrm = 0.0
    C_splurge_nrm = 0.0
    Income_nrm = 0.0
    Cratio_scalar = float(Cratio)

    _do_welfare = welfare_CRRA is not None
    if _do_welfare:
        rho = float(welfare_CRRA)
        U_nrm = 0.0
        MU_inv_nrm = 0.0
        # Per-destination-state aggregates for stratified welfare:
        # at each (j_dest), accumulate population mass and consumption-related
        # moments. Used for TM-a stratified rep-agent welfare (UI).
        C_splurge_nrm_per_jp = np.zeros(J)
        Income_nrm_per_jp = np.zeros(J)
        U_nrm_per_jp = np.zeros(J)
        MU_inv_nrm_per_jp = np.zeros(J)
        state_fracs_dest = np.zeros(J)

    # SPEED (2026-07-26): the per-destination consumption block is hoisted out of
    # the origin loop, and optionally memoised across periods. Both are ALGEBRAIC
    # identities, not approximations — see the two facts below.
    #
    # FACT 1 (hoist). m_next, and hence c_star/xi/c_actual and the welfare arrays,
    # are functions of the DESTINATION state jp only: they are built from
    # dist_aGrid, Rfree_arr[jp], PermGroFac_arr[jp], IncShkDstn_list[jp] and
    # TranShk_addition[jp]. The ORIGIN state j enters solely through the scalar
    # weight d_j[a] * micro_trans[j, jp]. The old code recomputed the whole block
    # once per NON-ZERO (j, jp) pair; the micro Markov arrays have average
    # in-degree 2.0, so that was ~2x redundant. Summing the weight over j first,
    #     w_a[jp, a] = sum_j dist_2d[j, a] * micro_trans[j, jp],
    # gives weights[a, s] = w_a[jp, a] * pmv[s], identical term by term.
    #
    # FACT 2 (cross-period cache). None of the block's inputs depend on `dist`,
    # which is the only thing that varies from period to period. So for a fixed
    # (macro, emp_tc, Cratio, AggDemandFac, TranShk_addition) the block is
    # IDENTICAL across periods. The caller already memoises the transition matrix
    # on exactly that key (`tm_cache` in propagate_experiment_tm_a) — which is why
    # _build_period_tm_a costs 2.6% of the run while THIS function cost 70.8%
    # (py-spy, 2026-07-26). Passing that same key in via _cons_key/_cons_cache
    # extends the existing caching to the dominant cost.
    #
    # Zero-skip parity: the old inner loop skipped trans < 1e-15. Masking those
    # entries to 0.0 before the contraction preserves that exactly. Rows with no
    # mass are dropped as before. Float SUMMATION ORDER differs, so agreement is
    # to round-off rather than bit-identical ([[feedback_numerical_stability_acceptance_criterion]]).
    mt = np.where(micro_trans < 1e-15, 0.0, micro_trans)
    _live = dist_2d.sum(axis=1) > 0.0
    if not np.any(_live):
        w_a = np.zeros((J, A))
    else:
        w_a = mt[_live, :].T @ dist_2d[_live, :]        # (J, A)

    for jp in range(J):
        w_row = w_a[jp, :]
        if w_row.sum() <= 0.0:
            continue

        blk = None
        if _cons_cache is not None and _cons_key is not None:
            blk = _cons_cache.get((_cons_key, jp))
        if blk is None:
            dstn = _dstn_list()[jp]
            psi = dstn.atoms[0]
            xi_raw = dstn.atoms[1]
            pmv = dstn.pmv

            # Effective transitory income: AD scaling + per-state additive.
            xi_eff = AggDemandFac * xi_raw + TranShk_addition[jp]

            inv_pG = 1.0 / (psi * PermGroFac_arr[jp])
            m_next = (Rfree_arr[jp] * dist_aGrid)[:, None] \
                * inv_pG[None, :] + xi_eff[None, :]
            m_flat = m_next.ravel()
            c_star_flat = cFuncs[jp](m_flat,
                                     np.full_like(m_flat, Cratio_scalar))
            c_star = c_star_flat.reshape(A, len(pmv))
            xi_2d = np.broadcast_to(xi_eff[None, :], c_star.shape)
            c_actual = (1.0 - Splurge) * c_star + Splurge * xi_2d

            u_actual = mu_inv_actual = None
            if _do_welfare:
                c_safe = np.maximum(c_actual, 1e-16)
                if abs(rho - 1.0) < 1e-12:
                    u_actual = np.log(c_safe)
                else:
                    u_actual = c_safe ** (1.0 - rho) / (1.0 - rho)
                mu_inv_actual = c_safe ** rho

            blk = (pmv, c_star, xi_2d, c_actual, u_actual, mu_inv_actual)
            if _cons_cache is not None and _cons_key is not None:
                _cons_cache[(_cons_key, jp)] = blk

        pmv, c_star, xi_2d, c_actual, u_actual, mu_inv_actual = blk

        weights = w_row[:, None] * pmv[None, :]
        C_nrm += float(np.sum(weights * c_star))
        C_splurge_nrm += float(np.sum(weights * c_actual))
        Income_nrm += float(np.sum(weights * xi_2d))

        if _do_welfare:
            U_nrm += float(np.sum(weights * u_actual))
            MU_inv_nrm += float(np.sum(weights * mu_inv_actual))
            # Per-destination-state accumulators (stratified welfare)
            state_fracs_dest[jp] += float(np.sum(weights))
            C_splurge_nrm_per_jp[jp] += float(np.sum(weights * c_actual))
            Income_nrm_per_jp[jp] += float(np.sum(weights * xi_2d))
            U_nrm_per_jp[jp] += float(np.sum(weights * u_actual))
            MU_inv_nrm_per_jp[jp] += float(np.sum(weights * mu_inv_actual))

    result = {
        'C_nrm': C_nrm,
        'C_splurge_nrm': C_splurge_nrm,
        'Income_nrm': Income_nrm,
        'state_fracs': state_fracs,
    }
    if _do_welfare:
        result['U_nrm'] = U_nrm
        result['MU_inv_nrm'] = MU_inv_nrm
        # Per-destination-state aggregates for stratified welfare
        result['C_splurge_nrm_per_jp'] = C_splurge_nrm_per_jp
        result['Income_nrm_per_jp'] = Income_nrm_per_jp
        result['U_nrm_per_jp'] = U_nrm_per_jp
        result['MU_inv_nrm_per_jp'] = MU_inv_nrm_per_jp
        result['state_fracs_dest'] = state_fracs_dest
    return result


def build_experiment_period_tm_a(agent, macro_curr, dist_aGrid, Cratio=1.0,
                                 neutral_measure=False,
                                 TranShk_addition=None,
                                 employed_tran_shk_scale=1.0,
                                 ad_tran_shk_scale=1.0,
                                 micro_trans_override=None,
                                 cfunc_macro_override=None,
                                 interpretation='CDC'):
    """
    a-indexed experiment-period TM builder.

    Propagates state (a_{t-1}, j_{t-1}) to (a_t, j_t) for one period of
    the recession / policy experiment. In the a-indexed convention the
    period encompasses j-transition + xi draw + consumption + save, all
    under the current macro state. There is no separate macro_next
    parameter (the m-indexed split between "macro_t for cFunc" and
    "macro_next for transition + income" collapses under a-indexing).

    Parameters
    ----------
    agent : AggFiscalType (solved under the experiment Markov structure).
    macro_curr : int
        Macro state indexing cFunc, IncShkDstn, and CondMrkvArrays for
        this period. ``src_offset = dst_offset = macro_curr * J_micro``.
    dist_aGrid : np.ndarray, shape (A,).
    Cratio : float, AD consumption ratio passed as 2nd cFunc arg.
    neutral_measure : bool, Harmenberg Q reweighting.
    TranShk_addition : np.ndarray (J_micro,) or None
        Per-destination-state additive transitory income (e.g. stimulus
        check, already normalized to p_t). Added to xi after AD scaling
        — matches the m-indexed ``mNrm_shift`` convention (NOT scaled by
        ADF), which the existing experiment propagator assumes.
    employed_tran_shk_scale : float
        Multiplier on xi atoms for micro state 0 only (tax cut channel).
    ad_tran_shk_scale : float
        Multiplier on xi atoms for all micro states (AD Channel A).
    micro_trans_override : (J_micro, J_micro) or None
        If provided, overrides ``CondMrkvArrays[macro_curr]`` — used by
        the initial half-step to blend the unemployment spike into the
        period-0 Markov transition.
    cfunc_macro_override : int or None
        If provided, use this macro state for cFunc (not macro_curr).
        Supports the initial-period case where agents consumed during
        burn-in under the base macro's cFunc, even though period 0 of
        the experiment has a different macro state.
    interpretation : str, default 'CDC'
        Threaded through to ``_build_period_tm_a``. Default 'CDC'
        preserves byte-identical pre-existing behavior. See
        ``BUGS_private/HAFiscal_splurge_budget_inconsistency/code_cheatsheet_tm_a_kernel.md``
        33.8 for the per-line implementation map.

    Returns
    -------
    scipy.sparse.csc_matrix (A*J_micro, A*J_micro) — column-stochastic.
    """
    # HAFISCAL_DIST_TAIL_STATE refuse (scope TS-1): the experiment/Step-5a
    # path must never build under the tail state — Step-5a is measured
    # top-indifferent (3e-5, dist-grid-top scoping plan P2) and stays out of
    # scope. Refuse LOUDLY at entry, before any agent attribute is touched.
    if _dist_tail_state_enabled():
        raise RuntimeError(
            "build_experiment_period_tm_a: HAFISCAL_DIST_TAIL_STATE=on is "
            "out of scope for the experiment/Step-5a path (scope TS-1: "
            "baseline-ergodic TM + estimation read-out ONLY; Step-5a is "
            "measured top-indifferent at 3e-5). Unset the flag for "
            "experiment propagation.")
    J_micro = agent.num_base_MrkvStates
    src_offset = macro_curr * J_micro
    cfunc_offset = src_offset if cfunc_macro_override is None \
        else cfunc_macro_override * J_micro

    sol = agent.solution[0]
    cFuncs = [sol.cFunc[cfunc_offset + j] for j in range(J_micro)]

    IncShkDstn_list = [agent.IncShkDstn[0][src_offset + jp]
                       for jp in range(J_micro)]

    micro_trans = (agent.CondMrkvArrays[macro_curr]
                   if micro_trans_override is None
                   else micro_trans_override)

    Rfree_arr = np.asarray(agent.Rfree[:J_micro], dtype=np.float64)
    PermGroFac_arr = np.asarray(agent.PermGroFac[0][:J_micro], dtype=np.float64)
    LivPrb_arr_raw = np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64)
    T_age = getattr(agent, 'T_age', None)
    LivPrb_arr = _effective_LivPrb(LivPrb_arr_raw, T_age)

    markov_ergodic_micro = _solve_markov_ergodic(micro_trans)
    NewBornDist = _make_newborn_dist_a(dist_aGrid, markov_ergodic_micro)

    TranMatrix = _build_period_tm_a(
        dist_aGrid, float(agent.Splurge), cFuncs, IncShkDstn_list,
        micro_trans, Rfree_arr, PermGroFac_arr, LivPrb_arr,
        NewBornDist, Cratio=Cratio, neutral_measure=neutral_measure,
        ad_tran_shk_scale=ad_tran_shk_scale,
        employed_tran_shk_scale=employed_tran_shk_scale,
        TranShk_addition=TranShk_addition,
        interpretation=interpretation,
    )
    return TranMatrix, IncShkDstn_list, cFuncs


def propagate_experiment_tm_a(agent, baseline_ergodic, EconomyMrkv_init,
                              dist_aGrid, E_pLvl, Cratio=1.0, act_T=None,
                              neutral_measure=False, check_info=None,
                              shock_type=None,
                              ADelasticity=0.0, ad_timing=_HAFISCAL_TM_AD_TIMING,
                              cfunc_offset=_HAFISCAL_TM_CFUNC_OFFSET,
                              interpretation='CDC',
                              compute_welfare=False):
    """
    a-indexed analogue of ``propagate_experiment_tm``.

    Differs from the m-indexed path in three structural ways:

    1. ``baseline_ergodic`` is over (a, j_micro) — the END-of-burn-in
       distribution. No ``base_aPol`` argument is needed because the
       savings decision has already happened in the burn-in ergodic.
       The unemployment spike is blended into period-0's CondMrkvArrays
       and the TM_a for t=0 handles the full experiment period
       (j-transition + xi draw + consumption + save).
    2. Each period's TM_a (via build_experiment_period_tm_a) handles
       AD scaling and tax-cut scaling inside its kernel via
       ad_tran_shk_scale / employed_tran_shk_scale. No separate
       pre-scaled IncShkDstn_list copies.
    3. The check-period bucket aggregation follows the m-indexed
       decomposition: TM captures MPC response via TranShk_addition,
       but the splurge-on-check is aggregated separately in LEVEL
       units using the bucket's exact E_check_level_b. This preserves
       the paper's intended cov(phase_out, pLvl) accuracy.

    Signature matches propagate_experiment_tm for drop-in dispatch
    from Simulate.py (Phase 3.6), minus ``base_aPol``.

    The `interpretation` parameter is threaded through to all calls to
    `build_experiment_period_tm_a` (33.8) and `compute_period_aggregates_tm_a`
    (33.7). This function itself does not contain any interpretation-
    specific arithmetic; per cheat-sheet 33.9 the `(eq:check-level-decomp)`
    formula at the check-period decomposition is interpretation-shared by
    construction. Default 'CDC' preserves byte-identical pre-existing
    behavior for callers that do not pass the parameter. (When written, no
    caller threaded it; since then the estimation path threads it via
    get_interpretation() — BUG-051 matched-pair fix, 2026-06-05 — the
    phase2_* diagnostics pass it explicitly, and several tm_methods-internal
    sites read getattr(agent, 'interpretation', 'CDC'). The production
    Simulate.py dispatch remains interpretation-independent.)

    Welfare moments (added 2026-05-09): when ``compute_welfare=True``, also
    accumulates per-period normalized felicity and inverse-MU expectations:
    U_nrm_series[t] = E_pi(t)[u(c_actual_norm)] and MU_inv_nrm_series[t] =
    E_pi(t)[c_actual_norm^rho]. Also returns pLvl_factor_series[t] for use
    by the welfare aggregator. See conclusions_private/2026-05-09_welfare6_
    tm_a_option_b3_math.md for the analytical derivation.

    Returns
    -------
    dict with AggCons (length act_T), AggIncome (length act_T).
        When compute_welfare=True, also U_nrm_series, MU_inv_nrm_series,
        pLvl_factor_series (each length act_T) and welfare_CRRA (scalar).
    """
    if interpretation not in ('CDC', 'ESC'):
        raise ValueError(
            f"interpretation must be 'CDC' or 'ESC', got: {interpretation!r}"
        )
    # HAFISCAL_DIST_TAIL_STATE refuse (scope TS-1): the experiment/Step-5a
    # propagator must never run under the tail state (Step-5a is measured
    # top-indifferent at 3e-5). Refuse LOUDLY at entry, before any agent
    # attribute is touched; a size check on the handed-in baseline ergodic
    # below catches a tail-state artifact even with the flag since unset.
    if _dist_tail_state_enabled():
        raise RuntimeError(
            "propagate_experiment_tm_a: HAFISCAL_DIST_TAIL_STATE=on is out "
            "of scope for the experiment/Step-5a path (scope TS-1: "
            "baseline-ergodic TM + estimation read-out ONLY). Unset the "
            "flag for experiment propagation.")
    if act_T is None:
        act_T = len(EconomyMrkv_init)

    if np.isscalar(Cratio):
        Cratio_path = np.full(act_T, float(Cratio))
    else:
        Cratio_path = np.asarray(Cratio, dtype=float)

    J_micro = agent.num_base_MrkvStates
    Splurge = float(agent.Splurge)
    A_grid = len(dist_aGrid)
    # Tail-state size tripwire (fires regardless of the flag's CURRENT
    # value): a baseline ergodic of length (A+1)*J_micro can only be a
    # HAFISCAL_DIST_TAIL_STATE artifact handed across the scope boundary.
    if np.asarray(baseline_ergodic).size == (A_grid + 1) * J_micro:
        raise RuntimeError(
            f"propagate_experiment_tm_a received a TAIL-STATE baseline "
            f"ergodic (size {(A_grid + 1) * J_micro} = (A+1)*J — built under "
            f"HAFISCAL_DIST_TAIL_STATE). Scope TS-1 keeps tail-state TMs out "
            f"of the experiment/Step-5a propagator; rebuild the baseline "
            f"ergodic with the flag off.")

    _welfare_CRRA = float(agent.CRRA) if compute_welfare else None
    if compute_welfare:
        U_nrm_series = np.zeros(act_T)
        MU_inv_nrm_series = np.zeros(act_T)
        pLvl_factor_series = np.zeros(act_T)
        dist_series = []  # List of A*J arrays, one per period (pre-step state)
        # Per-destination-state series for stratified welfare
        C_splurge_per_jp_series = np.zeros((act_T, J_micro))
        Income_per_jp_series = np.zeros((act_T, J_micro))
        U_per_jp_series = np.zeros((act_T, J_micro))
        MU_inv_per_jp_series = np.zeros((act_T, J_micro))
        state_fracs_dest_series = np.zeros((act_T, J_micro))
        # Per-BUCKET welfare moments (Check periods + bucket carry).
        # Each entry is a list of dicts (one per bucket at that period).
        # For non-bucket periods, list has length 1 with whole-cohort data.
        bucket_welfare_series = [None] * act_T

    # --- Half-step: blend the unemployment spike into period-0's
    # micro Markov transition. Under a-indexing there is no separate
    # consumption step before the spike; the whole period happens in
    # the TM kernel, with the spike appearing as a row-0 modification
    # of CondMrkvArrays[initial_macro].
    initial_macro = EconomyMrkv_init[0] if len(EconomyMrkv_init) > 0 else 0
    micro_trans_init = agent.CondMrkvArrays[initial_macro].copy()
    is_recession = (initial_macro % 2 == 1)
    _uses_spike = is_recession or _mc_hit_uses_recession_urate(shock_type)
    if _uses_spike:
        Un = float(agent.Urate_normal)
        Ur = float(agent.Urate_recession) if is_recession else Un
        if Ur > Un:
            spike_frac = (Ur - Un) / (1.0 - Un)
            micro_trans_init[0, :] = (
                (1.0 - spike_frac) * agent.CondMrkvArrays[initial_macro][0, :]
                + spike_frac * agent.CondMrkvArrays[initial_macro][1, :]
            )

    # Starting distribution: the base-ergodic (end-of-burn-in). Under
    # a-indexing, no pre-consumption step is needed.
    dist = np.asarray(baseline_ergodic, dtype=np.float64).copy()

    C_series = np.zeros(act_T)
    Y_series = np.zeros(act_T)

    tm_cache = {}
    # Same key, same invariance argument: the per-destination consumption block
    # inside compute_period_aggregates_tm_a depends on (macro, emp_tc, Cratio,
    # AggDemandFac) but NOT on `dist`, so it repeats across periods exactly as the
    # TM does. The TM was cached here and this was not — worth 2.6% vs 70.8% of
    # the run (py-spy 2026-07-26). Wired only at the call sites that pass no
    # TranShk_addition; the check-bucket site varies mNrm_shift_b per bucket and
    # stays uncached.
    cons_cache = {}
    bucket_carry = None

    # pLvl_factor recurrence — same as the m-indexed propagator.
    u_ergodic = 1.0 - np.sum(baseline_ergodic[:A_grid])
    g_base_pLvl = effective_pLvl_growth(agent, u_ergodic)
    _LivPrb_eff = _effective_LivPrb(
        np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64),
        getattr(agent, 'T_age', None))
    delta_eff = 1.0 - np.mean(_LivPrb_eff)
    pLvl_factor = 1.0

    # Harmenberg neutral-measure state-frac tracking (unchanged).
    if neutral_measure:
        _std_state_fracs = np.array([
            np.sum(baseline_ergodic[j * A_grid:(j + 1) * A_grid])
            for j in range(J_micro)
        ])
    else:
        _std_state_fracs = None

    Rfree_arr = np.asarray(agent.Rfree[:J_micro], dtype=np.float64)
    PermGroFac_arr = np.asarray(agent.PermGroFac[0][:J_micro], dtype=np.float64)

    for t in range(act_T):
        macro_t = EconomyMrkv_init[t] if t < len(EconomyMrkv_init) else 0

        is_check_period = (check_info is not None and t == check_info['period'])
        emp_tc = _tax_cut_employed_factor(agent, macro_t, shock_type)

        # RecState for AD timing (matches m-indexed semantics exactly).
        # CFunc-offset: see BUGS_private/HAFiscal_BUG-041_TM_CFunc_cell_offset_one_period.md
        Cratio_t = _cratio_for_period(Cratio_path, t, cfunc_offset)
        if ad_timing == 'lagged' and t > 0:
            macro_prev = EconomyMrkv_init[t - 1] \
                if (t - 1) < len(EconomyMrkv_init) else 0
            RecState_t = float(macro_prev % 2 == 1)
        else:
            RecState_t = float(macro_t % 2 == 1)
        AggDemandFac_t = (Cratio_t ** (ADelasticity * RecState_t)
                          if ADelasticity > 0 else 1.0)

        # Resolve micro_trans for this period: spike blend only at t=0.
        micro_trans_t = (micro_trans_init if t == 0
                         else agent.CondMrkvArrays[macro_t])

        # Destination IncShkDstn for period-t aggregation — the raw
        # agent distributions; scaling / addition happens inside the
        # aggregator and builder via their parameters.
        src_offset = macro_t * J_micro
        IncShkDstn_raw = [agent.IncShkDstn[0][src_offset + j]
                          for j in range(J_micro)]
        cFuncs_t = [agent.solution[0].cFunc[src_offset + j]
                    for j in range(J_micro)]

        if is_check_period:
            # Per-bucket processing: each bucket has its own TM (built
            # with TranShk_addition = mNrm_shift for MPC capture) and
            # its own level aggregation using E_check_level_b.
            N_agent = agent.AgentCount
            C_level_agg = 0.0
            Y_level_agg = 0.0
            dist_next_agg = np.zeros_like(dist)
            bucket_dists_next = []
            t_check_U_nrm = 0.0
            t_check_MU_inv_nrm = 0.0

            # State fractions and destination marginal.
            # Under a-indexing, `dist` is over (a_{t-1}, j_{t-1}), so
            # the raw marginal is the SOURCE state distribution. The
            # m-indexed check code uses the DESTINATION state
            # distribution (post-halfstep j_t) in the splurge-base
            # decomposition — so propagate source through micro_trans_t
            # to get the destination marginal and use THAT in the
            # manual splurge_base_b / income_base_b formulas below.
            source_state_fracs = np.array([
                np.sum(dist[j * A_grid:(j + 1) * A_grid])
                for j in range(J_micro)
            ])
            # Account for mortality replacement: share (1 - LivPrb_eff)
            # dies and is replaced by newborns drawn from the Markov
            # stationary of micro_trans_t. Newborns have a=0 and
            # fractional dist that should be included in the dest
            # marginal.
            _LivPrb_src = _LivPrb_eff  # (J_micro,)
            _markov_erg = _solve_markov_ergodic(micro_trans_t)  # (J_micro,)
            _death = 1.0 - np.mean(_LivPrb_src)
            dest_state_fracs = (
                source_state_fracs * _LivPrb_src @ micro_trans_t
                + _death * _markov_erg
            )
            if dest_state_fracs.sum() > 0:
                dest_state_fracs = dest_state_fracs / dest_state_fracs.sum()
            # Base (pre-AD, pre-shift) E[xi|j_dest]
            E_TranShk_base = np.array([
                np.dot(IncShkDstn_raw[j].pmv, IncShkDstn_raw[j].atoms[1])
                for j in range(J_micro)
            ])
            # Keep the old name state_fracs for backward reference
            # in per-bucket code — it now points to DEST marginal to
            # match m-indexed semantics.
            state_fracs = dest_state_fracs

            for bucket in check_info['buckets']:
                w_b = bucket['weight']
                E_pLvl_b = bucket['E_pLvl_b']
                E_check_level_b = bucket['E_check_level_b']
                mNrm_shift_b = np.asarray(bucket['mNrm_shift'],
                                          dtype=np.float64)

                TM_b, _IncShk, _cFuncs = build_experiment_period_tm_a(
                    agent, macro_curr=macro_t, dist_aGrid=dist_aGrid,
                    Cratio=Cratio_t, neutral_measure=neutral_measure,
                    TranShk_addition=mNrm_shift_b,
                    employed_tran_shk_scale=emp_tc,
                    ad_tran_shk_scale=AggDemandFac_t,
                    micro_trans_override=micro_trans_t if t == 0 else None,
                    interpretation=interpretation,
                )

                # C_nrm_b = E[c* at (m + check)] under this bucket's TM.
                agg_b = compute_period_aggregates_tm_a(
                    dist, dist_aGrid, cFuncs_t, IncShkDstn_raw,
                    micro_trans_t, Rfree_arr, PermGroFac_arr,
                    Splurge, Cratio=Cratio_t,
                    AggDemandFac=AggDemandFac_t,
                    TranShk_addition=mNrm_shift_b,
                    neutral_measure=neutral_measure,
                    interpretation=interpretation,
                    welfare_CRRA=_welfare_CRRA,
                )
                eff_pLvl_b = E_pLvl_b * pLvl_factor

                # Decomposed level aggregation — matches m-indexed
                # propagator's check-block to keep E_check_level_b
                # exact (rather than using E_check_nrm_b · E_pLvl_b).
                nonsplurge_b = (1.0 - Splurge) * agg_b['C_nrm'] \
                    * N_agent * eff_pLvl_b
                splurge_base_b = Splurge * float(np.dot(state_fracs,
                                                        E_TranShk_base)) \
                    * AggDemandFac_t * N_agent * eff_pLvl_b
                splurge_check_b = Splurge * E_check_level_b * N_agent

                C_level_agg += w_b * (nonsplurge_b + splurge_base_b
                                      + splurge_check_b)

                income_base_b = float(np.dot(state_fracs, E_TranShk_base)) \
                    * AggDemandFac_t * N_agent * eff_pLvl_b
                income_check_b = E_check_level_b * N_agent
                Y_level_agg += w_b * (income_base_b + income_check_b)

                if compute_welfare:
                    t_check_U_nrm += w_b * agg_b['U_nrm']
                    t_check_MU_inv_nrm += w_b * agg_b['MU_inv_nrm']
                    # Save per-bucket welfare moments for this period
                    if bucket_welfare_series[t] is None:
                        bucket_welfare_series[t] = []
                    bucket_welfare_series[t].append({
                        'weight': float(w_b),
                        'E_pLvl_b': float(E_pLvl_b),
                        'E_check_level_b': float(E_check_level_b),
                        'pLvl_factor': float(pLvl_factor),
                        'U_nrm_b': float(agg_b['U_nrm']),
                        'MU_inv_nrm_b': float(agg_b['MU_inv_nrm']),
                        'C_splurge_nrm_b': float(agg_b['C_splurge_nrm']),
                        'Income_nrm_b': float(agg_b['Income_nrm']),
                    })

                dist_next_b = TM_b @ dist
                if sp.issparse(dist_next_b):
                    dist_next_b = np.asarray(dist_next_b).flatten()
                dist_next_agg += w_b * dist_next_b

                dist_b_normed = np.maximum(dist_next_b, 0.0)
                s_b = np.sum(dist_b_normed)
                if s_b > 0:
                    dist_b_normed /= s_b
                bucket_dists_next.append(dist_b_normed)

            C_series[t] = C_level_agg
            Y_series[t] = Y_level_agg
            if compute_welfare:
                U_nrm_series[t] = t_check_U_nrm
                MU_inv_nrm_series[t] = t_check_MU_inv_nrm
                pLvl_factor_series[t] = pLvl_factor
                dist_series.append(np.asarray(dist).copy())
                # Per-state aggregates during check-period: zero out for
                # simplicity (UI welfare cells don't involve check processing,
                # so this branch is irrelevant for stratified UI welfare).
                C_splurge_per_jp_series[t, :] = 0.0
                Income_per_jp_series[t, :] = 0.0
                U_per_jp_series[t, :] = 0.0
                MU_inv_per_jp_series[t, :] = 0.0
                state_fracs_dest_series[t, :] = 0.0

            bucket_carry = {
                'dists': bucket_dists_next,
                'weights': [b['weight'] for b in check_info['buckets']],
                'E_pLvl_b': [b['E_pLvl_b'] for b in check_info['buckets']],
            }

            dist = np.maximum(dist_next_agg, 0.0)
            s = np.sum(dist)
            if s > 0:
                dist /= s

            # pLvl recurrence update
            u_rec_t = 1.0 - state_fracs[0]
            g_rec_t = effective_pLvl_growth(agent, u_rec_t)
            pLvl_factor = ((1.0 - delta_eff) * g_rec_t * pLvl_factor
                           + (1.0 - (1.0 - delta_eff) * g_base_pLvl))
            if neutral_measure and _std_state_fracs is not None:
                _std_state_fracs = _propagate_state_fracs(
                    _std_state_fracs, micro_trans_t,
                    np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64),
                    getattr(agent, 'T_age', None))
            continue

        # Standard (non-check) period. Cache TM across identical calls.
        cache_key = (macro_t, emp_tc, Cratio_t, AggDemandFac_t, t == 0)
        if cache_key in tm_cache:
            TM_t = tm_cache[cache_key]
        else:
            TM_t, _IncShk, _cFuncs = build_experiment_period_tm_a(
                agent, macro_curr=macro_t, dist_aGrid=dist_aGrid,
                Cratio=Cratio_t, neutral_measure=neutral_measure,
                employed_tran_shk_scale=emp_tc,
                ad_tran_shk_scale=AggDemandFac_t,
                micro_trans_override=micro_trans_t if t == 0 else None,
                interpretation=interpretation,
            )
            tm_cache[cache_key] = TM_t

        if bucket_carry is not None:
            # Per-bucket carry: aggregate using per-bucket E_pLvl_b.
            N_agent = agent.AgentCount
            C_level_agg = 0.0
            Y_level_agg = 0.0
            t_carry_U_nrm = 0.0
            t_carry_MU_inv_nrm = 0.0

            for b_idx in range(len(bucket_carry['dists'])):
                w_b = bucket_carry['weights'][b_idx]
                E_pLvl_b = bucket_carry['E_pLvl_b'][b_idx]
                dist_b = bucket_carry['dists'][b_idx]

                agg_b = compute_period_aggregates_tm_a(
                    dist_b, dist_aGrid, cFuncs_t, IncShkDstn_raw,
                    micro_trans_t, Rfree_arr, PermGroFac_arr,
                    Splurge, Cratio=Cratio_t,
                    AggDemandFac=AggDemandFac_t,
                    neutral_measure=neutral_measure,
                    interpretation=interpretation,
                    welfare_CRRA=_welfare_CRRA,
                    _cons_cache=cons_cache, _cons_key=cache_key,
                )

                scale_b = N_agent * E_pLvl_b * pLvl_factor
                C_level_agg += w_b * scale_b * agg_b['C_splurge_nrm']
                Y_level_agg += w_b * scale_b * agg_b['Income_nrm']

                if compute_welfare:
                    t_carry_U_nrm += w_b * agg_b['U_nrm']
                    t_carry_MU_inv_nrm += w_b * agg_b['MU_inv_nrm']
                    # Save per-bucket welfare moments for this period
                    if bucket_welfare_series[t] is None:
                        bucket_welfare_series[t] = []
                    bucket_welfare_series[t].append({
                        'weight': float(w_b),
                        'E_pLvl_b': float(E_pLvl_b),
                        'pLvl_factor': float(pLvl_factor),
                        'U_nrm_b': float(agg_b['U_nrm']),
                        'MU_inv_nrm_b': float(agg_b['MU_inv_nrm']),
                        'C_splurge_nrm_b': float(agg_b['C_splurge_nrm']),
                        'Income_nrm_b': float(agg_b['Income_nrm']),
                    })

                dist_b_next = TM_t @ dist_b
                if sp.issparse(dist_b_next):
                    dist_b_next = np.asarray(dist_b_next).flatten()
                dist_b_next = np.maximum(dist_b_next, 0.0)
                s_b = np.sum(dist_b_next)
                if s_b > 0:
                    dist_b_next /= s_b
                bucket_carry['dists'][b_idx] = dist_b_next

            C_series[t] = C_level_agg
            Y_series[t] = Y_level_agg
            if compute_welfare:
                U_nrm_series[t] = t_carry_U_nrm
                MU_inv_nrm_series[t] = t_carry_MU_inv_nrm
                pLvl_factor_series[t] = pLvl_factor
                # bucket_carry has multiple distributions; save the weighted-avg
                _w_sum = sum(bucket_carry['weights'])
                if _w_sum > 0:
                    _avg = sum(bucket_carry['weights'][k] * bucket_carry['dists'][k]
                               for k in range(len(bucket_carry['dists']))) / _w_sum
                else:
                    _avg = np.asarray(dist).copy()
                dist_series.append(np.asarray(_avg).copy())
                # Per-state series during bucket-carry: aggregate per-bucket
                # per-state contributions from agg_b objects (which have the
                # per-state arrays computed via welfare_CRRA passed-through).
                # We don't have agg_b objects accessible here (they're inside
                # the per-bucket loop above), so set to zero for this period;
                # bucket-carry periods are typically t>=1 after a Check, where
                # the per-state breakdown is less critical for UI welfare.
                # (UI welfare cells don't have bucket processing.)
                C_splurge_per_jp_series[t, :] = 0.0
                Income_per_jp_series[t, :] = 0.0
                U_per_jp_series[t, :] = 0.0
                MU_inv_per_jp_series[t, :] = 0.0
                state_fracs_dest_series[t, :] = 0.0

            dist = sum(bucket_carry['weights'][i] * bucket_carry['dists'][i]
                       for i in range(len(bucket_carry['dists'])))
            dist = np.maximum(dist, 0.0)
            s = np.sum(dist)
            if s > 0:
                dist /= s

            u_rec_t = 1.0 - np.sum(dist[:A_grid])
            g_rec_t = effective_pLvl_growth(agent, u_rec_t)
            pLvl_factor = ((1.0 - delta_eff) * g_rec_t * pLvl_factor
                           + (1.0 - (1.0 - delta_eff) * g_base_pLvl))
            if neutral_measure and _std_state_fracs is not None:
                _std_state_fracs = _propagate_state_fracs(
                    _std_state_fracs, micro_trans_t,
                    np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64),
                    getattr(agent, 'T_age', None))
            continue

        # Normal period (no check, no bucket carry).
        agg_t = compute_period_aggregates_tm_a(
            dist, dist_aGrid, cFuncs_t, IncShkDstn_raw,
            micro_trans_t, Rfree_arr, PermGroFac_arr,
            Splurge, Cratio=Cratio_t,
            AggDemandFac=AggDemandFac_t,
            neutral_measure=neutral_measure,
            interpretation=interpretation,
            welfare_CRRA=_welfare_CRRA,
            _cons_cache=cons_cache, _cons_key=cache_key,
        )
        scale = agent.AgentCount * E_pLvl * pLvl_factor
        C_series[t] = scale * agg_t['C_splurge_nrm']
        Y_series[t] = scale * agg_t['Income_nrm']
        if compute_welfare:
            U_nrm_series[t] = agg_t['U_nrm']
            MU_inv_nrm_series[t] = agg_t['MU_inv_nrm']
            pLvl_factor_series[t] = pLvl_factor
            dist_series.append(np.asarray(dist).copy())
            C_splurge_per_jp_series[t, :] = agg_t['C_splurge_nrm_per_jp']
            Income_per_jp_series[t, :] = agg_t['Income_nrm_per_jp']
            U_per_jp_series[t, :] = agg_t['U_nrm_per_jp']
            MU_inv_per_jp_series[t, :] = agg_t['MU_inv_nrm_per_jp']
            state_fracs_dest_series[t, :] = agg_t['state_fracs_dest']
            # Single-bucket entry for non-Check normal periods
            bucket_welfare_series[t] = [{
                'weight': 1.0,
                'E_pLvl_b': float(E_pLvl),
                'pLvl_factor': float(pLvl_factor),
                'U_nrm_b': float(agg_t['U_nrm']),
                'MU_inv_nrm_b': float(agg_t['MU_inv_nrm']),
                'C_splurge_nrm_b': float(agg_t['C_splurge_nrm']),
                'Income_nrm_b': float(agg_t['Income_nrm']),
            }]

        dist = TM_t @ dist
        if sp.issparse(dist):
            dist = np.asarray(dist).flatten()
        dist = np.maximum(dist, 0.0)
        s = np.sum(dist)
        if s > 0:
            dist /= s

        u_rec_t = 1.0 - np.sum(dist[:A_grid])
        g_rec_t = effective_pLvl_growth(agent, u_rec_t)
        pLvl_factor = ((1.0 - delta_eff) * g_rec_t * pLvl_factor
                       + (1.0 - (1.0 - delta_eff) * g_base_pLvl))
        if neutral_measure and _std_state_fracs is not None:
            _std_state_fracs = _propagate_state_fracs(
                _std_state_fracs, micro_trans_t,
                np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64),
                getattr(agent, 'T_age', None))

    result = {'AggCons': C_series, 'AggIncome': Y_series}
    if compute_welfare:
        result['U_nrm_series'] = U_nrm_series
        result['MU_inv_nrm_series'] = MU_inv_nrm_series
        result['pLvl_factor_series'] = pLvl_factor_series
        result['dist_series'] = dist_series  # List length act_T (or shorter if some periods skipped)
        result['welfare_CRRA'] = _welfare_CRRA
        result['E_pLvl_init'] = float(E_pLvl)
        result['AgentCount'] = int(agent.AgentCount)
        # Per-state series for stratified rep-agent welfare (Path B).
        result['C_splurge_per_jp_series'] = C_splurge_per_jp_series
        result['Income_per_jp_series'] = Income_per_jp_series
        result['U_per_jp_series'] = U_per_jp_series
        result['MU_inv_per_jp_series'] = MU_inv_per_jp_series
        result['state_fracs_dest_series'] = state_fracs_dest_series
        result['J_micro'] = int(J_micro)
        # Per-BUCKET welfare moments for bucket-aware welfare (Check progressivity)
        result['bucket_welfare_series'] = bucket_welfare_series
    return result





def initialize_mc_from_tm_ergodic(agents, baseline_tm_data, mc_warmup=24,
                                  use_dual_MC=False):
    """Seed each MC agent's state from the TM(-a) ergodic distribution, then run a
    short warmup so residual mismatch settles — instead of a long cold-start burn-in.

    Extracted 2026-06-08 from the inline Simulate() block so the welfare6 pipeline can
    route its MC init through the SAME warm-start (it was cold-starting; see
    project_check_rec_aplvl_factorization). Pure refactor of the init+warmup logic
    (the env-gated POST_INIT diag print is not carried over). Both Simulate() and
    welfare6_scenario now call this.

    agents : list of AggFiscalType (one per cohort).
    baseline_tm_data : list of per-cohort TM baseline dicts (from compute_baseline_tm_data).
    """
    import os
    import numpy as np
    from income_process_sst import (effective_pLvl_growth,
                                     effective_perm_shock_periods_for_t_age)
    # pLvl seeding method — see HAFISCAL_MC_PLVL_INIT in docs/ENV_FLAGS.md and
    # the matching branch in Simulate.py (kept in sync deliberately).
    mc_plvl_init = os.environ.get(
        'HAFISCAL_MC_PLVL_INIT', 'analytic_markov').strip().lower()
    if mc_plvl_init not in ('analytic_markov', 'analytic_markov_conditional',
                            'analytic_employed', 'legacy_synthetic'):
        raise ValueError(
            f"HAFISCAL_MC_PLVL_INIT={mc_plvl_init!r} invalid; expected "
            "'analytic_markov', 'analytic_markov_conditional', "
            "'analytic_employed', or 'legacy_synthetic'.")
    for i, agent in enumerate(agents):
        bd_i = baseline_tm_data[i]
        tm_a_init = bd_i.get('tm_a_indexed', False)
        if tm_a_init:
            # TM-a path: sample (j, aNrm) DIRECTLY from the a-indexed ergodic.
            erg = bd_i['ergodic']
            grid = bd_i['dist_aGrid']
            A_i = len(grid)
            rng_i = np.random.RandomState(agent.seed)
            N_i = agent.AgentCount
            flat_probs = np.asarray(erg) / np.sum(erg)
            bins = rng_i.choice(len(flat_probs), size=N_i, p=flat_probs)
            agent_j = bins // A_i
            agent_aNrm = grid[bins % A_i]
        else:
            # TM-m path: sample (j, mNrm), invert via base cFunc to aNrm.
            erg = bd_i.get('cohort_ergodic')
            if erg is None:
                erg = bd_i['ergodic']
            grid = bd_i['dist_mGrid']
            M_i = len(grid)
            J_i = agent.num_base_MrkvStates
            rng_i = np.random.RandomState(agent.seed)
            N_i = agent.AgentCount
            flat_probs = erg / np.sum(erg)
            bins = rng_i.choice(len(flat_probs), size=N_i, p=flat_probs)
            agent_j = bins // M_i
            agent_mNrm = grid[bins % M_i]
            sol_i = agent.solution[0]
            agent_aNrm = np.zeros(N_i)
            for j in range(J_i):
                mask = agent_j == j
                if np.any(mask):
                    c = sol_i.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
                    agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)

        # Ages from the ergodic age distribution. Under the belief-consistent
        # uncapped world (T_age=None, the 2026-07-27 epoch) the geometric age
        # chain is tolerance-truncated exactly like the five sites above —
        # this sixth site was missed by the epoch sweep and crashed the first
        # post-epoch welfare run (BUG-054 integration overnight).
        L = agent.LivPrb[0][0]
        T_ag = effective_age_chain_length(L, getattr(agent, 'T_age', 400))
        age_probs = np.array([L ** (k - 1) for k in range(1, T_ag + 1)])
        age_probs /= np.sum(age_probs)
        agent_ages = rng_i.choice(T_ag, size=N_i, p=age_probs) + 1

        # Seed the pLvl marginal at (an approximation to) its steady state.
        # (agent_ages above is still used below for t_age.)
        if mc_plvl_init == 'analytic_markov_conditional':
            # CONDITIONAL on (age, state): each agent's pLvl drawn from its own
            # (age, base-Mrkv-state) cell of the exact Markov recursion, so pLvl
            # is correlated with age + employment state at init (kills the
            # var(log p) warmup overshoot the pooled marginal produces). Still
            # pLvl ⊥ aNrm within a state (the within-state a–p joint = TM-ap).
            agent_pLvl = sample_pLvl_conditional_markov(
                agent, agent_ages, agent_j, rng_i)
        elif mc_plvl_init == 'analytic_markov':
            # UNEMPLOYMENT-AWARE analytic ergodic mixture: per-(age,state)
            # Gaussian mixture from the exact Markov recursion (reproduces
            # compute_log_p_moments_exact). N stratified representative pLvl
            # values, permuted across agents (pLvl ⊥ aNrm).
            agent_pLvl = sample_pLvl_steady_state(
                agent, N_i, rng_i, pLvl_dist='markov', method='stratified')
        elif mc_plvl_init == 'analytic_employed':
            # EMPLOYED-ONLY analytic ergodic mixture: N stratified representative
            # pLvl values, permuted across agents so they attach independently
            # of the (j, aNrm) draw (pLvl ⊥ aNrm).
            agent_pLvl = sample_pLvl_steady_state(
                agent, N_i, rng_i, employed_only=True, method='stratified')
        else:
            # legacy_synthetic: older unemployment-folded per-age random draw
            # (bit-identical to pre-2026-06-13 behavior). Perm-shock variance
            # only in employed periods.
            u_p = unemployment_rate_for_tm_synthetic_pLvl(bd_i, agent)
            g_lvl = effective_pLvl_growth(agent, u_p)
            pLogMean = agent.pLogInitMean
            pLogStd = getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0))
            PermShkDstn_0 = agent.IncShkDstn_base[0][0]
            log_ps = np.log(PermShkDstn_0.atoms[0])
            ps_var = (np.dot(PermShkDstn_0.pmv, log_ps ** 2)
                      - np.dot(PermShkDstn_0.pmv, log_ps) ** 2)
            effective_emp_periods = effective_perm_shock_periods_for_t_age(
                agent_ages, agent, u_p)
            log_pLvl = rng_i.normal(pLogMean, pLogStd, N_i)
            log_pLvl += agent_ages * np.log(g_lvl)
            log_pLvl += effective_emp_periods * (-ps_var / 2.0)
            log_pLvl += rng_i.normal(0, np.sqrt(ps_var * effective_emp_periods))
            agent_pLvl = np.exp(log_pLvl)

        # Inject into agent state.
        agent.state_now['aNrm'][:] = agent_aNrm
        agent.state_now['pLvl'][:] = agent_pLvl
        if 'aLvl' in agent.state_now:
            agent.state_now['aLvl'][:] = agent_aNrm * agent_pLvl
        agent.shocks['Mrkv'][:] = agent_j
        if hasattr(agent, 't_age') and agent.t_age is not None:
            agent.t_age[:] = agent_ages
        agent.Cratio = 1.0
        agent.state_now['PlvlAgg'] = 1.0

        if use_dual_MC and hasattr(agent, 'state_now_Q'):
            for k, v in agent.state_now.items():
                if isinstance(v, np.ndarray):
                    agent.state_now_Q[k] = v.copy()
                else:
                    agent.state_now_Q[k] = v

    # Short warmup to let residual distributional mismatch settle.
    for _t in range(mc_warmup):
        for agent in agents:
            agent.sim_one_period()
