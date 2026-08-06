"""Regression lock for BUG-052 — the welfare-6 experiment must start at the ERGODIC wealth.

The welfare experiment is evaluated on the agents' t=0 cross-section. The beta-calibration
targets the *ergodic* liquid-wealth distribution (the estimation burns in T_sim=T_age*2 and
settles to E[aNrm]~=0.31). For internal consistency the welfare experiment must hit that same
ergodic cross-section, NOT a cold a~=0 start (E[aNrm]~=0.174). BUG-052 was the silent
divergence between these two; this test is the lock that prevents it recurring.

Default = ergodic (warm-start ON). HAFISCAL_WELFARE6_TM_INIT=0 is the toggle-off paper trail
(cold-start) for isolating the bug's effect, NOT a QE-reproduction default.

Slow (each case builds + solves HS_Only and runs the base scenario). Run with:
    pytest Code/HA-Models/test_welfare6_ergodic_init.py -m slow
"""
import os
import pickle
import subprocess
import sys

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_FPC = os.path.join(_HERE, "FromPandemicCode")

# The ergodic E[aNrm] for HS_Only is ~0.31 (TM ergodic 0.301, warm-MC 0.306, estimation
# burn-in 0.309); the cold-start t=0 is ~0.174. Bands leave wide margin around N=2000 noise.
_ERGODIC_LO, _ERGODIC_HI = 0.27, 0.34
_COLD_HI = 0.22


def _run_base_t0_aNrm(out_dir, tm_init):
    """Run the base scenario once and return the t=0 cross-section mean aNrm."""
    env = dict(os.environ)
    env.pop("HAFISCAL_WELFARE6_TM_INIT", None)          # start from a clean default
    if tm_init is not None:
        env["HAFISCAL_WELFARE6_TM_INIT"] = tm_init
    env.update(HAFISCAL_USE_SOLUTION_CACHE="0", HAFISCAL_USE_JAX_2B="0", PYTHONUNBUFFERED="1")
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run(
        [sys.executable, "welfare6_scenario.py", "--scenario", "base",
         "--parametrization", "HS_Only", "--out-dir", out_dir,
         "--agent-count-total", "2000"],
        cwd=_FPC, env=env, check=True,
    )
    with open(os.path.join(out_dir, "base.pkl"), "rb") as f:
        return float(np.asarray(pickle.load(f)["aNrm_all_bs"])[0].mean())


@pytest.mark.slow
def test_welfare6_default_starts_at_ergodic(tmp_path):
    """DEFAULT (flag unset): the welfare experiment starts at the ergodic, not cold."""
    e = _run_base_t0_aNrm(str(tmp_path / "default"), tm_init=None)
    assert _ERGODIC_LO < e < _ERGODIC_HI, (
        f"BUG-052 regression: default welfare init not ergodic — t=0 E[aNrm]={e:.3f}, "
        f"expected ergodic ~0.31 in ({_ERGODIC_LO},{_ERGODIC_HI}). The warm-start default "
        f"may have been disabled, or the injection point broke."
    )


@pytest.mark.slow
def test_welfare6_cold_toggle_reproduces_bug(tmp_path):
    """The =0 toggle reproduces the cold-start (the BUG-052 paper trail) for isolation."""
    e = _run_base_t0_aNrm(str(tmp_path / "cold"), tm_init="0")
    assert e < _COLD_HI, (
        f"HAFISCAL_WELFARE6_TM_INIT=0 did not cold-start — t=0 E[aNrm]={e:.3f}, "
        f"expected cold ~0.174 (<{_COLD_HI}). The toggle-off path is broken."
    )
