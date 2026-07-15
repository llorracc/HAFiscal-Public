# HAFiscal Validation Framework

## Overview

This validation framework ensures numerical reproducibility of HAFiscal computations across different HARK versions (0.14.1 and 0.17.0).

## Quick Start

```bash
cd /home/econ-ark/GitHub/llorracc/HAFiscal-Latest/Code/HA-Models

# Quicktest (~5 min): Rapid validation with reduced parameters
python quicktest_orchestrator.py --all

# Full validation (~1 hour): Production parameters
python quicktest_orchestrator.py --full --all
```

## Validation Modes

### Quicktest Mode (Default)
- **Purpose**: Rapid validation of computational machinery
- **Duration**: ~5 minutes
- **Parameters**: Reduced (200 agents, 10 periods, 2 types)
- **Steps**: 6 steps covering initialization, income, solver, simulation, and estimation

### Full Validation Mode
- **Purpose**: Production-level validation
- **Duration**: ~1 hour
- **Parameters**: Full (5000 agents, 800 periods, 7 types)
- **Steps**: 4 steps covering solver convergence, full simulation, and estimation pipelines

## Version Definitions

| Version | Description | HARK | Notes |
|---------|-------------|------|-------|
| `0.14.1-original` | HAFiscal-QE reference | 0.14.1 | **DO NOT MODIFY** - preserves reproducibility |
| `0.14.1-bugfixed` | Bug-fixed 0.14.1 | 0.14.1 | Uses IndShock when Rboro==Rsave |
| `0.17.0-native` | Recommended for new work | 0.17.0 | Refactored solver with bug inadvertently fixed |

### Expected Results
- `0.14.1-original` vs `0.17.0-native`: ~0.06% difference (due to grid bug)
- `0.14.1-bugfixed` vs `0.17.0-native`: **IDENTICAL** (both correct)

## The KinkedR Grid Bug

### What Happened
HARK 0.14.1's `KinkedRconsumerType` solver had a bug in grid construction:

```python
# Bug in HARK 0.14.1 KinkedR solver:
aNrmNow = aXtraGrid + mNrmMinNow  # mNrmMinNow = max(BoroCnstNat, BoroCnstArt) = 0

# Correct behavior (IndShock solver):
aNrmNow = aXtraGrid + BoroCnstNat  # BoroCnstNat = -0.135
```

### Impact
With `BoroCnstArt = 0` (no borrowing):
- `mNrmMinNow = max(-0.135, 0) = 0.0`
- Grid started at 0.0 instead of -0.135
- This prevented proper LowerEnvelope construction
- Result: ~0.06% consumption function difference

### Fix in 0.17.0
HARK 0.17.0's refactored solver delegates to `solve_one_period_ConsIndShock` when `Rboro == Rsave`, which correctly uses `BoroCnstNat`.

## Validation Steps

### Quicktest Steps

| Step | Name | Description | Output Keys |
|------|------|-------------|-------------|
| 1 | `agent_initialization` | Agent state setup | aNrm_mean, pLvl_mean, Mrkv_dist |
| 2 | `income_process` | Income shock distributions | IncShkDstn_pmv, PermShk_mean |
| 3 | `solver_single_iteration` | Single solver iteration | cFunc_test_points, vFunc_test_points |
| 4 | `simulation_short` | Short simulation (5 periods) | AggCons, AggWealth |
| 5 | `estimation_splurge_single_eval` | Splurge objective function | obj_func_value, simulated_MPC |
| 6 | `estimation_agg_fiscal` | Aggregate fiscal objective | obj_func_value, beta_gradient |

### Full Validation Steps

| Step | Name | Description | Timeout |
|------|------|-------------|---------|
| 1 | `solver_full_convergence` | Full solver with 48-point grid | 60 min |
| 2 | `simulation_full` | 800 periods, 5000 agents | 60 min |
| 3 | `estimation_splurge_full` | Full estimation pipeline | 60 min |
| 4 | `estimation_agg_fiscal_full` | Markov consumer simulation | 60 min |

## RNG Synchronization

To achieve exact numerical identity between HARK versions, the framework uses RNG-synchronized consumer types and solver patches.

### RNGSyncKinkedRconsumerType

This class replicates HARK 0.14.1's exact RNG consumption pattern:

1. **`reset_rng()`**: Only resets `self.RNG`, not distribution RNGs
2. **`sim_birth()`**: Always consumes 2 RNG integers for seeds (even when N=0)
3. **`IncShkDstn` seed handling**: Uses appropriate seed based on construction pattern:
   - If `seed` NOT in init_params: Uses default seed (763607780)
   - If `seed` IN init_params: Uses per-seed lookup table

### HARK 0.17.0 Solver Patches

Three patches applied to `solve_one_period_ConsKinkedR` for numerical compatibility:

1. **Grid compatibility (Rboro == Rsave)**:
   - Adjusts `aXtraGrid` by `(mNrmMinNow - BoroCnstNat)` before delegating
   - Ensures identical grid construction as HARK 0.14.1's KinkedR solver

2. **Kink point grid (Rboro > Rsave)**:
   - Changed `[0.0, 1e-15]` to `[0.0, 0.0]` at kink point
   - HARK 0.14.1 used "two copies of a=0" for proper kink handling

3. **Interest rate assignment**:
   - Changed `Rfree[aNrmNow <= 0] = Rboro` to `Rfree[0:i_kink] = Rboro`
   - This leaves the last zero at `i_kink` with Rsave (matching 0.14.1)

### Achieved Numerical Identity

| Step | Max Difference | Status |
|------|----------------|--------|
| Solver | 1.33e-15 | ✅ Machine precision |
| Simulation | 4.44e-14 | ✅ Machine precision |
| Estimation | 1.43e-05 | ✅ ~0.002% (accumulated FP rounding) |

## Commands

```bash
# List available steps
python quicktest_orchestrator.py --list

# Check status
python quicktest_orchestrator.py --status

# Run specific step
python quicktest_orchestrator.py --step 3

# Three-way comparison (shows bug impact)
python quicktest_orchestrator.py --all --three-way

# Full validation
python quicktest_orchestrator.py --full --all

# Specific versions
python quicktest_orchestrator.py --all --versions 0.14.1-original 0.17.0-native
```

## Output Locations

- Quicktest: `/tmp/hafiscal_quicktest/`
- Full validation: `/tmp/hafiscal_fulltest/`

Subdirectories:
- `logs/`: Detailed execution logs
- `results/`: JSON result files
- `checkpoints/`: Progress checkpoints
- `debug/`: Failure diagnostics

## Tolerance

The default comparison tolerance is **1%** (0.01 log points):
- Values within 1% are considered matching
- Larger differences trigger investigation

## Troubleshooting

### Step Fails with RNG Differences
- Check that `rng_synchronized_consumer.py` is in the code path
- Verify `agent.seed` is set consistently

### Step Fails with Shape Mismatch
- Check `AgentCount` and `T_sim` parameters match
- Verify Markov state dimensions

### Step Times Out
- Reduce parameters for debugging
- Check for infinite loops in solver

## File Structure

```
Code/HA-Models/
├── quicktest_orchestrator.py      # Main orchestrator
├── quicktest_config.py            # Configuration and parameters
├── rng_synchronized_consumer.py   # RNG-synced consumer types
├── quicktest_steps/               # Quicktest step scripts
│   ├── test_agent_init.py
│   ├── test_income_process.py
│   ├── test_solver.py
│   ├── test_simulation.py
│   ├── test_estimation_splurge.py
│   └── test_estimation_agg.py
├── fulltest_steps/                # Full validation step scripts
│   ├── test_solver_full.py
│   ├── test_simulation_full.py
│   ├── test_estimation_splurge_full.py
│   └── test_estimation_agg_full.py
└── VALIDATION_FRAMEWORK.md        # This documentation
```

## Contributing

When adding new validation steps:
1. Create script in `quicktest_steps/` or `fulltest_steps/`
2. Add `QuicktestStep` definition to orchestrator
3. Define meaningful `output_keys` for comparison
4. Test with both HARK versions
5. Document expected behavior
