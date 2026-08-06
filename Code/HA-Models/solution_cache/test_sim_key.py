"""Plan 2 GATE 4 — SIM-cache key unit test (DESIGN-ONLY helpers in keys.py).

Asserts ``gather_sim_inputs``'s hash CHANGES whenever any panel-determining
input changes — specifically each of:
    {seed_offset, use_shuffle, HAFISCAL_SHUFFLE_MRKV_TRANSITION, T_sim,
     a per-cohort AgentCount}
plus a couple of the other RNG/shape determinants for good measure — and that
``verify_sim_panel`` accepts a panel whose recorded shock-hash matches and
rejects one whose generating arrays differ.

Uses a tiny STUB economy (a plain object exposing only the attributes the key
helpers read) so the test is fast and needs no HARK build. These helpers are
gated behind HAFISCAL_USE_SIM_CACHE (default OFF) and are not wired into any
run path; this test exercises the key/verify logic directly.
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from keys import (  # noqa: E402
    gather_sim_inputs, hash_sim_inputs, verify_sim_panel, _panel_shock_hash,
)


# --------------------------------------------------------------------------
# Tiny stub economy: only the attributes the SIM-key helpers actually read.
# _agent_params_dict reads scalar/array params via hasattr; _cohort_seeds reads
# agent.seed and agent.IncShkDstn[0].seed; gather_solve_inputs reads
# len(eco.agents) and per-agent AgentCount; _ad_params_dict reads eco-level AD
# attrs (absent here -> empty, which is fine for the key).
# --------------------------------------------------------------------------
class _StubDstn:
    def __init__(self, seed):
        self.seed = int(seed)


class _StubAgent:
    def __init__(self, agent_count, seed, incshk_seed):
        self.AgentCount = int(agent_count)
        self.seed = int(seed)
        self.IncShkDstn = [_StubDstn(incshk_seed)]
        # A couple of cFunc-affecting params so the solve-input base isn't empty.
        self.CRRA = 2.0
        self.DiscFac = 0.97


class _StubEco:
    def __init__(self, agents):
        self.agents = agents


def _make_eco(agent_counts=(100, 200), base_seed=0):
    agents = [
        _StubAgent(ac, seed=base_seed + i, incshk_seed=763607780 + i)
        for i, ac in enumerate(agent_counts)
    ]
    return _StubEco(agents)


def _key(**overrides):
    """Build a SIM-key hash with a baseline config, overriding selected args."""
    eco = overrides.pop("eco", None) or _make_eco()
    kwargs = dict(
        shock_type="recessionCheck",
        mc_method="hark_mc",
        seeds=(0,),
        use_shuffle=False,
        init_panel_method="hark_ref",
        agent_count_per_cohort=None,  # -> reads stub AgentCount
        seed_offset=0,
        T_sim=200,
        act_T=200,
        economy_mrkv_init="norec",
    )
    kwargs.update(overrides)
    return hash_sim_inputs(gather_sim_inputs(eco, **kwargs))


def _with_env(var, value, fn):
    """Run fn() with os.environ[var]=value, restoring the prior value after."""
    sentinel = object()
    prev = os.environ.get(var, sentinel)
    os.environ[var] = value
    try:
        return fn()
    finally:
        if prev is sentinel:
            os.environ.pop(var, None)
        else:
            os.environ[var] = prev


def test_seed_offset_changes_hash():
    base = _key(seed_offset=0)
    other = _key(seed_offset=1)
    assert base != other, "seed_offset must change the SIM key"
    print(f"OK  seed_offset changes hash: {base[:12]} != {other[:12]}")


def test_use_shuffle_changes_hash():
    base = _key(use_shuffle=False)
    other = _key(use_shuffle=True)
    assert base != other, "use_shuffle must change the SIM key"
    print(f"OK  use_shuffle changes hash: {base[:12]} != {other[:12]}")


def test_shuffle_mrkv_transition_changes_hash():
    base = _with_env("HAFISCAL_SHUFFLE_MRKV_TRANSITION", "plain", lambda: _key())
    other = _with_env(
        "HAFISCAL_SHUFFLE_MRKV_TRANSITION", "stratified", lambda: _key())
    assert base != other, (
        "HAFISCAL_SHUFFLE_MRKV_TRANSITION (plain vs stratified, the +8.26%-UI "
        "footgun) must change the SIM key")
    print(f"OK  SHUFFLE_MRKV_TRANSITION changes hash: {base[:12]} != {other[:12]}")


def test_T_sim_changes_hash():
    base = _key(T_sim=200)
    other = _key(T_sim=400)
    assert base != other, "T_sim (panel length) must change the SIM key"
    print(f"OK  T_sim changes hash: {base[:12]} != {other[:12]}")


def test_per_cohort_agent_count_changes_hash():
    base = _key(eco=_make_eco(agent_counts=(100, 200)))
    other = _key(eco=_make_eco(agent_counts=(100, 201)))  # one cohort N changed
    assert base != other, "a per-cohort AgentCount change must change the SIM key"
    print(f"OK  per-cohort AgentCount changes hash: {base[:12]} != {other[:12]}")


def test_cohort_rng_seed_changes_hash():
    """The per-cohort agent RNG seed is a panel determinant (changes realization)."""
    base = _key(eco=_make_eco(base_seed=0))
    other = _key(eco=_make_eco(base_seed=10000))  # different agent .seed streams
    assert base != other, "per-cohort agent RNG seed must change the SIM key"
    print(f"OK  cohort RNG seed changes hash: {base[:12]} != {other[:12]}")


def test_tm_init_env_changes_hash():
    base = _with_env("HAFISCAL_WELFARE6_TM_INIT", "1", lambda: _key())
    other = _with_env("HAFISCAL_WELFARE6_TM_INIT", "0", lambda: _key())
    assert base != other, "HAFISCAL_WELFARE6_TM_INIT (init panel) must change the key"
    print(f"OK  WELFARE6_TM_INIT changes hash: {base[:12]} != {other[:12]}")


def test_economy_mrkv_init_changes_hash():
    base = _key(economy_mrkv_init="norec")
    other = _key(economy_mrkv_init="rec")
    assert base != other, "EconomyMrkv_init path must change the SIM key"
    print(f"OK  EconomyMrkv_init changes hash: {base[:12]} != {other[:12]}")


def test_identical_inputs_same_hash():
    """Sanity: identical inputs hash identically (no spurious nondeterminism)."""
    eco = _make_eco()
    assert _key(eco=eco) == _key(eco=eco), "identical SIM inputs must hash equally"
    print("OK  identical SIM inputs hash equally")


def test_verify_sim_panel_accepts_matching():
    sh = np.array([[1.0, 2.0], [3.0, 4.0]])
    sb = np.array([0, 1, 0, 1], dtype=np.int64)
    recorded = _panel_shock_hash(sh, sb)
    panel = {"shock_history": sh, "sim_birth": sb, "shock_hash": recorded}
    ok, recomputed, rec = verify_sim_panel(panel, seeds=(0,))
    assert ok and recomputed == recorded == rec, (
        f"verify_sim_panel should accept a matching panel; got ok={ok}")
    print("OK  verify_sim_panel accepts a matching panel")


def test_verify_sim_panel_rejects_altered_shocks():
    sh = np.array([[1.0, 2.0], [3.0, 4.0]])
    sb = np.array([0, 1, 0, 1], dtype=np.int64)
    recorded = _panel_shock_hash(sh, sb)
    # Tamper with one shock value -> recomputed hash must differ.
    sh2 = sh.copy()
    sh2[0, 0] = 99.0
    panel = {"shock_history": sh2, "sim_birth": sb, "shock_hash": recorded}
    ok, recomputed, rec = verify_sim_panel(panel, seeds=(0,))
    assert (not ok) and recomputed != recorded, (
        f"verify_sim_panel must reject an altered panel; got ok={ok}")
    print("OK  verify_sim_panel rejects an altered-shocks panel")


def test_verify_sim_panel_rejects_missing_hash():
    sh = np.array([[1.0, 2.0]])
    sb = np.array([0, 1], dtype=np.int64)
    panel = {"shock_history": sh, "sim_birth": sb}  # no recorded shock_hash
    ok, _, rec = verify_sim_panel(panel, seeds=(0,))
    assert (not ok) and rec is None, "missing recorded hash must not verify"
    print("OK  verify_sim_panel rejects a panel with no recorded hash")


if __name__ == "__main__":
    test_seed_offset_changes_hash()
    test_use_shuffle_changes_hash()
    test_shuffle_mrkv_transition_changes_hash()
    test_T_sim_changes_hash()
    test_per_cohort_agent_count_changes_hash()
    test_cohort_rng_seed_changes_hash()
    test_tm_init_env_changes_hash()
    test_economy_mrkv_init_changes_hash()
    test_identical_inputs_same_hash()
    test_verify_sim_panel_accepts_matching()
    test_verify_sim_panel_rejects_altered_shocks()
    test_verify_sim_panel_rejects_missing_hash()
    print("All SIM-key (GATE 4) tests passed.")
