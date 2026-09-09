# Concept Glossary for AI Understanding

**Purpose**: Define key concepts, theories, and methods for AI systems to understand the HAFiscal research

**Last Updated**: 2025-12-17

---

## Economic Theories & Models

### Buffer Stock Model
- **Type**: Economic theory
- **Domain**: Household consumption-saving behavior
- **Key Feature**: Precautionary saving under income uncertainty
- **Originated**: Carroll (1997) "Buffer-Stock Saving and the Life Cycle/Permanent Income Hypothesis"
- **Implementation**: `Code/HA-Models/` directory
- **Core Equation**: V(m,θ) = max[u(c) + βE[V(m',θ')]]
- **Intuition**: Households maintain a "buffer stock" of savings as insurance against income shocks

### HANK (Heterogeneous Agent New Keynesian)
- **Type**: Macroeconomic modeling framework
- **Definition**: Combines heterogeneous agent models with New Keynesian features (sticky prices, monetary policy)
- **Key Innovation**: Incorporates realistic household heterogeneity into macro models
- **Contrast with RANK**: Representative Agent NK models assume identical households
- **Implementation**: `Code/HA-Models/FromPandemicCode/`
- **Key Papers**: Kaplan & Violante (2014), Auclert et al. (2021)

### Two-Asset Model
- **Type**: Household portfolio choice framework
- **Definition**: Households hold liquid assets (checking) and illiquid assets (housing, retirement)
- **Key Insight**: Explains high MPCs despite substantial wealth
- **Implementation**: HARK's TwoAssetConsumerType
- **Originated**: Kaplan & Violante (2014) "A Model of the Consumption Response to Fiscal Stimulus Payments"

---

## Key Economic Concepts

### Marginal Propensity to Consume (MPC)
- **Definition**: Additional consumption per dollar of additional income
- **Formula**: ∂C/∂Y or ΔC/ΔY
- **Typical Range**: 0.05 to 0.95 (highly heterogeneous across households)
- **Empirical Evidence**: Parker et al. (2013) find MPC ~0.50-0.90 for stimulus checks
- **Code Location**: `Code/HA-Models/FromPandemicCode/AggFiscalMAIN.py` (MPC computed in policy analysis)
- **Paper Reference**: Table 2, Figure 3
- **Why It Matters**: High MPCs among low-wealth households amplify fiscal stimulus effects

### Intertemporal MPC (iMPC)
- **Definition**: MPC as a function of time since income shock
- **Formula**: MPC_t = ∂C_t/∂Y_0 (consumption at time t due to income shock at time 0)
- **Key Feature**: Decays over time as consumption smoothing occurs
- **Calibration Target**: Fagereng et al. (2021) Norwegian data
- **Code Location**: `Code/Empirical/iMPC_analysis.py`
- **Paper Reference**: Figure 2

### Fiscal Multiplier
- **Definition**: Change in GDP per dollar of government spending
- **Formula**: Multiplier = ΔY/ΔG
- **Typical Range**: 0.5 to 2.0 depending on policy design and economic conditions
- **Three Policies Compared**:
  1. Stimulus checks: ~1.2-1.5
  2. UI extensions: ~1.2-1.5
  3. Tax cuts: ~0.8-1.0
- **Paper Reference**: Table 8, Section 5.2

### Welfare Measure
- **Type**: Consumption-equivalent variation
- **Definition**: Percentage increase in consumption equivalent to policy effect
- **Formula**: Λ such that U(C×(1+Λ)) = U(C + policy)
- **Code Location**: `Code/HA-Models/FromPandemicCode/Welfare.py:Welfare_Results()`
- **Units**: Percent of lifetime consumption
- **Key Result**: UI extensions provide highest welfare per dollar spent

---

## Computational Methods

### Endogenous Grid Method (EGM)
- **Type**: Numerical solution technique
- **Purpose**: Solve household consumption-saving problems efficiently
- **Originated**: Carroll (2006) "The Method of Endogenous Gridpoints"
- **Key Advantage**: Avoids root-finding by solving on endogenous grid
- **Implementation**: HARK's `ConsIndShockModel.solve()`
- **Speed**: ~100x faster than traditional value function iteration

### Dynamic Programming
- **Type**: Computational technique for sequential decision problems
- **Bellman Equation**: V(s) = max_a [u(s,a) + βE[V(s')]]
- **Backward Induction**: Solve from terminal period backward
- **Implementation**: All models in `Code/HA-Models/`
- **State Variables**: Cash-on-hand (m), permanent income (p), employment state (θ)

### Calibration
- **Type**: Parameter estimation method
- **Method**: Choose parameters to match empirical moments
- **Targets**: 
  - Wealth distribution (SCF 2004)
  - MPCs (Parker et al. 2013)
  - iMPCs (Fagereng et al. 2021)
  - Aggregate consumption (NIPA)
- **Code Location**: `Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py` (estimation and calibration)
- **Paper Reference**: Table 1, Section 3

### Monte Carlo Simulation
- **Purpose**: Simulate household behavior under uncertainty
- **Method**: Draw random income shocks, solve and simulate many agents
- **Sample Size**: 10,000-100,000 households per simulation
- **Code Location**: `Code/HA-Models/FromPandemicCode/Simulate.py`
- **Computational Time**: ~30 seconds per policy scenario (8-core machine)

---

## Data Sources & Formats

### Survey of Consumer Finances (SCF)
- **Type**: Microdata on US household finances
- **Provider**: Federal Reserve Board
- **Frequency**: Triennial (every 3 years)
- **Sample Size**: ~6,000 households
- **Key Variables**: Income, wealth, assets, demographics
- **Paper Uses**: 2004 SCF (2013 dollars after CPI adjustment)
- **Code Location**: `Code/Empirical/make_liquid_wealth.py` (data processing)
- **Download**: <https://www.federalreserve.gov/econres/scfindex.htm>

### Real Survey of Consumer Finances (RSCF)
- **Type**: Archived SCF data with inflation adjustments
- **File**: `rscfp2004.dta` (Stata format)
- **Adjustment**: 2022$ → 2013$ using CPI-U-RS factor 1.1587
- **Purpose**: Reproducible data with documented inflation adjustments
- **Location**: Root directory (with-precomputed-artifacts branch)

### National Income and Product Accounts (NIPA)
- **Type**: Aggregate US economic data
- **Provider**: Bureau of Economic Analysis (BEA)
- **Key Series**: Personal consumption expenditures, disposable income
- **Purpose**: Calibration of aggregate model moments
- **Code Location**: `Code/Empirical/NIPA_data.py`

---

## Software Tools & Frameworks

### HARK (Heterogeneous Agents Resources and toolKit)
- **Type**: Python toolkit for heterogeneous agent models
- **Provider**: Econ-ARK project (<https://econ-ark.org>)
- **Key Classes**:
  - `IndShockConsumerType`: Idiosyncratic income shocks
  - `TwoAssetConsumerType`: Liquid + illiquid assets
  - `AggShockConsumerType`: Aggregate economic shocks
- **Installation**: `pip install econ-ark`
- **Documentation**: <https://docs.econ-ark.org>
- **GitHub**: <https://github.com/econ-ark/HARK>

### Dolo
- **Type**: Economic modeling language
- **Purpose**: Specify and solve dynamic models
- **Used For**: HANK-SAM aggregate dynamics
- **Code Location**: `Code/HA-Models/HANKSAMmodel.yaml`

### Voila
- **Type**: Dashboard framework (Jupyter widgets → web apps)
- **Purpose**: Interactive policy exploration
- **Implementation**: `dashboard/app.ipynb`
- **Launch**: `voila dashboard/app.ipynb` or MyBinder link

---

## Model-Specific Terms

### HANK-SAM (Heterogeneous Agent NK with Sticky Attention Model)
- **Type**: Specific HANK variant used in this paper
- **Key Features**:
  1. Heterogeneous households (HANK)
  2. Sticky expectations (Reis 2006)
  3. Nominal rigidities (NK)
  4. Aggregate demand feedback
- **Originated**: Crawley (2020) pandemic paper
- **Implementation**: `Code/HA-Models/FromPandemicCode/HANKSAM.py`

### Sticky Expectations
- **Definition**: Information friction where agents update beliefs infrequently
- **Formulation**: λ fraction update each period
- **Effect**: Dampens immediate consumption response to policy
- **Parameter**: λ ≈ 0.25 (quarterly updating)
- **Code Location**: `Code/HA-Models/StickyE/`
- **Paper Reference**: Carroll et al. (2020) "Modeling the Consumption Response to the CARES Act"

### Splurge Factor
- **Definition**: Immediate, non-optimizing consumption response
- **Parameter**: ξ ∈ [0,1]
- **Interpretation**: Fraction of windfall consumed immediately
- **Empirical Basis**: Baker et al. (2020) pandemic stimulus spending
- **Implementation**: `splurge` parameter in HARK models

---

## Policy Interventions Analyzed

### Stimulus Checks (Direct Payments)
- **Form**: One-time lump-sum payments to households
- **Historical Examples**: 
  - 2008: $600-$1,200
  - 2020-2021: $1,200, $600, $1,400
- **Targeting**: Broad-based, income-phased
- **Paper Simulation**: $1,200 per household
- **Code**: `Code/HA-Models/FromPandemicCode/AggFiscalMAIN.py` (policy comparison includes stimulus checks)

### Unemployment Insurance Extensions
- **Form**: Temporary increase in UI benefits (duration or amount)
- **Historical Examples**:
  - 2008-2013: Emergency UI extensions
  - 2020-2021: $300-$600/week supplements
- **Targeting**: Unemployed workers only
- **Paper Simulation**: 6-month extension with $300/week supplement
- **Code**: `Code/HA-Models/FromPandemicCode/AggFiscalMAIN.py` (policy comparison includes UI extensions)

### Payroll Tax Cuts
- **Form**: Temporary reduction in payroll tax rate
- **Historical Examples**:
  - 2011-2012: 2% payroll tax holiday
- **Targeting**: All employed workers
- **Paper Simulation**: 2% cut for 2 years
- **Code**: `Code/HA-Models/FromPandemicCode/AggFiscalMAIN.py` (policy comparison includes tax cuts)

---

## Mathematical Notation

| Symbol | Meaning | Context |
|--------|---------|---------|
| m | Cash-on-hand | Household state variable |
| c | Consumption | Household choice |
| a | Assets | End-of-period savings |
| θ | Employment state | Employed/unemployed |
| β | Discount factor | ~0.96 (quarterly) |
| ρ | CRRA parameter | Risk aversion ~2 |
| R | Interest rate | Gross return on assets |
| Y | Income | Labor + capital income |
| G | Government spending | Fiscal variable |
| π | Inflation | Price level growth |
| i | Nominal interest rate | Monetary policy |
| Λ | Welfare measure | Consumption equivalent |

---

## Empirical Moments & Calibration Targets

| Moment | Target Value | Source | Model Match |
|--------|--------------|---------|-------------|
| Median MPC (1 quarter) | 0.53 | Parker et al. (2013) | 0.51 |
| Mean MPC (1 quarter) | 0.48 | Parker et al. (2013) | 0.46 |
| Wealth Gini | 0.816 | SCF 2004 | 0.812 |
| Median net worth | $93,100 | SCF 2004 | $91,800 |
| Wealth share (top 10%) | 71.5% | SCF 2004 | 70.8% |
| iMPC (1 year) | 0.25 | Fagereng et al. (2021) | 0.24 |
| Consumption/Income | 0.92 | NIPA | 0.91 |

---

## Computational Environment

### System Requirements
- **OS**: Linux, macOS, Windows (WSL2)
- **CPU**: 8+ cores recommended
- **RAM**: 16+ GB recommended
- **Storage**: 5 GB for code + data
- **Python**: 3.9 or 3.10 (3.11+ not tested)

### Key Dependencies
- **HARK**: >= 0.13.0 (heterogeneous agent toolkit)
- **numpy**: >= 1.21 (numerical computing)
- **scipy**: >= 1.7 (optimization, interpolation)
- **pandas**: >= 1.3 (data manipulation)
- **matplotlib**: >= 3.4 (visualization)
- **seaborn**: >= 0.11 (statistical plots)
- **dolo**: >= 0.4 (model solution)

### Computational Time

See [timing estimates](../reproduce/benchmarks/README.md) (Single Source of Truth) for hardware-specific data and instructions to view actual benchmarks.

---

## Common Acronyms

| Acronym | Full Name | Context |
|---------|-----------|---------|
| HANK | Heterogeneous Agent New Keynesian | Model class |
| RANK | Representative Agent New Keynesian | Comparison benchmark |
| MPC | Marginal Propensity to Consume | Key parameter |
| iMPC | Intertemporal MPC | Time-varying MPC |
| UI | Unemployment Insurance | Policy intervention |
| SCF | Survey of Consumer Finances | Data source |
| RSCF | Real SCF | Inflation-adjusted SCF |
| NIPA | National Income & Product Accounts | Aggregate data |
| EGM | Endogenous Grid Method | Solution method |
| CRRA | Constant Relative Risk Aversion | Utility function |
| AR(1) | Autoregressive order 1 | Income process |
| QE | Quantitative Economics | Journal |

---

## Research Genealogy

### This Paper Builds On

1. **Carroll (1997)**: "Buffer-Stock Saving and the Life Cycle/Permanent Income Hypothesis"
   - Foundation: Buffer stock model
   - Innovation: Precautionary saving with income uncertainty

2. **Kaplan & Violante (2014)**: "A Model of the Consumption Response to Fiscal Stimulus Payments"
   - Foundation: Two-asset HANK model
   - Innovation: Illiquid wealth explains high MPCs

3. **Parker et al. (2013)**: "Consumer Spending and the Economic Stimulus Payments of 2008"
   - Foundation: Empirical MPC estimates
   - Data: CEX consumption survey

4. **Fagereng et al. (2021)**: "MPC Heterogeneity and Household Balance Sheets"
   - Foundation: Intertemporal MPC dynamics
   - Data: Norwegian registry data

5. **Carroll et al. (2020)**: "Modeling the Consumption Response to the CARES Act"
   - Foundation: HANK-SAM framework
   - Innovation: Sticky expectations + splurge factors

### This Paper Extends

- **Welfare Analysis**: First comprehensive welfare comparison of stimulus policies
- **Policy Comparison**: Systematic comparison of checks, UI, and tax cuts
- **Calibration**: Matches both micro (iMPCs) and macro (aggregates) moments
- **Implementation**: Full computational replication package

---

## Related Research Areas

### Upstream Fields
- Consumption theory (life-cycle, permanent income)
- Dynamic programming
- Numerical methods
- Income risk and insurance

### Downstream Applications
- Policy evaluation and design
- Business cycle analysis
- Monetary-fiscal interactions
- Wealth inequality

### Parallel Work
- Other HANK models (Auclert et al., Bayer & Luetticke)
- Fiscal multiplier estimation (Ramey, Auerbach-Gorodnichenko)
- Household finance (Gourinchas & Parker, Cagetti & De Nardi)

---

## Key Equations in the Paper

### Bellman Equation (Equation 3, Page 10)
```
V(m,θ) = max_c [u(c) + βE[V(m',θ')]]
subject to: a = m - c, m' = Ra + Y(θ')
```
**Implementation**: `Code/HA-Models/SolveDynamic.py:45`

### MPC Definition (Equation 7, Page 15)
```
MPC = ∂c/∂m
```
**Implementation**: `Code/HA-Models/FromPandemicCode/AggFiscalMAIN.py` (MPC computed in policy analysis)

### Welfare Measure (Equation 12, Page 22)
```
Λ = [V_policy/V_baseline]^(1/(1-ρ)) - 1
```
**Implementation**: `Code/HA-Models/FromPandemicCode/Welfare.py:67`

### Aggregate Consumption (Equation 15, Page 28)
```
C_t = ∫ c(m,θ) dμ_t(m,θ)
```
**Implementation**: `Code/HA-Models/Aggregate.py:89`

---

## Troubleshooting Quick Reference

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| HARK import error | Wrong Python version | Use Python 3.9 or 3.10 |
| Memory error | Insufficient RAM | Reduce grid size in calibration |
| Slow computation | CPU bottleneck | Use `--comp min` for quick test |
| LaTeX error | Missing packages | Run `./reproduce.sh --envt` |
| Data file not found | Wrong branch | Switch to `with-precomputed-artifacts` |

---

**For More Information**:
- Technical details: See other files in `README_IF_YOU_ARE_AN_AI/`
- Quick start: `000_AI_QUICK_START_GUIDE.md`
- Computational workflows: `030_COMPUTATIONAL_WORKFLOWS.md`
- Troubleshooting: `080_TROUBLESHOOTING_FOR_AI_SYSTEMS.md`
