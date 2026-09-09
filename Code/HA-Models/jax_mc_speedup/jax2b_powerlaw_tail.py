"""Power-law measured-Q tail attach for the JAX-2B solve paths (F1.1, 2026-07-23).

plans/20260723_measured-q-tail-default-finalization_plan.md F1: the JAX-2B /
2B-vmap kernels replace HARK's ``solve_agent`` loop and wrap their output
tables in ``_JAXcFuncWrap`` — pure-numpy per-C-slice linear interpolation whose
above-top-knot behavior is NAIVE-LINEAR (last-segment slope forever). Under the
power-law PF-decay DEFAULT that was a LIVE default-path gap (the stock solver
attaches ``PowerLawDecayLinearInterp`` per (state, C-slice); the 2B wrapper
attached nothing). Owner pre-authorization (b): implement the attach if it is a
small clean post-solve construction with parity gates — this module is that
construction.

Design — a bounded post-solve wrap, mirroring the stock attach block
(``AggFiscalModel.solve_agg_cons_markov_alt``: the per-C-slice ``if _pf_decay:``
block, ``AggFiscalModel.py:2616-2686`` as of 2026-09-03 — locate it by its
comment "Attach the per-(CURRENT-STATE-i, C-slice-n) AD-AWARE PF asymptote";
the gating prologue ``_pf_decay``/``_pf_slice_ctor``/``_pf_local2`` sits at
:2341-2440) exactly. The mirror is a HAND COPY of that block, not an import
(the block is inline in the goldens-bearing solver), so the two policies are
BOUND by a parity gate rather than by construction:
``jax_mc_speedup/test_jax2b_attach_decision_parity.py`` executes the live PE
block on the same knots and asserts the same decision, the same exponent and
the same tail (sweep-table row Q20, ``conclusions_private/
2026-09-02_dual-path-sweep_table.md`` §4; Phase-2 brief 2026-09-03).

* Per agent, compute the SAME AD-aware limits the stock solver uses —
  ``compute_pf_decay_limits(agent.MrkvArray[0], agent.Rfree, ...)`` gives
  (MPCmin, h_AD[(Ccount, StateCount)]).
* Per (state i, C-slice n), on the wrapper's own augmented knot arrays
  ``x_grids[n] = [0] + (mNrm[n] - BoroCnstNat[n])``, ``f_values[n] = [0] +
  cNrm[n]`` (identical structure to the stock solver's ``m_temp``/``c_temp``):
  apply the stock attach conditions (``level_diff > tol`` and ``slope_top >=
  MPCmin``) and build the SAME ``PowerLawDecayLinearInterp`` — including the
  measured-Q kwargs from ``local_q_tail`` under the production
  ``HAFISCAL_PF_DECAY_Q`` predicate.
* ``_JAXcFuncWrapPowerlawTail`` evaluates the parent's naive-linear blend and
  then adds, ONLY for above-top queries, the per-contributing-slice correction
  ``tail_n(x) - linear_n(x)`` blended with the parent's own C-weights. For
  in-sample queries the correction is exactly zero, so the wrapper is
  BIT-IDENTICAL to the plain ``_JAXcFuncWrap`` there (parity gate A);
  ``derivativeX`` (finite-difference) and the ``_JAXvPfuncWrap`` marginal
  value inherit the tail automatically.

Deviation from the stock block (documented): the stock solver HALTs on an
above-line top knot (Carroll-Kimball, an invariant of ITS constrained-PF-start
backward iterates). The JAX-2B fixed point carries a ~kernel-parity (~1e-3
class) offset from the stock one, so a hard HALT here would be brittle against
parity noise on a knot that sits close to the line; an above-line knot instead
WARNS once per solve and skips the attach for that slice (keeping the parent's
naive-linear there).

Gating: attach iff the power-law form is the effective default
(``HAFISCAL_PF_DECAY_EXTRAP`` truthy, not ``exp``) and
``HAFISCAL_JAX2B_ALLOW_NO_TAIL`` != 1 (the escape hatch: restores the
pre-attach legacy wrapper for benchmarking/back-compat; IN the solution-cache
key — it changes the produced cFunc under fixed other flags). Under ``exp``
there is no attach either: 2B never had an exponential attach, and that
historical behavior is exactly what the escape/legacy states reproduce.
"""
from __future__ import annotations

import os
import sys
import warnings

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_HA_MODELS = os.path.normpath(os.path.join(_HERE, ".."))
_FPC = os.path.join(_HA_MODELS, "FromPandemicCode")
for _p in (_HA_MODELS, _FPC, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Single source of truth for the gating predicates (Step-1 helper, F1.4).
from step1_powerlaw_tail import measured_q_active, powerlaw_form_active  # noqa: E402
# The plain 2B wrapper (FromPandemicCode; imports jax — the 2B path needs jax
# anyway, and this module is only imported from the 2B drop-in construction).
from jax_solver_drop_in import _JAXcFuncWrap  # noqa: E402

__all__ = ["attach_enabled", "build_tail_solution",
           "build_tail_solution_from_params", "_JAXcFuncWrapPowerlawTail",
           "powerlaw_form_active", "measured_q_active"]


def attach_enabled():
    """True iff the 2B output should get the power-law tail attach."""
    if os.environ.get("HAFISCAL_JAX2B_ALLOW_NO_TAIL", "0") == "1":
        return False
    return powerlaw_form_active()


class _JAXcFuncWrapPowerlawTail(_JAXcFuncWrap):
    """``_JAXcFuncWrap`` + per-(C-slice) power-law decay tails above the top knot.

    ``tail_funcs[n]`` is a ``PowerLawDecayLinearInterp`` (or None = keep
    naive-linear) per C-slice, built on the SAME augmented knots as
    ``self._x_grids[n]``/``self._f_values[n]``. In-sample evaluation is the
    parent's bit-identical path plus an exactly-zero correction; above a
    slice's top knot the correction replaces the parent's naive-linear
    last-segment extrapolation with the power-law tail, blended in C with the
    parent's own bracketing weights. ``derivativeX`` (finite difference on
    ``self``) and ``distance`` (cNrm tables) inherit unchanged.
    """

    def __init__(self, cNrm_i, mNrm_i, BoroCnstNat_i, Cgrid, BoroCnstArt,
                 tail_funcs=None):
        super().__init__(cNrm_i, mNrm_i, BoroCnstNat_i, Cgrid, BoroCnstArt)
        self.tail_funcs = tail_funcs if tail_funcs is not None else [None] * len(self.Cgrid)
        self._x_top = self._x_grids[:, -1].copy()
        self._c_top = self._f_values[:, -1].copy()
        self._slope_top = ((self._f_values[:, -1] - self._f_values[:, -2])
                           / (self._x_grids[:, -1] - self._x_grids[:, -2]))

    def _slice_correction(self, n, x):
        """tail_n(x) - naive_linear_n(x), zero where x <= x_top_n."""
        corr = np.zeros_like(x, dtype=float)
        fn = self.tail_funcs[n]
        if fn is None:
            return corr
        above = x > self._x_top[n]
        if not np.any(above):
            return corr
        xa = x[above]
        lin = self._c_top[n] + self._slope_top[n] * (xa - self._x_top[n])
        corr[above] = np.asarray(fn(xa), dtype=float) - lin
        return corr

    def __call__(self, m, C):
        m_arr = np.asarray(m)
        C_arr = np.asarray(C)
        orig_shape = m_arr.shape
        m_flat = np.atleast_1d(m_arr).flatten().astype(float)
        C_flat = np.atleast_1d(C_arr).flatten().astype(float)
        if C_flat.shape[0] == 1 and m_flat.shape[0] > 1:
            C_flat = np.broadcast_to(C_flat, m_flat.shape)
        if m_flat.shape[0] == 1 and C_flat.shape[0] > 1:
            m_flat = np.broadcast_to(m_flat, C_flat.shape)

        # Parent evaluation (bit-identical path, incl. constraint + NaN mask)
        base = np.atleast_1d(np.asarray(
            super().__call__(m_flat, C_flat), dtype=float))

        # Above-top correction: mirror the parent's C-bracketing/weights
        bn_at_C = np.interp(C_flat, self.Cgrid, self.BoroCnstNat)
        m_shifted = m_flat - bn_at_C
        if np.any(m_shifted > np.min(self._x_top)):
            y_grid = self.Cgrid
            Ny = y_grid.shape[0]
            y_pos = np.clip(np.searchsorted(y_grid, C_flat, side="left"), 1, Ny - 1)
            alpha_y = (C_flat - y_grid[y_pos - 1]) / (y_grid[y_pos] - y_grid[y_pos - 1])
            corr = np.zeros_like(m_shifted)
            for n in np.unique(np.concatenate([y_pos - 1, y_pos])):
                w = np.where(y_pos - 1 == n, 1.0 - alpha_y,
                             np.where(y_pos == n, alpha_y, 0.0))
                sel = w != 0.0
                if np.any(sel):
                    c_n = self._slice_correction(int(n), m_shifted[sel])
                    corr[sel] += w[sel] * c_n
            # The unconstrained branch is the min() winner wherever a
            # correction is nonzero (tails sit far below c = m - BoroCnstArt),
            # and corrections are exactly 0.0 in-sample, so adding preserves
            # bit-identity there.
            base = base + corr
        if orig_shape == ():
            return float(base[0])
        return base.reshape(orig_shape)


def _build_tail_funcs_for_state(i, x_grids, f_values, MPCmin, h_AD_col,
                                measured_q, warn_state):
    """Per-C-slice PowerLawDecayLinearInterp list for combined state ``i``.

    Mirrors the stock attach conditions (the ``if _pf_decay:`` per-slice block
    of ``AggFiscalModel.solve_agg_cons_markov_alt``, ``AggFiscalModel.py:2622-2686``
    as of 2026-09-03; ``_h_in``/``_pf_top``/``_slope_top``/``_level_diff``/``_tol``):
    level_diff > tol and slope_top >= MPCmin => attach; |level_diff| <= tol =>
    keep naive-linear; level_diff < -tol => (2B deviation) warn once + skip.
    Hand copy, bound by ``test_jax2b_attach_decision_parity.py`` (sweep row Q20,
    2026-09-03): the gate runs the live PE block on identical knots, so an edit
    to either side that moves a decision, an exponent or a tail value fails it.
    """
    from powerlaw_decay import PowerLawDecayLinearInterp
    if measured_q:
        from local_q_tail import local_q_from_knots
    nC = x_grids.shape[0]
    out = []
    for n in range(nC):
        x = np.asarray(x_grids[n], dtype=float)
        c = np.asarray(f_values[n], dtype=float)
        h = float(h_AD_col[n])
        pf_top = MPCmin * (x[-1] + h)
        slope_top = (c[-1] - c[-2]) / (x[-1] - x[-2])
        level_diff = pf_top - c[-1]
        tol = 1e-9 * max(1.0, abs(pf_top))
        if level_diff < -tol:
            if not warn_state.get("above_line", False):
                warn_state["above_line"] = True
                warnings.warn(
                    f"jax2b_powerlaw_tail: state {i} C-slice {n} top knot "
                    f"c={c[-1]:.6g} EXCEEDS the AD-aware PF line {pf_top:.6g} "
                    f"(m_top={x[-1]:.6g}, h_AD={h:.6g}). The stock solver HALTs "
                    "here (Carroll-Kimball); the 2B kernel-parity floor makes a "
                    "hard HALT brittle, so this slice keeps naive-linear "
                    "extrapolation instead. Investigate if widespread.")
            out.append(None)
            continue
        if not (level_diff > tol and slope_top >= MPCmin):
            out.append(None)  # at-the-line band: naive-linear is harmless (stock)
            continue
        kw = {}
        if measured_q:
            lq = local_q_from_knots(x[1:], c[1:], h, MPCmin)
            if lq["ok"]:
                kw = dict(decay_extrap_Q=lq["Q"],
                          q_diagnostics=(lq["Q1"], lq["Q2"], lq["drift"]))
        fn = PowerLawDecayLinearInterp(
            x, c, intercept_limit=MPCmin * h, slope_limit=MPCmin, **kw)
        if getattr(fn, "decay_extrap_form", "exp") != "powerlaw":
            fn = None  # ctor validity guards refused (warned) -> naive-linear
        out.append(fn)
    return out


def build_tail_solution(agent, cNrm, mNrm, BoroCnstNat_per_i, Cgrid_np,
                        BoroCnstArt, CRRA):
    """Build the tail-attached ConsumerSolution from JAX output tables.

    AGENT-BASED ADAPTER. Kept with its original signature so the two 2B callers
    (`jax_solver_iterated_drop_in`, `jax_solver_iterated_multicohort`), which
    replace `HARK.core.solve_agent(agent, ...)` and therefore HAVE an agent,
    are unchanged. It only unpacks the agent and delegates to
    ``build_tail_solution_from_params``.

    The plain JAX solver (`jax_solver_drop_in.solve_agg_cons_markov_jax`)
    replaces `solve_one_period`, whose HARK signature carries NO agent — but it
    already receives every field this needs as an explicit argument, so it calls
    the ``_from_params`` entry point directly. One tail implementation, three
    callers (SST, owner ruling 2026-07-25).
    """
    return build_tail_solution_from_params(
        cNrm=cNrm, mNrm=mNrm, BoroCnstNat_per_i=BoroCnstNat_per_i,
        Cgrid_np=Cgrid_np, BoroCnstArt=BoroCnstArt, CRRA=CRRA,
        MrkvArray0=agent.MrkvArray[0], Rfree=agent.Rfree,
        PermGroFac=agent.PermGroFac, IncShkDstn0=agent.IncShkDstn[0],
        Cgrid=agent.Cgrid, ADFunc=agent.ADFunc,
        num_base_MrkvStates=agent.num_base_MrkvStates,
        DiscFac=agent.DiscFac, LivPrb=agent.LivPrb)


def build_tail_solution_from_params(*, cNrm, mNrm, BoroCnstNat_per_i, Cgrid_np,
                                    BoroCnstArt, CRRA, MrkvArray0, Rfree,
                                    PermGroFac, IncShkDstn0, Cgrid, ADFunc,
                                    num_base_MrkvStates, DiscFac, LivPrb):
    """Build the tail-attached ConsumerSolution from JAX output tables (no agent).

    THE single tail-attach entry point for every JAX solve path. It owns no tail
    MATH: the exponent measurement lives in ``local_q_tail`` and the attach
    formula in ``powerlaw_decay.PowerLawDecayLinearInterp`` — the same two
    modules the stock numpy solver uses — so all engines share one construction
    by import, not by copy.

    Returns None when the attach is disabled (caller keeps the legacy wrap) or
    when the FHWC/RIC guard fails (stock fallback semantics: warn + legacy).
    Shapes: cNrm/mNrm (StateCount, Ccount, aCount); BoroCnstNat_per_i
    (StateCount, Ccount).
    """
    if not attach_enabled():
        return None
    from AggFiscalModel import compute_pf_decay_limits
    from jax_solver_drop_in import _JAXvPfuncWrap, _JAXmNrmMinWrap
    from HARK.ConsumptionSaving.ConsAggShockModel import ConsumerSolution

    measured_q = measured_q_active()
    if measured_q:
        import local_q_tail
        local_q_tail.begin_round()

    MPCmin, h_AD = compute_pf_decay_limits(
        np.asarray(MrkvArray0, dtype=float), Rfree,
        PermGroFac, IncShkDstn0, np.asarray(Cgrid, float),
        ADFunc, num_base_MrkvStates,
        float(DiscFac), float(CRRA), LivPrb)
    if (not (MPCmin is not None and MPCmin > 0)) or (not np.all(np.isfinite(h_AD))):
        warnings.warn(
            "jax2b_powerlaw_tail: RIC/FHWC fails (MPCmin<=0 or h non-finite) — "
            "keeping the legacy no-limit 2B wrapper (stock fallback semantics).")
        return None

    StateCount = cNrm.shape[0]
    warn_state = {}
    cFuncNow, vPfuncNow, mNrmMinNow = [], [], []
    for j in range(StateCount):
        # Reconstruct the wrapper's augmented per-slice knots to size the tails
        probe = _JAXcFuncWrapPowerlawTail(cNrm[j], mNrm[j], BoroCnstNat_per_i[j],
                                          Cgrid_np, BoroCnstArt, tail_funcs=None)
        tails = _build_tail_funcs_for_state(
            j, probe._x_grids, probe._f_values, float(MPCmin), h_AD[:, j],
            measured_q, warn_state)
        probe.tail_funcs = tails
        cFuncNow.append(probe)
        vPfuncNow.append(_JAXvPfuncWrap(probe, CRRA))
        mNrmMinNow.append(_JAXmNrmMinWrap(BoroCnstNat_per_i[j], Cgrid_np,
                                          BoroCnstArt))

    if measured_q:
        local_q_tail.maybe_warn_drift()
    return ConsumerSolution(cFunc=cFuncNow, vPfunc=vPfuncNow,
                            mNrmMin=mNrmMinNow)
