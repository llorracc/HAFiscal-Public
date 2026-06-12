# HAFiscal Upgrade Validation Records

This directory contains chronological records of HARK version upgrade attempts and validation results.

## Directory Structure

```
reproduce/upgrade-validation/
├── README.md                          # This file
├── UPGRADE_PLAN.md                    # Master upgrade plan and methodology
├── snapshots/                         # Pre-upgrade result snapshots
│   └── baseline_YYYYMMDD-HHMM/       # Timestamped baseline snapshots
│       ├── metadata.json              # Snapshot metadata (HARK version, git commit, etc.)
│       ├── estimation_results.json    # Estimation parameters (splurge, beta, nabla)
│       ├── multipliers.json           # Fiscal multipliers
│       ├── detailed_results.json      # Full numerical outputs (MPCs, Lorenz points, etc.)
│       └── table_values.json          # Numerical values extracted from .tex tables
├── attempts/                          # Individual upgrade attempt records
│   └── YYYYMMDD-HHMM_hark-X.Y.Z/     # Timestamped attempt directories
│       ├── attempt_report.md          # Human-readable attempt report
│       ├── attempt_metadata.json      # Machine-readable metadata
│       ├── validation_results.json    # Detailed comparison results
│       ├── fixes_applied.md           # List of code changes made
│       └── logs/                      # Associated log files
└── comparisons/                       # Cross-version comparison reports
    └── compare_YYYYMMDD-HHMM.md       # Comparison report documents
```

## Filename Pattern

All timestamped files/directories follow the pattern:
```
YYYYMMDD-HHMM_description
```

Examples:
- `20260124-1630_hark-0.17.0` - Attempt at upgrading to HARK 0.17.0
- `baseline_20260124-1600` - Baseline snapshot taken at 16:00 on 2026-01-24

## Quantitative Results Tracked

### 1. Estimation Parameters (from `--comp min` and `--comp full`)
- `splurge` - Splurge parameter
- `beta` - Discount factor center
- `nabla` - Discount factor spread

### 2. Fiscal Multipliers (from HANK model)
- UI extension multiplier (active/fixed nominal/fixed real rate)
- Transfer multiplier (active/fixed nominal/fixed real rate)
- Tax cut multiplier (active/fixed nominal/fixed real rate)

### 3. Welfare Results
- NPV multipliers for each policy
- Cumulative multipliers over time

### 4. Figure Verification (Secondary)
- **NOT based on file hashes** (too brittle - changes with timestamps, metadata, etc.)
- Extract numerical data points from figures where possible
- Visual inspection only for qualitative changes

## Meaningful Difference Threshold

A difference is considered **meaningful** if it exceeds **0.02 log points (~2%)**:
- Differences < 0.5%: Numerical noise, acceptable
- Differences 0.5% - 2%: Minor, document but acceptable  
- Differences > 2%: **PAUSE** - analyze cause, wait for user input

## Validation Levels

| Level | Command | Duration | Coverage |
|-------|---------|----------|----------|
| **nano** | `--comp nano` | ~10 sec | Basic syntax/import |
| **micro** | `--comp micro` | ~15 sec | Model setup |
| **mini** | `--comp mini` | ~40 sec | Single iteration |
| **min** | `--comp min` | ~2 hours | Full estimation, reduced iterations |
| **full** | `--comp full` | ~4-5 days | Complete reproduction |

## Acceptance Criteria

Results are evaluated using **log-point differences**:

| Difference | Classification | Action |
|------------|----------------|--------|
| < 0.005 (0.5%) | Numerical noise | ✅ Accept |
| 0.005 - 0.02 (0.5% - 2%) | Minor deviation | ✅ Accept with documentation |
| > 0.02 (2%) | **Meaningful difference** | ⚠️ **PAUSE** - analyze and await user input |

### On Meaningful Differences

If any metric exceeds the 0.02 log-point threshold:
1. **STOP** automated validation
2. **ANALYZE** the specific metrics that differ
3. **INVESTIGATE** potential causes (API changes, algorithm changes, bug fixes)
4. **REPORT** findings with full context
5. **WAIT** for user decision before proceeding

## Usage

### Creating a Baseline Snapshot
```bash
./reproduce/upgrade-validation/capture_snapshot.py --output snapshots/baseline_$(date +%Y%m%d-%H%M)
```

### Recording an Upgrade Attempt
```bash
./reproduce/upgrade-validation/record_attempt.py \
    --hark-version 0.17.0 \
    --baseline snapshots/baseline_20260124-1600 \
    --output attempts/$(date +%Y%m%d-%H%M)_hark-0.17.0
```

### Generating a Comparison Report
```bash
./reproduce/upgrade-validation/compare_results.py \
    --baseline snapshots/baseline_20260124-1600 \
    --attempt attempts/20260124-1630_hark-0.17.0 \
    --output comparisons/compare_$(date +%Y%m%d-%H%M).md
```
