"""Quantiles of a distribution carried on an asset grid, by interpolating its weighted CDF.

BUG-079 (found 2026-08-20; owner ruling the same day: "interpolate the weighted CDF").

THE DEFECT.  The Step-2 estimators (``estim_phase2_tm_a.py``; legacy ``estim_phase2_tm.py``)
target the median liquid-wealth / permanent-income ratio of each education group.  The
model side is the pooled ergodic distribution of the transition-matrix engine: mass ``w_i``
on grid level ``a_i``, every grid level listed once per (discount-factor type x Markov
state).  They computed its median with ``HARK.utilities.get_percentiles`` -- a SAMPLE
quantile routine: sort the entries, cumulate their mass, interpolate the inverse CDF
between CONSECUTIVE ENTRIES.  Fed a gridded distribution, the interpolant is flat between
two consecutive entries on the same level, and the only place the value can move from one
level to the next is the segment between the last entry of a level and the first entry of
the next -- a segment whose mass is that of ONE (type, state) cell, ~1e-4..1e-3 of the
population.  So the model median was, for all practical purposes, a step function of the
parameters taking values on the grid, with cliffs between plateaus; and its value depended
on the sort order among tied entries.  Measured at the installed 2026-08-20 optimum (level
spacing at the median: Dropout 11%, HS 3.3%, College 3.0%): every group's optimum was a
corner solution within 1.6e-6 .. 1.7e-4 mass of a cliff; a 1e-10 relative perturbation of
the weights flipped the College distance 1.04 -> 2.06; and the calibration "missed" its
median targets by -6.3% / -0.04% / -1.4% (D / HS / C) for no economic reason.

THE ESTIMATOR.  The grid distribution is what the lottery (linear-interpolation, "tent")
kernel of the transition matrix makes it: mass landing at ``a'`` in ``(a_k, a_{k+1})`` is
split between the two bracketing levels in proportion to proximity, so the mass at level
``a_k`` is ``int f(a') tent_k(a') da'``.  The CDF of that distribution evaluated AT a level
is the mass strictly below the level plus HALF the level's own mass,

    F(a_k) = sum_{a_i < a_k} w_i + (1/2) sum_{a_i = a_k} w_i ,

and a quantile is the inverse of the piecewise-linear interpolant of F through the points
``(a_k, F(a_k))``.  The 1/2 is derived, not a convention: for a density that is linear
across a cell the tent kernel gives ``w_k = f(a_k) h`` exactly on a uniform grid (and
``w_0 = f(a_0) h/2`` at the boundary), so ``sum_{j<k} w_j + w_k/2 = h (f_0/2 + f_1 + ... +
f_{k-1} + f_k/2)`` -- the trapezoid rule, exact for linear f, for ``int_{a_0}^{a_k} f``.  The
"left" convention ``sum_{a_i <= a_k} w_i`` overstates ``F(a_k)`` by ``w_k/2`` and biases every
quantile LOW by half a level's mass (1.7 units = 1.5% of the College median at aCount=200).
The residual error of this estimator is O(h^2) in the level spacing -- the same order as
the TM discretisation itself -- against O(h) for node snapping; it is continuous in the
weights (a 1e-10 relative perturbation moves the College median by ~3e-9); and it depends
on the distribution alone, not on how its entries are listed.

Measured on the installed calibration: medians read 4.61 / 29.71 / 112.86 against the
targets 4.64 / 30.20 / 112.80 (D / HS / C).

Selection: ``HAFISCAL_STEP2_MEDIAN=interp`` (default) | ``node`` (the pre-fix HARK call, for
bisection and anchor reproduction).  See ``Code/HA-Models/docs/ENV_FLAGS.md`` and
``BUGS_private/HAFiscal_BUG-079_step2-median-grid-quantization.md``.
"""
from __future__ import annotations

import os

import numpy as np

__all__ = [
    "MEDIAN_MODES",
    "cdf_at_levels",
    "weighted_quantile_interp",
    "median_mode",
    "step2_median",
]

MEDIAN_MODES = ("interp", "node")
_ENV = "HAFISCAL_STEP2_MEDIAN"


def cdf_at_levels(a, w):
    """CDF of a gridded distribution, evaluated at its distinct levels.

    Parameters
    ----------
    a : array_like
        Asset level of each entry.  Levels may repeat (one entry per type x state is the
        normal case); entries are pooled by level.
    w : array_like
        Non-negative mass of each entry (any normalisation).

    Returns
    -------
    levels : ndarray
        Distinct levels carrying positive mass, ascending.
    F_at : ndarray
        ``F(levels[k])`` = normalised mass strictly below ``levels[k]`` plus half the mass
        at it (tent-kernel CDF; see the module docstring).  Strictly increasing.
    mass : ndarray
        Normalised mass at each level (sums to 1).
    """
    a = np.asarray(a, dtype=float).ravel()
    w = np.asarray(w, dtype=float).ravel()
    if a.shape != w.shape:
        raise ValueError(f"a and w must have the same size; got {a.size} and {w.size}")
    if a.size == 0:
        raise ValueError("empty distribution")
    if not (np.all(np.isfinite(a)) and np.all(np.isfinite(w))):
        raise ValueError("levels and masses must be finite")
    if np.any(w < 0.0):
        raise ValueError("masses must be non-negative")
    total = float(np.sum(w))
    if not total > 0.0:
        raise ValueError("total mass must be positive")
    levels, inverse = np.unique(a, return_inverse=True)
    mass = np.bincount(inverse, weights=w, minlength=levels.size) / total
    keep = mass > 0.0
    levels, mass = levels[keep], mass[keep]
    below = np.concatenate(([0.0], np.cumsum(mass)[:-1]))
    F_at = below + 0.5 * mass
    return levels, F_at, mass


def weighted_quantile_interp(a, w, q):
    """Quantile(s) of a gridded distribution by linear interpolation of its weighted CDF.

    ``q`` may be a scalar or an array of probabilities in the open interval (0, 1).  Returns
    an array of the same shape as ``np.atleast_1d(q)``.  A probability below ``F(levels[0])``
    or above ``F(levels[-1])`` (inside the outermost half-masses) returns the boundary level.
    """
    levels, F_at, _ = cdf_at_levels(a, w)
    q_arr = np.atleast_1d(np.asarray(q, dtype=float))
    if np.any(~np.isfinite(q_arr)) or np.any(q_arr <= 0.0) or np.any(q_arr >= 1.0):
        raise ValueError("quantile probabilities must lie in (0, 1)")
    return np.interp(q_arr, F_at, levels)


def median_mode(mode=None):
    """Resolve the Step-2 median estimator: explicit ``mode`` or ``HAFISCAL_STEP2_MEDIAN``."""
    m = (mode if mode is not None else os.environ.get(_ENV, "interp")).strip().lower()
    if m not in MEDIAN_MODES:
        raise ValueError(f"{_ENV} must be one of {MEDIAN_MODES}; got {m!r}")
    return m


def step2_median(a, w, mode=None):
    """The Step-2 model median of a pooled gridded distribution, shape ``(1,)``.

    ``interp`` (default): :func:`weighted_quantile_interp` at 0.5.
    ``node``: the pre-fix ``HARK.utilities.get_percentiles`` call, byte-for-byte, for
    bisection and anchor reproduction.
    """
    m = median_mode(mode)
    if m == "interp":
        return weighted_quantile_interp(a, w, 0.5)
    from HARK.utilities import get_percentiles  # node mode only
    return get_percentiles(np.asarray(a), weights=np.asarray(w), percentiles=[0.5])
