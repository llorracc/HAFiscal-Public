"""Cache-key COVERAGE tripwire (Plan 2, STEP 1 / GATE 3).

Reads ``Code/HA-Models/docs/ENV_FLAGS.md`` as the authoritative flag inventory and
checks **set-coverage** between each flag's ``cache-key:`` classification and the
``solution_cache.keys._HAFISCAL_NUMERICAL_ENV_VARS`` whitelist:

  * every flag classified ``paired`` or ``path`` MUST appear in the whitelist;
  * every flag classified ``excluded`` MUST be absent from the whitelist;
  * (``transitive`` flags are unconstrained — they are captured via the hashed
    agent/eco params, so they may be in OR out of the whitelist without failing.)

WHAT THIS TEST IS — AND IS NOT (read before trusting it as a guarantee)
-----------------------------------------------------------------------
This is a **coverage tripwire**, NOT a matched-pair correctness proof. It only checks
that the docs↔whitelist *sets* agree under the human-authored ``cache-key:`` labels in
ENV_FLAGS.md. It CANNOT decide whether a flag is genuinely matched-paired with the
calibration — that judgment is *semantic* and human-owned: the calibration β is
re-estimated PAIRED with a regime (e.g. ``HAFISCAL_PERMGROFAC_FIX`` /
``HAFISCAL_GIC_SHAVE_ON_GPF``), so a flag's effect can be *transitively captured* in the
hashed ``DiscFac``/``PermGroFac`` and STILL need keying because cross-loading the other
regime's solution is meaningless. A mechanical "is it transitively captured?" classifier
would have *re-introduced* BUG-047/BUG-059 (it would have said "captured → no need to
key"). The source of truth for matched-pairing is therefore:

    * ``Code/HA-Models/_permgrofac.py`` (the hard ``stamp_regime`` / ``assert_regime``
      guard + ``permgrofac_calib_path`` regime-paired calibration selection), and
    * ``Code/HA-Models/_regime.py`` (the composite cache fingerprint), and
    * the ``feedback_calibration_solver_matched_pair`` standing rule
      ("{PermGroFac regime, calibration, interpretation} move together").

This test is the cheap *coverage net* that would have caught BUG-047/BUG-059 as a
documentation-vs-whitelist gap; the hard runtime backstop is the fingerprint guard
(``_regime.assert_fingerprint``, exercised by ``test_fingerprint_guard.py``).

ROBUSTNESS
----------
The structured ``cache-key:`` field is being ADDED to ENV_FLAGS.md by the parent task
(Plan 2 STEP 1/STEP 6). Until at least one flag carries that tag, the docs side of the
coverage check is undefined, so this test ``pytest.skip``s with a clear message rather
than hard-failing. The duplicate-whitelist assertion (below) does NOT depend on the tag
and always runs.

Pure-stdlib regex scan over the registry + a single import of the whitelist tuple; runs
in well under a second.
"""
import os
import re
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent          # .../Code/HA-Models/solution_cache
_HA_MODELS = _HERE.parent                          # .../Code/HA-Models
_REGISTRY = _HA_MODELS / "docs" / "ENV_FLAGS.md"

# Import the whitelist tuple the same way the other solution_cache tests do.
sys.path.insert(0, str(_HERE))
from keys import _HAFISCAL_NUMERICAL_ENV_VARS  # noqa: E402


# One ``### HAFISCAL_<NAME>`` heading per flag (mirrors test_env_flag_registry.py).
_HEADING = re.compile(r"^### (HAFISCAL_[A-Z0-9_]+)\s*$", re.MULTILINE)

# The ``cache-key:`` classification, accepted in either of the two forms the parent
# might use, case-insensitively:
#   * a bold field on its own line:   **Cache-key:** paired
#   * an inline lowercase token:       cache-key: paired
# Capture the first classification word (paired|path|transitive|excluded).
_CACHE_KEY_FIELD = re.compile(
    r"(?:\*\*\s*cache-key\s*:\s*\*\*|cache-key\s*:)\s*[`*]*"
    r"(paired|path|transitive|excluded)\b",
    re.IGNORECASE,
)

_PAIRED_OR_PATH = {"paired", "path"}
_EXCLUDED = {"excluded"}
_TRANSITIVE = {"transitive"}
_VALID_CLASSES = _PAIRED_OR_PATH | _EXCLUDED | _TRANSITIVE


def _parse_registry_blocks():
    """Return ordered list of (flag_name, entry_block_text) from ENV_FLAGS.md.

    Block boundaries match test_env_flag_registry._parse_registry: an entry runs to
    the next ``### `` heading or the next ``## `` section, whichever comes first.
    """
    assert _REGISTRY.is_file(), f"registry file missing: {_REGISTRY}"
    text = _REGISTRY.read_text(encoding="utf-8")
    headings = list(_HEADING.finditer(text))
    entries = []
    for i, match in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        block = text[match.start():end]
        section_break = re.search(r"\n## ", block)
        if section_break:
            block = block[: section_break.start() + 1]
        entries.append((match.group(1), block))
    return entries


def _classify_flags():
    """Return {flag_name: cache-key class} for every flag that carries the tag."""
    classified = {}
    for name, block in _parse_registry_blocks():
        m = _CACHE_KEY_FIELD.search(block)
        if m:
            classified[name] = m.group(1).lower()
    return classified


def test_whitelist_has_no_duplicate_entries():
    """``_HAFISCAL_NUMERICAL_ENV_VARS`` must list each flag at most once.

    Regression for the ``HAFISCAL_GIC_SHAVE_ON_GPF`` duplicate de-duped 2026-06-22
    (it was listed twice; harmless to the hash because ``_env_dict`` collapses it to a
    dict key, but a maintenance trap — Plan 2 STEP 0/STEP 1). This assertion is
    independent of the ``cache-key:`` tag, so it always runs.
    """
    seen = {}
    for v in _HAFISCAL_NUMERICAL_ENV_VARS:
        seen[v] = seen.get(v, 0) + 1
    dupes = sorted(name for name, n in seen.items() if n > 1)
    assert not dupes, (
        "_HAFISCAL_NUMERICAL_ENV_VARS (solution_cache/keys.py) has duplicate "
        f"entries: {dupes}. List each flag exactly once."
    )


def test_cache_key_classification_is_valid_when_present():
    """Any ``cache-key:`` value present must be one of the four sanctioned classes.

    Skips (does not fail) when the tag has not been added to ENV_FLAGS.md yet, so this
    file can land before the parent's STEP-1/STEP-6 doc edit.
    """
    classified = _classify_flags()
    if not classified:
        pytest.skip(
            "cache-key: classification not yet in ENV_FLAGS.md "
            "(parent task Plan 2 STEP 1/STEP 6 adds the per-flag "
            "`cache-key: paired|path|transitive|excluded` field). "
            "No flag carries the tag — coverage check is undefined; skipping."
        )
    bad = {n: c for n, c in classified.items() if c not in _VALID_CLASSES}
    assert not bad, (
        f"flags with an unrecognized cache-key class (expected one of "
        f"{sorted(_VALID_CLASSES)}): {bad}"
    )


def test_cache_key_coverage_matches_whitelist():
    """docs↔whitelist SET coverage (the tripwire).

    RED if any ``paired``/``path`` flag is absent from
    ``_HAFISCAL_NUMERICAL_ENV_VARS``, or any ``excluded`` flag is present.
    ``transitive`` flags are unconstrained.

    Skips (does not fail) when no flag carries a ``cache-key:`` tag yet — the docs side
    of the check is undefined, so there is nothing to cover. (This is a COVERAGE
    tripwire, not a matched-pair proof; matched-pairing is human-owned — see the module
    docstring + ``_permgrofac.py`` / ``_regime.py`` + the
    ``feedback_calibration_solver_matched_pair`` rule.)
    """
    classified = _classify_flags()
    if not classified:
        pytest.skip(
            "cache-key: classification not yet in ENV_FLAGS.md "
            "(parent task Plan 2 STEP 1/STEP 6 adds the per-flag "
            "`cache-key: paired|path|transitive|excluded` field). "
            "Docs side of the coverage check is undefined; skipping. "
            "This is a COVERAGE tripwire only — matched-pairing is human-owned "
            "(_permgrofac.py / _regime.py / feedback_calibration_solver_matched_pair)."
        )

    whitelist = set(_HAFISCAL_NUMERICAL_ENV_VARS)
    problems = []

    missing = sorted(
        n for n, c in classified.items()
        if c in _PAIRED_OR_PATH and n not in whitelist
    )
    for name in missing:
        problems.append(
            f"{name}: classified '{classified[name]}' (cache-key-affecting) in "
            f"ENV_FLAGS.md but ABSENT from _HAFISCAL_NUMERICAL_ENV_VARS — add it to "
            f"the whitelist in solution_cache/keys.py (this is the BUG-047/BUG-059 "
            f"coverage-gap class)."
        )

    present = sorted(
        n for n, c in classified.items()
        if c in _EXCLUDED and n in whitelist
    )
    for name in present:
        problems.append(
            f"{name}: classified 'excluded' in ENV_FLAGS.md but PRESENT in "
            f"_HAFISCAL_NUMERICAL_ENV_VARS — a speedup/scheduling/reporting flag in "
            f"the key silently invalidates the cache on every flip; remove it from "
            f"the whitelist or re-classify it in ENV_FLAGS.md."
        )

    assert not problems, (
        f"{len(problems)} cache-key coverage problem(s) "
        f"(docs ENV_FLAGS.md ↔ keys._HAFISCAL_NUMERICAL_ENV_VARS):\n  - "
        + "\n  - ".join(problems)
        + "\n\nNOTE: this is a COVERAGE tripwire, NOT a matched-pair proof. "
        "Matched-pairing (does this flag need keying even when transitively "
        "captured?) is human-owned: see _permgrofac.py + _regime.py + the "
        "feedback_calibration_solver_matched_pair rule."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-q"]))
