"""Opt-in cohort-parallel economy solve for the Step-5a solve sites.

R8 item 8 scout (plans/20260724_speed-defaults-deep-dive_plan.md): wires the
validated fork-based cohort-parallel machinery
(FromPandemicCode/parallel_solve.py — bit-identical, 3.88x at Baseline 5x in
the welfare context) into Simulate.py's five explicit economy-solve call
sites, behind a NEW flag:

    HAFISCAL_STEP5A_PARALLEL_SOLVE   unset/''/'0'/'off'  -> disabled (default;
                                                            byte-identical stock
                                                            eco.solve())
                                     'auto'              -> context-budgeted
                                                            worker count (below)
                                     <positive int>      -> that many workers
                                                            per economy solve

Worker budgeting ('auto') — designed to COMPOSE with Simulate.py's existing
process-level fans instead of multiplying them (the known failure mode: see
conclusions_private/2026-07-07_thread-oversubscription-baseline-tma-multiplier.md):

  * The Step-5a entry point pins BLAS/OMP/numba threads to 1, so each pool
    worker is ~1 core. Process-parallelism is the only fan we budget.
  * Site 'initial' (Simulate.py, pre-fork parent): nothing else is running,
    budget = min(n_cohorts, ncpu).
  * Sites inside the outer shock-type fork children (norec/nonad/adtm/first):
    up to 7 shock children may solve concurrently, so budget
    = max(1, min(n_cohorts, ncpu // 8)) — the SAME divisor-8 assumption the
    inner duration fork's auto-budgeter already encodes
    (Simulate.py _fork_dispatch_durations). The solve pool exists only DURING
    eco.solve(), which completes before that child's duration fork starts, so
    within one child the two fans never overlap in time; across siblings the
    shared divisor keeps the whole-run process count ~ncpu.
  * An explicit integer is taken AS-IS per solve (mirrors HAFISCAL_DUR_WORKERS
    semantics) and therefore MULTIPLIES with the outer shock fork — the
    operator owns that product.

Fidelity to AggregateDemandEconomy.solve() (AggFiscalModel.py — read, not
modified here):
  * stamp_regime(eco) is mirrored before dispatch (the stock solve stamps the
    PermGroFac regime; parallel_eco_solve alone does not).
  * agent.pre_solve() runs in the PARENT before dispatch (the stock sequential
    loop mutates parent-side agent state, e.g. update_solution_terminal; the
    fork worker re-runs pre_solve on identical state, which is deterministic
    and idempotent) and agent.post_solve() runs in the PARENT after solutions
    are installed — exactly once each in the parent, as in the stock loop.
    This is the correctness refinement the welfare-context wiring
    (welfare6_scenario._parallel_agg_solve) already adopted.
  * The stock solve's special kernels are NOT reproduced by the fork worker,
    so if any of HAFISCAL_USE_JAX_2B(_VMAP) / HAFISCAL_STEP2_NAMG (or the
    deprecated HAFISCAL_STEP2_ANDERSON alias) / HAFISCAL_STEP5_ATI is enabled,
    this wrapper falls back LOUDLY to the stock eco.solve() (which handles
    them) rather than silently bypassing them.

Test-only knobs (never set in production):
    HAFISCAL_STEP5A_FORCE_POOL=1      route through the fork pool even when the
                                      worker clamp lands at 1. HS_Only Step-5a
                                      has DiscFacCount=1 (ONE cohort), so
                                      without this the HS_Only bit-identity
                                      gate would silently take the sequential
                                      fallback and validate nothing.
    HAFISCAL_STEP5A_SOLVE_PROBE_DIR   if set, after EVERY wrapped solve
                                      (flag on or off) dump a deterministic
                                      pickle of cFunc evaluations on a fixed
                                      probe grid to this directory — the
                                      byte-compare artifact for the gate
                                      (parallel_solve_test.py precedent).

Scope note: this wrapper covers Simulate.py's five explicit solve sites only.
The AD-loop's INTERNAL re-solves (tm_methods.run_ad_tm Phase-1 training calls
economy.solve() once per AD iteration) and run_experiment_tm's per-agent
agent.solve() are out of this scout's file scope and remain sequential.
"""
from __future__ import annotations

import os
import sys

_TRUTHY = ('1', 'on', 'true', 'yes')

# Env flags whose solve-path branches inside AggregateDemandEconomy.solve()
# the fork worker does not reproduce -> loud sequential fallback.
_INCOMPATIBLE_SOLVE_FLAGS = (
    'HAFISCAL_USE_JAX_2B',
    'HAFISCAL_USE_JAX_2B_VMAP',
    'HAFISCAL_STEP2_NAMG',
    'HAFISCAL_STEP2_ANDERSON',   # deprecated alias for STEP2_NAMG
    'HAFISCAL_STEP5_ATI',
)

# Divisor for the in-child 'auto' budget: assume up to 7 outer shock-type fork
# workers may be active concurrently (4 recession + 3 norec) — the SAME
# assumption Simulate.py's _fork_dispatch_durations auto-budgeter encodes
# (ncpu // 8), so the two fans share one budget model.
_CHILD_BUDGET_DIVISOR = 8


def parse_step5a_flag(value=None):
    """Parse HAFISCAL_STEP5A_PARALLEL_SOLVE. Returns None (disabled), 'auto',
    or a positive int. Unrecognized values disable with a warning (safe)."""
    if value is None:
        value = os.environ.get('HAFISCAL_STEP5A_PARALLEL_SOLVE', '')
    v = value.strip().lower()
    if v in ('', '0', 'off', 'no', 'false'):
        return None
    if v == 'auto':
        return 'auto'
    if v.isdigit() and int(v) > 0:
        return int(v)
    print(f"[step5a-parallel] WARNING: unrecognized "
          f"HAFISCAL_STEP5A_PARALLEL_SOLVE={value!r} — treating as disabled.",
          flush=True)
    return None


def _incompatible_flags_active():
    return [f for f in _INCOMPATIBLE_SOLVE_FLAGS
            if os.environ.get(f, '').strip().lower() in _TRUTHY]


def budget_workers(spec, n_cohorts, in_child):
    """Worker count for one wrapped economy solve. See module docstring."""
    # Affinity-aware: under a SLURM cgroup/taskset, cpu_count() reports the
    # whole node while the cpuset is the real grant.
    try:
        ncpu = len(os.sched_getaffinity(0)) or 1
    except (AttributeError, OSError):
        ncpu = os.cpu_count() or 1
    if spec == 'auto':
        if in_child:
            return max(1, min(n_cohorts, ncpu // _CHILD_BUDGET_DIVISOR))
        return max(1, min(n_cohorts, ncpu))
    # explicit int: as-is, clamped to the cohort count (extra workers idle)
    return max(1, min(int(spec), n_cohorts))


def step5a_eco_solve(eco, entry_pid, label=''):
    """Drop-in for the five `eco.solve()` call sites in Simulate.py.

    entry_pid: os.getpid() captured at Simulate() start (pre-fork parent);
               a differing current pid means we are inside a forked shock
               worker -> shared ('auto') budget.
    label:     call-site tag for logging + probe filenames.
    """
    spec = parse_step5a_flag()
    if spec is not None:
        bad = _incompatible_flags_active()
        if bad:
            print(f"[step5a-parallel] {label}: falling back to stock eco.solve() — "
                  f"incompatible solver opt-in(s) active: {', '.join(bad)} "
                  f"(the fork worker runs plain HARK solve_agent only).",
                  flush=True)
            spec = None

    force_pool = os.environ.get(
        'HAFISCAL_STEP5A_FORCE_POOL', '').strip().lower() in _TRUTHY

    if spec is None:
        eco.solve()
        _maybe_dump_probe(eco, label)
        return

    n_cohorts = len(eco.agents)
    in_child = os.getpid() != entry_pid
    n_workers = budget_workers(spec, n_cohorts, in_child)

    if n_workers <= 1 and not force_pool:
        # Nothing to parallelize (e.g. single-cohort HS_Only) — stock path,
        # which also keeps stamp_regime + special-kernel handling exact.
        eco.solve()
        _maybe_dump_probe(eco, label)
        return

    from _permgrofac import stamp_regime
    from parallel_solve import parallel_eco_solve

    print(f"[step5a-parallel] {label}: cohort-parallel solve "
          f"({n_cohorts} cohorts / {n_workers} workers; "
          f"{'child' if in_child else 'parent'} context"
          f"{'; force_pool' if force_pool else ''})", flush=True)

    # Mirror the stock solve's parent-side effects exactly (see module
    # docstring): regime stamp + pre_solve in the parent before dispatch.
    stamp_regime(eco)
    for agent in eco.agents:
        agent.pre_solve()

    parallel_eco_solve(eco, n_workers=n_workers, warm_start=True,
                       verbose=True, force_pool=force_pool)

    # post_solve in the parent after solutions are installed (stock loop
    # order). The fork worker's own post_solve ran on a discarded copy.
    for agent in eco.agents:
        agent.post_solve()

    _maybe_dump_probe(eco, label)


# --------------------------------------------------------------------------
# Probe support (gate artifact; parallel_solve_test.py precedent)
# --------------------------------------------------------------------------

def _probe_grid():
    import numpy as np
    # Dense body + log-spaced extension past the production dist-grid top
    # (dist_aGrid_max=1300) so tail-extrapolation behavior is byte-compared too.
    return np.concatenate([
        np.linspace(0.01, 20.0, 200),
        np.geomspace(20.0, 3000.0, 120),
    ]).astype(np.float64)


def probe_payload(eco, label):
    """Deterministic per-agent cFunc evaluations on the fixed probe grid."""
    import numpy as np
    m = _probe_grid()
    ones = np.ones_like(m)
    agents_out = []
    for agent in eco.agents:
        sol = agent.solution[0]
        n_states = len(sol.cFunc)
        evals = np.empty((n_states, m.size), dtype=np.float64)
        for j in range(n_states):
            evals[j, :] = np.asarray(sol.cFunc[j](m, ones), dtype=np.float64)
        agents_out.append({'n_states': int(n_states), 'cFunc_evals': evals})
    return {'label': label, 'probe_m': m, 'agents': agents_out}


def _maybe_dump_probe(eco, label):
    probe_dir = os.environ.get('HAFISCAL_STEP5A_SOLVE_PROBE_DIR', '').strip()
    if not probe_dir:
        return
    try:
        import pickle
        os.makedirs(probe_dir, exist_ok=True)
        safe = ''.join(ch if (ch.isalnum() or ch in '-_') else '_'
                       for ch in (label or 'unlabeled'))
        path = os.path.join(probe_dir, f'probe_{safe}.pkl')
        with open(path, 'wb') as fh:
            pickle.dump(probe_payload(eco, label), fh,
                        protocol=pickle.HIGHEST_PROTOCOL)
        print(f"[step5a-parallel] probe dumped: {path}", flush=True)
    except Exception as exc:  # probes must never abort a run
        sys.stderr.write(f"[step5a-parallel] probe dump FAILED for "
                         f"{label!r}: {exc!r}\n")
