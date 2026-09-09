"""farfield_tail_q.py — the FAR-FIELD tail exponent via an Anderson mini-solve.

THE PROBLEM (owner framing, 2026-08-21): the certified power-law continuation attaches at
the top gridpoint with an exponent MEASURED from adjacent top-knot secants. All three
identifying inputs are top-knot-local, so coarse solve grids (hermite60's 60-basis)
destroy the measurement (drift ~0.2/e-fold ⟹ ~1e-3 far-field error ⟹ the S1 acceptance
FAIL, ∇ −2.3%). The July feasibility bound: identification needs span AND density at the
top; 60-point grids keep only the span.

THE WAY AROUND (owner-approved; second design after the first was falsified in-session):
measure the exponent from the far field itself, generated analytically — no grid knots
involved — and pin only the AMPLITUDE by top-knot level continuity (the one datum coarse
grids keep accurate; the `decay_extrap_Q` override path of powerlaw_decay does exactly
this: A = top-knot gap, Q = supplied).

DESIGN HISTORY (recorded per the failed-attempts discipline):
- v1 (k-step Richardson): iterate T from the PF anchor c̄, model gap_k = (1−λ^k)·gap_∞
  with scalar λ, Richardson to gap_∞. FALSIFIED by measurement 2026-08-21 (~18:5x): the
  linearized backward operator's far-field spectrum sits at μ ≈ 1 for patient atoms
  (measured λ̂ = 0.997..1.01) — increments are non-contractive because the far-field
  SHAPE rotates toward the fixed point's exponent (the resolvent reshapes the forcing's
  exponent toward q*), which no scalar-λ extrapolation can see. More plain EGM steps
  cannot fix this. Also NOT fixable by pinning q to the asymptotic root q*: the July
  2026-07-22 measurements showed the extrapolation's USED range (top..~20×top) is
  PRE-asymptotic (effective exponent 0.39–0.63 vs q* 1.37-class) — that ruling stands.
- v2 (this file): SOLVE the far-field problem to convergence — Anderson-accelerated EGM
  ("one FTI leap", the owner's hint) on a dedicated wide log grid in X = m + h spanning
  ~[0.05, 512]×(x_top + h). Anderson handles μ ≈ 1 spectra in a few dozen operator
  applications; each application is one analytic expectation over the type's OWN
  discretized shocks. q̂ is then the log-log slope of the CONVERGED gap over the USED
  window (default [1.5, 20]×), i.e. the true pre-asymptotic effective exponent with a
  decades-long lever arm and zero grid noise. The reported curvature diagnostic is the
  drift analog (how non-constant the effective exponent is across the window).

Edge handling: information flows both ways (m' = (R/Γψ)a + θ, with R/Γψ on both sides of
1), so both edges carry a buffer far outside the fit window and the log-gap interpolant
extends with END SLOPES (not clamps); the wide buffer keeps edge error from reaching the
window within the iteration count (verified by the V0 deep-solve truth gate).

Consumers: `HAFISCAL_PF_DECAY_Q=farfield` (Step-1 wrap in rng_synchronized_consumer.py).
S2/AggFiscalModel keeps its certified `measured` default; adoption there is a separate
decision. Plan: remedies plan F addenda; onset-rule ruling doc for the anchor machinery.
"""
from __future__ import annotations

import numpy as np

_MEMO: dict = {}


def _key(*vals):
    out = []
    for v in vals:
        if isinstance(v, (float, np.floating)):
            out.append(float(f"{float(v):.12g}"))
        elif isinstance(v, np.ndarray):
            out.append(tuple(float(f"{x:.12g}") for x in np.ravel(v)))
        else:
            out.append(v)
    return tuple(out)


def _interp_loggap_extend(lx, lg):
    """log-gap interpolant with end-slope extension (never clamp: both edges transport).
    Defensive: dedupes x (EGM re-tabulation can repeat knots) and guards the end slopes."""
    lx, idx = np.unique(lx, return_index=True)
    lg = lg[idx]
    sl_lo = (lg[1] - lg[0]) / max(lx[1] - lx[0], 1e-12)
    sl_hi = (lg[-1] - lg[-2]) / max(lx[-1] - lx[-2], 1e-12)

    def f(lxq):
        out = np.interp(lxq, lx, lg)
        lo = lxq < lx[0]
        hi = lxq > lx[-1]
        if np.any(lo):
            out[lo] = lg[0] + sl_lo * (lxq[lo] - lx[0])
        if np.any(hi):
            out[hi] = lg[-1] + sl_hi * (lxq[hi] - lx[-1])
        return out
    return f


def farfield_q(Rfree, DiscFacEff, CRRA, PermGroFac, psi, theta, pmv,
               x_top, *, window=(1.5, 20.0), n_grid=300, grid_span=(0.05, 512.0),
               anderson_depth=6, tol=1e-9, itmax=300):
    """Far-field tail exponent q̂ for one solve-slice, with diagnostics.

    Returns (q_hat, diag); (None, diag) when unhealthy (caller falls back to the
    measured/slope modes). Memoized on the solve primitives.
    """
    memo_k = _key(Rfree, DiscFacEff, CRRA, PermGroFac, psi, theta, pmv, x_top,
                  window, n_grid, grid_span, anderson_depth, tol, itmax)
    if memo_k in _MEMO:
        return _MEMO[memo_k]

    R, beta_eff, rho, G = float(Rfree), float(DiscFacEff), float(CRRA), float(PermGroFac)
    psi = np.asarray(psi, dtype=float)
    theta = np.asarray(theta, dtype=float)
    w = np.asarray(pmv, dtype=float)
    pat = (R * beta_eff) ** (1.0 / rho) / R
    kappa = 1.0 - pat
    if not (0.0 < kappa < 1.0) or G >= R:
        out = (None, {"reason": f"degenerate limits kappa={kappa:.4g} G/R={G / R:.4g}"})
        _MEMO[memo_k] = out
        return out
    h = G / (R - G)

    def cbar(m):
        return kappa * (m + h)

    pivot_top = x_top + h
    # State: log-gap at fixed m-points, log-spaced in X = m + h across the buffered span.
    # FLOOR: assets a = (1-κ̲)X − h must stay strictly positive, so the bottom buffer is
    # X_min = h/(1−κ̲)·(1+margin) — below that the model region is meaningless and the
    # clamped duplicates NaN the end-slope extension (caught by the first sanity run).
    X_lo = max(grid_span[0] * pivot_top, h / (1.0 - kappa) * 1.10)
    X_grid = np.geomspace(X_lo, grid_span[1] * pivot_top, n_grid)
    m_grid = X_grid - h
    lx = np.log(X_grid)
    # EOP asset points paired to the m-grid via the anchor policy (fixed representation;
    # the EGM re-tabulation below maps back onto m_grid each application).
    a_grid = (1.0 - kappa) * X_grid - h          # strictly positive by the X_lo floor
    Rratio = (R / (G * psi))[:, None]
    growth = (G * psi)[:, None] ** (-rho)
    m_next = Rratio * a_grid[None, :] + theta[:, None]
    lx_next = np.log(m_next + h)

    win_mask = (X_grid >= window[0] * pivot_top) & (X_grid <= window[1] * pivot_top)
    if win_mask.sum() < 6:
        out = (None, {"reason": "fit window under-resolved on the mini-grid"})
        _MEMO[memo_k] = out
        return out

    def apply_T(lg):
        """One EGM application: log-gap at m_grid -> log-gap at m_grid."""
        gap_eval = _interp_loggap_extend(lx, lg)
        c_next_vals = cbar(m_next) - np.exp(gap_eval(lx_next))
        c_next_vals = np.maximum(c_next_vals, 1e-12)
        integ = (growth * c_next_vals ** (-rho) * w[:, None]).sum(0)
        c_a = (R * beta_eff * integ) ** (-1.0 / rho)
        m_a = a_grid + c_a
        g_a = np.maximum(cbar(m_a) - c_a, 1e-300)
        back = _interp_loggap_extend(np.log(m_a + h), np.log(g_a))
        return back(lx)

    # --- initial guess: ONE plain step from the anchor (gap identically 0 at c̄) ---
    c0 = cbar(m_next)
    integ0 = (growth * c0 ** (-rho) * w[:, None]).sum(0)
    c_a0 = (R * beta_eff * integ0) ** (-1.0 / rho)
    g0 = np.maximum(cbar(a_grid + c_a0) - c_a0, 1e-300)
    lg = _interp_loggap_extend(np.log(a_grid + c_a0 + h), np.log(g0))(lx)

    # --- Anderson(type-II) accelerated fixed point on the log-gap vector ---
    hist_x, hist_f = [], []
    it_used, resid_sup = itmax, np.inf
    for it in range(itmax):
        f = apply_T(lg)
        r = f - lg
        resid_sup = float(np.max(np.abs(r[win_mask])))
        if resid_sup < tol:
            lg, it_used = f, it + 1
            break
        hist_x.append(lg.copy())
        hist_f.append(f.copy())
        if len(hist_x) > anderson_depth:
            hist_x.pop(0)
            hist_f.pop(0)
        mdep = len(hist_x)
        if mdep >= 2:
            Rm = np.stack([hist_f[j] - hist_x[j] for j in range(mdep)], axis=1)
            dR = Rm[:, 1:] - Rm[:, [0]]
            try:
                gam, *_ = np.linalg.lstsq(dR, -Rm[:, 0], rcond=None)
                alpha = np.empty(mdep)
                alpha[0] = 1.0 - gam.sum()
                alpha[1:] = gam
                lg = sum(alpha[j] * hist_f[j] for j in range(mdep))
            except np.linalg.LinAlgError:
                lg = f
        else:
            lg = f
    else:
        lg = f  # itmax reached; diagnostics report the residual

    # --- q̂ = window slope of the converged log gap; curvature = the drift analog ---
    xw, yw = lx[win_mask], lg[win_mask]
    xm, ym = xw.mean(), yw.mean()
    slope = float(np.sum((xw - xm) * (yw - ym)) / np.sum((xw - xm) ** 2))
    resid_fit = float(np.sqrt(np.mean((yw - (ym + slope * (xw - xm))) ** 2)))
    quad = np.polyfit(xw - xm, yw, 2)
    curvature = float(2.0 * quad[0])                 # d q_eff / d log X across the window
    q_hat = -slope
    diag = {
        "q_hat": float(q_hat), "curvature": curvature, "fit_resid_log": resid_fit,
        "anderson_iters": int(it_used), "anderson_resid_sup": resid_sup,
        "kappa": float(kappa), "h": float(h),
        "window_X_over_Xtop": (float(window[0]), float(window[1])),
    }
    healthy = (q_hat > 0.0 and resid_sup < 1e-6 and resid_fit < 0.25)
    out = ((float(q_hat), diag) if healthy
           else (None, {**diag, "reason": "unhealthy (q<=0, non-converged, or bad fit)"}))
    _MEMO[memo_k] = out
    return out
