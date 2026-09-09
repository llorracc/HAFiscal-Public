# Clean_Folders.py Usage Guide

**Purpose**: Intelligent cleanup utility that reads robustness flags from `AggFiscalMAIN.py` and removes orphaned outputs.

## Quick Start

```bash
cd Code/HA-Models/FromPandemicCode

# Preview what would be deleted (recommended first step)
python Clean_Folders.py --dry-run

# Actually delete orphaned outputs
python Clean_Folders.py

# Only delete very large files (>5MB)
python Clean_Folders.py --size-threshold 5
```

## How It Works

1. **Reads SST**: Parses `AggFiscalMAIN.py` to extract robustness flag values
2. **Identifies targets**: For each flag set to `False`, identifies corresponding output directories
3. **Selective deletion**: Removes only large files (default: >1MB) from those directories
4. **Reports results**: Shows what was deleted and how much space was freed

## Command-Line Options

### `--dry-run`
Preview what would be deleted without actually deleting anything.

**Example:**
```bash
python Clean_Folders.py --dry-run
```

**Output:**
```
Reading robustness flags from AggFiscalMAIN.py (SST)...
Found 9 flags in AggFiscalMAIN.py

======================================================================
DRY RUN: Showing what would be deleted (no files will be removed)
======================================================================

✗ Run_CRRA1_robustness = False → Cleaning outputs...
    [DRY RUN] Would delete: cumulative_multipliers.pdf (2.3 MB)
    [DRY RUN] Would delete: recession_dynamics.pdf (1.8 MB)
    → Would delete 12 file(s) from Figures/CRRA1/ (28.5 MB)
...
```

### `--size-threshold MB`
Only delete files larger than the specified size in megabytes (default: 1 MB).

**Examples:**
```bash
python Clean_Folders.py --size-threshold 1    # Default: >1MB
python Clean_Folders.py --size-threshold 5    # Only >5MB files
python Clean_Folders.py --size-threshold 0.5  # >512KB files
```

## What Gets Cleaned

### Deleted (for disabled robustness checks):
- ✅ Large PDF files (>1MB default) - computational outputs
- ✅ Large PNG/SVG files (>1MB) - plots
- ✅ Any other large files in robustness directories

### Preserved:
- ✅ Small files (<1MB) - logs, metadata, config
- ✅ All outputs from **enabled** robustness checks (`True` flags)
- ✅ All baseline results (`CRRA2/`, `Splurge0/` when flags are `True`)

## Single Source of Truth Pattern

The script implements the SST pattern:

```
AggFiscalMAIN.py (SST)          Clean_Folders.py (Reader)
┌──────────────────────┐        ┌──────────────────────┐
│ Run_CRRA1_robustness │───────>│ Parses to extract    │
│        = False       │        │ flag values          │
│                      │        │                      │
│ Run_Rfree_robustness │───────>│ Determines which     │
│        = False       │        │ directories to clean │
└──────────────────────┘        └──────────────────────┘
```

**Benefits:**
- 📍 **One source of truth**: Flags defined once in `AggFiscalMAIN.py`
- 🔄 **Always synced**: Cleanup reads current flag values
- 🛡️ **No duplication**: No hardcoded directory lists
- 🔍 **Transparent**: Can preview with `--dry-run` before deleting

## When to Use

### After Development
When you've been experimenting with robustness checks and want to clean up:
```bash
python Clean_Folders.py --dry-run  # Check what would be deleted
python Clean_Folders.py            # Clean if happy with preview
```

### Before Committing
Before committing changes to ensure no orphaned outputs:
```bash
python Clean_Folders.py
git status  # Verify only intended files remain
```

### Periodic Maintenance
Run periodically to keep repository clean:
```bash
# Add to your workflow or run monthly
python Clean_Folders.py
```

## Integration with Workflow

### Manual (Current)
Run cleanup manually after simulations complete.

### Automated (Optional)
Modify `do_all.py` to run cleanup automatically:

```python
# At the end of do_all.py
if run_step_5:
    print('Step 5: Comparing policies\n')
    os.chdir('FromPandemicCode')
    os.system("python AggFiscalMAIN.py")
    
    # Automatic cleanup of orphaned outputs
    print('\nCleaning orphaned robustness outputs...')
    os.system("python Clean_Folders.py")
    
    os.chdir('../')
    print('Concluded Step 5. \n')
```

## Troubleshooting

### "ERROR: AggFiscalMAIN.py not found"
You're not in the correct directory. Run from `Code/HA-Models/FromPandemicCode/`:
```bash
cd Code/HA-Models/FromPandemicCode
python Clean_Folders.py
```

### "No robustness flags found"
Check that `AggFiscalMAIN.py` has flag assignments like:
```python
Run_CRRA1_robustness = False
```

### Want to keep specific outputs temporarily
Set the flag to `True` in `AggFiscalMAIN.py`:
```python
Run_CRRA1_robustness = True  # Cleanup will skip this
```

Then run cleanup - outputs for this robustness check will be preserved.

## Examples

### Example 1: Preview before cleaning
```bash
$ python Clean_Folders.py --dry-run

Reading robustness flags from AggFiscalMAIN.py (SST)...
Found 9 flags in AggFiscalMAIN.py

✗ Run_CRRA1_robustness = False → Cleaning outputs...
    [DRY RUN] Would delete: cumulative_multipliers.pdf (2.3 MB)
    → Would delete 1 file(s) from Figures/CRRA1/ (2.3 MB)

Would delete 1 file(s), would free 2.3 MB
```

### Example 2: Actual cleanup
```bash
$ python Clean_Folders.py

Reading robustness flags from AggFiscalMAIN.py (SST)...
Found 9 flags in AggFiscalMAIN.py

✗ Run_CRRA1_robustness = False → Cleaning outputs...
    Deleted: cumulative_multipliers.pdf (2.3 MB)
    → Deleted 1 file(s) from Figures/CRRA1/ (2.3 MB)

✓ Deleted 1 file(s), freed 2.3 MB
```

### Example 3: All directories clean
```bash
$ python Clean_Folders.py

Reading robustness flags from AggFiscalMAIN.py (SST)...
Found 9 flags in AggFiscalMAIN.py

✗ Run_CRRA1_robustness = False → Cleaning outputs...
    (No large files found in Figures/CRRA1/)
...

✓ No orphaned outputs found - all directories are clean.
```

## See Also

- **`CLEANUP-SST-PATTERN.md`**: Detailed explanation of the SST pattern
- **`AggFiscalMAIN.py`**: Single Source of Truth for robustness flags
- **`README.md`**: Overview of the computational model


