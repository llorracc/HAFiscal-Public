# Recession macro-state schema (G-03)

**Status:** DRAFT (created by `plans/20260611_doloplus-orchestrator-spec.md` P1)
**Normative owner:** `HAFiscal-doloplus-orchestrator.md` §5 (prose); this file is the
machine-facing schema of the hierarchical Markov-state machinery the dolo-plus stage
receives as `MrkvArray` / `RecState_of_z`.

---

## 1. Flat encoding

```
z = J·MacroMrkv + MicroMrkv        # AggFiscalModel.py::AggFiscalType.get_markov_states
MacroMrkv = z // J ;  MicroMrkv = z % J
RecState(z) = (z // J) % 2 == 1    # parity rule; mill_rule, solve_agg_cons_markov_alt
```

`J = num_base_MrkvStates` (`EstimParameters.py`): **6** under
`HAFISCAL_UI_STATE_ENCODING='bug_fix'` (default), **4** under `'legacy'`
(`HAFISCAL_QE_FIDELITY=1` implies legacy).

### 1.1 Micro index map (J = 6)

| micro | label | income (normal policy) |
|---|---|---|
| 0 | `e` employed | `θ·ADF` (+ TaxCut factor in tax-cut states) |
| 1 | `u1Q` | `IncUnemp = 0.7` |
| 2 | `u2Q` | `IncUnemp = 0.7` |
| 3 | `u3Q` | `IncUnempNoBenefits = 0.5`; `0.7` iff UI-extension AND RecState(z) |
| 4 | `u4Q` | same rule as u3Q |
| 5 | `noBen` (X) | `IncUnempNoBenefits = 0.5` |

(`AggFiscalType.hit_with_recession_shock` BUG-043 override block; J = 4 legacy drops
u3Q/u4Q and delivers UI via the freeze-window `transition_ub=False` arrays.)

## 2. Macro chain

Builder: `Parameters.py::make_macro_mrkv_array_recession(Rspell,
num_experiment_periods)`. With N = `num_experiment_periods`:

- **2(N+1) macro states**, indexed 0..2N+1, in (normal, recession) pairs:
  macro 2k = normal at experiment-clock k, macro 2k+1 = recession at clock k.
- Pair-local transition: `[[1, 0], [1−R_persist, R_persist]]`,
  `R_persist = 1 − 1/Rspell` (Rspell = 6 production; `Rspell_4` sensitivity: 4).
  Recession at clock k continues into recession at clock k+1 w.p. R_persist, else
  recovers to normal at clock k+1. Last pair wraps to pair 0 (absorbing normal).
- Sizes: Baseline N = 20 → 42 macro / 252 flat (J=6); Reduced & HS_Only N = 10 →
  22 macro / 132 flat. `max_recession_duration` = 21 / 11
  (`Parameters.py::return_parameters`).

## 3. Conditional micro arrays

`Parameters.py::make_cond_mrkv_arrays_recession` returns a list of length 2(N+1),
alternating `[normal, recession, normal, recession, ...]`, each entry a J×J
`small_MrkvArray(e, u, ub)`:

```
U_persist = 1 − 1/Uspell
E_persist = 1 − Urate·(1−U_persist)/(1−Urate)     # math-derive-appendix (emp-persist)
```

Normal columns use (`Urate_normal_e`, `Uspell_normal = 1.5`); recession columns use
(`Urate_recession = 2·Urate_normal_e`, `Uspell_recession = 4`). The full flat chain
is assembled by `Parameters.py::make_full_mrkv_array` via HARK's
`make_hierarchical_mrkv_array`. Scenario selection:
`AggFiscalType.update_mrkv_array(shock_type)` /
`AggregateDemandEconomy.switch_shock_type`.

| shock_type | macro array | conditional arrays |
|---|---|---|
| `base` | 1 macro state | `[MrkvArray_base]` |
| `recession`, `recessionCheck`, `recessionTaxCut`, plus non-recession policy variants | `MacroMrkvArray_recession` | alternating normal/recession |
| `recessionUI` | same | legacy: UI freeze-window arrays (`transition_ub=False`); bug_fix: identical to recession (policy moves to income; BUG-050 caveat for the Step-5 multiplier path) |

## 4. Imposed macro paths (`EconomyMrkv_init`)

The macro path is deterministic input to
`AggregateDemandEconomy.run_experiment`; only micro transitions are stochastic.
Conventions (`Simulate.py::run_experiments_all_recessions`,
`welfare6_scenario.py::_prob_weighted_rec`,
`AggregateDemandEconomy.solve_ad_recession`):

| path | sequence |
|---|---|
| no-recession policy | `[2, 4, ..., 2N] + [0]*20` |
| recession, duration d+1 | `[2, 4, ..., 2N]` with first d+1 entries +1, then `[0]*20` |
| AD training (worst case) | `[3, 5, ..., 2N+1] + [1]*12 + [0]*...` |

Initial hit: `AggFiscalType.hit_with_recession_shock` jumps every agent's macro
index to 3 (recession scenarios) or 2 (non-recession policy scenarios) and moves
employed agents to u1Q w.p. `(U_rec − U_norm)/(1 − U_norm)`.

## 5. Duration weighting

Reported recession aggregates are probability-weighted across durations:

```
P(dur = t+1) = R_persist^t · (1 − R_persist)      # math-derive-appendix (recession-duration)
last bucket  = 1 − Σ previous                     # welfare6_scenario.py::_prob_weighted_rec
```

(`Simulate.py` `recession_prob_array`; `Welfare.py::Welfare_Results`.)

## 6. Calibration fields (validation contract)

A conforming recession-state configuration MUST specify, with production values:

| field | production | reduced | source |
|---|---|---|---|
| `num_experiment_periods` N | 20 | 10 | `Parameters.py::return_parameters` |
| `max_recession_duration` | 21 | 11 | same |
| `Rspell` | 6 | 6 | same |
| `Urate_normal` (D/H/C) | 0.085/0.044/0.027 | same | `EstimParameters.py` |
| `Urate_recession` | 2× normal | same | `Parameters.py::return_parameters` |
| `Uspell_normal` / `Uspell_recession` | 1.5 / 4 | same | `EstimParameters.py` / `Parameters.py` |
| `J` (micro states) | 6 (`bug_fix`) | 6 | `EstimParameters.py` |
| flat `StateCount` = 2(N+1)·J | 252 | 132 | derived; must equal `len(MrkvArray)` per scenario |

Invariants: row-stochastic macro and micro arrays; `RecState_of_z` parity table of
length 2(N+1)·J; conditional-array list length exactly 2(N+1), alternating
normal/recession.
