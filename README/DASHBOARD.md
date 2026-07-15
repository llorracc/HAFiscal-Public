# Interactive Dashboard Guide

## What Is the Dashboard?

The HAFiscal Interactive Dashboard is a browser-based tool that lets you explore the paper's HANK-SAM model without running any code locally. It's designed for **policy researchers, central bank economists, and anyone who wants quick results**.

---

## Launch Options

### Option 1: MyBinder (Recommended for Quick Exploration)

[![Launch on MyBinder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/llorracc/HAFiscal-Public/HEAD?urlpath=voila%2Frender%2Fdashboard%2Fapp.ipynb)

**Pros**:

- No installation required
- Works in any modern browser
- Always uses latest version

**Cons**:

- May take 1-2 minutes to start (building environment)
- Session expires after ~10 minutes of inactivity
- Slower than local installation

### Option 2: Local Installation (Recommended for Extended Use)

```bash
# From repository root
cd dashboard
./start-dashboard.sh
```

Or manually:

```bash
cd dashboard
voila app.ipynb
```

See [dashboard/DASHBOARD_README.md](../dashboard/DASHBOARD_README.md) for detailed setup instructions.

---

## What Can You Do?

| Feature | Description |
|---------|-------------|
| **Policy Comparison** | Compare stimulus checks, UI extensions, tax cuts side-by-side |
| **Parameter Adjustment** | Modify Taylor rule coefficient, policy size, duration |
| **Monetary Regimes** | Standard Taylor rule, fixed nominal rate, fixed real rate |
| **Visualizations** | Fiscal multipliers over 20 quarters, consumption impulse responses |

---

## Dashboard Controls

### Adjustable Parameters

| Parameter | Range | Default | What It Does |
|-----------|-------|---------|--------------|
| Taylor Rule Coefficient | 0–3.0 | 1.5 | How aggressively monetary policy responds to inflation |
| Fiscal Policy Size | 0–2% GDP | 1% | Magnitude of stimulus as share of GDP |
| Policy Duration | 1–8 quarters | 4 | How long the policy lasts |

### Policy Scenarios

1. **Standard Taylor Rule**: Central bank responds normally to inflation
2. **Fixed Nominal Rate**: Zero lower bound scenario (constrained monetary policy)
3. **Fixed Real Rate**: Alternative monetary stance

---

## Connection to Paper Results

Dashboard results correspond to **Section 5** (HANK Robustness) and **Table 8** in the paper.

### Expected Results with Default Parameters

| Policy | Multiplier (Taylor Rule) | Multiplier (Fixed Rate) |
|--------|--------------------------|-------------------------|
| UI Extension | ~1.2 | ~1.5 |
| Stimulus Check | ~1.2 | ~1.5 |
| Tax Cut | ~1.0 | ~1.2 |

If your results differ significantly, check:

1. Parameter settings match defaults
2. MyBinder environment loaded correctly
3. Try refreshing and restarting

---

## For Deeper Analysis

After exploring the dashboard, you may want to:

1. **Understand the math**: Read [Model Summary](../README_IF_YOU_ARE_AN_AI/035_MODEL_SUMMARY.md)
2. **See all results**: Review the [paper PDF](../HAFiscal.pdf)
3. **Run full replication**: Follow [REPLICATION.md](REPLICATION.md)
4. **Explore the code**: Start with [Code Navigation](../README_IF_YOU_ARE_AN_AI/060_CODE_NAVIGATION.md)

---

## Technical Details

### Files

| File | Purpose |
|------|---------|
| `dashboard/app.ipynb` | Main Voila dashboard notebook |
| `dashboard/app.py` | Python script version (jupytext sync) |
| `dashboard/hank_sam.py` | Core HANK-SAM model implementation |
| `dashboard/hafiscal.py` | HAFiscal model wrapper |
| `dashboard/plotting_functions.py` | Visualization utilities |

### Dependencies

- Python 3.11+
- Voila (for web deployment)
- ipywidgets (for interactivity)
- HARK library (heterogeneous agent toolkit)

All dependencies are specified in `dashboard/environment.yml`.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| MyBinder won't start | Wait 2-3 minutes; try a different browser |
| Widgets not displaying | Refresh the page; clear browser cache |
| Results look wrong | Check parameter values; compare to paper Table 8 |
| Session expired | Click the MyBinder badge again to restart |

For more issues, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Related Documentation

- [Full Dashboard Documentation](../dashboard/DASHBOARD_README.md) — Complete technical guide
- [Computational Workflows](../README_IF_YOU_ARE_AN_AI/030_COMPUTATIONAL_WORKFLOWS.md) — Full pipeline details
- [Interactive Dashboard (AI Guide)](../README_IF_YOU_ARE_AN_AI/070_INTERACTIVE_DASHBOARD.md) — AI-specific documentation

---

*This dashboard makes fiscal policy research accessible without requiring computational expertise.*

