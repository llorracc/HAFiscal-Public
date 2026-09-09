# Equation Map for AI Systems

**Purpose**: Provide a searchable map between mathematical equations, their code implementations, and paper references.

**Last Updated**: 2025-12-31

**Usage**: Use this document to quickly locate where specific equations are implemented in code or referenced in the paper.

---

## Quick Reference Table

| Equation ID | Description | Paper Reference | Code Location | Mathematical Form |
|-------------|-------------|-----------------|---------------|-------------------|
| eq:model | Consumption decomposition | Eq. (1) | `AggFiscalModel.py:consumption()` | $\mathbf{c} = \mathbf{c}_{sp} + \mathbf{c}_{opt}$ |
| eq:splurge | Splurge consumption | Eq. (2) | `AggFiscalModel.py:consumption()` | $\mathbf{c}_{sp} = \varsigma \mathbf{y}$ |
| eq:bellman | Value function | Section 2.1 | `EstimAggFiscalModel.py` (via HARK) | $V_s = \max\{u(c) + \beta E[V']\}$ |
| eq:euler | Euler equation | Implicit (EGM) | `ConsMarkovModel.py` (HARK) | $u'(c) = \beta R E[u'(c')]$ |
| eq:budget | Budget constraint | Section 2.1 | `EstimAggFiscalModel.py` | $\mathbf{a} = \mathbf{m} - \mathbf{c}$, $\mathbf{m}' = R\mathbf{a} + \mathbf{y}'$ |
| eq:perm_income | Permanent income | Section 2.2 | `EstimAggFiscalModel.py:getIncome()` | $\mathbf{p}' = \psi' \Gamma_e \mathbf{p}$ |
| eq:income | Income realization | Section 2.2 | `EstimAggFiscalModel.py:getIncome()` | $\mathbf{y} = f(\mathbf{p}, s, \xi)$ |
| eq:aggregate | Aggregate consumption | Section 3 | `AggFiscalMAIN.py:computeAggregate()` | $C = \int \mathbf{c}_i d\mu$ |
| eq:ad_feedback | AD feedback | Section 4.5 | `AggFiscalMAIN.py:computeAD()` | $AD(C) = (C/\tilde{C})^\kappa$ |

---

## Detailed Equation Index

### Core Consumption Equations

#### eq:model - Consumption Decomposition

**Equation:**
$$\mathbf{c}_{i,t} = \mathbf{c}_{sp,i,t} + \mathbf{c}_{opt,i,t}$$

**Paper Reference**: Equation (1) in Model section

**Code Location**: 
- File: `Code/HA-Models/FromPandemicCode/AggFiscalModel.py`
- Method: `consumption()` (around line 150-200)
- Implementation: Adds `cSplurge` (from `getIncome()`) to `cOpt` (from consumption function)

**LaTeX Source**: `Equations/splurge.ltx`, also in `Subfiles/Model.tex` (line 33)

**Related Code**:
- Splurge component: `AggFiscalModel.getIncome()` computes $\varsigma \mathbf{y}$
- Optimal component: `EstimAggFiscalModel.solve()` provides consumption function

---

#### eq:splurge - Splurge Consumption

**Equation:**
$$\mathbf{c}_{sp,i,t} = \varsigma \cdot \mathbf{y}_{i,t}$$

**Paper Reference**: Equation (2) in Model section

**Code Location**:
- File: `Code/HA-Models/FromPandemicCode/AggFiscalModel.py`
- Method: `getIncome()` 
- Variable: `cSplurge = Splurge * yNow` (where `Splurge = 0.249`)

**Parameter Location**: `Code/HA-Models/FromPandemicCode/EstimParameters.py`
- `Splurge = 0.249` (estimated value)

**Estimation Code**: `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py`

---

### Dynamic Programming Equations

#### eq:bellman - Value Function (Bellman Equation)

**Equation:**
$$V_s(\mathbf{m}, \mathbf{p}) = \max_{\mathbf{c}} \left\{ u(\mathbf{c}) + \beta (1-D) \mathbb{E}\left[ V_{s'}(\mathbf{m}', \mathbf{p}') \mid s \right] \right\}$$

**Paper Reference**: Standard dynamic programming setup (Section 2.1)

**Code Location**:
- File: `Code/HA-Models/FromPandemicCode/EstimAggFiscalModel.py`
- Method: `solve()` calls HARK's `ConsMarkovModel.solve()`
- HARK implementation: `HARK/ConsumptionSaving/ConsMarkovModel.py`

**Solution Method**: Endogenous Grid Method (EGM)
- EGM implementation: `HARK/ConsumptionSaving/ConsIndShockModel.py`

**State Variables**:
- $\mathbf{m}$ = Market resources (cash-on-hand)
- $\mathbf{p}$ = Permanent income
- $s$ = Employment/benefit state

---

#### eq:euler - Euler Equation

**Equation:**
$$u'(\mathbf{c}_{opt}) = \beta (1-D) R \mathbb{E}\left[ u'(\mathbf{c}'_{opt}) \right]$$

**Where:** $u'(c) = c^{-\gamma}$ for CRRA utility

**Paper Reference**: First-order condition (implicit in EGM solution)

**Code Location**:
- EGM solver: `HARK/ConsumptionSaving/ConsIndShockModel.py`
- Called from: `EstimAggFiscalModel.solve()`

**Implementation Note**: EGM solves this equation without explicitly writing it out - uses the endogenous grid method to find consumption function directly.

---

#### eq:budget - Budget Constraints

**Equations:**
$$\mathbf{a}_{i,t} = \mathbf{m}_{i,t} - \mathbf{c}_{i,t}$$

$$\mathbf{m}_{i,t+1} = R \cdot \mathbf{a}_{i,t} + \mathbf{y}_{i,t+1}$$

$$\mathbf{a}_{i,t} \geq 0$$

**Paper Reference**: Section 2.1, budget constraint

**Code Location**:
- Asset update: `EstimAggFiscalModel.updateSolutionTerminal()` or `postsolve()`
- Resource evolution: `EstimAggFiscalModel.simOnePeriod()` updates `mNxt`
- Borrowing constraint: Enforced by HARK's `KinkedRconsumerType` (no borrowing: $R_{borrow} = \infty$)

**Key Variables**:
- `aNrm` = Normalized assets ($\mathbf{a}/\mathbf{p}$)
- `mNrm` = Normalized market resources ($\mathbf{m}/\mathbf{p}$)
- `Rfree` = Gross interest rate ($R = 1.01$)

---

### Income Process Equations

#### eq:perm_income - Permanent Income Evolution

**Equation:**
$$\mathbf{p}_{i,t+1} = \psi_{i,t+1} \cdot \Gamma_{e(i)} \cdot \mathbf{p}_{i,t}$$

**Where:**
- $\psi_{i,t+1} \sim \text{Lognormal}(0, \sigma_\psi^2)$, $\sigma_\psi = 0.0548$
- $\Gamma_e$ = Education-specific growth rate

**Paper Reference**: Section 2.2, permanent income process

**Code Location**:
- File: `Code/HA-Models/FromPandemicCode/EstimAggFiscalModel.py`
- Method: `simOnePeriod()` updates `pLvlNxt`
- Permanent shock: `PermShkStd = 0.0548` in `EstimParameters.py`

**Parameter Values** (from `EstimParameters.py`):
- `PermGroFac_d` = 1.0036 (dropout)
- `PermGroFac_h` = 1.0045 (highschool)
- `PermGroFac_c` = 1.0049 (college)

---

#### eq:income - Income Realization

**Equation:**
$$\mathbf{y}_{i,t} = \begin{cases}
\xi_{i,t} \cdot \mathbf{p}_{i,t} & \text{if employed (state 0)} \\
\rho_b \cdot \mathbf{p}_{i,t} & \text{if unemployed with UI (states 1-2)} \\
\rho_{nb} \cdot \mathbf{p}_{i,t} & \text{if unemployed without UI (state 3)}
\end{cases}$$

**Where:**
- $\xi_{i,t} \sim \text{Lognormal}(0, \sigma_\xi^2)$, $\sigma_\xi = 0.346$
- $\rho_b = 0.7$ (UI replacement rate)
- $\rho_{nb} = 0.5$ (no-UI replacement rate)

**Paper Reference**: Section 2.2, income by employment status

**Code Location**:
- File: `Code/HA-Models/FromPandemicCode/EstimAggFiscalModel.py`
- Method: `getIncome()` computes `yNow`
- State-dependent: Uses Markov state to determine replacement rate

**Parameters** (from `EstimParameters.py`):
- `TranShkStd = 0.346` (transitory shock std)
- UI replacement rates defined in parameter setup

---

### Aggregation Equations

#### eq:aggregate - Aggregate Consumption

**Equation:**
$$C_t = \int \mathbf{c}_{i,t} \, d\mu(i) = \sum_{h} w_h \sum_{i \in h} \mathbf{c}_{i,t}$$

**Where:**
- $h$ = Household type (education × discount factor)
- $w_h$ = Population weight for type $h$
- $\mu$ = Measure over agents

**Paper Reference**: Section 3, aggregation

**Code Location**:
- File: `Code/HA-Models/FromPandemicCode/AggFiscalMAIN.py`
- Method: `computeAggregate()` sums over simulated agents
- Weights: Uses population shares from `EstimParameters.py`

**Implementation**: Monte Carlo integration with 5,000 agents per type

---

#### eq:ad_feedback - Aggregate Demand Feedback

**Equation:**
$$AD(C_t) = \begin{cases}
\left(\frac{C_t}{\tilde{C}}\right)^\kappa & \text{if in recession} \\
1 & \text{otherwise}
\end{cases}$$

**Modified Income:**
$$\mathbf{y}_{AD,i,t} = AD(C_t) \cdot \mathbf{y}_{i,t}$$

**Where:**
- $\kappa = 0.3$ = Consumption elasticity of productivity
- $\tilde{C}$ = Steady-state consumption

**Paper Reference**: Section 4.5, aggregate demand extension

**Code Location**:
- File: `Code/HA-Models/FromPandemicCode/AggFiscalMAIN.py`
- Method: `computeAD()` computes AD multiplier
- Iterative solution: Solves for fixed point $C^* = \int c_i(AD(C^*) \mathbf{y}_i) d\mu$

**Parameter**: `AD_elasticity = 0.3` in parameter files

---

### Policy Equations

#### eq:stimulus_check - Stimulus Check Formula

**Equation:**
$$\text{Check}_i = \begin{cases}
\$1,200 & \text{if } \mathbf{p}_i < \$100,000 \\
\$1,200 \cdot \frac{\$150,000 - \mathbf{p}_i}{\$50,000} & \text{if } \$100,000 \leq \mathbf{p}_i \leq \$150,000 \\
0 & \text{if } \mathbf{p}_i > \$150,000
\end{cases}$$

**Paper Reference**: Section 4.1, stimulus check design

**Code Location**:
- File: `Code/HA-Models/FromPandemicCode/AggFiscalModel.py`
- Method: `getIncome()` adds `checkAmount` to income
- Calculation: Based on permanent income level `pLvl`

**Parameters**: Defined in policy experiment setup (check amount, phase-out thresholds)

---

### Welfare and MPC Equations

#### eq:mpc - Marginal Propensity to Consume

**Equation:**
$$MPC_{i,t} = \frac{\partial \mathbf{c}_{i,t}}{\partial \mathbf{y}_{i,t}}$$

**Aggregate MPC:**
$$MPC_t = \frac{\partial C_t}{\partial Y_t}$$

**Paper Reference**: Section 3.1, MPC calculation

**Code Location**:
- File: `Code/HA-Models/FromPandemicCode/FiscalTools.py`
- Method: `computeMPC()` computes numerical derivative
- Implementation: Compares consumption with/without income shock

---

#### eq:welfare - Welfare Measure (CEV)

**Equation:**
Find $\Lambda$ such that:
$$U(C \cdot (1+\Lambda)) = U(C + \Delta)$$

**Where:**
- $U(\cdot)$ = Lifetime utility
- $\Delta$ = Policy-induced consumption change
- $\Lambda$ = Consumption-equivalent variation (CEV)

**Paper Reference**: Section 5.1, welfare analysis

**Code Location**:
- File: `Code/HA-Models/FromPandemicCode/Welfare.py`
- Method: `computeWelfare()` solves for $\Lambda$
- Implementation: Root-finding to solve utility equality

---

### Sequence-Space Jacobian Equations

#### eq:jacobian_household - Household Jacobian

**Equation:**
$$\mathbf{J}_h = \frac{\partial \mathbf{c}_h(\mathbf{S})}{\partial \mathbf{S}}$$

**Where:**
- $\mathbf{c}_h$ = Consumption response function for household type $h$
- $\mathbf{S}$ = Sequence of aggregate states

**Paper Reference**: HANK section, uses Auclert et al. (2021) method

**Code Location**:
- File: `Code/HA-Models/FromPandemicCode/HA-Fiscal-HANK-SAM.py`
- Computes: Jacobian matrices mapping aggregate shocks to individual responses
- Output: `HA_Fiscal_Jacs.obj` (pickled Jacobian matrices)

---

#### eq:jacobian_aggregate - Aggregate Jacobian

**Equation:**
$$\frac{\partial C}{\partial X} = \int \frac{\partial \mathbf{c}_i}{\partial X} d\mu(i)$$

**Where:** $X$ = Policy shock sequence

**Code Location**:
- File: `Code/HA-Models/FromPandemicCode/HA-Fiscal-HANK-SAM.py`
- Aggregates: Household Jacobians to get aggregate responses
- Output: Impulse response functions for multipliers

---

## Parameter Value Reference

For quick lookup of parameter values used in equations:

| Parameter | Symbol | Value | Code Location |
|-----------|--------|-------|---------------|
| Splurge factor | $\varsigma$ | 0.249 | `EstimParameters.py: Splurge` |
| Risk aversion | $\gamma$ | 2.0 | `EstimParameters.py: CRRA` |
| Interest rate | $R$ | 1.01 | `EstimParameters.py: Rfree` |
| Death probability | $D$ | 1/160 | `EstimParameters.py: LivPrb = 1-1/160` |
| Permanent shock std | $\sigma_\psi$ | 0.0548 | `EstimParameters.py: PermShkStd` |
| Transitory shock std | $\sigma_\xi$ | 0.346 | `EstimParameters.py: TranShkStd` |
| UI replacement rate | $\rho_b$ | 0.7 | `EstimParameters.py` (UI parameters) |
| No-UI replacement rate | $\rho_{nb}$ | 0.5 | `EstimParameters.py` |
| AD elasticity | $\kappa$ | 0.3 | Parameter in `AggFiscalMAIN.py` |

---

## Equation Label Cross-Reference

This table maps LaTeX equation labels (if they exist) to the equations above:

| LaTeX Label | Equation ID | Location in Paper |
|-------------|-------------|-------------------|
| `\label{eq:model}` | eq:model | Model section, Equation (1) |
| (other labels) | (check LaTeX source) | (check paper) |

**Note**: The paper uses `\label{eq:model}` for the consumption decomposition. Other equations may not have explicit labels but are referenced by section number.

---

## Code Function → Equation Mapping

Reverse lookup: Given a code function, what equation does it implement?

| Code Function/Method | Equation ID | File |
|---------------------|-------------|------|
| `AggFiscalModel.consumption()` | eq:model, eq:splurge | `AggFiscalModel.py` |
| `EstimAggFiscalModel.solve()` | eq:bellman, eq:euler | `EstimAggFiscalModel.py` |
| `EstimAggFiscalModel.getIncome()` | eq:income, eq:perm_income | `EstimAggFiscalModel.py` |
| `AggFiscalMAIN.computeAggregate()` | eq:aggregate | `AggFiscalMAIN.py` |
| `AggFiscalMAIN.computeAD()` | eq:ad_feedback | `AggFiscalMAIN.py` |
| `FiscalTools.computeMPC()` | eq:mpc | `FiscalTools.py` |
| `Welfare.computeWelfare()` | eq:welfare | `Welfare.py` |
| `HA-Fiscal-HANK-SAM.py` (main) | eq:jacobian_household, eq:jacobian_aggregate | `HA-Fiscal-HANK-SAM.py` |

---

## How to Use This Map

1. **Find equation in paper** → Look up Equation ID in "Quick Reference Table" → Get code location
2. **Find code function** → Look up in "Code Function → Equation Mapping" → Get equation ID → See mathematical form
3. **Understand implementation** → Use Equation ID → Read "Detailed Equation Index" → See both math and code details

---

## Related Documents

- **040_MATHEMATICAL_STRUCTURE.md**: Comprehensive mathematical framework
- **035_MODEL_SUMMARY.md**: Model description with equations
- **CONCEPT_GLOSSARY.md**: Concept definitions
- **060_CODE_NAVIGATION.md**: Code structure guide

