# Mathematical Model Summary for AI Systems

## Overview

This document provides a comprehensive mathematical summary of the heterogeneous agent model used in "Welfare and Spending Effects of Consumption Stimulus Policies" by Carroll, Crawley, Du, Frankovic, and Tretvoll (2025).

The model is a **perpetual-youth heterogeneous agent model** with:

- Three education groups (Dropout, Highschool, College)
- Heterogeneous discount factors within each education group
- Permanent and transitory income shocks
- Unemployment risk with time-limited benefits
- A "splurge" consumption component
- Optional aggregate demand feedback effects

---

## Core Model Equations

### 1. Consumption Decomposition

Total consumption for consumer $i$ at time $t$ consists of two components:

$$\mathbf{c}_{i,t} = \mathbf{c}_{sp,i,t} + \mathbf{c}_{opt,i,t}$$

Where:

- $\mathbf{c}_{i,t}$ = Total consumption
- $\mathbf{c}_{sp,i,t}$ = Splurge consumption (immediate, non-optimizing)
- $\mathbf{c}_{opt,i,t}$ = Optimal consumption (from dynamic optimization)

### 2. Splurge Consumption

The splurge is a fixed fraction of current income:

$$\mathbf{c}_{sp,i,t} = \varsigma \cdot \mathbf{y}_{i,t}$$

Where:

- $\varsigma$ = Splurge factor (estimated to be 0.249)
- $\mathbf{y}_{i,t}$ = Current income

**Economic Intuition**: The splurge captures the empirical finding that consumers spend a fraction of income immediately upon receipt, regardless of their wealth level. This is crucial for matching the high MPCs observed even among wealthy households.

### 3. Optimal Consumption Problem

The consumer maximizes expected lifetime utility:

$$\max \sum_{t=0}^{\infty} \beta_i^t (1-D)^t \mathbb{E}_0 [u(\mathbf{c}_{opt,i,t})]$$

Where:

- $\beta_i$ = Consumer $i$'s subjective discount factor
- $D$ = Death probability (quarterly, set to 1/160)
- $u(c)$ = CRRA utility function

### 4. Utility Function

Standard CRRA (Constant Relative Risk Aversion) utility:

$$u(c) = \frac{c^{1-\gamma}}{1-\gamma} \quad \text{for } \gamma \neq 1$$

$$u(c) = \log(c) \quad \text{for } \gamma = 1$$

Where:

- $\gamma$ = Coefficient of relative risk aversion (set to 2)

### 5. Budget Constraint

The optimization is subject to:

$$\mathbf{a}_{i,t} = \mathbf{m}_{i,t} - \mathbf{c}_{i,t}$$

$$\mathbf{m}_{i,t+1} = R \cdot \mathbf{a}_{i,t} + \mathbf{y}_{i,t+1}$$

$$\mathbf{a}_{i,t} \geq 0$$

Where:

- $\mathbf{a}_{i,t}$ = End-of-period assets (after consumption)
- $\mathbf{m}_{i,t}$ = Market resources (cash-on-hand)
- $R$ = Gross interest rate on savings (1.01 quarterly)

---

## Income Process

### 1. Permanent Income Evolution

$$\mathbf{p}_{i,t+1} = \psi_{i,t+1} \cdot \Gamma_{e(i)} \cdot \mathbf{p}_{i,t}$$

Where:

- $\mathbf{p}_{i,t}$ = Permanent income level
- $\psi_{i,t+1}$ = Permanent income shock (log-normal)
- $\Gamma_{e(i)}$ = Average income growth rate for education group $e(i)$
- $\sigma_\psi = 0.0548$ (quarterly standard deviation)

### 2. Income Realization by Employment Status

$$\mathbf{y}_{i,t} = \begin{cases}
\xi_{i,t} \cdot \mathbf{p}_{i,t} & \text{if employed} \\
\rho_b \cdot \mathbf{p}_{i,t} & \text{if unemployed with benefits} \\
\rho_{nb} \cdot \mathbf{p}_{i,t} & \text{if unemployed without benefits}
\end{cases}$$

Where:

- $\xi_{i,t}$ = Transitory income shock (log-normal, $\sigma_\xi = 0.346$)
- $\rho_b = 0.7$ = Replacement rate with unemployment benefits
- $\rho_{nb} = 0.5$ = Replacement rate without benefits

### 3. Employment Transitions (Markov Process)

The employment state follows a 4-state Markov chain:

| State | Description |
|-------|-------------|
| 0 | Employed |
| 1 | Unemployed with benefits (quarter 1) |
| 2 | Unemployed with benefits (quarter 2) |
| 3 | Unemployed without benefits |

**Transition Probabilities (Normal Times)**:

- $\pi_{eu}^e$ = Probability of job loss (education-specific)
- $\pi_{ue} = 2/3$ = Probability of finding a job (same for all)

**Education-Specific Job Loss Probabilities (Normal Times)**:

- Dropout: $\pi_{eu}^d = 6.2\%$
- Highschool: $\pi_{eu}^h = 3.1\%$
- College: $\pi_{eu}^c = 1.8\%$

---

## Heterogeneity Structure

### 1. Education Groups

Three education levels with population shares:

| Group | Share | Initial Income | Growth Rate |
|-------|-------|----------------|-------------|
| Dropout | 9.3% | $6,200/quarter | $\Gamma_d = 1.0036$ |
| Highschool | 52.7% | $11,100/quarter | $\Gamma_h = 1.0045$ |
| College | 38.0% | $14,500/quarter | $\Gamma_c = 1.0049$ |

### 2. Discount Factor Distribution

Within each education group, discount factors are uniformly distributed:

$$\beta_i \sim \text{Uniform}[\beta_e - \nabla_e, \beta_e + \nabla_e]$$

**Estimated Parameters**:

| Group | $\beta_e$ (Center) | $\nabla_e$ (Spread) |
|-------|-------------------|---------------------|
| Dropout | 0.720 | 0.372 |
| Highschool | 0.903 | 0.085 |
| College | 0.970 | 0.019 |

The distribution is discretized with 7 types per education group.

---

## Recession Dynamics

### 1. Recession Onset (MIT Shock)

At recession start:

- Unemployment rate doubles for all education groups
- Expected unemployment duration increases from 1.5 to 4 quarters
- $\pi_{ue}$ drops from 2/3 to 0.25

### 2. Recession Duration

Recession ends stochastically with an expected duration of 6 quarters.

### 3. Policy Responses

**Stimulus Check**:

$$\text{Check}_{i} = \begin{cases}
\$1,200 & \text{if } \mathbf{p}_i < \$100,000 \\
\$1,200 \cdot \frac{\$150,000 - \mathbf{p}_i}{\$50,000} & \text{if } \$100,000 \leq \mathbf{p}_i \leq \$150,000 \\
0 & \text{if } \mathbf{p}_i > \$150,000
\end{cases}$$

**Extended UI Benefits**:
Unemployment benefits extended from 2 quarters to 4 quarters.

**Payroll Tax Cut**:
Employed consumers receive 2% income boost for 8 quarters.

---

## Aggregate Demand Extension

### 1. AD Feedback Function

$$AD(C_t) = \begin{cases}
\left(\frac{C_t}{\tilde{C}}\right)^\kappa & \text{if in recession} \\
1 & \text{otherwise}
\end{cases}$$

Where:

- $C_t$ = Aggregate consumption
- $\tilde{C}$ = Steady-state consumption
- $\kappa = 0.3$ = Consumption elasticity of productivity

### 2. Modified Income

$$\mathbf{y}_{AD,i,t} = AD(C_t) \cdot \mathbf{y}_{i,t}$$

---

## Solution Method

### 1. Algorithm: Endogenous Grid Method (EGM)

The model is solved using the **Endogenous Grid Method** from the HARK library:

1. Define grid over end-of-period assets
2. Use Euler equation (first-order conditions) to find consumption at each grid point
3. Compute beginning-of-period resources (the "endogenous grid")
4. Interpolate to obtain consumption function $c(m)$

### 2. EGM with Markov States

For the Markov employment states, EGM is applied state-by-state:

1. Solve for consumption function in each Markov state
2. Expectations integrate over both income shocks and state transitions
3. Iterate until consumption functions converge
4. Each state has its own consumption function $c_s(m)$

### 3. Simulation

Monte Carlo simulation with:

- 5,000 agents per type
- 21 types total (7 discount factor types × 3 education groups)
- 800 quarters of simulation

---

## Calibration Targets

### 1. Norwegian Data (Splurge Estimation)

From Fagereng, Holm, and Natvik (2021):

- **Intertemporal MPC profile**: Match consumption response to lottery wins over 4 years
- **Cross-sectional MPC**: Match MPC by liquid wealth quartile

### 2. US Data (Full Model)

From Survey of Consumer Finances 2004:

- **Liquid Wealth Distribution**: Match Lorenz curve points (20th, 40th, 60th, 80th percentiles)
- **Wealth-to-Income Ratio**: Target median ratio by education group
- **Education Shares**: Match population distribution

### 3. Labor Market

From Bureau of Labor Statistics:

- **Unemployment Rates**: Education-specific (8.5%, 4.4%, 2.7%)
- **Unemployment Duration**: 1.5 quarters in normal times

---

## Key Model Outputs

### 1. Marginal Propensity to Consume (MPC)

The model produces MPCs that vary by:

- Liquid wealth level
- Time since income shock (iMPCs)
- Education group

### 2. Fiscal Multipliers

Aggregate consumption response to $1 of government spending:

- Immediate (same quarter)
- Cumulative (over time)
- With/without aggregate demand effects

### 3. Welfare Measures

Consumption-equivalent variation (CEV):
The permanent proportional increase in consumption that would make agents indifferent between the policy and no policy.

---

## Code Implementation

### Key Files

| File | Purpose |
|------|---------|
| `do_all.py` | Master pipeline script |
| `EstimAggFiscalModel.py` | Core model class (`AggFiscalType`) |
| `EstimAggFiscalMAIN.py` | Discount factor estimation |
| `AggFiscalMAIN.py` | Policy comparison |
| `Estimation_BetaNablaSplurge.py` | Splurge factor estimation |

### HARK Library Components

- `MarkovConsumerType` - Base class for Markov employment states
- `ConsIndShockModel` - Standard consumption-saving model
- `KinkedRconsumerType` - Handles different borrowing/saving rates

---

## Notation Reference

| Symbol | Meaning | Typical Value |
|--------|---------|---------------|
| $\mathbf{c}$ | Consumption | - |
| $\mathbf{a}$ | End-of-period assets | - |
| $\mathbf{m}$ | Market resources (cash-on-hand) | - |
| $\mathbf{y}$ | Income | - |
| $\mathbf{p}$ | Permanent income | - |
| $\beta$ | Discount factor | 0.72–0.99 |
| $\gamma$ | Risk aversion | 2.0 |
| $\varsigma$ | Splurge factor | 0.249 |
| $R$ | Gross interest rate | 1.01 |
| $D$ | Death probability | 1/160 |
| $\Gamma$ | Permanent income growth | 1.004–1.005 |
| $\psi$ | Permanent income shock | $\sigma = 0.055$ |
| $\xi$ | Transitory income shock | $\sigma = 0.346$ |
| $\rho_b$ | UI replacement rate | 0.70 |
| $\rho_{nb}$ | Non-UI replacement rate | 0.50 |
| $\kappa$ | AD elasticity | 0.30 |

---

## References for AI Systems

- **Paper**: Carroll, Crawley, Du, Frankovic, Tretvoll (2025). "Welfare and Spending Effects of Consumption Stimulus Policies"
- **Code**: `Code/HA-Models/` directory
- **HARK Library**: <https://github.com/econ-ark/HARK>
- **Related Literature**:
  - Fagereng, Holm, Natvik (2021) - Norwegian lottery data
  - Kaplan, Violante (2014) - Two-asset HANK model
  - Auclert et al. (2021) - Sequence-space Jacobian methods
  - Carroll et al. (2020) - Sticky expectations

