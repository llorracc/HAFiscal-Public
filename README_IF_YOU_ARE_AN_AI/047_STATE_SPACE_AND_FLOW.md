# State Space and Computational Flow for AI Systems

**Purpose**: Document the state space structure, state transitions, and computational flow of mathematical operations.

**Last Updated**: 2025-12-31

---

## 1. State Space Structure

### 1.1 Individual Agent State

**State Vector:**
$$\mathbf{s}_i = (\mathbf{m}_i, \mathbf{p}_i, s_i, e_i, \beta_i)$$

**Components:**
- **$\mathbf{m}_i \in \mathbb{R}_+$**: Market resources (cash-on-hand) = assets + current income
- **$\mathbf{p}_i \in \mathbb{R}_+$**: Permanent income level (normalized base income)
- **$s_i \in \{0,1,2,3\}$**: Employment/benefit state (Markov state)
- **$e_i \in \{d,h,c\}$**: Education group (dropout, highschool, college)
- **$\beta_i \in [0.3, 1.0]$**: Discount factor (heterogeneous within education group)

**Code Location**: Stored in HARK `AgentType` objects
- `mNrm` = Normalized market resources ($\mathbf{m}/\mathbf{p}$)
- `pLvl` = Permanent income level ($\mathbf{p}$)
- `state_now` = Current Markov state ($s$)
- Education and discount factor are type-level (not state variables, but agent characteristics)

### 1.2 Employment States (Markov Chain)

**State Space:** $\{0, 1, 2, 3\}$

| State | Description | Income Level |
|-------|-------------|--------------|
| 0 | Employed | $\xi \cdot \mathbf{p}$ (with transitory shock) |
| 1 | Unemployed, UI quarter 1 | $\rho_b \cdot \mathbf{p}$ (70% replacement) |
| 2 | Unemployed, UI quarter 2 | $\rho_b \cdot \mathbf{p}$ (70% replacement) |
| 3 | Unemployed, no UI | $\rho_{nb} \cdot \mathbf{p}$ (50% replacement) |

**State Transitions:**

**Normal Times:**
- $0 \to 1$: Probability $\pi_{eu}^e$ (education-specific job loss)
- $1 \to 2$: Probability $1 - \pi_{ue}$ (continue unemployment)
- $1 \to 0$: Probability $\pi_{ue} = 2/3$ (find job)
- $2 \to 3$: Probability $1 - \pi_{ue}$ (benefits expire)
- $2 \to 0$: Probability $\pi_{ue} = 2/3$ (find job)
- $3 \to 0$: Probability $\pi_{ue} = 2/3$ (find job)
- $3 \to 3$: Probability $1 - \pi_{ue}$ (stay unemployed)

**Recession:**
- Job loss probabilities double: $\pi_{eu}^e \to 2\pi_{eu}^e$
- Job finding probability drops: $\pi_{ue} = 2/3 \to 0.25$

**Code Location**: 
- Transition matrix: `EstimParameters.py` defines `MarkovArray`
- State evolution: `EstimAggFiscalModel.simOnePeriod()` draws new state

### 1.3 Aggregate State

**Aggregate State Vector:**
$$\mathbf{S}_t = (C_t, Y_t, \text{recession}_t, t)$$

**Components:**
- **$C_t$**: Aggregate consumption at time $t$
- **$Y_t$**: Aggregate income at time $t$
- **$\text{recession}_t \in \{0,1\}$**: Recession indicator
- **$t$**: Time period

**Code Location**: `AggFiscalMAIN.py` tracks aggregate state

---

## 2. State Evolution (Flow Diagram)

### 2.1 One-Period Agent State Transition

```
Time t state: (m_t, p_t, s_t, e, β)
        ↓
  1. Draw income shocks: ξ_t, ψ_t
        ↓
  2. Compute income: y_t = f(p_t, s_t, ξ_t)
        ↓
  3. Compute consumption: c_t = c_s(m_t) + ς·y_t
        ↓
  4. Update assets: a_t = m_t - c_t
        ↓
  5. Draw state transition: s_{t+1} ~ π_{s_t·}
        ↓
  6. Update permanent income: p_{t+1} = ψ_t·Γ_e·p_t
        ↓
  7. Update market resources: m_{t+1} = R·a_t + y_{t+1}
        ↓
Time t+1 state: (m_{t+1}, p_{t+1}, s_{t+1}, e, β)
```

**Code Location**: `EstimAggFiscalModel.simOnePeriod()` implements this flow

### 2.2 Computational Flow: Model Solution

```
1. Initialize agent types (education × discount factor)
        ↓
2. Set up income process (shock distributions, Markov transitions)
        ↓
3. Solve value function (EGM):
   For each state s:
     a. Define grid over assets a
     b. Use Euler equation: u'(c) = βRE[u'(c')]
     c. Find consumption c(a) at each grid point
     d. Compute endogenous grid: m = a + c(a)
     e. Interpolate to get c_s(m)
        ↓
4. Simulate economy:
   For each period t:
     a. Draw shocks (ξ, ψ) for all agents
     b. Compute income y_i for each agent
     c. Evaluate consumption function: c_i = c_{s_i}(m_i) + ς·y_i
     d. Update state (a, m, p, s) for all agents
     e. Aggregate: C_t = Σ w_i·c_i
        ↓
5. Compute statistics (MPCs, multipliers, welfare)
```

**Code Location**: 
- Solution: `EstimAggFiscalModel.solve()`
- Simulation: `AggFiscalMAIN.py` orchestrates simulation loop

---

## 3. Function Dependencies

### 3.1 Consumption Function Dependencies

**Consumption function:** $c_s(\mathbf{m})$ depends on:
- State $s$ (employment/benefit status)
- Market resources $\mathbf{m}$
- Discount factor $\beta$ (via value function)
- Income process parameters (via expectations)

**Computed from:**
- Value function $V_s(\mathbf{m}, \mathbf{p})$ (via EGM)
- Euler equation (first-order condition)

**Used by:**
- Simulation: `simOnePeriod()` evaluates $c_s(\mathbf{m})$
- Policy experiments: Consumption response to shocks

### 3.2 Income Function Dependencies

**Income:** $\mathbf{y} = f(\mathbf{p}, s, \xi)$ depends on:
- Permanent income $\mathbf{p}$
- Employment state $s$
- Transitory shock $\xi$

**Computed from:**
- Permanent income evolution: $\mathbf{p}' = \psi' \Gamma_e \mathbf{p}$
- State-dependent replacement rates ($\rho_b$, $\rho_{nb}$)
- Transitory shock distribution

**Used by:**
- Consumption: $\mathbf{c}_{sp} = \varsigma \mathbf{y}$
- Budget constraint: $\mathbf{m}' = R\mathbf{a} + \mathbf{y}'$

### 3.3 Aggregation Dependencies

**Aggregate consumption:** $C = \int \mathbf{c}_i d\mu(i)$ depends on:
- Individual consumption $\mathbf{c}_i$ for all agents
- Agent distribution $\mu$ (education groups, discount factors, wealth distribution)

**Computed from:**
- Individual consumption functions evaluated at agent states
- Agent weights (population shares)

**Used by:**
- Aggregate demand feedback: $AD(C)$
- Policy multiplier calculations
- Welfare aggregation

---

## 4. Computational Graph

### 4.1 Forward Pass (Simulation)

```
Input: Initial distribution of agents {s_i,0}
       Policy shocks {ΔX_t}
       Parameters θ

For t = 0 to T:
  For each agent i:
    p_i,t → [perm shock ψ] → p_i,t+1
    (p_i,t, s_i,t) → [trans shock ξ] → y_i,t
    m_i,t → [cons function c_s] → c_i,t
    (m_i,t, c_i,t) → [budget] → a_i,t
    (a_i,t, y_i,t+1) → [budget] → m_i,t+1
    s_i,t → [Markov π] → s_i,t+1
  
  Aggregate: {c_i,t} → C_t
  AD feedback: C_t → AD(C_t) → modify {y_i,t+1}
  
Output: Time series {C_t}, {Y_t}, individual paths
```

### 4.2 Backward Pass (Solution)

```
Input: Terminal condition V_T(m) = 0 (no bequests)
       Parameters θ
       Income process

For t = T-1 down to 0:
  For each state s:
    For each asset grid point a:
      Compute expected continuation value E[V_{t+1}]
      Use Euler equation: u'(c) = βRE[u'(c')]
      Solve for c(a)
      Compute endogenous grid: m = a + c(a)
    Interpolate: c_s(m) from grid points
    
Output: Consumption functions {c_s(m)} for all states
```

---

## 5. Key Invariants and Properties

### 5.1 Homogeneity

**Property**: Consumption function is homogeneous of degree 1:
$$c_s(\lambda \mathbf{m}, \lambda \mathbf{p}) = \lambda c_s(\mathbf{m}, \mathbf{p})$$

**Implication**: Can normalize by permanent income:
$$c_s(\mathbf{m}/\mathbf{p}) = c_s(\mathbf{m})/\mathbf{p}$$

**Code Usage**: HARK uses normalized variables (`mNrm`, `cNrm`) for computational efficiency

### 5.2 Budget Balance

**Invariant**: Assets evolve according to:
$$\mathbf{a}_t = \mathbf{m}_t - \mathbf{c}_t$$
$$\mathbf{m}_{t+1} = R \mathbf{a}_t + \mathbf{y}_{t+1}$$

**Code Check**: `EstimAggFiscalModel.simOnePeriod()` enforces this

### 5.3 No Borrowing

**Constraint**: $\mathbf{a}_t \geq 0$ (no borrowing allowed)

**Implementation**: HARK's `KinkedRconsumerType` sets borrowing rate to infinity

---

## 6. State Space Dimensions

### 6.1 Continuous Dimensions

- **Market resources**: $\mathbf{m} \in [0, \infty)$ (practical upper bound ~$10^6$ in normalized units)
- **Permanent income**: $\mathbf{p} \in (0, \infty)$ (grows over time)
- **Discount factor**: $\beta \in [0.3, 1.0]$ (discretized to 7 types per education)

### 6.2 Discrete Dimensions

- **Employment state**: $s \in \{0,1,2,3\}$ (4 states)
- **Education**: $e \in \{d,h,c\}$ (3 groups)
- **Discount types**: 7 per education (discretized uniform distribution)
- **Total agent types**: $3 \times 7 = 21$ types

### 6.3 Grid Sizes

**EGM Solution:**
- Asset grid: ~200 points (HARK default)
- Market resources grid: Endogenous (computed from asset grid)
- State grid: 4 points (one per Markov state)

**Simulation:**
- Agents per type: 5,000
- Total agents: $21 \times 5,000 = 105,000$
- Time periods: 800 quarters (200 years)

---

## 7. State Initialization

### 7.1 Stationary Distribution

**Initial state**: Drawn from stationary distribution of the model

**Components:**
- Permanent income: From stationary distribution of permanent income process
- Market resources: From stationary distribution given permanent income
- Employment state: From stationary distribution of Markov chain

**Code Location**: `EstimAggFiscalMAIN.py` initializes agents

### 7.2 Burn-in Period

**Practice**: Simulate for burn-in periods before policy shock to ensure stationary distribution

**Code**: `AggFiscalMAIN.py` includes burn-in simulation

---

## 8. Policy Shock Integration

### 8.1 Shock Timing

**Policy shocks** are integrated into state evolution:

```
Normal flow:
  m_t → c_t → a_t → m_{t+1}

With policy shock ΔX_t:
  m_t → c_t → a_t → m_{t+1}
  ΔX_t → modifies y_{t+1} or adds to m_{t+1}
```

**Example (Stimulus Check)**:
- Adds to market resources: $\mathbf{m}_{t+1} = R\mathbf{a}_t + \mathbf{y}_{t+1} + \text{Check}_i$
- Amount depends on permanent income: $\text{Check}_i = f(\mathbf{p}_i)$

**Code Location**: `AggFiscalModel.getIncome()` adds policy transfers

### 8.2 State-Dependent Policies

**UI Extension**: Modifies Markov transition matrix
- Extends states 1-2 (with benefits) from 2 to 4 quarters
- Changes transition probabilities: $\pi_{ss'} \to \pi_{ss'}^{\text{extended}}$

**Code Location**: `EstimParameters.py` defines extended UI parameters

---

## 9. Code Structure Reference

### 9.1 State Storage

**Individual States:**
- HARK `AgentType` objects store: `mNrm`, `pLvl`, `state_now`
- Arrays store states for all agents in simulation

**Aggregate State:**
- `AggFiscalMAIN.py` tracks: `C_t`, `Y_t`, recession indicator

### 9.2 State Transitions

**Individual:**
- `EstimAggFiscalModel.simOnePeriod()`: Updates one agent's state
- `AggFiscalModel.simulate()`: Updates all agents' states

**Aggregate:**
- `AggFiscalMAIN.computeAggregate()`: Aggregates individual states

---

## 10. Related Documents

- **040_MATHEMATICAL_STRUCTURE.md**: Comprehensive mathematical framework
- **045_EQUATION_MAP.md**: Equation-to-code mapping
- **035_MODEL_SUMMARY.md**: Model description with equations
- **060_CODE_NAVIGATION.md**: Code structure guide

