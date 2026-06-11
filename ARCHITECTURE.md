# HAFiscal Code Architecture

**Purpose**: Understand the organization and flow of code in this repository  
**Last Updated**: 2025-12-17

---

## High-Level Architecture

```
Data Sources → Data Processing → Model Estimation → Policy Analysis → Output Generation
    ↓               ↓                  ↓                ↓                ↓
  SCF 2004    make_liquid_    EstimAggFiscalMAIN   AggFiscalMAIN   Output_Results.py
              _wealth.py                              .py            Welfare.py
```

---

## Directory Structure

```
HAFiscal-Latest/
├── Code/                          # All computational code
│   ├── Empirical/                 # Data processing
│   │   ├── make_liquid_wealth.py  # Construct liquid wealth measure
│   │   ├── adjust_scf_inflation.py # Inflation adjustments
│   │   ├── compare_scf_datasets.py # Dataset comparisons
│   │   ├── download_scf_data.sh   # Download SCF data
│   │   └── *.dta, *.csv          # Data files
│   └── HA-Models/                 # Heterogeneous agent models
│       ├── do_all.py              # Main pipeline orchestrator
│       ├── reproduce_min.py       # Minimal validation script
│       ├── Target_AggMPCX_LiquWealth/  # Step 1: Splurge estimation
│       │   └── Estimation_BetaNablaSplurge.py
│       └── FromPandemicCode/      # Steps 2-5: Main analysis
│           ├── EstimAggFiscalMAIN.py    # Step 2: Estimation
│           ├── AggFiscalMAIN.py          # Step 5: Policy comparison
│           ├── AggFiscalModel.py         # Model classes
│           ├── Simulate.py               # Simulation
│           ├── Output_Results.py         # Generate figures/tables
│           ├── Welfare.py                # Welfare calculations
│           ├── Parameters.py             # Model parameters
│           ├── EstimParameters.py        # Estimation parameters
│           ├── Figures/                  # Generated figures
│           └── Tables/                   # Generated tables
├── Figures/                       # Figure LaTeX files (*.tex, *.pdf)
├── Tables/                        # Table LaTeX files (*.tex, *.pdf)
├── Subfiles/                      # LaTeX paper sections
├── HAFiscal.tex                   # Main LaTeX document
├── reproduce.sh                   # Main entry point for all operations
├── environment.yml                # Conda environment specification
└── README/                        # Extended documentation
```

---

## Core Computational Pipeline

The computational workflow is orchestrated by `Code/HA-Models/do_all.py` and consists of 5 sequential steps:

### Step 1: Splurge Factor Estimation (~20 minutes)

```
SCF 2004 Data
    ↓
Code/Empirical/make_liquid_wealth.py
    - Process SCF microdata
    - Calculate liquid wealth distribution
    - Generate calibration targets
    ↓
Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py
    - Jointly estimate discount factor distribution and splurge factor
    - Match aggregate MPC and liquid wealth distribution
    ↓
Outputs:
  - Figure 1: MPC_WealthQuartiles_Figure.pdf
  - Table 1: MPC_WealthQuartiles_Table.tex
  - Estimated parameters saved for later steps
```

**Key Files**:
- `Code/Empirical/make_liquid_wealth.py` - Data processing
- `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py` - Splurge estimation

**Runtime**: ~20 minutes

---

### Step 2: Discount Factor Distribution Estimation (~21 hours) ⚠️

```
Calibration Targets (from Step 1)
    ↓
Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py
    - Estimate discount factor distributions for 3 education groups
    - Simulated Method of Moments matching consumption drop upon UI exit
    - ~7 hours per education group
    ↓
Code/HA-Models/FromPandemicCode/CreateLPfig.py
    - Generate Figure 2 (lifecycle profiles)
    ↓
Code/HA-Models/FromPandemicCode/CreateIMPCfig.py
    - Generate Figure 3 (impulse response functions)
    ↓
Outputs:
  - Figure 2: Lifecycle profiles
  - Figure 3: iMPC profiles
  - Estimated parameters for each education group
  - Results: AllResults_CRRA_2.0_R_1.01.txt
```

**Key Files**:
- `Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py` - Main estimation
- `Code/HA-Models/FromPandemicCode/EstimParameters.py` - Calibrated parameters
- `Code/HA-Models/FromPandemicCode/CreateLPfig.py` - Figure 2
- `Code/HA-Models/FromPandemicCode/CreateIMPCfig.py` - Figure 3

**Runtime**: ~21 hours (7 hours × 3 education groups)

---

### Step 3: Robustness Check with Splurge=0 (OPTIONAL, ~21 hours)

```
Same as Step 2, but with Splurge=0 parameter
    ↓
Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (Splurge=0)
    ↓
Outputs:
  - Table 8: welfare6_SplurgeComp.tex (robustness comparison)
```

**Note**: This step is **disabled by default** in `do_all.py` (set `run_step_3=True` to enable)

**Runtime**: ~21 hours (similar to Step 2)

---

### Step 4: HANK-SAM Model Robustness (~1 hour)

```
Code/HA-Models/FromPandemicCode/HA-Fiscal-HANK-SAM.py
    - Compute household Jacobian matrices
    - General equilibrium effects
    ↓
Code/HA-Models/FromPandemicCode/HA-Fiscal-HANK-SAM-to-python.py
    - Run HANK-SAM experiments
    - Sequence Space Jacobian methods
    ↓
Outputs:
  - Figure 5: HANK-SAM policy comparisons
  - Jacobian matrices: HA_Fiscal_Jacs.obj, HA_Fiscal_Jacs_UI_extend_real.obj
```

**Key Files**:
- `Code/HA-Models/FromPandemicCode/HA-Fiscal-HANK-SAM.py` - Jacobian computation
- `Code/HA-Models/FromPandemicCode/HA-Fiscal-HANK-SAM-to-python.py` - Experiments

**Runtime**: ~1 hour

---

### Step 5: Policy Comparison (~65 hours) ⚠️

```
Baseline Model (from Step 2)
    ↓
Code/HA-Models/FromPandemicCode/AggFiscalMAIN.py
    - Analyze three fiscal policies:
      1. UI benefit extension
      2. Stimulus checks (lump-sum transfers)
      3. Payroll tax cuts
    - Welfare and spending analysis
    - Fiscal multiplier calculations
    ↓
Code/HA-Models/FromPandemicCode/Output_Results.py
    - Generate Figure 4 (policy effects, 6 subfigures)
    - Generate Table 6 (fiscal multipliers)
    ↓
Code/HA-Models/FromPandemicCode/Welfare.py
    - Calculate welfare changes by wealth percentile
    - Generate Figure 6 (welfare comparisons)
    - Generate Table 7 (welfare effectiveness)
    ↓
Outputs:
  - Figure 4: Policy effects (6 panels)
  - Figure 6: Welfare comparisons
  - Table 6: Multipliers (Multiplier.tex)
  - Table 7: Welfare (welfare6.tex)
  - Table 8: Splurge comparison (if Step 3 run)
```

**Key Files**:
- `Code/HA-Models/FromPandemicCode/AggFiscalMAIN.py` - Policy comparison
- `Code/HA-Models/FromPandemicCode/AggFiscalModel.py` - Model classes
- `Code/HA-Models/FromPandemicCode/Simulate.py` - Simulation utilities
- `Code/HA-Models/FromPandemicCode/Output_Results.py` - Figure/table generation
- `Code/HA-Models/FromPandemicCode/Welfare.py` - Welfare calculations

**Runtime**: ~65 hours (longest step)

---

## Module Dependency Graph

```
External Libraries
  ↓
  HARK (econ-ark)
  ↓
FromPandemicCode/AggFiscalModel.py
  ↓
  ├→ EstimAggFiscalMAIN.py (Step 2)
  │    ↓
  │    ├→ CreateLPfig.py → Figure 2
  │    └→ CreateIMPCfig.py → Figure 3
  │
  ├→ AggFiscalMAIN.py (Step 5)
  │    ↓
  │    ├→ Simulate.py
  │    ├→ Output_Results.py → Figure 4, Table 6
  │    └→ Welfare.py → Figure 6, Table 7
  │
  └→ HA-Fiscal-HANK-SAM.py (Step 4)
       ↓
       HA-Fiscal-HANK-SAM-to-python.py → Figure 5
```

---

## Entry Points

### Main Entry Point: `reproduce.sh`

```bash
./reproduce.sh [flags]

Flags:
  --envt        Set up Python environment
  --docs        Compile LaTeX documents
  --comp min    Run minimal computation (~1 hour)
  --comp full   Run full computation (~4-5 days)
  --data        Download/process data
```

**What it does**:
```
--envt:  Install dependencies → Verify setup
--docs:  Run LaTeX compiler → Generate PDF
--comp:  Calls Code/HA-Models/do_all.py with configured steps
```

### Secondary Entry Point: `Code/HA-Models/do_all.py`

```python
# Run all steps (4-5 days)
cd Code/HA-Models
python do_all.py

# Or run minimal validation (~1 hour)
python reproduce_min.py
```

**Direct script execution** (individual steps):

```bash
# Step 1: Splurge estimation
cd Code/HA-Models/Target_AggMPCX_LiquWealth
python Estimation_BetaNablaSplurge.py

# Step 2: Estimation
cd Code/HA-Models/FromPandemicCode
python EstimAggFiscalMAIN.py

# Step 5: Policy comparison
cd Code/HA-Models/FromPandemicCode
python AggFiscalMAIN.py

# Generate outputs
python Output_Results.py
python Welfare.py
```

---

## Computational Bottlenecks

| Stage | Runtime | Parallelizable? | Bottleneck |
|-------|---------|-----------------|------------|
| Step 1: Splurge estimation | 20 min | No | Single optimization |
| Step 2: Estimation | 21 hours | Partial | Education groups (can parallelize) |
| Step 3: Robustness (optional) | 21 hours | Partial | Similar to Step 2 |
| Step 4: HANK-SAM | 1 hour | Partial | Jacobian computation |
| Step 5: Policy comparison | 65 hours | Partial | Policy scenarios |

**Total Runtime**:
- With Step 3: ~108 hours (4.5 days)
- Without Step 3: ~87 hours (3.6 days)

**Parallelization opportunities**:
- Step 2: Run education groups in parallel
- Step 5: Some policy scenarios can be parallelized

---

## External Dependencies

### Python Packages (from pyproject.toml/environment.yml)

**Core**:
- `econ-ark >= 0.14.1`: Heterogeneous agent toolkit (HARK)
- `numpy >= 1.21`: Numerical computing
- `scipy >= 1.7`: Optimization, statistics
- `pandas >= 1.3`: Data manipulation

**Visualization**:
- `matplotlib >= 3.4`: Plotting
- `seaborn >= 0.11`: Statistical visualization

**Data**:
- `pyreadstat`: Read Stata files (.dta)
- `openpyxl`: Excel files (if needed)

**Other**:
- `joblib`: Parallel processing
- `sequence-jacobian`: For HANK-SAM models (Step 4)

### LaTeX Packages (from reproduce/required_latex_packages.txt)

Key packages: `econark`, `subfiles`, `hyperref`, `booktabs`, `graphicx`, `amsmath`, `natbib`

---

## File Size Reference

| Directory | Typical Size | Notes |
|-----------|-------------|-------|
| Code/ | ~2 MB | Python scripts |
| Code/HA-Models/FromPandemicCode/Figures/ | ~20 MB | Generated PDFs |
| Code/HA-Models/FromPandemicCode/Tables/ | ~1 MB | LaTeX tables |
| Code/HA-Models/Results/ | ~500 MB | Intermediate results (not in repo) |
| .venv-{platform}/ | ~1 GB | Python environment (not in repo) |

---

## Testing & Validation

### Quick Verification (`--comp min`)

The minimal reproduction runs a subset of steps to verify the environment works:

```bash
./reproduce.sh --comp min
```

This executes `Code/HA-Models/reproduce_min.py` which runs faster validation steps.

### Full Validation (`--comp full`)

```bash
./reproduce.sh --comp full
```

This runs all 5 steps (or 4 if Step 3 is disabled) and generates all figures and tables.

**Runtime**: 4-5 days

---

## Common Workflows

### Workflow 1: Quick Verification

```bash
./reproduce.sh --envt           # Set up environment
./reproduce.sh --docs           # Compile paper
./reproduce.sh --comp min       # Quick validation
# Total: ~1-2 hours
```

### Workflow 2: Run Single Step

```bash
# Step 1 only
cd Code/HA-Models
python do_all.py  # Edit do_all.py: set run_step_1=True, others=False

# Step 5 only (requires Steps 1-2 completed first)
cd Code/HA-Models/FromPandemicCode
python AggFiscalMAIN.py
```

### Workflow 3: Modify Model Parameters

```python
# Edit parameters
vim Code/HA-Models/FromPandemicCode/Parameters.py
# or
vim Code/HA-Models/FromPandemicCode/EstimParameters.py

# Re-run affected step
cd Code/HA-Models/FromPandemicCode
python EstimAggFiscalMAIN.py  # If estimation params changed
python AggFiscalMAIN.py        # If policy params changed
```

---

## Key Files Reference

### Model Definition
- `Code/HA-Models/FromPandemicCode/AggFiscalModel.py` - Core model classes
- `Code/HA-Models/FromPandemicCode/ConsMarkovModel.py` - Consumer model with Markov unemployment
- `Code/HA-Models/FromPandemicCode/EstimAggFiscalModel.py` - Estimation-specific variants

### Parameters
- `Code/HA-Models/FromPandemicCode/Parameters.py` - Model parameters
- `Code/HA-Models/FromPandemicCode/EstimParameters.py` - Estimation/calibration parameters

### Estimation
- `Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py` - Main estimation (Step 2)
- `Code/HA-Models/FromPandemicCode/EstimSetupEconomy.py` - Economy setup for estimation

### Policy Analysis
- `Code/HA-Models/FromPandemicCode/AggFiscalMAIN.py` - Policy comparison (Step 5)
- `Code/HA-Models/FromPandemicCode/Simulate.py` - Simulation utilities
- `Code/HA-Models/FromPandemicCode/Welfare.py` - Welfare calculations

### Output Generation
- `Code/HA-Models/FromPandemicCode/Output_Results.py` - Generate figures and tables
- `Code/HA-Models/FromPandemicCode/CreateLPfig.py` - Generate Figure 2
- `Code/HA-Models/FromPandemicCode/CreateIMPCfig.py` - Generate Figure 3

### Utilities
- `Code/HA-Models/FromPandemicCode/FiscalTools.py` - Helper functions
- `Code/HA-Models/FromPandemicCode/Clean_Folders.py` - Cleanup utility

---

## Additional Documentation

- **Equation mapping**: See `README_IF_YOU_ARE_AN_AI/045_EQUATION_MAP.md`
- **Concept definitions**: See `README_IF_YOU_ARE_AN_AI/CONCEPT_GLOSSARY.md`
- **Computational workflows**: See `README_IF_YOU_ARE_AN_AI/030_COMPUTATIONAL_WORKFLOWS.md`
- **Code navigation**: See `README_IF_YOU_ARE_AN_AI/060_CODE_NAVIGATION.md`
- **Detailed Code README**: See `Code/HA-Models/README.md`
- **Code Directory Overview**: See `Code/README.md`

---

**For questions**: File an issue at <https://github.com/llorracc/HAFiscal-Latest/issues>
