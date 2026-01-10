# Code Navigation Guide for AI Systems

## Directory Structure Overview

```text
Code/
├── HA-Models/                      # Python heterogeneous agent models
│   ├── do_all.py                   # 🎯 MAIN ENTRY POINT
│   ├── reproduce_min.py            # Quick validation (~1 hour)
│   ├── README.md                   # Detailed documentation
│   │
│   ├── Target_AggMPCX_LiquWealth/  # Step 1: Splurge estimation
│   │   └── Estimation_BetaNablaSplurge.py
│   │
│   ├── FromPandemicCode/           # Steps 2-5: Main analysis
│   │   ├── EstimAggFiscalMAIN.py   # Step 2: Discount factors
│   │   ├── AggFiscalMAIN.py        # Step 5: Policy comparison
│   │   ├── HA-Fiscal-HANK-SAM.py   # Step 4: HANK Jacobians
│   │   └── ...
│   │
│   └── Results/                    # Output text files
│
└── Empirical/                      # Python empirical analysis
    ├── make_liquid_wealth.py       # SCF data processing
    ├── rscfp2004.dta               # SCF 2004 data
    └── download_scf_data.sh        # Data download script
```

---

## Key Entry Points

### Primary Entry Point

| File | Purpose | Usage |
|------|---------|-------|
| `Code/HA-Models/do_all.py` | Master pipeline controller | `python do_all.py` |

This script controls all 5 computational steps via boolean flags at the top of the file.

### Quick Validation

| File | Purpose | Runtime |
|------|---------|---------|
| `Code/HA-Models/reproduce_min.py` | Minimal validation run | See [timing estimates](../reproduce/benchmarks/README.md) |

Use this to verify the environment works before full replication.

---

## Step-by-Step File Map

### Step 1: Splurge Factor Estimation

| File | Purpose |
|------|---------|
| `Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py` | Main estimation script |
| `Target_AggMPCX_LiquWealth/SetupParamsCSTW.py` | Parameter configuration |

**Outputs**: Figure 1, splurge factor estimate (ς = 0.249)

### Step 2: Discount Factor Estimation

| File | Purpose |
|------|---------|
| `FromPandemicCode/EstimAggFiscalMAIN.py` | Main estimation driver |
| `FromPandemicCode/EstimAggFiscalModel.py` | `AggFiscalType` model class |
| `FromPandemicCode/EstimParameters.py` | Estimation parameters |
| `FromPandemicCode/EstimSetupEconomy.py` | Economy setup |
| `FromPandemicCode/CreateLPfig.py` | Generate Figure 2 |
| `FromPandemicCode/CreateIMPCfig.py` | Generate Figure 3 |

**Outputs**: Figures 2-3, discount factor distributions by education

### Step 4: HANK Model

| File | Purpose |
|------|---------|
| `FromPandemicCode/HA-Fiscal-HANK-SAM.py` | Compute household Jacobians |
| `FromPandemicCode/HA-Fiscal-HANK-SAM-to-python.py` | Run HANK experiments |

**Outputs**: Figure 5, Jacobian matrices for dashboard

### Step 5: Policy Comparison

| File | Purpose |
|------|---------|
| `FromPandemicCode/AggFiscalMAIN.py` | Main policy comparison |
| `FromPandemicCode/AggFiscalModel.py` | Policy simulation model |
| `FromPandemicCode/Welfare.py` | Welfare calculations |
| `FromPandemicCode/Output_Results.py` | Results formatting |

**Outputs**: Figure 4, Figure 6, Tables 6-8

---

## Core Model Classes

### `AggFiscalType` (EstimAggFiscalModel.py)

The main heterogeneous agent model class, extending HARK's `MarkovConsumerType`:

```python
class AggFiscalType(MarkovConsumerType):
    # Key methods:
    # - solve()           : Solve consumer's problem via EGM
    # - simulate()        : Monte Carlo simulation
    # - hitWithRecessionShock() : Apply recession/policy shocks
    # - saveState() / restoreState() : State management for counterfactuals
```

### Key Parameters (EstimParameters.py)

```python
# Calibrated values
CRRA = 2.0              # Risk aversion
Splurge = 0.249         # Splurge factor
Rfree = 1.01            # Quarterly interest rate
LivPrb = 1 - 1/160      # Survival probability
```

---

## Support Files

### Utilities

| File | Purpose |
|------|---------|
| `FromPandemicCode/FiscalTools.py` | Helper functions |
| `FromPandemicCode/OtherFunctions.py` | Additional utilities |
| `FromPandemicCode/Simulate.py` | Simulation routines |
| `FromPandemicCode/ConsMarkovModel.py` | Markov consumption model |

### Configuration

| File | Purpose |
|------|---------|
| `matplotlib_config.py` | Plot styling configuration |
| `logging_config.py` | Logging setup |

### Cleanup

| File | Purpose |
|------|---------|
| `FromPandemicCode/Clean_Folders.py` | Remove generated files |

---

## Output Locations

### Figures

| Location | Contents |
|----------|----------|
| `Target_AggMPCX_LiquWealth/Figures/` | Figure 1 (splurge estimation) |
| `FromPandemicCode/Figures/` | Figures 2-6 |

### Tables

| Location | Contents |
|----------|----------|
| `FromPandemicCode/Tables/CRRA2/` | Main results (baseline CRRA=2) |
| `FromPandemicCode/Tables/Splurge0/` | Robustness (no splurge) |
| `FromPandemicCode/Tables/*/` | Other robustness variants |

### Numerical Results

| Location | Contents |
|----------|----------|
| `Results/AllResults_CRRA_2.0_R_1.01.txt` | Baseline numerical results |
| `Results_HANK/` | HANK model outputs |

---

## Empirical Data Processing

### Stata Processing

```bash
# Run in Python:
python3 Code/Empirical/make_liquid_wealth.py
```

Produces calibration targets from SCF 2004 data.

### Python Data Scripts

| File | Purpose |
|------|---------|
| `make_liquid_wealth.py` | Primary SCF data processing script |
| `adjust_scf_inflation.py` | Inflation adjustments |
| `compare_scf_datasets.py` | Data validation |
| `download_scf_data.sh` | Download SCF data files |

---

## Dependencies

### HARK Library

The code extensively uses the [HARK library](https://github.com/econ-ark/HARK):

```python
from HARK.ConsumptionSaving.ConsMarkovModel import MarkovConsumerType
from HARK.ConsumptionSaving.ConsIndShockModel import ConsumerSolution
from HARK.distribution import DiscreteDistribution, Uniform
from HARK.interpolation import LinearInterp, BilinearInterp
```

### Other Key Dependencies

- `numpy` - Numerical computing
- `scipy` - Optimization (minimize)
- `matplotlib` - Plotting
- `pandas` - Data handling

---

## Quick Reference: "I want to..."

| Goal | Start Here |
|------|------------|
| Run everything | `python do_all.py` |
| Quick test | `python reproduce_min.py` |
| Just splurge estimation | `cd Target_AggMPCX_LiquWealth && python Estimation_BetaNablaSplurge.py` |
| Just policy comparison | `cd FromPandemicCode && python AggFiscalMAIN.py` |
| Understand the model class | Read `FromPandemicCode/EstimAggFiscalModel.py` |
| See parameter values | Read `FromPandemicCode/EstimParameters.py` |
| Process SCF data | Run `python3 Code/Empirical/make_liquid_wealth.py` |

---

## File Naming Conventions

- `*MAIN.py` - Main driver scripts
- `*Model.py` - Model class definitions
- `*Parameters.py` - Parameter configurations
- `Create*.py` - Figure/output generation
- `Estim*.py` - Estimation-related code
- `*_tabular_generate.py` - Table generation scripts

