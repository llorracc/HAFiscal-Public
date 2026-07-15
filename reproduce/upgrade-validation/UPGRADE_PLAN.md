# HAFiscal HARK Upgrade Validation Plan

## Overview

This document defines the comprehensive methodology for validating HARK version upgrades
to ensure quantitative results remain consistent.

## Upgrade Validation Steps

### Phase 0: Pre-Upgrade Preparation

#### Step 0.1: Capture Baseline Results
```bash
# Ensure current code produces correct results
./reproduce.sh --comp min

# Capture comprehensive baseline snapshot
./reproduce/upgrade-validation/capture_snapshot.py \
    --output snapshots/baseline_$(date +%Y%m%d-%H%M) \
    --hark-version $(python -c "import HARK; print(HARK.__version__)") \
    --notes "Pre-upgrade baseline"
```

#### Step 0.2: Document Current State
- Record current HARK version in pyproject.toml
- Record git commit hash
- Save all result files with timestamps

### Phase 1: Upgrade Attempt

#### Step 1.1: Create Upgrade Branch
```bash
git checkout -b hark-upgrade-X.Y.Z
```

#### Step 1.2: Update Dependencies
```bash
# Update pyproject.toml
# Run: uv sync
```

#### Step 1.3: Run Syntax Validation
```bash
# Quick check that code can be imported
./reproduce.sh --comp nano   # ~10 seconds
./reproduce.sh --comp micro  # ~15 seconds
```

#### Step 1.4: Run Minimal Validation
```bash
# Full estimation with reduced iterations
./reproduce.sh --comp min    # ~2 hours
```

#### Step 1.5: Compare Results
```bash
./reproduce/upgrade-validation/compare_results.py \
    --baseline snapshots/baseline_YYYYMMDD-HHMM \
    --current \
    --output comparisons/compare_$(date +%Y%m%d-%H%M).md
```

### Phase 2: Fix Iteration (if needed)

For each compatibility issue encountered:

#### Step 2.1: Identify the Issue
- Error message/traceback
- Affected file(s) and line(s)
- Root cause (API change, deprecation, etc.)

#### Step 2.2: Implement Fix
- Make minimal necessary changes
- Add comments explaining HARK version compatibility

#### Step 2.3: Create MWE
- Write minimal working example that tests the fix
- Ensure MWE passes on both old and new HARK versions

#### Step 2.4: Document Fix
```markdown
## Fix: [Description]
- **File**: `Code/HA-Models/...`
- **Line(s)**: X-Y
- **Issue**: [What broke]
- **Fix**: [What was changed]
- **MWE**: `validation_mwe.py::test_X`
```

#### Step 2.5: Re-run Validation
Repeat Steps 1.3-1.5 after each fix

### Phase 3: Full Validation (optional but recommended)

#### Step 3.1: Run Full Reproduction
```bash
./reproduce.sh --comp full   # 4-5 days
```

#### Step 3.2: Comprehensive Comparison
Compare ALL quantitative outputs:
- Estimation parameters
- Multipliers
- Welfare calculations
- Figure outputs

### Phase 4: Documentation and Merge

#### Step 4.1: Create Upgrade Report
```bash
./reproduce/upgrade-validation/record_attempt.py \
    --hark-version X.Y.Z \
    --baseline snapshots/baseline_YYYYMMDD-HHMM \
    --status SUCCESS \
    --output attempts/$(date +%Y%m%d-%H%M)_hark-X.Y.Z
```

#### Step 4.2: Update Documentation
- Update pyproject.toml version comments
- Update any HARK version notes
- Add entry to CHANGELOG

#### Step 4.3: Merge
```bash
git checkout main
git merge hark-upgrade-X.Y.Z
```

---

## Quantitative Metrics to Track

### Primary Metrics (must match within tolerance)

| Metric | Source File | Tolerance |
|--------|-------------|-----------|
| `splurge` | `Result_AllTarget.txt` | 0.5% |
| `beta` | `Result_AllTarget.txt` | 0.01% |
| `nabla` | `Result_AllTarget.txt` | 0.1% |

### Secondary Metrics (should match)

| Metric | Source | Tolerance |
|--------|--------|-----------|
| UI multiplier | HANK output | 1% |
| Transfer multiplier | HANK output | 1% |
| Tax cut multiplier | HANK output | 1% |
| Phillips curve slope | HANK output | 1% |

### Tertiary Metrics (informational)

| Metric | Source | Notes |
|--------|--------|-------|
| Computation time | Benchmark | May vary by hardware |
| Convergence iterations | Log output | May vary slightly |
| Memory usage | Profiler | May vary by HARK version |

---

## Acceptance Criteria Matrix

| Validation Level | Duration | Metrics Checked | Required for Merge? |
|------------------|----------|-----------------|---------------------|
| nano | 10s | Syntax only | Yes |
| micro | 15s | Imports | Yes |
| mini | 40s | Single iteration | Yes |
| **min** | 2h | **Full estimation** | **Yes** |
| full | 5d | Complete reproduction | Recommended |

---

## Current Upgrade Status

### HARK 0.14.1 → 0.17.0 (January 2026)

| Phase | Status | Date | Notes |
|-------|--------|------|-------|
| Phase 0 | ✅ Complete | 2026-01-24 | Baseline captured |
| Phase 1 | ✅ Complete | 2026-01-24 | --comp min passed |
| Phase 2 | ✅ Complete | 2026-01-24 | 4 fixes applied |
| Phase 3 | ⏳ Pending | - | --comp full not yet run |
| Phase 4 | ⏳ Pending | - | Awaiting Phase 3 |

#### Fixes Applied
1. `unpack_cFunc()` removal (3 locations)
2. `t_sim` reset before simulate(1) (2 locations)
3. `solution[0].cFunc` access pattern (4 locations)
4. `initialize_sim()` rename (1 location, dead code)

#### Validation Results
| Metric | HARK 0.14.1 | HARK 0.17.0 | Difference |
|--------|-------------|-------------|------------|
| splurge | 0.24611389 | 0.24664554 | 0.22% ✅ |
| beta | 0.96755116 | 0.96754368 | 0.0008% ✅ |
| nabla | 0.05780500 | 0.05780761 | 0.0045% ✅ |
