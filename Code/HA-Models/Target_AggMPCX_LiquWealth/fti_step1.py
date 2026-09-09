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

# --- Tail-form consistency guard -> ROUTER (meld plan Phase 0 core, upgraded
# by the F1 everywhere-audit 2026-07-23 after meld P1/P2 landed the power-law
# tail in hark_fti's AndersonEGM at fast-time-iteration d474914). Under the
# power-law PF-decay DEFAULT:
#   * method AndersonEGM -> ROUTE: the transplant solve runs with
#     tail_form='powerlaw' (tail_Q=None => hark_fti's slope-derived Q,
#     powerlaw_tail.slope_derived_Q; an explicit Q can be threaded via the
#     ``tail_Q`` kwarg of make_fti_type/transplant_fti_cfunc/solve_types_fti).
#   * any other method (NAM/ATI/NAMG single-state) -> REFUSE loudly (their
#     solvers still pin the EXPONENTIAL tail; the latent silent-wrong-tail gap
#     recorded in plans/20260716_anderson-powerlaw-tail-meld_plan.md Phase 0),
#     both here at import (env-configured method) and per-call in
#     make_fti_type (programmatic method overrides).
# HAFISCAL_FTI_ALLOW_TAIL_MISMATCH=1 is KEPT for deliberate mismatch
# benchmarking: it restores the pre-router behavior everywhere (exp-pinned FTI
# solve, no routing, no refusal) — including for AndersonEGM.
#: Which FTI realization to use for the transplant. (Read before the guard:
#: the guard's refusal is scoped to non-AndersonEGM methods.)
FTI_METHOD = os.environ.get("HAFISCAL_FTI_METHOD", "NAM").upper()
_pf_form_raw = os.environ.get("HAFISCAL_PF_DECAY_EXTRAP", "1").strip().lower()
# SST predicate (owner ruling 2026-07-24): grid_sizing.powerlaw_form_active is
# THE form test, shared with the production attach / NAMG guard / JAX-2B gate.
_HA_MODELS_DIR = os.path.normpath(os.path.join(_HERE, ".."))
if _HA_MODELS_DIR not in sys.path:
    sys.path.insert(0, _HA_MODELS_DIR)
from grid_sizing import powerlaw_form_active as _pf_form_active  # noqa: E402

#: True iff the power-law PF-decay form is the effective default (the SST
#: predicate; evaluated once at import like the rest of this module's config).
POWERLAW_ACTIVE = _pf_form_active()
_TAIL_MISMATCH_OK = _env_on("HAFISCAL_FTI_ALLOW_TAIL_MISMATCH", "0")


def _refuse_exp_pinned_method(method):
    raise RuntimeError(
        f"HAFISCAL_STEP1_FTI with FTI method {method!r} while the power-law "
        f"PF-decay form is active (HAFISCAL_PF_DECAY_EXTRAP={_pf_form_raw!r}): "
        "this hark_fti method still pins the legacy EXPONENTIAL tail, so the "
        "transplant would solve with the wrong tail (meld Phase-0 guard; only "
        "AndersonEGM has the power-law tail — meld P1/P2 — and ROUTES instead). "
        "Either use HAFISCAL_FTI_METHOD=AndersonEGM, run the legacy tail "
        "explicitly (HAFISCAL_PF_DECAY_EXTRAP=exp or 0), or set "
        "HAFISCAL_FTI_ALLOW_TAIL_MISMATCH=1 for deliberate benchmarking.")


def _kernel_supports_powerlaw_namg():
    """True iff the installed hark_fti advertises the NAMG power-law port.

    N3 capability handshake (2026-07-25, plan 20260725_namg-powerlaw-port):
    NAMG gained real power-law support (tail evaluation + analytic chain-rule
    Jacobian; gated 17 Newton iters = the exp control at the cap atom), so it
    ROUTES rather than refusing — but only when the INSTALLED kernel says so.
    Read the capability from the kernel, never from a version/env guess; an
    older sibling checkout keeps refusing exactly as before.
    """
    try:
        import hark_fti
        return bool(getattr(hark_fti, 'NAMG_SUPPORTS_POWERLAW_TAIL', False))
    except Exception:
        return False


#: Methods that carry the power-law tail and may therefore ROUTE under the
#: power-law default: AndersonEGM always (meld P1/P2); NAMG when the installed
#: kernel advertises the N3 port.
def _method_routes_under_powerlaw(method):
    # Callers pass either a RAW env token (upper-cased, at import) or an
    # already-canonical name (from `_canonical_method`, inside make_fti_type),
    # so resolve defensively rather than assuming one convention.
    canon = _METHOD_BY_UPPER.get(str(method).upper(), method)
    if canon == ANDERSON_EGM_METHOD:
        return True
    if canon == NAMG_METHOD:
        return _kernel_supports_powerlaw_namg()
    return False


if (STEP1_FTI_ON and POWERLAW_ACTIVE and not _TAIL_MISMATCH_OK
        and not _method_routes_under_powerlaw(FTI_METHOD)):
    _refuse_exp_pinned_method(FTI_METHOD)
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
#: Tightened 5e-2 -> 1e-3 (meld plan P0, 2026-07-23): a wrong-tail solve feeds back
#: ~5e-3-class cFunc differences IN-SAMPLE (decay_form/t0_out.txt: in-sample
#: exp-vs-powerlaw max|dC/C| = 5.2e-3), which the old 5e-2 masked; correct-tail
#: solver parity is ~1e-9 (bakeoff), so 1e-3 cannot false-positive a healthy graft.
#: Defense-in-depth behind the tail-form ROUTER above (covers the
#: HAFISCAL_FTI_ALLOW_TAIL_MISMATCH escape, the routed-Anderson case, + future
#: form drift).
GRAFT_ATOL = float(os.environ.get("HAFISCAL_STEP1_FTI_ATOL", "1e-3"))
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


def make_fti_type(base, DiscFac, method=None, autoExtend=None, tail_Q=None):
    """Build an (unsolved) FTI/NAMG type matching a Step-1 KinkedR type.

    ``method='NAMG'`` builds the global-Newton type (its closed-form ``namg_auto_grid``
    replaces ``autoExtendGridTop``); ``'NAM'``/``'ATI'`` build the per-call FTI type.

    Tail router (F1, 2026-07-23): under the power-law PF-decay default (and no
    mismatch escape), ``AndersonEGM`` types are configured with
    ``anderson_tail_form='powerlaw'`` + ``anderson_tail_Q=tail_Q`` (``None`` =>
    hark_fti's slope-derived Q, ``powerlaw_tail.slope_derived_Q``), so every
    sweep AND the returned solution are power-law-tail-consistent (meld P1
    machinery); any other method raises (exp-pinned; see module guard).
    ``tail_Q`` is ignored outside the routed case.
    """
    method = _canonical_method(method or FTI_METHOD)
    autoExtend = FTI_AUTOEXTEND if autoExtend is None else autoExtend
    _route_powerlaw = POWERLAW_ACTIVE and not _TAIL_MISMATCH_OK
    if _route_powerlaw and not _method_routes_under_powerlaw(method):
        # Programmatic method overrides must hit the same wall as the
        # env-configured method does at import.
        _refuse_exp_pinned_method(method)
    if method == NAMG_METHOD:
        agent = IndShockConsumerTypeNAMG(
            namg_auto_grid=autoExtend,
            **_solve_params(base, DiscFac),
        )
        if _route_powerlaw:
            # N3 (2026-07-25): the ported kernel takes the tail form + the
            # measured Q the same way AndersonEGM does; 'chain' is the only
            # sanctioned q-mode ('lagged' raises in the kernel by design).
            agent.namg_tail_form = "powerlaw"
            agent.namg_tail_q_mode = "chain"
            if tail_Q is not None:
                agent.namg_tail_Q = tail_Q
    elif method == ANDERSON_EGM_METHOD:
        # Licence-clean Anderson-accelerated EGM: reaches the SAME EGM fixed point in
        # far fewer sweeps at the GIC edge, with no grid-auto-extend / PF-seed machinery
        # (it pre-converges its own scalars). ``autoExtend`` is inert for this method.
        agent = IndShockConsumerTypeFTI(
            method=ANDERSON_EGM_METHOD,
            **_solve_params(base, DiscFac),
        )
        if _route_powerlaw:
            agent.anderson_tail_form = "powerlaw"
            agent.anderson_tail_Q = None if tail_Q is None else float(tail_Q)
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


def transplant_fti_cfunc(ThisType, base_params, method=None, autoExtend=None, atol=None,
                         tail_Q=None):
    """Safely graft the FTI ``cFunc`` onto an already-solved EGM host ``ThisType``.

    ``ThisType`` must already be solved (its EGM solution supplies every field the
    simulator reads; only ``cFunc`` is replaced — the clean pattern). The FTI policy is
    grafted only if it converged and agrees with EGM (see ``_fti_is_trustworthy``);
    otherwise the EGM policy is kept (transparent fallback). Sets ``ThisType._fti_grafted``
    (bool) and ``ThisType._fti_reason`` (str) for diagnostics. ``HAFISCAL_STEP1_FTI_FORCE=1``
    grafts unconditionally (benchmarking only). ``tail_Q`` threads an explicit
    power-law exponent to the routed AndersonEGM solve (see ``make_fti_type``).
    """
    atol = GRAFT_ATOL if atol is None else atol
    fti = make_fti_type(base_params, ThisType.DiscFac, method=method, autoExtend=autoExtend,
                        tail_Q=tail_Q)
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


def _maybe_rewrap_host_powerlaw(ThisType):
    """F7 host-side tail consistency (2026-07-24, reinstating the F1.4
    machinery after the owner's grid ruling): under the power-law default,
    rewrap the freshly-solved EGM HOST's cFunc tail to the production
    power-law measured-Q form (``step1_powerlaw_tail``) BEFORE the graft
    comparison, so (i) the policy kept on graft-fallback equals the default
    (non-FTI) Step-1 path's, and (ii) the comparison is form-consistent.
    In-sample the rewrap is bit-identical, so ``_fti_is_trustworthy``'s
    resolved-region gate is unaffected either way. No-op under exp/0 (the
    helper gates itself); a missing helper must never break the FTI path."""
    try:
        import step1_powerlaw_tail  # Code/HA-Models on sys.path (insert above)
        step1_powerlaw_tail.maybe_rewrap_types([ThisType])
    except Exception as _e:  # noqa: BLE001
        print(f"[fti_step1] host powerlaw rewrap unavailable ({_e!r}); "
              f"host keeps the HARK-native tail.")


def solve_types_fti(EstTypeList, base_params, method=None, autoExtend=None, tail_Q=None):
    """Solve each Step-1 type (host EGM) then transplant the FTI cFunc.

    Caller runs ``initialize_sim()``/``simulate()`` afterward (unchanged). Used only
    when ``STEP1_FTI_ON``; the OFF path keeps HAFiscal's original
    ``multi_thread_commands(..., ['solve()', ...])`` verbatim.

    HOST TAIL NOTE (F7 ruling, 2026-07-24): under the power-law default the
    Step-1 hosts solve on the K·h̄ grid (the SST resolver applied to
    base_params in Estimation_BetaNablaSplurge) and get the power-law
    measured-Q tail rewrap below — the same policy the default (non-FTI)
    Step-1 path produces. Routed Anderson-powerlaw grafts then face a
    form-consistent host in the trust gate.
    """
    for ThisType in EstTypeList:
        ThisType.solve()  # host: full ConsumerSolution structure for the simulator
        _maybe_rewrap_host_powerlaw(ThisType)
        transplant_fti_cfunc(ThisType, base_params, method=method, autoExtend=autoExtend,
                             tail_Q=tail_Q)
    return EstTypeList
