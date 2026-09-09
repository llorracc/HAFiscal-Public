"""Power-law measured-Q tail rewrap for Step-1-class HARK-1D KinkedR hosts.

**STATUS: WIRED on the Step-1 estimation path** (``maybe_rewrap_types`` runs after
every solve inside ``FagerengObjFunc``), and since 2026-08-21/22 it is part of the
GRID-ONLY S1 default stack — the CHS branch below retrofits the hermite host in
place with the knot-measured exponent (flip ``4122ddba``; evidence:
``conclusions_private/2026-08-21_step1-grid-only-default-flip.md``). Historical
note: the F1.4 ruling (2026-07-24) had REVERTED an earlier wiring after its
neutrality gate failed at the legacy aXtraMax=20 grid (exp f0=0.0677 vs powerlaw
f0=0.0663, |dObj/Obj| ≈ 2e-2 — with the grid top ≪ hNrm the tail form moved the
targets); the measured-Q K·h̄ grid world (F7) later re-wired it with the grid top
where identification holds. The predicates here
(``powerlaw_form_active``/``measured_q_active``) remain the SST aliases consumed
by ``jax_mc_speedup/jax2b_powerlaw_tail.py``.

Original purpose (F1.4 of
plans/20260723_measured-q-tail-default-finalization_plan.md): bring the Step-1
(Target_AggMPCX_LiquWealth splurge/beta estimation) consumption functions onto
the SAME default tail the production Step-2/5 solver attaches — the power-law
decay toward the PF line ``MPCmin*(m + hNrm)`` with the locally-measured
exponent Q — instead of HARK's native EXPONENTIAL decay.

Mechanics (the fti_step1 "clean-pattern transplant" precedent): Step-1 types
are solved by HARK's stock KinkedR solver, whose ``solution[0].cFunc`` is
``LowerEnvelope(LinearInterp(mNrm, cNrm, intercept_limit=MPCmin*hNrm,
slope_limit=MPCmin), cFuncCnst, nan_bool=False)`` — the unconstrained branch
carries HARK's exp-decay extrapolation. ``rewrap_type_cfunc_powerlaw`` swaps
ONLY that unconstrained branch for a ``PowerLawDecayLinearInterp`` built on the
IDENTICAL knots and limits (in-sample values bit-identical; only the above-grid
tail form changes), exactly as the production attach block does per slice
(AggFiscalModel.solve_agg_cons_markov_alt). Only ``cFunc`` is swapped — the
graft precedent: Step-1's simulation and objective read nothing else
(vPfunc/vPPfunc are never consulted; see the 2026-07-23 F1 recon).

Measured Q: the same ``local_q_tail.local_q_from_knots`` two-secant estimator
as production, gated by the same ``HAFISCAL_PF_DECAY_Q`` predicate. At Step-1's
legacy grid (``aXtraMax=20`` vs ``hNrm~200``) the ``(x+h)`` log-leverage is
MARGINAL: the top-3-knot span measures ~0.051, just above the 0.05
identifiability gate, so the estimator runs and attaches a genuinely LOCAL
(shallow-depth, hence large — the dual-process Q(x) profile is sigmoid, not
flat) exponent; on any grid below the gate it issues the one-shot "too
shallow" verdict and the ctor falls back to the slope-derived Q — the SAME
semantics as the production attach at any too-shallow grid.

Fixed-point caveat (documented, accepted): the rewrap is post-solve, so the
backward iterations themselves still used HARK's exp tail for above-grid
continuation evaluations. The F1.4 owner gate is estimation-NEUTRALITY of the
whole port (objective moves < ~1e-4 relative), which bounds the combined
effect; a deeper in-solve port would require patching HARK's solver internals
and is not warranted while the neutrality gate passes.

Gating: ``maybe_rewrap_types`` is active only when the power-law PF-decay form
is the effective default (``HAFISCAL_PF_DECAY_EXTRAP`` truthy and not ``exp``
— same predicate as the production attach); under ``exp``/``0`` it is a no-op.
No new env flags; the tail-affecting state is fully described by the existing
``HAFISCAL_PF_DECAY_EXTRAP`` / ``HAFISCAL_PF_DECAY_Q`` (both already in the
solution-cache key whitelist).
"""
from __future__ import annotations

import os
import sys

import numpy as np

_HA_MODELS = os.path.dirname(os.path.abspath(__file__))
if _HA_MODELS not in sys.path:
    sys.path.insert(0, _HA_MODELS)  # powerlaw_decay, local_q_tail

__all__ = ["powerlaw_form_active", "measured_q_active",
           "rewrap_type_cfunc_powerlaw", "maybe_rewrap_types"]


def powerlaw_form_active():
    """True iff the power-law PF-decay form is the effective default.

    SST delegation (owner ruling 2026-07-24): the predicate lives in
    ``grid_sizing.powerlaw_form_active`` — one implementation shared with the
    production attach, the FTI router, the NAMG guard and the JAX-2B gate.
    This thin alias keeps the existing import surface (jax2b + tests).
    """
    from grid_sizing import powerlaw_form_active as _f
    return _f()


def measured_q_active():
    """True iff the measured (local two-secant) Q source is selected on top of
    the power-law form — grid_sizing's ``powerlaw_measured_active`` SST
    predicate.

    NOTE (SST alignment, 2026-07-24): historically this alias tested ONLY the
    Q-source spelling; every wired caller (the Step-1 rewrap gate, the JAX-2B
    attach) already gates it behind ``powerlaw_form_active()``, so delegating
    to the joint predicate is call-site-equivalent and removes drift risk.
    """
    from grid_sizing import powerlaw_measured_active as _f
    return _f()


def rewrap_type_cfunc_powerlaw(ThisType):
    """Swap a solved Step-1 type's unconstrained cFunc branch to the power-law
    tail (measured Q where identifiable). Returns (bool swapped, str reason).

    Never raises on an unexpected host shape — returns (False, reason) and the
    stock exp-tailed policy is kept (the transparent-fallback convention).
    """
    from HARK.interpolation import LinearInterp, LowerEnvelope
    from powerlaw_decay import PowerLawDecayLinearInterp
    sol = getattr(ThisType, "solution", [None])[0]
    if sol is None:
        return False, "no solution"
    cf = getattr(sol, "cFunc", None)
    if not isinstance(cf, LowerEnvelope) or len(getattr(cf, "functions", [])) != 2:
        return False, f"cFunc not a 2-branch LowerEnvelope ({type(cf).__name__})"
    unc, cnst = cf.functions
    if (isinstance(unc, PowerLawDecayLinearInterp)
            or getattr(unc, "decay_extrap_form", "") in ("powerlaw", "mom_chart")):
        # Covers both a prior rewrap AND a farfield-mode solver-level retrofit
        # (PowerLawDecayCHSInterp class-swap): never override an installed
        # power-law tail — the farfield exponent comes from the mini-solve,
        # not from the knot secants (mode orthogonality, 2026-08-21).
        return False, "already power-law"
    mpc_min = float(sol.MPCmin)
    h = float(sol.hNrm)
    if not (np.isfinite(h) and mpc_min > 0.0):
        return False, f"RIC/FHWC fails (MPCmin={mpc_min}, hNrm={h})"
    if type(unc) is not LinearInterp:
        # hermite60 host: solve_one_period_ConsKinkedR under CubicBool builds
        # HARK's scipy-backed CubicHermiteInterp. Measure the local Q from the
        # (knot-extended) top secants and retrofit IN PLACE via
        # powerlaw_decay.retrofit_powerlaw — the class-swap preserves every
        # interior coefficient (incl. the kink-segment surgery) and changes
        # only the above-top form. Found by the grid-only comprehensive
        # battery 2026-08-21: without this branch the hermite60+tail-knots
        # candidate silently kept the stock exp tail ("not LinearInterp"),
        # so the method the paper describes never reached the computation.
        from powerlaw_decay import retrofit_powerlaw
        try:
            x = np.asarray(unc.x_list, dtype=float)
            y = np.asarray(unc.y_list, dtype=float)
        except Exception:
            return False, (f"unconstrained branch not LinearInterp and exposes "
                           f"no knot lists ({type(unc).__name__})")
        if not measured_q_active():
            return False, f"measured Q not active for CHS host ({type(unc).__name__})"
        from local_q_tail import local_q_from_knots
        lq = local_q_from_knots(x[1:], y[1:], h, mpc_min)
        if not lq["ok"]:
            # The expected verdict on a basis-only (no tail knots) hermite
            # grid: too shallow to identify Q locally — keep the stock tail,
            # exactly as the LinearInterp path warns-and-falls-back.
            return False, "measured Q unidentifiable on CHS host (too-shallow grid)"
        if retrofit_powerlaw(unc, lq["Q"], (lq["Q1"], lq["Q2"], lq["drift"])):
            return True, "ok (CHS in-place retrofit)"
        return False, "retrofit_powerlaw validity guards refused (stock tail kept)"
    if not getattr(unc, "decay_extrap", False):
        # Host solver attached no decay limits (e.g. degenerate slope match):
        # nothing to re-form.
        return False, "host LinearInterp has no decay extrapolation"
    x = np.asarray(unc.x_list, dtype=float)
    y = np.asarray(unc.y_list, dtype=float)
    ctor_kw = {}
    if measured_q_active():
        from local_q_tail import local_q_from_knots
        # Exclude the bottom boundary knot, as the production attach does
        # (only the top-of-grid knots matter to the estimator anyway).
        lq = local_q_from_knots(x[1:], y[1:], h, mpc_min)
        if lq["ok"]:
            ctor_kw = dict(decay_extrap_Q=lq["Q"],
                           q_diagnostics=(lq["Q1"], lq["Q2"], lq["drift"]))
        # ok=False => slope-derived Q inside the ctor (the estimator already
        # issued its one-shot "too shallow" fallback warning — the expected
        # verdict at Step-1's aXtraMax=20 << hNrm~200 grid).
    new_unc = PowerLawDecayLinearInterp(
        x, y,
        intercept_limit=float(unc.intercept_limit),
        slope_limit=float(unc.slope_limit),
        **ctor_kw,
    )
    if getattr(new_unc, "decay_extrap_form", "exp") != "powerlaw":
        # Ctor validity guards refused (warned already) — keep the stock policy.
        return False, "PowerLawDecayLinearInterp validity guards refused"
    nan_bool = cf.compare is np.nanmin
    sol.cFunc = LowerEnvelope(new_unc, cnst, nan_bool=nan_bool)
    return True, "ok"


def maybe_rewrap_types(type_list):
    """Wire-in point: rewrap every solved type IF the power-law default is
    active; no-op (returns 0) otherwise. Returns the number of types swapped."""
    if not powerlaw_form_active():
        return 0
    n = 0
    for t in type_list:
        ok, _reason = rewrap_type_cfunc_powerlaw(t)
        n += int(ok)
    return n
