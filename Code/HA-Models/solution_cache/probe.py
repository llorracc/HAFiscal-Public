"""Single-EGM-step fixed-point probe for cache hits — DIAGNOSTIC ONLY (Plan 2, STEP 3).

On a cache HIT the loaded solution is warm-started into ``agent.solution``. This module
runs ONE backward EGM step from that loaded solution and reports the per-cohort
self-distance ``distance_metric(solve_one_cycle(...), agent.solution[0])`` — i.e. "how
far is the loaded solution from being a fixed point of its own Bellman step?".

THIS IS NOT A GATE. It is LOG-ONLY and demoted on purpose:
  * EGM is a contraction, so one backward step from a seed that is only a small regime
    gap off (a discretionary-setting flip) closes only a fraction of the gap — the
    single-step residual falls UNDER tolerance while the seed is the wrong-regime
    solution. The probe therefore FALSE-PASSES exactly the small regime gaps it would
    most plausibly need to catch (Plan 2 §0 blocking issue 2).
  * The authoritative wrong-regime backstop is the DETERMINISTIC composite fingerprint
    (``_regime.assert_fingerprint``, raised at cache load — see ``ad_cache.py`` /
    ``test_fingerprint_guard.py``), which compares a regime TAG and is gap-magnitude
    independent. The probe is only useful to surface a GROSSLY stale entry (e.g. the
    full ~6-7% PERMGROFAC gap) during development.

RNG-SAFETY (load-only, observationally inert)
---------------------------------------------
The probe calls ONLY ``HARK.core.solve_one_cycle`` (a deterministic backward EGM step,
no RNG) + ``HARK.metric.distance_metric``. It NEVER calls ``run_experiment`` /
``initialize_sim`` / ``make_history`` / ``hit_with_recession_shock``, so it does NOT
touch ``eco.RNG`` / ``shocks`` / ``shock_history`` / ``history``. A cache hit with the
probe ON therefore produces the SAME downstream welfare/Cratio bytes as a hit with the
probe OFF — this is the property the dropped AD-residual gate (P2) falsely claimed (P2
*did* call ``run_experiment`` and would have perturbed the welfare sim). The probe also
NEVER rejects, re-solves, or mutates the loaded solution — it reports and returns.

SOLVER-AXIS HONESTY (Plan 2 §0 blocking issue 4)
------------------------------------------------
The probe runs HARK's ``solve_one_cycle`` UNCONDITIONALLY and labels its report
``[probe:hark-egm]``. It does NOT dispatch to the run's actual solver: the only
per-cohort backward primitive callable in isolation is HARK's EGM step; the JAX-2B
kernel (``jax_solver_iterated_drop_in.solve_to_convergence_consumer_solution``,
``HAFISCAL_USE_JAX_2B``) is a DIFFERENT map (~1e-3 parity) and the JAX-MC-AD engine has
no per-cohort EGM primitive at all. So under ``HAFISCAL_USE_JAX_2B=1`` the report is
annotated that the HARK-EGM probe is being run against a JAX-2B-solved cFunc and a
~1e-3 parity floor applies — the probe is informational there, never a claim of "verify
with the same map".

Gate: ``HAFISCAL_PROBE_CACHE_CONVERGENCE=1`` (default ``0`` → no probe, exact current
behavior). This module exposes the functions; the cache HIT branch wiring (calling
``probe_eco_fixed_point`` when the flag is set) is the parent's job (Plan 2 STEP 3) —
this module is import-safe and does nothing on import.

Plan: ``plans/20260622_content-addressed-solution-cache-warmstart-1iter-verify.md``.
"""
from __future__ import annotations

import os

PROBE_ENV_VAR = "HAFISCAL_PROBE_CACHE_CONVERGENCE"

_PROBE_LABEL = "[probe:hark-egm]"

# A live default-ON cache-hit VERIFY (gating on this probe) was prototyped and REVERTED
# 2026-06-22: it failed the cache-parity gate (the probe's solve_one_cycle perturbs the
# loaded agent → HIT != OFF), is gross-only (EGM's contraction hides moderate gaps on
# high-Þ/R cohorts), and is artifact-prone (a VALID AD-solved cFunc reads a ~6e-3 one-step
# residual). The byte-safe verification of reuse is the DETERMINISTIC fingerprint +
# key-completeness tripwire, not a dynamic probe. This module stays the LOG-ONLY dev
# diagnostic below. See conclusions_private/2026-06-22_numerical-stability-acceptance-criterion.md.


def probe_enabled():
    """True iff ``HAFISCAL_PROBE_CACHE_CONVERGENCE=1`` (default off).

    The cache HIT branch should guard its ``probe_eco_fixed_point`` call with this so
    the default path is exactly the current behavior (no probe).
    """
    return os.environ.get(PROBE_ENV_VAR, "0") == "1"


def probe_cohort_fixed_point(agent):
    """ONE backward EGM step from ``agent.solution[0]``; return ``(residual, n_step)``.

    ``residual`` = ``distance_metric(solve_one_cycle(agent, agent.solution[0], None),
    agent.solution[0])`` — the self-distance of the loaded solution under one Bellman
    step. ``n_step`` = 1 (one backward step; named for the API the plan specifies, and
    so a future multi-step variant can return >1 without changing the signature).

    RNG-free (no ``initialize_sim`` / ``run_experiment``), non-mutating: the new
    solution is computed into a local and discarded; ``agent.solution`` is left exactly
    as loaded. Returns ``(None, 0)`` if the agent has no solution to probe.
    """
    # Local imports so importing this module never drags in HARK on the default path.
    from HARK.core import solve_one_cycle
    from HARK.metric import distance_metric

    if not getattr(agent, "solution", None):
        return None, 0

    solution_last = agent.solution[0]
    # One backward EGM step. solve_one_cycle returns a fresh ONE-PERIOD CYCLE — i.e. a
    # LIST ``[solution]`` (HARK's ``solution_cycle``), NOT a bare solution — and does NOT
    # assign into agent.solution, so the loaded warm-start is untouched. Unwrap the
    # single period before distance-comparing; comparing the list to a ConsumerSolution
    # would hit distance_metric's mismatched-type sentinel (1000.0) and report a bogus
    # residual (verified 2026-06-22).
    solution_cycle = solve_one_cycle(agent, solution_last, None)
    solution_now = (solution_cycle[0]
                    if isinstance(solution_cycle, (list, tuple))
                    else solution_cycle)
    residual = distance_metric(solution_now, solution_last)
    return residual, 1


def probe_eco_fixed_point(eco, verbose=True):
    """Probe every cohort of a (cache-loaded) eco and LOG the per-cohort residuals.

    LOG-ONLY: never rejects, re-solves, or mutates. Safe to call on a cache hit because
    the underlying backward step is RNG-free (see module docstring). Returns the list of
    per-cohort ``(residual, n_step)`` tuples for callers/tests that want the numbers; on
    the default path (``HAFISCAL_PROBE_CACHE_CONVERGENCE`` unset) callers should not call
    this at all — guard with ``probe_enabled()``.

    The ``[probe:hark-egm]`` label states the solver axis; under
    ``HAFISCAL_USE_JAX_2B=1`` an extra parity-floor note is emitted.
    """
    agents = list(getattr(eco, "agents", []) or [])
    jax_2b = os.environ.get("HAFISCAL_USE_JAX_2B", "0") == "1"

    results = []
    if verbose:
        suffix = ""
        if jax_2b:
            suffix = (" (HARK-EGM probe vs a JAX-2B-solved cFunc; "
                      "HAFISCAL_USE_JAX_2B=1 → ~1e-3 parity floor applies — "
                      "informational, NOT a gate)")
        print(f"{_PROBE_LABEL} cache-hit fixed-point probe over "
              f"{len(agents)} cohort(s){suffix}", flush=True)

    worst = None
    for i, agent in enumerate(agents):
        try:
            residual, n_step = probe_cohort_fixed_point(agent)
        except Exception as e:  # never let a diagnostic break a (correct) hit
            residual, n_step = None, 0
            if verbose:
                print(f"{_PROBE_LABEL} cohort {i}: probe error "
                      f"({type(e).__name__}: {e}) — skipping (log-only diagnostic)",
                      flush=True)
        results.append((residual, n_step))
        if residual is not None and (worst is None or residual > worst):
            worst = residual
        if verbose and residual is not None:
            tol = getattr(agent, "tolerance", None)
            tol_str = f"; agent.tolerance={tol:g}" if isinstance(tol, (int, float)) else ""
            print(f"{_PROBE_LABEL} cohort {i}: one-step residual={residual:.3e}"
                  f"{tol_str}", flush=True)

    if verbose and worst is not None:
        print(f"{_PROBE_LABEL} worst one-step residual across cohorts={worst:.3e} "
              "(LOG-ONLY — the fingerprint guard is the authoritative gate; a small "
              "residual does NOT certify the regime, EGM being a contraction)",
              flush=True)
    return results
