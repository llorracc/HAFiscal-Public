# HAFiscal Code Architecture

**Purpose**: Understand the organization and flow of code in this repository  
**Last Updated**: 2025-12-17

---

## High-Level Architecture

```
Data Sources → Data Processing → Model Solution → Policy Analysis → Output Generation
    ↓               ↓                  ↓                ↓                ↓
  SCF, NIPA    DataRead.py      ConsumerModel.py  PolicyCompute.py  Output_Results.py
                                                                           ↓
                                                                  Figures/ + Tables/
```

---

## Directory Structure

```
HAFiscal-Latest/
├── Code/                      # All computational code
│   ├── Empirical/             # Data analysis and policy computations
│   ├── HA-Models/             # Heterogeneous agent models
│   ├── Calibration/           # Parameter calibration
│   └── Tools/                 # Utility functions
├── Figures/                   # Generated figures (PDF, PNG)
├── Tables/                    # Generated tables (LaTeX, CSV)
├── Subfiles/                  # LaTeX paper sections
├── HAFiscal.tex              # Main LaTeX document
├── reproduce.sh              # Main entry point for all operations
├── environment.yml           # Conda environment specification
└── README/                    # Extended documentation
```

---

## Core Data Pipeline

### Stage 1: Data Acquisition and Processing

```
Federal Reserve SCF Data
         ↓
    [Download]
         ↓
Code/Empirical/DataRead.py
    - Load SCF microdata
    - Clean and process
    - Apply CPI adjustments (2022$ → 2013$)
    - Create derived variables
         ↓
Processed Data (rscfp2004.dta)
         ↓
Code/Empirical/DataSummary.py
    - Compute wealth distribution moments
    - Calculate income statistics
    - Generate descriptive statistics
         ↓
Calibration Targets (saved as .pkl)
```

**Key Files**:
- `Code/Empirical/DataRead.py` (~300 lines)
- `Code/Empirical/DataSummary.py` (~200 lines)
- Output: `Data/rscfp2004.dta`, `Calibration/targets.pkl`

**Dependencies**: pandas, numpy, pyreadstat

---

### Stage 2: Model Calibration

```
Calibration Targets
         ↓
Code/Calibration/baseline_params.py
    - Set initial parameter guesses
    - Define parameter bounds
         ↓
Code/Calibration/calibrate_model.py
    - Run optimization to match moments
    - Iterate: solve model → simulate → compute moments → update params
         ↓
Calibrated Parameters (baseline_params.pkl)
         ↓
Code/Calibration/validation.py
    - Verify model matches all target moments
    - Generate validation tables
         ↓
Tables/calibration_fit.tex
```

**Key Files**:
- `Code/Calibration/baseline_params.py` (~150 lines)
- `Code/Calibration/calibrate_model.py` (~400 lines)
- `Code/Calibration/validation.py` (~250 lines)

**Dependencies**: HARK, scipy.optimize

**Runtime**: ~8 hours (on 8-core machine)

---

### Stage 3: Model Solution

```
Calibrated Parameters
         ↓
Code/HA-Models/ConsumerModel.py
    - Define HARK consumer type
    - Set up income process
    - Configure state space
         ↓
Solve Household Problem
    - Backward induction (EGM)
    - Store consumption policy functions
         ↓
Code/HA-Models/Simulate.py
    - Monte Carlo simulation
    - 10,000 households × 400 quarters
    - Track: consumption, wealth, MPC
         ↓
Simulated Distributions (baseline_sim.pkl)
```

**Key Files**:
- `Code/HA-Models/ConsumerModel.py` (~350 lines)
- `Code/HA-Models/Simulate.py` (~300 lines)

**Dependencies**: HARK, numpy

**Runtime**: ~30 seconds per solve + simulate cycle

---

### Stage 4: Policy Analysis

```
Baseline Simulation
         ↓
    Policy Intervention (choose one):
    ├── Stimulus Check
    ├── UI Extension
    └── Tax Cut
         ↓
Code/Empirical/{Policy}Compute.py
    - Modify income or transfer
    - Re-simulate consumption
    - Compute consumption difference (∆C)
         ↓
Code/Empirical/MultiplierCalc.py
    - Calculate fiscal multiplier
    - Compute iMPC path
         ↓
Code/Tools/Welfare.py
    - Calculate welfare changes
    - By wealth percentile
         ↓
Results (policy_results.pkl)
```

**Policy-Specific Files**:
1. `Code/Empirical/StimulusCheckCompute.py` (~400 lines)
2. `Code/Empirical/UICompute.py` (~350 lines)
3. `Code/Empirical/TaxCutCompute.py` (~450 lines)

**Common Files**:
- `Code/Empirical/MultiplierCalc.py` (~200 lines)
- `Code/Tools/Welfare.py` (~180 lines)

**Runtime**: ~10 hours per policy (full sensitivity analysis)

---

### Stage 5: Output Generation

```
Policy Results
         ↓
Code/Empirical/Output_Results.py
    - Load all policy results
    - Generate figures (matplotlib)
    - Generate tables (LaTeX)
         ↓
    Figures/               Tables/
    ├── Figure1.pdf        ├── Table1.tex
    ├── Figure2.pdf        ├── Table2.tex
    ├── Figure3.pdf        ├── Table3.tex
    └── ...                └── ...
         ↓
LaTeX Compilation (reproduce.sh --docs)
         ↓
HAFiscal.pdf
```

**Key Files**:
- `Code/Empirical/Output_Results.py` (~600 lines)
- `Code/Tools/Plotting.py` (~400 lines, plotting utilities)

**Dependencies**: matplotlib, seaborn, pandas

**Runtime**: ~2-3 minutes

---

## Module Dependency Graph

```
HARK (external)
  ↓
ConsumerModel.py
  ↓
  ├→ Simulate.py
  │    ↓
  │    ├→ StimulusCheckCompute.py ──┐
  │    ├→ UICompute.py ──────────────┤
  │    └→ TaxCutCompute.py ──────────┤
  │                                  ↓
  └→ Calibration/                MultiplierCalc.py
       calibrate_model.py            ↓
            ↓                    Welfare.py
       validation.py                 ↓
                               Output_Results.py
                                     ↓
                               Figures/ + Tables/
```

---

## Key Function Call Hierarchy

### Solving the Model

```
main()
  └─> load_baseline_params()
      └─> create_consumer_type(params)
          └─> solve()                      [HARK library]
              ├─> prepare()
              ├─> solve_one_period()       [Endogenous Grid Method]
              │   ├─> calc_EndOfPrd_vP()
              │   ├─> calc_mNrm()
              │   └─> make_cFunc()
              └─> add_to_time_inv()
```

### Policy Analysis

```
compute_stimulus_check_effects()
  ├─> load_calibrated_model()
  │   └─> solve()
  ├─> simulate_baseline()
  │   └─> initialize_sim()
  │       └─> simulate(T_sim)             [HARK library]
  ├─> simulate_policy(shock_amount)
  │   ├─> modify_income_process()
  │   └─> simulate(T_sim)
  ├─> compute_consumption_diff()
  └─> compute_fiscal_multiplier()
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
--comp:  Data → Calibrate → Solve → Policies → Output
```

### Secondary Entry Points (Direct Python)

```python
# Calibrate model
python Code/Calibration/calibrate_model.py

# Run single policy
python Code/Empirical/StimulusCheckCompute.py

# Generate figures/tables
python Code/Empirical/Output_Results.py
```

---

## Computational Bottlenecks

| Stage | Runtime | Parallelizable? | Bottleneck |
|-------|---------|-----------------|------------|
| Data processing | 2 min | No | I/O |
| Calibration | 8 hours | Partial | Optimization loop |
| Model solution | 30 sec | Yes | Numerical solver |
| Policy simulation | 10 hours | Yes | Monte Carlo |
| Figure generation | 2 min | Yes | Plotting |

**Parallelization opportunities**:
- Calibration: Parallel evaluation of objective function
- Policy simulation: Run policies independently
- Robustness checks: Full parallel (40 scenarios)

---

## External Dependencies

### Python Packages (from environment.yml)

**Core**:
- `HARK >= 0.13.0`: Heterogeneous agent toolkit
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
- `dill`: Serialization (for saving results)

### LaTeX Packages (from reproduce/required_latex_packages.txt)

Key packages: `econark`, `subfiles`, `hyperref`, `booktabs`, `graphicx`, `amsmath`, `natbib`

---

## File Size Reference

| Directory | Typical Size | Notes |
|-----------|-------------|-------|
| Code/ | ~2 MB | Python scripts |
| Data/ | ~50 MB | SCF microdata (not in repo) |
| Figures/ | ~20 MB | Generated PDFs |
| Tables/ | ~1 MB | LaTeX tables |
| Results/ | ~500 MB | Intermediate .pkl files (not in repo) |
| .venv-{platform}/ | ~1 GB | Python environment (not in repo) |

---

## Testing & Validation

### Quick Verification (`--comp min`)

```
Test 1: Data loading
  → Load SCF data
  → Verify key moments match targets
  Runtime: 30 seconds

Test 2: Model solution
  → Solve baseline model
  → Check consumption function shape
  Runtime: 30 seconds

Test 3: Policy simulation
  → Run one policy scenario (stimulus check)
  → Verify multiplier in reasonable range (0.5-2.0)
  Runtime: 10 minutes

Test 4: Output generation
  → Generate Figure 1 (iMPC plot)
  → Generate Table 1 (calibration targets)
  Runtime: 1 minute

Total: ~15 minutes
```

### Full Validation (`--comp full`)

- All 40 robustness scenarios
- All figures (1-7) and tables (1-8)
- Welfare analysis by percentile
- Sensitivity to key parameters

**Runtime**: 4-5 days

---

## Common Workflows

### Workflow 1: Quick Verification

```bash
./reproduce.sh --envt           # 10 min
./reproduce.sh --docs           # 1 min
./reproduce.sh --comp min       # 15 min
# Total: ~30 minutes
```

### Workflow 2: Extend Model

```python
# 1. Modify model
vim Code/HA-Models/ConsumerModel.py

# 2. Test solution
python Code/HA-Models/ConsumerModel.py

# 3. Run policy analysis
python Code/Empirical/StimulusCheckCompute.py

# 4. Regenerate outputs
python Code/Empirical/Output_Results.py
```

### Workflow 3: Add New Policy

```python
# 1. Copy template
cp Code/Empirical/StimulusCheckCompute.py Code/Empirical/NewPolicyCompute.py

# 2. Modify policy intervention
vim Code/Empirical/NewPolicyCompute.py
# Change how income/transfers are modified

# 3. Add to output script
vim Code/Empirical/Output_Results.py
# Add new policy to comparison tables/figures

# 4. Run analysis
python Code/Empirical/NewPolicyCompute.py
python Code/Empirical/Output_Results.py
```

---

## Debugging Tips

### Model Won't Solve

```python
# Check parameters in reasonable range
from Code.Calibration.baseline_params import params
print(params['CRRA'])      # Should be 1-10
print(params['DiscFac'])   # Should be 0.90-0.99
print(params['Rfree'])     # Should be 1.00-1.05

# Verify grid specifications
print(params['aXtraGrid'])  # Should span [0, 50+]
print(len(params['TranShkGrid']))  # Should have 7+ points
```

### Calibration Not Converging

```python
# Check objective function values
from Code.Calibration.calibrate_model import objective_function
obj_value = objective_function(initial_params)
# Should be < 1.0 for decent fit, < 0.1 for good fit

# Try tighter bounds
# Edit: Code/Calibration/calibrate_model.py
# Reduce parameter search ranges
```

### Simulation Crashes

```bash
# Check for NaN/Inf in results
python -c "from Code.HA_Models.Simulate import *; check_simulation_validity()"

# Reduce simulation length if memory issues
# Edit T_sim from 400 → 100 in Simulate.py
```

---

## Performance Optimization

### Parallelization

```python
# Use joblib for parallel policy runs
from joblib import Parallel, delayed

policies = ['stimulus', 'UI', 'taxcut']
results = Parallel(n_jobs=3)(
    delayed(run_policy)(p) for p in policies
)
```

### Caching

```python
# HARK models cache solution
agent.solve()  # First time: slow
agent.solve()  # Subsequent: instant (uses cache)

# Save solved model
import dill
with open('solved_model.pkl', 'wb') as f:
    dill.dump(agent, f)
```

---

## Additional Documentation

- **Equation mapping**: See `README_IF_YOU_ARE_AN_AI/045_EQUATION_MAP.md`
- **Concept definitions**: See `README_IF_YOU_ARE_AN_AI/CONCEPT_GLOSSARY.md`
- **Computational workflows**: See `README_IF_YOU_ARE_AN_AI/030_COMPUTATIONAL_WORKFLOWS.md`
- **Code navigation**: See `README_IF_YOU_ARE_AN_AI/060_CODE_NAVIGATION.md`

---

**For questions**: File an issue at <https://github.com/llorracc/HAFiscal-Latest/issues>
