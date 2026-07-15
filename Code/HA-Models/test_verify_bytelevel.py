"""Tests for --byte-identical (VERIFY level 'byte') — thread-2 component 5.

Byte-exactness is achieved the spec-sanctioned interim way: under 'byte' the ~3e-7 lossy
solution-cache reuse is forced OFF at every reuse site, so every solve is fresh-from-scratch
→ byte-exact by construction. These tests pin: the shared gate (`byte_exact_forces_fresh_solve`),
the behavioural force-fresh in the single-solve cache, the c3 byte tolerance (now exact), and
that every reuse site (both AD wrappers + the Leg-B belief seed) is guarded. Default / 'complete'
behaviour is unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HA = Path(__file__).resolve().parent
sys.path.insert(0, str(HA))
sys.path.insert(0, str(HA / "solution_cache"))
import cache as sc_cache            # noqa: E402  (solution_cache/cache.py)
import verify_resolve as vr         # noqa: E402


# --------------------------------------------------------------------------- #
# the shared gate
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("level,expect", [
    (None, False), ("numeric", False), ("complete", False), ("byte", True),
])
def test_byte_gate_by_level(monkeypatch, level, expect):
    if level is None:
        monkeypatch.delenv("HAFISCAL_VERIFY_LEVEL", raising=False)
    else:
        monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", level)
    assert sc_cache.byte_exact_forces_fresh_solve() is expect


def test_ad_cache_shares_the_gate():
    import ad_cache
    assert ad_cache.byte_exact_forces_fresh_solve is sc_cache.byte_exact_forces_fresh_solve


# --------------------------------------------------------------------------- #
# behavioural: the single-solve cache force-bypasses under byte (even cache ON)
# --------------------------------------------------------------------------- #
class _FakeEco:
    def __init__(self):
        self.solved = 0

    def solve(self):
        self.solved += 1

    def switch_shock_type(self, shock_type):  # not called for 'base'
        pass


def test_cached_eco_solve_forces_fresh_under_byte(monkeypatch):
    monkeypatch.setenv("HAFISCAL_USE_SOLUTION_CACHE", "1")   # cache ON ...
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "byte")      # ... but byte forces a fresh solve
    eco = _FakeEco()
    r = sc_cache.cached_eco_solve({"AggEco": eco}, shock_type="base")
    assert eco.solved == 1               # the eco.solve() pass-through ran ...
    assert r["cache_hit"] is False       # ... i.e. no cache reuse


def test_cached_eco_solve_not_forced_at_complete(monkeypatch):
    # at 'complete' the byte-bypass is NOT taken: with the cache OFF the off-branch is taken
    # for the ordinary reason, but the byte term contributes nothing (gate is False).
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "complete")
    assert sc_cache.byte_exact_forces_fresh_solve() is False


# --------------------------------------------------------------------------- #
# the c3 byte tolerance is now exact (reuse forced off -> fresh re-solve is bit-identical)
# --------------------------------------------------------------------------- #
def test_byte_tolerance_is_exact(monkeypatch):
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "byte")
    rtol, label = vr.tolerance()
    assert rtol == 0.0 and "byte-exact" in label
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "complete")
    assert vr.tolerance()[0] == 1e-6


# --------------------------------------------------------------------------- #
# static tripwires: every reuse site is guarded
# --------------------------------------------------------------------------- #
def test_ad_wrappers_guarded():
    src = (HA / "solution_cache" / "ad_cache.py").read_text()
    # both cached_solve_ad_recession + cached_solve_ad_recession_hark force-off under byte
    assert src.count("or byte_exact_forces_fresh_solve()") >= 2


def test_single_solve_cache_guarded():
    src = (HA / "solution_cache" / "cache.py").read_text()
    assert "or byte_exact_forces_fresh_solve()" in src


def test_belief_seed_guarded():
    src = (HA / "FromPandemicCode" / "welfare6_scenario.py").read_text()
    assert "byte_exact_forces_fresh_solve" in src
    assert "SEED skipped under --byte-identical" in src


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
