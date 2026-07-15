"""
Unit tests for AggFiscalType's `self.interpretation` attribute.

Per Phase 0.5 of plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md.

Verifies that the read-precedence (kwarg > env var > 'CDC' default) works
correctly. The attribute exists for downstream consumers that route TM-a
calls — that threading has since LANDED: the TM-a kernel functions (33.4-33.9)
take an `interpretation` parameter, several tm_methods.py call sites read
`getattr(agent, 'interpretation', 'CDC')`, and the estimation path threads
`get_interpretation()` (BUG-051 matched-pair fix, 2026-06-05). The production
Simulate.py dispatch itself remains interpretation-independent (it propagates
only the `tm_a_indexed` flag).
"""

import os
import sys
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

# CLAUDE.md note: EstimParameters reads sys.argv. Patch BEFORE importing.
# Save original argv and use placeholder so the module-level eval() succeeds.
_SAVED_ARGV = sys.argv
sys.argv = ['test_aggfiscal_interpretation_attr']

# Now safe to import.
from copy import deepcopy
from EstimParameters import init_dropout
from AggFiscalModel import AggFiscalType

# Restore argv after imports so pytest's own discovery isn't affected.
sys.argv = _SAVED_ARGV


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """Default each test to no env var set, so tests are independent."""
    monkeypatch.delenv('HAFISCAL_INTERPRETATION', raising=False)


def _make_minimal_agent(**kwds):
    """Construct AggFiscalType with minimal valid args + any extra kwds."""
    init = deepcopy(init_dropout)
    init.update(kwds)
    return AggFiscalType(**init)


def test_interpretation_default_is_CDC():
    """No kwarg, no env var → 'CDC'."""
    agent = _make_minimal_agent()
    assert agent.interpretation == 'CDC'


def test_interpretation_env_ESC(monkeypatch):
    monkeypatch.setenv('HAFISCAL_INTERPRETATION', 'ESC')
    agent = _make_minimal_agent()
    assert agent.interpretation == 'ESC'


def test_interpretation_env_lowercase_normalized(monkeypatch):
    monkeypatch.setenv('HAFISCAL_INTERPRETATION', 'esc')
    agent = _make_minimal_agent()
    assert agent.interpretation == 'ESC'


def test_interpretation_kwarg_overrides_env(monkeypatch):
    """Explicit kwarg wins over env var."""
    monkeypatch.setenv('HAFISCAL_INTERPRETATION', 'CDC')
    agent = _make_minimal_agent(interpretation='ESC')
    assert agent.interpretation == 'ESC'


def test_interpretation_kwarg_lowercase_normalized():
    """Lowercase kwarg accepted, normalized to upper."""
    agent = _make_minimal_agent(interpretation='cdc')
    assert agent.interpretation == 'CDC'


def test_interpretation_invalid_kwarg_raises():
    with pytest.raises(ValueError, match="interpretation must be 'CDC' or 'ESC'"):
        _make_minimal_agent(interpretation='FOO')


def test_interpretation_invalid_env_raises(monkeypatch):
    monkeypatch.setenv('HAFISCAL_INTERPRETATION', 'BOGUS')
    with pytest.raises(ValueError, match="must be 'CDC' or 'ESC'"):
        _make_minimal_agent()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
