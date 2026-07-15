# Single Source of Truth Pattern for Robustness Output Cleanup

**Date**: 2025-01
**Status**: Implemented

## Problem

The repository accumulated ~80-90 orphaned robustness check PDFs (several hundred MB) from:
- Development experiments that were never completed
- Previously-enabled robustness checks that were later disabled by editor request
- Manual exploration of parameter spaces

These outputs were generated when robustness flags were temporarily set to `True`, but remained after flags were set back to `False`.

## Solution: SST-Based Intelligent Cleanup

### Before (Manual, Error-Prone)

1. Robustness flags in `AggFiscalMAIN.py` controlled execution
2. `Clean_Folders.py` hardcoded directories to clean
3. Manual execution required: `python Clean_Folders.py`
4. Easy to forget → orphaned outputs accumulated

**Problems:**
- Two separate sources of truth (flags vs. hardcoded dirs)
- Manual cleanup step often forgotten
- No guarantee of sync between flags and cleanup script

### After (Intelligent, Self-Syncing)

1. **Single Source of Truth**: `AggFiscalMAIN.py` defines robustness flags
2. **Smart Reader**: `Clean_Folders.py` **reads** flags from `AggFiscalMAIN.py`
3. **Separation of Concerns**: 
   - `AggFiscalMAIN.py` = simulation logic only
   - `Clean_Folders.py` = cleanup utility that respects the SST

**Benefits:**
- **Single Source of Truth**: Flags defined once in `AggFiscalMAIN.py`
- **No Duplication**: `Clean_Folders.py` reads flags, doesn't duplicate them
- **Always Synced**: Cleanup automatically respects current flag values
- **Separation of Concerns**: Simulation and cleanup are separate tools
- **Flexible**: Can run cleanup manually or integrate into workflow

## Implementation Details

### 1. Single Source of Truth (AggFiscalMAIN.py)

```python
# SST: These flags control execution
# Clean_Folders.py reads these flags to determine cleanup
Run_Main                = True   # Always keep
Run_EqualPVs            = True   # Always keep
Run_Splurge0            = True   # Online appendix

# Robustness checks excluded from paper
Run_ADElas_robustness   = False  
Run_CRRA1_robustness    = False 
Run_CRRA3_robustness    = False 
Run_Rfree_robustness    = False 
Run_Rspell_robustness   = False 
Run_LowerUBnoB          = False
```

### 2. Smart Reader (Clean_Folders.py)

```python
def read_robustness_flags_from_sst(main_script_path='./AggFiscalMAIN.py'):
    """Parse AggFiscalMAIN.py to extract flag values"""
    flag_values = {}
    pattern = r'^(Run_\w+)\s*=\s*(True|False)'
    
    for line in content.split('\n'):
        match = re.match(pattern, line.strip())
        if match:
            flag_name = match.group(1)
            flag_value = match.group(2) == 'True'
            flag_values[flag_name] = flag_value
    
    return flag_values
```

### 3. Flag-to-Directory Mapping (Clean_Folders.py)

```python
FLAG_TO_DIRECTORIES = {
    'Run_CRRA1_robustness': [
        'Figures/CRRA1/',
        'Figures/CRRA1_PVSame/'
    ],
    'Run_Rfree_robustness': [
        'Figures/Rfree_1005/',
        'Figures/Rfree_1015/',
        # ... PVSame variants
    ],
    # ... etc
}
```

### Cleanup Function Behavior

- **Reads** flag values from `AggFiscalMAIN.py` (SST)
- **Scans** directories mapped to `False` flags
- **Deletes** files >1MB (large computational outputs)
- **Preserves** small files (metadata, logs, config)
- **Reports** actions taken (files deleted, space freed)
- **Supports** `--dry-run` to preview actions
- **Configurable** size threshold via `--size-threshold`

## Workflow Integration

### Manual Cleanup

Run cleanup manually after simulations:

```bash
cd Code/HA-Models/FromPandemicCode
python Clean_Folders.py               # Clean with default settings
python Clean_Folders.py --dry-run     # Preview what would be deleted
python Clean_Folders.py --size-threshold 5  # Only delete files >5MB
```

### Automated Cleanup (Optional)

To integrate cleanup into the workflow, modify `do_all.py`:

```python
if run_step_5:
    os.chdir('FromPandemicCode')
    os.system("python AggFiscalMAIN.py")    # Run simulations
    os.system("python Clean_Folders.py")    # Clean orphaned outputs
    os.chdir('../')
```

This ensures cleanup happens after every full computational run.

## How to Enable a Robustness Check

To add back a robustness check:

1. **Change the flag** in `AggFiscalMAIN.py`:
   ```python
   Run_CRRA1_robustness = True  # Changed from False
   ```

2. **Run the workflow**:
   ```bash
   cd Code/HA-Models/FromPandemicCode
   python AggFiscalMAIN.py
   ```

3. **Outputs are generated** and **retained** (cleanup skips `True` flags)

## Evolution from Old Clean_Folders.py

- **Old approach**: Hardcoded list of directories to clean
- **New approach**: Reads flags from `AggFiscalMAIN.py` and determines directories dynamically
- **Benefit**: Zero duplication - flags defined once, cleanup reads them

## SST Principle

This pattern follows the **Single Source of Truth** principle:

- ✅ **One authoritative source**: Flags in `AggFiscalMAIN.py`
- ✅ **No duplication**: No separate cleanup config
- ✅ **Self-consistent**: Can't have mismatch between flags and cleanup
- ✅ **Maintainable**: Change flag → change behavior everywhere

## Files Modified

1. **`AggFiscalMAIN.py`**
   - Enhanced flag documentation to clarify they are the SST
   - No cleanup logic added (separation of concerns)

2. **`Clean_Folders.py`**
   - Completely rewritten to parse `AggFiscalMAIN.py`
   - Added command-line interface with `--dry-run` and `--size-threshold`
   - Added comprehensive docstrings and comments
   - Made intelligent: reads SST instead of hardcoding directories

3. **`README.md`**
   - Documented intelligent cleanup pattern
   - Explained usage and benefits

## Testing

### Dry Run (Preview)

See what would be deleted without actually deleting:

```bash
cd Code/HA-Models/FromPandemicCode
python Clean_Folders.py --dry-run
```

Expected output:
```
Reading robustness flags from AggFiscalMAIN.py (SST)...
Found 9 flags in AggFiscalMAIN.py

======================================================================
DRY RUN: Showing what would be deleted (no files will be removed)
======================================================================
Size threshold: Files larger than 1.0 MB
======================================================================

✓ Run_Main = True  → Keeping outputs
✓ Run_Splurge0 = True  → Keeping outputs
✗ Run_CRRA1_robustness = False → Cleaning outputs...
    [DRY RUN] Would delete: cumulative_multipliers.pdf (2.3 MB)
    → Would delete 12 file(s) from Figures/CRRA1/ (28.5 MB)
...
======================================================================
DRY RUN SUMMARY
======================================================================
Would delete 87 file(s), would free 423.5 MB
```

### Actual Cleanup

Run actual cleanup:

```bash
python Clean_Folders.py
```

Expected output shows actual deletions instead of "[DRY RUN] Would delete".

## Future Considerations

1. **Retention Policy**: Consider whether any disabled robustness outputs should be archived rather than deleted

2. **Size Threshold**: Current >1MB threshold could be made configurable

3. **Backup**: Before first run with new cleanup, consider backing up existing robustness outputs if needed

4. **Git Integration**: Add cleanup verification to CI/CD to ensure no orphaned outputs in repo

## References

- **SST Doctrine**: See `@local/METADATA_SST.md` for project-wide SST principles
- **Workflow**: See `do_all.py` for computational workflow orchestration
- **Robustness Appendix**: See `Subfiles/Appendix-Robustness.tex` (hidden in PDF, only uses summary figures)


