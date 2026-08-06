"""Stale-hit regression for the composite regime fingerprint (Plan 2, STEP 5 / GATE 2).

Proves ``_regime.assert_fingerprint`` HARD-RAISES when a cached solution's stored regime
fingerprint disagrees with the live regime — the deterministic backstop that converts the
BUG-047 / BUG-059 silent-wrong-reuse class into a loud refusal at cache load.

Three cases (all pure unit tests on ``_regime`` — NO HARK, NO economy build, <2s):

  1. BIG gap (PermGroFac regime). Stamp a payload fingerprint under
     ``HAFISCAL_PERMGROFAC_FIX=1`` (``pgfFix``), then flip the env to ``=0`` (``pgfLegacy``,
     the ~6-7% cFunc gap) and assert ``assert_fingerprint(stored)`` raises ``RuntimeError``.

  2. SMALL / discretionary gap. Flip a DISCRETIONARY regime dimension that shifts the cFunc
     <1% rather than the full PermGroFac flip — here ``HAFISCAL_INTERPRETATION`` (CDC↔ESC),
     which ``config.effective_config()`` reads, so it is a live fingerprint dimension. Assert
     it STILL raises. This is the case the demoted single-EGM-step probe would FALSE-PASS
     (a contraction undershoots a small gap in one step — Plan 2 §0 blocking issue 2): the
     fingerprint compares a TAG, so it is gap-MAGNITUDE-INDEPENDENT. If the interpretation
     dimension is somehow not live in this environment (``config`` unavailable → degraded
     ``'?'`` on both sides), the test falls back to the ``HAFISCAL_GIC_SHAVE_ON_GPF``
     dimension, which ``_regime`` reads directly (no ``config`` dependency) — the tag-compare
     is gap-magnitude-independent for ANY dimension, which is the whole point.

  3. LEGACY (None) fingerprint. A pre-guard cache entry carries no fingerprint; assert
     ``assert_fingerprint(None)`` does NOT raise (it defers to the existing
     ``assert_regime`` untagged-passes policy — same contract as ``_permgrofac``).

Pure ``_regime`` unit test: it imports ``_regime`` (which imports ``_permgrofac`` and,
lazily, the side-effect-free ``config`` package) but NOT HARK, and builds a tiny dict
payload rather than an eco — so it runs in well under a second.
"""
import os
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent          # .../Code/HA-Models/solution_cache
_HA_MODELS = _HERE.parent                          # .../Code/HA-Models (where _regime lives)
# _regime imports `from _permgrofac import ...`; both live at Code/HA-Models.
for _p in (str(_HA_MODELS), str(_HA_MODELS / "FromPandemicCode")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _regime  # noqa: E402


_REGIME_ENV_VARS = (
    "HAFISCAL_PERMGROFAC_FIX",
    "HAFISCAL_GIC_SHAVE_ON_GPF",
    "HAFISCAL_WORLD",
    "HAFISCAL_INTERPRETATION",
    "HAFISCAL_SIM_METHOD",
    "HAFISCAL_MULTIPLIER_ENGINE",
)


@pytest.fixture(autouse=True)
def _clean_regime_env(monkeypatch):
    """Each test starts from a known regime-env baseline (all regime vars cleared),
    then sets exactly the vars it needs via monkeypatch (auto-reverted after)."""
    for var in _REGIME_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    yield


def _fake_payload(fingerprint):
    """A minimal cache-payload-shaped dict (no HARK objects) carrying a stored
    fingerprint — mirrors the ``regime_fingerprint`` slot written by
    ``ad_cache._save_hark_ad_result``."""
    return {
        "version": 1,
        "result_type": "hark_ad_converged",
        "regime_fingerprint": fingerprint,
        # (no extracted_eco / stored — the guard fires BEFORE reconstruction)
    }


def test_no_hark_imported():
    """Sanity: ``_regime`` must stay a pure deterministic tuple comparison with no
    solver dependency — importing it must NOT drag in HARK (keeps it <2s and
    independent of the solver stack).

    Checked in a FRESH subprocess, not via this process's ``sys.modules``: the
    in-process check was order-dependent (any earlier test in the session that
    imports HARK — e.g. the ADelasticity round-trip guard, which builds HARK
    objects — would falsely trip it). The subprocess isolates the real invariant:
    "import _regime in isolation ⇒ HARK absent."""
    import subprocess
    code = (
        "import sys; "
        f"sys.path[:0] = [{str(_HA_MODELS)!r}, {str(_HA_MODELS / 'FromPandemicCode')!r}]; "
        "import _regime; "
        "sys.exit(1 if 'HARK' in sys.modules else 0)"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, (
        "importing _regime pulled in HARK — the fingerprint guard must stay a pure "
        f"deterministic tuple comparison with no solver dependency.\n{r.stderr}")


def test_big_gap_permgrofac_mismatch_raises(monkeypatch):
    """PermGroFac regime flip (FIX=1 stored → FIX=0 live) is a HARD refusal."""
    monkeypatch.setenv("HAFISCAL_PERMGROFAC_FIX", "1")
    stored = _regime.regime_fingerprint()
    assert stored[0] == "pgfFix", f"expected pgfFix under FIX=1, got {stored}"
    payload = _fake_payload(stored)

    # Now the live regime is the OTHER PermGroFac regime.
    monkeypatch.setenv("HAFISCAL_PERMGROFAC_FIX", "0")
    live = _regime.regime_fingerprint()
    assert live[0] == "pgfLegacy", f"expected pgfLegacy under FIX=0, got {live}"
    assert live != stored  # the gap is real

    with pytest.raises(RuntimeError, match="matched-pair"):
        _regime.assert_fingerprint(payload["regime_fingerprint"],
                                   context="test:big-gap")


def test_small_discretionary_gap_still_raises(monkeypatch):
    """A discretionary regime flip (<1% cFunc shift) STILL raises — the fingerprint
    compares a TAG, so it is gap-magnitude-independent (the case the single-step probe
    would FALSE-PASS). Primary dimension: interpretation (CDC↔ESC, read by
    config.effective_config). Falls back to GIC_SHAVE_ON_GPF (read directly by _regime)
    if interpretation is not a live fingerprint dimension here."""
    monkeypatch.setenv("HAFISCAL_PERMGROFAC_FIX", "1")
    monkeypatch.setenv("HAFISCAL_GIC_SHAVE_ON_GPF", "1")

    # Try the interpretation dimension first (discretionary; config-driven).
    monkeypatch.setenv("HAFISCAL_INTERPRETATION", "CDC")
    stored = _regime.regime_fingerprint()
    monkeypatch.setenv("HAFISCAL_INTERPRETATION", "ESC")
    live = _regime.regime_fingerprint()

    dimension = "interpretation (CDC->ESC)"
    if live == stored:
        # config.effective_config() not live here (degraded '?' on both sides) — fall
        # back to a regime dimension _regime reads directly. The tag-compare being
        # gap-magnitude-independent does not depend on WHICH dimension flips, so this
        # still demonstrates the required property.
        monkeypatch.setenv("HAFISCAL_INTERPRETATION", "ESC")  # keep interp fixed
        monkeypatch.setenv("HAFISCAL_GIC_SHAVE_ON_GPF", "1")
        stored = _regime.regime_fingerprint()
        monkeypatch.setenv("HAFISCAL_GIC_SHAVE_ON_GPF", "0")
        live = _regime.regime_fingerprint()
        dimension = "gic_shave_on_gpf (1->0)"

    assert live != stored, (
        f"no live discretionary fingerprint dimension found to flip "
        f"(tried {dimension}); cannot exercise the small-gap case — "
        f"fingerprint stayed {stored}")
    # The PermGroFac leg is UNCHANGED in both cases — proving this is a small,
    # non-PermGroFac (discretionary) gap, not the big BUG-047 flip.
    assert live[0] == stored[0] == "pgfFix", (
        f"small-gap case must hold the PermGroFac leg fixed; got "
        f"stored={stored}, live={live}")

    payload = _fake_payload(stored)
    with pytest.raises(RuntimeError, match="matched-pair"):
        _regime.assert_fingerprint(payload["regime_fingerprint"],
                                   context=f"test:small-gap [{dimension}]")


def test_none_fingerprint_legacy_does_not_raise(monkeypatch):
    """A legacy cache entry (no stored fingerprint) loads without raising — it defers to
    the existing assert_regime untagged-passes policy."""
    monkeypatch.setenv("HAFISCAL_PERMGROFAC_FIX", "0")  # arbitrary live regime
    payload = _fake_payload(None)
    # Must NOT raise.
    _regime.assert_fingerprint(payload["regime_fingerprint"], context="test:legacy")


def test_matching_fingerprint_does_not_raise(monkeypatch):
    """Sanity / NO-GO guard #4: an IDENTICAL stored vs live fingerprint is accepted
    exactly as today (the new guard must not weaken the accept path)."""
    monkeypatch.setenv("HAFISCAL_PERMGROFAC_FIX", "1")
    monkeypatch.setenv("HAFISCAL_INTERPRETATION", "ESC")
    stored = _regime.regime_fingerprint()
    payload = _fake_payload(stored)
    # Same env → same live fingerprint → must NOT raise.
    _regime.assert_fingerprint(payload["regime_fingerprint"], context="test:match")


if __name__ == "__main__":
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-q"]))
