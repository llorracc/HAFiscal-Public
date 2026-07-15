"""Guard tests for the config resolver (axes, precedence, footgun gate, banner).

Pure/offline. Imports the package (config.resolve) so the relative imports work;
apply() is exercised only against a throwaway os.environ copy.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from config.resolve import resolve, format_banner, apply, METHODS  # noqa: E402
from config.catalog import DEFAULT, AS_CORRECTED  # noqa: E402


def test_world_base_matches_catalog():
    r = resolve(DEFAULT)
    # owner ruling 2026-06-13 (Q5): ESC is the default-world interpretation (== paper's)
    assert r.env["HAFISCAL_INTERPRETATION"] == "ESC"
    assert r.env["HAFISCAL_GICX_MODE"] == "hardcoded"
    r2 = resolve(AS_CORRECTED)
    assert r2.env["HAFISCAL_INTERPRETATION"] == "ESC"
    # owner ruling 2026-06-14: 2-D 'hardcoded' GICx is used in BOTH worlds (result-neutral);
    # the paper's 3-D 'legacy' NM lives only on the frozen old branch.
    assert r2.env["HAFISCAL_GICX_MODE"] == "hardcoded"


def test_improvement_opt_in_layers_onto_as_corrected():
    r = resolve(AS_CORRECTED, improvements=["gicx"])
    assert r.env["HAFISCAL_GICX_MODE"] == "hardcoded"
    assert r.provenance["HAFISCAL_GICX_MODE"] == "improvement:gicx"
    # discretionary stays at paper
    assert r.env["HAFISCAL_INTERPRETATION"] == "ESC"


def test_unknown_inputs_raise():
    with pytest.raises(ValueError):
        resolve("nonsense-world")
    with pytest.raises(ValueError):
        resolve(DEFAULT, improvements=["not-an-improvement"])
    with pytest.raises(ValueError):
        resolve(DEFAULT, method="QQ")


def test_method_and_scope_axes():
    r = resolve(DEFAULT, method="both", scope=[1, 2, 5])
    assert r.env["HAFISCAL_SIM_METHOD"] == "both"
    assert r.env["HAFISCAL_RUN_STEP_1"] == "1"
    assert r.env["HAFISCAL_RUN_STEP_3"] == "0"
    assert r.env["HAFISCAL_RUN_STEP_5"] == "1"
    assert r.scope == (1, 2, 5)


def test_override_has_highest_precedence():
    r = resolve(DEFAULT, overrides={"HAFISCAL_INTERPRETATION": "ESC"})
    assert r.env["HAFISCAL_INTERPRETATION"] == "ESC"
    assert r.provenance["HAFISCAL_INTERPRETATION"] == "override"


def test_footgun_gate_blocks_plain_shuffle():
    with pytest.raises(ValueError, match="FOOTGUN"):
        resolve(DEFAULT, overrides={"HAFISCAL_SHUFFLE_MRKV_TRANSITION": "shuffle"})
    # escape hatch
    r = resolve(DEFAULT, overrides={"HAFISCAL_SHUFFLE_MRKV_TRANSITION": "shuffle"},
                allow_footguns=True)
    assert r.env["HAFISCAL_SHUFFLE_MRKV_TRANSITION"] == "shuffle"


def test_banner_mentions_world_and_provenance():
    b = format_banner(resolve(AS_CORRECTED, improvements=["gicx"]))
    assert "world        : as-corrected" in b
    assert "improvement:gicx" in b


def test_apply_uses_setdefault_semantics():
    saved = dict(os.environ)
    try:
        os.environ.pop("HAFISCAL_INTERPRETATION", None)
        os.environ["HAFISCAL_GICX_MODE"] = "preset-wins"
        r = resolve(DEFAULT)
        did = apply(r)
        assert os.environ["HAFISCAL_INTERPRETATION"] == "ESC"   # newly set (owner ruling 2026-06-13: ESC is the default-world interpretation)
        assert os.environ["HAFISCAL_GICX_MODE"] == "preset-wins"  # preserved
        assert "HAFISCAL_INTERPRETATION" in did
        assert "HAFISCAL_GICX_MODE" not in did
    finally:
        os.environ.clear()
        os.environ.update(saved)
