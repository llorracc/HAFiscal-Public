"""Opt-in FTI (NAM/ATI) wiring for HAFiscal Step-1 (beta/splurge estimation).

Step-1 solves an infinite-horizon (``cycles=0``), single-state, KinkedR-with-
``BoroCnstArt=0`` problem whose own docstring calls it "mathematically equivalent
to IndShockConsumerType" (agents never borrow, so the Rboro kink is inert). The
most-patient tapered discount-factor type sits at GPF-Mod ~ 0.999 — exactly the
regime where EGM time-iteration crawls and White's Newton Arbitrage Method (NAM)
converges in a grid-independent number of Newton steps.

This module implements the **clean-pattern cFunc transplant** validated by the PoC
(``llorracc/fast-time-iteration`` finding 2215h,
``experiments/hafiscal/poc_hafiscal_step1_fti.py``): solve the equivalent problem
with ``IndShockConsumerTypeFTI`` and assign its ``cFunc`` onto the already-solved
KinkedR host, leaving HAFiscal's ``initialize_sim()``/``simulate()``/RNG path
untouched.

STRICTLY OPT-IN. With ``HAFISCAL_STEP1_FTI`` unset/``0`` (default) this module is
never invoked and Step-1 behaves byte-identically. The solver itself is the external
``hark_fti`` package, now homed in the sibling ``fast-time-iteration`` repo (located
at runtime by ``Code/HA-Models/FromPandemicCode/_hark_fti_path.py``; see that repo's
``hark_fti/PROVENANCE.md`` + ``hark_fti/MANIFEST.md``).

Env flags
---------
- ``HAFISCAL_STEP1_FTI``           : ``1`` to enable the transplant (default ``0`` = OFF).
- ``HAFISCAL_FTI_METHOD``          : ``NAM`` (default), ``ATI``, ``NAMG``, or ``AndersonEGM``.
  ``NAMG`` is the opt-in GLOBAL Newton (``hark_fti.global_newton``): it removes the
  lagged-continuation outer loop that makes plain NAM/ATI crawl at the GIC edge, so
  the most-patient discount-factor type converges in ~20–30 grid-independent Newton
  steps instead of falling back to EGM. Use ``NAMG`` to actually solve (not just
  fall back on) the patient type. ``AndersonEGM`` (case-insensitive) is the licence-clean
  Tier-C alternative: it Anderson-accelerates the EGM contraction itself (no White/NAM
  Jacobian), reaching the SAME EGM fixed point in ~6x fewer sweeps at the GIC edge. Like
  NAMG it actually solves the patient type; unlike NAM/ATI it needs no PF-seed/grid-auto
  machinery and supports vFunc/cubic.
- ``HAFISCAL_STEP1_FTI_AUTOEXTEND``: ``1`` (default) to let the solver size its own grid
  top — ``autoExtendGridTop`` for NAM/ATI, the closed-form ``namg_auto_grid`` for NAMG
  (the patient GIC-edge type needs an adequate top to be accurate); ``0`` to solve on
  the host's grid (shared-knot parity with EGM, but the patient type may be slow).
"""
from __future__ import annotations

import os
import sys
from copy import deepcopy

import numpy as np

# The generic FTI solvers now live in the sibling ``fast-time-iteration`` repo (their
# canonical home). ``FromPandemicCode/_hark_fti_path`` locates that checkout and puts
# the external ``hark_fti`` package on sys.path. All of hark_fti's internal imports are
# ``HARK.``-qualified, so it binds to HAFiscal's installed HARK.
_HERE = os.path.dirname(os.path.abspath(__file__))
_FROMPANDEMIC = os.path.normpath(os.path.join(_HERE, "..", "FromPandemicCode"))
if _FROMPANDEMIC not in sys.path:
    sys.path.insert(0, _FROMPANDEMIC)
import _hark_fti_path  # noqa: F401,E402  -- resolve external `hark_fti` (fast-time-iteration)

from hark_fti import (  # noqa: E402
    ANDERSON_EGM_METHOD,
    FTI_METHODS,
    NAMG_METHOD,
    IndShockConsumerTypeFTI,
    IndShockConsumerTypeNAMG,
)

#: Methods this wiring can build: the per-call FTI realizations, the global Newton (NAMG),
#: and the licence-clean Anderson-accelerated EGM (Tier C). Compared case-insensitively
#: (see ``_canonical_method``) because env vars arrive upper-cased.
STEP1_METHODS = tuple(FTI_METHODS) + (NAMG_METHOD, ANDERSON_EGM_METHOD)

#: Upper-cased token -> canonical method name. ``HAFISCAL_FTI_METHOD`` is read and
#: ``.upper()``-ed, but the FTI type matches ``ANDERSON_EGM_METHOD`` (mixed-case
#: ``"AndersonEGM"``) exactly, so map it back.
_METHOD_BY_UPPER = {m.upper(): m for m in STEP1_METHODS}


def _canonical_method(method):
    """Resolve a (possibly upper-cased) method token to its canonical STEP1_METHODS name."""
    if method in STEP1_METHODS:
        return method
    canon = _METHOD_BY_UPPER.get(str(method).upper())
    if canon is None:
        raise ValueError(f"HAFISCAL_FTI_METHOD={method!r} not in {STEP1_METHODS}")
    return canon


def _env_on(name, default="0"):
    return os.environ.get(name, default) == "1"


#: Master opt-in switch (read once at import; default OFF).
STEP1_FTI_ON = _env_on("HAFISCAL_STEP1_FTI", "0")
#: Which FTI realization to use for the transplant.
FTI_METHOD = os.environ.get("HAFISCAL_FTI_METHOD", "NAM").upper()
#: Let NAM size its own grid top (default ON; the patient GIC-edge type needs it).
FTI_AUTOEXTEND = _env_on("HAFISCAL_STEP1_FTI_AUTOEXTEND", "1")
#: Safe-graft guard: graft the FTI policy only if it CONVERGED (Newton iters below this
#: budget — converged moderate types use <~250; a non-converged GIC-edge solve hits the
#: solver's ~5000 cap) AND it agrees with the EGM host on the resolved region to
#: ``GRAFT_ATOL``. Otherwise keep EGM (transparent fallback). Plain NAM does not yet
#: solve the patient GIC-edge type — that is Phase-4 (GMRES-ATI / Markov FTI) work — so
#: the fallback is what keeps the opt-in result correct today. Set
#: ``HAFISCAL_STEP1_FTI_FORCE=1`` to graft unconditionally (benchmarking only).
GRAFT_MAX_ITERS = int(os.environ.get("HAFISCAL_STEP1_FTI_MAXITERS", "1000"))
GRAFT_ATOL = float(os.environ.get("HAFISCAL_STEP1_FTI_ATOL", "5e-2"))
GRAFT_FORCE = _env_on("HAFISCAL_STEP1_FTI_FORCE", "0")

# Only the keys the IndShock/FTI solver consumes (KinkedR's Rboro/Rsave are dropped;
# the single Rfree below is the saving rate, which is all that matters at BoroCnstArt=0).
_SOLVE_KEYS = (
    "CRRA Rfree PermGroFac BoroCnstArt PermShkStd PermShkCount TranShkStd TranShkCount "
    "UnempPrb IncUnemp aXtraMin aXtraMax aXtraCount aXtraNestFac LivPrb"
).split()


def _solve_params(base, DiscFac):
    """Minimal solve-param dict for an FTI/IndShock type from Step-1's base_params."""
    p = {k: deepcopy(base[k]) for k in _SOLVE_KEYS}
    # FTI/IndShock expect the time-varying (list) form for Rfree; use the saving rate
    # (= Rfree at BoroCnstArt=0, where agents never hit the Rboro kink).
    rfree = base.get("Rsave", base["Rfree"])
    p["Rfree"] = [float(np.asarray(rfree).reshape(-1)[0])]
    p.update(
        DiscFac=DiscFac,
        cycles=0,
        T_cycle=1,
        vFuncBool=False,
        CubicBool=False,
        aXtraExtra=None,
    )
    return p


def make_fti_type(base, DiscFac, method=None, autoExtend=None):
    """Build an (unsolved) FTI/NAMG type matching a Step-1 KinkedR type.

    ``method='NAMG'`` builds the global-Newton type (its closed-form ``namg_auto_grid``
    replaces ``autoExtendGridTop``); ``'NAM'``/``'ATI'`` build the per-call FTI type.
    """
    method = _canonical_method(method or FTI_METHOD)
    autoExtend = FTI_AUTOEXTEND if autoExtend is None else autoExtend
    if method == NAMG_METHOD:
        agent = IndShockConsumerTypeNAMG(
            namg_auto_grid=autoExtend,
            **_solve_params(base, DiscFac),
        )
    elif method == ANDERSON_EGM_METHOD:
        # Licence-clean Anderson-accelerated EGM: reaches the SAME EGM fixed point in
        # far fewer sweeps at the GIC edge, with no grid-auto-extend / PF-seed machinery
        # (it pre-converges its own scalars). ``autoExtend`` is inert for this method.
        agent = IndShockConsumerTypeFTI(
            method=ANDERSON_EGM_METHOD,
            **_solve_params(base, DiscFac),
        )
    else:
        agent = IndShockConsumerTypeFTI(
            method=method,
            autoExtendGridTop=autoExtend,
            **_solve_params(base, DiscFac),
        )
    agent.cycles = 0
    return agent


def _fti_is_trustworthy(fti, host, atol):
    """True iff the FTI solve converged and agrees with the EGM host where it matters.

    Method-agnostic safety gate for the graft: (1) converged within the iteration budget
    (a non-converged GIC-edge Newton solve hits the solver's cap); (2) finite, strictly
    increasing policy; (3) max |cFunc_FTI - cFunc_host| < ``atol`` on the host's resolved
    region above the borrowing constraint (the ergodic mass lives well inside this).
    """
    iters = int(getattr(fti, "completed_cycles", -1))
    if not (1 <= iters < GRAFT_MAX_ITERS):
        return False, f"not converged (iters={iters})"
    mMin = float(fti.solution[0].mNrmMin)
    top = float(getattr(host, "aXtraMax", getattr(fti, "aXtraMax", 20.0)))
    m = np.linspace(mMin + 0.5, max(mMin + 1.0, top), 60)
    c_fti = np.asarray(fti.solution[0].cFunc(m), dtype=float)
    if not (np.all(np.isfinite(c_fti)) and np.all(np.diff(c_fti) > 0)):
        return False, "non-finite or non-monotone policy"
    c_host = np.asarray(host.solution[0].cFunc(m), dtype=float)
    max_dc = float(np.max(np.abs(c_fti - c_host)))
    if max_dc >= atol:
        return False, f"disagrees with EGM (max|dC|={max_dc:.2e} >= {atol:.1e})"
    return True, f"ok (iters={iters}, max|dC|={max_dc:.2e})"


def transplant_fti_cfunc(ThisType, base_params, method=None, autoExtend=None, atol=None):
    """Safely graft the FTI ``cFunc`` onto an already-solved EGM host ``ThisType``.

    ``ThisType`` must already be solved (its EGM solution supplies every field the
    simulator reads; only ``cFunc`` is replaced — the clean pattern). The FTI policy is
    grafted only if it converged and agrees with EGM (see ``_fti_is_trustworthy``);
    otherwise the EGM policy is kept (transparent fallback). Sets ``ThisType._fti_grafted``
    (bool) and ``ThisType._fti_reason`` (str) for diagnostics. ``HAFISCAL_STEP1_FTI_FORCE=1``
    grafts unconditionally (benchmarking only).
    """
    atol = GRAFT_ATOL if atol is None else atol
    fti = make_fti_type(base_params, ThisType.DiscFac, method=method, autoExtend=autoExtend)
    fti.solve()
    if GRAFT_FORCE:
        ok, reason = True, "forced"
    else:
        ok, reason = _fti_is_trustworthy(fti, ThisType, atol)
    if ok:
        ThisType.solution[0].cFunc = fti.solution[0].cFunc
    ThisType._fti_grafted = bool(ok)
    ThisType._fti_reason = reason
    ThisType._fti_iters = int(getattr(fti, "completed_cycles", -1))
    return ThisType


def solve_types_fti(EstTypeList, base_params, method=None, autoExtend=None):
    """Solve each Step-1 type (host EGM) then transplant the FTI cFunc.

    Caller runs ``initialize_sim()``/``simulate()`` afterward (unchanged). Used only
    when ``STEP1_FTI_ON``; the OFF path keeps HAFiscal's original
    ``multi_thread_commands(..., ['solve()', ...])`` verbatim.
    """
    for ThisType in EstTypeList:
        ThisType.solve()  # host: full ConsumerSolution structure for the simulator
        transplant_fti_cfunc(ThisType, base_params, method=method, autoExtend=autoExtend)
    return EstTypeList
