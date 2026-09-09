# Paper Abstract and Key Claims

## Abstract

Using a heterogeneous agent model calibrated to match spending dynamics over four years following an income shock (Fagereng, Holm, and Natvik 2021), we assess the effectiveness of three fiscal stimulus policies implemented during recent recessions. Unemployment insurance (UI) extensions are the "bang for the buck" winner when the metric is effectiveness in boosting utility. Stimulus checks are second-best and have two advantages (over UI): they arrive faster, and are scalable. A temporary (two-year) cut in wage taxation is considerably less effective than the other policies and has negligible effects in the version of our model without a multiplier.

---

## Key Claims (Structured for AI Indexing)

### Claim 1: UI Extensions Have Highest Welfare Effectiveness

> **Statement**: Unemployment insurance extensions provide the highest welfare gain per dollar of government spending.

**Evidence**:

- Welfare gain (CEV): 0.010-0.012 per dollar spent
- Targets spending to those most affected by recession
- 81.1% of stimulus consumed during recession

**Location in Paper**: Section 4, Tables 6-7

---

### Claim 2: Stimulus Checks Are Second-Best but More Practical

> **Statement**: Direct stimulus checks are second in welfare effectiveness but offer practical advantages: faster delivery and scalability.

**Evidence**:

- Welfare gain (CEV): 0.000-0.002 per dollar spent
- 74.2% consumed during recession
- Can reach all households immediately

**Location in Paper**: Section 4, Tables 6-7

---

### Claim 3: Tax Cuts Are Least Effective

> **Statement**: Temporary payroll tax cuts are the least effective stimulus policy, with negligible welfare effects in the baseline model.

**Evidence**:

- Welfare gain (CEV): ~0.000 (near zero)
- Only 42.1% consumed during recession
- Multiplier of 0.847-0.978 (lowest among policies)

**Location in Paper**: Section 4, Tables 6-7

---

### Claim 4: Aggregate Demand Effects Matter

> **Statement**: Including aggregate demand feedback effects substantially increases the effectiveness of all policies.

**Evidence**:

- Stimulus check multiplier: 0.879 → 1.234 (with AD)
- UI extension multiplier: 0.906 → 1.211 (with AD)
- Tax cut multiplier: 0.847 → 0.978 (with AD)

**Location in Paper**: Section 5

---

### Claim 5: The "Splurge Factor" Captures Empirical MPC Patterns

> **Statement**: A "splurge" component (ς = 0.249) is necessary to match observed marginal propensity to consume patterns.

**Evidence**:

- Without splurge: model underpredicts immediate consumption response
- Splurge = 24.9% of income consumed immediately upon receipt
- Calibrated to Norwegian lottery data (Fagereng et al. 2021)

**Location in Paper**: Section 3

---

## Quantitative Results Summary

### Fiscal Multipliers (10-Year Horizon)

| Policy | Without AD | With AD | 1st Round AD |
|--------|------------|---------|--------------|
| Stimulus Check | 0.879 | 1.234 | 1.157 |
| UI Extension | 0.906 | 1.211 | 1.148 |
| Tax Cut | 0.847 | 0.978 | 0.951 |

### Welfare Gains (Consumption Equivalent Variation)

| Policy | Without AD | With AD |
|--------|------------|---------|
| Stimulus Check | 0.000 | 0.002 |
| UI Extension | 0.010 | 0.012 |
| Tax Cut | -0.000 | 0.000 |

### Timing of Stimulus

| Policy | Expenditure During Recession | Consumption During Recession |
|--------|------------------------------|------------------------------|
| Stimulus Check | 100.0% | 74.2% |
| UI Extension | 79.6% | 81.1% |
| Tax Cut | 57.8% | 42.1% |

---

## Model Parameters Summary

| Parameter | Symbol | Value | Source |
|-----------|--------|-------|--------|
| Splurge Factor | ς | 0.249 | Estimated (Section 3) |
| Risk Aversion | γ | 2.0 | Standard |
| Interest Rate | R | 1.01 (quarterly) | Calibration |
| Death Probability | D | 1/160 | Perpetual youth |
| UI Replacement Rate | ρ_b | 0.70 | BLS data |
| Non-UI Replacement Rate | ρ_nb | 0.50 | Calibration |

---

## Citation

Carroll, C. D., Crawley, E., Du, W., Frankovic, I., & Tretvoll, H. (2025). Welfare and Spending Effects of Consumption Stimulus Policies. *Quantitative Economics*.

**BibTeX**:

```bibtex
@article{carroll2025welfare,
  title={Welfare and Spending Effects of Consumption Stimulus Policies},
  author={Carroll, Christopher D. and Crawley, Edmund and Du, William and Frankovic, Ivan and Tretvoll, Hakon},
  journal={Quantitative Economics},
  year={2025}
}
```

---

## Keywords for Indexing

- Fiscal stimulus
- Heterogeneous agents
- HANK models
- Marginal propensity to consume (MPC)
- Unemployment insurance
- Stimulus checks
- Tax cuts
- Welfare analysis
- Aggregate demand
- Splurge consumption
- DSGE
- Computational economics

---

*This document provides structured claims for AI systems to index and reference.*

