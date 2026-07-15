"""Validate that HAFiscal/HARK SHAs no longer affect the cache hash.

Strategy: build the same inputs dict twice with different provenance, and
confirm hash_solve_inputs returns the same key.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from keys import hash_solve_inputs, check_provenance_match


def _make_inputs(hafiscal_sha, hark_sha, python_ver="3.11"):
    return {
        "shock_type": "recession",
        "mc_method": "hark_mc",
        "seeds": [0],
        "use_shuffle": False,
        "init_panel_method": "newborn_pool",
        "agent_count_per_cohort": [10000],
        "n_cohorts": 1,
        "agents": [{"CRRA": 2.0, "DiscFac": 0.97}],
        "ad": {"num_max_iterations_solvingAD": 10},
        "env": {"HAFISCAL_PLVL_GROWS_DURING_UNEMP": "off"},
        "provenance": {
            "hafiscal_sha": hafiscal_sha,
            "hark_sha": hark_sha,
            "python": python_ver,
        },
    }


def test_sha_excluded():
    a = _make_inputs("abc123", "deadbeef")
    b = _make_inputs("xyz789", "cafefeed")  # different SHAs
    ka = hash_solve_inputs(a)
    kb = hash_solve_inputs(b)
    assert ka == kb, (
        f"SHAs should be excluded from hash but keys differ:\n"
        f"  a (sha=abc123/deadbeef): {ka}\n"
        f"  b (sha=xyz789/cafefeed): {kb}")
    print(f"OK  hash excludes provenance: {ka[:12]}... matches across SHAs")


def test_numerical_param_still_invalidates():
    a = _make_inputs("abc123", "deadbeef")
    c = _make_inputs("abc123", "deadbeef")
    c["agents"][0]["CRRA"] = 3.0  # changed numerical param
    ka = hash_solve_inputs(a)
    kc = hash_solve_inputs(c)
    assert ka != kc, "Changed CRRA should produce different hash"
    print(f"OK  numerical change invalidates: {ka[:12]} != {kc[:12]}")


def test_check_provenance_match():
    cached = {"hafiscal_sha": "abc123", "hark_sha": "deadbeef", "python": "3.11"}
    # Current matches cached -> empty diff
    diffs = check_provenance_match(cached, current_provenance=cached)
    assert diffs == [], f"Expected no diffs but got {diffs}"
    # Different HAFiscal SHA -> one diff
    current = dict(cached, hafiscal_sha="xyz789")
    diffs = check_provenance_match(cached, current_provenance=current)
    assert len(diffs) == 1 and diffs[0][0] == "hafiscal_sha", \
        f"Expected single hafiscal_sha diff but got {diffs}"
    print(f"OK  check_provenance_match detects {diffs[0][0]} change")


def test_warn_provenance_mismatch_prints():
    """Verify _warn_provenance_mismatch emits a warning line when SHAs differ."""
    import io
    import json
    import tempfile
    from contextlib import redirect_stdout
    from cache import _warn_provenance_mismatch

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({
            "inputs": {
                "provenance": {
                    "hafiscal_sha": "OLD_FAKE_SHA_123",
                    "hark_sha": "OLD_FAKE_SHA_456",
                    "python": "3.0",
                }
            }
        }, f)
        meta_path = f.name

    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            _warn_provenance_mismatch(meta_path, label="test")
        out = buf.getvalue()
        assert "[test] provenance mismatch" in out, \
            f"Expected warning line, got: {out!r}"
        assert "OLD_FAKE_SHA_123" in out, \
            f"Expected old hafiscal SHA in warning, got: {out!r}"
        print(f"OK  warn line printed: {out.strip()}")
    finally:
        os.unlink(meta_path)


def test_warn_silent_on_no_meta():
    """Verify warn is silent (not an error) when meta_path doesn't exist."""
    import io
    from contextlib import redirect_stdout
    from cache import _warn_provenance_mismatch

    buf = io.StringIO()
    with redirect_stdout(buf):
        _warn_provenance_mismatch("/nonexistent/path.meta.json", label="test")
    out = buf.getvalue()
    assert out == "", f"Expected silent return, got: {out!r}"
    print("OK  silent return on missing meta_path")


if __name__ == "__main__":
    test_sha_excluded()
    test_numerical_param_still_invalidates()
    test_check_provenance_match()
    test_warn_provenance_mismatch_prints()
    test_warn_silent_on_no_meta()
    print("All SHA-exclusion tests passed.")
