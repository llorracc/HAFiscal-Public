# HAFiscal Common Workflows

**Version**: 1.0  
**Last Updated**: 2025-11-16

This guide provides step-by-step workflows for common tasks in the HAFiscal repository, organized by user type and goal.

---

## Table of Contents

1. [For Replicators](#for-replicators)
2. [For Researchers](#for-researchers)
3. [For Contributors](#for-contributors)
4. [For Instructors and Students](#for-instructors-and-students)
5. [For Dashboard Users](#for-dashboard-users)

---

## For Replicators

**Goal**: Reproduce the paper's results

### Quick Document Check (10 minutes)

Verify you can generate the paper PDF without running computations:

```bash
# Clone and setup
git clone {{REPO_URL}}.git
cd {{REPO_NAME}}

# Install UV and create environment
curl -LsSf https://astral.sh/uv/install.sh | sh
./reproduce/reproduce_environment_comp_uv.sh

# Generate documents
./reproduce.sh --docs main

# Check output
ls -lh HAFiscal.pdf HAFiscal-Slides.pdf
```

**Success**: Both PDFs should exist and be >1MB.

### Minimal Computational Validation (1 hour)

Run a subset of computations to validate the pipeline:

```bash
# From HAFiscal directory
./reproduce.sh --comp min

# Check generated files
ls Code/HA-Models/FromPandemicCode/Figures/CRRA2/
ls Code/HA-Models/FromPandemicCode/Tables/CRRA2/
```

**Success**: Should see several PDF figures and LaTeX tables.

### Full Replication (4-5 days on a high-end 2025 laptop)

Reproduce all computational results:

```bash
# From HAFiscal directory
./reproduce.sh --comp full

# Monitor progress
tail -f Code/HA-Models/do_all.log  # if logging enabled

# After completion, regenerate documents
./reproduce.sh --docs main
```

**Timeline**:

- Step 1: ~20 minutes
- Step 2: ~21 hours
- Step 3: ~21 hours (optional, for appendix)
- Step 4: ~1 hour
- Step 5: ~65 hours

**Hardware matters**: Times are for reference hardware (8-core CPU, 16GB RAM, NVMe SSD). Your times may vary significantly.

### Compare Your Results

```bash
# Check key numbers in generated results
cat Code/HA-Models/Results/AllResults_CRRA_2.0_R_1.01.txt

# Compare figures visually
open Code/HA-Models/FromPandemicCode/Figures/CRRA2/*.pdf

# Compare tables
cat Code/HA-Models/FromPandemicCode/Tables/CRRA2/Multiplier.tex
```

**Note**: Small numerical differences (<1%) are expected due to optimization algorithms and numerical precision.

---

## For Researchers

**Goal**: Understand, modify, or extend the models

### Explore the Model (1-2 hours)

```bash
# Setup environment
cd HAFiscal
uv sync
source .venv/bin/activate

# Read the computational README
cat Code/HA-Models/README.md

# Examine key model files
code Code/HA-Models/FromPandemicCode/AggFiscalModel.py      # Core model
code Code/HA-Models/FromPandemicCode/EstimParameters.py     # Parameters
code Code/HA-Models/FromPandemicCode/AggFiscalMAIN.py       # Policy comparison
```

### Run Individual Steps

```bash
cd Code/HA-Models

# Step 1: Estimate splurge factor
cd Target_AggMPCX_LiquWealth
python Estimation_BetaNablaSplurge.py
cd ..

# Step 2: Estimate discount factors (long!)
cd FromPandemicCode
python EstimAggFiscalMAIN.py
cd ..

# Step 5: Compare policies (very long!)
cd FromPandemicCode
python AggFiscalMAIN.py
cd ..
```

### Modify Model Parameters

```bash
# 1. Edit parameters
vim Code/HA-Models/FromPandemicCode/EstimParameters.py

# 2. Test with minimal run
python Code/HA-Models/reproduce_min.py

# 3. If successful, run full pipeline
python Code/HA-Models/do_all.py
```

### Add New Policy

```bash
# 1. Study existing policy implementation
vim Code/HA-Models/FromPandemicCode/AggFiscalMAIN.py
# Look for UIextension, Checks, TaxCut implementations

# 2. Add your policy (e.g., NewPolicy)
#    - Define policy parameters
#    - Implement shock/transfer
#    - Add to comparison loop

# 3. Test with single agent type first
python -c "from AggFiscalMAIN import *; test_new_policy()"

# 4. Run full comparison
python AggFiscalMAIN.py
```

### Compare Alternative Specifications

The code supports multiple parametrizations:

```bash
cd Code/HA-Models/FromPandemicCode

# Edit AggFiscalMAIN.py to select parametrization
# flag_ParamSettings = {
#     'CRRA': 2.0,              # Try 1.0 or 3.0
#     'Rfree': 1.01,            # Try 1.005 or 1.015
#     'PVSame': False,          # Try True for equal PV
#     'Splurge': True           # Try False for no splurge
# }

# Run with new parameters
python AggFiscalMAIN.py

# Results in new subdirectory
ls Figures/CRRA3/  # if you changed CRRA to 3.0
ls Tables/CRRA3/
```

---

## For Contributors

**Goal**: Improve the codebase or documentation

### Setup for Development

```bash
# Clone SOURCE repository (not public!)
git clone {{REPO_URL}}.git
cd {{REPO_NAME}}

# Create development branch
git checkout -b feature/my-improvement

# Setup environment
uv sync
source .venv/bin/activate
```

**Important**: Always work in `{{REPO_NAME}}`, never directly in `econ-ark/HAFiscal`.

### Make Code Changes

```bash
# 1. Make changes
vim Code/HA-Models/FromPandemicCode/MyFile.py

# 2. Test changes
python Code/HA-Models/reproduce_min.py  # Quick test

# 3. Run full test if needed
python Code/HA-Models/do_all.py

# 4. Commit
git add Code/HA-Models/FromPandemicCode/MyFile.py
git commit -m "feat: Improve MyFile performance"
```

### Update Documentation

```bash
# 1. Edit documentation
vim docs/MY_TOPIC.md

# 2. Update documentation index if new file
vim docs/README.md

# 3. Commit
git add docs/
git commit -m "docs: Add MY_TOPIC documentation"
```

### Test LaTeX Changes

```bash
# 1. Edit LaTeX
vim Subfiles/Model.tex

# 2. Test standalone compilation
cd Subfiles
latexmk -pdf Model.tex
cd ..

# 3. Test in full document
./reproduce.sh --docs main

# 4. Commit if successful
git add Subfiles/Model.tex
git commit -m "docs: Clarify model description"
```

### Dashboard Changes

```bash
# 1. Edit dashboard
vim dashboard/app.ipynb

# 2. Test locally
cd dashboard
voila app.ipynb --no-browser

# Open http://localhost:8866 and test

# 3. Commit
git add dashboard/app.ipynb
git commit -m "feat: Add new dashboard preset"
```

### Submit Pull Request

```bash
# 1. Push branch
git push origin feature/my-improvement

# 2. Create PR on GitHub
#    Go to: {{REPO_URL}}
#    Click "Pull Requests" → "New Pull Request"
#    Select your branch

# 3. After merge, sync to public (maintainers only)
cd ~/GitHub/HAFiscal-make
./makePublic-master.sh
```

---

## For Instructors and Students

**Goal**: Use HAFiscal for teaching or learning

### Classroom Demo (30 minutes)

```bash
# 1. Launch dashboard (no installation needed!)
# Go to: https://mybinder.org/v2/gh/econ-ark/HAFiscal/master?urlpath=voila/render/dashboard/app.ipynb

# 2. Show students:
#    - Adjust monetary policy (Taylor rule, fixed nominal, fixed real)
#    - Compare fiscal policies (UI, checks, tax cuts)
#    - Observe fiscal multipliers in real-time
#    - Discuss parameter effects
```

### Student Exercise: Replicate One Figure

```bash
# 1. Students clone repository
git clone {{REPO_URL}}.git
cd {{REPO_NAME}}
./reproduce/reproduce_environment_comp_uv.sh

# 2. Run step 1 only (~20 minutes)
cd Code/HA-Models/Target_AggMPCX_LiquWealth
python Estimation_BetaNablaSplurge.py

# 3. Check output
ls ../../Figures/liquwealthdistribution.pdf

# 4. Discussion:
#    - What does the figure show?
#    - How does the model match the data?
#    - What if we changed the splurge parameter?
```

### Student Project: Modify Policy

```bash
# Assignment: Implement a graduated income tax

# 1. Students study existing tax implementation
vim Code/HA-Models/FromPandemicCode/AggFiscalMAIN.py
# Look for TaxCut implementation

# 2. Modify to make progressive
# - Add income brackets
# - Add bracket-specific rates
# - Update tax calculation

# 3. Run with minimal parameters
python reproduce_min.py

# 4. Write report:
#    - How does progressive tax affect multipliers?
#    - Which income groups benefit most?
#    - Welfare implications?
```

### Course Material

Use HAFiscal components in teaching:

**Macroeconomics**:

- Heterogeneous agent models
- Fiscal policy effectiveness
- Automatic stabilizers vs. discretionary policy

**Computational Economics**:

- Solving heterogeneous agent models
- Method of simulated moments estimation
- Sequence space Jacobian methods

**Public Economics**:

- Welfare analysis of transfers
- Tax incidence in general equilibrium
- Optimal fiscal policy design

---

## For Dashboard Users

**Goal**: Explore policy scenarios interactively

### Online Dashboard (No Installation)

```bash
# Open in browser:
https://mybinder.org/v2/gh/econ-ark/HAFiscal/master?urlpath=voila/render/dashboard/app.ipynb

# Or production server:
http://45.55.225.169:8866
```

### Local Dashboard Setup

```bash
# 1. Clone and setup
git clone {{REPO_URL}}.git
cd {{REPO_NAME}}
uv sync
source .venv/bin/activate

# 2. Launch dashboard
cd dashboard
voila app.ipynb --no-browser

# 3. Open browser to http://localhost:8866
```

### Explore Policy Scenarios

**Preset Scenarios**:

1. Click "Baseline" - Standard parameters
2. Click "Short tax cut" - Brief tax reduction
3. Click "High output target" - Aggressive stabilization
4. Click "Extended UI" - Long unemployment benefits

**Custom Scenarios**:

1. Adjust sliders:
   - **Φπ** (phi_pi): Monetary policy response to inflation
   - **ρi** (rho_i): Interest rate persistence
   - **τdur** (tau_dur): Fiscal policy duration
   - **Target** (target): Output stabilization goal

2. Observe real-time updates:
   - Fiscal multipliers over 20 quarters
   - Consumption impulse responses
   - Comparison across scenarios

**Compare Policies**:

- Scenario 1: Baseline
- Scenario 2: UI Extension
- Scenario 3: Stimulus Checks
- Scenario 4: Tax Cut

All scenarios use same monetary policy for clean comparison.

### Export Results

```python
# In notebook mode (not Voila), run:
import matplotlib.pyplot as plt

# Save figure
plt.savefig('my_policy_comparison.pdf')

# Export data
import pandas as pd
df = pd.DataFrame({
    'Quarter': quarters,
    'Multiplier_UI': multipliers_ui,
    'Multiplier_Checks': multipliers_checks,
    'Multiplier_TaxCut': multipliers_taxcut
})
df.to_csv('multipliers.csv', index=False)
```

---

## Troubleshooting Common Issues

### "File not found" errors in LaTeX

**Problem**: Missing figure or table files  
**Cause**: Haven't run computational pipeline  
**Solution**:

```bash
# Run minimal computation first
./reproduce.sh --comp min
# Then compile documents
./reproduce.sh --docs main
```

### Computational script hangs

**Problem**: Script seems frozen  
**Cause**: Long optimization step (can take hours)  
**Solution**:

```python
# Add progress output to script
import logging
logging.basicConfig(level=logging.INFO)

# Or check system resources
htop  # Linux
top   # macOS
```

### Different results than paper

**Problem**: Numbers don't match exactly  
**Cause**: Numerical optimization, floating point precision  
**Expected**: <1% difference is normal  
**Check**:

```bash
# Are you using correct data vintage?
ls Code/Empirical/rscfp2004.dta  # Should be original, not USD2022

# Check Python versions
python --version  # Should be 3.9+

# Check key package versions
python -c "import numpy; print(numpy.__version__)"
```

---

## Quick Reference by Goal

| Goal | Entry Point | Time | Difficulty |
|------|-------------|------|------------|
| **Check paper PDF** | `./reproduce.sh --docs main` | 5-10 min | Easy |
| **Test pipeline** | `./reproduce.sh --comp min` | ~1 hour | Easy |
| **Full replication** | `./reproduce.sh --comp full` | 4-5 days on a high-end 2025 laptop | Medium |
| **Modify model** | `Code/HA-Models/.../*.py` | Varies | Hard |
| **Update docs** | `docs/*.md` | <30 min | Easy |
| **Explore interactively** | Dashboard | Immediate | Easy |
| **Classroom demo** | MyBinder dashboard | Immediate | Easy |
| **Student project** | Modify one policy | Days-weeks | Medium |

---

## See Also

- **[README.md](README.md)** - Main documentation
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Repository structure
- **[README/INSTALLATION.md](README/INSTALLATION.md)** - Setup instructions
- **[README/TROUBLESHOOTING.md](README/TROUBLESHOOTING.md)** - Common problems
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines

---

**Version**: 1.0  
**Last Updated**: 2025-11-16  
**Feedback**: Open an issue at {{REPO_URL}}/issues
