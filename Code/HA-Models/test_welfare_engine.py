"""Guard tests for the canonical welfare-engine resolution (2026-08-02).

Covers the precedence contract of welfare_engine.resolve_welfare_engine and
the mutation semantics of apply_welfare_engine_defaults. Pure-dict tests —
no os.environ mutation, no simulation.
"""

import pytest

from welfare_engine import (ARC_KEYS, HYBRID_BUNDLE,
                            apply_welfare_engine_defaults,
                            resolve_welfare_engine)


def test_default_is_hybrid():
    assert resolve_welfare_engine({}) == "hybrid"


def test_explicit_wins_over_world_guard():
    env = {"HAFISCAL_WELFARE_ENGINE": "hybrid",
           "HAFISCAL_QE_FIDELITY": "1",
           "HAFISCAL_WORLD": "as-corrected"}
    assert resolve_welfare_engine(env) == "hybrid"
    env["HAFISCAL_WELFARE_ENGINE"] = "hark"
    assert resolve_welfare_engine(env) == "hark"


def test_world_guard_forces_hark():
    assert resolve_welfare_engine({"HAFISCAL_QE_FIDELITY": "1"}) == "hark"
    assert resolve_welfare_engine({"HAFISCAL_WORLD": "as-corrected"}) == "hark"
    assert resolve_welfare_engine({"HAFISCAL_WORLD": "default"}) == "hybrid"


def test_invalid_explicit_raises():
    with pytest.raises(ValueError):
        resolve_welfare_engine({"HAFISCAL_WELFARE_ENGINE": "hybird"})


def test_hybrid_apply_setdefaults_bundle():
    env = {}
    assert apply_welfare_engine_defaults(env, verbose=False) == "hybrid"
    assert {k: env[k] for k in HYBRID_BUNDLE} == HYBRID_BUNDLE


def test_hybrid_apply_respects_explicit_override():
    env = {"HAFISCAL_REPLAY_CRATIO_PREV": "0"}
    apply_welfare_engine_defaults(env, verbose=False)
    assert env["HAFISCAL_REPLAY_CRATIO_PREV"] == "0"  # explicit env wins
    assert env["HAFISCAL_JAX_MC_REPLAY_AD"] == "1"


def test_hark_apply_clears_arc_flags_only():
    env = {k: "1" for k in HYBRID_BUNDLE}
    env["HAFISCAL_WELFARE_ENGINE"] = "hark"
    apply_welfare_engine_defaults(env, verbose=False)
    for k in ARC_KEYS:
        assert k not in env
    # Legacy wrapper-era defaults are NOT arc flags and stay untouched.
    assert env["HAFISCAL_USE_JAX_MC"] == "1"
    assert env["HAFISCAL_USE_SOLUTION_CACHE"] == "1"


def test_bundle_contains_the_cogate_pair():
    # The loader co-gate (solution_cache/cache.py:346-350): PRESOLVE alone is
    # a silent no-op. The bundle must always carry the pair together.
    assert HYBRID_BUNDLE["HAFISCAL_REPLAY_PRESOLVE_CACHE"] == "1"
    assert HYBRID_BUNDLE["HAFISCAL_AD_INIT_CACHE"] == "1"
