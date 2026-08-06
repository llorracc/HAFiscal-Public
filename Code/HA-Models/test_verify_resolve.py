"""Tests for the --complete re-solve-and-compare reuse gate — thread-2 component 3.

Layers (cascade-gated: the fast tiers run unconditionally; the real-compute integration is
opt-in via HAFISCAL_RUN_RESOLVE_ITEST=1):
  1. scope / tolerance — the VERIFY-axis policy pieces;
  2. compare_pickles / run_compare — the numeric comparison (identical, within-tol = the
     cache's ~3e-7 loss, beyond-tol, shape & NaN-pattern mismatch, missing pkl);
  3. report — PASS vs FAIL headline + diagnostics;
  4. the run_welfare6_parallel hook gate with launch_scenarios MOCKED (numeric => skip;
     complete => re-run cache-OFF at the SAME seed + compare; a mismatch => fail (False);
     scope=none => skip; a machinery error => degrade (True));
  5. a static tripwire that the hook is wired into main() with a 0/1 return;
  6. an OPT-IN tiny-scale integration (real base-cell cache-off re-run + compare).

Build: plans/20260622_thread2-flag-taxonomy-build-execution-plan.md (component 3).
"""
from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pytest

HA_MODELS = Path(__file__).resolve().parent
FROM_PANDEMIC = HA_MODELS / "FromPandemicCode"

sys.path.insert(0, str(HA_MODELS))
import verify_resolve as vr  # noqa: E402


# --------------------------------------------------------------------------- #
# 1. scope + tolerance
# --------------------------------------------------------------------------- #
def test_scope_keywords(monkeypatch):
    monkeypatch.delenv("HAFISCAL_VERIFY_RESOLVE_SCOPE", raising=False)
    assert len(vr.scope()) == 12                       # default 'all'
    monkeypatch.setenv("HAFISCAL_VERIFY_RESOLVE_SCOPE", "none")
    assert vr.scope() == ()
    monkeypatch.setenv("HAFISCAL_VERIFY_RESOLVE_SCOPE", "canary")
    assert vr.scope() == ("base",)
    monkeypatch.setenv("HAFISCAL_VERIFY_RESOLVE_SCOPE", "sample")
    assert vr.scope() == ("base", "recessionCheck_AD")
    monkeypatch.setenv("HAFISCAL_VERIFY_RESOLVE_SCOPE", "bogus-xyz")
    assert len(vr.scope()) == 12                       # unrecognized -> all


def test_scope_explicit_list(monkeypatch):
    monkeypatch.setenv("HAFISCAL_VERIFY_RESOLVE_SCOPE", "base,recession_AD,not-a-scenario")
    assert vr.scope() == ("base", "recession_AD")      # unknown dropped


def test_tolerance(monkeypatch):
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "complete")
    rtol, label = vr.tolerance()
    assert rtol == 1e-6 and "Tier-I" in label
    # component 5: byte forces reuse off -> a fresh re-solve is bit-identical -> exact compare
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "byte")
    rtol, label = vr.tolerance()
    assert rtol == 0.0 and "byte-exact" in label


# --------------------------------------------------------------------------- #
# 2. compare_pickles / run_compare
# --------------------------------------------------------------------------- #
def _mk(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(data, f)
    return path


def _base_payload():
    return {
        "cLvl_all_splurge": np.linspace(1.0, 5.0, 200),
        "pLvl_all_bs": np.ones((4, 200)) * 1.3,
        "ui_norec": np.array([np.nan]),       # the 0/0 cell -> NaN, legitimately
        "tag": "base", "meta": None,          # non-numeric: skipped
    }


def test_compare_identical(tmp_path):
    p = _base_payload()
    a = _mk(str(tmp_path / "a" / "base.pkl"), p)
    b = _mk(str(tmp_path / "b" / "base.pkl"), {**p, "cLvl_all_splurge": p["cLvl_all_splurge"].copy()})
    r = vr.compare_pickles(a, b)
    assert r["worst_reldiff"] == 0.0 and r["n_compared"] == 3


def test_compare_excludes_runtime_metadata(tmp_path):
    # runtime_s = wall-clock duration, legitimately differs run-to-run; must NOT count as a
    # mismatch (regression guard for the integration finding 2026-06-22).
    p = _base_payload()
    a = _mk(str(tmp_path / "a" / "base.pkl"), {**p, "runtime_s": 8.0})
    b = _mk(str(tmp_path / "b" / "base.pkl"), {**p, "runtime_s": 4.0})
    assert vr.compare_pickles(a, b)["worst_reldiff"] == 0.0


def test_compare_within_cache_loss(tmp_path):
    p = _base_payload()
    a = _mk(str(tmp_path / "a" / "base.pkl"), p)
    b = _mk(str(tmp_path / "b" / "base.pkl"),
            {**p, "cLvl_all_splurge": p["cLvl_all_splurge"] * (1 + 3e-7)})
    r = vr.compare_pickles(a, b)
    assert 0 < r["worst_reldiff"] < 1e-6        # the ~3e-7 cache loss passes Tier-I


def test_compare_beyond_tol(tmp_path):
    p = _base_payload()
    big = p["cLvl_all_splurge"].copy(); big[0] *= 1.001
    a = _mk(str(tmp_path / "a" / "base.pkl"), p)
    b = _mk(str(tmp_path / "b" / "base.pkl"), {**p, "cLvl_all_splurge": big})
    r = vr.compare_pickles(a, b)
    assert r["worst_reldiff"] > 1e-6 and r["worst_key"] == "cLvl_all_splurge"


def test_compare_shape_and_nan_mismatch(tmp_path):
    p = _base_payload()
    a = _mk(str(tmp_path / "a" / "base.pkl"), p)
    shp = _mk(str(tmp_path / "s" / "base.pkl"), {**p, "pLvl_all_bs": np.ones((4, 199))})
    nan = _mk(str(tmp_path / "n" / "base.pkl"), {**p, "ui_norec": np.array([0.85])})
    assert vr.compare_pickles(a, shp)["worst_reldiff"] == float("inf")
    assert vr.compare_pickles(a, nan)["worst_reldiff"] == float("inf")


def test_run_compare(tmp_path):
    p = _base_payload()
    _mk(str(tmp_path / "prod" / "base.pkl"), p)
    _mk(str(tmp_path / "fresh_ok" / "base.pkl"), {**p})
    big = p["cLvl_all_splurge"].copy(); big[0] *= 1.01
    _mk(str(tmp_path / "fresh_bad" / "base.pkl"), {**p, "cLvl_all_splurge": big})

    ok, mis, miss, det = vr.run_compare(str(tmp_path / "prod"),
                                        str(tmp_path / "fresh_ok"), ("base",), 1e-6)
    assert ok and not mis and not miss

    ok, mis, miss, det = vr.run_compare(str(tmp_path / "prod"),
                                        str(tmp_path / "fresh_bad"), ("base",), 1e-6)
    assert not ok and mis[0][0] == "base"

    # missing pkl -> recorded as machinery 'missing', NOT a mismatch
    ok, mis, miss, det = vr.run_compare(str(tmp_path / "prod"),
                                        str(tmp_path / "fresh_ok"),
                                        ("base", "recessionCheck_AD"), 1e-6)
    assert ok and miss == ["recessionCheck_AD"]


def test_report_pass_and_fail(capsys):
    vr.report(True, [], [], {"base": {"worst_reldiff": 3e-7}}, 1e-6, "Tier-I (1e-6)")
    out = capsys.readouterr()
    assert "PASS" in out.out
    vr.report(False, [("recessionCheck_AD", "cLvl_all_splurge", 1e-3)], [], {},
              1e-6, "Tier-I (1e-6)")
    err = capsys.readouterr().err
    assert "FAIL" in err and "SUSPECT" in err and "BUG-047" in err


# --------------------------------------------------------------------------- #
# 4. the run_welfare6_parallel hook gate (launch_scenarios mocked — no compute)
# --------------------------------------------------------------------------- #
@pytest.fixture
def rw_module():
    sys.path.insert(0, str(FROM_PANDEMIC))
    try:
        import run_welfare6_parallel as rw
    except Exception as e:  # pragma: no cover
        pytest.skip(f"run_welfare6_parallel import failed: {e}")
    return rw


def _fake_args(**over):
    import argparse
    base = dict(seed_offset=0, max_parallel=12, ad_tolerance=None, solve_workers=None,
                duration_workers=None, agent_count_total=None, max_gpu_slots=1,
                max_cpu_slots=2, ad_cache=None)
    base.update(over)
    return argparse.Namespace(**base)


def test_hook_noop_at_numeric(rw_module, monkeypatch):
    monkeypatch.delenv("HAFISCAL_VERIFY_LEVEL", raising=False)
    launches = []
    monkeypatch.setattr(rw_module, "launch_scenarios", lambda *a, **k: launches.append(k) or {})
    assert rw_module._maybe_verify_resolve("Baseline", "/tmp/o", "/tmp/l", _fake_args()) is True
    assert launches == []


def test_hook_resolves_cache_off_same_seed(rw_module, monkeypatch):
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "complete")
    monkeypatch.delenv("HAFISCAL_VERIFY_RESOLVE_SCOPE", raising=False)
    launches = []
    monkeypatch.setattr(rw_module, "launch_scenarios",
                        lambda *a, **k: launches.append((a, k)) or {s: (0, 1.0) for s in a[1]})
    monkeypatch.setattr(vr, "run_compare",
                        lambda pd, fd, sc, tol: (True, [], [], {s: {"worst_reldiff": 3e-7} for s in sc}))
    monkeypatch.setattr(vr, "report", lambda *a, **k: None)
    ok = rw_module._maybe_verify_resolve("Baseline", "/tmp/o", "/tmp/l", _fake_args(seed_offset=7))
    assert ok is True
    assert len(launches) == 1
    a, k = launches[0]
    assert len(a[1]) == 12                 # scope=all
    assert k["ad_cache"] is False          # cache OFF -> fresh solve
    assert k["seed_offset"] == 7           # SAME seed as production (isolates the reuse)


def test_hook_mismatch_fails(rw_module, monkeypatch):
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "complete")
    monkeypatch.setattr(rw_module, "launch_scenarios", lambda *a, **k: {s: (0, 1.0) for s in a[1]})
    monkeypatch.setattr(vr, "run_compare",
                        lambda pd, fd, sc, tol: (False, [("recessionCheck_AD", "cLvl", 1e-3)], [], {}))
    monkeypatch.setattr(vr, "report", lambda *a, **k: None)
    assert rw_module._maybe_verify_resolve("Baseline", "/tmp/o", "/tmp/l", _fake_args()) is False


def test_hook_scope_none_skips(rw_module, monkeypatch):
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "complete")
    monkeypatch.setenv("HAFISCAL_VERIFY_RESOLVE_SCOPE", "none")
    launches = []
    monkeypatch.setattr(rw_module, "launch_scenarios", lambda *a, **k: launches.append(k) or {})
    assert rw_module._maybe_verify_resolve("Baseline", "/tmp/o", "/tmp/l", _fake_args()) is True
    assert launches == []


def test_hook_machinery_error_degrades(rw_module, monkeypatch):
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "complete")
    monkeypatch.delenv("HAFISCAL_VERIFY_RESOLVE_SCOPE", raising=False)

    def boom(*a, **k):
        raise RuntimeError("re-run crashed")
    monkeypatch.setattr(rw_module, "launch_scenarios", boom)
    # a re-run crash must DEGRADE (True), not fail the production result
    assert rw_module._maybe_verify_resolve("Baseline", "/tmp/o", "/tmp/l", _fake_args()) is True


# --------------------------------------------------------------------------- #
# 5. static tripwire: hook wired into main() with a 0/1 return
# --------------------------------------------------------------------------- #
def test_hook_wired_into_main():
    src = (FROM_PANDEMIC / "run_welfare6_parallel.py").read_text()
    assert "def _maybe_verify_resolve(" in src
    assert "_resolve_ok = _maybe_verify_resolve(" in src
    assert "return 0 if _resolve_ok else 1" in src


# --------------------------------------------------------------------------- #
# 6. OPT-IN tiny-scale integration (real base-cell cache-off re-run + compare)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(os.environ.get("HAFISCAL_RUN_RESOLVE_ITEST") != "1",
                    reason="set HAFISCAL_RUN_RESOLVE_ITEST=1 to run the real tiny-scale "
                           "re-solve-and-compare (launches welfare6_scenario base cells)")
def test_integration_tiny_scale(tmp_path, monkeypatch):
    sys.path.insert(0, str(FROM_PANDEMIC))
    import run_welfare6_parallel as rw
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "complete")
    monkeypatch.setenv("HAFISCAL_VERIFY_RESOLVE_SCOPE", "canary")
    out_dir = str(tmp_path / "prod")
    log_dir = str(tmp_path / "log")
    # production base.pkl (cache off, seed 0)
    rw.launch_scenarios("Reduced_Run", ("base",), 1, out_dir, log_dir,
                        agent_count_total=400, seed_offset=0, ad_cache=False)
    ok = rw._maybe_verify_resolve("Reduced_Run", out_dir, log_dir,
                                  _fake_args(max_parallel=1, agent_count_total=400))
    # two fresh same-seed solves must match within Tier-I -> PASS
    assert ok is True
    assert os.path.exists(os.path.join(out_dir + "_verify_resolve", "base.pkl"))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
