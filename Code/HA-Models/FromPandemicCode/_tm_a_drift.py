"""MC ⇄ TM-a drift measurement.

Per plan 20260503-1437h_mc_tma_companion_and_drift.md Phase 2.

When MC is initialized at TM-a's ergodic distribution and simulated forward,
no systematic drift should appear in the cross-section moments. This module
computes:

  - mean log(aNrm)         — drift threshold: |Δ| < 0.03 (absolute on log scale)
  - var log(aNrm)          — drift threshold: |Δ|/var_TMa < 0.03 (relative)
  - Lorenz shares of aNrm  — PRIMARY metric, threshold 3pp (constraint-robust)
  - mean/var log(pLvl)     — N-AWARE statistical band (see below), not a fixed 0.03

Asymmetric thresholds: mean is a level (absolute log-diff = ~3% multiplicative);
variances are scale parameters (relative makes more sense).

pLvl-moment drift is N-AWARE (calibrated 2026-06-13): log(pLvl) is a near-unit-
root random walk weakly mean-reverted by mortality, so the cross-sectional
mean/var of a FINITE MC panel are themselves random and wander. Under CORRECT
calibration the pLvl drift is therefore not 0 but ~ Normal(center, (scale/√N)²);
the gate accepts ``|drift − center| ≤ z·scale/√N`` (default z=3.090 ⇒ ≈0.2%
false-fail), so it tolerates finite-population noise but still fires on real
miscalibration. The raw drift value is ALWAYS printed (not just pass/fail), so
subtle drift stays visible in logs even though the abort band is conservative.
See the _PLVL_DRIFT_* constants and
conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md (§14).

For each (cohort, β-atom) sub-population, drift is measured independently;
also reported at the cohort-aggregate and population-aggregate levels.

Failure mode (per user direction 2026-05-03): HARD-FAIL when drift exceeds
threshold. Opt-out via env var HAFISCAL_DRIFT_HARD_FAIL=0 (downgrades to
WARNING). Threshold itself overridable via HAFISCAL_DRIFT_THRESHOLD; pLvl band
via HAFISCAL_DRIFT_PLVL_NAWARE (0=legacy fixed) and HAFISCAL_DRIFT_PLVL_Z.

Public API:
  compute_tma_analytical_moments(ergodic_dict, agent) → dict
  compute_mc_empirical_moments(agent) → dict
  measure_drift(tma_moments, mc_moments) → dict (includes pass/fail per metric)
  assess_and_report(drift, threshold, hard_fail) → bool (True=pass; raises if hard_fail)
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np


_DEFAULT_THRESHOLD = 0.03   # 3% — see asymmetric interpretation in module docstring
_TINY = 1e-12               # log-floor for zero-asset agents

# ---------------------------------------------------------------------------
# N-aware acceptance band for pLvl-moment drift (calibrated 2026-06-13).
#
# log(pLvl) is a near-unit-root random walk weakly mean-reverted by mortality
# (LivPrb≈0.99 → ~100-period reversion timescale), so the CROSS-SECTIONAL
# mean/var of a FINITE MC panel are themselves slowly-autocorrelated random
# variables that wander. Under CORRECT calibration the pLvl-moment drift
# (MC@warmup minus the analytic ergodic) is therefore not zero but
#     drift ~ Normal( center , (scale / sqrt(N))^2 )
# where  center  is the systematic warmup-transient overshoot (≈N-independent:
# the pooled analytic_markov seed attaches pLvl independently of (age,state);
# a finite warmup re-correlates them, transiently overshooting), and
# scale/sqrt(N)  is finite-population sampling noise (1/sqrt(N) confirmed —
# sd·sqrt(N) is constant across N).
#
# Calibrated from 50 RNG seeds × N∈{1500,3000,6000} (HS_Only, warmup=24, the
# production default). The var-drift scale 1.225 ≈ √2·0.87, close to the
# Gaussian relative-variance law √(2/N). Empirical exceedance of the z=2.576
# band was 0/50 at every N during calibration; the production default was then
# widened to z=3.090 (≈0.2% false-fail) per owner direction 2026-06-13,
# while a genuine miscalibration drives drift far outside center±band and still
# fails. NOTE: ``center`` is mildly cohort-dependent (it scales with how
# strongly pLvl varies with age/state); validated to also pass dropout+college
# in a full Reduced_Run. Re-derive (e.g. if warmup or seed method changes) per
# conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md (§14).
_PLVL_DRIFT_NAWARE = True          # HAFISCAL_DRIFT_PLVL_NAWARE=0 → legacy fixed thr
_PLVL_MEAN_DRIFT_CENTER = 0.0235   # systematic mean log(p) drift (abs)
_PLVL_MEAN_DRIFT_SCALE = 0.349     # sd(mean-drift) · sqrt(N)
_PLVL_VAR_DRIFT_CENTER = 0.073     # systematic var log(p) drift (rel)
_PLVL_VAR_DRIFT_SCALE = 1.225      # sd(var-drift) · sqrt(N)
_PLVL_DRIFT_Z = 3.090              # 0.2% two-sided critical value (P[false-fail]≈0.2%)


def _pLvl_drift_band(center: float, scale: float, N: int, z: float) -> tuple[float, float]:
    """N-aware acceptance band ``center ± z·scale/√N`` for a pLvl-moment drift."""
    half = z * scale / np.sqrt(max(int(N), 1))
    return center - half, center + half


def _safe_log(x: np.ndarray, floor: float = _TINY) -> np.ndarray:
    """log(x) with mass at x≈0 floored to log(floor). Treats 0 as floor.

    Both TM-a and MC will have some agents with aNrm≈0 (borrowing-constraint
    binding). Without the floor, log(0) = -inf produces NaN in the mean/var.
    """
    x = np.asarray(x, dtype=np.float64)
    return np.log(np.where(x > floor, x, floor))


def _percentile_from_distribution(grid: np.ndarray, weights: np.ndarray, q: float) -> float:
    """Inverse CDF: smallest grid value with cumulative weight >= q."""
    cdf = np.cumsum(weights)
    idx = np.searchsorted(cdf, q)
    idx = min(idx, len(grid) - 1)
    return float(grid[idx])


# Standard Lorenz percentile cutoffs — match the Step-2 targets convention
# (data_LorenzPts in EstimParameters.py uses [0.2, 0.4, 0.6, 0.8]).
LORENZ_PERCENTILES = (0.20, 0.40, 0.60, 0.80)


def lorenz_shares_from_weighted_grid(
    grid: np.ndarray, weights: np.ndarray,
    percentiles: tuple[float, ...] = LORENZ_PERCENTILES,
) -> np.ndarray:
    """Analytical Lorenz curve cumulative wealth shares at given percentiles.

    For a discrete distribution (grid, weights) where each grid[i] is a
    wealth value and weights[i] is the population share at that value,
    returns the fraction of total wealth held by the bottom p fraction
    of the population (in PERCENT, matching `data_LorenzPts` convention).

    Parameters
    ----------
    grid : np.ndarray, shape (N,)
        Wealth values (must be >= 0; sorted ascending recommended).
    weights : np.ndarray, shape (N,)
        Population shares (sum to 1).
    percentiles : tuple of floats in (0, 1)
        Population fractions at which to evaluate cumulative wealth share.

    Returns
    -------
    np.ndarray, shape (len(percentiles),)
        Cumulative wealth share at each percentile, IN PERCENT.

    Robust to constraint mass: when grid[0] = 0 and weights[0] is large
    (e.g., 27% at constraint for impatient agents), the Lorenz at low
    percentiles is correctly 0 rather than -∞ as for log moments.
    """
    grid = np.asarray(grid, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    weights = weights / weights.sum()

    cum_pop = np.cumsum(weights)
    wealth_per_bin = grid * weights
    cum_wealth = np.cumsum(wealth_per_bin)
    total_wealth = cum_wealth[-1]
    if total_wealth <= 0:
        return np.zeros(len(percentiles))

    out = []
    for p in percentiles:
        # Find the bin where cumulative population first crosses p
        idx = np.searchsorted(cum_pop, p)
        if idx >= len(grid):
            out.append(100.0)  # 100% of wealth at p=1
            continue
        # Linear interpolation within the bin: what share of bin's wealth
        # is in the "below-p" portion?
        if idx == 0:
            # Below first bin's full mass
            frac_in_bin = p / cum_pop[0] if cum_pop[0] > 0 else 0.0
            below_p_wealth = frac_in_bin * wealth_per_bin[0]
        else:
            frac_in_bin = (p - cum_pop[idx - 1]) / weights[idx]
            below_p_wealth = cum_wealth[idx - 1] + frac_in_bin * wealth_per_bin[idx]
        out.append(100.0 * below_p_wealth / total_wealth)
    return np.array(out)


def lorenz_shares_empirical(
    aNrm_samples: np.ndarray,
    percentiles: tuple[float, ...] = LORENZ_PERCENTILES,
) -> np.ndarray:
    """Empirical Lorenz shares from MC samples. Same convention (PERCENT)."""
    samples = np.asarray(aNrm_samples, dtype=np.float64)
    samples_sorted = np.sort(samples)
    n = len(samples_sorted)
    weights = np.ones(n) / n
    return lorenz_shares_from_weighted_grid(samples_sorted, weights, percentiles)


def compute_tma_analytical_moments(
    ergodic: np.ndarray, dist_aGrid: np.ndarray, J: int,
    *, agent=None, unemployment_rate: float | None = None,
) -> dict[str, float]:
    """Analytical moments of log(aNrm) and log(pLvl) under TM-a / pLvl ergodic.

    Parameters
    ----------
    ergodic : np.ndarray, shape (J*A,)  OR  (J, A)
        Joint ergodic distribution over (Markov state j, aNrm grid index a).
    dist_aGrid : np.ndarray, shape (A,)
        The a-grid (first entry typically 0).
    J : int
        Number of Markov states.
    agent : AggFiscalType, optional
        If supplied, also compute analytical pLvl moments via
        compute_pLvl_distribution (which uses Harmenberg-style mixture-of-
        lognormals over age cohorts). Without it, mean_log_p / var_log_p
        are NaN.
    unemployment_rate : float or None
        Passed to compute_pLvl_distribution. Affects effective per-period
        growth rate and shock variance.

    Returns
    -------
    dict with:
      mean_log_a, var_log_a — from TM-a's a-ergodic
      mean_log_p, var_log_p — from analytical pLvl ergodic (if agent given)
      mass_at_zero — total mass at aNrm = 0 (informational)
    """
    erg = np.asarray(ergodic, dtype=np.float64)
    if erg.ndim == 1:
        A = len(dist_aGrid)
        erg = erg.reshape(J, A)
    erg = erg / erg.sum()  # normalize defensively

    aGrid = np.asarray(dist_aGrid, dtype=np.float64)
    log_a = _safe_log(aGrid)
    # Marginal over Markov states: sum to get aNrm distribution
    aNrm_marginal = erg.sum(axis=0)
    aNrm_marginal /= aNrm_marginal.sum()

    mean_log_a = float(np.dot(aNrm_marginal, log_a))
    var_log_a = float(np.dot(aNrm_marginal, log_a ** 2) - mean_log_a ** 2)
    mass_at_zero = float(aNrm_marginal[0]) if aGrid[0] == 0.0 else 0.0

    # Level moments + Lorenz shares (the PRIMARY drift metrics — robust to
    # constraint mass; see compute_mc_empirical_moments docstring for why
    # log moments are unreliable in the presence of constraint mass).
    mean_aNrm = float(np.dot(aNrm_marginal, aGrid))
    var_aNrm = float(np.dot(aNrm_marginal, aGrid ** 2) - mean_aNrm ** 2)
    pct_25 = _percentile_from_distribution(aGrid, aNrm_marginal, 0.25)
    pct_50 = _percentile_from_distribution(aGrid, aNrm_marginal, 0.50)
    pct_75 = _percentile_from_distribution(aGrid, aNrm_marginal, 0.75)

    lorenz = lorenz_shares_from_weighted_grid(aGrid, aNrm_marginal)  # PERCENT

    out = {
        "mean_log_a": mean_log_a,
        "var_log_a": var_log_a,
        "mass_at_zero": mass_at_zero,
        "mean_log_p": float("nan"),
        "var_log_p": float("nan"),
        "mean_aNrm": mean_aNrm,
        "var_aNrm": var_aNrm,
        "pct_aNrm_25": pct_25,
        "pct_aNrm_50": pct_50,
        "pct_aNrm_75": pct_75,
        # Lorenz shares of aNrm at p=20/40/60/80 (PERCENT) — PRIMARY drift metric
        "lorenz_p20": float(lorenz[0]),
        "lorenz_p40": float(lorenz[1]),
        "lorenz_p60": float(lorenz[2]),
        "lorenz_p80": float(lorenz[3]),
    }

    # pLvl analytical moments (Phase 2.5):
    #   - mean_log_p / var_log_p come from compute_pLvl_distribution
    #     (the (1-u) single-Gaussian-per-cohort lognormal-mixture approximation).
    #   - mean_log_p_exact / var_log_p_exact come from compute_log_p_moments_exact
    #     (Markov-chain matrix-iteration, exact under HARK's employment dynamics).
    # Both are computed so drift checks can compare MC empirical to either.
    if agent is not None:
        try:
            from tm_methods import compute_pLvl_distribution
            pLvl_grid, p_weights = compute_pLvl_distribution(
                agent, n_points=200, unemployment_rate=unemployment_rate,
            )
            log_p = _safe_log(pLvl_grid)
            mean_log_p = float(np.dot(p_weights, log_p))
            var_log_p = float(np.dot(p_weights, log_p ** 2) - mean_log_p ** 2)
            out["mean_log_p"] = mean_log_p
            out["var_log_p"] = var_log_p
        except Exception as _e:
            print(f"[drift] WARNING: pLvl analytical moments unavailable: {_e!r}")
        try:
            from tm_methods import compute_log_p_moments_exact
            exact = compute_log_p_moments_exact(
                agent, unemployment_rate=unemployment_rate,
            )
            out["mean_log_p_exact"] = exact["mean_log_p_exact"]
            out["var_log_p_exact"] = exact["var_log_p_exact"]
        except Exception as _e:
            print(f"[drift] WARNING: exact pLvl moments unavailable: {_e!r}")

    return out


def compute_mc_empirical_moments(
    aLvl: np.ndarray, pLvl: np.ndarray
) -> dict[str, float]:
    """Empirical moments of aNrm and pLvl from MC simulated state.

    aNrm computed from aLvl/pLvl (avoid relying on agent.state_now['aNrm']
    which may have BUG-031/034 dispatch differences).

    Parameters
    ----------
    aLvl : np.ndarray, shape (N,) — household-total assets (BUG-031/034 fix applied)
    pLvl : np.ndarray, shape (N,) — permanent income level

    Returns
    -------
    dict with:
      mean_log_a, var_log_a       — log moments (HYPERSENSITIVE to constraint mass)
      mean_log_p, var_log_p       — log moments
      mass_at_zero                — fraction with aNrm <= _TINY
      pct_aNrm_25/50/75           — robust percentiles (PRIMARY drift metric)
      mean_aNrm, var_aNrm         — level moments (less constraint-sensitive)

    Note (added 2026-05-03 after first companion run): mean log(a) is
    NOT a reliable drift metric. TM-a places constraint mass at exactly
    a=0 (log → -inf, floored to log(1e-12)=-27.6); MC places it at small
    positive values. Even a few percent mass-at-constraint difference
    between the two yields huge log-moment "drift" that doesn't reflect
    any real distributional difference. The percentile comparison shows
    TM-a and MC agree within 1-3% at every quantile.
    """
    aLvl = np.asarray(aLvl, dtype=np.float64)
    pLvl = np.asarray(pLvl, dtype=np.float64)

    # Empty cross-section (e.g. an HS_Only / College_Beta_Het masked cohort with
    # AgentCount=0): there is no MC distribution to summarize. Return NaNs rather
    # than letting np.percentile([]) / cum_wealth[-1] raise IndexError. Callers
    # should skip these cohorts; this is defense in depth.
    if aLvl.size == 0 or pLvl.size == 0:
        nan = float("nan")
        return {k: nan for k in (
            "mean_log_a", "var_log_a", "mean_log_p", "var_log_p",
            "mass_at_zero", "pct_aNrm_25", "pct_aNrm_50", "pct_aNrm_75",
            "mean_aNrm", "var_aNrm",
            "lorenz_p20", "lorenz_p40", "lorenz_p60", "lorenz_p80",
        )}

    # Empirical aNrm = aLvl / pLvl (handle pLvl=0 defensively)
    pLvl_safe = np.where(pLvl > _TINY, pLvl, _TINY)
    aNrm = aLvl / pLvl_safe

    log_a = _safe_log(aNrm)
    log_p = _safe_log(pLvl)

    pct_25, pct_50, pct_75 = np.percentile(aNrm, [25, 50, 75])

    lorenz = lorenz_shares_empirical(aNrm)  # PERCENT, at p=20/40/60/80

    return {
        "mean_log_a": float(np.mean(log_a)),
        "var_log_a": float(np.var(log_a)),
        "mean_log_p": float(np.mean(log_p)),
        "var_log_p": float(np.var(log_p)),
        "mass_at_zero": float(np.mean(aNrm <= _TINY)),
        "pct_aNrm_25": float(pct_25),
        "pct_aNrm_50": float(pct_50),
        "pct_aNrm_75": float(pct_75),
        "mean_aNrm": float(np.mean(aNrm)),
        "var_aNrm": float(np.var(aNrm)),
        # Lorenz shares of aNrm at p=20/40/60/80 (PERCENT) — PRIMARY drift metric
        "lorenz_p20": float(lorenz[0]),
        "lorenz_p40": float(lorenz[1]),
        "lorenz_p60": float(lorenz[2]),
        "lorenz_p80": float(lorenz[3]),
    }


def measure_drift(
    tma_moments: dict[str, float],
    mc_moments: dict[str, float],
) -> dict[str, Any]:
    """Compute drift = MC − TM-a for each comparable moment.

    Asymmetric:
      mean_log_a: ABSOLUTE log-diff (interpretable as multiplicative %)
      var_log_a:  RELATIVE: (mc - tma) / tma
      var_log_p:  not in tma_moments (TM-a doesn't track pLvl analytically);
                  reported as raw value only — the "drift threshold" applies
                  to var_log_p drift across MC simulation periods (deferred:
                  the companion plan, plans/20260503-1437h_mc_tma_companion_and_drift.md,
                  closed 2026-05 without implementing it)
                  OR to drift between MC inits with different RNG seeds (a
                  cross-seed sensitivity check — the remaining fallback).
    """
    drift = {}
    # PRIMARY metric: Lorenz shares of aNrm at p=20/40/60/80, in PERCENT.
    # Robust to constraint mass (Lorenz at low p is naturally near 0 for
    # high-inequality distributions; both TM-a and MC report the same near-zero
    # value rather than -∞ as for log moments). Matches Step-2 estimation
    # targets convention (data_LorenzPts).
    # User direction 2026-05-03: "track the Lorenz quantiles for aNrm rather
    # than the log."
    for q in (20, 40, 60, 80):
        tma_l = tma_moments.get(f"lorenz_p{q}")
        mc_l = mc_moments.get(f"lorenz_p{q}")
        if tma_l is not None and mc_l is not None:
            # Lorenz is in [0, 100] PERCENT; absolute drift in percentage points
            drift[f"lorenz_p{q}_abs_pp"] = mc_l - tma_l

    # SECONDARY (informational): aNrm percentile drift, level moments, etc.
    for q in (25, 50, 75):
        tma_q = tma_moments.get(f"pct_aNrm_{q}")
        mc_q = mc_moments.get(f"pct_aNrm_{q}")
        if tma_q is not None and mc_q is not None:
            if abs(tma_q) > _TINY:
                drift[f"pct_aNrm_{q}_rel"] = (mc_q - tma_q) / tma_q
            else:
                drift[f"pct_aNrm_{q}_rel"] = float("nan")
                drift[f"pct_aNrm_{q}_abs"] = mc_q

    # DIAGNOSTIC ONLY: log moments (constraint-mass-sensitive; not primary)
    drift["mean_log_a_abs"] = mc_moments["mean_log_a"] - tma_moments["mean_log_a"]
    if abs(tma_moments["var_log_a"]) > _TINY:
        drift["var_log_a_rel"] = (mc_moments["var_log_a"] - tma_moments["var_log_a"]) / tma_moments["var_log_a"]
    else:
        drift["var_log_a_rel"] = float("nan")
    # pLvl analytical: prefer exact Markov-chain moments (compute_log_p_moments_exact,
    # 2026-05-06) over the legacy (1-u) lognormal-mixture single-Gaussian-per-cohort
    # approximation (compute_pLvl_distribution). The exact formula matches MC at
    # N=100k within sampling noise for D-cohort under Config B; the legacy approx
    # was off by +4.6% rel on var log(p) for D, which had forced the threshold
    # loosening below. Fall back to legacy if _exact fields are absent (backward
    # compat with old saved tma_moments dicts).
    tma_mean_p = tma_moments.get("mean_log_p_exact",
                                 tma_moments.get("mean_log_p", float("nan")))
    tma_var_p = tma_moments.get("var_log_p_exact",
                                tma_moments.get("var_log_p", float("nan")))
    if not np.isnan(tma_mean_p):
        drift["mean_log_p_abs"] = mc_moments["mean_log_p"] - tma_mean_p
    else:
        drift["mean_log_p_abs"] = float("nan")
    if not np.isnan(tma_var_p) and abs(tma_var_p) > _TINY:
        drift["var_log_p_rel"] = (mc_moments["var_log_p"] - tma_var_p) / tma_var_p
    else:
        drift["var_log_p_rel"] = float("nan")
    drift["mc_mass_at_zero"] = mc_moments.get("mass_at_zero", float("nan"))
    drift["tma_mass_at_zero"] = tma_moments.get("mass_at_zero", float("nan"))
    drift["mass_at_zero_abs"] = drift["mc_mass_at_zero"] - drift["tma_mass_at_zero"]
    return drift


def assess_and_report(
    drift: dict[str, Any],
    *,
    threshold: float | None = None,
    hard_fail: bool | None = None,
    label: str = "",
    agent: Any = None,
) -> bool:
    """Check drift against threshold; print a summary; HARD-FAIL or WARN per env.

    Returns True if all checks pass, False (or raises) on failure.

    Env vars:
      HAFISCAL_DRIFT_THRESHOLD   override default 0.03
      HAFISCAL_DRIFT_HARD_FAIL   '1' (default; raises) or '0' (warns)

    pLvl-moment threshold: tight (= ``threshold``) for both Config A and Config B.
    Previously, Config B (perm_shocks_during_unemployment=False) used a loosened
    threshold (max(threshold*4, 0.12)) because the analytical reference was the
    (1-u) lognormal-mixture single-Gaussian-per-cohort approximation, which biased
    var log(p) by up to ~15% under high-u cohorts. As of 2026-05-06 the analytical
    reference is the exact Markov-chain matrix-iteration formula
    (compute_log_p_moments_exact), so the loosening is no longer needed.
    """
    if threshold is None:
        threshold = float(os.environ.get("HAFISCAL_DRIFT_THRESHOLD", _DEFAULT_THRESHOLD))
    if hard_fail is None:
        hard_fail = os.environ.get("HAFISCAL_DRIFT_HARD_FAIL", "1") == "1"

    var_log_p_threshold = threshold

    # N-aware pLvl-moment band (see _PLVL_DRIFT_* and module docstring): the
    # pLvl drift is finite-population noise of a near-unit-root process around a
    # systematic warmup-transient center, so a fixed 0.03 spuriously fails at
    # production N. Band = center ± z·scale/√N (default z=3.090 ⇒ ≈0.2% false-fail).
    pLvl_naware = os.environ.get(
        "HAFISCAL_DRIFT_PLVL_NAWARE", "1" if _PLVL_DRIFT_NAWARE else "0") == "1"
    pLvl_z = float(os.environ.get("HAFISCAL_DRIFT_PLVL_Z", _PLVL_DRIFT_Z))
    N_agent = int(getattr(agent, "AgentCount", 0) or 0) if agent is not None else 0
    pLvl_naware = pLvl_naware and N_agent > 0  # need N to form the band

    failures: list[str] = []
    # PRIMARY: Lorenz share drift in percentage points
    # Threshold interpretation: 0.03 (default) means 3 percentage points.
    # For Step-2-targets-style Lorenz at p=20/40/60/80 (which range from
    # ~0.01% at the bottom for impatient cohorts to ~10% at the top), 3pp
    # is meaningful: catches large distributional shifts without
    # over-flagging the bottom percentiles where Lorenz is naturally near 0.
    threshold_pp = threshold * 100  # threshold is fraction; Lorenz is in PERCENT
    for q in (20, 40, 60, 80):
        d = drift.get(f"lorenz_p{q}_abs_pp", float("nan"))
        if not np.isnan(d) and abs(d) > threshold_pp:
            failures.append(
                f"Lorenz p{q}: drift={d:+.3f}pp (threshold ±{threshold_pp:.2f}pp)"
            )
    # SECONDARY: pLvl moments (still meaningful since pLvl has no constraint mass)
    mean_log_p_abs = drift.get("mean_log_p_abs", float("nan"))
    var_log_p_rel = drift.get("var_log_p_rel", float("nan"))
    if pLvl_naware:
        mean_lo, mean_hi = _pLvl_drift_band(
            _PLVL_MEAN_DRIFT_CENTER, _PLVL_MEAN_DRIFT_SCALE, N_agent, pLvl_z)
        var_lo, var_hi = _pLvl_drift_band(
            _PLVL_VAR_DRIFT_CENTER, _PLVL_VAR_DRIFT_SCALE, N_agent, pLvl_z)
        if not np.isnan(mean_log_p_abs) and not (mean_lo <= mean_log_p_abs <= mean_hi):
            failures.append(
                f"mean log(p): drift={mean_log_p_abs:+.4f} outside N-aware band "
                f"[{mean_lo:+.4f}, {mean_hi:+.4f}] (N={N_agent}, z={pLvl_z})"
            )
        if not np.isnan(var_log_p_rel) and not (var_lo <= var_log_p_rel <= var_hi):
            failures.append(
                f"var log(p): drift={var_log_p_rel:+.4f} outside N-aware band "
                f"[{var_lo:+.4f}, {var_hi:+.4f}] (N={N_agent}, z={pLvl_z})"
            )
    else:
        if not np.isnan(mean_log_p_abs) and abs(mean_log_p_abs) > threshold:
            failures.append(
                f"mean log(p): drift={mean_log_p_abs:+.4f} (threshold ±{threshold:.3f} absolute)"
            )
        if not np.isnan(var_log_p_rel) and abs(var_log_p_rel) > var_log_p_threshold:
            failures.append(
                f"var log(p): drift={var_log_p_rel:+.4f} relative (threshold ±{var_log_p_threshold:.3f})"
            )
    # NOTE: log(a) moments and aNrm percentiles are NOT primary fail criteria
    # — see compute_mc_empirical_moments docstring. Reported for diagnostic only.
    var_log_a_rel = drift.get("var_log_a_rel", float("nan"))

    prefix = f"[drift{(' ' + label) if label else ''}]"
    print(f"{prefix} === PRIMARY metric: Lorenz shares of aNrm (in percentage points) ===")
    for q in (20, 40, 60, 80):
        print(f"{prefix} Lorenz p{q} drift = {drift.get(f'lorenz_p{q}_abs_pp', float('nan')):+.3f}pp  [PRIMARY]")
    print(f"{prefix} === SECONDARY: pLvl moments ===")
    if pLvl_naware:
        _mlo, _mhi = _pLvl_drift_band(
            _PLVL_MEAN_DRIFT_CENTER, _PLVL_MEAN_DRIFT_SCALE, N_agent, pLvl_z)
        _vlo, _vhi = _pLvl_drift_band(
            _PLVL_VAR_DRIFT_CENTER, _PLVL_VAR_DRIFT_SCALE, N_agent, pLvl_z)
        print(f"{prefix} mean log(p) drift = {mean_log_p_abs:+.4f} (abs)  "
              f"N-aware band [{_mlo:+.4f}, {_mhi:+.4f}] (N={N_agent})")
        print(f"{prefix} var  log(p) drift = {var_log_p_rel:+.4f} (rel)  "
              f"N-aware band [{_vlo:+.4f}, {_vhi:+.4f}]")
    else:
        print(f"{prefix} mean log(p) drift = {mean_log_p_abs:+.4f} (abs)")
        print(f"{prefix} var  log(p) drift = {var_log_p_rel:+.4f} (rel)")
    print(f"{prefix} === DIAGNOSTIC (constraint-mass artifacts; NOT primary) ===")
    print(f"{prefix} aNrm p25 drift = {drift.get('pct_aNrm_25_rel', float('nan')):+.4f} (rel)")
    print(f"{prefix} aNrm p50 drift = {drift.get('pct_aNrm_50_rel', float('nan')):+.4f} (rel)")
    print(f"{prefix} aNrm p75 drift = {drift.get('pct_aNrm_75_rel', float('nan')):+.4f} (rel)")
    print(f"{prefix} mean log(a) = {drift.get('mean_log_a_abs', float('nan')):+.4f} (abs); var log(a) = {var_log_a_rel:+.4f} (rel)")
    print(f"{prefix} mass-at-zero diff = {drift.get('mass_at_zero_abs', float('nan')):+.4f}  (MC {drift.get('mc_mass_at_zero', float('nan')):.3f} vs TM-a {drift.get('tma_mass_at_zero', float('nan')):.3f})")

    if failures:
        msg = (
            f"{prefix} DRIFT EXCEEDS THRESHOLD ({threshold}):\n  "
            + "\n  ".join(failures)
        )
        if hard_fail:
            raise RuntimeError(msg + "\n  (set HAFISCAL_DRIFT_HARD_FAIL=0 to downgrade to WARNING)")
        else:
            print(f"WARNING: {msg}")
            return False
    print(f"{prefix} ✓ all drift checks pass (threshold {threshold})")
    return True


# ---------- CLI for ad-hoc inspection ----------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python _tm_a_drift.py <ergodic.npy> <agent_state_pickle>")
        sys.exit(1)
    # Stub — full CLI deferred to companion-runner script in Phase 4
    print("CLI stub: full ad-hoc drift inspection deferred to Phase 4")
