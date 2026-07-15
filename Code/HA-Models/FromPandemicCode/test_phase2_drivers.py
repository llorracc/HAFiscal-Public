"""
Smoke + invariant tests for the Phase 2 CDC vs ESC comparison drivers.

Covers structural correctness (clean imports, correct shapes, expected
types) and cheap sanity invariants (sum-of-AgentCount, stationarity of
macro-0 baseline, CDC ≈ ESC at baseline).

Slow end-to-end runs are NOT covered here — those live in the drivers
themselves (phase2_*_cdc_vs_esc.py). Run with:
    pytest Code/HA-Models/FromPandemicCode/test_phase2_drivers.py -v
"""

import os
import sys
import importlib
import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))


# ---------------------------------------------------------------------------
# Module-level fixtures: each driver is imported once. Patch sys.argv first
# (the drivers read it during EstimParameters import per CLAUDE.md).
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def saved_argv():
    """Save and restore sys.argv around driver imports."""
    saved = sys.argv
    yield
    sys.argv = saved


@pytest.fixture(autouse=True)
def _restore_interpretation_env():
    """The CDC-vs-ESC drivers align HAFISCAL_INTERPRETATION with each leg
    (required by the BUG-051 matched-pair guard). Restore the env after each
    test so an 'ESC' leg doesn't leak into other suites in the same pytest
    process (whose explicit interpretation='CDC' calls would then be
    rejected by assert_interpretation)."""
    saved = os.environ.get('HAFISCAL_INTERPRETATION')
    yield
    if saved is None:
        os.environ.pop('HAFISCAL_INTERPRETATION', None)
    else:
        os.environ['HAFISCAL_INTERPRETATION'] = saved


@pytest.fixture(scope='module')
def check_drv(saved_argv):
    sys.argv = ['phase2_check_cdc_vs_esc']
    return importlib.import_module('phase2_check_cdc_vs_esc')


@pytest.fixture(scope='module')
def taxcut_drv(saved_argv):
    sys.argv = ['phase2_taxcut_cdc_vs_esc']
    return importlib.import_module('phase2_taxcut_cdc_vs_esc')


@pytest.fixture(scope='module')
def ui_drv(saved_argv):
    sys.argv = ['phase2_ui_cdc_vs_esc']
    return importlib.import_module('phase2_ui_cdc_vs_esc')


@pytest.fixture(scope='module')
def recession_drv(saved_argv):
    sys.argv = ['phase2_recession_cdc_vs_esc']
    return importlib.import_module('phase2_recession_cdc_vs_esc')


@pytest.fixture(scope='module')
def multibeta_drv(saved_argv):
    sys.argv = ['phase2_multibeta_cdc_vs_esc']
    return importlib.import_module('phase2_multibeta_cdc_vs_esc')


@pytest.fixture(scope='module')
def multicohort_drv(saved_argv):
    sys.argv = ['phase2_multicohort_cdc_vs_esc']
    return importlib.import_module('phase2_multicohort_cdc_vs_esc')


# ---------------------------------------------------------------------------
# Test 1: clean imports for all 6 drivers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('drv_name', [
    'phase2_check_cdc_vs_esc',
    'phase2_taxcut_cdc_vs_esc',
    'phase2_ui_cdc_vs_esc',
    'phase2_recession_cdc_vs_esc',
    'phase2_multibeta_cdc_vs_esc',
    'phase2_multicohort_cdc_vs_esc',
])
def test_phase2_driver_imports(drv_name, saved_argv):
    sys.argv = [drv_name]
    mod = importlib.import_module(drv_name)
    assert hasattr(mod, 'main'), f"{drv_name} missing main()"
    assert hasattr(mod, 'build_HS_economy') or \
           hasattr(mod, 'build_HS_multibeta_economy') or \
           hasattr(mod, 'build_population_economy'), \
        f"{drv_name} missing a build_* function"


# ---------------------------------------------------------------------------
# Test 2: Markov path generators (cheap)
# ---------------------------------------------------------------------------

def test_mrkv_path_no_recession_taxcut(taxcut_drv):
    p = taxcut_drv.mrkv_path_taxcut_no_recession(num_experiment_periods=10,
                                                  total_T=30)
    assert len(p) == 30
    assert p[:10] == [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
    assert p[10:] == [0] * 20


def test_mrkv_path_no_recession_ui(ui_drv):
    p = ui_drv.mrkv_path_no_recession(num_experiment_periods=10, total_T=30)
    assert len(p) == 30
    assert p[:10] == [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
    assert p[10:] == [0] * 20


def test_mrkv_path_recession_fixed(recession_drv):
    """First `duration` macro states get +1 (odd → recession active)."""
    p = recession_drv.mrkv_path_recession_fixed(num_experiment_periods=10,
                                                 total_T=30, duration=3)
    assert len(p) == 30
    assert p[:3] == [3, 5, 7], "first 3 entries should be odd (recession)"
    assert p[3:10] == [8, 10, 12, 14, 16, 18, 20]
    assert p[10:] == [0] * 20


def test_mrkv_path_recession_fixed_zero_duration(recession_drv):
    p = recession_drv.mrkv_path_recession_fixed(num_experiment_periods=10,
                                                 total_T=30, duration=0)
    assert p[:10] == [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]


def test_recession_prob_array(recession_drv):
    """Geometric duration distribution; must sum to 1."""
    arr = recession_drv.recession_prob_array(Rspell=6, max_recession_duration=11)
    assert len(arr) == 11
    np.testing.assert_allclose(arr.sum(), 1.0, atol=1e-12)
    assert arr[0] > arr[-1], "geometric: P(d=0) > P(d=10)"


# ---------------------------------------------------------------------------
# Test 3: AgentCount=1 invariance — economy build sets correct AgentCount
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_check_drv_AgentCount_1(check_drv):
    eco, _ = check_drv.build_HS_economy()
    assert len(eco.agents) == 1
    assert eco.agents[0].AgentCount == 1
    assert getattr(eco.agents[0], 'tm_a_indexed', False) is True


@pytest.mark.slow
def test_taxcut_drv_AgentCount_1(taxcut_drv):
    eco, _ = taxcut_drv.build_HS_economy()
    assert len(eco.agents) == 1
    assert eco.agents[0].AgentCount == 1


@pytest.mark.slow
def test_ui_drv_AgentCount_1(ui_drv):
    eco, _ = ui_drv.build_HS_economy()
    assert len(eco.agents) == 1
    assert eco.agents[0].AgentCount == 1


@pytest.mark.slow
def test_recession_drv_AgentCount_1(recession_drv):
    eco, _, _ = recession_drv.build_HS_economy()
    assert len(eco.agents) == 1
    assert eco.agents[0].AgentCount == 1


@pytest.mark.slow
def test_multibeta_population_mass_unity(multibeta_drv):
    eco, _, _ = multibeta_drv.build_HS_multibeta_economy()
    total_mass = sum(a.AgentCount for a in eco.agents)
    np.testing.assert_allclose(total_mass, 1.0, atol=1e-12)
    # All atoms in DiscFacDstns[1] for HS
    discfacs = sorted([a.DiscFac for a in eco.agents])
    assert len(discfacs) == len(eco.agents)
    assert all(0 < df < 1 for df in discfacs), "β atoms must be in (0, 1)"


@pytest.mark.slow
def test_multicohort_population_mass_unity(multicohort_drv):
    eco, _, _ = multicohort_drv.build_population_economy()
    total_mass = sum(a.AgentCount for a in eco.agents)
    np.testing.assert_allclose(total_mass, 1.0, atol=1e-12)
    # 21 types: 3 cohorts × 7 atoms (Baseline parametrization)
    assert len(eco.agents) == 21


# ---------------------------------------------------------------------------
# Test 4: macro-0 baseline stationarity (single agent only — cheap)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_check_drv_baseline_stationary(check_drv):
    """Macro-0 baseline AggCons should be ~constant over time (HS at
    steady state). Allow 1% drift for grid effects."""
    eco, num_experiment_periods = check_drv.build_HS_economy()
    base = check_drv.run_baseline(eco, 'CDC', num_experiment_periods)
    c = base['AggCons_pc']
    rel_drift = float(np.max(np.abs(c - c[0])) / max(abs(c[0]), 1e-12))
    assert rel_drift < 0.01, f"baseline drift {rel_drift:.4%} > 1%"


@pytest.mark.slow
def test_check_drv_cdc_esc_baseline_close(check_drv):
    """CDC and ESC baseline AggCons should agree to <1% per cheat-sheet
    (~0.05% expected at single HS / mid-β)."""
    eco, num_experiment_periods = check_drv.build_HS_economy()
    base_cdc = check_drv.run_baseline(eco, 'CDC', num_experiment_periods)
    base_esc = check_drv.run_baseline(eco, 'ESC', num_experiment_periods)
    ratio = base_esc['AggCons_pc'][0] / base_cdc['AggCons_pc'][0]
    assert abs(ratio - 1.0) < 0.01, \
        f"CDC vs ESC baseline ratio {ratio:.6f} differs by >1%"
