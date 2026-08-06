"""F1.4 gate tests: the Step-1 power-law measured-Q tail rewrap
(``step1_powerlaw_tail.py``; plans/20260723_measured-q-tail-default-finalization_plan.md).

Covers, on a REAL solved Step-1-class KinkedR host (one mid-ladder type, ~seconds):
  (a) the rewrap swaps the unconstrained branch to ``PowerLawDecayLinearInterp``
      with the powerlaw form engaged, keeping identical knots/limits;
  (b) IN-SAMPLE the rewrapped cFunc is bit-identical to the stock one (the
      port changes extrapolation only);
  (c) ABOVE-GRID the powerlaw tail sits strictly BELOW the exp tail and below
      the PF line (slower gap decay — the honest tail), approaching the line;
  (d) the measured-Q estimator RUNS at the Step-1 host grid (top-3 ln(x+h)
      span ~0.051, marginally above the 0.05 gate) and the ctor attaches the
      measured most-local Q (slope-derived Q remains the sub-gate fallback);
  (e) gating: under the explicit legacy tail (exp / 0) the wire-in is a no-op;
  (f) the measured-Q override DOES land when the grid is deep enough
      (synthetic deep-grid host).
"""
import os
import sys
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

_HA_MODELS = os.path.dirname(os.path.abspath(__file__))
_TARGET = os.path.join(_HA_MODELS, "Target_AggMPCX_LiquWealth")
for _p in (_HA_MODELS, _TARGET):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType  # noqa: E402
from HARK.interpolation import LinearInterp, LowerEnvelope  # noqa: E402
from SetupParamsCSTW import init_infinite  # noqa: E402

import local_q_tail  # noqa: E402
import step1_powerlaw_tail as spt  # noqa: E402
from powerlaw_decay import PowerLawDecayLinearInterp  # noqa: E402


def _base_params():
    """Step-1 NOR base_params (mirrors Estimation_BetaNablaSplurge.py; same
    reconstruction as test_fti_step1.py)."""
    b = deepcopy(init_infinite)
    b["LivPrb"] = [1 - 1 / 160]
    b["Rfree"] = 1.02 ** 0.25
    b["Rsave"] = 1.02 ** 0.25
    b["Rboro"] = 1.137 ** 0.25
    b["pLogInitMean"] = 0
    b["UnempPrb"] = 0.044
    b["IncUnemp"] = 0.60
    b["PermShkStd"] = [0.001 ** 0.5]
    b["TranShkStd"] = [0.132 ** 0.5]
    b["BoroCnstArt"] = 0
    b["PermGroFacAgg"] = 1.01 ** 0.25
    b["CRRA"] = 2.0
    b["T_age"] = None
    return b


@pytest.fixture(scope="module")
def solved_host():
    t = KinkedRconsumerType(**_base_params())
    t.DiscFac = 0.94  # mid-ladder: fast EGM convergence, decidedly buffer-stock
    t.cycles = 0
    t.solve()
    return t


def setup_function(_):
    local_q_tail.reset_diagnostics()


def test_rewrap_swaps_form_and_is_insample_identical(solved_host, monkeypatch):
    monkeypatch.delenv("HAFISCAL_PF_DECAY_EXTRAP", raising=False)  # default = powerlaw
    t = deepcopy(solved_host)
    sol = t.solution[0]
    old_cf = sol.cFunc
    old_unc = old_cf.functions[0]
    m_top = float(old_unc.x_list[-1])
    m_in = np.linspace(0.0, m_top, 601)
    c_before = np.asarray(old_cf(m_in), dtype=float)

    n = spt.maybe_rewrap_types([t])
    assert n == 1
    new_cf = t.solution[0].cFunc
    assert isinstance(new_cf, LowerEnvelope)
    new_unc = new_cf.functions[0]
    assert isinstance(new_unc, PowerLawDecayLinearInterp)
    assert new_unc.decay_extrap_form == "powerlaw"
    np.testing.assert_array_equal(np.asarray(new_unc.x_list), np.asarray(old_unc.x_list))
    np.testing.assert_array_equal(np.asarray(new_unc.y_list), np.asarray(old_unc.y_list))

    # (b) in-sample: bit-identical
    c_after = np.asarray(new_cf(m_in), dtype=float)
    np.testing.assert_array_equal(c_before, c_after)

    # (c) above-grid: powerlaw strictly below exp, both strictly below the PF
    # line, powerlaw approaching it (gap shrinking with m)
    MPCmin, hNrm = float(sol.MPCmin), float(sol.hNrm)
    m_out = np.array([m_top * 1.5, m_top * 3, m_top * 10, m_top * 50])
    c_exp = np.asarray(old_cf(m_out), dtype=float)
    c_pl = np.asarray(new_cf(m_out), dtype=float)
    pf = MPCmin * (m_out + hNrm)
    assert np.all(c_pl < c_exp), (c_pl, c_exp)
    assert np.all(c_pl < pf) and np.all(c_exp <= pf + 1e-12)
    gap = pf - c_pl
    assert np.all(np.diff(gap / pf) < 0)  # relative gap collapses with depth

    # (d) Q source at this host: the top-3 knots of the Step-1 grid carry a
    # marginal-but-sufficient ln(x+h) span (~0.051 >= MIN_SPAN 0.05), so the
    # measured-Q estimator RUNS (it would fall back only below the span gate)
    # and the ctor uses the measured most-local Q, recorded in local_q_diag.
    # (The large local exponent at this shallow depth is the LOCAL Q the attach
    # wants — not the far-field q*; the dual-process profiles are sigmoid.)
    assert new_unc._q_override is not None
    assert new_unc.local_q_diag is not None
    _q1, _q2, _drift = new_unc.local_q_diag
    assert abs(float(new_unc.decay_extrap_Q) - _q2) < 1e-12
    assert local_q_tail.DIAG["n_local2"] >= 1


def test_legacy_tail_gating_is_noop(solved_host, monkeypatch):
    for form in ("exp", "0"):
        monkeypatch.setenv("HAFISCAL_PF_DECAY_EXTRAP", form)
        t = deepcopy(solved_host)
        cf_obj = t.solution[0].cFunc
        assert spt.maybe_rewrap_types([t]) == 0
        assert t.solution[0].cFunc is cf_obj  # untouched object


def test_measured_q_lands_on_deep_grid(monkeypatch):
    # Synthetic deep-grid host: exact power-law gap around the PF line with
    # enough (x+h) leverage for the two-secant estimator.
    monkeypatch.delenv("HAFISCAL_PF_DECAY_EXTRAP", raising=False)
    monkeypatch.delenv("HAFISCAL_PF_DECAY_Q", raising=False)
    MPC, H, Q_true = 0.0054, 196.85, 0.61
    m = np.geomspace(0.5, 3 * H, 80)
    x = m + H
    gap = 0.5 * (x / x[-1]) ** (-Q_true)
    c = MPC * x - gap
    m0 = np.insert(m, 0, 0.0)
    c0 = np.insert(c, 0, 0.0)
    host_unc = LinearInterp(m0, c0, intercept_limit=MPC * H, slope_limit=MPC)
    cnst = LinearInterp(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    sol = SimpleNamespace(cFunc=LowerEnvelope(host_unc, cnst, nan_bool=False),
                          MPCmin=MPC, hNrm=H)
    t = SimpleNamespace(solution=[sol])
    ok, reason = spt.rewrap_type_cfunc_powerlaw(t)
    assert ok, reason
    new_unc = t.solution[0].cFunc.functions[0]
    assert new_unc._q_override is not None
    assert abs(float(new_unc.decay_extrap_Q) - Q_true) < 1e-6
    assert new_unc.local_q_diag is not None


def test_double_rewrap_is_refused(solved_host, monkeypatch):
    monkeypatch.delenv("HAFISCAL_PF_DECAY_EXTRAP", raising=False)
    t = deepcopy(solved_host)
    assert spt.maybe_rewrap_types([t]) == 1
    ok, reason = spt.rewrap_type_cfunc_powerlaw(t)
    assert not ok and "already power-law" in reason


def test_step1_grid_resolver_anchors(monkeypatch):
    # F7 (2026-07-24): Step-1's grid comes from the SST resolver with ITS OWN
    # primitives (R=Rsave=1.02**0.25, Γ=1) and anchors (legacy 20/20,
    # aXtraMin=1e-5, count_basis_anchor=20). Default => K·h̄ top ≈ 604.5 with
    # the basis-192 count; legacy opt-outs => UNCOERCED 20/20 (byte-identical).
    import math
    import grid_sizing as gs
    b = _base_params()
    R = float(b["Rsave"])
    G = float(np.asarray(b["PermGroFac"]).reshape(-1)[0])
    kw = dict(Rfree=R, PermGroFac=G, legacy_aMax=b["aXtraMax"],
              legacy_count=b["aXtraCount"], aXtraMin=b["aXtraMin"],
              count_basis_anchor=20)
    aMax, aCount, why = gs.resolve_solve_grid(environ={}, **kw)
    assert math.isclose(aMax, 3.0 * G / (R - G))          # ≈ 604.478
    assert 600 < aMax < 610
    assert aCount == gs.solve_grid_count(aMax, aXtraMin=float(b["aXtraMin"]),
                                         legacy_aMax=20, legacy_count=192)
    assert 230 < aCount < 245 and why is not None
    for env in ({"HAFISCAL_PF_DECAY_EXTRAP": "exp"},
                {"HAFISCAL_PF_DECAY_EXTRAP": "0"},
                {"HAFISCAL_PF_DECAY_Q": "slope"}):
        aMax, aCount, why = gs.resolve_solve_grid(environ=env, **kw)
        assert why is None
        assert aMax == b["aXtraMax"] and type(aMax) is type(b["aXtraMax"])
        assert aCount == b["aXtraCount"] and type(aCount) is type(b["aXtraCount"])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
