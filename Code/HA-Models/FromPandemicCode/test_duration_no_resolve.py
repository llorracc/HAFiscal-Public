"""BUG-064 regression: the duration loop must not re-solve the economy.

`run_experiment` calls `solve_if_changed()` per agent, which re-solves whenever
MrkvArray != MrkvArray_prev. `switch_shock_type` swaps MrkvArray (6x6 base ->
132x132 recession) and `Market.solve()` never updates MrkvArray_prev, so before the
fix the guard fired on the FIRST task of EVERY forked duration child: 21 agents,
serially, per child. MEASURED 2026-07-30 at Baseline recessionCheck (solo, dw=2):
duration loop 3320.6 s -> 208.0 s, i.e. ~94% of it was a re-solve that reproduces
the policy exactly (measured move 0.000e+00; panels agree to 4.0e-16).

This defect has now surfaced by two independent routes -- the AD path in 2026-07-29
(where it masqueraded as "JAX makes HARK simulation 16x slower") and the non-AD path
in 2026-07-30 -- so the invariant belongs in a test rather than in a third comment.

The tests drive the REAL `AggFiscalType.solve_if_changed` guard over stub agents, so
they check the semantics that matter rather than a source pattern; the last one is a
cheap ordering guard, because syncing AFTER the fork would leave every child stale.
"""
import inspect
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# welfare6_scenario -> Parameters -> EstimParameters reads sys.argv[5] as Splurge,
# so it must not see pytest's argv. (welfare6_scenario strips its OWN flags for the
# same reason; under pytest there is nothing of its own to strip.)
_ARGV, _CWD = sys.argv[:], os.getcwd()
sys.argv = [_ARGV[0]]
try:
    import welfare6_scenario as W
    from AggFiscalModel import AggFiscalType
finally:
    sys.argv = _ARGV
    os.chdir(_CWD)

N_AGENTS = 3
N_DURATIONS = 4


class _StubAgent:
    """Duck-types just enough for the real solve_if_changed guard."""

    def __init__(self):
        self.MrkvArray = [np.eye(6)]
        self.MrkvArray_prev = [np.eye(4)]   # stale AND a different size, as after
        self.solve_calls = 0                # switch_shock_type(base -> recession)

    def solve(self):
        self.solve_calls += 1


class _StubEco:
    def __init__(self):
        self.agents = [_StubAgent() for _ in range(N_AGENTS)]

    def run_experiment(self, **kwargs):
        for a in self.agents:
            AggFiscalType.solve_if_changed(a)      # the real guard
        n = 5
        return {"cLvl_all_splurge": np.ones((n, 2)), "AggIncome": np.ones(n),
                "AggCons": np.ones(n), "pLvl_all": np.ones((n, 2)),
                "Mrkv_hist": np.zeros((n, 2))}


def _ctx():
    return {"base_dict": {}, "Rspell": 6.0, "num_experiment_periods": 2,
            "max_recession_duration": N_DURATIONS}


def _run(monkeypatch, resolve_env):
    if resolve_env is None:
        monkeypatch.delenv("HAFISCAL_DURATION_RESOLVE", raising=False)
    else:
        monkeypatch.setenv("HAFISCAL_DURATION_RESOLVE", resolve_env)
    eco = _StubEco()
    W._prob_weighted_rec(_ctx(), eco, {}, duration_workers=1)
    return sum(a.solve_calls for a in eco.agents)


def test_duration_loop_performs_no_resolves(monkeypatch):
    """The invariant. Any non-zero count is ~94% of the loop's wall at Baseline."""
    assert _run(monkeypatch, None) == 0


def test_escape_hatch_restores_the_old_behaviour(monkeypatch):
    """HAFISCAL_DURATION_RESOLVE=1 is the A/B lever; one re-solve per agent, since
    the guard rebinds MrkvArray_prev itself once it has fired."""
    assert _run(monkeypatch, "1") == N_AGENTS


def test_sync_happens_before_the_fork():
    """Ordering guard: children inherit the economy by copy-on-write, so a sync
    placed after Pool() would leave every child stale and restore the defect."""
    body = inspect.getsource(W._prob_weighted_rec)
    sync = body.index("_sync_mrkv_prev(eco)")
    fork = body.index("Pool(")
    assert sync < fork, "the MrkvArray_prev sync must precede pool creation"


def test_every_run_experiment_caller_is_covered():
    """BUG-064's invariant must hold at its SOURCE, not per caller.

    The fix has now been placed per-caller twice and missed a site both times:
    2026-07-29 covered the AD path only; 2026-07-30 covered `_prob_weighted_rec`,
    which `run_norec` does not call -- it invokes `run_experiment` directly, so
    Check/UI/TaxCut kept re-solving (measured 32.6 s of UI's 61 s wall at HS_Only,
    ~5000 s of 6395 s at Baseline).

    So this asserts the structural property instead of a line: every function that
    calls `run_experiment` must either sync first, or reach it through something
    that did. `_parallel_agg_solve` is that something -- it is monkey-patched over
    AggregateDemandEconomy.solve at import, so ANY caller that solves is covered.
    """
    import welfare6_scenario as W

    # 1. the source: the solve wrapper syncs on BOTH of its paths
    solve_src = inspect.getsource(W._parallel_agg_solve)
    calls = solve_src.count("_sync_mrkv_prev(self)")   # calls, not doc mentions
    assert calls == 2, (
        f"both the serial-delegate and pool paths of _parallel_agg_solve must "
        f"sync; found {calls} call(s)")

    # 2. the documented bypass: restore_ADsolution installs a solution without
    #    solving, so run_recession_AD must sync explicitly
    assert "_sync_mrkv_prev" in inspect.getsource(W.run_recession_AD)

    # 3. no caller of run_experiment may rely on an inline copy of the policy
    for fn_name in ("run_base", "run_norec", "_prob_weighted_rec",
                    "run_recession_AD"):
        src = inspect.getsource(getattr(W, fn_name))
        assert "MrkvArray_prev = " not in src, (
            f"{fn_name} has an inline MrkvArray_prev assignment; call "
            f"_sync_mrkv_prev instead so there is one definition of the policy")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
