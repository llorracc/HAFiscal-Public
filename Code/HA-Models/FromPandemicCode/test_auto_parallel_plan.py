"""Unit tests for run_welfare6_parallel._auto_parallel_plan.

EVERY expectation here is pinned to a measurement, named at its assertion. The
table has now been wrong twice, in opposite directions, so the rule for changing
it is: re-measure first, then cite the measurement.

  * ORIGINAL, from plans/20260421-0806h_auto-parallelism-heuristic.md §4.1 —
    assumed the duration pool scales, spent the whole budget on it
    (dw=min(20, budget)).
  * 2026-07-29 — benchmarking said it ANTI-scales past ~2 (178.9 s @dw=1 vs
    308.5 @11), so `rec` moved to (2, budget//2).
  * 2026-07-30 — that benchmark was measuring BUG-064 (every fork child
    re-solved the economy), not the pool. Re-measured on the fixed code at
    Baseline recessionCheck, one build+solve with every width timed in-process,
    dw=2 bracketed first/last at 1.0% drift, AggCons hash identical throughout:

        dw       1       2       4       8      16
      wall  361.8s  212.6s  107.6s   59.6s   49.3s
      speed  1.00x   1.70x   3.36x   6.07x   7.33x
      effic    ---     85%     84%     76%     46%

    So the pool scales, 8 is the knee, and `rec` becomes (min(8, budget),
    min(21, budget)) — the FULL budget to each, since solve and duration are
    sequential phases within a scenario and never co-run.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from run_welfare6_parallel import (_auto_parallel_plan, ALL_SCENARIOS,
                                   _is_recession_scenario, _battery_exit_code,
                                   _MAX_DURATION_WORKERS)


# Each row: (cpu_count, max_parallel, n_scenarios,
#            expected budget,
#            expected norec (dw, sw),
#            expected rec   (dw, sw))
CASES = [
    ( 32, 12, 12,  2, (1,  2), ( 2,  2)),
    ( 32,  1,  1, 32, (1, 21), ( 8, 21)),  # solo: dw at the measured knee, sw at n_cohorts
    ( 32,  4,  4,  8, (1,  8), ( 8,  8)),
    (  8,  4,  4,  2, (1,  2), ( 2,  2)),
    (  8,  1, 12,  8, (1,  8), ( 8,  8)),
    ( 64,  8,  8,  8, (1,  8), ( 8,  8)),
]


def test_auto_parallel_plan_table():
    scenarios_full = list(ALL_SCENARIOS)  # 12 scenarios
    for cpu, mp, n_scen, exp_budget, exp_norec, exp_rec in CASES:
        scenarios = scenarios_full[:n_scen]
        plan = _auto_parallel_plan(cpu, mp, scenarios)
        assert plan["budget"] == exp_budget, (
            f"cpu={cpu} mp={mp} n={n_scen}: budget={plan['budget']}, expected {exp_budget}"
        )
        got_norec = (plan["norec"]["duration_workers"], plan["norec"]["solve_workers"])
        assert got_norec == exp_norec, (
            f"cpu={cpu} mp={mp} n={n_scen}: norec={got_norec}, expected {exp_norec}"
        )
        got_rec = (plan["rec"]["duration_workers"], plan["rec"]["solve_workers"])
        assert got_rec == exp_rec, (
            f"cpu={cpu} mp={mp} n={n_scen}: rec={got_rec}, expected {exp_rec}"
        )


def test_slot_cap_bounds_effective_outer():
    """The hardware slots, not max_parallel, decide how many children co-run.

    Regression for the 2026-07-29 battery: max_parallel=12 with the default
    gpu=1/cpu=2 slots budgeted 32//12 = 2 cores per scenario while only 3
    children were ever in flight, so 26 of 32 cores idled the whole run.
    """
    scenarios = list(ALL_SCENARIOS)
    starved = _auto_parallel_plan(32, 12, scenarios)
    assert starved["budget"] == 2, starved["budget"]

    slotted = _auto_parallel_plan(32, 12, scenarios, slot_cap=3)
    assert slotted["effective_outer"] == 3, slotted["effective_outer"]
    assert slotted["budget"] == 10, slotted["budget"]
    assert slotted["norec"]["solve_workers"] == 10
    # Both pools get the whole budget: they are sequential phases, not rivals.
    assert slotted["rec"]["duration_workers"] == 8
    assert slotted["rec"]["solve_workers"] == 10

    # A slot_cap looser than max_parallel must not inflate concurrency.
    assert _auto_parallel_plan(32, 3, scenarios, slot_cap=12)["budget"] == 10


def test_duration_workers_never_exceed_cap():
    """dw stays at or below the measured knee, and never exceeds the budget.

    Past the knee efficiency falls off a cliff (76% at dw=8 -> 46% at dw=16, for
    a further 1.21x), and oversubscribing the budget would make co-running
    scenarios contend for the same cores.
    """
    for cpu in (8, 32, 64, 256):
        for mp in (1, 2, 4, 12):
            plan = _auto_parallel_plan(cpu, mp, list(ALL_SCENARIOS))
            dw = plan["rec"]["duration_workers"]
            assert dw <= _MAX_DURATION_WORKERS, (cpu, mp, plan)
            assert dw <= plan["budget"], (cpu, mp, plan)


def test_sequential_phases_each_get_the_full_budget():
    """Regression for the pre-2026-07-30 `budget // rec_duration` split.

    eco.solve() completes before the first duration fork exists, so dividing the
    budget between the two pools starved both at once: at 32 cores solo it gave
    the solve 16 workers instead of 21 and the duration loop 2 instead of 8.
    """
    plan = _auto_parallel_plan(32, 1, ["recessionCheck"], n_agent_types=21,
                               n_durations=21)
    assert plan["budget"] == 32
    assert plan["rec"]["solve_workers"] == 21      # capped by cohorts, not by dw
    assert plan["rec"]["duration_workers"] == 8    # capped by the knee, not by sw


def test_is_recession_scenario():
    assert _is_recession_scenario("recession")
    assert _is_recession_scenario("recessionUI")
    assert _is_recession_scenario("recessionCheck_AD")
    assert not _is_recession_scenario("base")
    assert not _is_recession_scenario("Check")
    assert not _is_recession_scenario("UI")
    assert not _is_recession_scenario("TaxCut")


def test_battery_exit_code():
    """A dead child must reach the exit code.

    Regressions for two real incidents on 2026-07-28: the wrapper returned 0 with
    every scenario FAILED, and returned 0 again with 5 of 12 children killed
    mid-queue by an outer timeout. Both were read as success.
    """
    req = list(ALL_SCENARIOS)
    ok = {s: (0, 10.0) for s in req}

    # all good
    assert _battery_exit_code(ok, [], req) == 0
    # one child died -> fail, even though every pickle exists (stale pickles!)
    bad = dict(ok, recessionCheck_AD=(1, 10.0))
    assert _battery_exit_code(bad, [], req) == 1
    # killed by a timeout: negative rc (-SIGTERM) counts as failure
    killed = dict(ok, UI=(-15, 3.0))
    assert _battery_exit_code(killed, [], req) == 1
    # requested but not produced -> fail
    assert _battery_exit_code(ok, ["TaxCut"], req) == 1
    # out-of-scope companion missing -> NOT a failure (documented subset mode)
    subset = ["recessionCheck_AD"]
    assert _battery_exit_code({"recessionCheck_AD": (0, 9.0)},
                              ["base", "Check"], subset) == 0
    # ...but a failure inside a subset run still fails
    assert _battery_exit_code({"recessionCheck_AD": (2, 9.0)},
                              ["base", "Check"], subset) == 1
    # the resolve gate keeps its veto
    assert _battery_exit_code(ok, [], req, resolve_ok=False) == 1


def test_min_one_worker():
    # Degenerate: more scenarios than cores should still give budget ≥ 1
    plan = _auto_parallel_plan(1, 8, list(ALL_SCENARIOS))
    assert plan["budget"] >= 1
    assert plan["norec"]["solve_workers"] >= 1
    assert plan["rec"]["duration_workers"] >= 1
    assert plan["rec"]["solve_workers"] >= 1


def test_zero_scenarios_safe():
    # Shouldn't divide by zero on empty scenario list
    plan = _auto_parallel_plan(32, 12, [])
    assert plan["budget"] >= 1


if __name__ == "__main__":
    test_auto_parallel_plan_table()
    test_is_recession_scenario()
    test_min_one_worker()
    test_zero_scenarios_safe()
    print("All tests passed.")


def test_longest_job_first_cpu_priority():
    """The CPU-slot rule must prefer AD scenarios (the long jobs).

    Regression for the 2026-07-29 battery, where the non-AD-first rule made
    recessionCheck_AD wait 81.9 min and recessionTaxCut_AD 117.4 min for a slot
    and left a 20.6-minute single-scenario tail. Post-BUG-064 the non-AD
    scenarios are ~12 min against the AD ones' 33-144 min, so short-first
    strands the critical path.

    Checked against the source because the scheduler is a closure over live
    subprocesses; a behavioural test would need a battery to run.
    """
    import inspect
    import run_welfare6_parallel as R
    body = inspect.getsource(R.launch_scenarios)
    cpu_slot = body.index("if cpu_in_flight < max_cpu_slots:")
    tail = body[cpu_slot:]
    assert tail.index("_pop_eligible_ad()") < tail.index("non_ad_queue.pop(0)"), (
        "the CPU slot must try an eligible AD scenario before a non-AD one")
