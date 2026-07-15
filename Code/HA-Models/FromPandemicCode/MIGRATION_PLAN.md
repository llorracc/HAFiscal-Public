# HAFiscal HARK 0.14.1 → 0.17.0 Migration: Documentation Plan

## Overview

This document outlines a plan to properly document the migration of HAFiscal from 
HARK 0.14.1 to HARK 0.17.0, ensuring that both HAFiscal coauthors and HARK 
collaborators can understand the full process.

## Target Audiences

### 1. HAFiscal Coauthors
**Need to understand:**
- Why migration was necessary (HARK 0.14.1 is deprecated)
- What bugs were discovered and fixed in HAFiscal itself
- How to verify that results are reproducible
- Which branch to use going forward

### 2. HARK Maintainers/Collaborators  
**Need to understand:**
- The broadcasting bug that affected downstream users
- How HAFiscal served as a real-world test case
- What the fix entails and why it's backward compatible

### 3. Future Developers/Researchers
**Need to understand:**
- How to migrate other HARK 0.14.x codebases to 0.17.x
- Common pitfalls (RNG changes, API changes)
- How to verify numerical identity after migration

---

## Proposed Documentation Structure

### A. In HAFiscal-Latest Repository

#### 1. High-Level Migration Guide (NEW)
**Location:** `docs/HARK_Migration_Guide.md`  
**Audience:** HAFiscal coauthors, future researchers

**Contents:**
- Executive summary of the migration
- Timeline of discovery and fixes
- Step-by-step guide to reproducing the verification
- FAQ for common questions

#### 2. Technical Notes (EXISTS - enhance)
**Location:** `Code/HA-Models/FromPandemicCode/HARK_VERSION_NOTES.md`  
**Audience:** Developers, technical reviewers

**Contents:** (already has most of this)
- Detailed description of each fix
- Code snippets showing before/after
- Verification results with numbers

#### 3. Bug Report Document (EXISTS)
**Location:** `Code/HA-Models/FromPandemicCode/bug_report_BoroCnstNat.md`  
**Audience:** Technical reviewers, HARK maintainers

**Purpose:** Documents the BoroCnstNat bug for potential upstream fix

#### 4. Branch README Updates
**Location:** Branch-specific README sections

Each relevant branch should have clear documentation of its purpose.

---

### B. In HARK Repository

#### 1. PR #1701 (EXISTS)
Already documents the broadcasting fix with MWE and tests.

#### 2. Changelog Entry (PROPOSE)
Add to `CHANGELOG.md` for next release (0.17.1):
```
### Fixed
- Fixed array broadcasting in 2D/3D/4D interpolators when mixing scalar and 
  array inputs (#1701). This restores behavior that worked in 0.14.x.
```

#### 3. Migration Notes (PROPOSE)
**Location:** `docs/migration/0.14-to-0.17.md` (new file)

Document known breaking changes and how to handle them, using HAFiscal as 
a case study.

---

## Proposed Branch Structure

### HAFiscal-Latest Branches

```
master (HARK 0.14.1)
│   └── Current production branch
│
├── master-with-borocnstnat-fix-using-0p14p1
│   └── BoroCnstNat bug fixed, still uses HARK 0.14.1
│   └── Serves as "ground truth" for verification
│
└── master-with-borocnstnat-fix-using-0p17p0  ← RECOMMENDED FOR NEW WORK
    └── Full HARK 0.17.0 compatibility
    └── Includes all fixes (BoroCnstNat, RNG sync)
    └── Pins to HARK broadcasting-fix tag
    └── VERIFIED: Produces identical results to 0p14p1 branch
```

### Future Plan
Once HARK 0.17.1 is released with the broadcasting fix:
1. Update `master-with-borocnstnat-fix-using-0p17p0` to use `econ-ark>=0.17.1`
2. Merge to `master`
3. Archive the 0p14p1 branch as historical reference

---

## Detailed Documentation Contents

### Document 1: Migration Guide (for coauthors)

```markdown
# Migrating HAFiscal to HARK 0.17.0

## Why Migrate?

HARK 0.14.1 was released in [date] and is no longer actively maintained.
HARK 0.17.0 includes:
- Performance improvements
- Bug fixes
- New features
- Better documentation

## What Changed?

### Issue 1: Broadcasting Bug in HARK (Fixed in HARK)

HARK 0.17.0 introduced a regression where interpolation functions failed
when called with mixed scalar/array inputs like `func(array, scalar)`.

**Impact:** Many HAFiscal functions use this pattern.
**Resolution:** Fixed via PR #1701, now merged to HARK master.

### Issue 2: BoroCnstNat Bug in HAFiscal (Fixed in HAFiscal)

During migration testing, we discovered a pre-existing bug in HAFiscal's
natural borrowing constraint calculation that existed in both versions.

**Impact:** Affected constraint calculations in edge cases.
**Resolution:** Fixed in `AggFiscalModel.py`.

### Issue 3: RNG Synchronization (Adaptation in HAFiscal)

HARK 0.17.0 changed how random number generators are initialized.

**Impact:** Simulations produced different random sequences.
**Resolution:** Added synchronization code to replicate 0.14.1 behavior.

## How to Verify

1. Install HARK 0.14.1 environment
2. Run `AggFiscalMAIN_reduced.py` on `master-with-borocnstnat-fix-using-0p14p1`
3. Install HARK 0.17.0 environment  
4. Run `AggFiscalMAIN_reduced.py` on `master-with-borocnstnat-fix-using-0p17p0`
5. Compare results - should be identical within floating-point precision

## Which Branch Should I Use?

- **For new development:** `master-with-borocnstnat-fix-using-0p17p0`
- **For reproducing published results:** Either branch (verified identical)
- **For understanding the original code:** `master` (unfixed)
```

### Document 2: HARK Migration Notes (for HARK repo)

```markdown
# Migrating from HARK 0.14.x to 0.17.x

## Breaking Changes

### Interpolation with Mixed Scalar/Array Inputs

**Versions affected:** 0.15.0 through 0.17.0 (fixed in 0.17.1)

In 0.14.x, you could call interpolation functions with mixed inputs:
```python
func(np.array([1, 2, 3]), 1.0)  # array for x, scalar for y
```

In 0.17.0, this raised an `IndexError`. 

**Workaround for 0.17.0:** Install from the fix tag:
```
pip install econ-ark @ git+https://github.com/econ-ark/HARK.git@v0.17.0.post1-broadcasting-fix
```

**Permanent fix:** Upgrade to 0.17.1+ when released.

### Random Number Generator Behavior

HARK 0.17.0 changed how `reset_rng()` works:
- 0.14.x: Resets agent RNG and IncShkDstn distributions
- 0.17.x: Resets ALL distributions in `self.distributions`

**Impact:** Simulations may produce different random sequences.

**If you need identical sequences:** Override `reset_rng()` in your agent class
to replicate 0.14.x behavior. See HAFiscal's `AggFiscalType` for an example.

## Case Study: HAFiscal Migration

The HAFiscal project successfully migrated from 0.14.1 to 0.17.0 with
verified numerical identity. Key learnings:

1. The broadcasting fix was critical
2. RNG synchronization required careful tracing
3. Migration revealed a pre-existing bug in the project's own code

Full documentation: [link to HAFiscal migration docs]
```

---

## Action Items

### Completed ✅

1. [x] Create `docs/HARK_Migration_Guide.md` in HAFiscal-Latest
2. [x] Create `HARK_VERSION_NOTES.md` with verification results
3. [x] Create `MIGRATION_PLAN.md` with decisions documented
4. [x] Push documentation to `master-with-borocnstnat-fix-using-0p17p0`
5. [x] Verify numerical identity (all 21 result files match)

### Pending Actions

#### For Pandemic Codebase (Priority: N/A - No Action Needed)
6. [x] ~~Create PR to Pandemic repo~~ **NOT NEEDED**
   - After code analysis: The Pandemic code is CORRECT
   - The bug was introduced when HAFiscal extended the code to handle
     `mNrmMinNext` as a function (for the Cratio dimension)
   - Pandemic always uses scalar `mNrmMinNext`, which has the correct formula

#### For HARK Repository (Priority: Medium)
7. [ ] Propose changelog entry for 0.17.1 release to @mnwhite
8. [ ] Consider adding `docs/migration/case_study_hafiscal.md` to HARK

#### For HAFiscal Repository (Priority: After HARK 0.17.1 Release)
9. [ ] When HARK 0.17.1 releases: Update `pyproject.toml` to use `econ-ark>=0.17.1`
10. [ ] Merge `master-with-borocnstnat-fix-using-0p17p0` to `master`
11. [ ] Update paper reproduction instructions if needed
12. [ ] Archive/delete obsolete migration branches

---

## Decisions Made (2025-01-18)

1. **Should the BoroCnstNat fix be backported to the original Pandemic code?**
   - **DECISION: YES** - Create a PR to the Pandemic codebase to fix the bug at 
     the source.

2. **Should `master` be updated to require HARK 0.17.1+ once released?**
   - **DECISION: YES** - Once HARK 0.17.1 is released with the broadcasting fix, 
     update HAFiscal `master` to pin to `econ-ark>=0.17.1`.

3. **How should we handle the RNG synchronization long-term?**
   - **DECISION: KEEP FOREVER** - The RNG synchronization code causes no harm and 
     preserves backward compatibility with HARK 0.14.1 results.

---

## Timeline

| Date | Milestone |
|------|-----------|
| 2025-01-18 | Numerical identity verified |
| 2025-01-18 | Documentation plan created |
| TBD | Migration guide reviewed by coauthors |
| TBD | HARK 0.17.1 released |
| TBD | HAFiscal master updated to use 0.17.1 |
