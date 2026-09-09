# HARK Version Compatibility Notes

This document describes the changes required to achieve numerical identity between
HAFiscal running on HARK 0.14.1 and HARK 0.17.0.

## Summary of Changes

Three categories of changes were required:

### 1. HARK Broadcasting Fix (PR #1701)

**Location**: HARK repository (not HAFiscal)

**Problem**: HARK 0.17.0's 2D/3D/4D interpolators failed when called with mixed
scalar/array inputs (e.g., `func(array, scalar)`). This pattern worked in 0.14.1
but caused `IndexError` in 0.17.0.

**Fix**: Added `np.broadcast_arrays()` calls in `HARKinterpolator2D`, 
`HARKinterpolator3D`, and `HARKinterpolator4D` to handle mixed inputs.

**Status**: Merged to HARK master via PR #1701. This branch pins to tag 
`v0.17.0.post1-broadcasting-fix` which includes the fix. Once HARK 0.17.1 is 
released, update `pyproject.toml` to use `econ-ark>=0.17.1`.

### 2. BoroCnstNat Calculation Fix (HAFiscal)

**Location**: `AggFiscalModel.py`, function `solve_one_period_ConsMrkvAggFiscal`

**Problem**: The natural borrowing constraint calculation was missing the 
`PermGroFac * PermShk / Rfree` factor in the `else` branch.

**Original (incorrect)**:
```python
else:
    aNrmMin_candidates = (mNrmMinNext(Cnext_array[:, 0, :]) - TranShkValsNext_tiled[:, 0, :])
```

**Fixed**:
```python
else:
    aNrmMin_candidates = PermGroFac[j]*PermShkValsNext_tiled[:, 0, :] / Rfree[j] * \
        (mNrmMinNext(Cnext_array[:, 0, :]) - TranShkValsNext_tiled[:, 0, :])
```

**Note**: This bug existed in both 0.14.1 and 0.17.0 versions of HAFiscal. It was 
NOT inherited from Pandemic - the original Pandemic code is correct. The bug was 
introduced when HAFiscal extended the code to handle `mNrmMinNext` as a function 
(for the Cratio/aggregate consumption dimension), and the `else` branch was 
incorrectly implemented without the multiplicative factor.

### 3. RNG Synchronization (HAFiscal)

**Locations**: 
- `AggFiscalModel.py` - `reset_rng()` and `sim_birth()` methods
- `Simulate.py` - IncShkDstn seed initialization

**Problem**: HARK 0.17.0 changed how random number generators are initialized and
reset, causing different RNG sequences than 0.14.1. Specifically:
1. `reset_rng()` resets more distributions in 0.17.0
2. `sim_birth()` consumes RNG integers differently
3. `IncShkDstn` distributions receive different seeds during construction

**Fixes**:

1. Override `reset_rng()` in `AggFiscalType` to replicate 0.14.1's behavior (reset 
   main RNG and IncShkDstn distributions only).

2. Override `sim_birth()` in `AggFiscalType` to consume RNG integers in the same 
   sequence as 0.14.1 + HAFiscal's local ConsMarkovModel.

3. In `Simulate.py`, explicitly synchronize `IncShkDstn` seeds before restructuring:
   ```python
   # HARK 0.17.0 FIX: Sync IncShkDstn seeds to match HARK 0.14.1 (763607780)
   for BaseType in BaseTypeList:
       BaseType.IncShkDstn[0].seed = 763607780
       BaseType.IncShkDstn[0].reset()
   ```

**Note**: These are intentional adaptations to maintain reproducibility across
versions, not HARK bugs. The seed value 763607780 is the seed that HARK 0.14.1
assigns to the IncShkDstn during construction.

## Verification

Numerical identity was verified on 2025-01-18 using `AggFiscalMAIN_reduced.py` 
with the `Reduced_Run` parametrization. All 21 result files were compared:

| File | Max Difference | Status |
|------|----------------|--------|
| base_results.csv | 3.49e-10 | ✅ MATCH |
| recession_results.csv | 3.71e-10 | ✅ MATCH |
| recession_results_AD.csv | 3.71e-10 | ✅ MATCH |
| recessionCheck_results.csv | 3.64e-10 | ✅ MATCH |
| recessionCheck_results_AD.csv | 3.71e-10 | ✅ MATCH |
| recessionUI_results.csv | 3.71e-10 | ✅ MATCH |
| recessionUI_results_AD.csv | 3.78e-10 | ✅ MATCH |
| recessionTaxCut_results.csv | 3.64e-10 | ✅ MATCH |
| recessionTaxCut_results_AD.csv | 3.64e-10 | ✅ MATCH |
| UI_results.csv | 3.49e-10 | ✅ MATCH |
| Check_results.csv | 3.49e-10 | ✅ MATCH |
| TaxCut_results.csv | 3.57e-10 | ✅ MATCH |
| base_results_full.csv | 3.49e-10 | ✅ MATCH |

All differences are within floating-point precision (~1e-9), confirming complete
numerical identity between HARK 0.14.1 and HARK 0.17.0 (with fixes applied).

### Test Environment

- **HARK 0.14.1**: conda environment `HAFiscal_ark-0p14_python3p9`
- **HARK 0.17.0**: venv with `econ-ark @ git+https://github.com/econ-ark/HARK.git@v0.17.0.post1-broadcasting-fix`
- **Runtime**: ~26 minutes per version for full Reduced_Run

This verification does not provide exhaustive coverage of all code paths but 
confirms the core simulation produces identical results across all experiment 
types (baseline, recession, UI extension, tax cut, checks) with and without 
aggregate demand effects.

## Branch Structure

- `master-with-borocnstnat-fix-using-0p14p1`: BoroCnstNat fix with HARK 0.14.1
- `master-with-borocnstnat-fix-using-0p17p0`: Full 0.17.0 compatibility (this branch)
  - Includes BoroCnstNat fix
  - Includes RNG synchronization code
  - Pins HARK to broadcasting-fix tag
