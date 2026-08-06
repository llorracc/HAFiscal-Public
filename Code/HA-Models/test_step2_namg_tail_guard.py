"""F1 everywhere-audit gate tests: the Step-2 NAMG tail-form consistency guard.

Same guard class as fti_step1's Phase-0 guard (test_fti_tail_guard.py): the
NAMG-Markov opt-in produces EXPONENTIAL-tailed base solutions, so under the
measured-Q power-law default (HAFISCAL_PF_DECAY_EXTRAP truthy, not 'exp' —
default ON since 2026-07-23) the opt-in must REFUSE LOUDLY at solve() time
rather than silently solve with the wrong tail or silently fall back to EGM.
Legal paths: the explicit legacy tail (exp / 0), or the benchmarking escape
hatch HAFISCAL_NAMG_ALLOW_TAIL_MISMATCH=1.

The guard lives in ``AggregateDemandEconomy._step2_namg_enabled`` (a
staticmethod evaluated once per ``solve()``), so it is unit-testable
in-process with env patching — no economy construction needed.
"""
import sys
from pathlib import Path

import pytest

_HA_MODELS = Path(__file__).resolve().parent
_FPC = _HA_MODELS / "FromPandemicCode"
for _p in (str(_HA_MODELS), str(_FPC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# EstimParameters (imported by AggFiscalModel) parses sys.argv for Rfree/CRRA/
# IncUnemp overrides; under pytest argv holds test paths -> patch it first
# (the standard repo test pattern, see CLAUDE.md).
_argv_saved, sys.argv = sys.argv, [sys.argv[0]]
try:
    from AggFiscalModel import AggregateDemandEconomy  # noqa: E402
finally:
    sys.argv = _argv_saved

_GUARD = AggregateDemandEconomy._step2_namg_enabled


def _set_env(monkeypatch, **env):
    for var in ("HAFISCAL_STEP2_NAMG", "HAFISCAL_STEP2_ANDERSON",
                "HAFISCAL_PF_DECAY_EXTRAP", "HAFISCAL_NAMG_ALLOW_TAIL_MISMATCH"):
        monkeypatch.delenv(var, raising=False)
    for var, val in env.items():
        monkeypatch.setenv(var, val)


def test_off_is_false_and_never_raises(monkeypatch):
    for form in (None, "powerlaw", "exp", "0"):
        env = {} if form is None else {"HAFISCAL_PF_DECAY_EXTRAP": form}
        _set_env(monkeypatch, **env)
        assert _GUARD() is False


def test_guard_fires_on_default_powerlaw_form(monkeypatch):
    # NAMG on + flag unset (default = powerlaw since 2026-07-23) -> refuse
    _set_env(monkeypatch, HAFISCAL_STEP2_NAMG="1")
    with pytest.raises(RuntimeError, match="EXPONENTIAL tail"):
        _GUARD()


def test_guard_fires_on_explicit_powerlaw_form(monkeypatch):
    _set_env(monkeypatch, HAFISCAL_STEP2_NAMG="1",
             HAFISCAL_PF_DECAY_EXTRAP="powerlaw")
    with pytest.raises(RuntimeError, match="HAFISCAL_NAMG_ALLOW_TAIL_MISMATCH"):
        _GUARD()


def test_guard_fires_via_deprecated_alias(monkeypatch):
    _set_env(monkeypatch, HAFISCAL_STEP2_ANDERSON="1")
    with pytest.deprecated_call():
        with pytest.raises(RuntimeError, match="EXPONENTIAL tail"):
            _GUARD()


def test_guard_allows_legacy_tails_and_escape_hatch(monkeypatch):
    for env in ({"HAFISCAL_STEP2_NAMG": "1", "HAFISCAL_PF_DECAY_EXTRAP": "exp"},
                {"HAFISCAL_STEP2_NAMG": "1", "HAFISCAL_PF_DECAY_EXTRAP": "0"},
                {"HAFISCAL_STEP2_NAMG": "1",
                 "HAFISCAL_NAMG_ALLOW_TAIL_MISMATCH": "1"},
                {"HAFISCAL_STEP2_NAMG": "1",
                 "HAFISCAL_PF_DECAY_EXTRAP": "powerlaw",
                 "HAFISCAL_NAMG_ALLOW_TAIL_MISMATCH": "1"}):
        _set_env(monkeypatch, **env)
        assert _GUARD() is True, f"unexpected refusal under {env}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
