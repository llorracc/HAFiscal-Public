"""Cohort parallelization for AggregateDemandEconomy.solve().

Drop-in parallel replacement for eco.solve() that distributes the per-cohort
HARK solves across multiprocessing workers via fork (avoiding pickle issues
with the AggregateDemandEconomy lambda ADFunc).

Usage (programmatic):
    from parallel_solve import parallel_eco_solve
    parallel_eco_solve(eco, n_workers=8)

Usage (env flag, monkey-patches eco.solve):
    HAFISCAL_PARALLEL_SOLVE=8 python ...
    # then welfare6_scenario / run_welfare6_parallel calls eco.solve() — parallel.

The implementation uses module-level globals (`_AGENTS_CACHE`, `_FROM_SOLUTIONS`)
so workers can access agents via index without pickling the agent objects
through the multiprocessing queue. Returns ConsumerSolution per agent
(picklable).

IMPORTANT: set OMP_NUM_THREADS=1 (or low) before parallelizing — otherwise
numpy BLAS threads in each worker oversubscribe the CPU.
"""
from __future__ import annotations
import os
import sys

# Supervised pool (infrastructure A6, Code/HA-Models/pool_supervision.py): a
# worker killed by the cgroup OOM-killer FAILS the map within seconds instead
# of hanging it for ever (multiprocessing.Pool waited indefinitely for the dead
# worker's result; 2026-08-28). Code/HA-Models is the dir AggFiscalModel /
# EstimParameters also put on sys.path; the guard makes this module standalone.
_HA_MODELS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HA_MODELS not in sys.path:
    sys.path.insert(0, _HA_MODELS)
from pool_supervision import supervised_map  # noqa: E402


# Module-level state for fork-based parallel solve
_AGENTS_CACHE = None
_FROM_SOLUTIONS = None
# Engine ladder (P4 of plans_local/20260824-1530h): when a caller asks for it,
# the worker runs the SAME cold ladder as AggregateDemandEconomy.solve() —
# store -> ATI router -> accel -> EGM — instead of plain accel/EGM. `_ECO` is
# the economy being solved (fork-inherited; the router's helpers are
# self-independent statics, the object is passed for fidelity). Off by
# default so every existing caller (the welfare battery's own pool does not
# come through here, but any direct parallel_eco_solve() user might) keeps
# its byte-identical plain-EGM behavior.
_ECO = None
_ENGINE_LADDER = False


def _solve_worker(idx):
    """Worker: solve agent at _AGENTS_CACHE[idx], return (idx, solution,
    engine, wall_s).

    Runs in a forked subprocess. Reads agent + from_solution from the
    module globals (inherited via fork). Returns ConsumerSolution which
    pickles fine for return to parent.
    """
    import time as _time
    from HARK.core import solve_agent
    from AggFiscalModel import maybe_accel_solution
    agent = _AGENTS_CACHE[idx]
    from_sol = _FROM_SOLUTIONS[idx] if _FROM_SOLUTIONS else None
    _t0 = _time.time()
    agent.pre_solve()
    # Shared solved-policy store (plans_local/20260824-1530h): the welfare
    # battery's cohort workers bypass AggregateDemandEconomy.solve(), so the
    # store hooks here too — same qualification, same guard; the parent
    # installs the returned solution as before.
    try:
        from solution_cache import policy_store as _ps
        _eligible = _ps.enabled() and _ps.is_cold_ad_off(agent, from_sol)
    except Exception:
        _ps, _eligible = None, False
    if _eligible:
        stored = _ps.try_load(agent, None)
        if stored is not None:
            agent.post_solve()
            return idx, [stored], 'store', _time.time() - _t0
        if _ps.require_hits():
            _ps.raise_on_miss(agent, 'parallel_solve worker')
    engine = None
    solution = None
    if _ENGINE_LADDER and _ECO is not None:
        # Mirror the economy-level ladder's ATI rung (AggFiscalModel.solve):
        # the router installs agent.solution itself and returns True; False is
        # its own in-family fallback (unqualified atom, non-convergence, the
        # BUG-088 spurious-fixed-point gate) -> the EGM rungs below, exactly as
        # in the sequential loop. NAMG (Step 2 only) is not mirrored — the
        # step5a wrapper keeps it on its incompatible list.
        from AggFiscalModel import try_solve_ati_markov, step5_ati_enabled
        if step5_ati_enabled() and try_solve_ati_markov(agent, from_sol):
            solution = agent.solution
            engine = 'ati'
    if solution is None:
        solution = maybe_accel_solution(agent, from_sol)
        engine = 'accel' if solution is not None else None
    if solution is None:
        solution = solve_agent(agent, False, from_solution=from_sol)
        engine = 'egm-cold' if from_sol is None else 'egm-warm'
    agent.post_solve()
    if _eligible:
        _ps.save(agent, solution[0],
                 producer={'engine': engine, 'site': 'parallel_solve'})
    return idx, solution, engine, _time.time() - _t0


def parallel_eco_solve(eco, n_workers=None, warm_start=True, verbose=False,
                       force_pool=False, engine_ladder=False):
    """Parallel replacement for eco.solve() — solves all cohorts concurrently.

    Args:
      eco: AggregateDemandEconomy with .agents list
      n_workers: number of parallel workers (default: env var or N_cohorts capped at cpu_count)
      warm_start: pass previous solution as from_solution (matches HARK warm_start)
      verbose: print timing info
      force_pool: TEST-ONLY knob (default False = behavior unchanged for all
        existing callers). When True, route through the fork Pool even when the
        worker clamp lands at 1 (e.g. a single-cohort HS_Only economy), so
        bit-identity gates genuinely exercise the fork + pickle-return path
        instead of silently taking the sequential fallback.
      engine_ladder: run the economy-level cold ladder (store -> ATI router ->
        accel -> EGM) in each worker instead of plain accel/EGM — the Step-5a
        wrapper's opt-in (P4, 2026-08-24). Default False keeps every existing
        caller byte-identical.
    """
    global _AGENTS_CACHE, _FROM_SOLUTIONS, _ECO, _ENGINE_LADDER

    n_cohorts = len(eco.agents)
    if n_workers is None:
        env = os.environ.get('HAFISCAL_PARALLEL_SOLVE', '')
        if env.isdigit() and int(env) > 0:
            n_workers = int(env)
        else:
            # Affinity-aware: under a SLURM cgroup/taskset, cpu_count()
            # reports the whole node while the cpuset is the real grant.
            try:
                n_workers = min(n_cohorts, len(os.sched_getaffinity(0)) or 1)
            except (AttributeError, OSError):
                n_workers = min(n_cohorts, os.cpu_count() or 1)
    n_workers = max(1, min(n_workers, n_cohorts))

    if n_workers == 1 and not force_pool:
        # Sequential fallback (no fork overhead)
        return _sequential_solve(eco, warm_start=warm_start)

    # Build from_solutions (warm-start cache) in parent
    from_solutions = []
    for agent in eco.agents:
        from_sol = None
        if warm_start and hasattr(agent, 'solution') and agent.solution and len(agent.solution) > 0:
            prev_sol = agent.solution[0]
            current_states = agent.MrkvArray[0].shape[0]
            prev_states = len(prev_sol.vPfunc) if hasattr(prev_sol, 'vPfunc') else 0
            if prev_states == current_states:
                from_sol = prev_sol
        from_solutions.append(from_sol)

    # Set module globals BEFORE forking so workers inherit them
    _AGENTS_CACHE = list(eco.agents)
    _FROM_SOLUTIONS = from_solutions
    _ECO = eco if engine_ladder else None
    _ENGINE_LADDER = bool(engine_ladder)
    if engine_ladder:
        # The PARENT must be able to unpickle the workers' results: ATI-solved
        # policies carry hark_fti classes (the as-corrected multiplier entry
        # deadlocked its pool on exactly this, 2026-08-24).
        try:
            from solution_cache.policy_store import ensure_fti_importable
            ensure_fti_importable()
        except Exception:
            pass

    if verbose:
        import time
        t0 = time.time()
        print(f"[parallel_solve] {n_cohorts} cohorts / {n_workers} workers"
              f"{' (engine ladder)' if engine_ladder else ''} ...", flush=True)

    try:
        # Force fork start method on Linux; on macOS it changed to spawn in Py3.8+.
        # Same function, one call per cohort, results in input order -- what
        # pool.map returned; the workers are forked inside the call, after the
        # globals above are set, exactly as Pool(...) forked them here.
        results = supervised_map(_solve_worker, range(n_cohorts),
                                 n_workers=n_workers, start_method='fork',
                                 site='parallel_solve.parallel_eco_solve')
    finally:
        # Clear globals so they're not held in memory
        _AGENTS_CACHE = None
        _FROM_SOLUTIONS = None
        _ECO = None
        _ENGINE_LADDER = False

    # Assign solutions back to agents
    for idx, sol, _engine, _wall in results:
        eco.agents[idx].solution = sol

    if verbose:
        # Per-engine accounting in the same shape as the sequential loop's
        # [solve-wall] line (P0): worker CPU-seconds by engine, plus the pool's
        # wall — the ratio is the realized parallel speedup.
        by_engine = {}
        for _idx, _sol, _engine, _wall in results:
            n, s = by_engine.get(_engine, (0, 0.0))
            by_engine[_engine] = (n + 1, s + _wall)
        cpu_total = sum(s for _n, s in by_engine.values())
        parts = ' '.join(f"{k}={n}({s:.0f}s)" for k, (n, s) in
                         sorted(by_engine.items(), key=lambda kv: -kv[1][1]))
        print(f"[parallel_solve] done in {time.time()-t0:.2f}s "
              f"(worker-seconds {cpu_total:.0f}s: {parts})", flush=True)


def _sequential_solve(eco, warm_start=True):
    """Sequential fallback (matches AggregateDemandEconomy.solve)."""
    from HARK.core import solve_agent
    from AggFiscalModel import maybe_accel_solution
    for agent in eco.agents:
        from_solution = None
        if warm_start and hasattr(agent, 'solution') and agent.solution and len(agent.solution) > 0:
            prev_sol = agent.solution[0]
            current_states = agent.MrkvArray[0].shape[0]
            prev_states = len(prev_sol.vPfunc) if hasattr(prev_sol, 'vPfunc') else 0
            if prev_states == current_states:
                from_solution = prev_sol
        agent.pre_solve()
        agent.solution = maybe_accel_solution(agent, from_solution)
        if agent.solution is None:
            agent.solution = solve_agent(agent, False,
                                         from_solution=from_solution)
        agent.post_solve()


def install_parallel_solve_via_env(eco):
    """If HAFISCAL_PARALLEL_SOLVE is set, replace eco.solve with parallel version.

    Returns True if installed, False if env var not set or value is invalid.
    """
    env = os.environ.get('HAFISCAL_PARALLEL_SOLVE', '')
    if not env or env == '0':
        return False
    try:
        n_workers = int(env) if env.isdigit() else None  # None = auto
    except ValueError:
        return False
    # Monkey-patch: bind parallel_eco_solve as eco.solve
    original_solve = eco.solve
    def _patched_solve(self=eco, warm_start=True):
        parallel_eco_solve(self, n_workers=n_workers, warm_start=warm_start)
    # Preserve original under _solve_sequential for debugging
    eco._solve_sequential = original_solve
    eco.solve = _patched_solve
    print(f"[parallel_solve] eco.solve patched with parallel ({n_workers or 'auto'} workers)",
          flush=True)
    return True
