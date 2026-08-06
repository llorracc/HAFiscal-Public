"""Regression gate: the AD-belief seed-aware reset in ``solve_ad_recession``.

R8 item 5 (plans/20260724_speed-defaults-deep-dive_plan.md) hard invariant:

    HAFISCAL_AD_BELIEF_SEED consume wiring (welfare6_scenario.run_recession_AD)
    seeds ``eco.CFunc`` and sets ``eco._ad_warm_start=True``; the seed-aware reset
    inside ``AggregateDemandEconomy.solve_ad_recession`` (landed e368b8af,
    2026-06-22) must be STRICTLY BEHIND that attribute:

      flag OFF (``_ad_warm_start`` absent or False)  =>  the cold flat reset runs
      unchanged — a pre-set ``eco.CFunc`` belief is DISCARDED and the whole AD
      trajectory is byte-identical to a clean cold call (the pre-seed-flag
      behavior).

      flag ON (``_ad_warm_start=True``)  =>  the seed survives BOTH clobber
      points: (1) the top-of-call flat reset is skipped, so the presolve solves
      against the seed; (2) the seed is re-applied after ``self.update()``
      (which unconditionally rebuilds a flat CFunc), so the loop's first
      ``run_experiment`` starts from the seed.

This is a FAST unit gate: it drives the REAL ``solve_ad_recession`` loop (real
Picard step, real ``Macro_2_Micro_CFunc`` / ``Compare_CFunc_Convergence`` /
instrumentation / RECONCILED-001 bound) over a stubbed economy whose
``solve``/``update``/``run_experiment`` are deterministic O(1) fakes — no HARK
economy build, so the whole module runs in seconds after the HARK import. The
heavy end-to-end warm-start parity gate (sidecar publish/load, fingerprint soft
gate, welfare panels) is the separate slow suite
``solution_cache/test_ad_belief_seed_parity.py``.

Stub geometry: ``num_base_MrkvStates=1`` and ``num_experiment_periods=1`` give a
4x4 macro==micro CFunc grid (the loop writes MacroCFunc[0][3], [3][1], [1][1]),
and the canned ``run_experiment`` is an affine contraction of the current belief
whose Cratio values stay inside the RECONCILED-001 [0.8, 1.2] matched bound.
"""

import os
import sys

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_FPC = os.path.join(_HERE, "FromPandemicCode")
for _p in (_HERE, _FPC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Parameters.py reads sys.argv (Rfree/CRRA/IncUnemp) at import time — strip
# pytest's args first (CLAUDE.md; same pattern as fti_diagnostics/_poc_ad_anderson.py).
sys.argv = sys.argv[:1]

from AggFiscalModel import AggregateDemandEconomy, CRule  # noqa: E402  (heavy HARK import, no economy build)

_MACRO_DIM = 4      # = 2*num_experiment_periods + 2 with P=1 (indices 0..3 used by the loop)
_NB = 1             # num_base_MrkvStates -> micro dim == macro dim
_P = 1              # num_experiment_periods
_CUTOFF = 1e-3
_MAXIT = 25
_CR_LEN = _P + 11   # Cratio_hist must reach index P+10 for the loop's tail mean


def _flat(dim):
    return [[CRule(1.0, 0.0) for _ in range(dim)] for _ in range(dim)]


def _vec(C):
    """[intercept, slope, ...] flattening (same layout as _cfunc_to_vec)."""
    out = []
    for row in C:
        for c in row:
            out.extend((c.intercept, c.slope))
    return np.asarray(out, dtype=float)


class _DummyAgent:
    def __init__(self):
        self.CFunc = None


class _StubEco:
    """Duck-typed stand-in driven through the REAL ``solve_ad_recession``.

    The belief-update algebra (Picard step / Anderson step / Macro->Micro map /
    convergence metric / warm-start touch-points) is the REAL class code; only
    the expensive economy operations are canned:

      solve()          -> records the belief it was called under (presolve = idx 0)
      update()         -> rebuilds a FLAT CFunc (mirrors the real update()'s
                          unconditional intercept_prev/slope_prev rebuild — the
                          second clobber point the seed-aware path re-applies over)
      run_experiment() -> records the belief at entry; returns a deterministic
                          affine-contraction Cratio_hist inside [0.8, 1.2]
    """

    # Real methods under test / supporting the loop:
    solve_ad_recession = AggregateDemandEconomy.solve_ad_recession
    Macro_2_Micro_CFunc = AggregateDemandEconomy.Macro_2_Micro_CFunc
    Compare_CFunc_Convergence = AggregateDemandEconomy.Compare_CFunc_Convergence
    _ad_anderson_step = AggregateDemandEconomy._ad_anderson_step
    _cfunc_to_vec = staticmethod(AggregateDemandEconomy._cfunc_to_vec)
    _vec_to_cfunc = staticmethod(AggregateDemandEconomy._vec_to_cfunc)

    def __init__(self):
        self.num_base_MrkvStates = _NB
        self.num_experiment_periods = _P
        self.Cfunc_iter_stepsize = 0.5
        self.demand_ADelasticity = 0.3
        self.agents = [_DummyAgent(), _DummyAgent()]
        self.CFunc = _flat(_MACRO_DIM)
        # Trace of the REAL loop's interaction with the economy:
        self.solve_seen = []        # CFunc vec at each self.solve() call (idx 0 = presolve)
        self.experiment_seen = []   # CFunc vec at each run_experiment() entry
        self.cratio_returned = []   # the canned Cratio_hist handed back each iteration

    # --- canned economy operations -------------------------------------
    def solve(self, *a, **k):
        self.solve_seen.append(_vec(self.CFunc))

    def update(self):
        # The real AggregateDemandEconomy.update() unconditionally rebuilds
        # self.CFunc from the flat intercept_prev/slope_prev arrays
        # (AggFiscalModel.py ~2066-2072) — reproduce that clobber exactly.
        self.CFunc = _flat(len(self.CFunc))

    def run_experiment(self, **kwargs):
        self.experiment_seen.append(_vec(self.CFunc))
        mi = float(np.mean([c.intercept for row in self.CFunc for c in row]))
        base = np.full(_CR_LEN, 1.0)
        base[0], base[1] = 0.96, 0.98
        cr = base + 0.30 * (mi - 1.0)   # affine contraction; stays well inside [0.8, 1.2]
        self.cratio_returned.append(cr.copy())
        return {"Cratio_hist": cr}


def _run(eco, *, preset=None, warm=None, maxit=_MAXIT, cutoff=_CUTOFF):
    """Drive the real solve_ad_recession on a stub; return a summary dict."""
    if preset is not None:
        eco.CFunc = [[CRule(c.intercept, c.slope) for c in row] for row in preset]
        for ag in eco.agents:
            ag.CFunc = eco.CFunc
    if warm is not None:
        eco._ad_warm_start = warm
    eco.solve_ad_recession(maxit, convergence_cutoff=cutoff, name=None,
                           shock_type="recession")
    return {
        "iters": int(eco._ad_last_iters),
        "converged": bool(eco._ad_last_converged),
        "final_vec": _vec(eco.CFunc),
        "cratio": np.asarray(eco._ad_last_cratio_hist, dtype=float),
        "solve_seen": [v.copy() for v in eco.solve_seen],
        "experiment_seen": [v.copy() for v in eco.experiment_seen],
        "cratio_returned": [v.copy() for v in eco.cratio_returned],
    }


def _preset_belief():
    """A visibly non-flat belief (what a sidecar seed looks like)."""
    b = _flat(_MACRO_DIM)
    b[0][3] = CRule(1.05, 0.0)
    b[3][1] = CRule(0.93, 0.0)
    b[1][1] = CRule(1.02, 0.0)
    return b


_FLAT_VEC = _vec(_flat(_MACRO_DIM))


def _assert_identical_trajectory(a, b, label):
    assert a["iters"] == b["iters"], (
        f"{label}: iteration count changed ({a['iters']} vs {b['iters']}) — "
        f"the flag-off reset path is no longer byte-identical")
    for key in ("solve_seen", "experiment_seen", "cratio_returned"):
        assert len(a[key]) == len(b[key]), f"{label}: {key} length differs"
        for i, (x, y) in enumerate(zip(a[key], b[key])):
            assert np.array_equal(x, y), (
                f"{label}: {key}[{i}] differs — flag-off trajectory not "
                f"byte-identical (max|d|={np.max(np.abs(x - y)):.3e})")
    assert np.array_equal(a["final_vec"], b["final_vec"]), (
        f"{label}: converged CFunc differs under flag-off")
    assert np.array_equal(a["cratio"], b["cratio"]), (
        f"{label}: final Cratio_hist differs under flag-off")


@pytest.fixture(autouse=True)
def _no_anderson_env(monkeypatch):
    """These tests exercise the stock damped-Picard branch — pin the env."""
    monkeypatch.delenv("HAFISCAL_AD_ANDERSON", raising=False)


def test_flag_off_reset_discards_preset_belief():
    """HARD INVARIANT (flag off => byte-identical current behavior): with
    ``_ad_warm_start`` ABSENT, a pre-set eco.CFunc belief is discarded by the
    cold flat reset and the entire AD trajectory equals a clean cold call."""
    ref = _run(_StubEco())                                   # clean cold call
    pre = _run(_StubEco(), preset=_preset_belief())          # pre-seeded, flag absent
    # The presolve must have seen the FLAT belief in both runs (reset ran):
    assert np.array_equal(ref["solve_seen"][0], _FLAT_VEC)
    assert np.array_equal(pre["solve_seen"][0], _FLAT_VEC), (
        "pre-set belief LEAKED into the presolve with _ad_warm_start absent — "
        "the cold flat reset was skipped")
    _assert_identical_trajectory(ref, pre, "flag-absent+preset vs clean-cold")


def test_flag_false_same_as_absent():
    """``_ad_warm_start=False`` must behave exactly like the attribute being
    absent (the consume wiring resets it to False after each AD solve)."""
    ref = _run(_StubEco())
    off = _run(_StubEco(), preset=_preset_belief(), warm=False)
    assert np.array_equal(off["solve_seen"][0], _FLAT_VEC)
    _assert_identical_trajectory(ref, off, "flag-False+preset vs clean-cold")


def test_flag_on_seed_survives_both_clobber_points():
    """``_ad_warm_start=True``: the seed survives (1) the top-of-call flat reset
    (presolve sees the seed) and (2) the ``self.update()`` clobber (the loop's
    first run_experiment starts from the seed)."""
    seed = _preset_belief()
    seed_vec = _vec(seed)
    on = _run(_StubEco(), preset=seed, warm=True)
    assert np.array_equal(on["solve_seen"][0], seed_vec), (
        "warm start: presolve did NOT see the seed (top-of-call reset clobbered it)")
    assert np.array_equal(on["experiment_seen"][0], seed_vec), (
        "warm start: first run_experiment did NOT see the seed "
        "(self.update()'s flat rebuild clobbered it — the re-apply touch-point broke)")
    # And the trajectory genuinely differs from the cold run (the seed is live):
    ref = _run(_StubEco())
    assert not np.array_equal(on["experiment_seen"][0], ref["experiment_seen"][0])


def test_flag_on_warm_from_converged_reduces_iters_same_fixed_point():
    """Seeding from the cold run's own converged belief (the cross-phase consume
    pattern) must (a) cut the iteration count and (b) land on the same fixed
    point to within the loop's convergence tolerance."""
    cold_eco = _StubEco()
    cold = _run(cold_eco)
    assert cold["converged"], "stub cold run failed to converge — fixture broken"
    converged_belief = [[CRule(c.intercept, c.slope) for c in row]
                        for row in cold_eco.CFunc]
    warm = _run(_StubEco(), preset=converged_belief, warm=True)
    assert warm["converged"]
    assert warm["iters"] < cold["iters"], (
        f"warm-from-converged did not reduce AD iterations "
        f"(cold={cold['iters']}, warm={warm['iters']})")
    dmax = float(np.max(np.abs(warm["final_vec"] - cold["final_vec"])))
    assert dmax < 10 * _CUTOFF, (
        f"warm-start fixed point drifted from the cold fixed point: "
        f"max|dCFunc|={dmax:.3e} (loop cutoff {_CUTOFF:g})")


def test_flag_cleared_after_warm_run_reverts_to_cold():
    """After a warm run, clearing the flag (as run_recession_AD does) must give
    the cold behavior again on the SAME economy object — no sticky state."""
    eco = _StubEco()
    _run(eco, preset=_preset_belief(), warm=True)
    eco._ad_warm_start = False          # what run_recession_AD does post-solve
    eco.solve_seen, eco.experiment_seen, eco.cratio_returned = [], [], []
    again = _run(eco)                   # eco.CFunc currently non-flat (converged)
    assert np.array_equal(again["solve_seen"][0], _FLAT_VEC), (
        "after clearing _ad_warm_start the cold flat reset must run again")
    ref = _run(_StubEco())
    _assert_identical_trajectory(ref, again, "cleared-flag rerun vs clean-cold")
