# Mathematical Structure for AI Systems

**Purpose**: Provide a comprehensive mathematical framework map for AI systems to understand the model structure, equation hierarchy, and computational relationships.

**Last Updated**: 2025-12-31

---

## Document Structure

This document organizes the mathematical content hierarchically:

1. **Core Mathematical Objects** - Fundamental equations and definitions
2. **Equation Map** - Mapping between equations, code locations, and paper references
3. **State Space and Operators** - State variables, transition operators, and function spaces
4. **Computational Structure** - How mathematical objects map to code implementations
5. **Sequence-Space Jacobian Framework** - The computational method for aggregation

---

## 1. Core Mathematical Objects

### 1.1 Agent-Level Problem

#### Value Function (Bellman Equation)

The consumer's value function satisfies:

$$V_s(\mathbf{m}, \mathbf{p}) = \max_{\mathbf{c}} \left\{ u(\mathbf{c}) + \beta (1-D) \mathbb{E}\left[ V_{s'}(\mathbf{m}', \mathbf{p}') \mid s \right] \right\}$$

**Where:**
- $V_s(\mathbf{m}, \mathbf{p})$ = Value function in state $s$ with market resources $\mathbf{m}$ and permanent income $\mathbf{p}$
- $s$ = Employment/benefit state (0=employed, 1-2=UI benefits, 3=no benefits)
- $u(c)$ = CRRA utility function
- $\beta$ = Discount factor (heterogeneous across agents)
- $D$ = Death probability = 1/160
- $\mathbb{E}[\cdot \mid s]$ = Expectation over income shocks and state transitions

**Code Location**: Solved implicitly in `EstimAggFiscalModel.py` via HARK's `solve()` method using EGM

**Paper Reference**: Standard dynamic programming setup, see MODEL_SUMMARY.md Section 3

#### Euler Equation (First-Order Condition)

At optimum, consumption satisfies:

$$u'(\mathbf{c}_{opt}) = \beta (1-D) R \mathbb{E}\left[ u'(\mathbf{c}'_{opt}) \right]$$

**Where:**
- $u'(c) = c^{-\gamma}$ = Marginal utility (CRRA)
- $R = 1.01$ = Gross interest rate

**Code Location**: Implemented in HARK's EGM solver (`ConsMarkovModel.py`)

**Intuition**: Marginal utility today equals discounted expected marginal utility tomorrow, adjusted for interest rate

#### Budget Constraints

**End-of-period assets:**
$$\mathbf{a} = \mathbf{m} - \mathbf{c}$$

**Next-period resources:**
$$\mathbf{m}' = R \cdot \mathbf{a} + \mathbf{y}'$$

**Borrowing constraint:**
$$\mathbf{a} \geq 0$$

**Code Location**: `EstimAggFiscalModel.py:updateSolutionTerminal()`, `postsolve()`

### 1.2 Consumption Decomposition

**Total consumption:**
$$\mathbf{c} = \mathbf{c}_{sp} + \mathbf{c}_{opt}$$

**Splurge component:**
$$\mathbf{c}_{sp} = \varsigma \cdot \mathbf{y}$$

**Optimal component:**
$$\mathbf{c}_{opt} = c_s(\mathbf{m}) \quad \text{(from value function)}$$

**Where:**
- $\varsigma = 0.249$ = Splurge factor (estimated)
- $c_s(\mathbf{m})$ = Consumption function (solution to Bellman equation)

**Code Location**: 
- Splurge: `AggFiscalModel.py:consumption()` method
- Optimal: `EstimAggFiscalModel.py` solved via EGM

**Paper Reference**: Eq. (1) in paper, MODEL_SUMMARY.md Section 1.1

### 1.3 Income Process

#### Permanent Income Evolution

$$\mathbf{p}' = \psi' \cdot \Gamma_e \cdot \mathbf{p}$$

**Where:**
- $\psi' \sim \text{Lognormal}(0, \sigma_\psi^2)$ = Permanent shock, $\sigma_\psi = 0.0548$
- $\Gamma_e$ = Education-specific growth rate ($\Gamma_d=1.0036$, $\Gamma_h=1.0045$, $\Gamma_c=1.0049$)
- $e \in \{d, h, c\}$ = Education group (dropout, highschool, college)

**Code Location**: `EstimAggFiscalModel.py:initializeSim()`, permanent income shocks

#### Income Realization

$$\mathbf{y} = \begin{cases}
\xi \cdot \mathbf{p} & \text{if employed (state 0)} \\
\rho_b \cdot \mathbf{p} & \text{if unemployed with UI (states 1-2)} \\
\rho_{nb} \cdot \mathbf{p} & \text{if unemployed without UI (state 3)}
\end{cases}$$

**Where:**
- $\xi \sim \text{Lognormal}(0, \sigma_\xi^2)$ = Transitory shock, $\sigma_\xi = 0.346$
- $\rho_b = 0.7$ = UI replacement rate
- $\rho_{nb} = 0.5$ = No-UI replacement rate

**Code Location**: `EstimAggFiscalModel.py:getIncome()`

#### State Transitions (Markov Process)

States: $\{0, 1, 2, 3\}$ representing employment/benefit status

**Transition matrix** (education and time-dependent):
- Normal times: $\pi_{eu}^e$ (education-specific job loss), $\pi_{ue} = 2/3$ (job finding)
- Recession: Unemployment rate doubles, $\pi_{ue} = 0.25$

**Code Location**: `EstimParameters.py` defines transition probabilities

### 1.4 Aggregation Operators

#### Individual-to-Aggregate Mapping

For any agent-level variable $x_i$, the aggregate is:

$$X = \int x_i \, d\mu(i)$$

**Where:**
- $\mu$ = Measure over agents (accounts for education groups, discount factors, wealth distribution)

**Code Location**: `AggFiscalMAIN.py:computeAggregate()` uses Monte Carlo integration

#### Aggregate Consumption

$$C_t = \int \mathbf{c}_{i,t} \, d\mu(i)$$

**Code Location**: `AggFiscalMAIN.py` aggregates over simulated agents

### 1.5 Policy Shocks

#### Stimulus Check

$$\text{Check}_i = \begin{cases}
\$1,200 & \text{if } \mathbf{p}_i < \$100,000 \\
\$1,200 \cdot \frac{\$150,000 - \mathbf{p}_i}{\$50,000} & \text{if } \$100,000 \leq \mathbf{p}_i \leq \$150,000 \\
0 & \text{if } \mathbf{p}_i > \$150,000
\end{cases}$$

**Code Location**: `AggFiscalModel.py:getIncome()` adds check to income

#### UI Extension

Extends benefit duration from 2 to 4 quarters (modifies Markov transition matrix)

**Code Location**: `EstimParameters.py` defines extended UI parameters

#### Tax Cut

2% income boost for employed agents, lasting 8 quarters

**Code Location**: `AggFiscalModel.py:getIncome()` multiplies income by 1.02

---

## 2. Equation Map: Paper ↔ Code ↔ Math

| Equation/Concept | Paper Location | Code Location | Mathematical Form |
|------------------|----------------|---------------|-------------------|
| Consumption decomposition | Eq. (1) | `AggFiscalModel.py:consumption()` | $\mathbf{c} = \mathbf{c}_{sp} + \mathbf{c}_{opt}$ |
| Splurge consumption | Eq. (2) | `AggFiscalModel.py:consumption()` | $\mathbf{c}_{sp} = \varsigma \mathbf{y}$ |
| Value function | Section 2.1 | `EstimAggFiscalModel.py` (via HARK) | $V_s(\mathbf{m}, \mathbf{p}) = \max\{u(c) + \beta E[V']\}$ |
| Euler equation | Implicit in EGM | `ConsMarkovModel.py` (HARK) | $u'(c) = \beta R E[u'(c')]$ |
| Budget constraint | Section 2.1 | `EstimAggFiscalModel.py:update()` | $\mathbf{a} = \mathbf{m} - \mathbf{c}$, $\mathbf{m}' = R\mathbf{a} + \mathbf{y}'$ |
| Permanent income | Section 2.2 | `EstimAggFiscalModel.py:getIncome()` | $\mathbf{p}' = \psi' \Gamma_e \mathbf{p}$ |
| Income realization | Section 2.2 | `EstimAggFiscalModel.py:getIncome()` | $\mathbf{y} = f(\xi, \rho, \mathbf{p})$ |
| State transitions | Section 2.2 | `EstimParameters.py` | Markov matrix $\pi_{ss'}$ |
| Aggregate consumption | Section 3 | `AggFiscalMAIN.py:computeAggregate()` | $C = \int \mathbf{c}_i d\mu$ |
| AD feedback | Section 4.5 | `AggFiscalMAIN.py:computeAD()` | $AD(C) = (C/\tilde{C})^\kappa$ |
| MPC calculation | Section 3.1 | `FiscalTools.py:computeMPC()` | $MPC = \partial C / \partial Y$ |
| Welfare measure | Section 5.1 | `Welfare.py:computeWelfare()` | CEV: $U(C(1+\Lambda)) = U(C + \Delta)$ |

---

## 3. State Space and Operators

### 3.1 Individual State Space

**State vector for agent $i$:**
$$\mathbf{s}_i = (\mathbf{m}_i, \mathbf{p}_i, s_i, e_i, \beta_i)$$

**Components:**
- $\mathbf{m}_i \in \mathbb{R}_+$ = Market resources (cash-on-hand)
- $\mathbf{p}_i \in \mathbb{R}_+$ = Permanent income level
- $s_i \in \{0,1,2,3\}$ = Employment/benefit state
- $e_i \in \{d,h,c\}$ = Education group
- $\beta_i \in [\beta_e - \nabla_e, \beta_e + \nabla_e]$ = Discount factor

**Code Location**: State variables stored in `AgentType` objects in HARK

### 3.2 Aggregate State

**Aggregate state vector:**
$$\mathbf{S} = (C, Y, \text{recession\_flag}, t)$$

**Where:**
- $C$ = Aggregate consumption
- $Y$ = Aggregate income
- $\text{recession\_flag} \in \{0,1\}$ = Recession indicator
- $t$ = Time period

**Code Location**: `AggFiscalMAIN.py` tracks aggregate state

### 3.3 Transition Operators

#### Individual Transition Operator

$T_i: \mathbf{s}_i \mapsto \mathbf{s}'_i$ defined by:
1. Income shock: $\mathbf{y}' = f(\xi', \psi', s', \mathbf{p})$
2. Asset evolution: $\mathbf{a} = \mathbf{m} - \mathbf{c}(\mathbf{m})$, $\mathbf{m}' = R\mathbf{a} + \mathbf{y}'$
3. Permanent income: $\mathbf{p}' = \psi' \Gamma_e \mathbf{p}$
4. State transition: $s' \sim \pi_{ss'}$

**Code Location**: `EstimAggFiscalModel.py:simOnePeriod()`

#### Aggregation Operator

$\mathcal{A}: \{\mathbf{s}_i\} \mapsto \mathbf{S}$ aggregates individual states:
$$C = \sum_i w_i \mathbf{c}_i, \quad Y = \sum_i w_i \mathbf{y}_i$$

**Where:** $w_i$ = Agent weight (population share)

**Code Location**: `AggFiscalMAIN.py:computeAggregate()`

---

## 4. Sequence-Space Jacobian Framework

### 4.1 Overview

The model uses **Sequence-Space Jacobian (SSJ) methods** (Auclert et al. 2021) to compute aggregate responses efficiently.

**Key Idea**: Compute Jacobian matrices that map sequences of aggregate shocks to sequences of aggregate outcomes.

### 4.2 Household Jacobian

For household type $h$, the Jacobian maps aggregate variables to individual responses:

$$\mathbf{J}_h = \frac{\partial \mathbf{c}_h(\mathbf{S})}{\partial \mathbf{S}}$$

**Where:**
- $\mathbf{c}_h$ = Consumption response function for type $h$
- $\mathbf{S}$ = Sequence of aggregate states

**Code Location**: `HA-Fiscal-HANK-SAM.py` computes household Jacobians

### 4.3 Aggregate Jacobian

Aggregate consumption response:

$$\frac{\partial C}{\partial X} = \int \frac{\partial \mathbf{c}_i}{\partial X} d\mu(i)$$

**Where:** $X$ = Policy shock sequence (e.g., stimulus checks, UI extensions)

**Code Location**: `HA-Fiscal-HANK-SAM.py` aggregates household Jacobians

### 4.4 Policy Experiments

For policy shock $\Delta X_t$, consumption response is:

$$\Delta C_t = \sum_{s=0}^t \mathbf{J}_{t-s} \cdot \Delta X_s$$

**Code Location**: `HA-Fiscal-HANK-SAM.py` computes impulse responses

---

## 5. Computational Structure

### 5.1 Solution Algorithm: Endogenous Grid Method (EGM)

**Input**: State space grid, parameters, income process

**Output**: Consumption function $c_s(\mathbf{m})$ for each state $s$

**Algorithm** (simplified):
1. Start with terminal period: $c_T(\mathbf{m}) = \mathbf{m}$ (no bequests)
2. For $t = T-1, T-2, \ldots, 0$:
   - Define grid over end-of-period assets $\mathbf{a}$
   - Use Euler equation to find consumption $c(\mathbf{a})$
   - Compute endogenous grid: $\mathbf{m} = \mathbf{a} + c(\mathbf{a})$
   - Interpolate to get $c_t(\mathbf{m})$

**Code Location**: HARK's `ConsMarkovModel.solve()` (called by `EstimAggFiscalModel.solve()`)

### 5.2 Simulation Algorithm

**Input**: Solved consumption functions, initial distribution, income process

**Output**: Time series of individual and aggregate variables

**Algorithm**:
1. Initialize agents: $\{\mathbf{m}_{i,0}, \mathbf{p}_{i,0}, s_{i,0}\}$ from stationary distribution
2. For $t = 0, 1, 2, \ldots, T$:
   - Draw income shocks: $\xi_{i,t}, \psi_{i,t}$
   - Compute consumption: $\mathbf{c}_{i,t} = c_{s_{i,t}}(\mathbf{m}_{i,t})$
   - Update assets: $\mathbf{a}_{i,t} = \mathbf{m}_{i,t} - \mathbf{c}_{i,t}$
   - Draw state transitions: $s_{i,t+1} \sim \pi_{s_{i,t} \cdot}$
   - Update resources: $\mathbf{m}_{i,t+1} = R\mathbf{a}_{i,t} + \mathbf{y}_{i,t+1}$
   - Update permanent income: $\mathbf{p}_{i,t+1} = \psi_{i,t+1} \Gamma_e \mathbf{p}_{i,t}$
3. Aggregate: $C_t = \sum_i w_i \mathbf{c}_{i,t}$

**Code Location**: `EstimAggFiscalModel.simulate()`, `AggFiscalMAIN.py`

### 5.3 Calibration Algorithm

**Objective**: Find parameters $\theta$ to match empirical moments $m^{\text{data}}$

$$\min_\theta \| m(\theta) - m^{\text{data}} \|^2$$

**Moments targeted**:
- Wealth distribution (Lorenz curve points)
- MPC by wealth quartile
- Intertemporal MPC profile
- Education group shares

**Code Location**: 
- Splurge: `Estimation_BetaNablaSplurge.py`
- Discount factors: `EstimAggFiscalMAIN.py`

---

## 6. Key Mathematical Properties

### 6.1 Homogeneity Properties

**Consumption function**: Homogeneous of degree 1 in $(\mathbf{m}, \mathbf{p})$:
$$c_s(\lambda \mathbf{m}, \lambda \mathbf{p}) = \lambda c_s(\mathbf{m}, \mathbf{p})$$

**Implication**: Can normalize by permanent income: $c_s(m/p) = c_s(\mathbf{m}/\mathbf{p})$

**Code Location**: Used for computational efficiency in HARK

### 6.2 Stationarity

**Stationary distribution**: Exists under certain conditions (boundedness, ergodicity)

**Code Location**: Approximated by long simulation in `EstimAggFiscalMAIN.py`

### 6.3 Aggregate Demand Feedback

**AD function** (active in recession):
$$AD(C) = \left(\frac{C}{\tilde{C}}\right)^\kappa$$

**Modified income**:
$$\mathbf{y}_{AD} = AD(C) \cdot \mathbf{y}$$

**Fixed point**: $C^* = \int c_i(AD(C^*) \cdot \mathbf{y}_i) d\mu(i)$

**Code Location**: `AggFiscalMAIN.py:computeAD()`, solved iteratively

---

## 7. Notation Index

| Symbol | Meaning | Domain/Type | Typical Value |
|--------|---------|-------------|---------------|
| $\mathbf{c}$ | Consumption | $\mathbb{R}_+$ | - |
| $\mathbf{c}_{sp}$ | Splurge consumption | $\mathbb{R}_+$ | $\varsigma \mathbf{y}$ |
| $\mathbf{c}_{opt}$ | Optimal consumption | $\mathbb{R}_+$ | $c_s(\mathbf{m})$ |
| $\mathbf{a}$ | End-of-period assets | $\mathbb{R}_+$ | $\mathbf{m} - \mathbf{c}$ |
| $\mathbf{m}$ | Market resources | $\mathbb{R}_+$ | Cash-on-hand |
| $\mathbf{y}$ | Income | $\mathbb{R}_+$ | $f(\mathbf{p}, s, \xi)$ |
| $\mathbf{p}$ | Permanent income | $\mathbb{R}_+$ | - |
| $s$ | Employment state | $\{0,1,2,3\}$ | - |
| $e$ | Education group | $\{d,h,c\}$ | - |
| $\beta$ | Discount factor | $[0.3, 1.0]$ | 0.72-0.99 |
| $\gamma$ | Risk aversion | $\mathbb{R}_+$ | 2.0 |
| $\varsigma$ | Splurge factor | $[0,1]$ | 0.249 |
| $R$ | Gross interest rate | $\mathbb{R}_+$ | 1.01 |
| $D$ | Death probability | $[0,1]$ | 1/160 |
| $\Gamma_e$ | Income growth | $\mathbb{R}_+$ | 1.004-1.005 |
| $\psi$ | Permanent shock | Lognormal | $\sigma=0.055$ |
| $\xi$ | Transitory shock | Lognormal | $\sigma=0.346$ |
| $\rho_b$ | UI replacement rate | $[0,1]$ | 0.70 |
| $\rho_{nb}$ | No-UI replacement rate | $[0,1]$ | 0.50 |
| $\pi_{ss'}$ | Transition probability | $[0,1]$ | Markov matrix |
| $\kappa$ | AD elasticity | $\mathbb{R}_+$ | 0.30 |
| $C$ | Aggregate consumption | $\mathbb{R}_+$ | - |
| $Y$ | Aggregate income | $\mathbb{R}_+$ | - |
| $V_s(\mathbf{m},\mathbf{p})$ | Value function | $\mathbb{R}$ | - |
| $c_s(\mathbf{m})$ | Consumption function | $\mathbb{R}_+$ | Solution to Bellman |
| $\mathbf{J}_h$ | Household Jacobian | Matrix | Sequence-space |

---

## 8. References for Mathematical Details

**Primary References**:
- **MODEL_SUMMARY.md**: Detailed model description with all equations
- **Paper**: Carroll et al. (2025) - Full mathematical exposition
- **HARK Documentation**: <https://hark.readthedocs.io/> - Computational methods

**Key Papers**:
- Auclert et al. (2021) - Sequence-space Jacobian methods
- Carroll (2006) - Endogenous Grid Method
- Kaplan & Violante (2014) - Two-asset HANK model

**Code Locations**:
- Core model: `Code/HA-Models/FromPandemicCode/EstimAggFiscalModel.py`
- Policy simulation: `Code/HA-Models/FromPandemicCode/AggFiscalModel.py`
- HANK/SAM: `Code/HA-Models/FromPandemicCode/HA-Fiscal-HANK-SAM.py`
- Parameters: `Code/HA-Models/FromPandemicCode/EstimParameters.py`

---

## 9. Equation-to-Code Cross-Reference

For quick lookup, here are key mathematical operations and their code locations:

**Value function solution** → `EstimAggFiscalModel.solve()` → calls HARK's `ConsMarkovModel.solve()`

**Consumption choice** → `AggFiscalModel.consumption()` → combines splurge + optimal

**Income process** → `EstimAggFiscalModel.getIncome()` → computes $\mathbf{y}$ from $\mathbf{p}$, $s$, shocks

**State transitions** → `EstimAggFiscalModel.simOnePeriod()` → draws $s' \sim \pi_{ss'}$

**Aggregation** → `AggFiscalMAIN.computeAggregate()` → sums over agents

**MPC computation** → `FiscalTools.computeMPC()` → numerical derivative

**Welfare calculation** → `Welfare.computeWelfare()` → solves for CEV

**Jacobian computation** → `HA-Fiscal-HANK-SAM.py` → sequence-space method

