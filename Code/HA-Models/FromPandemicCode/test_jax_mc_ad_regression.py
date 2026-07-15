"""
Regression test: HAFISCAL_USE_JAX_MC=1 vs default HARK on recession AD.

Pins JAX-vs-HARK Cratio_hist agreement within MC noise + Mrkv timing
artifact at HS_Only. Skipped in CI by default; opt-in with --run-slow.
"""
import os, pickle, subprocess
import pytest
import numpy as np


pytestmark = pytest.mark.skipif(
    os.environ.get('HAFISCAL_RUN_SLOW_TESTS', '') != '1',
    reason="Slow JAX AD regression — set HAFISCAL_RUN_SLOW_TESTS=1 to enable")


def test_jax_ad_matches_hark_hs_only(tmp_path):
    """JAX AD outer loop must converge to within 2% of HARK at HS_Only."""
    # Generate HARK reference
    ref_pkl = tmp_path / "hs_ad_ref.pkl"
    env = os.environ.copy()
    env.update({
        'HAFISCAL_UI_STATE_ENCODING': 'bug_fix',
        'HAFISCAL_AGENTCOUNT_H': '1800',
        'HAFISCAL_AGGREGATE_BY_EDU_SHARE': 'auto',
        'HAFISCAL_AD_MAX_ITER': '5',
        'OMP_NUM_THREADS': '2',
        'PYTHONUNBUFFERED': '1',
    })
    env.pop('LD_LIBRARY_PATH', None)
    repo_code = os.path.dirname(os.path.abspath(__file__))
    cmd = ['python', '-u', 'jax_mc_ad_make_hark_ref.py']
    r = subprocess.run(cmd, cwd=repo_code, env=env, capture_output=True, text=True)
    assert r.returncode == 0, f"HARK ref failed:\n{r.stderr[-2000:]}"
    ref = pickle.load(open(os.path.join(repo_code, 'welfare6_HS_ad_ref/recession_AD.pkl'), 'rb'))

    # Run JAX validation
    cmd = ['python', '-u', 'jax_mc_ad_solve_validate.py']
    r = subprocess.run(cmd, cwd=repo_code, env=env, capture_output=True, text=True)
    assert r.returncode == 0, f"JAX validate failed:\n{r.stderr[-2000:]}"

    # Parse mean ratio from stdout
    out = r.stdout
    for line in out.splitlines():
        if 'Mean ratio JAX/HARK' in line:
            ratio = float(line.split(':')[-1].strip())
            break
    else:
        pytest.fail("could not parse mean ratio from JAX validate output")

    # Must be within 2% (covers MC noise + Mrkv timing artifact)
    assert abs(ratio - 1.0) < 0.02, (
        f"JAX/HARK Cratio mean ratio {ratio:.4f} exceeds 2% tolerance")
