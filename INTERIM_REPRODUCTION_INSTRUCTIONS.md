# Interim Reproduction Instructions

> **Currency note (2026-06-11):** HARK 0.17.1 was released 2026-02-02, but this repo has since moved to a newer pinned HARK; current reproduction instructions live in `reproduce/README.md` (uv-based) — this file is kept as the interim-period record.

> ⚠️ **DELETE THIS FILE** after HARK 0.17.1 is released and HAFiscal is updated.
> See `TODO_HARK_0171_UPDATE.md` for the update checklist.

---

## Current Status (as of 2025-01-18)

HAFiscal requires a patched version of HARK due to a bug in HARK 0.17.0's 
interpolation code. This document explains how to reproduce results until 
HARK 0.17.1 is released with the fix.

## Reproduction Options

### Option 1: Use HARK 0.14.1 (Original Environment)

This reproduces results using the original HARK version:

```bash
# Create environment with HARK 0.14.1
conda create -n HAFiscal_ark-0p14 python=3.9
conda activate HAFiscal_ark-0p14
pip install econ-ark==0.14.1 sequence-jacobian==1.0.0

# Checkout the fixed branch
git clone https://github.com/llorracc/HAFiscal-Latest.git
cd HAFiscal-Latest
git checkout master-with-borocnstnat-fix-using-0p14p1

# Run reproduction
cd Code/HA-Models/FromPandemicCode
python AggFiscalMAIN_reduced.py  # ~26 minutes
```

### Option 2: Use HARK 0.17.0 with Fix (Recommended for New Work)

This uses the modern HARK with the broadcasting fix:

```bash
# Clone and checkout
git clone https://github.com/llorracc/HAFiscal-Latest.git
cd HAFiscal-Latest
git checkout master-with-borocnstnat-fix-using-0p17p0

# Install (uses pinned HARK with fix)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .

# Run reproduction
cd Code/HA-Models/FromPandemicCode
python AggFiscalMAIN_reduced.py  # ~26 minutes
```

### Option 3: After HARK 0.17.1 Release (Future)

Once HARK 0.17.1 is released, the standard installation will work:

```bash
git clone https://github.com/llorracc/HAFiscal-Latest.git
cd HAFiscal-Latest
git checkout master  # or main branch after merge
pip install -e .
cd Code/HA-Models/FromPandemicCode
python AggFiscalMAIN_reduced.py
```

## Numerical Identity Verification

Both Option 1 and Option 2 produce **identical results** (verified 2025-01-18):

| Metric | Max Difference |
|--------|----------------|
| AggCons | 3.49×10⁻¹⁰ |
| AggIncome | 3.71×10⁻¹⁰ |
| NPV_AggCons | 3.64×10⁻¹⁰ |

All differences are within floating-point precision.

## Dependencies Pinning

For exact reproduction, the key dependency versions are:

| Package | Version (0.14.1 env) | Version (0.17.0 env) |
|---------|---------------------|---------------------|
| econ-ark | 0.14.1 | git@v0.17.0.post1-broadcasting-fix |
| sequence-jacobian | 1.0.0 | 1.0.0 |
| numpy | ≥1.24,<2 | ≥1.24,<2 |
| scipy | ≥1.10 | ≥1.10 |

## Questions?

- See `docs/HARK_Migration_Guide.md` for detailed migration documentation
- See `Code/HA-Models/FromPandemicCode/HARK_VERSION_NOTES.md` for technical details
- Open an issue: https://github.com/llorracc/HAFiscal-Latest/issues
