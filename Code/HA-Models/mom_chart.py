"""mom_chart.py — Method-of-Moderation log-gap chart for Step-1-class 1-D hosts.

The proposal from the 2026-08-22 dimensional-robustness exchange (owner-charged A/B,
plan: plans_local/20260822-0230h_mom-chart-s1-ab_plan.md): re-CHART the solved
consumption function instead of re-coordinatizing the solver. Given the host's solved
knots (xᵢ, cᵢ, c′ᵢ) and the PF bound c̄(m) = κ̲·(m+h̄), represent the UNCONSTRAINED
branch as a cubic Hermite of y = log(gap) against ξ = log(m+h̄):

    gᵢ = κ̲·(xᵢ+h̄) − cᵢ           (Carroll–Kimball: strictly positive)
    y′ᵢ = (xᵢ+h̄)·(κ̲ − c′ᵢ)/gᵢ     (exact chain rule at the knots)

Evaluation inverts the chart: c(m) = κ̲·(m+h̄) − exp(y(log(m+h̄))), and the MPC is
κ̲ − (g/X)·y′(ξ). Beyond the knot range the chart continues LINEARLY in (ξ, y) with
its end slopes — above the top this IS a power-law gap with the locally-measured
exponent (the attach falls out of the chart; no separate estimator), and below the
bottom knot the log-X coordinate compresses the whole [0, x₀] m-range into a
vanishing ξ-sliver (X = m+h̄ ≥ h̄), so no low-end pathology is reachable.

Wiring pattern mirrors the proven power-law retrofit exactly (powerlaw_decay):
``chartify_chs`` swaps ``__class__`` ON THE HOST INSTANCE (HARK's scipy-backed
``CubicHermiteInterp``) — in-place, so every captured reference (``vPfunc`` holds the
same object) sees the chart with zero reference surgery — and installs the chart
attributes. ``distance_criteria`` mirrors the stock class, so solve-convergence
semantics are unchanged. Transparent-fallback convention: any unhealthy geometry
refuses (host untouched, stock tail kept) and the caller warns once.

Consumers: ``HAFISCAL_PF_DECAY_Q=chart`` (per-iteration install in
rng_synchronized_consumer, alongside the farfield gate). Opt-in only — no default
change under this program (plan §2.4).
"""
from __future__ import annotations

import os

import numpy as np
from scipy.interpolate import CubicHermiteSpline, PchipInterpolator

try:
    from HARK.interpolation import CubicHermiteInterp as _HARK_CHS
except Exception:  # pragma: no cover
    _HARK_CHS = None

__all__ = ["MoMLogGapChartCHS", "chartify_chs"]


if _HARK_CHS is not None:
    class MoMLogGapChartCHS(_HARK_CHS):
        """Chart twin of HARK's scipy-backed ``CubicHermiteInterp``.

        Never constructed directly: ``chartify_chs`` swaps ``__class__`` on a stock
        instance and installs the ``_chart_*`` attributes. Evaluation is ENTIRELY
        chart-based (interior and both extrapolation ends) — unlike the power-law
        retrofit, which only replaces the above-top region — because the chart's
        interior representation quality IS the registered question of the A/B.
        """

        distance_criteria = ["x_list", "y_list", "dydx_list"]

        def _chart_pieces(self, x):
            X = np.maximum(np.asarray(x, dtype=float) + self._chart_h, 1e-12)
            xi = np.log(X)
            lo, hi = self._chart_xi_lo, self._chart_xi_hi
            y = np.empty_like(xi)
            dy = np.empty_like(xi)
            inb = (xi >= lo) & (xi <= hi)
            if np.any(inb):
                y[inb] = self._chart_spline(xi[inb])
                dy[inb] = self._chart_dspline(xi[inb])
            below = xi < lo
            if np.any(below):
                y[below] = self._chart_y_lo + self._chart_s_lo * (xi[below] - lo)
                dy[below] = self._chart_s_lo
            above = xi > hi
            if np.any(above):
                y[above] = self._chart_y_hi + self._chart_s_hi * (xi[above] - hi)
                dy[above] = self._chart_s_hi
            g = np.exp(y)
            return X, g, dy

        def _eval_helper(self, x, out_bot, out_top):
            X, g, _ = self._chart_pieces(x)
            return self._chart_kappa * X - g

        def _der_helper(self, x, out_bot, out_top):
            X, g, dy = self._chart_pieces(x)
            return self._chart_kappa - (g / X) * dy


def chartify_chs(unc, MPCmin, hNrm):
    """In-place chartification of a stock solved CHS host. Returns (bool, reason).

    Guards mirror the retrofit conventions: on any unhealthy geometry the host is
    left untouched (stock tail kept) and (False, why) comes back for the caller's
    one-shot warning.
    """
    if _HARK_CHS is None:
        return False, "HARK CubicHermiteInterp unavailable"
    if getattr(unc, "decay_extrap_form", "") == "mom_chart":
        return True, "already chart"
    if type(unc) is not _HARK_CHS:
        return False, f"host is not a stock CubicHermiteInterp ({type(unc).__name__})"
    kappa, h = float(MPCmin), float(hNrm)
    if not (np.isfinite(h) and kappa > 0.0):
        return False, f"RIC/FHWC fails (MPCmin={kappa}, hNrm={h})"
    x = np.asarray(unc.x_list, dtype=float)
    # Evaluate the ACTUAL host at its knots (values and slopes) rather than trusting
    # y_list/dydx_list: any coefficient surgery (the KinkedR kink segment) is then
    # represented faithfully. Must happen BEFORE the class swap.
    c = np.asarray(unc(x), dtype=float)
    dc = np.asarray(unc.derivative(x), dtype=float)
    X = x + h
    if not np.all(X > 0.0) or not np.all(np.diff(X) > 0.0):
        return False, "knot X = x + hNrm not positive/increasing"
    g = kappa * X - c
    if not np.all(g > 0.0):
        return False, "non-positive PF gap at a knot (chart undefined)"
    xi = np.log(X)
    y = np.log(g)
    dydxi = X * (kappa - dc) / g
    if not (np.all(np.isfinite(y)) and np.all(np.isfinite(dydxi))):
        return False, "non-finite chart data"
    # Interp kind (mechanism-pin experiment, owner word 2026-08-22): 'hermite'
    # (default) uses the EXACT transformed knot slopes; 'pchip' discards them for
    # scipy's shape-preserving monotone slopes -- if the chart's estimation-surface
    # roughness comes from slope-noise-driven Hermite oscillation between sparse
    # top knots, PCHIP kills it by construction (y is strictly decreasing, so
    # monotone interpolation is admissible).
    kind = os.environ.get('HAFISCAL_MOM_CHART_INTERP', 'hermite').strip().lower()
    if kind == 'pchip':
        spline = PchipInterpolator(xi, y)
        dspl = spline.derivative()
        s_lo, s_hi = float(dspl(xi[0])), float(dspl(xi[-1]))
    elif kind == 'hermite':
        spline = CubicHermiteSpline(xi, y, dydxi)
        s_lo, s_hi = float(dydxi[0]), float(dydxi[-1])
    else:
        return False, f"unknown HAFISCAL_MOM_CHART_INTERP={kind!r}"
    if s_hi >= 0.0:
        return False, f"top end slope {s_hi:.4g} >= 0 (gap not decaying)"
    unc.__class__ = MoMLogGapChartCHS
    unc._chart_kappa = kappa
    unc._chart_h = h
    unc._chart_xi_lo = float(xi[0])
    unc._chart_xi_hi = float(xi[-1])
    unc._chart_y_lo = float(y[0])
    unc._chart_y_hi = float(y[-1])
    unc._chart_s_lo = s_lo
    unc._chart_s_hi = s_hi
    unc._chart_spline = spline
    unc._chart_dspline = spline.derivative()
    unc._chart_interp_kind = kind
    unc.decay_extrap = True
    unc.decay_extrap_form = "mom_chart"
    # The chart's above-top continuation is a power law with this exponent — exposed
    # under the same attribute the probe/certification machinery already reads.
    unc.decay_extrap_Q = float(-s_hi)
    return True, "ok (chartified in place)"


# ── PR co-debug dispatch (see powerlaw_decay.py's twin block; owner charge
# 2026-08-22). The PR spells the chartifier `chartify_in_place(interp, MPCmin,
# hNrm, interp_kind=...)`; this adapter carries HAFISCAL_MOM_CHART_INTERP through
# so both implementations read the same knob.
try:
    import hark_tail_pr as _htp
    if _htp.pr_mode_active():
        _pr_chartify = _htp.load().chartify_in_place

        def chartify_chs(unc, MPCmin, hNrm):  # noqa: F811 — deliberate rebinding
            kind = os.environ.get('HAFISCAL_MOM_CHART_INTERP', 'hermite').strip().lower()
            return _pr_chartify(unc, MPCmin, hNrm, interp_kind=kind)

        print(f"[tail-impl] chartify -> PR ({_htp.source()})")
except Exception as _e:
    import warnings as _w
    _w.warn(f"hark_tail_pr dispatch unavailable ({_e!r}); vendored chartify kept.")
