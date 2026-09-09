#!/usr/bin/env python3
"""verify_level.py — canonical reader for the reuse-fidelity VERIFY axis.

The VERIFY axis (thread-2 taxonomy) is ORTHOGONAL to the METHOD axis
(``HAFISCAL_MULTIPLIER_ENGINE``) and the WORLD axis (``HAFISCAL_WORLD``). It selects
HOW HARD a run double-checks that any REUSED solution — the AD solution cache, the
cross-phase belief seed, a warm start — still gives the right answer:

    numeric (default) — the numerically-equivalent standard (Tier-F/I): a reuse is
                        accepted when the RESULT is unchanged to tolerance. Fast. This is
                        the default reproduction path; behavior is byte-identical to
                        pre-flag code (no consumer acts unless the level is raised).
    complete          — numeric + the opt-in double-checks: the multi-seed cross-section
                        drift+SE headline (welfare_drift_report.py), re-solve-and-compare
                        on any reuse, and the de-biased one-step result-validity gate
                        (Gate A — see the derivation doc in Refs).
    byte              — complete + byte-exact reuse: the deterministic fingerprint gate
                        (Gate B) + a full-object cache round-trip. The strictest level.

Surfaced by ``reproduce.sh`` as ``--complete`` / ``--byte-identical`` (default = numeric),
which export ``HAFISCAL_VERIFY_LEVEL``. Every entry point reads the level THROUGH this
module so the interpretation (ordering, safe-degradation) lives in exactly one place.

Why a strictness RANK (not just three names): each level is a SUPERSET of the checks of
the levels below it, so "is the active level at least X?" is the natural gate
(``verify_at_least(COMPLETE)``), and reproduce.sh's strictest-requested-level-wins
composition mirrors the same order.

Safe degradation (standing rule — abundant diagnostics, never abort a long run on a
typo): an unrecognized ``HAFISCAL_VERIFY_LEVEL`` warns once on stderr and falls back to
``numeric`` (the fast default), rather than raising. A *programmer* error — passing an
unknown level to ``verify_at_least`` in code — DOES raise, because that is a bug, not a
user typo.

Spec:    plans/20260622_reuse-fidelity-verification-flag-taxonomy.md
Build:   plans/20260622_thread2-flag-taxonomy-build-execution-plan.md
Gate A:  conclusions_private/2026-06-22_reuse-gate-A-vs-B-and-debias-derivation.md
Criterion: conclusions_private/2026-06-22_numerical-stability-acceptance-criterion.md
"""
from __future__ import annotations

import os
import sys

NUMERIC = "numeric"
COMPLETE = "complete"
BYTE = "byte"

# Strictness rank: each level INCLUDES every check of the levels below it.
_RANK = {NUMERIC: 0, COMPLETE: 1, BYTE: 2}

ENV_VAR = "HAFISCAL_VERIFY_LEVEL"

# Emit the unrecognized-value warning at most once per process (a long reproduction may
# call get_verify_level() many times; one warning is informative, many are noise).
_warned_unrecognized = set()


def get_verify_level():
    """Return the active verify level: one of ``numeric`` | ``complete`` | ``byte``.

    Unset -> ``numeric``. Case- and whitespace-insensitive. An unrecognized value
    safe-degrades to ``numeric`` with a one-time stderr warning (never raises)."""
    raw = os.environ.get(ENV_VAR, NUMERIC)
    level = raw.strip().lower()
    if level not in _RANK:
        if raw not in _warned_unrecognized:
            _warned_unrecognized.add(raw)
            print(
                f"[verify_level] WARNING: {ENV_VAR}={raw!r} is unrecognized "
                f"(expected one of {sorted(_RANK, key=_RANK.get)}); "
                f"degrading to {NUMERIC!r} (the fast, behavior-neutral default).",
                file=sys.stderr,
            )
        return NUMERIC
    return level


def verify_at_least(level):
    """True iff the ACTIVE level is at least ``level`` in strictness.

    Gate opt-in checks with this, e.g. ``if verify_at_least(COMPLETE): run_drift()``.
    Raises ValueError on an unknown ``level`` argument — that is a programmer error
    (a code typo), distinct from a user's env-var typo, which safe-degrades."""
    if level not in _RANK:
        raise ValueError(
            f"unknown verify level {level!r}; expected one of "
            f"{sorted(_RANK, key=_RANK.get)}")
    return _RANK[get_verify_level()] >= _RANK[level]


def verify_rank(level=None):
    """Integer strictness rank (numeric=0 < complete=1 < byte=2).

    ``verify_rank()`` ranks the active level; ``verify_rank('byte')`` ranks a named one.
    A name not in the rank table maps to 0 (numeric) — matches get_verify_level's
    safe-degradation so callers need no extra guard."""
    lvl = level if level is not None else get_verify_level()
    return _RANK.get(lvl, 0)


if __name__ == "__main__":
    _lvl = get_verify_level()
    print(
        f"{ENV_VAR}={_lvl} (rank {verify_rank(_lvl)}; "
        f"complete={verify_at_least(COMPLETE)}, byte={verify_at_least(BYTE)})"
    )
