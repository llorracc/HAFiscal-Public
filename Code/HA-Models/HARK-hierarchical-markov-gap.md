# Why HAFiscal Needed Custom Markov Infrastructure

## For HARK developers: a capability gap discovered during the HAFiscal project

**Date:** March 2026
**HARK version:** 0.17.0
**Repository:** `llorracc/HAFiscal-Latest`
**Relevant HARK modules:** `ConsMarkovModel.py`, `ConsAggShockModel.py`

---

## 1. Summary

The HAFiscal project studies fiscal policy multipliers (stimulus checks, UI
extensions, tax cuts) in a heterogeneous-agent model where individual agents
face idiosyncratic employment shocks whose transition dynamics depend on the
aggregate state of the economy (normal times vs. recession). Building this
model required approximately 500 lines of custom simulation infrastructure
that overrides core HARK methods — code that was hand-written by research
economists rather than software engineers, and is consequently fragile,
difficult to maintain, and was the source of multiple bugs during a recent
HARK version upgrade.

This document explains what HAFiscal needed, what HARK provides, why the
existing tools were insufficient, and what HARK would need to offer natively
so that future projects with similar requirements do not have to build their
own ad hoc solutions.

---

## 2. What HARK provides (as of 0.17.0)

HARK has two Markov-aware consumer types. Each handles one level of a
two-level problem, but they cannot be combined.

### 2.1 `MarkovConsumerType` (in `ConsMarkovModel.py`)

This type gives each agent an **idiosyncratic** Markov state. At each
simulation step, every agent independently draws a new state from a
transition matrix:

```python
# MarkovConsumerType.get_markov_states (simplified)
for t in range(self.T_cycle):
    markov_process = MarkovProcess(self.MrkvArray[t], seed=...)
    MrkvNow[right_age] = markov_process.draw(MrkvPrev[right_age])
self.shocks["Mrkv"] = MrkvNow
```

`shocks["Mrkv"]` is a **vector** of length `AgentCount` — each agent has
their own state. There is no concept of an economy-wide aggregate state that
is common to all agents.

### 2.2 `AggShockMarkovConsumerType` (in `ConsAggShockModel.py`)

This type provides an **aggregate** Markov state that is common to all
agents. The economy (a `CobbDouglasMarkovEconomy` market object) draws a
single macro state each period and passes it to all agents:

```python
# AggShockMarkovConsumerType.getMrkvNow
def getMrkvNow(self):
    return self.shocks["Mrkv"] * np.ones(self.AgentCount, dtype=int)
```

Here `shocks["Mrkv"]` is a **single integer**, broadcast to all agents.
Agents do not have individual Markov states — everyone in the same aggregate
state faces the same income distribution.

The `get_shocks` method on this class contains an explicit acknowledgment of
the incompatibility:

> *"Unfortunately, the get_shocks method for MarkovConsumerType cannot be
> used, as that method assumes that MrkvNow is a vector with a value for
> each agent, not just a single int."*

### 2.3 The two types are architecturally disconnected

`MarkovConsumerType` inherits from `IndShockConsumerType`.
`AggShockMarkovConsumerType` inherits from `AggShockConsumerType`, which
also inherits from `IndShockConsumerType` — but *not* from
`MarkovConsumerType`.

```
IndShockConsumerType
├── MarkovConsumerType          (per-agent Markov states)
└── AggShockConsumerType
    └── AggShockMarkovConsumerType  (economy-wide Markov state)
```

There is no type that combines both capabilities.

---

## 3. What HAFiscal needed

HAFiscal models a recession as an aggregate event that changes the dynamics
of individual employment. This requires a **hierarchical Markov structure**
with two levels:

### Micro level (per-agent, idiosyncratic)

Each agent occupies one of `num_base_MrkvStates = 4` individual states:

| State | Meaning |
|-------|---------|
| 0 | Employed |
| 1 | Unemployed, 2 quarters of UI benefits remaining |
| 2 | Unemployed, 1 quarter of UI benefits remaining |
| 3 | Unemployed, no benefits |

Transitions between these states are governed by a 4×4 matrix that depends
on the current aggregate state — job-loss rates are higher and unemployment
spells are longer during a recession.

### Macro level (economy-wide, aggregate)

The economy occupies a single aggregate state that applies to all agents
simultaneously. In the baseline (no experiment), this is just state 0
("normal times"). During a policy experiment, the macro state indexes a
time path through the experiment: normal, recession-quarter-1,
recession-quarter-2, ..., back to normal. With `num_experiment_periods = 20`,
this creates `2 × 21 = 42` macro states (normal/recession at each time
step).

The aggregate state is **not drawn per-agent** — it is set by the economy
object and is identical for all agents in a given period.

### The combined state

HAFiscal encodes the two levels into a single integer:

```python
Mrkv = num_base_MrkvStates * MacroMrkvNow + MicroMrkvNow
```

With 4 micro states and 42 macro states, the full state space has
`4 × 42 = 168` states. The solver needs a consumption function for each of
these 168 states, which it gets by solving against the full 168×168
transition matrix built by taking a Kronecker-like product of the macro and
(state-conditional) micro transition matrices.

### Additional requirements

HAFiscal also needed:

- **State-conditional micro transitions:** The micro transition matrix
  changes depending on the macro state (different unemployment rates in
  normal vs. recession times, different benefit expiration rules under UI
  extension policies).

- **Sticky information:** Agents update their *perception* of the macro
  state only with probability `UpdatePrb` each period. An agent may be
  objectively in a recession but still consume as if in normal times because
  they have not yet "noticed" the recession. This requires tracking both
  the true Markov state and the perceived Markov state.

- **Fiscal experiment machinery:** The ability to hit all agents with a
  recession shock at a specific time, activate policy interventions (UI
  extensions, stimulus checks, tax cuts) that modify the Markov structure
  mid-simulation, and compute paired counterfactuals (baseline vs.
  experiment) on the same panel of agents.

---

## 4. What HAFiscal had to build

Because no HARK type supports both aggregate and idiosyncratic Markov
states, HAFiscal overrides the core simulation lifecycle with custom methods
in its `AggFiscalType` class (which inherits from `MarkovConsumerType`):

### `get_markov_states` — Replaced entirely

HARK's version draws each agent's full state independently from a flat
transition matrix. HAFiscal replaces this with a two-step process:

```python
def get_markov_states(self):
    self.get_macro_markov_states()   # Broadcast economy state to all agents
    self.get_micro_markov_states()   # Draw individual transitions given macro state
    MrkvNow = self.num_base_MrkvStates * self.MacroMrkvNow + self.MicroMrkvNow
    self.shocks['Mrkv'] = MrkvNow.astype(int)
```

`get_macro_markov_states` sets `MacroMrkvNow` from `EconomyMrkvNow` (passed
by the market object). `get_micro_markov_states` draws from the appropriate
micro transition matrix conditional on the current macro state, using
`CondMrkvArrays[macro_state]`.

### `initialize_sim` — Bypassed

HARK's `MarkovConsumerType.initialize_sim` draws initial Markov states from
`MrkvInitDstn`, a flat distribution over the full state space. HAFiscal
bypasses this entirely, calling `IndShockConsumerType.initialize_sim`
directly and then setting initial micro states from the ergodic
unemployment distribution and macro states to "normal times."

### `get_states` — Extended

HAFiscal adds a sticky-information layer: the true Markov state is
decomposed into macro and micro components, and only the micro component
is updated unconditionally. The macro component of each agent's *perceived*
state is updated only if the agent's `update_draw` falls below `UpdatePrb`.

### `AggregateDemandEconomy` — Built from scratch

HARK's `CobbDouglasMarkovEconomy` manages the aggregate Markov state and
computes market-clearing prices via a Cobb-Douglas production function.
HAFiscal needed a different market structure — an aggregate demand feedback
channel where individual income depends on aggregate consumption — so it
built a custom `AggregateDemandEconomy` class (~280 lines) that manages the
experiment timeline, sets the economy-wide Markov state, and runs the
aggregate demand fixed-point iteration.

### `make_full_mrkv_array` — Custom transition matrix construction

HAFiscal builds the full 168×168 transition matrix from separate macro and
micro components via a Kronecker-like product, with the ability to swap in
different micro matrices (e.g., extended UI benefits) at specific time
periods within the experiment.

### Total custom code

Approximately 500 lines of simulation infrastructure in `AggFiscalModel.py`,
plus the market class, the transition matrix construction in `Parameters.py`,
and the experiment/shock machinery. This code was written by research
economists working under deadline pressure, and the recent HARK 0.14.1 →
0.17.0 upgrade revealed multiple subtle bugs in the interaction between
this custom code and HARK's internals (RNG synchronization, state
save/restore, Markov initialization).

---

## 5. What HARK would need to provide

For a project like HAFiscal to be buildable without custom simulation
infrastructure, HARK would need a consumer type that combines aggregate
and idiosyncratic Markov states. Concretely:

### A new `AggIndMarkovConsumerType` (or equivalent)

This type would accept:

- **`MicroMrkvArrays`**: A dictionary (or list) mapping each macro state to
  a micro transition matrix. `MicroMrkvArrays[macro_state]` is an
  `S_micro × S_micro` matrix governing individual transitions when the
  economy is in `macro_state`.

- **`MacroMrkvArray`** (optional): A macro transition matrix, if the type
  should draw its own aggregate states. Alternatively, the aggregate state
  could be set externally by a Market object (as in
  `AggShockMarkovConsumerType`).

The type would:

1. **Receive the aggregate state from a Market object** each period (or
   draw it from `MacroMrkvArray` if running standalone).

2. **Draw individual micro transitions** from `MicroMrkvArrays[macro_state]`
   for each agent, given their current micro state.

3. **Expose both levels as attributes:** `self.MacroMrkvNow` (integer,
   common to all agents) and `self.MicroMrkvNow` (vector, per-agent),
   alongside the combined `self.shocks['Mrkv']` for solver compatibility.

4. **Build the flat transition matrix automatically** by taking the
   Kronecker-like product of `MacroMrkvArray` and the state-conditional
   `MicroMrkvArrays`, for use by the solver. The solver already handles
   flat Markov chains of arbitrary size; it does not need to know about
   the hierarchical structure.

5. **Support state-conditional income distributions and parameters:**
   `IncShkDstn[macro_state][micro_state]`, `Rfree[combined_state]`,
   `PermGroFac[combined_state]`, etc. — as the existing solver already
   expects.

### Corresponding Market class support

The `Market` base class (or a subclass like `CobbDouglasMarkovEconomy`)
would need to:

- Maintain a `MacroMrkvNow` attribute and pass it to agents via `sow_vars`.
- Support time-varying macro transition matrices (for experiments that
  change the macro dynamics at specific periods).

### What this would eliminate

With such a type, HAFiscal's custom `get_markov_states`,
`get_macro_markov_states`, `get_micro_markov_states`, `initialize_sim`
bypass, and the manual `Mrkv = num_base * Macro + Micro` encoding/decoding
could all be replaced by standard HARK calls. The experiment-specific
machinery (recession shocks, policy activation) and the sticky-information
layer would still require project-specific code, but the foundational
Markov simulation infrastructure would come from HARK.

---

## 6. A related gap on the solver side

This document focuses on the simulation-phase gap (how agents' Markov
states evolve during simulation). There is a separate but related gap on
the solver side.

HARK's `solve_ConsAggMarkov` solver computes consumption functions in an
economy with aggregate Markov states, but it assumes a Cobb-Douglas
production function with market-clearing prices (`Rfunc`, `wFunc`). HAFiscal
needed a solver where individual income depends on aggregate consumption
through a reduced-form aggregate demand feedback channel (`ADFunc`), not on
capital-to-labor ratios. This required a custom solver
(`solve_agg_cons_markov_alt`) that adds an aggregate consumption dimension
(`Cgrid`) to the consumption function, making it a function of both
individual resources `m` and aggregate consumption `C`.

Generalizing the solver to support pluggable aggregate feedback mechanisms
(beyond Cobb-Douglas) would be a valuable but separate enhancement. The
Markov hierarchy gap described in this document is independent of the solver
gap and could be addressed first.

---

## 7. Conclusion

The combination of economy-wide aggregate states and agent-level
idiosyncratic states — where individual transition probabilities depend on
the aggregate state — is a standard feature of modern macroeconomic models.
HARK's current architecture splits this into two incompatible types, forcing
users to build fragile custom infrastructure. A native hierarchical Markov
type would make HARK significantly more useful for the class of
heterogeneous-agent macro models (fiscal policy, business cycle analysis,
state-dependent unemployment dynamics) that motivate much of the HARK
project's reason for being.
