"""Pytest wrapper for the equation-tag registry checker (fast tier, no solves).

Runs check_eqn_registry.py's forward + reverse checks in --strict mode against
the committed eqn_registry.yaml.  See plans/20260611_doloplus-eqn-tag-registry.md.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_eqn_registry  # noqa: E402


def test_registry_strict():
    """Registry is internally consistent and covers every in-code citation."""
    assert check_eqn_registry.main(["--strict"]) == 0


def test_canonical_yaml_parses():
    """The canonical YAML spec re-parses (guards the STATUS header + spec edits)."""
    data = check_eqn_registry.load_canonical_yaml()
    assert data["name"] == "hafiscal_household"
    assert check_eqn_registry.yaml_equation_blocks(data), "no equation blocks found"
