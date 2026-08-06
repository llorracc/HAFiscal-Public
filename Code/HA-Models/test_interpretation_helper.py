"""
Unit tests for _interpretation.py helper module.

Per Phase 0.5 of plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md.
"""

import os
import sys
import tempfile
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from _interpretation import (
    get_interpretation, suffix_path, resolve_path,
    get_world, world_suffix, calib_suffix, resolve_calib_path,
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """Default each test to no env var set, so tests are independent."""
    monkeypatch.delenv('HAFISCAL_INTERPRETATION', raising=False)
    monkeypatch.delenv('HAFISCAL_WORLD', raising=False)


# -----------------------------------------------------------------------
# get_interpretation
# -----------------------------------------------------------------------

def test_get_interpretation_default_is_CDC():
    """No env var → 'CDC'."""
    assert get_interpretation() == 'CDC'


def test_get_interpretation_explicit_CDC(monkeypatch):
    monkeypatch.setenv('HAFISCAL_INTERPRETATION', 'CDC')
    assert get_interpretation() == 'CDC'


def test_get_interpretation_explicit_ESC(monkeypatch):
    monkeypatch.setenv('HAFISCAL_INTERPRETATION', 'ESC')
    assert get_interpretation() == 'ESC'


def test_get_interpretation_lowercase_normalized(monkeypatch):
    """Lowercase env var value is normalized to upper."""
    monkeypatch.setenv('HAFISCAL_INTERPRETATION', 'esc')
    assert get_interpretation() == 'ESC'


def test_get_interpretation_invalid_raises(monkeypatch):
    monkeypatch.setenv('HAFISCAL_INTERPRETATION', 'FOO')
    with pytest.raises(ValueError, match="must be 'CDC' or 'ESC'"):
        get_interpretation()


# -----------------------------------------------------------------------
# suffix_path
# -----------------------------------------------------------------------

def test_suffix_path_default_appends_CDC():
    """Default interpretation 'CDC' produces _CDC suffix."""
    assert suffix_path('foo.txt') == 'foo_CDC.txt'


def test_suffix_path_ESC(monkeypatch):
    monkeypatch.setenv('HAFISCAL_INTERPRETATION', 'ESC')
    assert suffix_path('Result_AllTarget.txt') == 'Result_AllTarget_ESC.txt'


def test_suffix_path_with_directory():
    """Directory components preserved."""
    assert suffix_path('/some/dir/foo.txt') == '/some/dir/foo_CDC.txt'


def test_suffix_path_rejects_non_txt():
    with pytest.raises(ValueError, match="expects a .txt path"):
        suffix_path('foo.csv')


# -----------------------------------------------------------------------
# resolve_path
# -----------------------------------------------------------------------

def test_resolve_path_suffixed_exists(tmp_path):
    """If suffixed file exists, return it."""
    base = tmp_path / 'foo.txt'
    suffixed = tmp_path / 'foo_CDC.txt'
    suffixed.write_text('hello')
    assert resolve_path(str(base)) == str(suffixed)


def test_resolve_path_fallback_unsuffixed(tmp_path):
    """If suffixed file doesn't exist, fall back to un-suffixed path."""
    base = tmp_path / 'foo.txt'
    # Neither file exists — but resolve_path returns the un-suffixed path
    # for the caller to attempt; existence check is the caller's job.
    assert resolve_path(str(base)) == str(base)


def test_resolve_path_with_ESC_env(tmp_path, monkeypatch):
    """With ESC env, suffixed path lookup uses _ESC."""
    monkeypatch.setenv('HAFISCAL_INTERPRETATION', 'ESC')
    base = tmp_path / 'foo.txt'
    suffixed = tmp_path / 'foo_ESC.txt'
    suffixed.write_text('hello')
    assert resolve_path(str(base)) == str(suffixed)


# -----------------------------------------------------------------------
# WORLD axis: get_world / world_suffix / calib_suffix
# -----------------------------------------------------------------------

def test_get_world_default():
    """No env var → 'default'."""
    assert get_world() == 'default'


def test_get_world_as_corrected(monkeypatch):
    monkeypatch.setenv('HAFISCAL_WORLD', 'as-corrected')
    assert get_world() == 'as-corrected'


def test_get_world_normalizes_case_and_space(monkeypatch):
    monkeypatch.setenv('HAFISCAL_WORLD', '  As-Corrected ')
    assert get_world() == 'as-corrected'


def test_get_world_invalid_raises(monkeypatch):
    monkeypatch.setenv('HAFISCAL_WORLD', 'qe')
    with pytest.raises(ValueError, match="must be 'default' or 'as-corrected'"):
        get_world()


def test_get_world_require_raises_when_unset():
    with pytest.raises(RuntimeError, match="must be set explicitly"):
        get_world(require=True)


def test_world_suffix_default_is_empty():
    assert world_suffix() == ''


def test_world_suffix_as_corrected(monkeypatch):
    monkeypatch.setenv('HAFISCAL_WORLD', 'as-corrected')
    assert world_suffix() == '_ascorrected'


def test_calib_suffix_combinations(monkeypatch):
    # CDC + default → '' (byte-for-byte legacy)
    assert calib_suffix() == ''
    # ESC + default → '_ESC'
    monkeypatch.setenv('HAFISCAL_INTERPRETATION', 'ESC')
    assert calib_suffix() == '_ESC'
    # ESC + as-corrected → '_ESC_ascorrected' (interp first, then world)
    monkeypatch.setenv('HAFISCAL_WORLD', 'as-corrected')
    assert calib_suffix() == '_ESC_ascorrected'
    # CDC + as-corrected → '_ascorrected'
    monkeypatch.delenv('HAFISCAL_INTERPRETATION', raising=False)
    assert calib_suffix() == '_ascorrected'


# -----------------------------------------------------------------------
# resolve_calib_path (world + interpretation aware betas reader)
# -----------------------------------------------------------------------

def test_resolve_calib_default_world_matches_resolve_path(tmp_path):
    """default world: resolve_calib_path behaves like resolve_path (legacy)."""
    base = tmp_path / 'DiscFacEstim.txt'
    base.write_text('betas')
    assert resolve_calib_path(str(base)) == str(base)


def test_resolve_calib_picks_world_file(tmp_path, monkeypatch):
    """ESC + as-corrected loads the _ESC_ascorrected file when present."""
    monkeypatch.setenv('HAFISCAL_INTERPRETATION', 'ESC')
    monkeypatch.setenv('HAFISCAL_WORLD', 'as-corrected')
    base = tmp_path / 'DiscFacEstim.txt'
    world_file = tmp_path / 'DiscFacEstim_ESC_ascorrected.txt'
    world_file.write_text('as-corrected betas')
    assert resolve_calib_path(str(base)) == str(world_file)


def test_resolve_calib_missing_world_warns_and_falls_back(tmp_path, monkeypatch):
    """as-corrected file missing → loud warning, fall back to default-world ESC."""
    monkeypatch.setenv('HAFISCAL_INTERPRETATION', 'ESC')
    monkeypatch.setenv('HAFISCAL_WORLD', 'as-corrected')
    base = tmp_path / 'DiscFacEstim.txt'
    default_world = tmp_path / 'DiscFacEstim_ESC.txt'
    default_world.write_text('default-world ESC betas')
    with pytest.warns(UserWarning, match="as-corrected calibration HAZARD"):
        got = resolve_calib_path(str(base))
    assert got == str(default_world)


def test_resolve_calib_rejects_non_txt():
    with pytest.raises(ValueError, match="expects a .txt path"):
        resolve_calib_path('foo.csv')


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
