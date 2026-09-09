# Interactive Dashboard Guide for AI Systems

## Overview

The HAFiscal project includes an **interactive dashboard** for exploring the HANK-SAM model's fiscal multipliers under different policy parameters. This guide helps AI systems understand how to use and reference the dashboard.

---

## Dashboard Files

| File | Purpose | Location |
|------|---------|----------|
| `HANK-and-SAM-tutorial.ipynb` | Educational notebook demonstrating HANK-SAM model | Repository root |
| `dashboard/app.ipynb` | Interactive Voila dashboard with sliders/widgets | `dashboard/` |
| `dashboard/app.py` | Python script version | `dashboard/` |
| `dashboard/hank_sam.py` | Core HANK-SAM model | `dashboard/` |
| `dashboard/hafiscal.py` | HAFiscal model wrapper | `dashboard/` |
| `dashboard/DASHBOARD_README.md` | Full documentation | `dashboard/` |

---

## Quick Access Methods

### Method 1: MyBinder (No Installation Required)

The repository is configured for MyBinder deployment. AI systems can direct users to:

```text
https://mybinder.org/v2/gh/llorracc/HAFiscal-Latest/HEAD?urlpath=voila%2Frender%2Fdashboard%2Fapp.ipynb
```

### Method 2: Local Execution

```bash
# From repository root
cd dashboard
voila app.ipynb
```

### Method 3: JupyterLab (Educational Notebook)

```bash
jupyter lab HANK-and-SAM-tutorial.ipynb
```

---

## Dashboard Capabilities

### Adjustable Parameters

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| Taylor Rule Coefficient | 0-3.0 | 1.5 | Monetary policy responsiveness |
| Fiscal Policy Size | 0-2% GDP | 1% | Stimulus magnitude |
| Policy Duration | 1-8 quarters | 4 | How long policy lasts |

### Policy Scenarios

1. **Standard Taylor Rule**: Normal monetary policy response
2. **Fixed Nominal Rate**: Zero lower bound scenario
3. **Fixed Real Rate**: Alternative monetary stance

### Output Visualizations

- **Fiscal multipliers** over 20 quarters
- **Consumption impulse responses** by policy type
- **Parameter summary** display

---

## Dashboard for AI Analysis

### Use Cases

1. **Sensitivity Analysis**: Vary parameters to understand model behavior
2. **Policy Comparison**: Visualize differences between UI, checks, tax cuts
3. **Monetary-Fiscal Interaction**: Explore how monetary policy affects fiscal multipliers
4. **Validation**: Compare dashboard outputs to paper results

### Programmatic Access

For AI systems needing programmatic access to the model:

```python
# Import the core model directly
import sys
sys.path.append('dashboard')
from hank_sam import HANKSAMModel

# Initialize and run
model = HANKSAMModel()
results = model.compute_multipliers(
    taylor_coefficient=1.5,
    fiscal_size=0.01,
    policy_duration=4
)
```

---

## Key HANK-SAM Model Details

The dashboard implements the **Heterogeneous Agent New Keynesian - Sequence Space Jacobian** (HANK-SAM) model from Section 5 of the paper.

### Model Components

- **Household Block**: Consumption-saving decisions with heterogeneous agents
- **Jacobian Matrices**: Pre-computed from `Code/HA-Models/FromPandemicCode/HA-Fiscal-HANK-SAM.py`
- **General Equilibrium**: Aggregate demand feedback effects

### Connection to Main Results

Dashboard results should match Table 8 in the paper when using baseline parameters:

| Policy | Multiplier (Taylor Rule) | Multiplier (Fixed Rate) |
|--------|--------------------------|-------------------------|
| UI Extension | ~1.2 | ~1.5 |
| Stimulus Check | ~1.2 | ~1.5 |
| Tax Cut | ~1.0 | ~1.2 |

---

## Dependencies

The dashboard requires:

- Python 3.11+
- `voila` (for web deployment)
- `ipywidgets` (for interactivity)
- `numpy`, `scipy`, `matplotlib`
- HARK library

All dependencies are specified in `dashboard/environment.yml`.

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Widgets not displaying | Run `jupyter nbextension enable --py widgetsnbextension` |
| Import errors | Ensure `dashboard/` is in Python path |
| Slow loading | Pre-computed Jacobians should load in ~5 seconds |

### Validation Checks

1. Multipliers should be positive for all policies
2. Fixed rate multipliers > Taylor rule multipliers
3. UI and check multipliers should be similar

---

## References

- **Full documentation**: `dashboard/DASHBOARD_README.md`
- **Model implementation**: `dashboard/hank_sam.py`
- **Paper Section 5**: HANK robustness analysis
- **Jacobian computation**: `Code/HA-Models/FromPandemicCode/HA-Fiscal-HANK-SAM.py`

---

*This guide enables AI systems to reference and utilize the interactive dashboard capabilities.*

