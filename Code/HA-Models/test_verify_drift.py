"""Tests for the --complete multi-seed drift+SE companion — thread-2 component 2.

Layers:
  1. verify_drift gate + seed-count (the VERIFY-axis pieces);
  2. report_multiseed over SYNTHETIC base.pkl dirs (known drift detected; <2-dir guard;
     best-effort on a corrupt pkl) — fast, no welfare compute;
  3. the run_welfare6_parallel hook gate logic with launch_scenarios MOCKED (numeric =>
     no-op; complete => N-1 base-cell launches at distinct seeds + one report) — fast;
  4. a static tripwire that the hook is wired into main();
  5. an OPT-IN tiny-scale integration (real base-cell subprocesses) — skipped unless
     HAFISCAL_RUN_DRIFT_ITEST=1 (cascade-gated: cheapest tiers run by default).

Build: plans/20260622_thread2-flag-taxonomy-build-execution-plan.md (component 2).
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
import verify_drift as vd  # noqa: E402


# --------------------------------------------------------------------------- #
# 1. gate + seed count
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("level,expect", [
    (None, False), ("numeric", False), ("complete", True), ("byte", True),
])
def test_should_run(monkeypatch, level, expect):
    if level is None:
        monkeypatch.delenv("HAFISCAL_VERIFY_LEVEL", raising=False)
    else:
        monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", level)
    assert vd.should_run() is expect


@pytest.mark.parametrize("val,expect", [
    (None, 4), ("4", 4), ("6", 6), ("2", 2),
    ("1", 2),    # floored
    ("0", 2),    # floored
    ("x", 4),    # non-int -> default
])
def test_n_seeds(monkeypatch, val, expect):
    if val is None:
        monkeypatch.delenv("HAFISCAL_VERIFY_DRIFT_SEEDS", raising=False)
    else:
        monkeypatch.setenv("HAFISCAL_VERIFY_DRIFT_SEEDS", val)
    assert vd.n_seeds() == expect


# --------------------------------------------------------------------------- #
# 2. report_multiseed over synthetic base.pkl dirs
# --------------------------------------------------------------------------- #
def _write_base_cell(d, *, widen_income, seed):
    """Write <d>/base.pkl with (T,N) aNrm_all_bs / pLvl_all_bs panels. If widen_income,
    var(log pLvl) grows from t=0 to t=end (a real ergodic-departure signal)."""
    os.makedirs(d, exist_ok=True)
    rng = np.random.default_rng(seed)
    T, N = 4, 300
    a = np.abs(rng.normal(2.0, 0.5, size=(T, N)))
    p = np.empty((T, N))
    sd0, sdE = (0.20, 0.30) if widen_income else (0.25, 0.25)
    p[0] = np.exp(rng.normal(0, sd0, N))
    p[-1] = np.exp(rng.normal(0, sdE, N))
    p[1:-1] = np.exp(rng.normal(0, 0.25, (T - 2, N)))
    with open(os.path.join(d, "base.pkl"), "wb") as f:
        pickle.dump({"aNrm_all_bs": a, "pLvl_all_bs": p}, f)
    return d


def test_report_multiseed_detects_real_income_drift(tmp_path, capsys):
    dirs = [_write_base_cell(str(tmp_path / f"seed_{s}"), widen_income=True, seed=s)
            for s in range(4)]
    rc = vd.report_multiseed(dirs, label="synthetic-real")
    out = capsys.readouterr().out
    assert rc == 0
    assert "MULTI-SEED MC DRIFT" in out and "base" in out
    # the var(log p) widening is a real, seed-stable drift -> REAL verdict
    vline = next(l for l in out.splitlines() if "d_var_log_p" in l)
    assert "REAL" in vline, vline


def test_report_multiseed_flat_is_noise(tmp_path, capsys):
    dirs = [_write_base_cell(str(tmp_path / f"seed_{s}"), widen_income=False, seed=s)
            for s in range(4)]
    assert vd.report_multiseed(dirs) == 0
    out = capsys.readouterr().out
    vline = next(l for l in out.splitlines() if "d_var_log_p" in l)
    assert "noise" in vline or "borderline" in vline, vline


def test_report_multiseed_needs_two_dirs(tmp_path):
    d = _write_base_cell(str(tmp_path / "only"), widen_income=True, seed=0)
    assert vd.report_multiseed([d]) == 1   # <2 -> 1, no raise


def test_report_multiseed_best_effort_on_corrupt(tmp_path):
    good = _write_base_cell(str(tmp_path / "good"), widen_income=True, seed=0)
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "base.pkl").write_bytes(b"not a pickle")
    # must DEGRADE (return 1) not raise — best-effort
    assert vd.report_multiseed([good, str(bad)]) == 1


# --------------------------------------------------------------------------- #
# 3. the run_welfare6_parallel hook gate (launch_scenarios mocked — no compute)
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
    monkeypatch.setattr(rw_module, "launch_scenarios",
                        lambda *a, **k: launches.append(k) or {})
    monkeypatch.setattr(vd, "report_multiseed",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    rw_module._maybe_emit_verify_drift("Baseline", "/tmp/out", "/tmp/log", _fake_args())
    assert launches == []   # numeric default => zero extra compute


def test_hook_launches_and_reports_at_complete(rw_module, monkeypatch):
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "complete")
    monkeypatch.setenv("HAFISCAL_VERIFY_DRIFT_SEEDS", "4")
    launches, reports = [], []
    monkeypatch.setattr(rw_module, "launch_scenarios",
                        lambda *a, **k: launches.append((a, k)) or {"base": (0, 1.0)})
    monkeypatch.setattr(vd, "report_multiseed",
                        lambda dirs, label=None: reports.append((list(dirs), label)) or 0)
    rw_module._maybe_emit_verify_drift("Baseline", "/tmp/out", "/tmp/log", _fake_args())
    assert len(launches) == 3                       # N-1 extra base cells
    assert all(a[1] == ("base",) for a, k in launches)
    assert sorted(k["seed_offset"] for a, k in launches) == [1, 2, 3]
    assert len(reports) == 1
    dirs, _label = reports[0]
    assert dirs[0] == "/tmp/out" and len(dirs) == 4   # main run reused as seed 0


def test_hook_respects_base_seed_offset(rw_module, monkeypatch):
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "byte")
    monkeypatch.setenv("HAFISCAL_VERIFY_DRIFT_SEEDS", "3")
    launches = []
    monkeypatch.setattr(rw_module, "launch_scenarios",
                        lambda *a, **k: launches.append(k) or {})
    monkeypatch.setattr(vd, "report_multiseed", lambda *a, **k: 0)
    rw_module._maybe_emit_verify_drift("Baseline", "/tmp/out", "/tmp/log",
                                       _fake_args(seed_offset=10))
    # base seed 10 reused; companions 11,12
    assert sorted(k["seed_offset"] for k in launches) == [11, 12]


# --------------------------------------------------------------------------- #
# 4. static tripwire: the hook is wired into main()
# --------------------------------------------------------------------------- #
def test_hook_wired_into_main():
    src = (FROM_PANDEMIC / "run_welfare6_parallel.py").read_text()
    assert "_maybe_emit_verify_drift(" in src
    # called within main (before the final return), defined as a function
    assert "def _maybe_emit_verify_drift(" in src
    assert src.count("_maybe_emit_verify_drift(") >= 2   # def + call


# --------------------------------------------------------------------------- #
# 5. OPT-IN tiny-scale integration (real base-cell subprocesses)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(os.environ.get("HAFISCAL_RUN_DRIFT_ITEST") != "1",
                    reason="set HAFISCAL_RUN_DRIFT_ITEST=1 to run the real tiny-scale "
                           "drift companion (launches welfare6_scenario base cells)")
def test_integration_tiny_scale(tmp_path, monkeypatch):
    sys.path.insert(0, str(FROM_PANDEMIC))
    import run_welfare6_parallel as rw
    monkeypatch.setenv("HAFISCAL_VERIFY_LEVEL", "complete")
    monkeypatch.setenv("HAFISCAL_VERIFY_DRIFT_SEEDS", "2")
    out_dir = str(tmp_path / "main")
    log_dir = str(tmp_path / "log")
    # produce the main run's base.pkl (seed 0) at tiny scale
    rw.launch_scenarios("Reduced_Run", ("base",), 1, out_dir, log_dir,
                        agent_count_total=400, seed_offset=0)
    rw._maybe_emit_verify_drift("Reduced_Run", out_dir, log_dir, _fake_args(
        max_parallel=1, agent_count_total=400))
    # the companion produced a seed_1 base.pkl
    assert os.path.exists(os.path.join(out_dir + "_verify_drift", "seed_1", "base.pkl"))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
