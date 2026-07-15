"""Gate tests for the opt-in Step-2 multi-state global-Newton (NAMG) base solver
(``HAFISCAL_STEP2_NAMG``; default OFF) in ``AggFiscalModel.AggregateDemandEconomy``.

Covers:
  * env gate + per-state param mapping (fast, pure-function unit tests);
  * deprecated ``HAFISCAL_STEP2_ANDERSON`` alias (the path now drives ``method='newton'``,
    not the Anderson contraction it was first named for — alias kept one cycle, warns);
  * regime / matched-pair gating (only fires in base / AD-off ``num_macro_states==1``,
    ``BoroCnstArt==0``, ``permgrofac_fix_on()``);
  * default-OFF behavior is the EGM path (the determinism JSON is byte-identical OFF —
    verified out-of-band; here we assert the path is inert when the flag is unset);
  * ON policy parity vs the production EGM base solve < 5e-3 (same fixed point to the
    fixed-grid-vs-endogenous-grid resolution gap);
  * cache-key disjointness: the NAMG path never runs in a regime where
    ``solution_cache`` (welfare6 / AD-on / Step-5 only) is used, so it cannot collide with
    an EGM-keyed cache entry; belt-and-suspenders, ``HAFISCAL_STEP2_NAMG`` is in the
    ``solution_cache`` key whitelist so flipping it changes the hash.

The integration test imports ``EstimAggFiscalMAIN`` (with ``HAFISCAL_SKIP_ESTIMATION=1``),
which builds + solves the base estimation economy once (~40s); skip it with
``HAFISCAL_SKIP_STEP2_NAMG_ITEST=1``.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# EstimParameters reads sys.argv[1] as Rfree; under pytest argv[1] is the test path.
# Trim to argv[0] so the default Rfree_base=[1.01] is used (CLAUDE.md: patch argv in tests).
_saved_argv = sys.argv[:]
sys.argv = sys.argv[:1]

from AggFiscalModel import AggregateDemandEconomy  # noqa: E402

sys.argv = _saved_argv


# --------------------------------------------------------------------------- #
# Fast, pure-function unit tests (no economy build).
# --------------------------------------------------------------------------- #
def test_default_off_env_gate(monkeypatch):
    monkeypatch.delenv("HAFISCAL_STEP2_NAMG", raising=False)
    monkeypatch.delenv("HAFISCAL_STEP2_ANDERSON", raising=False)
    assert AggregateDemandEconomy._step2_namg_enabled() is False
    monkeypatch.setenv("HAFISCAL_STEP2_NAMG", "1")
    assert AggregateDemandEconomy._step2_namg_enabled() is True
    monkeypatch.setenv("HAFISCAL_STEP2_NAMG", "0")
    assert AggregateDemandEconomy._step2_namg_enabled() is False


def test_deprecated_anderson_alias(monkeypatch):
    """``HAFISCAL_STEP2_ANDERSON`` is a DEPRECATED alias for ``HAFISCAL_STEP2_NAMG``.
    The Step-2 opt-in was renamed when the path switched from the Anderson contraction
    to the global-Newton (NAMG) solver; the old flag still enables the path for one
    back-compat cycle and emits a DeprecationWarning. The current flag takes precedence
    and does NOT warn."""
    monkeypatch.delenv("HAFISCAL_STEP2_NAMG", raising=False)
    monkeypatch.delenv("HAFISCAL_STEP2_ANDERSON", raising=False)
    assert AggregateDemandEconomy._step2_namg_enabled() is False

    # Old flag alone -> enabled, with a deprecation warning.
    monkeypatch.setenv("HAFISCAL_STEP2_ANDERSON", "1")
    with pytest.warns(DeprecationWarning):
        assert AggregateDemandEconomy._step2_namg_enabled() is True

    # Current flag takes precedence and must NOT warn (it short-circuits first).
    import warnings
    monkeypatch.setenv("HAFISCAL_STEP2_NAMG", "1")
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert AggregateDemandEconomy._step2_namg_enabled() is True


def test_per_state_param_mapping():
    f = AggregateDemandEconomy._per_state_param
    np.testing.assert_array_equal(f(1.01, 4), np.full(4, 1.01))          # scalar -> broadcast
    np.testing.assert_array_equal(f([1.0, 2.0, 3.0, 4.0], 4),            # exact length
                                  np.array([1.0, 2.0, 3.0, 4.0]))
    np.testing.assert_array_equal(f([1.0, 2.0, 3.0, 4.0, 9.0, 9.0], 4),  # base-slice of 6-encoding
                                  np.array([1.0, 2.0, 3.0, 4.0]))
    assert f([1.0, 2.0], 4) is None                                      # too short, not scalar


# --------------------------------------------------------------------------- #
# Integration: build the real base estimation economy once.
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def base_economy():
    if os.environ.get("HAFISCAL_SKIP_STEP2_NAMG_ITEST", "") == "1":
        pytest.skip("HAFISCAL_SKIP_STEP2_NAMG_ITEST=1")
    os.environ["HAFISCAL_SKIP_ESTIMATION"] = "1"
    os.environ.pop("HAFISCAL_STEP2_NAMG", None)
    _argv = sys.argv[:]
    sys.argv = sys.argv[:1]  # EstimParameters reads argv[1] as Rfree
    try:
        import EstimAggFiscalMAIN as E
    finally:
        sys.argv = _argv
    return E.AggDemandEconomy


def _solve_capture(eco, use_namg):
    if use_namg:
        os.environ["HAFISCAL_STEP2_NAMG"] = "1"
    else:
        os.environ.pop("HAFISCAL_STEP2_NAMG", None)
    for ag in eco.agents:
        ag._step2_namg_used = False
    eco.solve()
    used = sum(bool(getattr(ag, "_step2_namg_used", False)) for ag in eco.agents)
    cfuncs = [[ag.solution[0].cFunc[j] for j in range(np.asarray(ag.MrkvArray[0]).shape[0])]
              for ag in eco.agents]
    return used, cfuncs


def test_default_off_is_egm(base_economy):
    """Flag unset -> EGM path: no agent reports having used the NAMG solver."""
    used, _ = _solve_capture(base_economy, use_namg=False)
    assert used == 0


def test_on_fires_and_matches_egm_policy(base_economy):
    """Flag set -> every base/AD-off agent uses NAMG; policy matches EGM < 5e-3."""
    used_off, cf_off = _solve_capture(base_economy, use_namg=False)
    used_on, cf_on = _solve_capture(base_economy, use_namg=True)
    assert used_off == 0
    assert used_on == len(base_economy.agents) > 0

    m = np.linspace(0.5, 12.0, 60)
    ones = np.ones_like(m)
    worst = 0.0
    for ce, cn in zip(cf_off, cf_on):
        for j in range(len(ce)):
            c_e = np.asarray(ce[j](m, ones), dtype=float)
            c_n = np.asarray(cn[j](m, ones), dtype=float)
            worst = max(worst, float(np.max(np.abs(c_e - c_n))))
    assert worst < 5e-3, f"policy parity max|dc|={worst:.3e} exceeds 5e-3"


def test_regime_gate_recession_falls_back(base_economy):
    """num_macro_states > 1 (recession / AD-on) -> NAMG refuses, caller uses EGM."""
    os.environ["HAFISCAL_STEP2_NAMG"] = "1"
    agent = base_economy.agents[0]
    saved = agent.num_macro_states
    try:
        agent.num_macro_states = 2
        assert base_economy._try_solve_namg_base(agent, warm_start=False) is False
    finally:
        agent.num_macro_states = saved
        os.environ.pop("HAFISCAL_STEP2_NAMG", None)


def test_permgrofac_fix_gate(base_economy, monkeypatch):
    """FIX=0 (legacy marginal-value factor) -> NAMG refuses (matched-pair hazard)."""
    import _permgrofac
    monkeypatch.setattr(_permgrofac, "permgrofac_fix_on", lambda: False)
    # AggFiscalModel imported the symbol by name; patch there too.
    import AggFiscalModel
    monkeypatch.setattr(AggFiscalModel, "permgrofac_fix_on", lambda: False)
    agent = base_economy.agents[0]
    assert base_economy._try_solve_namg_base(agent, warm_start=False) is False


def test_cache_key_includes_namg_flag():
    """HAFISCAL_STEP2_NAMG is in the solution_cache key whitelist, so a NAMG-solved
    entry can never cross-load against an EGM-keyed one (belt-and-suspenders: the path is
    confined to num_macro_states==1, where the AD-on Step-5 cache is structurally never used).
    Verify the flag is in the whitelist AND that flipping it changes the hash."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    from solution_cache import keys as ck

    assert "HAFISCAL_STEP2_NAMG" in ck._HAFISCAL_NUMERICAL_ENV_VARS

    saved = os.environ.get("HAFISCAL_STEP2_NAMG")
    try:
        os.environ.pop("HAFISCAL_STEP2_NAMG", None)
        env_off = ck._env_dict()
        os.environ["HAFISCAL_STEP2_NAMG"] = "1"
        env_on = ck._env_dict()
    finally:
        if saved is None:
            os.environ.pop("HAFISCAL_STEP2_NAMG", None)
        else:
            os.environ["HAFISCAL_STEP2_NAMG"] = saved

    assert env_off["HAFISCAL_STEP2_NAMG"] == ""
    assert env_on["HAFISCAL_STEP2_NAMG"] == "1"
    inputs_off = {"env": env_off}
    inputs_on = {"env": env_on}
    assert ck.hash_solve_inputs(inputs_off) != ck.hash_solve_inputs(inputs_on)
