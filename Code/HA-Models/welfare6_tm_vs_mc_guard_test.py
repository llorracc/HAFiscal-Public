"""Unit test for the Phase C.1 matched-pair guard + bias/SE comparison columns
(welfare6_hybrid_table.{capture_welfare6_regime, assert_welfare6_regimes_match,
write_tm_vs_mc_comparison}). Synthetic cells, NO model run — validates the guard
fires on a regime mismatch and the bias / %bias / SE columns + ui_norec exclusion
+ UI flag are correct.

Run:  .venv/bin/python Code/HA-Models/welfare6_tm_vs_mc_guard_test.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "FromPandemicCode"))
from welfare6_hybrid_table import (capture_welfare6_regime,
                                   assert_welfare6_regimes_match,
                                   write_tm_vs_mc_comparison)

_FLAGS = ("HAFISCAL_PERMGROFAC_FIX", "HAFISCAL_UI_STATE_ENCODING",
          "HAFISCAL_INTERPRETATION")


def test_capture_regime_defaults():
    saved = {k: os.environ.pop(k, None) for k in _FLAGS}
    try:
        r = capture_welfare6_regime()
        assert r == {"permgrofac_fix": True, "ui_state_encoding": "bug_fix",
                     "interpretation": "CDC"}, r
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_capture_regime_reads_env():
    saved = {k: os.environ.get(k) for k in _FLAGS}
    try:
        os.environ["HAFISCAL_PERMGROFAC_FIX"] = "0"
        os.environ["HAFISCAL_INTERPRETATION"] = "esc"
        r = capture_welfare6_regime()
        assert r["permgrofac_fix"] is False and r["interpretation"] == "ESC", r
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_guard_matching_passes():
    r = {"permgrofac_fix": True, "ui_state_encoding": "bug_fix", "interpretation": "CDC"}
    assert_welfare6_regimes_match(r, dict(r))  # must not raise


def test_guard_none_is_soft():
    assert_welfare6_regimes_match(None, {"permgrofac_fix": True})
    assert_welfare6_regimes_match({"permgrofac_fix": True}, None)
    assert_welfare6_regimes_match(None, None)


def test_guard_mismatch_raises():
    a = {"permgrofac_fix": True, "ui_state_encoding": "bug_fix", "interpretation": "CDC"}
    b = {"permgrofac_fix": True, "ui_state_encoding": "bug_fix", "interpretation": "ESC"}
    try:
        assert_welfare6_regimes_match(a, b)
    except RuntimeError as e:
        assert "interpretation" in str(e) and "matched-pair" in str(e), str(e)
        return
    raise AssertionError("guard should have raised on interpretation mismatch")


def test_bias_se_columns_and_exclusions():
    tm = {"check_norec": 1.00, "check_rec": 1.30, "check_rec_AD": 1.40,
          "ui_norec": 0.85, "ui_rec": 1.50, "ui_rec_AD": 1.60,
          "taxcut_norec": 1.00, "taxcut_rec": 1.10, "taxcut_rec_AD": 1.20}
    mc = {"check_norec": 1.01, "check_rec": 1.3195, "check_rec_AD": 1.41,
          "ui_norec": -33.0, "ui_rec": 1.40, "ui_rec_AD": 1.50,
          "taxcut_norec": 1.00, "taxcut_rec": 1.122, "taxcut_rec_AD": 1.21}
    se = {"check_rec": 0.002}
    reg = {"permgrofac_fix": True, "ui_state_encoding": "bug_fix", "interpretation": "CDC"}
    out = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False).name
    try:
        rows = write_tm_vs_mc_comparison(tm, mc, out, tm_regime=reg,
                                         mc_regime=dict(reg), mc_se=se)
        by = {r["cell"]: r for r in rows}
        assert "ui_norec" not in by, "ui_norec must be EXCLUDED (0/0)"
        assert len(rows) == 8, f"expected 8 rows, got {len(rows)}"
        cr = by["check_rec"]
        assert abs(cr["bias"] - (1.3195 - 1.30)) < 1e-9, cr
        assert abs(cr["pct"] - 100.0 * (1.3195 - 1.30) / 1.30) < 1e-6, cr
        assert abs(cr["SE"] - 0.002) < 1e-12, cr
        assert by["taxcut_rec"]["SE"] is None, "no SE provided -> None"
        assert by["ui_rec"]["flag"] == "UI*" and by["ui_rec_AD"]["flag"] == "UI*"
        assert by["check_rec"]["flag"] == "" and by["taxcut_rec"]["flag"] == ""
        # the written report mentions the regime + the exclusion
        txt = open(out).read()
        assert "EXCLUDED" in txt and "interpretation" in txt
    finally:
        os.unlink(out)


def test_comparison_guard_blocks_mismatched_run():
    tm = {k: 1.0 for k in ("check_rec", "taxcut_rec")}
    mc = dict(tm)
    a = {"permgrofac_fix": True, "ui_state_encoding": "bug_fix", "interpretation": "CDC"}
    b = {"permgrofac_fix": False, "ui_state_encoding": "bug_fix", "interpretation": "CDC"}
    out = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False).name
    try:
        write_tm_vs_mc_comparison(tm, mc, out, tm_regime=a, mc_regime=b)
    except RuntimeError as e:
        assert "permgrofac_fix" in str(e), str(e)
        return
    finally:
        if os.path.exists(out):
            os.unlink(out)
    raise AssertionError("comparison should have refused mismatched regimes")


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
            passed += 1
        except Exception:
            print(f"  FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
