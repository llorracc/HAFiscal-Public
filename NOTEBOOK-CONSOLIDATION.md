# Notebook Consolidation - January 10, 2026

## Summary

Consolidated three redundant Jupyter notebooks into a single canonical version with clear naming and organization.

## Problem Identified

The repository contained **four** notebook/dashboard files with significant confusion:

1. `HAFiscal-jupyterlab.ipynb` (root, 293K, 53 cells) - Oldest version (May 4, 2025)
2. `HAFiscal-dashboard.ipynb` (root, 280K, 62 cells) - Updated version (Jun 25, 2025)
3. `dashboard/hafiscal.ipynb` (dashboard/, 282K, 62 cells) - Latest version (Jul 1, 2025)
4. `dashboard/app.ipynb` (dashboard/, 73K) - Professional interactive dashboard (different purpose)

**Issues:**
- First three were nearly identical (all by William Du, demonstrating HANK-SAM model)
- REMARK.md listed same file for both `notebooks` and `dashboards` fields
- Professional dashboard (`dashboard/app.ipynb`) was not referenced in REMARK.md
- Confusing naming made it unclear which was the canonical version

## Solution Implemented

### Files Consolidated

**Kept:**
- `dashboard/hafiscal.ipynb` → renamed and moved to → `HAFiscal-HANK-and-SAM.ipynb` (root)
  - Reason: Most recent (Jul 1, 2025), most complete (62 cells), part of "first dashboard" commit series

**Deleted:**
- `HAFiscal-jupyterlab.ipynb` (outdated, fewer cells)
- `HAFiscal-dashboard.ipynb` (redundant, superseded)

**Preserved:**
- `dashboard/app.ipynb` (kept as-is, serves different purpose - professional interactive dashboard)

### New Organization

```
Repository Root:
├── HAFiscal-HANK-and-SAM.ipynb    # Educational notebook (HANK-SAM demonstration)
└── dashboard/
    ├── app.ipynb                   # Professional interactive dashboard (Voila)
    ├── hafiscal.ipynb              # Source copy (preserved for dashboard/ context)
    └── ...
```

### Files Updated

1. **REMARK.md** (HAFiscal-Latest, HAFiscal-Public, econ-ark/HAFiscal)
   ```yaml
   notebooks:
     - HAFiscal-HANK-and-SAM.ipynb
   dashboards:
     - dashboard/app.ipynb
   ```

2. **HAFiscal.md**
   - Updated notebooks and dashboards fields to match REMARK.md

3. **README_IF_YOU_ARE_AN_AI/070_INTERACTIVE_DASHBOARD.md**
   - Updated dashboard files table
   - Changed Method 3 from `HAFiscal-jupyterlab.ipynb` to `HAFiscal-HANK-and-SAM.ipynb`

### What Each File Now Represents

| File | Purpose | Type | For |
|------|---------|------|-----|
| `HAFiscal-HANK-and-SAM.ipynb` | Educational demonstration of HANK-SAM model with code | Jupyter Notebook | Learning the model, seeing code, running experiments |
| `dashboard/app.ipynb` | Professional interactive dashboard with sliders/widgets | Voila Dashboard | Exploring results without code, policy comparison |

## Scope of Notebooks

**Important Note:** These notebooks demonstrate **only the HANK-SAM part** of the full HAFiscal project (approximately 10% of the computational workflow).

**What the notebooks show:**
- HANK (Heterogeneous Agent New Keynesian) model results
- SAM (Sequence of Markets) analysis
- Uses pre-computed Jacobians from `Code/HA-Models/FromPandemicCode/`
- Impulse responses to UI extension, tax cuts, transfers
- General equilibrium effects

**What the full HAFiscal project includes:**
1. Splurge factor estimation (~20 min)
2. Discount factor distribution estimation (~21 hours)
3. Robustness checks (~21 hours, optional)
4. HANK model (~1 hour) ← **What notebooks demonstrate**
5. Policy comparison (~65 hours)
6. Empirical data processing (SCF 2004 analysis)

Total full reproduction: **4-5 days of computation**

## Commands to Repeat This Process

```bash
# 1. Copy the latest version to root with new name
cp dashboard/hafiscal.ipynb HAFiscal-HANK-and-SAM.ipynb

# 2. Delete redundant versions
rm -f HAFiscal-jupyterlab.ipynb HAFiscal-dashboard.ipynb

# 3. Update REMARK.md
# Change notebooks: [HAFiscal-dashboard.ipynb] → [HAFiscal-HANK-and-SAM.ipynb]
# Change dashboards: [HAFiscal-dashboard.ipynb] → [dashboard/app.ipynb]

# 4. Update HAFiscal.md (same changes as REMARK.md)

# 5. Update README_IF_YOU_ARE_AN_AI/070_INTERACTIVE_DASHBOARD.md
# Update dashboard files table
# Change Method 3 reference

# 6. Commit changes
git add HAFiscal-HANK-and-SAM.ipynb REMARK.md HAFiscal.md README_IF_YOU_ARE_AN_AI/070_INTERACTIVE_DASHBOARD.md
git add -u  # Stage deletions
git commit -m "Consolidate notebooks: create canonical HAFiscal-HANK-and-SAM.ipynb"
```

## Verification

After consolidation:

```bash
# Should find only one notebook in root:
ls -lh HAFiscal*.ipynb
# Output: HAFiscal-HANK-and-SAM.ipynb

# Should reference correct files:
grep "HAFiscal-HANK-and-SAM\|dashboard/app" REMARK.md
# Output: both filenames in correct fields

# Professional dashboard still exists:
ls -lh dashboard/app.ipynb
# Output: dashboard/app.ipynb
```

## Impact on econ-ark.org

With these changes, the econ-ark.org website will display:

1. **"Launch Notebook"** button → Opens `HAFiscal-HANK-and-SAM.ipynb` in JupyterLab
   - Full code visible and editable
   - Educational/learning focused

2. **"Launch Dashboard"** button → Opens `dashboard/app.ipynb` in Voila
   - No code visible (clean UI)
   - Interactive sliders and widgets
   - Professional policy exploration tool

## References

- Git history for `dashboard/hafiscal.ipynb`: Commits 9b385918, ab1ac3a3, fb6cf2aa, 7fce675e, 819044ee
- Original notebooks created: d90b6242 "Add stubs for jupyterlab notebook and dashboard"
- Last update to HAFiscal-dashboard.ipynb: 76554ccc "Update Dashboard"

## Date

January 10, 2026 (2026-01-10T18:10:00Z)
