# HAFiscal Code Architecture

**Purpose**: Understand the organization and flow of code in this repository
(human-facing navigation entry point; `CLAUDE.md` is the AI-facing counterpart)  
**Last Updated**: 2026-06-11  
**Last verified:** 2026-06-11 (directory tree and entry points checked against the working tree)

> Pipeline **detail** (per-step scripts, runtimes, outputs, table/figure
> provenance) is owned by **[`Code/HA-Models/README.md`](Code/HA-Models/README.md)** —
> this document gives the high-level map and points there.

---

## High-Level Architecture

```
Data Sources → Data Processing → Model Estimation → Policy Analysis  → Output Generation
    ↓               ↓                  ↓                 ↓                  ↓
  SCF 2004    make_liquid_    EstimAggFiscalMAIN   AggFiscalMAIN     Output_Results.py
              _wealth.py         .py               _reduced.py (5a)   Welfare.py
                                                   run_welfare6_
                                                   parallel.py (5b)
```

---

## Directory Structure

```
HAFiscal-Latest/                   # (selected entries)
├── Code/                          # All computational code
│   ├── Empirical/                 # Data processing
│   │   ├── make_liquid_wealth.py  # Construct liquid wealth measure
│   │   ├── adjust_scf_inflation.py # Inflation adjustments
│   │   ├── compare_scf_datasets.py # Dataset comparisons
│   │   ├── download_scf_data.sh   # Download SCF data
│   │   └── *.dta, *.csv          # Data files
│   └── HA-Models/                 # Heterogeneous agent models
│       ├── do_all.py              # Main pipeline orchestrator (5 steps)
│       ├── do_all_reduced.py      # Reduced-scale pipeline for fast validation
│       ├── reproduce_min.py       # Minimal validation script
│       ├── Results/               # Estimation results (text files)
│       ├── Results_canonical/     # Canonical/pinned results snapshots
│       ├── solution_cache/        # Opt-in AD-solve cache (gitignored contents)
│       ├── jax_mc_speedup/        # JAX MC acceleration kernels + tests
│       ├── jax_tm_mult/           # JAX TM multiplier experiments
│       ├── dolo_plus_validation/  # Dolo-plus YAML model validation
│       ├── experiments/, scripts/ # Diagnostics and helper scripts
│       ├── diagnostics_archive/, hark_migration_archive/,
│       │   welfare6_diagnostics_archive/   # Archived diagnostics (historical)
│       ├── Target_AggMPCX_LiquWealth/  # Step 1: Splurge estimation
│       │   └── Estimation_BetaNablaSplurge.py
│       └── FromPandemicCode/      # Steps 2-5: Main analysis
│           ├── EstimAggFiscalMAIN.py     # Step 2: Estimation
│           ├── AggFiscalMAIN_reduced.py  # Step 5a: TM multipliers
│           │                             #   (AggFiscalMAIN.py retired 2026-04, c7e566d9)
│           ├── run_welfare6_parallel.py  # Step 5b: MC welfare-6 (parallel driver)
│           ├── AggFiscalModel.py         # Model classes
│           ├── Simulate.py               # Simulation
│           ├── tm_methods.py             # Transition-matrix methods
│           ├── Output_Results.py         # Generate figures/tables
│           ├── Welfare.py                # Welfare calculations
│           ├── Parameters.py             # Model parameters
│           ├── EstimParameters.py        # Estimation parameters
│           ├── Figures/                  # Generated figures (per parametrization)
│           └── Tables/                   # Generated tables (per parametrization)
├── Figures/                       # Figure LaTeX files (*.tex, *.pdf)
├── Tables/                        # Table LaTeX files (*.tex, *.pdf)
├── Subfiles/                      # LaTeX paper sections
├── HAFiscal.tex                   # Main LaTeX document
├── reproduce.sh                   # Main entry point for all operations
├── reproduce/                     # Reproduction scripts, env setup, benchmarks
├── docs/                          # Technical documentation
├── plans/                         # Working plans (see plans/INDEX.md)
├── history/                       # Dated session/decision history
├── README_IF_YOU_ARE_AN_AI/       # AI-oriented repo guides
├── pyproject.toml                 # Python dependencies (uv; authoritative)
├── environment.yml                # Conda environment specification (legacy alternative)
└── README/                        # Extended documentation
```

---

## Core Computational Pipeline

The computational workflow is orchestrated by `Code/HA-Models/do_all.py` and
consists of 5 sequential steps. Steps are toggled via environment variables
`HAFISCAL_RUN_STEP_{1,2,3,4,5}` (defaults: 1, 2, 4, 5 on; 3 off) and
`HAFISCAL_RUN_STEP_5B` (the welfare phase of Step 5).

**Per-step detail — scripts, runtimes (with dated claims), outputs, and the
paper table/figure provenance mapping — lives in
[`Code/HA-Models/README.md`](Code/HA-Models/README.md) (authoritative).**

| Step | What | Main script(s) | Key outputs |
|------|------|----------------|-------------|
| 1 | Splurge factor estimation (sec. 3.1) | `Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py` | Figure 1, Table 1, `Result_AllTarget*.txt` |
| 2 | Discount factor distributions, 3 education groups (sec. 3.3.3) | `FromPandemicCode/EstimAggFiscalMAIN.py` + `CreateLPfig.py`, `CreateIMPCfig.py`, tabular generators | Figures 2-3, `Results/AllResults_*.txt` |
| 3 | Splurge=0 robustness (Online Appendix; **off by default**) | `EstimAggFiscalMAIN.py 1.01 2.0 0.7 0.5 0` | `AllResults_*_Splurge0.txt` |
| 4 | HANK-SAM robustness (sec. 5) | `HA-Fiscal-HANK-SAM.py`, `HA-Fiscal-HANK-SAM-to-python.py` | Figure 5, Jacobian `.obj` files |
| 5 | Policy comparison (sec. 4), two phases | 5a: `AggFiscalMAIN_reduced.py --baseline` (TM multipliers, a-indexed); 5b: `run_welfare6_parallel.py --baseline` (MC welfare-6). Old `AggFiscalMAIN.py` retired 2026-04 (c7e566d9) | Figures 4 & 6, Tables 6-8 |

Data flow: SCF 2004 → `Code/Empirical/make_liquid_wealth.py` (calibration
targets) → Step 1 → Step 2 (→ Step 3 robustness) → Step 5; Step 4's HANK-SAM
results feed Figure 6 in Step 5 (hence Step 4 runs first).

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
  ├→ AggFiscalMAIN_reduced.py (Step 5a; old AggFiscalMAIN.py retired 2026-04)
  │    ↓
  │    ├→ Simulate.py / tm_methods.py
  │    └→ Output_Results.py → Figure 4, Table 6, Figure 6
  │
  ├→ run_welfare6_parallel.py (Step 5b)
  │    ↓
  │    └→ Welfare.py → Table 7
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

Flags (see ./reproduce.sh --help for the full, current list):
  --envt, -e          Test environment setup (TeX Live + Python/computational)
  --docs, -d [SCOPE]  Reproduce LaTeX documents (main|all|figures|tables|subfiles)
  --comp, -c [SCOPE]  Reproduce computational results
                      (nano|micro|mini|min|TM-and-MC|full|max; default: min)
  --data [SCOPE]      Reproduce empirical data or figures from results
```

**What it does**:
```
--envt:  Install dependencies → Verify setup
--docs:  Run LaTeX compiler → Generate PDF
--comp:  Calls Code/HA-Models/do_all.py (or reduced variants) with configured steps
```

### Secondary Entry Point: `Code/HA-Models/do_all.py`

```python
# Run all steps (4-5 days)
cd Code/HA-Models
python do_all.py

# Or run minimal validation (~1 hour)
python reproduce_min.py
```

**Direct script execution** (individual steps; details in `Code/HA-Models/README.md`):

```bash
# Step 1: Splurge estimation
cd Code/HA-Models/Target_AggMPCX_LiquWealth
python Estimation_BetaNablaSplurge.py

# Step 2: Estimation
cd Code/HA-Models/FromPandemicCode
python EstimAggFiscalMAIN.py

# Step 5a: TM multipliers (old AggFiscalMAIN.py entry point retired 2026-04)
cd Code/HA-Models/FromPandemicCode
HAFISCAL_TM_A_INDEXED=1 python AggFiscalMAIN_reduced.py --baseline

# Step 5b: MC welfare-6
python run_welfare6_parallel.py --baseline --table-dir Tables/Baseline
```

---

## Computational Bottlenecks

Authoritative, dated runtime claims per step: see the **Running Time
Estimates** table in [`Code/HA-Models/README.md`](Code/HA-Models/README.md).
Structurally:

| Stage | Parallelizable? | Bottleneck |
|-------|-----------------|------------|
| Step 1: Splurge estimation | No | Single optimization |
| Step 2: Estimation | Partial | Education groups (can parallelize) |
| Step 3: Robustness (optional) | Partial | Similar to Step 2 |
| Step 4: HANK-SAM | Partial | Jacobian computation |
| Step 5a: TM multipliers | Partial (forked-AD ≈2.4×) | a-indexed transition matrix |
| Step 5b: MC welfare-6 | Yes (parallel driver, ~6× wall) | MC scenario simulation |

Full pipeline is on the order of **4-5 days** end-to-end (longest poles:
Steps 2 and 5a).

**Parallelization opportunities** (some already wired in):
- Step 2: Run education groups in parallel
- Step 5a: forked-AD parallelism (measured 2.4×, 2026-06)
- Step 5b: `run_welfare6_parallel.py` auto-budgeted workers (~6 h → ~1 h)

---

## External Dependencies

### Python Packages (from pyproject.toml — authoritative; environment.yml is the legacy conda alternative)

**Core**:
- `econ-ark` (HARK) **0.17.x**, pinned via `[tool.uv.sources]` (git ref or local
  editable checkout depending on branch); Python **3.10/3.11** only
- `numpy >= 1.24, < 2`: Numerical computing (numpy 2.x not supported)
- `scipy`: Optimization, statistics
- `pandas`: Data manipulation

**Visualization**:
- `matplotlib >= 3.7`: Plotting
- `seaborn >= 0.12`: Statistical visualization (`analysis` dependency group)

**Other**:
- `numba >= 0.57`: JIT compilation (constrains Python to 3.10/3.11)
- `sequence-jacobian == 1.0.0`: For HANK-SAM models (Step 4)
- Optional groups in `pyproject.toml`: `jupyter`, `analysis`, `dev`, `jax`
  (JAX acceleration, CPU pin `<0.10` for numpy<2 compatibility)

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
# Step 1 only (steps are env-toggled; no need to edit do_all.py)
cd Code/HA-Models
HAFISCAL_RUN_STEP_2=false HAFISCAL_RUN_STEP_4=false HAFISCAL_RUN_STEP_5=false \
  python do_all.py

# Step 5 only (requires Steps 1-2 completed first)
cd Code/HA-Models/FromPandemicCode
HAFISCAL_TM_A_INDEXED=1 python AggFiscalMAIN_reduced.py --baseline   # 5a
python run_welfare6_parallel.py --baseline --table-dir Tables/Baseline  # 5b
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
HAFISCAL_TM_A_INDEXED=1 python AggFiscalMAIN_reduced.py --baseline  # If policy params changed
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
- `Code/HA-Models/FromPandemicCode/AggFiscalMAIN_reduced.py` - TM multipliers (Step 5a; old `AggFiscalMAIN.py` retired 2026-04)
- `Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py` - MC welfare-6 (Step 5b)
- `Code/HA-Models/FromPandemicCode/Simulate.py` - Simulation utilities
- `Code/HA-Models/FromPandemicCode/tm_methods.py` - Transition-matrix methods
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
