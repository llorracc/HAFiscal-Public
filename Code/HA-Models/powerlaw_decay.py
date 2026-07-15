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

from HARK.interpolation import LinearInterp

__all__ = ["PowerLawDecayLinearInterp"]


class PowerLawDecayLinearInterp(LinearInterp):
    """``LinearInterp`` whose above-grid decay toward the limiting line is a
    POWER LAW in ``(x + h)`` instead of an exponential in ``x - x_top``.

    Construct exactly like ``LinearInterp(x, y, intercept_limit, slope_limit)``.
    When the base class engages decay (limits supplied, top slope distinct from
    ``slope_limit``), this subclass re-uses its ``decay_extrap_A``/``_B`` and
    replaces only the tail's functional form.
    """

    def __init__(self, x_list, y_list, intercept_limit=None, slope_limit=None,
                 lower_extrap=False):
        super().__init__(x_list, y_list, intercept_limit, slope_limit,
                         lower_extrap)
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
