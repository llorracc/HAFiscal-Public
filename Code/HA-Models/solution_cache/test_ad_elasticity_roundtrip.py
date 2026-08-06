"""Fast regression guard for the JAX-AD cache ADelasticity round-trip.

Root cause (2026-06-23): reconstruct_eco_solution restored eco.CFunc + agent
solutions but NOT eco.ADelasticity. On a JAX-AD cache HIT the reconstructed eco
kept the base ADelasticity (0.0), which DISABLES the AD externality in the
downstream welfare sim — the restored AD belief becomes inert and the result
silently collapses to the no-AD recession (flat Baseline AD welfare column).

These are CHEAP unit checks (no economy build) that lock in the three invariants
of the fix, complementing the heavy end-to-end gate in test_ad_cache_parity.py
(which is marked `slow` and was NOT run during the cascade that shipped the bug):

  1. reconstruct_eco_solution RESTORES eco.ADelasticity when the cache carries it.
  2. reconstruct_eco_solution does NOT raise when the key is absent — it is shared
     with the base solution cache, whose entries legitimately lack ADelasticity.
  3. _load_ad_result (JAX-AD loader) RAISES StaleADCacheError on a pre-fix cache
     with no ADelasticity, so the HIT path self-heals by re-solving rather than
     returning a silently-wrong (flat) result.
"""
import os
import pickle
import types

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
# reconstruct_eco_solution imports AggFiscalModel (CRule) + HARK lazily, so
# FromPandemicCode (a sibling of solution_cache) must be importable.
_FPC = os.path.abspath(os.path.join(_HERE, "..", "FromPandemicCode"))


def _ensure_paths():
    import sys
    for p in (_HERE, _FPC):
        if p not in sys.path:
            sys.path.insert(0, p)
    # AggFiscalModel -> EstimParameters/Parameters read sys.argv[1:] as
    # Rfree/CRRA/IncUnemp overrides (see CLAUDE.md). Under pytest argv carries the
    # test path, which crashes that parse; strip to argv[0] before the lazy import.
    sys.argv = sys.argv[:1]


def _import_serialize():
    _ensure_paths()
    import serialize  # noqa: E402
    return serialize


def test_reconstruct_restores_adelasticity_when_present():
    serialize = _import_serialize()
    eco = types.SimpleNamespace(agents=[], ADelasticity=0.0)
    extracted = {"cohorts": [], "eco_CFunc": None, "ADelasticity": 0.3}
    serialize.reconstruct_eco_solution(eco, extracted)
    assert eco.ADelasticity == 0.3, (
        "reconstruct must restore eco.ADelasticity from the cache; leaving it at "
        "0.0 disables the AD externality and flattens the AD welfare column")


def test_reconstruct_does_not_raise_when_adelasticity_absent():
    # The base solution cache shares reconstruct_eco_solution; its pre-fix entries
    # have no ADelasticity and base ADelasticity (0.0) needs no restoring. Must NOT
    # raise — only the AD loader enforces the AD-cache invariant.
    serialize = _import_serialize()
    eco = types.SimpleNamespace(agents=[], ADelasticity=0.0)
    extracted = {"cohorts": [], "eco_CFunc": None}  # no ADelasticity key
    serialize.reconstruct_eco_solution(eco, extracted)  # must not raise
    assert eco.ADelasticity == 0.0


def test_load_ad_result_raises_on_stale_cache(tmp_path):
    _ensure_paths()
    import ad_cache  # noqa: E402
    from serialize import StaleADCacheError

    # A pre-fix JAX-AD payload: valid version/result_type, NO ADelasticity in
    # extracted_eco, regime_fingerprint=None (legacy → soft fingerprint check).
    payload = {
        "version": 1,
        "result_type": "ad_converged",
        "regime_fingerprint": None,
        "extracted_eco": {"cohorts": [], "eco_CFunc": None},  # <- stale: no ADelasticity
        "result": {"converged": True, "iter_history": []},
    }
    pkl_path = os.path.join(str(tmp_path), "ad_stale.pkl")
    with open(pkl_path, "wb") as f:
        pickle.dump(payload, f)

    eco = types.SimpleNamespace(agents=[], ADelasticity=0.0)
    with pytest.raises(StaleADCacheError):
        ad_cache._load_ad_result(eco, pkl_path, meta_path=None)


def test_new_ad_result_passes_staleness_check(tmp_path):
    # The same payload WITH ADelasticity must NOT raise (it reconstructs cleanly).
    _ensure_paths()
    import ad_cache  # noqa: E402

    payload = {
        "version": 1,
        "result_type": "ad_converged",
        "regime_fingerprint": None,
        "extracted_eco": {"cohorts": [], "eco_CFunc": None, "ADelasticity": 0.3},
        "result": {"converged": True, "iter_history": []},
    }
    pkl_path = os.path.join(str(tmp_path), "ad_new.pkl")
    with open(pkl_path, "wb") as f:
        pickle.dump(payload, f)

    eco = types.SimpleNamespace(agents=[], ADelasticity=0.0)
    result = ad_cache._load_ad_result(eco, pkl_path, meta_path=None)
    assert eco.ADelasticity == 0.3
    assert result["converged"] is True
