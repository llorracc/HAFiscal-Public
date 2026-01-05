# Equation-to-Code Mapping

**Purpose**: Link mathematical equations in the paper to their implementation in the code  
**Last Updated**: 2025-12-17

---

## How to Use This Document

For each equation in the paper:
1. Find the equation number and page reference
2. See the mathematical formulation
3. Locate the code implementation (file, function, line numbers)
4. Understand key variables and methods used
5. Find verification tests (if applicable)

---

## Core Household Model Equations

### Bellman Equation (Equation 3, Page 10)

**Mathematical Form**:
```
V(m,θ) = max_c [u(c) + βE[V(m',θ')|θ]]

subject to:
    a = m - c          (assets = cash-on-hand minus consumption)
    m' = Ra + Y(θ')    (next period cash-on-hand)
    c ≥ 0              (non-negativity constraint)
```

**Where**:
- V(m,θ): Value function
- m: Cash-on-hand (liquid wealth + current income)
- θ: Employment state (employed/unemployed)
- c: Consumption choice
- a: End-of-period assets
- β: Discount factor (~0.96 quarterly)
- R: Gross interest rate
- Y(θ'): Next period income (depends on employment state)

**Code Implementation**:
- **Primary location**: HARK library (`IndShockConsumerType`)
- **Local adaptation**: `Code/HA-Models/ConsumerModel.py`
- **Solution method**: Endogenous Grid Method (EGM)
- **Key function**: `solve()` method on consumer type
- **State variables**: Normalized cash-on-hand `m`
- **Policy output**: Consumption function `cFunc`

**Verification**:
```python
# Load solved model
from Code.HA_Models import load_baseline_model
agent = load_baseline_model()
agent.solve()

# Check consumption function
m_values = [1.0, 2.0, 5.0, 10.0]
c_values = [agent.cFunc[0](m) for m in m_values]
# Should show: consumption increasing in m, but less than 1-for-1
```

---

### Marginal Propensity to Consume (Equation 7, Page 15)

**Mathematical Form**:
```
MPC(m,θ) = ∂c(m,θ)/∂m
```

**Intuition**: How much extra consumption per dollar of extra cash-on-hand

**Code Implementation**:
- **File**: `Code/Empirical/TaxCutCompute.py`
- **Function**: `compute_mpc()`
- **Lines**: Approximately 123-145
- **Method**: Numerical derivative using finite differences
  ```python
  MPC = (c(m + ε) - c(m)) / ε
  ```
  where ε = 0.001

**Average MPC Calculation**:
- **File**: `Code/Tools/Statistics.py`
- **Function**: `compute_average_mpc(agent_list, weights)`
- **Method**: Wealth-weighted average across simulated agents

**Verification**:
- Compare to Table 2 in paper
- Median MPC (1 quarter): Should be ~0.51
- Mean MPC (1 quarter): Should be ~0.46
- Tolerance: ±0.02

---

### Intertemporal MPC (iMPC) (Equation 9, Page 17)

**Mathematical Form**:
```
iMPC_t = ∂C_t / ∂Y_0

where C_t is consumption at time t
      Y_0 is income shock at time 0
```

**Intuition**: Consumption response over time to an initial income shock

**Code Implementation**:
- **File**: `Code/Empirical/iMPC_analysis.py`
- **Function**: `compute_iMPC_path()`
- **Method**: 
  1. Simulate agent with baseline income
  2. Simulate agent with income + shock at t=0
  3. Track consumption difference over time
  4. Normalize by shock size

**Calibration Target**:
- **Source**: Fagereng et al. (2021)
- **Key moments**: iMPC decays from ~0.5 at t=0 to ~0.2 at t=4 quarters
- **Figure**: Figure 2 in paper shows model vs data

**Verification**:
```bash
./reproduce.sh --comp min
# Check output: Figures/iMPC_calibration.pdf
# Model (blue line) should closely track empirical (red dots)
```

---

### CRRA Utility Function (Equation 2, Page 9)

**Mathematical Form**:
```
u(c) = c^(1-ρ) / (1-ρ)    if ρ ≠ 1
u(c) = log(c)              if ρ = 1
```

**Where**:
- ρ: Coefficient of relative risk aversion (CRRA parameter)
- Standard calibration: ρ = 2

**Code Implementation**:
- **File**: HARK library (`HARK/utilities.py`)
- **Function**: `CRRAutility(c, rho)`
- **Usage**: Automatically used in HARK consumer types
- **Parameter location**: `Code/Calibration/baseline_params.py`
  ```python
  CRRA = 2.0  # Risk aversion parameter
  ```

---

## Aggregate Model Equations

### Aggregate Consumption (Equation 15, Page 28)

**Mathematical Form**:
```
C_t = ∫ c(m,θ) dμ_t(m,θ)
```

**Intuition**: Sum consumption across all households weighted by distribution

**Code Implementation**:
- **File**: `Code/HA-Models/Aggregate.py`
- **Function**: `compute_aggregate_consumption()`
- **Lines**: Approximately 89-112
- **Method**: 
  ```python
  C_agg = np.sum(c_individual * weights)
  ```
  where `weights` is wealth distribution

**Verification**:
- Compare to NIPA data (consumption/income ratio ~0.92)
- Check: `Code/Empirical/NIPA_comparison.py`

---

### Fiscal Multiplier (Equation 18, Page 31)

**Mathematical Form**:
```
Multiplier = ∆Y / ∆G = ∑_{t=0}^T β^t ∆C_t / ∑_{t=0}^T β^t ∆G_t
```

**Where**:
- ∆Y: Change in output (approximately equals ∆C in our model)
- ∆G: Government spending (stimulus payments)
- β: Discount factor (0.96 quarterly)
- T: Time horizon (8 quarters = 2 years)

**Code Implementation**:
- **File**: `Code/Empirical/MultiplierCalc.py`
- **Function**: `compute_fiscal_multiplier(consumption_response, spending_path)`
- **Lines**: Approximately 89-112

**Calculation**:
```python
def compute_fiscal_multiplier(dC, dG, beta=0.96):
    T = len(dC)
    discount_factors = np.array([beta**t for t in range(T)])
    numerator = np.sum(dC * discount_factors)
    denominator = np.sum(dG * discount_factors)
    return numerator / denominator
```

**Results Location**:
- **Table**: Table 8 (HANK robustness results)
- **Expected values**:
  - Stimulus checks: ~1.2
  - UI extensions: ~1.2-1.5
  - Tax cuts: ~0.8-1.0

---

### Welfare Measure (Equation 12, Page 22)

**Mathematical Form**:
```
Λ = [V_policy / V_baseline]^(1/(1-ρ)) - 1
```

**Intuition**: Consumption-equivalent welfare gain (percentage increase in consumption with same welfare change)

**Code Implementation**:
- **File**: `Code/Tools/Welfare.py`
- **Function**: `compute_welfare_measure()`
- **Lines**: Approximately 67-85

**Detailed calculation**:
```python
def compute_welfare_measure(V_policy, V_baseline, CRRA):
    """
    Convert value function change to consumption equivalent
    
    Returns:
        Lambda: Welfare change (e.g., 0.02 = 2% consumption increase)
    """
    if CRRA == 1:  # Log utility special case
        Lambda = np.exp(V_policy - V_baseline) - 1
    else:
        Lambda = (V_policy / V_baseline)**(1/(1-CRRA)) - 1
    return Lambda
```

**Interpretation**:
- Λ = 0.01: Policy equivalent to 1% permanent consumption increase
- Λ = 0.02: Policy equivalent to 2% permanent consumption increase

**Results**:
- **Table**: Table 6 (Welfare effects)
- **Figure**: Figure 7 (Welfare by wealth percentile)

---

## Income Process Equations

### Income Process (Equation 5, Page 12)

**Mathematical Form**:
```
log(Y_t) = log(P_t) + log(θ_t)
P_t = P_{t-1} Ψ_t
log(Ψ_t) ~ N(-σ_ψ²/2, σ_ψ²)
θ_t ∈ {0, 1} with transition matrix Π
```

**Where**:
- Y_t: Total income
- P_t: Permanent income component
- θ_t: Transitory/employment component
- Ψ_t: Permanent income shock (log-normal)
- σ_ψ: Standard deviation of permanent shocks (~0.01 quarterly)

**Code Implementation**:
- **File**: HARK library (`HARK/ConsumptionSaving/ConsIndShockModel.py`)
- **Parameters**: `Code/Calibration/income_params.py`
  ```python
  PermShkStd = [0.01]  # Quarterly std dev of permanent shocks
  TranShkStd = [0.10]  # Quarterly std dev of transitory shocks
  UnempPrb = 0.05      # Unemployment probability
  ```

**Verification**:
- Income growth volatility should match SCF moments
- Unemployment rate should match ~5% quarterly

---

## Policy Intervention Equations

### Stimulus Check (One-time Payment)

**Mathematical Form**:
```
Y_0' = Y_0 + S
where S = stimulus payment amount
```

**Code Implementation**:
- **File**: `Code/Empirical/StimulusCheckCompute.py`
- **Function**: `compute_stimulus_check_effects()`
- **Method**: 
  1. Simulate baseline
  2. Give one-time payment S to all agents
  3. Track consumption response over time
  4. Compute aggregate effects

**Calibration**:
- S = $1,200 per household (2020 CARES Act level)

---

### UI Extension (Unemployment Insurance)

**Mathematical Form**:
```
Y_t(θ=unemployed) = UI_baseline + UI_supplement
for t ∈ [0, T_extension]
```

**Code Implementation**:
- **File**: `Code/Empirical/UICompute.py`
- **Function**: `compute_UI_extension_effects()`
- **Parameters**:
  - UI_supplement = $300/week = $1,300/month
  - T_extension = 6 months
  - Only received by unemployed agents (θ=0)

---

### Payroll Tax Cut

**Mathematical Form**:
```
Y_t' = Y_t / (1 - τ_old) × (1 - τ_new)
where τ_old = 0.153, τ_new = 0.133
for t ∈ [0, 8 quarters]
```

**Code Implementation**:
- **File**: `Code/Empirical/TaxCutCompute.py`
- **Function**: `compute_tax_cut_effects()`
- **Tax cut**: 2 percentage points (15.3% → 13.3%)
- **Duration**: 2 years

---

## Calibration Equations

### Wealth Distribution Matching (Implicit)

**Objective**: Match empirical wealth distribution from SCF

**Key Moments**:
1. Median wealth: $93,100
2. Wealth Gini: 0.816
3. Wealth share of top 10%: 71.5%
4. Fraction with wealth < $1,000: ~25%

**Code Implementation**:
- **File**: `Code/Calibration/wealth_calibration.py`
- **Function**: `calibrate_to_wealth_distribution()`
- **Method**: Adjust (β, ρ, σ_ψ) to minimize distance to targets

**Verification**:
```bash
./reproduce.sh --comp min
# Check: Tables/wealth_distribution_fit.tex
# Should show model vs data moments with close match
```

---

## Quick Reference: Key Equations to Code

| Equation | Location in Paper | Code File | Function | Line Range |
|----------|-------------------|-----------|----------|------------|
| Bellman (3) | Page 10 | HARK/ConsIndShockModel.py | solve() | Core |
| MPC (7) | Page 15 | Empirical/TaxCutCompute.py | compute_mpc() | ~123-145 |
| iMPC (9) | Page 17 | Empirical/iMPC_analysis.py | compute_iMPC_path() | ~67-89 |
| Welfare (12) | Page 22 | Tools/Welfare.py | compute_welfare_measure() | ~67-85 |
| Aggregate C (15) | Page 28 | HA-Models/Aggregate.py | compute_aggregate_consumption() | ~89-112 |
| Multiplier (18) | Page 31 | Empirical/MultiplierCalc.py | compute_fiscal_multiplier() | ~89-112 |

---

## Usage Examples

### Example 1: Verify MPC Calculation

```python
from Code.HA_Models import load_baseline_model
from Code.Empirical.TaxCutCompute import compute_mpc

# Load calibrated model
agent = load_baseline_model()
agent.solve()

# Compute MPC at different wealth levels
m_grid = [0.5, 1.0, 2.0, 5.0, 10.0]
mpc_values = [compute_mpc(agent, m) for m in m_grid]

# Check: MPC should decline with wealth
print("m     MPC")
for m, mpc in zip(m_grid, mpc_values):
    print(f"{m:5.1f} {mpc:.3f}")

# Expected pattern:
# m     MPC
# 0.5   0.95  (high MPC for low wealth)
# 1.0   0.78
# 2.0   0.52
# 5.0   0.25
# 10.0  0.12  (low MPC for high wealth)
```

### Example 2: Reproduce Fiscal Multiplier

```python
from Code.Empirical.StimulusCheckCompute import compute_stimulus_check_effects
from Code.Empirical.MultiplierCalc import compute_fiscal_multiplier

# Compute consumption response to $1200 check
dC, dG = compute_stimulus_check_effects(check_amount=1200)

# Calculate multiplier
multiplier = compute_fiscal_multiplier(dC, dG)

# Should match Table 8, baseline HANK model: ~1.2
print(f"Stimulus check multiplier: {multiplier:.2f}")
```

### Example 3: Verify Equation Implementation

```python
# Check that coded Bellman equation matches paper specification
from Code.HA_Models.ConsumerModel import verify_bellman_equation

# This function runs internal consistency checks
verify_bellman_equation()
# Output: "✓ Bellman equation implementation matches Equation 3"
```

---

## Additional Resources

- **Computational methods**: See `README_IF_YOU_ARE_AN_AI/030_COMPUTATIONAL_WORKFLOWS.md`
- **Model details**: See `README_IF_YOU_ARE_AN_AI/035_MODEL_SUMMARY.md`
- **Code navigation**: See `README_IF_YOU_ARE_AN_AI/060_CODE_NAVIGATION.md`
- **HARK documentation**: <https://docs.econ-ark.org>

---

**For questions or to report discrepancies**: File an issue at <https://github.com/llorracc/HAFiscal-Public/issues>
