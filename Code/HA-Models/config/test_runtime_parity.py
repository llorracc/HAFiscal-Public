"""Runtime-parity guard: config/ catalog == what EstimParameters actually applies.

R2 wiring (2026-06-13): EstimParameters' canonical block selects a WORLD via
`HAFISCAL_WORLD` and applies the world-varying runtime settings from
`config.catalog.resolve_world(...)`. This guard proves the wiring stays faithful:

  1. For BOTH worlds, the env values EstimParameters sets for the authorized subset
     equal `resolve_world(world)` — so the catalog cannot silently drift from the code.
  2. NON-BREAKING contract for `default`: the authorized subset resolves to the exact
     legacy literals the block used before R2 (MC_SHUFFLE=1, stratified, transition,
     aMax=1300, perm=on, welfare6_fix=on, ui=bug_fix).
  3. The settings NOT in the world-apply subset are not forced *by the world axis*:
       - HAFISCAL_INTERPRETATION is set to the global ESC default (owner ruling Q5,
         wired 2026-06-14) UNCONDITIONALLY in the canonical block — so it is present,
         but WORLD-INVARIANT (identical in default and as-corrected), never world-varying.
       - HAFISCAL_TM_A_INDEXED stays UNSET (it is set per-entry-point, BUG-033).

EstimParameters imports HARK, so each world is checked in a clean subprocess.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from config.catalog import resolve_world  # noqa: E402

# Must mirror EstimParameters._WORLD_APPLY (the settings the canonical block is
# authorized to setdefault from the resolved world).
WORLD_APPLY = (
    "HAFISCAL_MC_SHUFFLE",
    "HAFISCAL_SHUFFLE_MRKV_TRANSITION",
    "HAFISCAL_SHUFFLE_NEWBORN_FIX",
    "HAFISCAL_TM_AMAX",
    "HAFISCAL_PERM_DURING_UNEMP",
    "HAFISCAL_WELFARE6_FIX_DUR_AVG",
    "HAFISCAL_UI_STATE_ENCODING",
)
# Settings outside the world-apply subset (see module docstring):
#  - WORLD_INVARIANT_GLOBAL: set unconditionally by the canonical block to a single
#    value in BOTH worlds (must never vary by world).
#  - WORLD_UNSET: the world wiring must leave these unset (owned per-entry-point).
WORLD_INVARIANT_GLOBAL = {"HAFISCAL_INTERPRETATION": "ESC"}
WORLD_UNSET = ("HAFISCAL_TM_A_INDEXED",)

# The byte-for-byte legacy literals the pre-R2 block produced for the `default` world.
DEFAULT_LEGACY_LITERALS = {
    "HAFISCAL_MC_SHUFFLE": "1",
    "HAFISCAL_SHUFFLE_MRKV_TRANSITION": "stratified",
    "HAFISCAL_SHUFFLE_NEWBORN_FIX": "transition",
    "HAFISCAL_TM_AMAX": "1300",
    "HAFISCAL_PERM_DURING_UNEMP": "on",
    "HAFISCAL_WELFARE6_FIX_DUR_AVG": "on",
    "HAFISCAL_UI_STATE_ENCODING": "bug_fix",
}

_HA_ROOT = Path(__file__).resolve().parents[1]
_FROM_PANDEMIC = _HA_ROOT / "FromPandemicCode"


def _import_estimparameters_env(world: str | None) -> dict:
    """Import EstimParameters in a clean subprocess; return the resulting env subset."""
    keys = list(WORLD_APPLY) + list(WORLD_INVARIANT_GLOBAL) + list(WORLD_UNSET)
    code = (
        "import sys; sys.argv=['x']\n"
        "import os, json\n"
        "import EstimParameters\n"
        f"print('PARITY_JSON=' + json.dumps({{k: os.environ.get(k) for k in {keys!r}}}))\n"
    )
    # Strip any HAFISCAL_* the test runner may carry so the child sees a clean slate.
    env = {k: v for k, v in os.environ.items() if not k.startswith("HAFISCAL_")}
    if world is not None:
        env["HAFISCAL_WORLD"] = world
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(_FROM_PANDEMIC),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"EstimParameters import failed (world={world!r}):\n{proc.stderr[-2000:]}"
    )
    line = next(ln for ln in proc.stdout.splitlines() if ln.startswith("PARITY_JSON="))
    return json.loads(line[len("PARITY_JSON="):])


@pytest.mark.parametrize("world", ["default", "as-corrected"])
def test_runtime_matches_catalog(world):
    """EstimParameters' applied subset == resolve_world(world) for that subset."""
    applied = _import_estimparameters_env(world)
    expected = resolve_world(world, include_estimation_only=False)
    for k in WORLD_APPLY:
        assert k in expected, f"{k} missing from resolve_world({world!r})"
        assert applied[k] == expected[k], (
            f"world={world}: {k}={applied[k]!r} applied but catalog says {expected[k]!r}"
        )


def test_default_world_is_byte_for_byte_legacy():
    """The `default` world must reproduce the exact pre-R2 literals (non-breaking)."""
    applied = _import_estimparameters_env("default")
    for k, v in DEFAULT_LEGACY_LITERALS.items():
        assert applied[k] == v, f"default world drifted: {k}={applied[k]!r} != {v!r}"


def test_unset_world_equals_default():
    """No HAFISCAL_WORLD set behaves identically to HAFISCAL_WORLD=default."""
    assert _import_estimparameters_env(None) == _import_estimparameters_env("default")


def test_world_unset_settings_stay_unset():
    """TM_A_INDEXED must remain unset by the world wiring (set per-entry-point)."""
    for world in (None, "default", "as-corrected"):
        applied = _import_estimparameters_env(world)
        for k in WORLD_UNSET:
            assert applied[k] is None, (
                f"world={world}: {k} was forced to {applied[k]!r}; the world wiring must not "
                f"touch it (set per-entry-point)."
            )


def test_interpretation_is_global_esc_and_world_invariant():
    """INTERPRETATION is the global ESC default (Q5) — present, and identical in both worlds."""
    vals = {}
    for world in (None, "default", "as-corrected"):
        applied = _import_estimparameters_env(world)
        for k, v in WORLD_INVARIANT_GLOBAL.items():
            assert applied[k] == v, (
                f"world={world}: {k}={applied[k]!r} but the global default must be {v!r} "
                f"(owner ruling Q5, ESC default-flip)."
            )
            vals.setdefault(k, applied[k])
            assert applied[k] == vals[k], (
                f"{k} varies by world ({applied[k]!r} != {vals[k]!r}); it must be world-invariant."
            )
