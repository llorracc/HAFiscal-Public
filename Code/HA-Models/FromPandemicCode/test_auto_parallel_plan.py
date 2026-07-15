"""Unit tests for run_welfare6_parallel._auto_parallel_plan.

Table drawn from plans/20260421-0806h_auto-parallelism-heuristic.md §4.1.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from run_welfare6_parallel import _auto_parallel_plan, ALL_SCENARIOS, _is_recession_scenario


# Each row: (cpu_count, max_parallel, n_scenarios,
#            expected budget,
#            expected norec (dw, sw),
#            expected rec   (dw, sw))
CASES = [
    ( 32, 12, 12,  2, (1,  2), ( 2, 1)),
    ( 32,  1,  1, 32, (1, 21), (20, 1)),
    ( 32,  4,  4,  8, (1,  8), ( 8, 1)),
    (  8,  4,  4,  2, (1,  2), ( 2, 1)),
    (  8,  1, 12,  8, (1,  8), ( 8, 1)),
    ( 64,  8,  8,  8, (1,  8), ( 8, 1)),
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


def test_is_recession_scenario():
    assert _is_recession_scenario("recession")
    assert _is_recession_scenario("recessionUI")
    assert _is_recession_scenario("recessionCheck_AD")
    assert not _is_recession_scenario("base")
    assert not _is_recession_scenario("Check")
    assert not _is_recession_scenario("UI")
    assert not _is_recession_scenario("TaxCut")


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
