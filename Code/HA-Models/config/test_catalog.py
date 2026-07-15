"""Guard test for the config-worlds catalog (SoT).

Validates internal consistency of the taxonomy + that every env-controlled
setting is a real documented flag in docs/ENV_FLAGS.md. Pure/offline; no
os.environ access, no model imports.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from catalog import (  # noqa: E402  (self-contained module; dir added to path above)
    BUG_FIX,
    IMPROVEMENT,
    DISCRETIONARY,
    CATEGORIES,
    CATALOG,
    DEFAULT,
    AS_CORRECTED,
    world_value,
    resolve_world,
)

_ENV_FLAGS = Path(__file__).resolve().parents[1] / "docs" / "ENV_FLAGS.md"


def test_categories_valid_and_fields_present():
    names = [s.name for s in CATALOG]
    assert len(names) == len(set(names)), "duplicate setting names"
    for s in CATALOG:
        assert s.category in CATEGORIES
        assert s.canonical != "" or s.env_var == "HAFISCAL_MC_SHUFFLE", s.name
        assert s.evidence, f"{s.name} missing evidence"
        assert s.refs, f"{s.name} missing refs"


def test_bug_fixes_identical_across_worlds():
    for s in CATALOG:
        if s.category == BUG_FIX:
            assert world_value(s, DEFAULT) == world_value(s, AS_CORRECTED) == s.canonical, s.name


def test_discretionary_reverts_in_as_corrected():
    for s in CATALOG:
        if s.category == DISCRETIONARY:
            assert world_value(s, DEFAULT) == s.canonical, s.name
            assert world_value(s, AS_CORRECTED) == s.paper, s.name


def test_improvement_off_in_as_corrected_unless_opted_in():
    for s in CATALOG:
        if s.category == IMPROVEMENT:
            assert world_value(s, DEFAULT) == s.canonical, s.name
            assert world_value(s, AS_CORRECTED) == s.paper, s.name
            on = world_value(s, AS_CORRECTED, frozenset({s.name}))
            assert on == s.canonical, f"{s.name} opt-in should flip to canonical"


def test_resolve_world_returns_env_map():
    d = resolve_world(DEFAULT)
    ac = resolve_world(AS_CORRECTED)
    # default and as-corrected must differ (discretionary + improvement settings)
    assert d != ac
    # env-controlled only
    assert all(k.startswith("HAFISCAL_") for k in d)


def test_every_env_setting_is_documented_in_env_flags():
    text = _ENV_FLAGS.read_text(encoding="utf-8")
    for s in CATALOG:
        if s.env_var:
            assert f"### {s.env_var}" in text, f"{s.env_var} not in ENV_FLAGS.md"
