"""
CDC baseline pinned-regression test.

Pins specific known-good values for the CDC interpretation so that any
behavior-changing edit on `_TM-vs-MC` (or any future configurable refactor
on `feature/cdc-esc-configurable`) is caught in seconds rather than only
in a 1-2 hour `--comp full --tm-only` re-run.

Two layers:

1. **Calibration-file content pins** (fast, robust). SHA256 hashes of the
   CDC-fitted calibration `.txt` files. Catches the most common regression
   risk: an estimation re-run that accidentally overwrites the published
   CDC values.

2. **Simulation-behavior pin** (slower, scaffolded but currently skipped).
   A small CDC simulation that asserts specific (β, m, a, c) values at
   specific (period, agent_index) pins. Currently skipped pending pin
   values from a known-good run; instructions to populate are in the
   docstring of `test_cdc_simulation_pin`.

Run with: `pytest Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py -v`

Created per plans/20260426-0706h_pre-refactor-prep.md item 4/4 as
prep for the planned `feature/cdc-esc-configurable` refactor.
"""

import hashlib
import os
from pathlib import Path

import pytest


# Locate the repository root by walking up from this file
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # Code/HA-Models/FromPandemicCode → repo root
assert (REPO_ROOT / 'Code' / 'HA-Models').is_dir(), \
    f"Couldn't locate repo root from {__file__}; got {REPO_ROOT}"


# ============================================================
# Layer 1: calibration file content pins
# ============================================================

# Pinned SHA256 hashes of the CDC-fitted calibration .txt files at the
# BUG-047 paper-grade re-estimated calibration (commit 2785c1f1, 2026-06-05;
# adds a fitted GICx field per education group). Previous anchor era was
# `reproduce-20260425-comp-full-tm-only`.
#
# To regenerate after an intentional re-fit, run:
#   python3 -c "import hashlib; from pathlib import Path; \
#     [print(f'{p.name}: {hashlib.sha256(p.read_bytes()).hexdigest()}') \
#      for p in [Path(f) for f in (...)]]"
# and replace the values below.
CDC_CALIBRATION_PINS = {
    'Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt':
        'beff9cd639d5e3edb19b6e3a0349b617a80335854aaeb91274ed4c970edde4f2',
    'Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt':
        'ac26dc37b703f692e441d897a372cdf6bcec6d43004d28e4cc9316fe3d9d8692',
    'Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_edType0.txt':
        '2149ffdb487a03b0c0170a73fe038809bee33956dd6fd9752543783bca4c5a95',
    'Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_edType1.txt':
        '7cd18ff947eac57c5953d1dbb1d144d301b3a84c8df3b3f59f007bde17ef79be',
    'Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_edType2.txt':
        '8fe0276f3e7c601649d935262503b91dc93714a5a35558b2b846574781e480d4',
}


@pytest.mark.parametrize('rel_path,expected_sha256', list(CDC_CALIBRATION_PINS.items()))
def test_cdc_calibration_file_unchanged(rel_path, expected_sha256):
    """Each CDC-fitted calibration .txt file matches its pinned SHA256.

    This catches accidental overwrites by:
      - An intentional or accidental re-run of Step 1 (lottery splurge fit)
        or Step 2 (β/∇ fit) producing slightly different numbers.
      - An RNG-seed change.
      - A formula edit in `_lottery_consumption_under_cdc` or `_wealth_under_cdc`
        that subtly shifts the fitted parameters.

    If this test fails, either:
      (a) the change was intentional → update the pinned hash here.
      (b) the change was accidental → revert.
    """
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"Expected file does not exist: {path}"
    actual_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual_sha256 == expected_sha256, (
        f"\nCDC calibration file content changed:\n"
        f"  file:     {rel_path}\n"
        f"  expected: {expected_sha256}\n"
        f"  actual:   {actual_sha256}\n"
        f"\nIf this change is intentional (e.g., you re-ran estimation with\n"
        f"updated formulas), update the pinned hash in CDC_CALIBRATION_PINS.\n"
        f"If unexpected, the file may have been overwritten accidentally —\n"
        f"check git log for the file and consider reverting."
    )


# ============================================================
# Layer 2: simulation-behavior pin (currently scaffolded, skipped)
# ============================================================

# To populate the pin values:
#   1. Remove the @pytest.mark.skip decorator below.
#   2. Run `pytest -s -v Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py::test_cdc_simulation_pin`.
#   3. The test will print the actual values it sees (currently asserts None).
#   4. Hard-code those values in CDC_SIMULATION_PINS below; re-run to confirm passing.
#   5. Commit the populated pin values; the test then catches any future drift.

CDC_SIMULATION_PINS = {
    # (period, agent_idx) -> {'aNrm': value, 'cNrm': value, 'cLvl_splurge': value, ...}
    # TO BE POPULATED. See instructions above.
}


@pytest.mark.skip(reason="pending BUG-034+035 re-anchor; new pin values captured in Step 4")
def test_cdc_simulation_pin():
    """Run a small CDC simulation and assert specific numerical pins.

    Setup: single agent type (college, mid-DiscFac), AgentCount=100,
    short horizon, seeded RNG, no AD/recession (baseline only).

    Pinned at: a few specific (period, agent_idx) -> {state_var: value}
    cells.

    This catches any behavior change in the CDC asset rule, the
    cLvl_splurge formula, or the wealth correction. Runs in <30 seconds
    (vs 1-2 hours for `--comp full --tm-only`).

    Limitations:
      - Only exercises the AggFiscalType simulation path (not the TM kernel
        in tm_methods.py; for that, see test_tm_a_indexed.py).
      - Only exercises baseline (no recession / AD / Check / UI / TaxCut).
        Those need separate pin tests if you want to catch regressions in
        the experiment-period code.
    """
    import sys
    if str(REPO_ROOT / 'Code' / 'HA-Models' / 'FromPandemicCode') not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / 'Code' / 'HA-Models' / 'FromPandemicCode'))

    # Suppress matplotlib backend issues + restore sys.argv expected by Parameters.py
    os.environ['MPLBACKEND'] = 'Agg'
    saved_argv = sys.argv
    sys.argv = ['test_cdc_baseline_pin']

    try:
        from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
        from Parameters import return_parameters

        # Use Reduced_Run for speed (3 types, fewer periods)
        params = return_parameters(Parametrization='Reduced_Run', OutputFor='_Main.py')
        init_college = params[2]
        init_ADEconomy = params[3]

        # Single college agent type, fixed seed
        agent = AggFiscalType(**init_college)
        agent.cycles = 0
        agent.AgentCount = 100
        agent.seed = 42

        economy = AggregateDemandEconomy(**init_ADEconomy)
        agent.get_economy_data(economy)
        agent.update_mrkv_array(shock_type='base')
        agent.update_solution_terminal()

        # Solve + simulate
        agent.solve()
        agent.initialize_sim()
        agent.simulate()

        # Currently asserts None — replace with actual pinned values
        # Print the actual values when populating:
        for (period, agent_idx), expected_pins in CDC_SIMULATION_PINS.items():
            for var, expected_val in expected_pins.items():
                actual = agent.history[var][period, agent_idx] \
                    if var in agent.history else agent.state_now[var][agent_idx]
                print(f"  pin[period={period}, agent={agent_idx}] {var}: actual={actual:.10f}, expected={expected_val}")
                assert abs(actual - expected_val) < 1e-8, \
                    f"CDC simulation pin drift: {var} at ({period}, {agent_idx}): {actual} vs expected {expected_val}"
    finally:
        sys.argv = saved_argv
