"""Composite matched-pair regime fingerprint for the solution cache (Plan 2, 2026-06-22).

Extends the PermGroFac matched-pair guard (``_permgrofac.py``: ``stamp_regime`` /
``assert_regime``, which cover ONLY the PermGroFac regime) to the full set of
regime-determining inputs a cached AD solution must match before it can be reused:
the PermGroFac regime, the GIC-shave-on-GPF regime (BUG-053), and the resolved config
world / method / interpretation.

A cached solution is reusable ONLY under an identical ``regime_fingerprint()``; a mismatch
is a HARD refusal at cache load — strictly stronger than the soft AD-residual "verify in
one iteration" gate that was rejected as unsound (too coarse at 1e-2, basin-blind, and
RNG-perturbing). See ``plans/20260622_content-addressed-solution-cache-warmstart-1iter-verify.md``.

This guard is DETERMINISTIC (a tuple comparison): no numerics, no RNG, no floating point,
so it never perturbs the welfare simulation and is bit-neutral on the accept path.
"""
import os

# Reuse the PermGroFac regime primitives — the existing hard guard this composite extends.
from _permgrofac import permgrofac_regime, stamp_regime, assert_regime  # noqa: F401


def gic_shave_on_gpf():
    """Raw tag for the BUG-053 GIC-shave-on-GPF regime (``HAFISCAL_GIC_SHAVE_ON_GPF``).

    Captures the literal env setting (unset -> ``'default'``) so any flip yields a distinct
    fingerprint. The flag flips whether ``theGICfactor`` caps the growth-patience factor
    (=1, the fix) or beta directly (=0), changing the cap-binding College beta atoms ->
    a numerically distinct cFunc paired with a regime-specific calibration.
    """
    return os.environ.get("HAFISCAL_GIC_SHAVE_ON_GPF", "default")


def _config_world_method_interp():
    """``(world, method, interpretation)`` from the resolved config; a ``('?','?','?')``
    fallback if ``config.effective_config()`` is unavailable in a stripped context — never
    crash a cache hit (Plan 2 §7 risk: fall back to the env-flag-only fingerprint + log)."""
    try:
        import config
        c = config.effective_config()

        def _g(k):
            if isinstance(c, dict):
                return c.get(k, "?")
            return getattr(c, k, "?")
        return (str(_g("world")), str(_g("method")), str(_g("interpretation")))
    except Exception:
        return ("?", "?", "?")


def regime_fingerprint():
    """Composite regime tag a cached solution must match to be reused:
    ``[permgrofac_regime, gic_shave_on_gpf, world, method, interpretation]``.

    Returned as a list (JSON/pickle round-trip friendly; JSON turns tuples into lists,
    so ``assert_fingerprint`` normalizes to list before comparing)."""
    w, m, i = _config_world_method_interp()
    return [permgrofac_regime(), gic_shave_on_gpf(), w, m, i]


def assert_fingerprint(stored_fp, context="cache load"):
    """HARD-raise if a stored regime fingerprint disagrees with the live one.

    Soft on a MISSING (``None``) stored fingerprint — legacy cache entries predating this
    guard still load, matching ``assert_regime``'s untagged-passes policy. HARD on any
    explicit mismatch. This is the authoritative wrong-regime backstop for cache reuse
    (the BUG-047 / BUG-059 silent-wrong-reuse class becomes a loud, deterministic refusal).
    """
    if stored_fp is None:
        return  # legacy entry with no fingerprint — defer to the existing assert_regime
    live = regime_fingerprint()
    if list(stored_fp) != list(live):
        raise RuntimeError(
            f"[matched-pair] {context}: cached solution was solved under regime fingerprint "
            f"{list(stored_fp)} but the active regime is {list(live)}. Reusing a solution from "
            "a different (PermGroFac / GIC-shave / world / method / interpretation) regime is a "
            "meaningless mismatched pairing — re-solve under the current flags, or purge "
            "solution_cache/ for this key. "
            "(plans/20260622_content-addressed-solution-cache-warmstart-1iter-verify.md.)"
        )
