# Compute the UI-expiry validation panels from the transition matrix, not from a simulated panel

**Status:** PROPOSED (owner charge 2026-09-06 ~05:00, following the observation that settled it:
"can't this be measured using the TM itself rather than MC, just by comparing the consumption of
people in ordinary times who are in the states 'Unemployed 1 Quarter', 2 qtrs, 3 qtrs etc, in which
no MC is necessary?").
**Owner instruction:** build the TM version, test it thoroughly against the MC version, and once it
passes all tests, wire it into the default workflow.

## 0. What the exhibits are, and why this is the right change

Two panels of the paper's model validation, both drawn by
`Code/HA-Models/FromPandemicCode/EvalConsDropUponUILeave.py`:

* **`UnempSpell_Dynamics.pdf`** — "Spending upon UI benefit expiry", the right panel of
  *Model validation for nontargeted spending patterns* (`Figures/untargetedMoments.tex`).
* **`UIextension_CompSplurge0.pdf`** — the same measurement with the splurge-zero model beside the
  estimated-splurge one, in *Validation moments in models with and without splurge*
  (`Figures/untargetedMoments_wSplZero.tex`).

These are NON-TARGETED moments: the model was never fitted to them, so agreement is evidence. The
splurge-comparison panel is the sharper of the two — the case for the splurge is that a model
without it cannot reproduce the spending drop when benefits run out, and this is where the reader
sees it.

**What the generator computes** (read from the code, not inferred): for every household episode that
ENTERS micro state 3 and then remains there at least three quarters, take the window from three
quarters before entry to two after; normalise consumption and income by that household's own
permanent income three quarters before entry; average across all such episodes. Six points per
series, three series (consumption, income, wealth-below-threshold).

**Micro state 3 is benefit exhaustion.** With `UBspell_normal = 2`, `small_MrkvArray` lays the
chain out as 0 = employed, 1 = unemployed quarter 1 (benefits), 2 = unemployed quarter 2 (benefits),
3 = unemployed, benefits EXHAUSTED (an absorbing-until-reemployment state). So "enters state 3" is
literally "benefits just ran out", which is what the panel is named for.

**Why TM rather than MC.** Every operation above is a conditional expectation over (micro state,
assets) — entering a state, surviving three quarters in it, and the three quarters before entry are
all reachable by propagating a conditional distribution through the same kernel the TM already
builds. Doing it by simulation buys nothing and costs a great deal:

1. **Sampling noise on a validation exhibit.** The panel version's six points are episode means over
   however many episodes a finite panel happens to produce.
2. **It drags in the whole panel-quality question.** An MC run must carry its TM-a companion and
   drift gate (standing rule). On 2026-09-06 the baseline-only pass ran in 37 s and then FAILED that
   gate: `[drift agent_2] Lorenz p80 drift −4.466pp` against ±3.00pp — the college group, i.e. the
   heavy-tail sampler limit of BUG-092 (E[p] shortfall shrinks only as N^−0.2). Nothing is wrong with
   the model; a finite equal-weight panel simply cannot represent that tail. Building a VALIDATION
   figure on a panel known to misstate the wealth distribution at p80 defeats its purpose.
3. **It is the only reason these two exhibits have been pending since August.** Not missing wiring.

**And the premise is already established.** By the time this runs, the TM engine is the production
multiplier engine (default since 2026-06-23 after the matched TM≡MC re-validation, β to ≤0.06 % at
~28× the speed), and TM-vs-MC agreement on everything both can measure is the standing certification.
So a TM computation of a conditional mean needs no new licence; the MC version is the cross-check,
not the reference.

## 1. Deliverable

`Code/HA-Models/ui_expiry_profile.py` — a NEW module (repo rule: new utilities live in
`Code/HA-Models/`, not `FromPandemicCode/`) exposing

```python
def ui_expiry_profile(agent, *, dist_aGrid_count=None, q_method=None, interpretation=None,
                      lead=3, lag=2, min_spell=3):
    """Episode-average normalized consumption / income / wealth around benefit exhaustion,
    computed analytically from the a-indexed transition matrix. Returns the same three
    length-(lead+lag+1) vectors EvalConsDropUponUILeave.calc_C_I_paths_for_Unemp returns."""
```

plus a thin adapter so `EvalConsDropUponUILeave.py` can take its series from either engine.

## 2. The construction

Let `J` be the micro-employment states, `A` the distribution asset grid, `Π` the (J·A × J·A) base
kernel the TM already builds (`build_tm_agg_fiscal_a`, `_baseline_ergodic_a`), `π` its ergodic
distribution, and `c(j, a)` the consumption rule on the same grid.

* **The event.** `E = {enter state 3 at t}` = mass in `(j ≠ 3, a)` at `t−1` that moves to `(3, a')`.
  Under the chain above the only inflow to 3 is from 2, so `E` is the 2→3 flow.
* **Survives `min_spell`.** Propagate the entry distribution forward under `Π` RESTRICTED to
  state 3 (`Π₃₃` block) for `min_spell−1` steps; the surviving sub-distribution is the episode
  population. Its mass is the episode weight; renormalise.
* **Lead window (the three quarters BEFORE entry).** Backward conditioning: the distribution at
  `t−k` conditional on entering at `t` and surviving, by Bayes on the same kernel
  (`P(x_{t−k} | E, survive) ∝ π(x_{t−k}) · P(E, survive | x_{t−k})`). Computed by propagating the
  survival indicator BACKWARD `k` steps — one sparse mat-vec per lead period, no new machinery.
* **Lag window.** Forward propagation of the surviving sub-distribution, UNRESTRICTED after the
  minimum spell (the generator does not require staying past three quarters).
* **The statistic.** At each window offset, the mass-weighted mean of `c(j, a)` and of income over
  the conditional distribution, divided by the normaliser (below).

### 2.1 The normalisation is the one real subtlety

The generator divides by **each household's own permanent income three quarters before entry**, not
by a common constant. In the TM the normalised policy `c(j, a)` is already per-unit-permanent-income,
so ratios of normalised quantities at the SAME date need no `p` at all — but this ratio spans dates,
and `p` grows between them. Two consequences:

* the exhibit is a ratio of levels across a 6-quarter window, so the TM version must carry the
  permanent-income growth factor between window offsets — the SST `effective_pLvl_growth`
  (`income_process_sst.py`) is the object, and it is state-dependent (employed vs unemployed growth,
  and λ = 0.44 scaling);
* under the uncapped process `p` is heavy-tailed, so a `p`-weighted conditional mean is NOT the same
  as the unweighted one. **Decide explicitly which the exhibit wants** — the MC version averages
  each episode's own ratio, i.e. an equal-weight-over-EPISODES mean of a `p`-cancelling ratio, which
  the TM reproduces by weighting states by episode mass and applying the deterministic growth factor
  between offsets. Write the derivation down before coding; this is where a silent mismatch would
  live, and it is the one place the two engines could legitimately disagree.

### 2.2 Hazards to handle explicitly

* **`== 3` is hardcoded** in the generator. Under `HAFISCAL_UI_STATE_ENCODING=calendar` there are 7
  micro states, not 4, and the exhaustion state is NOT index 3. The TM version must take the
  exhaustion index from `ui_extension_rule.py` / the encoding, and the MC version should be fixed to
  do the same before they are compared (otherwise the comparison tests the wrong state).
* **Splurge interpretation.** `cLvl_all_splurge` is the SPLURGE-inclusive consumption; the TM's
  `c(j, a)` must use the matching interpretation (CDC vs ESC — `build_tm_agg_fiscal_a` takes it).
* **Wealth series** is `aNrm < 0.005`, an indicator, not a level: the TM version computes the
  conditional PROBABILITY of that event, which is exact on the grid but discretisation-sensitive at
  the boundary. Check grid sensitivity separately.
* **Both arms.** The exhibit needs the estimated-splurge and the splurge-zero models; the TM version
  must be callable for each without a panel for either.

## 3. Test plan — it must pass all of these before any default flips

Reference arm = the MC version, run where the panel is TRUSTWORTHY, i.e. on the CAPPED (published)
calibration, where the drift gate passes and finite-N is not fighting a heavy tail.

| # | test | criterion |
|---|---|---|
| T1 | **N-ladder convergence.** MC at N, 4N, 10N (CRN, same seeds) vs the TM series on the published calibration. | Each of the 18 numbers (3 series × 6 offsets) converges monotonically toward the TM value; the residual falls at the expected rate. This is the real test — the standing rule is that numerical validation means a shared asymptotic limit, not point-wise equality. |
| T2 | **Seed band.** MC at S = 5 seeds, published calibration. | The TM value lies inside the across-seed band for every one of the 18 numbers. |
| T3 | **Grid ladder.** TM at `dist_aGrid_count` × {1, 2, 4}. | The TM series is converged in the grid to ≤ 0.1 % — it must not be the discretisation that agrees with MC. Run the `aNrm < 0.005` indicator separately: it is the boundary-sensitive one. |
| T4 | **Degenerate cross-check.** A configuration where the answer is known analytically (e.g. a two-state chain with a closed-form spell distribution). | Exact to machine precision. Guards the conditioning algebra — the backward Bayes step is where an off-by-one would hide, and an off-by-one there is exactly the class of defect BUG-112 was. |
| T5 | **Both encodings.** `legacy` (4 micro states) and `calendar` (7). | The exhaustion state is found from the encoding, not hardcoded; the two engines agree under both. |
| T6 | **Both arms.** Estimated splurge and splurge zero. | T1–T3 pass for each; the splurge-zero series shows the drop the paper's argument rests on. |
| T7 | **Uncapped calibration.** TM vs MC on the CURRENT default calibration. | EXPECTED TO DISAGREE, and that is the point: record by how much, and that the MC arm fails its drift gate here. This is the evidence that the TM version is the fix and not merely an alternative. |

Gates land as `Code/HA-Models/test_ui_expiry_profile.py`, in `make test-fast` where cheap (T4, T5,
the algebra) and as an opt-in battery where not (T1–T3, T6, T7).

## 4. Wiring, only after §3 passes

1. `EvalConsDropUponUILeave.py` takes its series from `ui_expiry_profile` by default, with
   `HAFISCAL_UI_EXPIRY_ENGINE=mc` retained as the cross-check arm (and as the reproduction path for
   the published figure).
2. `do_all.py` Step 5 calls the generator unconditionally — no pickle, no baseline-only pass, no
   drift gate in the way. **Remove** the Step-5c MC exhibit pass added on 2026-09-06 (`cf36947d`)
   and the Step-3 splurge-zero half, keeping `HAFISCAL_BASELINE_ONLY` (it is independently useful).
3. The figures become ordinary `_candidate` outputs of a default build, regenerable by anyone
   following the documented pipeline — which is the point of the whole exercise.

## 5. What is NOT in scope

The drift gate stays as it is: it is correct, it fired correctly, and the answer is to stop needing
a panel here, not to loosen it. `HAFISCAL_MC_STRATIFY_UNEMP` stays default-off — it was certified
harmless and no-variance-gain on the welfare cells at S = 10 (2026-08-28) and nothing here changes
that; if the MC cross-check arm wants it, that is a local choice for the cross-check.

## 6. Estimated cost

TM version and its algebra: half a day, dominated by §2.1 and the backward-conditioning derivation.
Tests: T4/T5 minutes; T1–T3 a few hours of compute on the published calibration (each MC arm is
~37 s per run plus the ladder). Wiring: an hour. No new solves at any point — the policy store
serves the household problem the pipeline has already solved.
