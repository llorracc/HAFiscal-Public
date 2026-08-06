"""Local two-secant estimation of the power-law tail exponent (owner design, 2026-07-22).

Instead of pinning the decay exponent to an asymptotic theory anchor (which the
2026-07-21/22 deep-solve traces showed matches NOTHING in the reachable range) or
to the one-segment slope at the top knot, estimate Q locally from three existing
top-of-grid knots of the SOLVED consumption function:

    Q_k = -d ln gap / d ln(x + h)   via two log-log secants Q1 (lower), Q2 (upper),

attach the tail with Q2 (most local), and use a windowed secant-difference per
e-fold of ln(x+h) as the a-posteriori DRIFT diagnostic that aXtraMax is high
enough for the local power law to be stable ("verify + warn, never iterate" —
the owner rejected a grow-until-tolerance re-solve loop). Calibration
(deep-truth prototype, decay_form/two_secant_prototype.py): |drift| <=
0.05/e-fold corresponds to ~1e-4-class far-field consumption error; the K=3
solve-top rule (aXtraMax = 3*h) runs silent on the tested production atoms.

DRIFT WINDOW (F5 refinement, 2026-07-23): the 2026-07-23 dual-process
sliding-window profiles showed the FINAL solved knot carries endpoint
noise/bias — last-knot windows read drift ~+0.07 where 5-knot interior
regressions ending one knot below are clean (the plateau evidence). The
DIAGNOSTIC drift is therefore measured on windows that EXCLUDE the final knot:
the same two-secant estimator, selected over the knots below the top one
(minimal-change design — one estimator, same per-e-fold units and span/gap
gates, window shifted down one knot to drop the contaminated endpoint; chosen
over a 5-knot regression, which would introduce a second estimator with its
own calibration). The ATTACH Q is untouched: it stays the most-local upper
secant Q2, endpoint included — locality beats endpoint polish for the attach
(the certification's self-limiting error structure). With fewer than 4 usable
knots the diagnostic falls back to the legacy top-window drift (Q2-Q1)/e-fold
(``drift_window='legacy-top'`` in the returned dict).

Identifiability requires real log-leverage in (x+h) below the top — impossible
when aXtraMax << h (the production-legacy T=40 vs h~197). Hence the companion
solve-top rule in EstimParameters (aXtraMax_g = K*h_g, HAFISCAL_PF_DECAY_AMAX_MULT,
default 3). See plans/20260722_local-two-secant-tail-q_plan.md.

Pure numpy; no repo imports (unit-testable standalone: test_local_q_tail.py).
"""

import os
import warnings

import numpy as np

__all__ = ["local_q_from_knots", "select_top_knots", "two_secant_q",
           "maybe_warn_drift", "begin_round", "reset_diagnostics", "DIAG"]

GAP_FLOOR = 1e-10          # trust gaps only where gap/c exceeds this (decay_form convention)
MIN_SPAN = 0.05            # minimum total ln(x+h) span across the three knots (e-folds)
SELECT_TARGETS = (0.8, 0.64)  # (x+h) fractions of the top pivot for the two lower knots

# Process-wide diagnostics (read by tests / post-solve inspection; warnings are one-shot).
DIAG = {"n_slices": 0, "n_local2": 0, "n_fallback": 0,
        "max_abs_drift": 0.0, "worst": None}
_WARNED = {"tol": False, "fallback": False}
# Per-solver-invocation ROUND (2026-07-23 wart fix): the process DIAG accumulates
# over EVERY EGM iterate, so its worst can be a transient far from the fixed
# point (observed: identical warning text across different-beta agents,
# inherited from a shared early iterate). begin_round() is called at the top of
# each solver invocation's attach block; the advisory then keys on the ROUND's
# worst, and only once it has STABILIZED across rounds (the converged plateau).
_ROUND = {"worst": 0.0, "rec": None, "prev": None, "stable": 0}


def begin_round():
    """Start a solver-invocation round (call at each attach-block top)."""
    _ROUND.update(worst=0.0, rec=None)


def reset_diagnostics():
    DIAG.update(n_slices=0, n_local2=0, n_fallback=0, max_abs_drift=0.0, worst=None)
    _WARNED.update(tol=False, fallback=False)
    _ROUND.update(worst=0.0, rec=None, prev=None, stable=0)


def select_top_knots(x, targets=SELECT_TARGETS):
    """Indices (i1, i2, itop) into ascending pivot coords ``x`` (= m + h):
    the top knot plus the existing knots nearest targets[0]*x_top and
    targets[1]*x_top. Returns None if three distinct knots are unavailable."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 3:
        return None
    itop = n - 1
    i2 = int(np.argmin(np.abs(x - targets[0] * x[itop])))
    i1 = int(np.argmin(np.abs(x - targets[1] * x[itop])))
    if i2 >= itop:
        i2 = itop - 1
    if i1 >= i2:
        i1 = i2 - 1
    if i1 < 0:
        # Targets fall below the lowest knot (grid top too shallow relative to h
        # for the intended leverage). Fall back to the last three knots — the
        # caller's span check then delivers the informative "aXtraMax too low"
        # verdict (plan §1: last-3 fallback).
        return itop - 2, itop - 1, itop
    return i1, i2, itop


def two_secant_q(x3, gap3):
    """(Q1, Q2, drift_per_efold) from three (pivot, gap) pairs, ascending in pivot."""
    lx, lg = np.log(np.asarray(x3, float)), np.log(np.asarray(gap3, float))
    Q1 = -(lg[1] - lg[0]) / (lx[1] - lx[0])
    Q2 = -(lg[2] - lg[1]) / (lx[2] - lx[1])
    drift = (Q2 - Q1) / (0.5 * (lx[2] - lx[0]))
    return float(Q1), float(Q2), float(drift)


def _interior_drift(x, c, h, mpc_min, min_span=MIN_SPAN, targets=SELECT_TARGETS):
    """Diagnostic drift from windows that EXCLUDE the final knot (F5, 2026-07-23).

    Runs the SAME triple-selection + two-secant pipeline as the attach path,
    but over ``x[:-1]``/``c[:-1]`` (top pivot = the second-to-last knot), so the
    endpoint-noisy final knot never enters the drift measurement. Returns the
    drift per e-fold, or ``None`` when the interior window is unusable (fewer
    than 4 knots overall, insufficient ln-span, or bad gaps) — the caller then
    falls back to the legacy top-window drift. Advisory only: failures here
    never affect the attach.
    """
    xi, ci = x[:-1], c[:-1]
    sel = select_top_knots(xi, targets)
    if sel is None:
        return None
    x3 = xi[np.array(sel)]
    if np.log(x3[-1] / x3[0]) < min_span:
        return None
    c3 = ci[np.array(sel)]
    gap3 = mpc_min * x3 - c3
    if np.any(gap3 <= 0.0) or np.any(gap3 / np.maximum(c3, 1e-300) <= GAP_FLOOR):
        return None
    _, _, drift = two_secant_q(x3, gap3)
    return drift


def local_q_from_knots(m, c, h, mpc_min, min_span=MIN_SPAN, targets=SELECT_TARGETS):
    """Full pipeline for one solved slice.

    m, c : ascending solved knots (EXCLUDING any synthetic bottom point).
    h    : the slice's human wealth (pivot offset; PF line = mpc_min*(m+h)).

    Returns dict(ok, Q, Q1, Q2, drift, reason). ok=False => caller falls back to
    the slope-based Q (and the one-shot fallback warning names the reason).
    """
    m = np.asarray(m, dtype=float)
    c = np.asarray(c, dtype=float)
    DIAG["n_slices"] += 1
    x = m + h
    sel = select_top_knots(x, targets)
    if sel is None:
        return _fallback("fewer than three usable knots")
    idx = np.array(sel)
    x3 = x[idx]
    span = np.log(x3[-1] / x3[0])
    if span < min_span:
        return _fallback(
            f"ln(x+h) span {span:.3f} < {min_span} (aXtraMax too low relative to h "
            f"for local-Q identifiability)")
    gap3 = mpc_min * x3 - c[idx]
    c3 = c[idx]
    if np.any(gap3 <= 0.0) or np.any(gap3 / np.maximum(c3, 1e-300) <= GAP_FLOOR):
        return _fallback("non-positive or sub-floor gap at a selected knot")
    Q1, Q2, drift_top = two_secant_q(x3, gap3)
    if Q2 <= 0.0:
        return _fallback(f"non-positive upper-secant exponent Q2={Q2:.4f}")
    # DIAGNOSTIC drift from interior windows (final knot excluded; F5 2026-07-23
    # — the endpoint carries noise/bias the sliding-window profiles localized to
    # the last knot). The ATTACH Q above stays the endpoint-inclusive Q2.
    drift = _interior_drift(x, c, h, mpc_min, min_span, targets)
    drift_window = "interior"
    if drift is None:
        drift, drift_window = drift_top, "legacy-top"
    DIAG["n_local2"] += 1
    if abs(drift) > DIAG["max_abs_drift"]:
        DIAG["max_abs_drift"] = abs(drift)
        DIAG["worst"] = dict(Q1=Q1, Q2=Q2, drift=drift, m_top=float(m[-1]), h=float(h))
    if abs(drift) > _ROUND["worst"]:
        _ROUND["worst"] = abs(drift)
        _ROUND["rec"] = dict(Q1=Q1, Q2=Q2, drift=drift, m_top=float(m[-1]), h=float(h))
    return dict(ok=True, Q=Q2, Q1=Q1, Q2=Q2, drift=drift,
                drift_window=drift_window, reason=None)


def _fallback(reason):
    DIAG["n_fallback"] += 1
    if not _WARNED["fallback"]:
        _WARNED["fallback"] = True
        warnings.warn(
            "local_q_tail: falling back to the slope-based decay exponent for at least "
            f"one slice ({reason}). If widespread, raise HAFISCAL_PF_DECAY_AMAX_MULT / "
            "HAFISCAL_SOLVE_AMAX. Further fallbacks this process are silent; see "
            "local_q_tail.DIAG.", stacklevel=3)
    return dict(ok=False, Q=None, Q1=None, Q2=None, drift=None,
                drift_window=None, reason=reason)


def maybe_warn_drift(tol=None):
    """One-shot advisory when a STABILIZED round's worst |drift| exceeds tolerance.

    Called at each solver-invocation return. 2026-07-23 wart fix: the old form
    warned on the worst drift EVER seen, which could be a transient early EGM
    iterate. Now the advisory keys on the ROUND (this invocation's attaches,
    begin_round() at the block top) and fires only once the round-worst has been
    stable (±10%) for >= 3 consecutive rounds — the converged plateau. Post-hoc
    tools should read the converged slices' ``local_q_diag`` directly (the
    k_sweep harness pattern).
    """
    if tol is None:
        tol = float(os.environ.get("HAFISCAL_PF_DECAY_DRIFT_TOL", "0.05"))
    r = _ROUND["worst"]
    prev = _ROUND["prev"]
    if prev is not None and abs(r - prev) <= 0.10 * max(r, prev, 1e-12):
        _ROUND["stable"] += 1
    else:
        _ROUND["stable"] = 0
    _ROUND["prev"] = r
    if _WARNED["tol"] or r <= tol or _ROUND["stable"] < 3:
        return
    _WARNED["tol"] = True
    w = _ROUND["rec"] or {}
    warnings.warn(
        f"local_q_tail: local power-law exponent still drifting at the grid top "
        f"on the converged plateau (round worst interior-window drift = "
        f"{r:.3f}/e-fold > tol {tol}; final knot excluded from the measurement — "
        f"F5 2026-07-23; attach secants Q1={w.get('Q1'):.3f} Q2={w.get('Q2'):.3f} "
        f"at m_top={w.get('m_top'):.1f}, h={w.get('h'):.1f}; stable "
        f"{_ROUND['stable']} rounds). The attach still uses the most-local Q2. "
        "First lever: raise HAFISCAL_AXTRA_COUNT (top-knot spacing is the "
        "dominant drift contaminant at low counts), then "
        "HAFISCAL_PF_DECAY_AMAX_MULT / HAFISCAL_SOLVE_AMAX. One-shot warning; see "
        "local_q_tail.DIAG.", stacklevel=2)
