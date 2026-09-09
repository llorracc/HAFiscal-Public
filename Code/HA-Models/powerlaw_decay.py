"""HAFiscal-local power-law decay tail for the pinned HARK's ``LinearInterp``.

The HARK PR (worktree ``HARK-pr-aggshock-pf-decay``, branch
``fix-aggshock-pf-decay-extrap``) adds ``LinearInterp(decay_extrap_form='powerlaw')``
upstream. The venv's PINNED HARK predates it, so this module provides the same
tail as a subclass — the PR-3-local / PR-1-canonical pattern (cf. BUG-062).
Selected via ``HAFISCAL_PF_DECAY_EXTRAP=powerlaw`` (any other truthy value keeps
the legacy exponential attach; see ``docs/ENV_FLAGS.md``).

Math (identical to the HARK-PR implementation; derivation:
``conclusions_private/2026-06-24_buffer-stock-decay-power-law-derivation.md`` §8):
the gap below the limiting line ``intercept_limit + slope_limit*x`` is

    gap(x) = A * ((x + h)/(x_top + h))**(-Q),   h = intercept_limit/slope_limit,
    Q = B * (x_top + h),

with ``A = decay_extrap_A`` (level gap at the top knot) and
``B = decay_extrap_B`` exactly as the exponential path computes them — so the
power law matches the LEVEL and the SLOPE of the interpolant at the top knot,
the same two conditions the exponential matches, and needs no extra parameters.
For a consumption function the limiting line is ``MPCmin*(m + hNrm)``, so ``h``
is human wealth. Evaluated via ``exp(-Q*log1p(.))`` for numerical stability;
for ``x - x_top << x_top + h`` it reduces to the exponential (which is exactly
why fits over a short span above the grid cannot distinguish the two forms,
while the tails differ materially — the true buffer-stock gap is power-law).

Validity guards (all hold for a converged consumption function by
Carroll-Kimball concavity; the AggFiscalModel attach site additionally HALTs on
above-line knots before ever constructing this class): top knot strictly below
the line (``A > 0``), approaching it (``B > 0``), ``slope_limit > 0``, positive
pivot ``x_top + h``. On violation: warn and disable decay extrapolation
entirely rather than risk a divergent tail.

Identity vs the HARK-PR implementation is asserted by
``decay_form/t0_solve_level_exp_vs_powerlaw.py`` (part 1).
"""

import warnings

import numpy as np

from HARK.interpolation import CubicInterp, LinearInterp

__all__ = ["PowerLawDecayLinearInterp", "PowerLawDecayCubicHermiteInterp"]


class PowerLawDecayLinearInterp(LinearInterp):
    """``LinearInterp`` whose above-grid decay toward the limiting line is a
    POWER LAW in ``(x + h)`` instead of an exponential in ``x - x_top``.

    Construct exactly like ``LinearInterp(x, y, intercept_limit, slope_limit)``.
    When the base class engages decay (limits supplied, top slope distinct from
    ``slope_limit``), this subclass re-uses its ``decay_extrap_A``/``_B`` and
    replaces only the tail's functional form.
    """

    def __init__(self, x_list, y_list, intercept_limit=None, slope_limit=None,
                 lower_extrap=False, decay_extrap_Q=None, q_diagnostics=None):
        # decay_extrap_Q: optional explicit exponent override (the local two-secant
        # estimate, HAFISCAL_PF_DECAY_Q=local2 — plans/20260722_local-two-secant-
        # tail-q_plan.md). When None, Q = B*(x_top+h) from the top-knot level+slope
        # pair exactly as before. q_diagnostics: optional (Q1, Q2, drift) tuple
        # stashed on the interpolant for post-solve inspection.
        super().__init__(x_list, y_list, intercept_limit, slope_limit,
                         lower_extrap)
        self._q_override = None if decay_extrap_Q is None else float(decay_extrap_Q)
        self.local_q_diag = q_diagnostics
        self.decay_extrap_form = "exp"  # until validated below
        if not getattr(self, "decay_extrap", False):
            return
        level_diff = float(self.decay_extrap_A)
        ok = (
            slope_limit is not None
            and slope_limit > 0.0
            and level_diff > 0.0
            and float(self.decay_extrap_B) > 0.0
        )
        if ok:
            pivot = float(self.x_list[-1]) + intercept_limit / slope_limit
            ok = pivot > 0.0
        if not ok:
            warnings.warn(
                "PowerLawDecayLinearInterp: the top knot is not strictly below "
                "the limiting line with slope strictly above slope_limit "
                f"(A={level_diff:.6g}, B={float(self.decay_extrap_B):.6g}, "
                f"slope_limit={slope_limit!r}); disabling decay extrapolation "
                "for this interpolant."
            )
            self.decay_extrap = False
            return
        self.decay_extrap_pivot = pivot
        if self._q_override is not None and self._q_override > 0.0:
            # Local two-secant Q (validity guards above still gate the attach; the
            # override only replaces WHICH exponent the power law uses).
            self.decay_extrap_Q = self._q_override
        else:
            self.decay_extrap_Q = float(self.decay_extrap_B) * pivot
        self.decay_extrap_form = "powerlaw"

    def _evalOrDer(self, x, _eval, _Der):
        out = super()._evalOrDer(x, _eval, _Der)
        if not (getattr(self, "decay_extrap", False)
                and getattr(self, "decay_extrap_form", "exp") == "powerlaw"):
            return out
        x = np.asarray(x)
        above = x > self.x_list[-1]
        if not np.any(above):
            return out
        x_temp = x[above] - self.x_list[-1]
        # gap = A * ((x + h)/(x_top + h))**(-Q); x + h = x_temp + pivot
        decay = self.decay_extrap_A * np.exp(
            -self.decay_extrap_Q * np.log1p(x_temp / self.decay_extrap_pivot)
        )
        k = 0
        if _eval:
            out[k][above] = (self.intercept_limit + self.slope_limit * x[above]
                             - decay)
            k += 1
        if _Der:
            # d(-gap)/dx = +(Q/(x + h)) * gap
            out[k][above] = (self.slope_limit
                             + self.decay_extrap_Q
                             / (x_temp + self.decay_extrap_pivot) * decay)
        return out


class PowerLawDecayCubicHermiteInterp(CubicInterp):
    """``CubicInterp`` (level + slope matched at every knot — the EGM-exact
    Hermite slices of the T2a arm, plan 20260803-2030h) whose above-grid decay
    toward the limiting line is the SAME certified power law as
    ``PowerLawDecayLinearInterp``.

    HARK's CubicInterp stores its above-top exponential-gap extrapolation in
    ``coeffs[n] = [intercept_limit, slope_limit, gap, slope_diff/gap]`` (eval:
    ``b + m*x - gap*exp(alpha*coeffs[n,3])``) — i.e. A = gap and
    B = -coeffs[n,3], the exact objects the linear tail uses. This subclass
    replaces only the above-top functional form; interior cubic-Hermite
    evaluation and the derivative are inherited untouched.

    Guards mirror the linear subclass: A>0, B>0, slope_limit>0, pivot>0 —
    else warn and keep the base exponential tail (never a divergent form).

    OWNER RULING (2026-08-04): the convergence distance measures LEVEL
    gridpoints only — ``dydx_list`` is excluded from ``distance_criteria``
    (the derivative field is determined by the envelope condition at the
    values' fixed point; including it made the Fritsch–Carlson clamp's
    active-set toggling near the kink oscillate the measured distance above
    tolerance, exploding iteration counts at sparse grids — plan
    20260803-2030h §3b).
    """

    distance_criteria = ["x_list", "y_list"]

    def __init__(self, x_list, y_list, dydx_list, intercept_limit=None,
                 slope_limit=None, lower_extrap=False, decay_extrap_Q=None,
                 q_diagnostics=None):
        super().__init__(x_list, y_list, dydx_list, intercept_limit,
                         slope_limit, lower_extrap)
        self._q_override = None if decay_extrap_Q is None else float(decay_extrap_Q)
        self.local_q_diag = q_diagnostics
        self.decay_extrap_form = "exp"
        if intercept_limit is None or slope_limit is None:
            return
        A = float(self.coeffs[self.n][2])           # gap at the top knot
        B = -float(self.coeffs[self.n][3])          # decay rate (>0 healthy)
        ok = slope_limit > 0.0 and A > 0.0 and B > 0.0
        if ok:
            pivot = float(self.x_list[-1]) + intercept_limit / slope_limit
            ok = pivot > 0.0
        if not ok:
            warnings.warn(
                "PowerLawDecayCubicHermiteInterp: top knot not strictly below "
                f"the limiting line with approaching slope (A={A:.6g}, "
                f"B={B:.6g}, slope_limit={slope_limit!r}); keeping the base "
                "exponential tail for this interpolant.")
            return
        self._pl_A = A
        self._pl_intercept = float(intercept_limit)
        self._pl_slope = float(slope_limit)
        self.decay_extrap_pivot = pivot
        if self._q_override is not None and self._q_override > 0.0:
            self.decay_extrap_Q = self._q_override
        else:
            self.decay_extrap_Q = B * pivot
        self.decay_extrap_form = "powerlaw"

    def _pl_gap(self, x_above):
        x_temp = np.asarray(x_above) - self.x_list[-1]
        decay = self._pl_A * np.exp(
            -self.decay_extrap_Q * np.log1p(x_temp / self.decay_extrap_pivot))
        return x_temp, decay

    def _evaluate(self, x):
        y = super()._evaluate(x)
        if getattr(self, "decay_extrap_form", "exp") != "powerlaw":
            return y
        x = np.asarray(x)
        above = x > self.x_list[-1]
        if np.any(above):
            _, decay = self._pl_gap(x[above])
            y[above] = self._pl_intercept + self._pl_slope * x[above] - decay
        return y

    def _der(self, x):
        dydx = super()._der(x)
        if getattr(self, "decay_extrap_form", "exp") != "powerlaw":
            return dydx
        x = np.asarray(x)
        above = x > self.x_list[-1]
        if np.any(above):
            x_temp, decay = self._pl_gap(x[above])
            dydx[above] = (self._pl_slope
                           + self.decay_extrap_Q
                           / (x_temp + self.decay_extrap_pivot) * decay)
        return dydx

    def _evalAndDer(self, x):
        # HARKinterpolator1D.eval_with_derivative routes here; keep both
        # consistent with the overridden pieces.
        return self._evaluate(x), self._der(x)


def retrofit_powerlaw(interp, decay_extrap_Q, q_diagnostics=None):
    """IN-PLACE retrofit of a stock HARK ``LinearInterp``/``CubicInterp`` (built WITH
    limits) into its PowerLawDecay* counterpart with an explicit exponent override.

    Motivation (2026-08-21, remedy-F/S1 arc): Step-1's cFuncs are built inside HARK's
    ``solve_one_period_ConsKinkedR`` — including the kink-segment coefficient surgery on
    the cubic path — so REBUILDING from knots would not be faithful. A class-swap plus
    the ctor's post-``super`` attach logic preserves every coefficient below the top
    bit-for-bit and changes ONLY the above-top functional form. Guards mirror the ctors:
    on any unhealthy geometry the object is left untouched (stock exponential tail) and
    the function returns False.

    ``decay_extrap_Q`` is the far-field exponent (farfield_tail_q.farfield_q) — the
    amplitude stays pinned by top-knot LEVEL continuity exactly as in the ctors.
    """
    from HARK.interpolation import CubicInterp as _HC, LinearInterp as _HL
    q = None if decay_extrap_Q is None else float(decay_extrap_Q)
    if q is None or q <= 0.0:
        return False
    if isinstance(interp, PowerLawDecayLinearInterp) or isinstance(
            interp, PowerLawDecayCubicHermiteInterp):
        # already powerlaw: just override the exponent
        interp._q_override = q
        interp.decay_extrap_Q = q
        interp.local_q_diag = q_diagnostics
        return True
    if _HARK_CHS is not None and type(interp) is _HARK_CHS:
        # HARK's scipy-backed cubic (what solve_one_period_ConsKinkedR builds): the final
        # coeffs row is [intercept_limit, slope_limit, gap, slope_diff/gap] — same A/B
        # convention as the legacy class.
        row = interp.coeffs[interp.n]
        intercept, slope, A = float(row[0]), float(row[1]), float(row[2])
        ok = slope > 0.0 and A > 0.0
        if ok:
            pivot = float(interp.x_list[interp.n - 1]) + intercept / slope
            ok = pivot > 0.0
        if not ok:
            warnings.warn("retrofit_powerlaw: unhealthy CHS top-knot geometry "
                          f"(A={A:.6g}, slope_limit={slope:.6g}); keeping the stock tail.")
            return False
        interp.__class__ = PowerLawDecayCHSInterp
        interp._q_override = q
        interp.local_q_diag = q_diagnostics
        interp._pl_A = A
        interp._pl_intercept = intercept
        interp._pl_slope = slope
        interp.decay_extrap_pivot = pivot
        interp.decay_extrap_Q = q
        interp.decay_extrap_form = "powerlaw"
        return True
    if isinstance(interp, _HC) and type(interp) is _HC:
        intercept = getattr(interp, "intercept_limit", None)
        slope = getattr(interp, "slope_limit", None)
        if intercept is None or slope is None or not np.isfinite(slope):
            return False
        A = float(interp.coeffs[interp.n][2])
        B = -float(interp.coeffs[interp.n][3])
        ok = slope > 0.0 and A > 0.0 and B > 0.0
        if ok:
            pivot = float(interp.x_list[-1]) + intercept / slope
            ok = pivot > 0.0
        if not ok:
            warnings.warn("retrofit_powerlaw: unhealthy cubic top-knot geometry "
                          f"(A={A:.6g}, B={B:.6g}); keeping the exponential tail.")
            return False
        interp.__class__ = PowerLawDecayCubicHermiteInterp
        interp._q_override = q
        interp.local_q_diag = q_diagnostics
        interp._pl_A = A
        interp._pl_intercept = float(intercept)
        interp._pl_slope = float(slope)
        interp.decay_extrap_pivot = pivot
        interp.decay_extrap_Q = q
        interp.decay_extrap_form = "powerlaw"
        return True
    if isinstance(interp, _HL) and type(interp) is _HL:
        if not getattr(interp, "decay_extrap", False):
            return False
        intercept = getattr(interp, "intercept_limit", None)
        slope = getattr(interp, "slope_limit", None)
        A = float(interp.decay_extrap_A)
        B = float(interp.decay_extrap_B)
        ok = (slope is not None and slope > 0.0 and A > 0.0 and B > 0.0)
        if ok:
            pivot = float(interp.x_list[-1]) + intercept / slope
            ok = pivot > 0.0
        if not ok:
            warnings.warn("retrofit_powerlaw: unhealthy linear top-knot geometry "
                          f"(A={A:.6g}, B={B:.6g}); keeping the exponential tail.")
            return False
        interp.__class__ = PowerLawDecayLinearInterp
        interp._q_override = q
        interp.local_q_diag = q_diagnostics
        interp.decay_extrap_pivot = pivot
        interp.decay_extrap_Q = q
        interp.decay_extrap_form = "powerlaw"
        return True
    return False


try:  # HARK's scipy-backed cubic (the class the 0.17 KinkedR solver actually builds)
    from HARK.interpolation import CubicHermiteInterp as _HARK_CHS
except Exception:  # pragma: no cover
    _HARK_CHS = None

if _HARK_CHS is not None:
    class PowerLawDecayCHSInterp(_HARK_CHS):
        """Retrofit twin of HARK's scipy-backed ``CubicHermiteInterp`` carrying the
        certified power-law above-top form. Never constructed directly:
        ``retrofit_powerlaw`` swaps ``__class__`` on a stock instance (preserving every
        interior coefficient bit-for-bit, including the KinkedR kink-segment surgery) and
        installs the attach attributes. ``distance_criteria`` mirrors the stock class so
        solve-convergence semantics are unchanged by the retrofit."""

        distance_criteria = ["x_list", "y_list", "dydx_list"]

        def _pl_gap_chs(self, x_above):
            x_temp = np.asarray(x_above) - self.x_list[self.n - 1]
            decay = self._pl_A * np.exp(
                -self.decay_extrap_Q * np.log1p(x_temp / self.decay_extrap_pivot))
            return x_temp, decay

        def _eval_helper(self, x, out_bot, out_top):
            y = super()._eval_helper(x, out_bot, out_top)
            if getattr(self, "decay_extrap_form", "exp") == "powerlaw" and np.any(out_top):
                _, decay = self._pl_gap_chs(x[out_top])
                y[out_top] = self._pl_intercept + self._pl_slope * x[out_top] - decay
            return y

        def _der_helper(self, x, out_bot, out_top):
            d = super()._der_helper(x, out_bot, out_top)
            if getattr(self, "decay_extrap_form", "exp") == "powerlaw" and np.any(out_top):
                x_temp, decay = self._pl_gap_chs(x[out_top])
                d[out_top] = (self._pl_slope
                              + self.decay_extrap_Q
                              / (x_temp + self.decay_extrap_pivot) * decay)
            return d


# ── PR co-debug dispatch (owner charge 2026-08-22: simultaneous debugging of HARK
# PR #1818 and this machine's consumers). Under HAFISCAL_TAIL_IMPL=pr the flown
# retrofit entrypoint is REBOUND to the PR module's implementation (loaded from the
# PR worktree against the PINNED HARK by hark_tail_pr.py; signature-identical).
# Every flown consumer imports `retrofit_powerlaw` at CALL time, so the rebinding
# reaches them. Default `vendored` = byte-identical to pre-flag behavior. Parity
# tripwire: test_step1_tail_attach.py::test_pr_impl_parity.
try:
    import hark_tail_pr as _htp
    if _htp.pr_mode_active():
        retrofit_powerlaw = _htp.load().retrofit_powerlaw  # noqa: F811
        print(f"[tail-impl] retrofit_powerlaw -> PR ({_htp.source()})")
except Exception as _e:  # the co-debug layer must never break the vendored path
    import warnings as _w
    _w.warn(f"hark_tail_pr dispatch unavailable ({_e!r}); vendored retrofit kept.")


def decay_linear_ctor(environ=None):
    """The LinearInterp constructor the PRODUCTION attach uses — one selection, shared by every solver.

    `PowerLawDecayLinearInterp` when the power-law PF-decay form is active, else HARK's `LinearInterp`. The form
    test is `grid_sizing.powerlaw_form_active` — THE SST predicate (owner ruling 2026-07-24), the same one
    `AggFiscalModel.solve_agg_cons_markov_alt` uses, so a solver that calls this cannot drift from the PE model's
    tail treatment. Added 2026-08-30 for BUG-106 (the HANK block's vendored Markov solver was building its
    consumption function with HARK's plain linear PF asymptote while the PE model attached the measured power-law
    decay — the same object by two methods).
    """
    from grid_sizing import powerlaw_form_active
    return PowerLawDecayLinearInterp if powerlaw_form_active(environ) else LinearInterp


def decay_cubic_ctor(environ=None):
    """The cubic twin of `decay_linear_ctor`: `PowerLawDecayCubicHermiteInterp` when the power-law form is active,
    else HARK's `CubicInterp`. Same SST predicate, same reason (BUG-106)."""
    from grid_sizing import powerlaw_form_active
    return PowerLawDecayCubicHermiteInterp if powerlaw_form_active(environ) else CubicInterp


def measured_tail_q_kwargs(m_knots, c_knots, hNrm, MPCmin, environ=None):
    """Constructor kwargs carrying the MEASURED tail exponent for the shared power-law tail, or ``{}``.

    One call reproducing the PE attach site's exponent selection (`AggFiscalModel.solve_agg_cons_markov_alt`, the
    `_pf_local2` block) for the vendored `ConsMarkovModel` solver — dual-path sweep 2026-09-02 §4 row Q1, executed
    as the Phase-2 MEASUREMENT of 2026-09-03 (a candidate for the owner's ruling: not adopted, goldens not re-pinned).

    Why: BUG-106 (2026-08-30) shared the tail FORM between the two solvers through `decay_linear_ctor` /
    `decay_cubic_ctor`, but the PE attaches the power law with the exponent MEASURED from the solved top-of-grid
    knots (`local_q_tail.local_q_from_knots`; `HAFISCAL_PF_DECAY_Q=measured`, the default in both worlds since
    2026-08-24, BUG-089) while the vendored solver still let the constructor derive Q from the top segment's
    level+slope pair — the exponent gap `step4/pe_anchor_gate.EXPECTED['cFunc/cap_atom']` declares.

    m_knots, c_knots : the solved knots WITHOUT the synthetic bottom point (the PE passes `m_temp[1:]`; the vendored
                       solver `mNrm[1:]` — `ConsMarkovSolver.solve` prepends the (mNrmMin_i, 0) knot).
    hNrm, MPCmin     : the slice's PF limits, line = MPCmin*(m + hNrm) — the same pair handed to the constructor.
    Returns ``{}`` (the constructor derives Q exactly as before) when the power-law form is off (HARK's plain
    interpolants take no exponent), when the exponent mode is not the measured family, or when the estimator
    declines (NaN: fewer than three usable knots / no log-leverage / non-positive gap) — the PE's own fallbacks.
    The estimator runs with diagnostics off (`measured_q_for_solver`, the BUG-089 solver hook), so the PE attach
    layer's drift advisory keeps counting only its own rounds.
    """
    import os
    from grid_sizing import powerlaw_form_active
    e = os.environ if environ is None else environ
    if not powerlaw_form_active(e):
        return {}
    if e.get("HAFISCAL_PF_DECAY_Q", "measured").strip().lower() not in ("local2", "measured", "farfield"):
        return {}
    from local_q_tail import measured_q_for_solver
    q = measured_q_for_solver(m_knots, c_knots, MPCmin, hNrm)
    return {"decay_extrap_Q": float(q)} if np.isfinite(q) else {}
