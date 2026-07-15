# How the Aggregate Demand Channel Works in HAFiscal

## The Question

> What I don't understand from reading the paper is how the "aggregate demand" channel works. Equations 7 and 8 give the math, but don't connect it back to the model. Do the agents *anticipate* the aggregate demand channel?
>
> How is it actually determined during the simulation? Aggregate C_t depends on individual c_{it}, which depends on y_{it}, which depends on AD(C_t), which obviously depends on C_t. So do you solve for the fixed point each period?

## Short Answer

**Yes, agents anticipate the AD channel.** The circularity is resolved via a **Krusell-Smith (1998) style outer iteration** — not by solving a within-period fixed point.

## The Three Key Objects

### 1. CRule — Agent Beliefs About Aggregate Consumption Dynamics

Agents hold beliefs about how the aggregate consumption ratio evolves over time. These beliefs are represented by `CRule` objects (in `AggFiscalModel.py`):

```python
class CRule(Model):
    '''
    A class to represent agent beliefs about aggregate consumption dynamics.
    '''
    def __init__(self, intercept, slope):
        self.intercept = intercept
        self.slope = slope

    def __call__(self, Cnow):
        Cnext = self.intercept + self.slope * (Cnow - 1.0)
        return Cnext
```

So agents believe: **Cratio\_{t+1} = intercept + slope × (Cratio\_t − 1)**, where Cratio\_t = C\_t / C\_t^{baseline}.

There is one CRule per (from-state, to-state) Markov pair. The full collection `CFunc[i][j]` gives the perceived law of motion for Cratio when transitioning from Markov state `i` to state `j`.

### 2. ADFunc — The Aggregate Demand Function

This maps the aggregate consumption ratio to an income multiplier:

```python
self.ADFunc = lambda C, RecState : C ** (RecState * self.ADelasticity)
```

So `AggDemandFac = Cratio^(ADelasticity)` during recessions (RecState=1), and `= 1` in normal times (RecState=0). This is the function corresponding to equations 7–8 in the paper.

### 3. 2D Consumption Functions

Agents' optimal policy depends on both individual wealth **and** the aggregate state:

```
cFunc(mNrm, Cratio)
```

This is a two-dimensional function — the second argument is the current aggregate consumption ratio.

## How Agents Internalize the AD Channel When Solving

In the one-period solver (`solve_agg_cons_markov_alt`), when computing the value of ending next period in combined Markov state `j`:

1. The solver uses `ADFunc` to compute how aggregate consumption scales income:

   ```python
   AggState = np.floor(j / num_base_MrkvStates)
   RecState = AggState % 2 == 1
   AggDemandFacnext_array = ADFunc(Cnext_array, RecState)
   TranShkValsNext_tiled = AggDemandFacnext_array * TranShkValsNext_tiled_noAD
   ```

2. The solver uses `CFunc[i][j]` to forecast next period's Cratio and weight the end-of-period marginal value:

   ```python
   for j in range(StateCount):
       if MrkvArray[i, j] > 0.:
           Cnext = CFunc[i][j](Cgrid)
           Cnext_tiled = np.tile(np.reshape(Cnext, (Ccount, 1)), (1, aCount))
           temp = EndOfPrdvPfunc_cond[j](aNrmNow_tiled, Cnext_tiled)
           EndOfPrdvP += MrkvArray[i, j] * temp
   ```

**Agents fully internalize the AD channel**: they know that aggregate consumption affects their income (via `ADFunc`), and they have beliefs about how aggregate consumption evolves (via `CFunc`).

## During Simulation: No Within-Period Fixed Point

During simulation, there is **no within-period iteration**. The economy's `mill_rule` runs sequentially each period:

1. **Aggregate** last period's individual consumption into `AggCons`.
2. **Compute** the realized `Cratio = AggCons / base_AggCons`.
3. **Predict** next period's `CratioNext` using the perceived law of motion `CFunc`.
4. **Compute** next period's `AggDemandFacNext = ADFunc(CratioNext, RecState)`.
5. **Sow** `CratioNext` and `AggDemandFacNext` to all agents.

```python
def mill_rule(self, cLvl_splurge):
    # ...
    AggCons = np.sum(cLvl_all_splurge)
    self.Cratio = AggCons / self.base_AggCons[self.Shk_idx]
    CratioNext = self.CFunc[...][...](self.Cratio)
    # ...
    AggDemandFacNext = self.ADFunc(CratioNext, RecState)
```

Agents then take `AggDemandFac` as given when computing their market resources:

```python
self.state_now["mNrm"] = self.state_now["bNrm"] + self.shocks['TranShk'] * self.AggDemandFac
```

There is no iteration within a period — the economy sows aggregates, agents respond, and the realized aggregate consumption is only used to update the *next* period's sown values.

## Where the Fixed Point IS Solved: The Outer Krusell-Smith Loop

The circularity is resolved in `solve_ad_recession`, which implements a classic Krusell-Smith iteration:

```
for iteration in range(num_max_iterations):
    1. Run the full simulation with current CFunc beliefs.
    2. Observe the realized Cratio_hist from the simulation.
    3. Update MacroCFunc: set CRule intercepts to realized Cratio values.
    4. Dampen: Step_Cfunc = Old + step * (New − Old).
    5. Re-solve agents' problems with the updated CFunc.
    6. Check convergence of CFunc (norm of slope + intercept changes).
    7. If converged, stop. Otherwise, repeat.
```

Concretely, the realized `Cratio_hist` from the simulation is read off and plugged directly into CRule intercepts (with slope = 0, since the macro state sequence is deterministic given the experiment timeline):

```python
MacroCFunc[0][3] = CRule(recession_results['Cratio_hist'][0], 0.0)
for j in range(self.num_experiment_periods - 1):
    MacroCFunc[2*j+3][2*j+5] = CRule(recession_results['Cratio_hist'][j+1], 0.0)
MacroCFunc[2*self.num_experiment_periods+1][1] = CRule(
    recession_results['Cratio_hist'][self.num_experiment_periods], 0.0)
MacroCFunc[1][1] = CRule(
    np.mean(recession_results['Cratio_hist'][num_experiment_periods+1:num_experiment_periods+10]), 0.0)
```

Then dampened with a step size before being used in the next iteration:

```python
Step_Cfunc[ii][jj].slope     = Old[ii][jj].slope     + step * (New[ii][jj].slope     - Old[ii][jj].slope)
Step_Cfunc[ii][jj].intercept = Old[ii][jj].intercept + step * (New[ii][jj].intercept - Old[ii][jj].intercept)
```

At convergence, agents' beliefs about the Cratio path are consistent with the realized aggregate outcome.

## Summary

| Question | Answer |
|----------|--------|
| Do agents anticipate the AD channel? | **Yes.** Their consumption function is 2D: `cFunc(mNrm, Cratio)`. They know `ADFunc` and `CFunc`. |
| Is there a within-period fixed point? | **No.** Each period, `AggDemandFac` is sown to agents as a given; they respond; aggregate C is computed after the fact. |
| How is the circularity resolved? | **Krusell-Smith outer iteration.** Guess CFunc → solve → simulate → observe realized Cratio path → update CFunc → repeat until convergence. |
| What are agents' beliefs? | Linear rules: Cratio\_{t+1} = intercept + slope × (Cratio\_t − 1), one per (from-state, to-state) Markov pair. |
| Is it a rational expectations equilibrium? | At convergence, agents' beliefs about Cratio dynamics are consistent with the realized aggregate outcome — an approximate REE in the Krusell-Smith sense. |

## Key Source Files

- `Code/HA-Models/FromPandemicCode/AggFiscalModel.py` — `AggFiscalType`, `AggregateDemandEconomy`, `solve_agg_cons_markov_alt`, `CRule`
- `Code/HA-Models/FromPandemicCode/EstimAggFiscalModel.py` — Estimation variant with the same structure
