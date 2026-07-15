#!/usr/bin/env python3
"""verify_onestep.py — the de-biased one-step result-validity gate (Gate A).

Thread-2 component 4 (the HIGH-risk one). The cheap alternative to component 3's full
re-solve: instead of re-solving a reused/cached solution from scratch, take backward solver
step(s) from it, see how far the step-residual is from zero, and DE-BIAS that residual by the
contraction modulus to infer how far the solution still is from the true fixed point.

THE PROBLEM (why the naive single-step probe was demoted to diagnostic-only): EGM is a
contraction with modulus L = Þ/R ≈ 0.99 at the College GIC-cap atom. Near the fixed point
x*, one step moves the residual r ≡ ||T(x) − x|| ≈ (1−L)·G, where G ≡ ||x − x*|| is the true
gap. So r UNDERSTATES G by (1−L): a BUG-047-scale 6% gap (G=0.06) gives r ≈ (1−0.99)·0.06 =
6e-4 — UNDER the solve's own ~1e-3 convergence tolerance. A naive "gate on r < tol" therefore
FALSE-PASSES exactly the small regime gaps it most needs to catch (the sibling cache plan's
adversarial finding, plans/20260622_content-addressed-...md §0.2).

THE DE-BIASING: recover G ≈ r₁/(1−L). The crux is HOW you get L — and a 2026-06-22 validation
gate (test_verify_onestep.py) settled it empirically:

  * KNOWN modulus (the SOUND gate). L = Þ/R of the SLOWEST atom is known analytically from the
    calibration. Given an UPPER BOUND L on the dominant contraction modulus, G_est = r₁/(1−L)
    is RIGOROUSLY conservative in ONE step: r₁ = ||(J−I)e|| ≥ (1−λ_dom)·G_dom ≥ (1−L)·G_dom,
    so G_est ≥ G_dom — it can never under-state the dangerous (slowest-relaxing) gap, hence
    never false-passes. No multi-step, no spectral-gap fragility.

  * ESTIMATED modulus (a FALLBACK, less robust). When L isn't supplied we estimate it from a
    few consecutive step-residuals as max(r_{n+1}/r_n) (the ratios climb toward λ_max as the
    fast modes decay). This catches gross / regime-scale gaps, but for a SMALL spectral gap it
    UNDER-states λ_max at finite k → G_est can under-state the gap. Operationally it still
    rejects 6%-scale gaps at a 1e-3 tol, but it is NOT a rigorous bound. Prefer a known L.

VERDICT (see the validation gate + conclusions doc): the de-biasing IS a sound reuse gate
WITH A KNOWN MODULUS; the estimated-modulus variant is a gross-gap screen only. Component 3
(full re-solve) remains the authoritative gate; this is the cheap first line, trustworthy at
the tight (Tier-I/F) standard only via the known-modulus path. Whether to wire it as a
default reuse gate is deferred to the owner given that verdict.

This module is PURE (operates on residuals + a modulus) so its soundness is decided by
synthetic contractions, independent of the real solver. The real-operator residual sequence
is produced by ``multistep_residuals`` (k backward EGM steps, extending
solution_cache/probe.py); that path needs HARK and is exercised only by the opt-in integration.

Spec:       plans/20260622_reuse-fidelity-verification-flag-taxonomy.md
Build:      plans/20260622_thread2-flag-taxonomy-build-execution-plan.md (component 4)
Derivation: conclusions_private/2026-06-22_reuse-gate-A-vs-B-and-debias-derivation.md (READ FIRST)
"""
from __future__ import annotations

_FLOOR = 1e-12   # residuals at/below this are "converged" (gap ~ 0)


def debiased_gap(r1, modulus):
    """De-bias one step-residual by the contraction modulus: ``G ≈ r1 / (1 - modulus)``.

    RIGOROUSLY conservative (``G_est`` >= the true dominant-mode gap, so the gate never
    false-passes) when ``modulus`` is an UPPER BOUND on the operator's dominant contraction
    modulus λ_dom: r1 = ||(J−I)e|| >= (1−λ_dom)·G_dom >= (1−modulus)·G_dom. One step suffices.
    """
    modulus = float(modulus)
    if not (0.0 <= modulus < 1.0):
        raise ValueError(f"modulus must be in [0,1); got {modulus}")
    return float(r1) / (1.0 - modulus)


def estimate_modulus(residuals, floor=_FLOOR):
    """FALLBACK dominant-modulus estimate when L is not known a priori.

    ``max(r_{n+1}/r_n)`` over consecutive residuals above ``floor``. The ratios climb toward
    λ_max as the faster modes decay, so the max is the best (and conservatively-high) finite-k
    estimate. LESS ROBUST than a known modulus: for a small spectral gap it under-states λ_max
    at finite k. Returns ``None`` if no valid ratio (all-but-one residual at floor)."""
    r = [float(x) for x in residuals]
    ratios = [r[i + 1] / r[i] for i in range(len(r) - 1) if r[i] > floor]
    return max(ratios) if ratios else None


def estimate_contraction_gap(residuals, modulus=None, floor=_FLOOR):
    """De-biased gap estimate ``G ≈ r1/(1-L)`` from consecutive step-residual norms.

    ``residuals`` = ``[r_1, ...]`` (>=1 if ``modulus`` is given, else >=2 to estimate it).
    ``modulus`` = a known upper bound on the dominant contraction modulus (the SOUND path —
    e.g. Þ/R of the slowest discount-factor atom); if ``None`` it is ESTIMATED from the
    residual ratios (the fallback). Returns a dict:
        L_est, G_est, contracting, at_floor, source ('known' | 'estimated' | ...), ratios, reason.
    With a known modulus G_est never under-states the dominant gap (no false-pass); with an
    estimated modulus it can, for a small spectral gap (a documented limitation)."""
    r = [float(x) for x in residuals]
    if any(x < 0 for x in r):
        raise ValueError("residual norms must be non-negative")
    if not r:
        raise ValueError("need at least one residual")

    ratios = [(r[i + 1] / r[i] if r[i] > floor else None) for i in range(len(r) - 1)]

    if max(r) <= floor:
        return {"L_est": 0.0, "G_est": 0.0, "contracting": True, "at_floor": True,
                "source": "known" if modulus is not None else "estimated",
                "ratios": ratios, "reason": "at-floor (already converged): gap ~ 0"}

    if modulus is not None:
        return {"L_est": float(modulus), "G_est": debiased_gap(r[0], modulus),
                "contracting": True, "at_floor": False, "source": "known",
                "ratios": ratios, "reason": "de-biased with a known dominant modulus"}

    # Fallback: estimate the modulus from the ratios.
    if len(r) < 2:
        raise ValueError("need >=2 residuals to estimate the modulus (or pass `modulus=`)")
    L = estimate_modulus(r, floor=floor)
    if L is None:
        # r1 above floor, every later residual at floor — one step closed it (fast mode).
        return {"L_est": 0.0, "G_est": r[0], "contracting": True, "at_floor": False,
                "source": "estimated", "ratios": ratios,
                "reason": "collapsed to floor in one step: fast mode, gap ~ r_1"}
    if L >= 1.0:
        return {"L_est": L, "G_est": float("inf"), "contracting": False, "at_floor": False,
                "source": "estimated", "ratios": ratios,
                "reason": f"not contracting (L_est={L:.4f} >= 1): seed is not a fixed point"}
    return {"L_est": L, "G_est": debiased_gap(r[0], L), "contracting": True,
            "at_floor": False, "source": "estimated", "ratios": ratios,
            "reason": "de-biased with an estimated (max-ratio) modulus — fallback, not rigorous"}


def naive_gap(residuals):
    """The NAIVE (un-de-biased) one-step estimate: just r_1. Provided so callers/tests can
    show the contrast — gating on this FALSE-PASSES a high-L regime gap (the whole point)."""
    return float(residuals[0])


def onestep_gate(residuals, tol, modulus=None, floor=_FLOOR):
    """Accept the reuse iff the de-biased gap estimate ``G_est <= tol``.

    Pass ``modulus=`` (a known upper bound on the dominant contraction modulus) for the SOUND,
    rigorously-conservative one-step gate; omit it to fall back to the (less robust) ratio
    estimate. Returns ``(accept: bool, est: dict)``."""
    est = estimate_contraction_gap(residuals, modulus=modulus, floor=floor)
    return (est["G_est"] <= tol), est


# --------------------------------------------------------------------------------------- #
# Real-operator residual sequence (k backward EGM steps) — needs HARK; opt-in integration.
# --------------------------------------------------------------------------------------- #
def multistep_residuals(agent, k=4):
    """Run ``k`` consecutive backward EGM steps from ``agent.solution[0]`` and return the
    list of consecutive self-distances ``[r_1, ..., r_k]`` for the de-biaser.

    Extends solution_cache/probe.probe_cohort_fixed_point (one step) to k steps: each step
    feeds the PREVIOUS step's output back in, so the residuals form the geometric sequence the
    de-biaser needs. RNG-free (only HARK.core.solve_one_cycle + HARK.metric.distance_metric),
    and NON-mutating: ``agent.solution`` is left exactly as loaded (we iterate a local copy).
    Returns ``[]`` if the agent has no solution. (For the SOUND gate, prefer passing a known
    modulus to onestep_gate and k=1; multi-step is only needed for the fallback estimate.)
    """
    from HARK.core import solve_one_cycle
    from HARK.metric import distance_metric

    if not getattr(agent, "solution", None):
        return []
    current = agent.solution[0]
    residuals = []
    for _ in range(k):
        cycle = solve_one_cycle(agent, current, None)
        nxt = cycle[0] if isinstance(cycle, (list, tuple)) else cycle
        residuals.append(float(distance_metric(nxt, current)))
        current = nxt
    return residuals
