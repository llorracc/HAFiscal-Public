# HAFISCAL_* environment-flag registry

**Single authoritative registry** of every `HAFISCAL_*` environment variable read by
`Code/HA-Models/**/*.py`. 124 flags. Generated 2026-06-11 at commit `e6859407`
(branch `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`, doc-rationalization worktree);
manually amended 2026-06-13 to add the previously missing generated-output
promotion flag, 2026-06-17 for the five Step-2/AD solver-speedup flags
(`HAFISCAL_STEP2_KEEP_REDUNDANT_SOLVE`, `HAFISCAL_STEP2_NAMG`,
`HAFISCAL_STEP2_NAMG_VERBOSE`, `HAFISCAL_SKIP_STEP2_NAMG_ITEST`,
`HAFISCAL_AD_ANDERSON`), and 2026-06-21 to rename the three Step-2 `*_ANDERSON*`
flags to `*_NAMG*` (the base-solve path was repointed from the Anderson
contraction to the global-Newton/NAMG solver, which reaches a machine-precision
Euler root; `HAFISCAL_STEP2_ANDERSON` stays as a deprecated alias), and
2026-06-22 to add the reuse-fidelity VERIFY-axis flags `HAFISCAL_VERIFY_LEVEL`
(thread-2 component 1), `HAFISCAL_VERIFY_DRIFT_SEEDS` (component 2), and
`HAFISCAL_VERIFY_RESOLVE_SCOPE` (component 3), plus the test-only opt-ins
`HAFISCAL_RUN_DRIFT_ITEST` and `HAFISCAL_RUN_RESOLVE_ITEST`.
Plan: `plans/20260611_env-flag-registry.md`. Authored from
read-site code + linked BUG/plan/conclusions provenance (Phase A inventory +
Phase B subsystem batches).

## Format legend

One `### HAFISCAL_<NAME>` heading per flag. Required fields:

- **Default:** value when the variable is unset (with the canonical-block `setdefault`
  noted where it differs from the call-site fallback).
- **Values:** accepted values and how they are parsed.
- **Status:** `live` | `diagnostic` | `deprecated` | `archived-only`.
  - `live` — read on production/default paths; behavior of standard runs depends on it.
  - `diagnostic` — read only by diagnostics, validation harnesses, benchmarks, or
    opt-in experimental paths; never required for production numbers.
  - `deprecated` — still referenced in code but has no behavioral consumer (zombie)
    or is superseded; exempt from the guard test's scan-presence assertion.
  - `archived-only` — read only under `*_archive/` trees (outside guard-scan scope).
- **Read by:** the read sites (file paths; line numbers as of the generation commit).
- **Purpose:** what it does, why it exists (BUG/decision provenance), interactions.
- **Refs:** plans / BUGS_private / conclusions_private / code docs.

Optional fields: **Needs-owner-review:** (open question for the owner — never guessed
away), **Note:** (ancillary facts, e.g. cache-key gaps).

## Reader workflow

Use this registry as the single source for `HAFISCAL_*` semantics before adding,
removing, or recommending an environment variable. A flag with
`Needs-owner-review` is not an invitation to guess a default or silently change
behavior; it is a queue of unresolved owner decisions. If a recommendation
depends on one of those rows, cite the row as an open prerequisite or make a
small, evidence-backed cleanup plan.

For current methodology defaults, remember that several defaults are applied by
the canonical block in `FromPandemicCode/EstimParameters.py` via
`os.environ.setdefault`, not necessarily by each call site's literal fallback.
The `HAFISCAL_QE_FIDELITY=1` escape hatch reverts to the QE-fidelity world, but
the owner-review queue records known gaps where reproduction profiles or
secondary docs may not set every necessary flag explicitly.

## Guard-test contract

`Code/HA-Models/test_env_flag_registry.py` (runs in `pytest Code/`) keeps this file
complete forever. It scans `Code/HA-Models/**/*.py` — excluding `*_archive/`,
`__pycache__`, and itself — for **any quoted `HAFISCAL_[A-Z0-9_]+` string literal**
(quoted-literal matching, not environ-call adjacency, so wrapper indirection like
`do_all.py:_env_run()` and module-constant indirection like
`solution_cache/cache.py:USE_CACHE_ENV_VAR` are caught) and asserts:

1. **Completeness** — every scanned flag has a `### HAFISCAL_<NAME>` heading here.
   *Adding a new flag to the code without a registry entry fails the suite.*
2. **No zombies** — every heading with Status `live` or `diagnostic` appears in the
   scan (`deprecated` / `archived-only` exempt). *Deleting a flag from the code
   requires flipping its Status here (or deleting the entry).*
3. **Structure** — every heading carries the required fields and a valid Status.

## Needs-owner-review summary — ALL 12 RESOLVED 2026-06-13

All twelve open owner-review items were ruled on 2026-06-13 (see each flag's
`RESOLVED` line for detail). Summary of dispositions:

> **MERGE RECONCILIATION (2026-06-13, econ-mw integration) — owner-ruled Q1–Q6.**
> The econ-mw branch independently ruled on the same items on 2026-06-12; three
> conflicted with the canonical ruling. The owner resolved all three on 2026-06-13:
> - `HAFISCAL_UI_STATE_ENCODING` (Q1/Q4): **coupling REMOVED.** The econ-mw
>   `QE_FIDELITY=1 ⟹ UI=legacy` wiring (duplicated in `EstimParameters.py`) was
>   de-duped (Q6) then deleted (Q1); UI encoding is purely the BUG-043 toggle. ✅ done.
> - `HAFISCAL_USE_JAX_2B` (Q2): **SANCTIONED for production welfare** (canonical
>   direction confirmed). ✅ resolved.
> - Config taxonomy (Q3/Q5): econ-mw's method switch was **renamed**
>   `HAFISCAL_MODE`→`HAFISCAL_MULTIPLIER_ENGINE` (values `tm`/`mc`); `legacy`/
>   `as-corrected` are reserved for the WORLD axis. `config/` interpretation default
>   flipped to `ESC` (Q5). `config/` package remains the intended SoT (not yet wired);
>   reconcile per the follow-up plan. ✅ rename done; wiring tracked.

| Flag | Ruling (2026-06-13) | Status |
|---|---|---|
| `HAFISCAL_NM_IN_PLACE` | Unify trajectory-log default to `'1'` | ✅ fixed in code |
| `HAFISCAL_AD_MAX_ITER` | Re-parent the `AgentCountTotal` block (Baseline unaffected) | ✅ fixed in code |
| `HAFISCAL_RUN_ONLY_SHOCK` | Remove the zombie from the knob-print list | ✅ fixed in code |
| `HAFISCAL_STEP5_SCOPE` | Delete the write-only `setdefault` | ✅ fixed in code |
| `HAFISCAL_SPLURGE_OLD` | Deprecate | ✅ doc (deprecated) |
| `HAFISCAL_VERSION` | Deprecate (archived-only candidate) | ✅ doc (deprecated) |
| `HAFISCAL_IS_FORCE_LOW_ANRM` | Deprecate (active-IS off the table) | ✅ doc (deprecated) |
| `HAFISCAL_WELFARE6_TM_INIT_MEASURE` | Deprecate the `Q` value (`P` stays live) | ✅ doc (deprecated) |
| `HAFISCAL_UI_STATE_ENCODING` | Intended — QE_FIDELITY stays independent; document extra step | ✅ doc |
| `HAFISCAL_USE_JAX_2B` | Sanctioned for production welfare (~1e-3 accepted) | ✅ doc |
| `HAFISCAL_AGENTCOUNT_TOTAL` | Deprecate; recipes use `--agent-count-total` / D,H,C trio | ✅ doc (deprecated) |
| `HAFISCAL_TM_MCOUNT` | **Superseded** — it is the live TM-a `aCount` (not the dead m-indexed knob); earlier "unify to 50" was wrong-direction (would coarsen prod grid). Plan: rename →`HAFISCAL_TM_ACOUNT` (inert) + separate owner-gated default study | ⏳ rename plan drafted (`plans/20260613-1755h_*`); R2 default study deferred |

**Remaining follow-ups (not owner-review questions):**
- `HAFISCAL_TM_MCOUNT`: rename →`HAFISCAL_TM_ACOUNT` (inert; it is the live TM-a
  `aCount`) and, separately and owner-gated, study the production default (UP to a
  converged value, NOT down to 50). See `plans/20260613-1755h_tm-mcount-to-acount-rename.md`.
- Correct the stale `HAFISCAL_AGENTCOUNT_TOTAL` recipe wording in
  `agenda_2026_06_03.md`, `agenda_2026_06_11_DRAFT.md`, and the cited memory.

---

## Generated Output & Freeze

### HAFISCAL_PROMOTE
**Default:** `0` / unset
**Values:** `1` = promotion mode; anything else = normal candidate-routing mode
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/generated_output.py (`is_promote`, `output_path`, `input_path`, `open_generated`); Code/HA-Models/_interpretation.py (`input_path`)
**Purpose:** QE-freeze candidate-routing switch. In normal runs, generators write `_candidate` siblings instead of overwriting canonical paper-rendered outputs, and readers prefer fresh candidates when present. Under `HAFISCAL_PROMOTE=1`, generated-output helpers write/read the canonical path; this is intended only inside the deliberate promote workflow, normally reached via `HAFISCAL_UNLOCK=1 make promote-tables`. Do not set this flag for ordinary regeneration or exploratory runs.
**Refs:** Code/HA-Models/README.md § "QE-Frozen Results and the Candidate Workflow"; LOCKED_TABLES.manifest; plans/20260611_qe-baseline-freeze-and-candidate-lock_plan.md; Code/HA-Models/FromPandemicCode/generated_output.py

---

## Estimation & Interpretation

### HAFISCAL_AXTRA_COUNT
**Default:** `48`
**Values:** positive integer
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (`:174` get, `:175` membership-print)
**Purpose:** Overrides `aXtraCount`, the base number of end-of-period asset gridpoints above the minimum in the household solver's `aXtraGrid`. Prints `[axtra-override] ...` when set. Used for solver-grid-convergence sweeps; production leaves it unset. Numerically load-bearing when set, but no cache-key gap: `solution_cache` keys on the resulting `aXtraGrid` contents directly.
**Refs:** (no plan/BUG provenance found)

### HAFISCAL_ENDOGENOUS_GRID
**Default:** `0` (off; the legacy single hand-set `aXtraMax=40` is shared by all education groups)
**Values:** truthy `1` = on; `0`/empty/`false`/`False` = off
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (endogenous-grid block, just after `init_college`)
**Purpose:** Opt-in: size the household SOLVE grid `aXtraMax` ENDOGENOUSLY, PER education group, to the PF-asymptote (decay) extrapolation reach of that group's most-patient (GIC-cap) atom — `aXtraMax_e = ln(C1/bar)/MPCmin(gic_capped_beta(e))` via `grid_sizing.solve_grid_aMax` (College≈256, HS≈240, Dropout≈205 vs the legacy 40). MPCmin keys off the RIC (return patience), defined even when the growth/GIC-Mod conditions fail — so it is robust. Default OFF ⟹ byte-for-byte unchanged (the per-group writes are 40→40 no-ops and `grid_sizing` is never imported). Tunable via `HAFISCAL_GRID_C1`/`HAFISCAL_GRID_BAR`; an explicit `HAFISCAL_SOLVE_AMAX` overrides it. The TM grid is sized separately by `adaptive_grid_tm.production_aMax()` (1300); `grid_sizing.tm_grid_aMax` is that grid's analytic cross-check / GIC-Mod-failure fallback.
**Refs:** Code/HA-Models/grid_sizing.py; prompts_local/2026-06-24_grid-sizing-experiments-journal.md; plans/immutable-mixing-ripple.md

### HAFISCAL_SOLVE_AMAX
**Default:** unset (then `HAFISCAL_ENDOGENOUS_GRID` decides; else the legacy `aXtraMax=40`)
**Values:** float (top of the household solve `aXtraGrid`, applied to ALL education groups)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (endogenous-grid block)
**Purpose:** Explicit single-value override of the household SOLVE-grid `aXtraMax` for all education groups. Highest precedence (beats both the endogenous path and the legacy 40). The solve-grid companion to the TM-grid `HAFISCAL_TM_AMAX`; for solver-grid convergence sweeps or forcing a specific solve range.
**Refs:** Code/HA-Models/grid_sizing.py; prompts_local/2026-06-24_grid-sizing-experiments-journal.md

### HAFISCAL_GRID_C1
**Default:** `grid_sizing.SOLVE_C1` (`0.04`)
**Values:** float `> bar` (the decay-curve prefactor in `err(m) ≈ C1·exp(−MPCmin·m)`)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (endogenous-grid block; read only when `HAFISCAL_ENDOGENOUS_GRID` is on)
**Purpose:** Diagnostic knob for the endogenous SOLVE grid — the measured decay prefactor in `aXtraMax = ln(C1/bar)/MPCmin`. Re-derive via `scratchpad/exp3_decay_realG.py` (measured ≈0.034, rounded up to 0.04 so the grid is never undersized).
**Refs:** Code/HA-Models/grid_sizing.py (`SOLVE_C1`); prompts_local/2026-06-24_grid-sizing-experiments-journal.md (E3)

### HAFISCAL_GRID_BAR
**Default:** `grid_sizing.SOLVE_BAR` (`0.01`)
**Values:** float in `(0, C1)` (target max relative decay-extrapolation error over `[aXtraMax, tm_aMax]`)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (endogenous-grid block; read only when `HAFISCAL_ENDOGENOUS_GRID` is on)
**Purpose:** Diagnostic knob for the endogenous SOLVE grid — the tail-accuracy target in `aXtraMax = ln(C1/bar)/MPCmin`. Smaller bar → larger grid (1% → College≈256, 0.5% → ≈384). Step-2 β is insensitive (its moments live at m≈6 ≪ aXtraMax).
**Refs:** Code/HA-Models/grid_sizing.py (`SOLVE_BAR`); prompts_local/2026-06-24_grid-sizing-experiments-journal.md (E3)

### HAFISCAL_DISCFAC_FILE
**Default:** unset (calibration file resolved via `_interpretation.resolve_path` + `_permgrofac.permgrofac_calib_path` from the canonical `Results/DiscFacEstim_*.txt`)
**Values:** absolute path to a `DiscFacEstim_*.txt`
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/Parameters.py (`:92`)
**Purpose:** Explicit override of the discount-factor calibration file loaded by `return_parameters()`. Takes precedence over BOTH the interpretation-suffix resolution (`_ESC` vs unsuffixed) and the PermGroFac legacy-subdir mapping — so the matched-TRIPLE discipline {PermGroFac regime, calibration, interpretation} is the CALLER's responsibility: point it only at a file estimated under the same solver regime and interpretation you are running. The `_interpretation.resolve_path` ESC-fallback hazard warning (BUG-049: an ESC run silently reading CDC betas shifted the Check multiplier ~+4%) names this flag as the explicit fix.
**Refs:** BUGS_private/HAFiscal_BUG-049_esc_calibration_silent_fallback.md; plans/20260417-1242h_welfare-vs-multiplier-asymmetry-hypothesis_v2.md §6

### HAFISCAL_EDTYPES
**Default:** `0,1,2`
**Values:** comma-separated subset of `{0,1,2}` (0=Dropout, 1=Highschool, 2=College); `''` (empty) = run no cohorts (import-only no-op, used by harnesses that import the estimator for its setup/objective machinery)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (`:1219` cohort filter, `:1647` calcAllResults gate); Code/HA-Models/FromPandemicCode/estim_phase2_tm.py (`:157`); Code/HA-Models/FromPandemicCode/estim_phase2_tm_a.py (`:212`); Code/HA-Models/_registry.py (`:174`, fallback after `HAFISCAL_WRAPPER_EDTYPES`); Code/HA-Models/do_all_reduced.py (`:91`)
**Purpose:** Restrict Step-2 discount-factor estimation to a subset of education cohorts. A single-cohort run writes to a per-cohort file (`_edType{N}` inserted before the trailing `_ESC.txt`/`.txt`) so concurrent subprocesses don't clobber each other; any non-default value also disables the full-population `calcAllResults` readback (the wrapper merges per-cohort results and reruns it). Set per-child by `run_phase2_parallel.py`; set to `''` by `_tm_a_backfill.py`, `mc_tm_dist_eval.py`, `measure_gicfactor_tradeoff.py` (import-only).
**Refs:** plans/20260408-1024h_minimum-replicates-for-shuffle.md; plans/results/20260418-1634h_phase1.2-warmstart-validation.md

### HAFISCAL_GICX_MODE
**Default:** `hardcoded`
**Values:** `hardcoded` | `legacy` | `twophase` (anything else → `ValueError`)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (`:1281`); Code/HA-Models/FromPandemicCode/estim_phase2_tm_a.py (`:290`); Code/HA-Models/_registry.py (`:183`); in `solution_cache/keys.py` `_HAFISCAL_NUMERICAL_ENV_VARS`
**Purpose:** BUG-039 — dimensionality of the Step-2 Nelder-Mead. `hardcoded` (default since Phase G, 2026-05-03): 2-D NM over (β, ∇) with the GIC cap pinned at `logit(theGICfactor)` (module-load value, **currently 0.9995** — in-code comments still say 0.999, stale since the BUG-053 re-estimation). `legacy`: 3-D NM (β, ∇, GICx) with GICx a free fit knob (pre-Phase-G default; opt-in for verification; used by the BUG-047/BUG-053 re-estimation orchestrators). `twophase`: 2-D first, per-start 3-D refinement if the cap binds at the converged (β, ∇). GICx maps to a cap factor via `exp(GICx)/(1+exp(GICx))`.
**Refs:** BUGS_private/HAFiscal_BUG-039_GICx_unconditionally_optimized.md; plans/20260502-1145h_fix-BUG-039-GICx-NM-options.md; conclusions_private/2026-05-02_BUG-039_phase-g-default-cutover-recommendation.md

### HAFISCAL_GIC_SHAVE_ON_GPF
**Default:** `1`
**Values:** `0` = legacy BUG-053 behavior (shave is a ceiling on **beta**); any other value (incl. unset) = the fix (shave is a ceiling on the **GPF**)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (`:455`, inside `gic_capped_beta()`, via `import os as _os`; `gic_capped_beta` is also imported and called by Parameters.py when clipping a loaded calibration's β atoms)
**Purpose:** BUG-053 — selects the exponent in `gic_capped_beta(e, shave) = GICmaxBetas[e] * shave**exp`. The fix (`exp = CRRA`) makes `theGICfactor` a ceiling on the Growth Patience Factor, so the cap atom lands at GPF = shave exactly. The old bug (`exp = 1.0`) shaved β directly, putting the cap atom at GPF = shave^(1/CRRA) (e.g. 0.999 → 0.9995 with CRRA=2) — closer to the GIC boundary than nominal, with a fatter ergodic wealth tail, slower solve, and wider required asset grid. The cap is LOAD-BEARING for College, so the fix was paired with `theGICfactor = 0.9995` (EstimParameters.py:418) and a 2026-06-09 re-estimation that keeps the cap-β calibration-neutral while making the mechanism correct. Set `0` only for the QE-divergence ledger / before-after reproduction.
**Note:** in the `solution_cache/keys.py` `_HAFISCAL_NUMERICAL_ENV_VARS` whitelist since 2026-06-12 (this note previously recorded that gap — BUG-053/BUG-059 coverage class; the flag changes the clipped β atoms, which the key would otherwise capture only indirectly via per-cohort `DiscFac`).
**Refs:** BUGS_private/HAFiscal_BUG-053_gic_shave_on_beta_not_gpf.md

### HAFISCAL_INTERPRETATION
**Default:** **PRODUCTION default = `ESC`** (owner ruling Q5, wired 2026-06-14): `EstimParameters.py` sets `os.environ.setdefault(HAFISCAL_INTERPRETATION, 'ESC')` UNCONDITIONALLY in the canonical block (applies even under `HAFISCAL_QE_FIDELITY=1`, since the published-QE world is ESC), so every entry point runs ESC unless the env says otherwise. CDC is now an explicit opt-in (`reproduce.sh` `production_*`/`tm_*`/`mc_*` profiles export CDC and, being explicit, win). The **library** code-literal default in `_interpretation.py` stays `'CDC'` (conservative for direct importers + its unit tests). Precedence: explicit kwarg > env var > EstimParameters setdefault(`ESC`) > library code-literal(`CDC`). Guarded entry points still call `get_interpretation(require=True)` and **refuse to default**.
**Values:** `CDC` | `ESC` (case-insensitive; anything else → `ValueError`, fail-fast)
**Status:** live
**Read by:** Code/HA-Models/_interpretation.py (`:60` — the **code-level single source**: `get_interpretation` / `assert_interpretation` / `suffix_path` / `resolve_path` / `interp_suffix`); Code/HA-Models/FromPandemicCode/welfare6_scenario.py (`:952`); Code/HA-Models/FromPandemicCode/welfare6_hybrid_table.py (`:150`); Code/HA-Models/_registry.py (`:173`); Code/HA-Models/mc_tsim_convergence.py (`:53`, hard bracket-read — KeyError if unset); Code/HA-Models/tm_mixing_diagnostic.py (`:595`); Code/HA-Models/validate_mixing_ergodic.py (`:98`); setdefault-ESC drivers: Code/HA-Models/FromPandemicCode/harmenberg_doob_tier1_esc.py, Code/HA-Models/adaptive_grid_tm.py, Code/HA-Models/mc_tm_dist_eval.py, Code/HA-Models/measure_gicfactor_tradeoff.py, Code/HA-Models/dolo_plus_validation/check_vs_hafiscal_code.py; in `solution_cache/keys.py` whitelist and `welfare6_tm_vs_mc_guard_test.py`
**Purpose:** Selects the CDC-vs-ESC interpretation of the splurge — i.e. which budget/asset rule the simulator applies (CDC: `a = m − c_total` including the splurge wedge, per `(eq:budget-CDC)`; ESC: `a = m − cFunc(m)`, the splurger's `ς·y` lives on a separate ledger, per `(eq:budget-ESC)`) — and the calibration **filename-suffix convention**: ESC artifacts are written/read as `*_ESC.txt`, CDC stays unsuffixed; `resolve_path` falls back from suffixed to unsuffixed with a loud ESC-HAZARD warning (an ESC run silently reading CDC betas shifted the recession+AD Check multiplier ~+4% — BUG-049). This is one leg of the matched-TRIPLE invariant {PermGroFac regime, calibration file, interpretation} (BUG-051): `assert_interpretation()` raises if a kernel is called with an explicit `interpretation=` argument that disagrees with the env var, making the silent CDC-kernel-under-ESC-run class of bug impossible at guarded entry points.
**Refs:** Code/HA-Models/_interpretation.py docstring; BUGS_private/HAFiscal_BUG-051_tm_a_ESC_missing_splurge_correction.md; BUGS_private/HAFiscal_BUG-049_esc_calibration_silent_fallback.md; plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md §6; BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC*.md

### HAFISCAL_NM_FATOL
**Default:** `''` (unset → built-in `1e-2`)
**Values:** float string (e.g. `1e-4` to restore scipy's legacy default; `1e-3` intermediate)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (`:1406`); Code/HA-Models/_registry.py (`:188`, records `0.01` when unset)
**Purpose:** Overrides the Nelder-Mead objective-value convergence tolerance for Step-2 estimation (passed as `ftol` to `scipy.optimize.fmin` — the name says "fatol" but fmin takes `xtol`/`ftol`, not `minimize()`'s `xatol`/`fatol`). The HAFiscal default 1e-2 was validated at Baseline scale (max |ΔW6| = 0.01 vs reference across all welfare-6 cells, 3× wall-time reduction vs scipy's 1e-4; 1e-3 gave identical converged β/∇ at 2.3× the wall).
**Refs:** plans/results/20260419_overnight-digest.md §4, §6 (cited in code); plans/20260504-1450h_qe_fidelity_fast_profile.md

### HAFISCAL_NM_IN_PLACE
**Default:** `1`
**Values:** `1` = in-place agent mutation (default); `0` = original deepcopy+splice pattern
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (`:1062` behavior switch; `:1162` trajectory-record field)
**Purpose:** How the NM objective rebuilds the agent list each iteration. Default mutates the existing `AggDemandEconomy.agents` in place, preserving each agent's `.solution` across NM iterations so the solver warm-start in `AggregateDemandEconomy.solve()` fires for the cohort currently being estimated too (validated 2026-04-18 across all three cohorts, 1.27-1.35× per-iter speedup, max |Δβ| = 0 vs the deepcopy path). Set `0` only to bisect a regression against the pre-change pattern.
**RESOLVED 2026-06-13 (owner ruling):** the trajectory-record read site default was unified to `'1'` to match the behavior switch (was `'0'`, so an unset env var logged `in_place: false` while behavior was in-place). Logging-only fix; no behavior change.
**Refs:** plans/results/20260418-1634h_phase1.2-warmstart-validation.md; plans/20260418-2320h_overnight-speedup-chain.md

### HAFISCAL_NM_LOG_EVERY
**Default:** `5`
**Values:** integer stride; `0` (or negative) disables
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/estim_phase2_tm_a.py (`:369` — TM-a estimator only; the MC estimator does not read it)
**Purpose:** Live Nelder-Mead progress logging: wraps the TM-a objective to log every Nth evaluation (eval count, best objective so far, eval rate), because HARK's `verbose` only triggers scipy's final summary and exposes no per-iteration callback. NM has no fixed total — gauge progress from the objective plateauing plus the eval rate. Default on.
**Refs:** (no plan/BUG provenance found; added 2026-06-09 per in-code comment)

### HAFISCAL_NM_START_FROM_SAVED
**Default:** `1` (warm-start ON; default flipped 2026-05-03 per BUG-039 Phase G)
**Values:** `1` = prepend saved warm-start point; `0` = cold start only
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (`:1312`); Code/HA-Models/FromPandemicCode/estim_phase2_tm_a.py (`:311`); Code/HA-Models/_registry.py (`:184`); in `solution_cache/keys.py` `_HAFISCAL_NUMERICAL_ENV_VARS`
**Purpose:** BUG-039 Phase E warm-start: prepends the saved (β, ∇, GICx) as an ADDITIONAL Nelder-Mead starting point — registry-aware (prefers `_registry.find_warm_start_cal()`'s step2_cal for the matching configuration; falls back to the interpretation-suffix-named `DiscFacEstim_*.txt`; missing file → silently cold). Combined with multistart so the other starts still run (no stale-basin lock-in). Phase E validated round-trip preservation (warm-start from saved re-converges identically). Set `0` for a cold start — REQUIRED when re-estimating after a solver/model fix (never warm-start from a pre-fix calibration basin; the BUG-047/BUG-053 re-estimation orchestrators set `0` explicitly).
**Refs:** plans/20260502-1145h_fix-BUG-039-GICx-NM-options.md; conclusions_private/2026-05-02_BUG-039_phase-g-default-cutover-recommendation.md; plans/20260503-1030h_results-registry-and-impc-gof.md (Phase 3 registry-aware lookup)

### HAFISCAL_NM_TRAJECTORY
**Default:** `''` (off)
**Values:** filesystem path to a `.jsonl` file (appended to)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (`:1151`)
**Purpose:** Appends one JSON record per NM iteration (`iter`, `edtype`, `beta`, `spread`, `GICx`, `distance`, `iter_sec`, `in_place`) for before/after estimator comparisons. Set by the `validate_nm_warmstart.py` / `validate_nm_serial.py` / `validate_nm_loky_timeout.py` harnesses. (Its `in_place` field currently mis-reports when `HAFISCAL_NM_IN_PLACE` is unset — see that entry's Needs-owner-review.)
**Refs:** (no plan/BUG provenance found; companion of the validate_nm_* harnesses)

### HAFISCAL_NM_VALIDATE_N_ITERS
**Default:** `''` (no cap)
**Values:** integer N (non-integer silently ignored)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (`:1375`)
**Purpose:** Caps Nelder-Mead at N function calls/iterations (sets scipy `maxfun` and `maxiter`) so the `validate_nm_*` harnesses can run fixed-budget before/after comparisons instead of full convergence.
**Refs:** (no plan/BUG provenance found; companion of the validate_nm_* harnesses)

### HAFISCAL_NM_XATOL
**Default:** `''` (unset → built-in `1e-2`)
**Values:** float string (e.g. `1e-4` to restore scipy's legacy default)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (`:1400`); Code/HA-Models/_registry.py (`:187`, records `0.01` when unset)
**Purpose:** Overrides the Nelder-Mead parameter-space convergence tolerance for Step-2 estimation (passed as `xtol` to `scipy.optimize.fmin`; see HAFISCAL_NM_FATOL for the validation of the 1e-2 default and the fmin xtol/ftol vs minimize xatol/fatol naming).
**Refs:** plans/results/20260419_overnight-digest.md §4, §6 (cited in code); plans/20260504-1450h_qe_fidelity_fast_profile.md

### HAFISCAL_NUM_STARTS
**Default:** `1` (bit-for-bit the legacy single-start estimation)
**Values:** integer ≥ 1; effectively capped by the per-cohort start-grid sizes (Dropout 4, Highschool 3, College 2 — same grids in the MC and TM-a estimators; position 0 is always the legacy default start)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (`:1236`); Code/HA-Models/FromPandemicCode/estim_phase2_tm_a.py (`:267`); Code/HA-Models/FromPandemicCode/run_phase2_parallel.py (`:148`); Code/HA-Models/_registry.py (`:185`)
**Purpose:** BUG-036 multi-start Step-2 estimation: runs Nelder-Mead from N curated starting points per education cohort and keeps the global-best basin's parameters. Motivated by the Dropout cohort's multimodal objective (single-start lands in a ~47×-worse local basin); HS/College grids are cheap insurance. Multi-start (not the GIC change) is what produced the 15× wealth-fit improvement of 2026-04-30.
**Refs:** BUGS_private/HAFiscal_BUG-036_dropout_step2_local_minima.md §6.1; conclusions_private/2026-04-30_step2-wealthfit-15x-improvement-is-multistart-not-gic.md

### HAFISCAL_PARALLEL_MULTISTART
**Default:** `0`
**Values:** `1` = per-(cohort, start) subprocess parallelism (requires `HAFISCAL_NUM_STARTS` > 1 to take effect); else legacy one-subprocess-per-cohort with sequential multistart inside
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/run_phase2_parallel.py (`:147`); Code/HA-Models/_registry.py (`:186`)
**Purpose:** BUG-039 Phase F estimation-throughput knob: with multistart enabled, each cohort's starting points run as separate concurrent subprocesses (each child pinned via `HAFISCAL_PIN_START_INDEX`; per-cohort caps {D:4, HS:3, C:2}) — ~4× speedup for Dropout's 4 starts. MC estimator only: with `HAFISCAL_STEP2_METHOD=tm_a` the wrapper prints a notice and falls back to per-cohort mode (TM-a doesn't honor PIN_START_INDEX).
**Refs:** BUGS_private/HAFiscal_BUG-036_dropout_step2_local_minima.md; conclusions_private/2026-05-02_BUG-039_phase-g-default-cutover-recommendation.md

### HAFISCAL_PERMGROFAC_FIX
**Default:** `1` (fix ON; cutover 2026-06-04)
**Values:** `0` = legacy buggy solver + `Results/_pgf_legacy/` calibration (raises `FileNotFoundError` if the legacy-regime calibration is absent — refuses to mismatch); any other value (incl. unset) = fixed solver + canonical calibration
**Status:** live
**Read by:** Code/HA-Models/_permgrofac.py (`:28` — the **single source**: `permgrofac_fix_on()` / `permgrofac_regime()` / `permgrofac_calib_path()` / `stamp_regime()` / `assert_regime()`); Code/HA-Models/FromPandemicCode/welfare6_scenario.py (`:950`); Code/HA-Models/FromPandemicCode/welfare6_hybrid_table.py (`:148`); setdefault-`1`: Code/HA-Models/mc_tm_dist_eval.py, Code/HA-Models/mc_tsim_convergence.py; in `solution_cache/keys.py` `_HAFISCAL_NUMERICAL_ENV_VARS` and `welfare6_tm_vs_mc_guard_test.py`
**Purpose:** BUG-047 — the solver omitted the `PermGroFac^(-CRRA)` factor in the marginal-value recursion (~6-7% cFunc change), so the discount-factor calibration was re-estimated PAIRED with the fix regime. To make a mismatch impossible rather than discouraged, this ONE flag drives all three legs: (1) the solver math (AggFiscalModel.py), (2) the calibration-file selection (Parameters.py via `permgrofac_calib_path` — FIX=0 reads `Results/_pgf_legacy/`), and (3) solution stamping/assertion (`stamp_regime` at solve time, `assert_regime` at simulate/cache-restore time, so a cached or pickled solution from the OTHER regime cannot be silently simulated). One leg of the matched-TRIPLE {PermGroFac regime, calibration, interpretation} (with BUG-051).
**Refs:** BUGS_private/HAFiscal_BUG-047_permgrofac_marginal_value_factor.md; Code/HA-Models/_permgrofac.py docstring; BUGS_private/HARK+HAFiscal_TM_vs_MC_bug_index.md

### HAFISCAL_PF_DECAY_EXTRAP
**Default:** `0` (OFF; default path byte-for-byte unchanged)
**Values:** `0` / unset / `''` / `false` / `False` = OFF (legacy bare `LinearInterp(m_temp, c_temp)`, naive-linear extrapolation above the top grid point); `powerlaw` = ON with the **power-law** decay tail (2026-07-05: HAFiscal-local `powerlaw_decay.PowerLawDecayLinearInterp`, the mirror of the HARK-PR `LinearInterp(decay_extrap_form='powerlaw')`; theory-correct per the 2026-06-24 derivation §8); any other truthy value (e.g. `1`) = ON with the legacy **exponential** decay (the original PR-3 form — kept so existing callers are unchanged while the exp→powerlaw switch is under test, plans/2026-07-05_powerlaw-switch-test-plan.md)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py — two read sites: `solve_agg_cons_markov_alt` (the 2D-slice decay attach + Carroll-Kimball HALT) and `AggFiscalType.update_solution_terminal` (the constrained-PF backward-induction start, owner insight 2026-06-24). Both call the shared module-level helper `compute_pf_decay_limits` so terminal and slice-attach use identical limits.
**Purpose:** BUG-062 / PR-3 — opt-in per-Markov-state PF (perfect-foresight) decay extrapolation for the 2D AggShock consumption function. When ON, each per-state cFunc slice gets `slope_limit=MPCmin` and `intercept_limit=MPCmin*h_AD[n][i]`, so it decays to the affine PF asymptote `c_bar_i(m)=MPCmin*(m+h)` instead of following the last segment's slope forever. MPCmin is from `mom_bounds.compute_mpc_min` with mortality-as-impatience `DiscFac*LivPrb` (C-independent); h is the Markov-JOINT human wealth from `mom_bounds.solve_markov_human_wealth`. **AD-AWARE h (owner directive 2026-06-24):** the human wealth is AD-augmented and **C-dependent** — for each aggregate-consumption slice `n` (Cgrid[n]) the per-state income is scaled by `ADFunc(Cgrid[n], RecState_j)` (`= Cgrid[n]**ADelasticity` in recession states, `1` otherwise) BEFORE the human-wealth fixed point, so the PF tail of a recession regime reflects the AD income drop instead of using base income. `RecState_j = floor(j/num_base_MrkvStates)%2==1`. The aggregate C driving ADFunc is HELD at the slice value Cgrid[n] for the integration (documented approximation; the recession's mean-reversion is carried by the macro transitions already in MrkvArray). In the **baseline / `ADelasticity==0`, ADFunc≡1**, so `h_AD` is C-flat and equals the base joint-h for every slice — the AD code reduces EXACTLY (bit-identical) to the base-h version (verified). **Constrained-PF start (owner refinement 2026-06-24):** the backward induction is STARTED from the (now C-dependent) constrained PF terminal `c0_i(m,C)=min(m, MPCmin*(m+h_AD[n(C)][i]))` instead of HARK's consume-everything `c(m)=m` (built with `LowerEnvelope2D(IdentityFunction, LinearInterpOnInterp1D(per-C PFlines, Cgrid))`). By Carroll-Kimball precaution + Bellman monotonicity, every backward iterate then stays at/below the PF line, so the slice loop's HALT becomes the literal slope-independent invariant "above the line ⇒ impossible" (the old c=m start needed a transient-skip because consume-everything sits above the line at high m). The infinite-horizon fixed point is unique, so the start changes only the TRANSIENT path, not the converged cFunc (verified: PF-start vs c=m-start agree to 2.7e-10 at a 1e-12 solve tolerance). Guards: an FHWC/RIC fallback (RIC fails ⇒ MPCmin≤0, or FHWC fails ⇒ any non-finite h_AD ⇒ warn once + revert to legacy no-limit / consume-everything terminal) plus the Carroll-Kimball (1996) concavity HALT (`ValueError` if any solved top knot lies above the AD-aware PF line — theoretically impossible in a correct solve; owner ruling 2026-06-24: HALT, do not silently fall back). Default OFF ⇒ byte-for-byte unchanged. Couples to `HAFISCAL_ENDOGENOUS_GRID` (most valuable with the extended grid).
**Note (2026-07-05):** now in the `solution_cache/keys.py` `_HAFISCAL_NUMERICAL_ENV_VARS` whitelist (closes the known gap; one-time dev-cache key rewrite). The **HARK PR** (`fix-aggshock-pf-decay-extrap` worktree, commits `208f78f1`/`fed6f368`+) carries the canonical upstream machinery and uses the **power-law** decay form (`LinearInterp(decay_extrap_form='powerlaw')`, per `conclusions_private/2026-06-24_buffer-stock-decay-power-law-derivation.md` §8); this HAFiscal-local path still attaches HARK's legacy **exponential** decay — switching it to power-law is a pending owner decision (validation: `Code/HA-Models/decay_form/harness_powerlaw_extrap.py`).
**Refs:** plans/20260624_hark-2d-markov-extrapolation-fix.md (PR-3; authors BUG-062 on landing); BUGS_private/HAFiscal_BUG-061_solve_grid_aXtraMax_hardcoded_and_2D_aggshock_naive_extrap.md (layer-ii root cause); Code/HA-Models/mom_bounds.py (`solve_markov_human_wealth`, `compute_mpc_min`); Code/HA-Models/test_pf_asymptote_decay.py (regression test)

### HAFISCAL_PIN_START_INDEX
**Default:** unset (run all selected starts)
**Values:** integer K with 0 ≤ K < number of starts for the cohort (out of range → `ValueError`)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (`:1364` — MC estimator only; estim_phase2_tm_a.py does NOT honor it)
**Purpose:** BUG-039 Phase F: restricts the run to a single multistart point K and writes its result to `*_start{K}.txt`, so concurrent per-(cohort, start) workers don't clobber each other. Set per-child by `run_phase2_parallel.py` (when `HAFISCAL_PARALLEL_MULTISTART=1`) and by `reest_permgrofac_hybrid.py` (Dropout grid, one start per child).
**Refs:** BUGS_private/HAFiscal_BUG-039_GICx_unconditionally_optimized.md (Phase F)

### HAFISCAL_QUIET_BETADISTR
**Default:** `0` (print)
**Values:** `1` = suppress the load-time betaDistr print; anything else = print
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/Parameters.py (`:375`); set to `1` by Code/HA-Models/reestimate_bug053_orchestrate.py (`:93`) and Code/HA-Models/measure_gicfactor_tradeoff.py (`:20`)
**Purpose:** Suppresses the `[loaded calibration: EducationGroup e] betaDistr ...` diagnostic that prints the ON-DISK calibration's β atoms plus its OWN saved GIC cap/GPF/GICx on every `return_parameters()` call (including transitively at AggFiscalModel import). During a re-estimation that print shows the STALE pre-run calibration about to be overwritten — which once cost time chasing a phantom cap inconsistency (BUG-053 followup, 2026-06-09) — so re-estimation orchestrators set `1`; the estimator separately prints `[newly estimated ...]` for the new distribution.
**Refs:** BUGS_private/HAFiscal_BUG-053_gic_shave_on_beta_not_gpf.md (followup)

### HAFISCAL_REEST_INTERP
**Default:** `ESC`
**Values:** `ESC` | `CDC` (upper-cased; passed through to HAFISCAL_INTERPRETATION)
**Status:** live
**Read by:** Code/HA-Models/reest_permgrofac_hybrid.py (`:69`)
**Purpose:** Which interpretation the BUG-047 hybrid re-estimation orchestrator re-estimates. It sets `HAFISCAL_INTERPRETATION` to this value for itself (so its filename-helper calls resolve the right suffix: CDC writes the un-suffixed `DiscFacEstim_*.txt`, ESC writes `_ESC` files) and for all estimation children — which also get the fixed re-estimation recipe `PERMGROFAC_FIX=1`, `UI_STATE_ENCODING=bug_fix`, `GICX_MODE=legacy` (3-D fitted GICx), `NM_START_FROM_SAVED=0` (cold — no warm-start off the pre-fix basin), per-cohort `NUM_STARTS` {D:4, HS:1, C:1}.
**Refs:** BUGS_private/HAFiscal_BUG-047_permgrofac_marginal_value_factor.md

### HAFISCAL_SKIP_ESTIMATION
**Default:** `''` (off)
**Values:** `1` = skip; anything else = run normally
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (`:1183` sets `estimateDiscFacs=False`; `:1645` sets `calcAllResults=False`)
**Purpose:** Import `EstimAggFiscalMAIN.py` without running EITHER the Nelder-Mead estimation or the results readback — for harnesses that want its setup, agents, and objective machinery only (profile harness, `_tm_a_backfill.py`, `mc_tm_dist_eval.py`, `measure_gicfactor_tradeoff.py`). Contrast HAFISCAL_SKIP_ESTIMATION_OPTIMIZE, which skips only the optimizer.
**Refs:** conclusions_private/2026-05-01_saved-step2-cal-stale-due-to-bug-034.md

### HAFISCAL_SKIP_ESTIMATION_OPTIMIZE
**Default:** `''` (off)
**Values:** `1` = skip the Nelder-Mead optimize only
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (`:1185` sets `estimateDiscFacs=False`; `calcAllResults` still runs)
**Purpose:** Skip estimation but still run the full-population `calcAllResults` readback (tables/aggregates computed from the saved calibration). Set by `run_phase2_parallel.py`'s final pass after merging per-cohort results, which is always executed via `EstimAggFiscalMAIN.py` (MC-format results) regardless of `HAFISCAL_STEP2_METHOD`.
**Refs:** (no plan/BUG provenance found; part of the run_phase2_parallel wrapper design)

### HAFISCAL_SPLURGE_FILE
**Default:** unset (canonical `Target_AggMPCX_LiquWealth/Result_AllTarget*.txt` resolved via `_interpretation.resolve_path`)
**Values:** absolute path to a `Result_AllTarget*.txt` containing a dict with key `'splurge'`
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/Parameters.py (`:95`)
**Purpose:** Explicit override of the Step-1 splurge-estimation result file from which `return_parameters()` loads ς (welfare-attribution override block, alongside HAFISCAL_DISCFAC_FILE; the same matched-calibration discipline applies). Note HAFISCAL_SPLURGE_OVERRIDE (direct scalar) takes precedence over any file.
**Refs:** plans/20260417-1242h_welfare-vs-multiplier-asymmetry-hypothesis_v2.md §6

### HAFISCAL_SPLURGE_OLD
**Default:** `0`
**Values:** `1` = restore the pre-splurge-in-budget (buggy) asset update; anything else = current behavior
**Status:** deprecated (was: diagnostic) — owner ruling 2026-06-13. Still wired (harmless), but discouraged: it short-circuits before the per-agent interpretation branch (a no-op-equivalent under ESC) and exists only for retired BUG-031 diagnostics. Slated for removal with the BUG-031 diagnostic cleanup.
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py (`:1416`, in `get_poststates`); Code/HA-Models/FromPandemicCode/mc_welfare_diagnostic.py (`:44`, `:51`, labeling only)
**Purpose:** BUG-031 diagnostic toggle. With `1`, the MC asset update reverts to `a = m − cFunc(m)`, dropping the `ς·(y − cFunc)` wedge that the paper's budget identity (eq. 5) requires under the CDC interpretation — i.e. the ORIGINAL published behavior before the splurge-in-budget fix. Used only for the welfare-gap MC diagnostic. Interaction: under `HAFISCAL_INTERPRETATION=ESC` the `a = m − cFunc(m)` rule is the CORRECT ESC behavior (separate code branch, splurge on its own ledger), so this flag is only meaningful for CDC runs.
**RESOLVED 2026-06-13 (owner ruling):** deprecate (see Status above).
**Refs:** BUGS_private/HAFiscal_BUG-031_splurge_not_in_budget.md; BUGS_private/HAFiscal_splurge_budget_inconsistency/; plans/20260417-1242h_welfare-vs-multiplier-asymmetry-hypothesis.md

### HAFISCAL_SPLURGE_OVERRIDE
**Default:** unset (ς loaded from file)
**Values:** float string (invalid value → ignored with a console message; empty string → ignored)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/Parameters.py (`:159`)
**Purpose:** Direct scalar override for the splurge fraction ς; takes precedence over `Splurge_txt_location` (and therefore over HAFISCAL_SPLURGE_FILE). Built for the welfare-attribution experiment to isolate the ς contribution without fabricating a matching `Result_AllTarget*.txt`.
**Refs:** plans/20260417-1242h_welfare-vs-multiplier-asymmetry-hypothesis_v2.md §6

### HAFISCAL_STEP2_SIM_ENGINE
**Default:** `tm_ergodic` (flipped from `mc` 2026-06-23; `mc` opt-in)
**Values:** `mc` | `tm_ergodic` (anything else → `ValueError`)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/run_phase2_parallel.py (`_resolve_step2_engine`); Code/HA-Models/_registry.py (`step2_sim_engine`)
**Purpose:** PRIMARY axis for which engine computes the Step-2 ergodic wealth moments the (β,∇) estimator matches to targets. `mc` = Monte Carlo forward-panel objective (`EstimAggFiscalMAIN.py`). `tm_ergodic` = a-indexed transition-matrix ergodic objective (`estim_phase2_tm_a.py`): noise-free and ~10–21× faster than the MC panel, matching it within sampling noise (gated by `Code/HA-Models/toolmap/test_tm_ergodic_parity.py`; toolmap Phase A+B, 2026-06-21). The shipped ESC calibration (`DiscFacEstim_*_TM_a_ESC.txt`) was estimated this way, so `tm_ergodic` reproduces it while a fresh `mc` run does not. Supersedes the deprecated `HAFISCAL_STEP2_METHOD` (its `tm_a` value ≡ `tm_ergodic`); SIM_ENGINE wins if both are set (a disagreement prints a warning). **DEFAULT flipped to `tm_ergodic` 2026-06-23** (owner: llorracc) after the matched re-validation showed TM and MC estimate the SAME β to ≤0.06% across all three cohorts (the apparent Dropout gap was BUG-036 multimodality, not engine); `mc` is one flag away. Rationale + validation table: conclusions_private/2026-06-23_step2-default-flip-to-tm-ergodic.md.
**Refs:** conclusions_private/2026-06-23_step2-default-flip-to-tm-ergodic.md; plans/20260621_toolmap-phase-b.md; conclusions_private/2026-06-21_toolchain-ledger.md; Code/HA-Models/docs/SOLVE_SIMULATE_TOOLMAP.md

### HAFISCAL_STEP2_METHOD
**Default:** `mc`
**Values:** `mc` | `tm_a` (anything else → `ValueError`)
**Status:** deprecated — ALIAS of `HAFISCAL_STEP2_SIM_ENGINE` (2026-06-21); `tm_a` ≡ `tm_ergodic`. Still honored for backward compat; using it prints a deprecation notice.
**Read by:** Code/HA-Models/FromPandemicCode/run_phase2_parallel.py (`_resolve_step2_engine`); Code/HA-Models/_registry.py (`:180`)
**Purpose:** Which Step-2 discount-factor estimator the parallel wrapper dispatches: `mc` = Monte Carlo objective (`EstimAggFiscalMAIN.py`), `tm_a` = a-indexed transition-matrix objective (`estim_phase2_tm_a.py`). Both honor HAFISCAL_EDTYPES and write canonical + per-cohort files; TM-a's canonical filename carries a `_TM_a` method suffix (then the interpretation suffix). The wrapper's final `calcAllResults` pass always runs `EstimAggFiscalMAIN.py`, but deliberately PRESERVES this env var so `_registry` records the correct step2_method for later warm-start lookup. `tm_a` + `HAFISCAL_PARALLEL_MULTISTART` is unsupported (falls back to per-cohort mode). **Migration:** replace `HAFISCAL_STEP2_METHOD=tm_a` → `HAFISCAL_STEP2_SIM_ENGINE=tm_ergodic`, `=mc` → `=mc`.
**Refs:** plans/20260502-1256h_reproduce-sh-profile-machinery.md; plans/20260503-1030h_results-registry-and-impc-gof.md; plans/20260503-1437h_mc_tma_companion_and_drift.md; conclusions_private/2026-05-03_ESC-TMa-end-to-end-vs-QE-Jan.md

### HAFISCAL_UI_STATE_ENCODING
**Default:** `bug_fix` (EstimParameters.py:217; asserted to be one of the two values)
**Values:** `legacy` = 4 micro states {e, u1Q, u2Q, noBen}; UI extension implemented as a `transition_ub=False` freeze window over a fixed macro-state span — under-delivers benefits by 1Q for Case-1 agents (BUG-043) but is bit-identical to the published QE code. `bug_fix` = 6 micro states {e, u1Q, u2Q, u3Q, u4Q, noBen}; UI extension implemented as macro-state-conditional income at u3Q/u4Q (0.7 when recession + recessionUI scenario, 0.5 otherwise) — fixes BUG-043, matches paper Model.tex ("up to four quarters"), and as a side benefit enables shuffle-CRN for UI welfare cells. Cutover to bug_fix: 2026-05-16.
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (`:217`, drives `num_base_MrkvStates = 2 + UBspell_normal [+ Policy_ExtraBenefitQuarters]` → 6 vs 4 micro states, multiplying total Markov StateCount; ~2.25× slower a-indexed solves); Code/HA-Models/FromPandemicCode/welfare6_scenario.py (`:951`); Code/HA-Models/FromPandemicCode/welfare6_hybrid_table.py (`:149`); Code/HA-Models/mc_tm_dist_eval.py (setdefault); in `solution_cache/keys.py` `_HAFISCAL_NUMERICAL_ENV_VARS` and `welfare6_tm_vs_mc_guard_test.py`
**Purpose:** BUG-043 fix selector — extends the micro state space to encode the quarter-of-unemployment explicitly so the UI extension is a payout-based policy rather than a freeze-window mechanism.
**RESOLVED + DONE 2026-06-13 (owner ruling Q1/Q4): the `QE_FIDELITY⟹legacy-UI` coupling is REMOVED.** The econ-mw merge had wired `if HAFISCAL_QE_FIDELITY=='1': setdefault('HAFISCAL_UI_STATE_ENCODING','legacy')` in `EstimParameters.py`. That coupling has been **deleted** (2026-06-13): `HAFISCAL_UI_STATE_ENCODING` is now purely the BUG-043 bug-fix toggle, handled automatically by the `default`/`as-corrected` WORLD scheme (both = `bug_fix`); exact published-QE reproduction is the old branch's job, not a runtime flag. `HAFISCAL_QE_FIDELITY=1` no longer touches the UI encoding (it now only skips the canonical methodology setdefaults, and is itself deprecated/scheduled for removal — Q4). To reproduce pre-2026-05-16 UI numbers, set `HAFISCAL_UI_STATE_ENCODING=legacy` explicitly. Tracked in `plans/20260613-1830h_config-taxonomy-reconciliation-post-econ-mw-merge.md` (Q1/Q4).
**Refs:** BUGS_private/HAFiscal_BUG-043_ui_extension_under_delivers_for_during_recession_unemployment.md; BUGS_private/HAFiscal_BUG-048_recessionTaxCut_6state_crash.md; plans/20260511_BUG-043_fix_state_expansion_plan.md; conclusions_private/2026-05-16_canonical_config_recommendation.md

### HAFISCAL_URATE_NORMAL_C
**Default:** `0.027`
**Values:** float (normal-times unemployment rate, College)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (`:97` get; `:98` membership → prints `[urate-override] ...` if any of the three is set)
**Purpose:** Override the College normal-times unemployment rate used to build the micro Markov transition matrices. Built for shuffle-friendliness diagnostics: quota-exact urates at N=10k want D 0.090 / HS 0.045 / C 0.025 (candidate recalibration to surface at the next discount-factor re-estimation). Matched-calibration caveat: the production (β, ∇) estimates were made under the defaults, so overriding urates without re-estimating moves the model off its calibration targets.
**Refs:** plans/20260504-1700h_phase_F_mfmc_tm_a_control_variate.md (Phase H-0); conclusions_private/BUG-044_reduced_run_quota_exact.md

### HAFISCAL_URATE_NORMAL_D
**Default:** `0.085`
**Values:** float (normal-times unemployment rate, Dropout)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (`:95` get; `:98` membership-print)
**Purpose:** Dropout counterpart of HAFISCAL_URATE_NORMAL_C (see that entry for the shuffle-friendliness rationale, the quota-exact candidate value 0.090, and the matched-calibration caveat).
**Refs:** plans/20260504-1700h_phase_F_mfmc_tm_a_control_variate.md (Phase H-0); conclusions_private/BUG-044_reduced_run_quota_exact.md

### HAFISCAL_URATE_NORMAL_H
**Default:** `0.044`
**Values:** float (normal-times unemployment rate, Highschool)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (`:96` get; `:98` membership-print)
**Purpose:** Highschool counterpart of HAFISCAL_URATE_NORMAL_C (see that entry; quota-exact candidate value 0.045; matched-calibration caveat applies).
**Refs:** plans/20260504-1700h_phase_F_mfmc_tm_a_control_variate.md (Phase H-0); conclusions_private/BUG-044_reduced_run_quota_exact.md

### HAFISCAL_WRAPPER_EDTYPES
**Default:** `0,1,2`
**Values:** comma-separated subset of `{0,1,2}`
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/run_phase2_parallel.py (`:135`); Code/HA-Models/_registry.py (`:174`, takes precedence over HAFISCAL_EDTYPES when resolving the cohort set); in `solution_cache/keys.py` `_HAFISCAL_NUMERICAL_ENV_VARS`
**Purpose:** Which education cohorts the parallel Step-2 wrapper launches subprocesses for; skipped cohorts' records are reused from the existing canonical result file at merge time. Distinct from HAFISCAL_EDTYPES, which the wrapper sets per-child to a single cohort — set WRAPPER_EDTYPES (not EDTYPES) to restrict a `run_phase2_parallel.py` run.
**Refs:** plans/20260503-1030h_results-registry-and-impc-gof.md; plans/20260512_tm_a_4state_6state_plan.md

### HAFISCAL_RESULTS_OUT_DIR
**Default:** unset → per-edType output written to `../Results` (byte-for-byte unchanged)
**Values:** absolute path to a writable directory (created if missing)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (`:1580`, redirects the per-edType `_output_file` write); set per-machine by Code/HA-Models/reproduce/cross_machine_step2.py (`_launch`)
**Purpose:** Redirects ONLY the per-edType Step-2 OUTPUT write (`DiscFacEstim_..._edType{N}_ESC.txt`) to a scratch dir; warm-start READS still come from `../Results`. Lets a parallel / cross-machine run read the committed calibration as warm-start without clobbering the git-tracked `Results/` files (the orchestrator gathers from the scratch dir instead). Default unset is a no-op.
**Refs:** Code/HA-Models/reproduce/cross_machine_step2.py; Code/HA-Models/README.md (Step-2)

### HAFISCAL_PHASE2_FINALIZE_ONLY
**Default:** `0` / unset
**Values:** `1` = finalize-only mode; anything else = normal launch+merge
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/run_phase2_parallel.py (`:285`, main() early-return branch; `:251` env.pop to avoid child recursion); set by Code/HA-Models/reproduce/cross_machine_step2.py (`_finalize`)
**Purpose:** Cross-machine Step-2 finalize. Makes `run_phase2_parallel.py` SKIP the local subprocess launch and instead merge the per-edType files the orchestrator gathered (from `HAFISCAL_PHASE2_PER_EDTYPE_DIR`) into the candidate-routed canonical + run the calcAllResults pass, reusing the same `_merge_and_finalize` as the local fan-out path. Owner-gated (real re-estimation is opt-in).
**Refs:** Code/HA-Models/reproduce/cross_machine_step2.py

### HAFISCAL_PHASE2_PER_EDTYPE_DIR
**Default:** unset (required when `HAFISCAL_PHASE2_FINALIZE_ONLY=1`)
**Values:** path to a directory holding the 3 per-edType `DiscFacEstim_..._edType{N}_*.txt` files
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/run_phase2_parallel.py (`:286`; passed to `_merge_and_finalize(per_edtype_src_dir=...)`); set by Code/HA-Models/reproduce/cross_machine_step2.py (`_finalize`)
**Purpose:** Tells the finalize-only merge WHERE the gathered per-edType files live (the orchestrator's staging dir), instead of the default `../Results`. Keeps the git-tracked `Results/` clean during a cross-machine run. No effect unless `HAFISCAL_PHASE2_FINALIZE_ONLY=1`.
**Refs:** Code/HA-Models/reproduce/cross_machine_step2.py

### HAFISCAL_PHASE2_MERGE_ONLY
**Default:** `0` / unset
**Values:** `1` = stop after writing the merged candidate; else also run calcAllResults
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/run_phase2_parallel.py (`:291`; `_merge_and_finalize(run_calc=...)`)
**Purpose:** Finalize-only sub-switch to validate the merge wiring WITHOUT the expensive full-population calcAllResults solve — writes the candidate-routed merged canonical from the staged per-edType files and returns. Used by the cross-machine hardening validation; not for production. No effect unless `HAFISCAL_PHASE2_FINALIZE_ONLY=1`.
**Refs:** Code/HA-Models/reproduce/cross_machine_step2.py


## Pipeline & Infrastructure

(`HAFISCAL_QUIET_BETADISTR` and `HAFISCAL_STEP2_METHOD` are documented under
Estimation & Interpretation.)

### HAFISCAL_AD_CONVERGENCE_TOL
**Default:** unset (code default `convergence_tol_solvingAD` = `1e-3`; `1e-2` for Reduced_Run / Smoke_Test / HS_Only)
**Values:** float, e.g. `1e-2` (non-numeric → warning printed, value ignored)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/Parameters.py
**Purpose:** Override the AD-loop convergence tolerance in the Step-5 multiplier path ("Idea F" speedup knob). Loosening `1e-3` → `1e-2` typically cuts AD iterations from ~5 to ~3.
**Refs:** plans/20260504-1300h_qe_fidelity_speedup_systematic_test.md, plans/20260504-1450h_qe_fidelity_fast_profile.md, plans/results_20260504_speedup-test-matrix.md

### HAFISCAL_AD_MAX_ITER
**Default:** unset (code default `num_max_iterations_solvingAD` = `15`; `5` for Reduced_Run / Smoke_Test / HS_Only)
**Values:** int (non-int → warning printed, iteration cap ignored — but see side effect below, which still fires)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/Parameters.py (also echoed by Code/HA-Models/FromPandemicCode/jax_mc_baseline_5x_bench.py)
**Purpose:** Cap the number of AD-loop iterations in the Step-5 multiplier path (speedup-test knob, same family as HAFISCAL_AD_CONVERGENCE_TOL).
**RESOLVED 2026-06-13 (owner ruling: FIXED in code).** The mis-nested `AgentCountTotal` block (introduced by commit `e1fa6368`, 2026-05-04) was re-parented under `if Parametrization in ('Reduced_Run','Smoke_Test','HS_Only'):`, so `AgentCountTotal` now depends ONLY on the parametrization and `HAFISCAL_AD_MAX_ITER` controls only `num_max_iterations_solvingAD`. The prior bugs are gone: (a) AD_MAX_ITER no longer forces Baseline→5000; (b) reduced parametrizations get their intended small `AgentCountTotal` whether or not AD_MAX_ITER is set. **Baseline (the unset path) was 10000 before and after, so frozen paper numbers are unchanged.**
**Refs:** BUGS_private/HAFiscal_BUG-058_ad_max_iter_agentcount_reparenting.md (the dossier for this fix); plans/20260504-1300h_qe_fidelity_speedup_systematic_test.md, plans/20260504-1450h_qe_fidelity_fast_profile.md

### HAFISCAL_DUR_WORKERS
**Default:** unset → auto: `max(1, min(n_dur, ncpu // 8))` (the `//8` assumes up to 7 outer shock-type fork workers may be active concurrently)
**Values:** positive int; `1` = sequential (the recommended debug setting — fork-failure messages say "Re-run with HAFISCAL_DUR_WORKERS=1 to debug")
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/Simulate.py (`_fork_dispatch_durations`)
**Purpose:** Cap the fork width of the Step-5 per-recession-duration loops dispatched through `_fork_dispatch_durations`: MC durations (label `mc_rec`), TM no-AD durations (`tm_rec`), and the TM-AD Phase-2 duration evaluations (`tm_ad_rec`, the 2026-06-10/11 TM-AD fork — t=0 runs inline because Phase-1 CFunc training mutates the economy; t≥1 are read-only `skip_training=True` evaluations, FP-identical to sequential per the HS_Only bit-compare gate). NOT the same mechanism as welfare6_scenario.py's `--duration-workers` CLI flag (a separate pool in `_prob_weighted_rec`); the ~16 GB-per-fork OOM guidance in memory concerns that welfare6 CLI pool, not this env var.
**Refs:** plans/20260409-1238h_mc_only_speedups.md; conclusions_private/2026-06-03_duration_workers_resource_constraint.md (welfare6 pool, for disambiguation)

### HAFISCAL_FIGS_SUFFIX
**Default:** `''` (no suffix)
**Values:** any path-safe string, e.g. `_h0_treat_seed0`
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalMAIN_reduced.py
**Purpose:** Append a suffix to the parametrization name in Step-5 output dir paths — `Figures/<Param><suffix>/` and `Tables/<Param><suffix>/` — so parallel runs do not collide on `Figures/Reduced_Run/` etc.
**Refs:** conclusions_private/2026-05-04_h0-shuffle-validation-and-recalibration-leverage.md

### HAFISCAL_NO_FORK
**Default:** unset (fork parallelism ON wherever `os.fork` exists and there is >1 job)
**Values:** `1` | `true` | `yes` disable forking (anything else = enabled)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/Simulate.py — two gates: the outer shock-type fork (~line 1127; up to 7 parallel workers, 4 recession + 3 non-recession scenarios) and the inner `_fork_dispatch_durations` sequential fallback (~line 704). Code/HA-Models/FromPandemicCode/run_optc_param.py `setdefault`s it to `1` (Option-C single-parametrization runs default to no-fork).
**Purpose:** Kill-switch for all `os.fork()`-based parallelism in the Step-5 simulation driver — sequential fallback for debugging (the parallel-failure message says "Re-run with HAFISCAL_NO_FORK=1 to debug sequentially") or for platforms without fork.
**Refs:** plans/20260409-1238h_mc_only_speedups.md, plans/20260414-1453h_quick-MC-baseline-CRRA2-vs-QE.md, BUGS_private/HAFiscal_BUG-033_tm_a_indexed_refactor.md

### HAFISCAL_NO_SOLVE_CACHE
**Default:** `""` (in-process solve cache ON)
**Values:** anything not in `{"", "0", "false", "False"}` disables the cache
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/test_asymptotic_equality_revised.py
**Purpose:** Disable that test driver's IN-PROCESS dict solve-cache (key = `(Parametrization, shock_type)`, stores deepcopies of agent `solution` slots) so before/after regression checks can compare per-period series against un-cached behavior. Unrelated to the on-disk `solution_cache` package — see HAFISCAL_USE_SOLUTION_CACHE.
**Refs:** plans/20260408-1028h_asymptotic-equality-driver-baseline-cache-refactor_v3.md

### HAFISCAL_PARALLEL_SOLVE
**Default:** `''` (off → 1 worker / serial, unless a caller passes `n_workers` programmatically or `--solve-workers` on the CLI)
**Values:** positive int = worker count; `'0'`/`''` = off. (Edge: `parallel_solve.parallel_eco_solve` called with `n_workers=None` treats a set-but-non-digit value as auto = `min(n_cohorts, cpu_count)`; the welfare6_scenario import-time read requires a digit.)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/parallel_solve.py (`parallel_eco_solve` default + `install_parallel_solve_via_env`), Code/HA-Models/FromPandemicCode/welfare6_scenario.py (import-time seed of `_SOLVE_WORKERS`; `--solve-workers` CLI overrides), Code/HA-Models/FromPandemicCode/verify_welfare_replay.py (fallback when `--solve-workers` absent)
**Purpose:** Cohort-parallel HARK solves via fork-based multiprocessing (21 independent Baseline-5x cohorts; ~3.88× speedup, bit-identical to sequential; load-imbalance limited). **Wired ONLY into the welfare drivers** (welfare6_scenario, run_welfare6_parallel children, verify_welfare_replay, jax_mc_ad_multicohort refsim) — NOT into the Step-5 multiplier path (Simulate.py / AggFiscalMAIN*.py never read it). Set `OMP_NUM_THREADS=1` to avoid BLAS oversubscription. run_welfare6_parallel pins it to `1` in child envs (each spawn-pool worker is ~17 GB RSS with JAX 2B active; inner parallelism comes from HAFISCAL_USE_JAX_2B_THREADS instead).
**Refs:** CLAUDE.md §Cohort-parallel HARK solves; conclusions_private/2026-05-21_hark-jax_handoff.md, conclusions_private/2026-06-03_duration_workers_resource_constraint.md

### HAFISCAL_PROFILE
**Default:** `""` (off)
**Values:** anything not in `{"", "0", "false", "False"}` enables
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/test_asymptotic_equality_revised.py
**Purpose:** Print one line per timed block in the asymptotic-equality test driver (profile-first instrumentation: refactoring decisions must be driven by this data, not guesses). NOT the do_all.py pipeline profiler — that is `hafiscal_progress.py`, which is always on and reads no env flag.
**Refs:** plans/20260408-1028h_asymptotic-equality-driver-baseline-cache-refactor_v3.md

### HAFISCAL_QE_FIDELITY
**Default:** `''` (off → canonical Plan-A defaults applied)
**Values:** `1` = approximate published-QE methodology; anything else = canonical
**Status:** deprecated (owner ruling 2026-06-13, Q4; scheduled for removal)
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (gates the canonical `os.environ.setdefault` block: MC_SHUFFLE=1, SHUFFLE_MRKV_TRANSITION=stratified, SHUFFLE_NEWBORN_FIX=transition, TM_AMAX=1300 — under `=1` the call sites fall back to their legacy defaults: shuffle OFF, plain `'shuffle'`, aMax=500, and emits a `DeprecationWarning`); Code/HA-Models/do_all.py (Step 5a: omits the `HAFISCAL_TM_A_INDEXED=1` prefix → m-indexed TM multipliers); Code/HA-Models/FromPandemicCode/welfare6_hybrid_table.py, run_step5a_only.py, run_all.py, run_hybrid_welfare6.py (methodology reversion).
**Purpose:** Escape hatch that reverts the pipeline *methodology* to approximate the published HAFiscal-QE results. Works because EstimParameters is imported by every entry point before any of the gated vars are read at runtime.
**DEPRECATED 2026-06-13 (owner rulings Q1 + Q4).** It is redundant and is being retired: use the **`as-corrected` WORLD** (`Code/HA-Models/config/`) for the debugged counterfactual, or the **old branch / frozen tag `v2026-01-09-18-17`** for EXACT published-QE (which needs the matched buggy calibration files). As of 2026-06-13 it **no longer flips `HAFISCAL_UI_STATE_ENCODING`** (the `QE_FIDELITY⟹legacy-UI` coupling was removed per Q1; UI encoding is purely the BUG-043 toggle). The flag still functions as the methodology escape hatch but is slated for full removal once the `as-corrected` world is wired (see plan R2). Tracked in plans/20260613-1830h_config-taxonomy-reconciliation-post-econ-mw-merge.md (Q1/Q4).
**Refs:** CLAUDE.md §Canonical solution approach (Plan A, 2026-06-10); conclusions_private/2026-06-10_welfare_method_unified_MC.md, conclusions_private/2026-05-03_HAFiscal-QE-vs-current-comparison.md, conclusions_private/2026-05-04_qe_fidelity_full_vs_QE_published.md

### HAFISCAL_RUN_ONLY_SHOCK
**Default:** unset
**Values:** none consumed
**Status:** deprecated
**Read by:** none — the lone print-if-set reference in `run_step5a_only.py` was removed 2026-06-13.
**Purpose:** Zombie. Presumably a planned single-shock-type filter for Step-5a runs that was never implemented; nothing in any .py/.sh/.md changes behavior on it.
**RESOLVED 2026-06-13 (owner ruling: removed).** Deleted from `run_step5a_only.py`'s knob-print list. The flag now has zero references; retained here only as a historical record.
**Refs:** (none found)

### HAFISCAL_RUN_STEP_1
**Default:** unset → `True` (step runs)
**Values:** truthy iff `value.lower() ∈ {'true','1','yes'}`; ANY other set value — including `false`, `0`, and the empty string — disables the step
**Status:** live
**Read by:** Code/HA-Models/do_all.py — INDIRECTLY via the `_env_run(var, default)` wrapper (do_all.py:27-31 holds the actual `os.environ.get(var)`; the flag name appears only as a literal argument at do_all.py:33). Guard-test note: no direct `os.environ.get('HAFISCAL_RUN_STEP_1', ...)` pattern exists for this flag — the guard needs a KNOWN_INDIRECT entry or a quoted-literal scan. Recorded into run manifests by reproduce/build_manifest.py.
**Purpose:** Opt out of pipeline Step 1 (splurge-factor estimation, `Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py`; paper §3.1).
**Refs:** plans/20260421-1325h_minimal-reproduce-step5.md, plans/20260425-1015h_reproduce-self-documenting-runs.md, plans/20260425-1252h_reproduce-full-codebase-critique.md

### HAFISCAL_RUN_STEP_2
**Default:** unset → `True`
**Values:** truthy iff `value.lower() ∈ {'true','1','yes'}` (see HAFISCAL_RUN_STEP_1 for the empty-string footgun)
**Status:** live
**Read by:** Code/HA-Models/do_all.py — INDIRECTLY via `_env_run` (do_all.py:27-31; literal at :34). Same guard-test KNOWN_INDIRECT note as HAFISCAL_RUN_STEP_1. Recorded by reproduce/build_manifest.py.
**Purpose:** Opt out of pipeline Step 2 (discount-factor distribution estimation; paper §3.3.3).
**Refs:** plans/20260421-1325h_minimal-reproduce-step5.md, plans/20260425-1015h_reproduce-self-documenting-runs.md

### HAFISCAL_RUN_STEP_3
**Default:** `False` in do_all.py (`'false'` in do_all_reduced.py) — Step 3 produces Online-appendix robustness results, off by default
**Values:** truthy iff `value.lower() ∈ {'true','1','yes'}`
**Status:** live
**Read by:** Code/HA-Models/do_all.py — INDIRECTLY via `_env_run` (literal at :36) — AND directly by Code/HA-Models/do_all_reduced.py:46 (`os.environ.get('HAFISCAL_RUN_STEP_3', 'false')`). The only RUN_STEP flag with a direct-pattern read site (so it alone is visible to the guard's 4-pattern scan). Exported (default `'false'`) by reproduce/reproduce_computed.sh; recorded by reproduce/build_manifest.py.
**Purpose:** Opt IN to pipeline Step 3 (robustness results for the Online appendix).
**Refs:** plans/20260418-1441h_explore-further-speedups.md, plans/20260418-1531h_restore-reproduce-sh-comp-full.md, plans/20260421-1325h_minimal-reproduce-step5.md

### HAFISCAL_RUN_STEP_4
**Default:** unset → `True`
**Values:** truthy iff `value.lower() ∈ {'true','1','yes'}`
**Status:** live
**Read by:** Code/HA-Models/do_all.py — INDIRECTLY via `_env_run` (literal at :37). Same guard-test KNOWN_INDIRECT note as HAFISCAL_RUN_STEP_1. Recorded by reproduce/build_manifest.py.
**Purpose:** Opt out of pipeline Step 4 (HANK/SAM Jacobian experiments).
**Refs:** plans/20260421-1325h_minimal-reproduce-step5.md, plans/20260425-1015h_reproduce-self-documenting-runs.md

### HAFISCAL_RUN_STEP_5
**Default:** unset → `True`
**Values:** truthy iff `value.lower() ∈ {'true','1','yes'}`
**Status:** live
**Read by:** Code/HA-Models/do_all.py — INDIRECTLY via `_env_run` (literal at :38). Same guard-test KNOWN_INDIRECT note as HAFISCAL_RUN_STEP_1. Recorded by reproduce/build_manifest.py.
**Purpose:** Opt out of pipeline Step 5 (fiscal-policy comparison, paper §4) — both 5a (TM multipliers, `AggFiscalMAIN_reduced.py --baseline`) and 5b (MC welfare-6; separately gated by HAFISCAL_RUN_STEP_5B).
**Refs:** plans/20260425-1252h_reproduce-full-codebase-critique.md, plans/20260504-1450h_qe_fidelity_fast_profile.md

### HAFISCAL_RUN_STEP_5B
**Default:** unset → `True`
**Values:** truthy iff `value.lower() ∈ {'true','1','yes'}`
**Status:** live
**Read by:** Code/HA-Models/do_all.py — INDIRECTLY via `_env_run` (literal at :41). Same guard-test KNOWN_INDIRECT note as HAFISCAL_RUN_STEP_1. (do_all_reduced.py has no 5B gate.)
**Purpose:** Skip Step 5b (MC welfare-6 via `run_welfare6_parallel.py --baseline`) independently of Step 5a (TM multipliers). Skipping 5b is the qe_fidelity_fast pattern: multipliers only, no welfare.
**Refs:** plans/20260504-1450h_qe_fidelity_fast_profile.md, plans/20260506-2030h_ESC_MC_to_CDC_TM_migration.md

### HAFISCAL_SERIAL
**Default:** `''` (parallel: HARK `multi_thread_commands` over agent types via joblib)
**Values:** `1` → `multi_thread_commands_fake` (serial execution); anything else = parallel
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (the Step-2 MC estimator's baseline command loop: `solve() / initialize_sim() / simulate() / save_state()`). Set to `1` by Code/HA-Models/FromPandemicCode/run_phase2_parallel.py in every per-edType / per-start child (process-level parallelism outside, serial inner loop), by Code/HA-Models/FromPandemicCode/validate_nm_serial.py, and by Code/HA-Models/adaptive_grid_tm.py.
**Purpose:** Force serial agent-command execution inside the Step-2 estimation objective — for bisection/debugging, and as the standard child configuration under the process-parallel Step-2 wrappers (avoids nested joblib-inside-subprocess oversubscription).
**Refs:** plans/20260418-2320h_overnight-speedup-chain.md, plans/20260504-1300h_qe_fidelity_speedup_systematic_test.md, plans/results/20260418-2148h_A-weirdness-investigation.md

### HAFISCAL_SIM_METHOD
**Default:** `''` → script default `Run_Dict['sim_method'] = 'TM'` (AggFiscalMAIN_reduced.py:50)
**Values:** `MC` | `TM` | `both` (`dual_MC` is reachable only via the `--dual-mc` CLI flag, not this env var)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalMAIN_reduced.py — two sequential read sites (:95 and :108). Note: the first accepts ANY non-empty string verbatim into `Run_Dict['sim_method']`; the second re-applies only if the value is in `{MC, TM, both}` — so a typo'd value propagates unvalidated.
**Purpose:** Select the Step-5 simulation method without code edits. Set by reproduce/reproduce_computed_mc_only.sh (`MC`) and reproduce/reproduce_computed_tm_only.sh (`TM`), run_step5a_only.py (defaults `MC`), run_all.py (`TM`), scripts/run_with_tma_companion.py (`MC` — the point of the MC+TM-a companion rule). Recorded by reproduce/build_manifest.py.
**Refs:** plans/20260414-1453h_quick-MC-baseline-CRRA2-vs-QE.md, plans/20260425-1015h_reproduce-self-documenting-runs.md, conclusions_private/2026-05-03_HAFiscal-QE-vs-current-comparison.md, conclusions_private/2026-05-04_qe_fidelity_full_vs_QE_published.md

### HAFISCAL_MULTIPLIER_ENGINE
**Default:** `tm`
**Values:** `tm` | `mc` (case-insensitive; any other value raises `ValueError` at import)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (canonical block, non-QE_FIDELITY branch) — the IMPROVEMENT-001 **METHOD axis**. Resolves to a downstream `os.environ.setdefault`: `mc` → `HAFISCAL_SIM_METHOD=MC` (both engines share `HAFISCAL_TM_AMAX=1300`). Also surfaced as `reproduce.sh --multiplier-engine tm|mc` (`mc` additionally implies `--mc-only`).
**Purpose:** A SINGLE switch that selects the **multiplier engine** (not a scatter of flags), per IMPROVEMENT-001. Both engines share **everything** — every bug-fix (PERMGROFAC_FIX, GIC_SHAVE_ON_GPF, GICx-2D, 6-state UI), stratified-MC welfare, `aMax=1300`, AND the TM-ergodic MC seed (`Simulate.py` `mc_use_tm_init=True`). They differ on **exactly one axis** — `tm` = TM a-indexed multipliers vs `mc` = reliable stratified-MC — which makes `mc` a clean same-model TM-vs-MC method cross-check. **aMax stays 1300 in `mc`** (NOT the QE 500): mc seeds from the TM ergodic distribution, so a 500-truncated seed grid would chop the most-patient College atom's wealth tail (owner ruling 2026-06-13). This is a METHOD, *not* a WORLD: reserve `legacy`/`as-corrected` for the WORLD axis (`Code/HA-Models/config/`). Distinct from `HAFISCAL_QE_FIDELITY=1` (which reverts the *bug-fixes* too) and from exact-QE (the frozen tag `v2026-01-09-18-17`). Explicit `HAFISCAL_SIM_METHOD` / `HAFISCAL_TM_AMAX` still win (setdefault).
**Renamed 2026-06-13 (owner ruling Q3):** this is the renamed METHOD axis. The former `HAFISCAL_MODE` (values `default`/`legacy`) is kept as a **deprecated alias** (see below) because its `legacy` value collided with the `as-corrected` WORLD.
**Refs:** IMPROVEMENTS_private/HAFiscal_IMPROVEMENT-001_legacy_default_mode_taxonomy.md; conclusions_private/2026-06-10_welfare_method_unified_MC.md
**Added:** Q3 rename 2026-06-13.

### HAFISCAL_WORLD
**Default:** `default`
**Values:** `default` | `as-corrected` (case-insensitive; any other value raises `ValueError` at import)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (canonical block, non-QE_FIDELITY branch) — the **WORLD axis** (R2 wiring 2026-06-13). Selects the results-semantics world; values are sourced from `Code/HA-Models/config/catalog.py` via `resolve_world(...)` and applied with `os.environ.setdefault` (explicit env still wins). Guarded by `config/test_runtime_parity.py`. **ALSO read by `Code/HA-Models/_interpretation.py`** (`get_world`/`world_suffix`/`calib_suffix`/`resolve_calib_path`, 2026-06-14) for **calibration-file naming + loading**: the as-corrected world's re-estimated betas are written/read with an `_ascorrected` tag (after the `_ESC` interp tag) so they never clobber the default/headline betas. WRITE sites: `EstimAggFiscalMAIN.py`, `estim_phase2_tm_a.py`, `run_phase2_parallel.py`; READ site: `Parameters.py` (DiscFacEstim betas → `resolve_calib_path`; the SHARED splurge stays interp-only).
**Purpose:** The SoT-driven WORLD selector (distinct from the METHOD axis `HAFISCAL_MULTIPLIER_ENGINE`). `default` = canonical post-paper config (the paper's headline numbers) — **byte-for-byte non-breaking** (the applied subset equals the pre-R2 literals; world_suffix=''). `as-corrected` = paper config + ALL-and-ONLY bug fixes (the honest counterfactual): reverts the discretionary *runtime* choices (e.g. `HAFISCAL_PERM_DURING_UNEMP=off`) while keeping every bug-fix. **`as-corrected` emits a `RuntimeWarning`: it is RUNTIME-ONLY until the matched calibration exists** — a fully-matched counterfactual needs re-estimated calibration (perm-during-unemp affects the estimate), the Q4-phase-2 gate (run spec: `plans/20260614_as-corrected-calibration-run-spec.md`). Until then `resolve_calib_path` emits a LOUD `as-corrected calibration HAZARD` warning and falls back to the default-world betas (never silently). The world wiring does NOT force `HAFISCAL_TM_A_INDEXED` (per-entry-point, BUG-033). `HAFISCAL_INTERPRETATION` is NOT world-varying (ESC in both worlds): its ESC default-flip (Q5) is wired SEPARATELY as an unconditional global default in EstimParameters (2026-06-14), not via this world axis. exact published-QE is the frozen tag `v2026-01-09-18-17`, not a runtime world.
**Refs:** conclusions_private/20260613_config-worlds-definition-default-legacy.md; Code/HA-Models/config/catalog.py; plans/20260614_as-corrected-calibration-run-spec.md; plans/20260613-1830h_config-taxonomy-reconciliation-post-econ-mw-merge.md (R2)
**Added:** R2 wiring 2026-06-13; calibration-file I/O wiring 2026-06-14.

### HAFISCAL_MODE
**Default:** (unset; no default applied — defers to `HAFISCAL_MULTIPLIER_ENGINE`)
**Values:** `default` | `legacy` (DEPRECATED alias; any other value raises `ValueError` at import)
**Status:** deprecated (alias kept for one cycle)
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (only when `HAFISCAL_MULTIPLIER_ENGINE` is unset) — maps `default`→`tm`, `legacy`→`mc` and emits a `DeprecationWarning`. Also surfaced as the deprecated `reproduce.sh --mode default|legacy` (maps to `--multiplier-engine`, logs a WARNING).
**Purpose:** Back-compat for the pre-rename spelling. **Use `HAFISCAL_MULTIPLIER_ENGINE=tm|mc` instead.** The rename (owner ruling Q3, 2026-06-13) resolves the naming collision: `legacy` is a *method* (MC engine), NOT the `as-corrected` *world* (`Code/HA-Models/config/`). Scheduled for removal after one cycle; tracked in plans/20260613-1830h_config-taxonomy-reconciliation-post-econ-mw-merge.md (Q3).
**Refs:** IMPROVEMENTS_private/HAFiscal_IMPROVEMENT-001_legacy_default_mode_taxonomy.md
**Added:** econ-mw merge 2026-06-13; deprecated by Q3 rename 2026-06-13.

### HAFISCAL_STEP5_SCOPE
**Default:** `setdefault` to the run's parametrization (`Smoke_Test` / `HS_Only` / `Reduced_Run` / `Baseline`) by AggFiscalMAIN_reduced.py:159
**Values:** parametrization name (but see below — never consumed)
**Status:** deprecated
**Read by:** nothing. The registry gets the scope directly via `_cfg['step5_scope'] = _reduced_param` in `AggFiscalMAIN_reduced.py`; the env var is not consumed.
**Purpose:** (Intended) record the Step-5 scope in the results registry; (historical) a dead `setdefault` that was never wired to a consumer.
**RESOLVED 2026-06-13 (owner ruling: delete the write-only setdefault).** The redundant `os.environ.setdefault('HAFISCAL_STEP5_SCOPE', ...)` was removed from `AggFiscalMAIN_reduced.py`; the registry continues to record `step5_scope` from the local variable. The env var now has no read or write site.
**Refs:** (none found)

### HAFISCAL_TABLE_DIR
**Default:** unset → `Tables/Baseline/` or `Tables/Reduced_Run/` by parametrization
**Values:** directory path (created if missing; trailing slash normalized)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/run_hybrid_welfare6.py (set per-arm by Code/HA-Models/FromPandemicCode/run_welfare_attribution.sh)
**Purpose:** Redirect the hybrid-welfare6 driver's table output directory so welfare-attribution sweep arms write to separate dirs instead of overwriting each other.
**Refs:** Code/HA-Models/FromPandemicCode/run_welfare_attribution.sh (no plans/BUGS/conclusions refs found)

### HAFISCAL_USE_SOLUTION_CACHE
**Default:** `"0"` (off)
**Values:** `1` enables; anything else off
**Status:** live
**Read by:** Code/HA-Models/solution_cache/cache.py — NOTE: via the module constant `USE_CACHE_ENV_VAR = "HAFISCAL_USE_SOLUTION_CACHE"` (cache.py:39), read at cache.py:194 (`os.environ.get(USE_CACHE_ENV_VAR, "0")`) — a const-indirect read the guard's adjacency regex must tolerate; Code/HA-Models/jax_mc_speedup/jax_mc_speedup_bench.py; Code/HA-Models/welfare6_reconcile_sweep.py (`setdefault "1"`). Set to `1` in child envs by Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py and forced on by the solution_cache smoke tests; recorded by Code/HA-Models/experiments/append.py.
**Purpose:** On-disk cache of AD-converged `eco.solve()` outputs so a second invocation with identical numerical params skips the entire AD loop. Wired into `welfare6_scenario.run_recession_AD` for both JAX-AD (`cached_solve_ad_recession`) and HARK-AD (`cached_solve_ad_recession_hark`, covering all four `solve_ad_*` methods), plus `cached_eco_solve` for plain solves; on HIT the post-AD eco state + `eco.stored_solutions[name]` snapshot are reconstructed so downstream `restore_ADsolution` works unchanged. ~5000× speedup at Baseline AD HIT; ~250× at HS_Only HARK-AD HIT. Files: `Code/HA-Models/solution_cache/<parametrization>/<shock_type>/` (gitignored).
  **Cache-key whitelist:** `keys.py:37-66` `_HAFISCAL_NUMERICAL_ENV_VARS` — currently **15** numerical-output-affecting flags read into the key at keys.py:204 (PLVL_GROWS_DURING_UNEMP, TM_CFUNC_OFFSET, AGGREGATE_BY_EDU_SHARE, UI_STATE_ENCODING, SHUFFLE_MRKV_TRANSITION, AGENTCOUNT_{D,H,C}, INTERPRETATION, WRAPPER_EDTYPES, GICX_MODE, NM_START_FROM_SAVED, PERMGROFAC_FIX, USE_JAX_2B, USE_JAX_2B_VMAP). Pure-speedup flags are deliberately excluded; HAFiscal/HARK commit SHAs are excluded from the key (warn at load if changed). **Any new flag that changes numerical output MUST be added to this whitelist** — the PERMGROFAC_FIX omission was the 2026-06-04 matched-pair incident (calibration+solver+interpretation are an atomic matched triple).
**Refs:** CLAUDE.md §Solution cache; Code/HA-Models/solution_cache/__init__.py; conclusions_private/2026-05-20_jax_mc_speedup_and_cache.md, conclusions_private/2026-05-21_hark-jax_handoff.md; plans/20260608_overnight_grid_convergence_execution.md

### HAFISCAL_AD_BELIEF_PUBLISH
**Default:** `"1"` (on)
**Values:** `1` publishes the sidecar; anything else off
**Status:** live
**Cache-key:** `excluded` (publish-control; writes an extra sidecar after Step-5a, never changes the solved cFunc)
**Read by:** Code/HA-Models/FromPandemicCode/Simulate.py (after the `*_results_AD` pickle save in the `use_TM`/`use_MC` branches)
**Purpose:** Plan-1 Leg B (cross-phase AD-belief warm-start). When on, Step-5a writes a small AD-belief sidecar (`solution_cache/<param>/<shock_type>/ad_belief.pkl` = the converged macro `economy.CFunc` + a `keys`-hash fingerprint + `engine` tag) after the recession-AD solve, for Step-5b to optionally warm-start from. Best-effort (a sidecar failure never aborts Step-5a); strictly additive — it only writes an extra artifact.
**Refs:** plans/20260622_welfare6-reuse-presolved-AD-equilibria.md; Code/HA-Models/solution_cache/ad_belief.py

### HAFISCAL_AD_BELIEF_SEED
**Default:** `"0"` (off)
**Values:** `1` enables the warm-start; anything else off
**Status:** live
**Cache-key:** `excluded` (warm-start-only; the AD loop runs to its own `convergence_cutoff` unchanged, so the converged result is identical whether or not the seed is used)
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py (`run_recession_AD`, before `cached_solve_ad_recession[_hark]`)
**Purpose:** Plan-1 Leg B consume side. When on (and a matching AD-belief sidecar exists), Step-5b seeds `eco.CFunc` + each `agent.CFunc` from the sidecar then calls `solve_ad_recession` UNCHANGED (no verify/skip/assert-and-accept) — the loop converges to its own fixed point from the warm seed in fewer iterations. Soft-gated on a regime/calibration fingerprint mismatch (mismatch → ignore sidecar → flat path; never a correctness hazard). OFF (default) ⇒ `run_recession_AD` byte-identical to today. NOTE: currently speedup-inert on the HARK path — `solve_ad_recession` resets `CFunc` to flat at its top (AggFiscalModel.py:2682), overwriting the seed; making that reset seed-aware is a separate owner-sanctioned change. Stays default-OFF until the B4 parity gate is green HS_Only→College+beta-het and the LOCKED_TABLES CI gate passes.
**Refs:** plans/20260622_welfare6-reuse-presolved-AD-equilibria.md; Code/HA-Models/solution_cache/ad_belief.py; Code/HA-Models/solution_cache/test_ad_belief_seed_parity.py

### HAFISCAL_PROBE_CACHE_CONVERGENCE
**Default:** `"0"` (off)
**Values:** `1` enables the log-only diagnostic; anything else off
**Status:** diagnostic
**Cache-key:** `excluded` (diagnostic; log-only, never rejects/re-solves/mutates — observationally inert)
**Read by:** Code/HA-Models/solution_cache/probe.py (`probe_enabled`)
**Purpose:** Plan-2 STEP 3 diagnostic. When on AND a solution-cache HIT occurs, run ONE backward EGM step (`HARK.core.solve_one_cycle`) from the loaded solution and LOG the per-cohort fixed-point residual (`distance_metric`), labelled `[probe:hark-egm]` (+ a JAX-2B ~1e-3 parity-floor caveat under `HAFISCAL_USE_JAX_2B=1`). RNG-free (no `run_experiment`/sim) so it never perturbs the welfare sim. NOT a correctness gate — the deterministic regime fingerprint (`_regime.assert_fingerprint`, hard-raise on mismatch) is the gate; this only surfaces a grossly-stale entry during development.
**Refs:** plans/20260622_content-addressed-solution-cache-warmstart-1iter-verify.md; Code/HA-Models/solution_cache/probe.py

### HAFISCAL_USE_SIM_CACHE
**Default:** `"0"` (off)
**Values:** `1` would enable a forward-sim panel cache (NOT materialized — design-only this cycle)
**Status:** diagnostic
**Cache-key:** `excluded` (gate for the design-only SIM cache; not on any run path)
**Read by:** Code/HA-Models/solution_cache/keys.py (`gather_sim_inputs` / the SIM-cache design helpers)
**Purpose:** Plan-2 STEP 4 (DESIGN ONLY). Reserves the flag + the SIM-cache key design (`keys.gather_sim_inputs` pins every RNG/shape determinant a forward-sim panel depends on — per-cohort seeds, `seed_offset`, shuffle flags, `WELFARE6_TM_INIT`, `T_sim`, per-cohort `AgentCount`; `keys.verify_sim_panel` is a deterministic shock-hash re-derivation check). NOT materialized — the SOLVE-AD phase is the expensive one; the forward-sim (COMPUTE-WELFARE) phase is cheap and panels are large on disk, so a sim cache is deferred. No run path consults it.
**Refs:** plans/20260622_content-addressed-solution-cache-warmstart-1iter-verify.md; Code/HA-Models/solution_cache/keys.py

### HAFISCAL_SKIP_SLOW_ITEST
**Default:** `"0"` (the slow integration/parity tests run)
**Values:** `1` skips the slow economy-building tests; anything else = run
**Status:** diagnostic
**Cache-key:** `excluded` (test-only escape hatch; no production effect)
**Read by:** Code/HA-Models/solution_cache/test_ad_cache_parity.py, Code/HA-Models/solution_cache/test_ad_belief_seed_parity.py (module-level skip guard)
**Purpose:** Test-time escape hatch for the slow AD-cache / AD-belief parity gates (Plan-1 A3/B4), which build a real HS_Only recession-AD economy (minutes). Setting `1` skips them so collection never hangs on a constrained box and the fast unit suite runs alone. No production effect — read only by those two test modules.
**Refs:** plans/20260622_welfare6-reuse-presolved-AD-equilibria.md; Code/HA-Models/solution_cache/test_ad_cache_parity.py

### HAFISCAL_RUN_DRIFT_ITEST
**Default:** `unset` (the opt-in tiny-scale drift-companion integration test is SKIPPED)
**Values:** `1` runs it; anything else / unset skips
**Status:** diagnostic
**Cache-key:** `excluded` (test-only opt-in; no production effect)
**Read by:** Code/HA-Models/test_verify_drift.py (module-level skip guard)
**Purpose:** Test-time opt-in for the thread-2 component-2 drift-companion INTEGRATION test, which launches real `welfare6_scenario.py` `base`-cell subprocesses at tiny scale (Reduced_Run, agent-count 400, 2 seeds) and asserts the companion produced a seed-1 `base.pkl`. Skipped by default (cascade-gated: the fast unit tiers — gate, seed-count, synthetic report, mocked hook — run unconditionally; this real-compute tier runs only on demand). No production effect.
**Refs:** plans/20260622_thread2-flag-taxonomy-build-execution-plan.md (component 2); Code/HA-Models/test_verify_drift.py

### HAFISCAL_RUN_RESOLVE_ITEST
**Default:** `unset` (the opt-in tiny-scale re-solve-and-compare integration test is SKIPPED)
**Values:** `1` runs it; anything else / unset skips
**Status:** diagnostic
**Cache-key:** `excluded` (test-only opt-in; no production effect)
**Read by:** Code/HA-Models/test_verify_resolve.py (module-level skip guard)
**Purpose:** Test-time opt-in for the thread-2 component-3 re-solve-and-compare INTEGRATION test, which produces a production `base` pkl then re-runs it cache-OFF at tiny scale (Reduced_Run, agent-count 400, scope=canary) and asserts the comparison PASSES (two fresh same-seed solves match within Tier-I). Skipped by default (cascade-gated: the fast unit tiers — scope, tolerance, compare_pickles, mocked hook — run unconditionally; this real-compute tier runs only on demand). No production effect.
**Refs:** plans/20260622_thread2-flag-taxonomy-build-execution-plan.md (component 3); Code/HA-Models/test_verify_resolve.py

### HAFISCAL_VERIFY_LEVEL
**Default:** `"numeric"` (the fast, behavior-neutral default; unset ≡ numeric)
**Values:** `numeric` | `complete` | `byte` (case-/whitespace-insensitive; anything else safe-degrades to `numeric` with a one-time stderr warning, never aborts)
**Status:** diagnostic
**Cache-key:** `excluded` (the VERIFY axis governs how hard a REUSE is verified, not WHICH solution is computed; at `numeric` it is a no-op and a higher level only adds checks / tightens reuse-acceptance — the accepted result is unchanged to tolerance, so it must not partition the cache)
**Read by:** Code/HA-Models/verify_level.py (the canonical reader — `get_verify_level` / `verify_at_least`, via the module constant `ENV_VAR = "HAFISCAL_VERIFY_LEVEL"`); Code/HA-Models/do_all.py (announces a non-default level once); Code/HA-Models/test_verify_level.py. **Surfaced** by `reproduce.sh` as `--complete` (→ `complete`) / `--byte-identical` (→ `byte`); reproduce.sh exports it after arg-parse (strictest requested level wins; a pre-set env is respected and not downgraded).
**Purpose:** The umbrella **VERIFY axis** of the reuse-fidelity verification taxonomy (thread-2), ORTHOGONAL to the METHOD axis (`HAFISCAL_MULTIPLIER_ENGINE`) and the WORLD axis (`HAFISCAL_WORLD`). Selects how hard a run double-checks that any REUSED solution — the AD solution cache (`HAFISCAL_USE_SOLUTION_CACHE`), the cross-phase belief seed (`HAFISCAL_AD_BELIEF_SEED`), a warm start — still gives the right answer. `numeric` (default) = the numerically-equivalent standard (Tier-F/I: reuse accepted when the RESULT is unchanged to tolerance); the default reproduction path is byte-identical to pre-flag code. `complete` adds the opt-in double-checks (multi-seed cross-section drift+SE headline, re-solve-and-compare on reuse, the de-biased one-step result-validity Gate A). `byte` adds byte-exact reuse (the deterministic fingerprint Gate B + a full-object cache round-trip). Each level is a SUPERSET of the ones below (rank `numeric=0 < complete=1 < byte=2`). Consumers are wired INCREMENTALLY per the build plan — component 1 (this flag surface + reader) is live; the drift wiring, re-solve-and-compare, Gate A, and the byte-exact cache land in components 2–5.
**Refs:** plans/20260622_reuse-fidelity-verification-flag-taxonomy.md (spec); plans/20260622_thread2-flag-taxonomy-build-execution-plan.md (build); conclusions_private/2026-06-22_numerical-stability-acceptance-criterion.md (Tier-F/I); conclusions_private/2026-06-22_reuse-gate-A-vs-B-and-debias-derivation.md (Gate A/B)

### HAFISCAL_VERIFY_DRIFT_SEEDS
**Default:** `4` (unset ≡ 4; floored at 2 — an SE needs ≥2 samples)
**Values:** integer ≥ 2 (a sub-floor value warns and uses 2; a non-int warns and uses 4)
**Status:** diagnostic
**Cache-key:** `excluded` (controls the SAMPLE COUNT of the additive `--complete` drift companion; never changes a solved cFunc or a welfare cell)
**Read by:** Code/HA-Models/verify_drift.py (`n_seeds`) — the number of `base`-cell seed-offsets the `run_welfare6_parallel.py` `_maybe_emit_verify_drift` hook uses for the SE.
**Purpose:** Thread-2 component 2 (VERIFY axis, `--complete`). Number of seed-offsets for the multi-seed cross-section drift **SE** companion (standing rule: never report an MC drift without a multi-seed SE — one seed cannot separate a real ergodic-departure from sampling noise). Under `HAFISCAL_VERIFY_LEVEL>=complete`, the welfare step reports drift over this many seeds: it REUSES the main run as seed 0 and launches N−1 extra `base` (no-recession) cells (identical calibration/scale/flags, differing ONLY in RNG seed) via `launch_scenarios`, then reports mean ± SE per 4-moment signal. Higher N = tighter SE at more compute — this is the cost knob for `--complete`'s drift companion. No-op at the default VERIFY level `numeric` (the hook is gated on `verify_at_least(complete)`).
**Refs:** plans/20260622_thread2-flag-taxonomy-build-execution-plan.md (component 2); Code/HA-Models/verify_drift.py; Code/HA-Models/welfare_drift_report.py

### HAFISCAL_VERIFY_RESOLVE_SCOPE
**Default:** `all` (unset ≡ all — owner ruling 2026-06-22)
**Values:** `all` | `sample` (one non-AD + one AD: `base`, `recessionCheck_AD`) | `canary` (`base` only) | `none`, or an explicit comma-separated scenario list. An unrecognized keyword warns and falls back to `all`; an explicit list drops unknown names (with a warn).
**Status:** diagnostic
**Cache-key:** `excluded` (selects WHICH cells the additive `--complete` re-solve-compare verifies; never changes a solved cFunc or a welfare cell)
**Read by:** Code/HA-Models/verify_resolve.py (`scope`) — the scenarios the `run_welfare6_parallel.py` `_maybe_verify_resolve` hook re-solves cache-OFF and compares.
**Purpose:** Thread-2 component 3 (VERIFY axis, `--complete`). Selects which reused (cache-HIT / belief-seeded) cells the **re-solve-and-compare** reuse gate verifies: under `HAFISCAL_VERIFY_LEVEL>=complete`, the named scenarios are re-solved FROM SCRATCH (cache OFF, at the SAME `seed_offset` as production) and compared to the production result within Tier-I (1e-6). A genuine mismatch FAILS the run (the reused solution is suspect — a stale cache / the BUG-047 key-completeness class); a verify-machinery error degrades with diagnostics. `all` (default) verifies every cell (~2× solve cost — the four `*_AD` re-solves dominate); `sample`/`canary` bound it (the dominant failure mode — a stale cache from config-drift — corrupts every cell, so even one re-solve catches it); `none` disables. No-op at the default VERIFY level `numeric`.
**Refs:** plans/20260622_thread2-flag-taxonomy-build-execution-plan.md (component 3); Code/HA-Models/verify_resolve.py; conclusions_private/2026-06-22_reuse-gate-A-vs-B-and-debias-derivation.md

### HAFISCAL_VERSION
**Default:** `'unknown'` (script prints an error and exits)
**Values:** `0.14.1-bugfixed` | `0.17.0-native` (each selects a hardcoded absolute repo path under `/home/econ-ark/GitHub/llorracc/`)
**Status:** deprecated (was: diagnostic) — owner ruling 2026-06-13. The hardcoded machine-specific paths are stale (note `GitHub` vs this host's `github`); use only for the (closed) 0.14.1→0.17.0 upgrade-validation harness. Archived-only candidate.
**Read by:** Code/HA-Models/test_single_objective_eval.py
**Purpose:** Select which HARK-version checkout the single-point objective-evaluation harness targets (0.14.1 → 0.17.0 upgrade validation; dumps intermediates to `/tmp/hafiscal_debug_step1`).
**RESOLVED 2026-06-13 (owner ruling: deprecate).** See Status.
**Refs:** (none found)


## TM kernel

### HAFISCAL_COHORT_UNEMP_SHOCKS
**Default:** `degenerate`
**Values:** `degenerate` | `employed` | `perm_only`
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (`compute_baseline_tm_data`, the `q_method='cohort'` branch — the default q_method, taken under a-indexed + neutral measure)
**Purpose:** Shock treatment of the unemployed Markov states in the BUG-038 cohort-age π_Q decomposition (`compute_pi_q_via_cohort_age`). `degenerate` (default, production-faithful): unemployed states j∈{1,2,3} keep HAFiscal's degenerate-shock convention (ψ≡1, ξ=const), matching qe_fidelity's ψ_unemp=1 / `HAFISCAL_PERM_DURING_UNEMP=off`; the per-(cohort-age, state) 2-moment lognormal fit is then an approximation over j-path mixtures. `employed` (validation only): unemployed states inherit the employed shock distribution — makes the per-cell lognormal fit EXACT but modifies the model relative to HAFiscal production behavior. `perm_only` (validation only): ψ stochastic in all states (employed ψ-marginal) with ξ kept at the production degenerate unemployment income — satisfies the math doc §24.5 "ψ iid across all states" condition exactly; an MC comparison must install the same hybrid IncShkDstn. The env default was switched to `degenerate` in D-8 (2026-05-05) because `employed` is wrong under `HAFISCAL_PERM_DURING_UNEMP=off`.
**Refs:** conclusions_private/2026-05-05_mc-tm-residual-root-cause-pLvl-mrkv-conditional-bias.md, plans/20260429-1641h_cohort-age-decomposition-mc-init.md

### HAFISCAL_E_PLVL_MODE
**Default:** `exact`
**Values:** `exact` | `approx` (anything else raises ValueError)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (`compute_analytical_mean_pLvl`)
**Purpose:** How E[pLvl] is computed for TM aggregation. `exact` (default): Markov-chain matrix-iteration (`compute_E_pLvl_exact`) — exact under HARK's Markov-chain employment dynamics; no (1−u) collapse, no iid-Bernoulli assumption. `approx` (legacy fallback): the (1−u) population-weighted-arithmetic-mean growth approximation g = (1−u)·G + u over an age Markov chain — exact only under iid-Bernoulli employment. Both target the true ergodic value (the MC with HARK's default initialization carries a ~1% cohort-echo bias the formulas avoid).
**Refs:** conclusions_private/2026-05-08_FINAL_ESC_MC_to_CDC_TM_migration_complete.md

### HAFISCAL_MIXING_ACOUNT
**Default:** `200`
**Values:** positive int
**Status:** diagnostic
**Read by:** Code/HA-Models/tm_mixing_diagnostic.py (`__main__`), Code/HA-Models/validate_mixing_ergodic.py
**Purpose:** Grid size (aCount) of the base exp-mult grid built and stress-tested by the standalone TM-mixing diagnostic / ergodic-validation scripts ONLY. Does not affect production TM builds (production grid sizes come from the call-site aCount argument / `HAFISCAL_TM_MCOUNT` / `HAFISCAL_TM_ACOUNT`).
**Refs:** plans/20260609_ensure_connected_TM_mixing.md

### HAFISCAL_MIXING_APOL_TOL
**Default:** `0.05`
**Values:** float (aPol threshold, normalized units)
**Status:** live
**Read by:** Code/HA-Models/tm_mixing_diagnostic.py (module-level `APOL_CONSTRAINT_TOL`; the module is imported by tm_methods' production grid build)
**Purpose:** Boundary of the constraint region for the ψ-mixing machinery: aPol below this is treated as the constraint region, where ψ's fan-out ~ Rfree·aPol/Γ·Δ(1/ψ) vanishes and mixing is supplied by the transitory shock ξ, not ψ — collapses there are EXPECTED, not failures; the diagnostic headline counts only ψ-operative collapses (aPol > tol). Also serves as the default `m_floor` of `refine_grid_for_mixing`, i.e. the floor below which the default-on production mixing refinement (`HAFISCAL_TM_MIXING_GRID=1`) never inserts nodes. At production defaults the refinement adds 0 nodes, so changing this flag is observable only on coarser or custom grid configurations.
**Refs:** plans/20260609_ensure_connected_TM_mixing.md

### HAFISCAL_MIXING_SAFETY
**Default:** `1.0` (the production target via `mixing_logspacing_target` and the tm_mixing_diagnostic `__main__`; validate_mixing_ergodic.py deliberately defaults to `0.5`, its stress configuration)
**Values:** float multiplier on the discretized ψ log-range
**Status:** live
**Read by:** Code/HA-Models/tm_mixing_diagnostic.py (`mixing_logspacing_target` — called from tm_methods `build_tm_agg_fiscal_a` on every auto-grid build; also `__main__`), Code/HA-Models/validate_mixing_ergodic.py
**Purpose:** Scales the Alt-3 mixing log-spacing target: target = safety × log(ψ_max_atom/ψ_min_atom) (the BINDING discretized criterion). At safety=1 the criterion is Δlog(grid) < the FULL min→max atom log-range, which guarantees the extreme ψ atoms straddle ≥1 cell boundary for ANY alignment — one off-diagonal edge per ψ-operative row = irreducibility (the MODEST goal, not two-sided per-node connectivity). Drop below 1 only to add margin against the near-crossover span compression (the +ξ term shrinks the realized log-span just above the aPol > ξ·G/R gate). On the production grid safety=1.0 adds 0 nodes (byte-identical no-op); the knob matters for coarser grids.
**Refs:** plans/20260609_ensure_connected_TM_mixing.md

### HAFISCAL_MIXING_SIGMA_BOUND
**Default:** `3.0`
**Values:** float (k, std-devs of log ψ)
**Status:** diagnostic
**Read by:** Code/HA-Models/tm_mixing_diagnostic.py (module-level `SIGMA_BOUND`)
**Purpose:** Truncation radius of the permanent shock for the CONTINUOUS mixing criterion (condition A): the true lognormal ψ is recharacterized as truncated at ±k·σ of log ψ, giving log-range 2kσ; defining inf/sup of ψ requires a bounded shock. Tradeoff: tighter k = cleaner inf/sup but more discarded tail mass. Affects only the continuous-side diagnostic report — the BINDING discretized criterion (condition B, log(ψ_max_atom/ψ_min_atom)) used by the production mixing target does not depend on k.
**Refs:** plans/20260609_ensure_connected_TM_mixing.md

### HAFISCAL_TM_ACOUNT
**Default:** `200`
**Values:** positive int
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/estim_phase2_tm_a.py
**Purpose:** Distribution-grid size (the aCount of `build_tm_agg_fiscal_a`) for the Step-2 TM-a discount-factor estimation. The dist grid is ~1% of the per-eval cost (the per-atom solves dominate and are aCount-independent), and the pooled group MEDIAN — a calibration target — carries a ~1.5% quantization bias at aCount=200 that converges by ~1600 (jitter 1.49% → 0.06% vs an N=6400 reference; driven by the two GIC-cap atoms' fat tails). Finer dist grid = nearly-free accuracy on the median target; Lorenz targets are grid-robust either way. Distinct from `HAFISCAL_TM_MCOUNT` (the Step-5 / welfare-6 TM aggregation grid).
**Refs:** plans/20260609_ensure_connected_TM_mixing.md

### HAFISCAL_TM_AD_TIMING
**Default:** `lagged`
**Values:** `lagged` | `contemporaneous`
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (module-level)
**Purpose:** Override TM-a's ad_timing — which RecState the aggregate-demand factor uses. `lagged` (default, matches MC's QE convention): RecState[s−1] for ADF[s]. `contemporaneous`: RecState[s] for ADF[s] — diagnostic only; this is the wrong-timing variant whose MC analogue (mill_rule using the wrong RecState at the recession→recovery transition) caused BUG-030's ~11% excess AD amplification. Prints an override notice when set.
**Refs:** BUGS_private/HAFiscal_BUG-030_mill_rule_RecState_timing.md

### HAFISCAL_TM_AMAX
**Default:** `1300` (canonical, via `os.environ.setdefault` in the EstimParameters.py canonical block — skipped under `HAFISCAL_QE_FIDELITY=1`; the in-code fallback when the env var is unset AND no aMax argument is passed is the legacy `500`)
**Values:** float (top of the TM-a asset grid, aNrm units)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (canonical setdefault site), Code/HA-Models/FromPandemicCode/tm_methods.py (`build_tm_agg_fiscal_a`, consulted only when the `aMax` argument is None — explicit-aMax callers bypass the env), Code/HA-Models/tm_mixing_diagnostic.py, Code/HA-Models/validate_mixing_ergodic.py
**Purpose:** Upper bound of the TM-a asset grid. From the EstimParameters canonical block, verbatim: "aMax=1300 is NOT a magic number: the TM grid must cover the MOST-PATIENT College discount-factor atom (the GIC-cap atom, GPF=theGICfactor=0.9995 under the BUG-053 fix) — the most patient agents save the most, so that atom's ergodic aNrm tail is the binding constraint on aMax. 1300 = production_aMax() = the (1-1e-4) ergodic-aNrm quantile of that cap atom (adaptive_grid_tm.py:165); aMax=500 truncates it (biasing the College high-wealth agents). Re-derive via production_aMax() if the calibration / theGICfactor changes." `production_aMax()` (Code/HA-Models/adaptive_grid_tm.py) sizes the grid to the GIC-cap atom — β-INDEPENDENT, so no chicken-and-egg with the (β,∇) estimation — by interpolating the cap atom's ergodic CDF on a large covering grid; it replaced the broken `iterate()` trim/grow loop (a non-convergent 2-cycle). `HAFISCAL_QE_FIDELITY=1` skips the setdefault, reverting to the legacy 500 for reproducing the published-QE world (500 was itself the fix for an earlier aMax=50 tail-truncation bias, ~30% K/Y at high β).
**Refs:** Code/HA-Models/FromPandemicCode/EstimParameters.py (canonical block), Code/HA-Models/adaptive_grid_tm.py (`production_aMax`), plans/20260610_post_merge_canonicalize_default_solution.md, conclusions_private/2026-06-10_welfare_method_unified_MC.md

### HAFISCAL_TM_AMIN
**Default:** unset (the `aMin` argument default `0.0` applies)
**Values:** float (bottom of the TM-a asset grid)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (`build_tm_agg_fiscal_a`)
**Purpose:** Optional lower-bound override, companion to `HAFISCAL_TM_AMAX` (added 2026-06-09). Intended use: set to aNrmMin/10 from the most-impatient cohort's MC support so a SINGLE global grid spans [aNrmMin/10, aNrmMax·2] across ALL cohorts/groups (see Code/HA-Models/adaptive_grid_bounds.py). Set programmatically by the adaptive-grid tooling (adaptive_grid_tm.py, reestimate_bug053_orchestrate.py); the production default stays 0.0.
**Refs:** Code/HA-Models/adaptive_grid_bounds.py, Code/HA-Models/adaptive_grid_tm.py

### HAFISCAL_TM_A_CACHE
**Default:** `0` (off)
**Values:** `1` = on; anything else = off
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (`build_tm_agg_fiscal_a`)
**Purpose:** Opt-in TM-a warm-start cache (MC⇄TM-a companion Phase 3): skip the full TM-a rebuild (per-state solve + matrix construction) when a prior run with the same (agent config, build args, HARK version, tm_methods.py commit) is on disk — SHA-256 key over the canonical config, stored under Code/HA-Models/Results/registry/tm_a_cache/, atomic writes; see FromPandemicCode/_tm_a_cache.py. Benefit is ZERO within NM estimation (each eval changes β → different solution) but large for repeated calcAllResults / multiplier / sensitivity passes at a converged calibration. Auto-disabled when a custom `dist_aGrid` is injected: the (aCount, aMin, aMax, aFac) cache key cannot describe an external grid, so a stale exp-mult entry would otherwise be returned by mistake. Enabled (=1) by the run_step5a_only.py and scripts/run_with_tma_companion.py wrappers.
**Refs:** Code/HA-Models/FromPandemicCode/_tm_a_cache.py (module docstring), plans/20260503-1437h_mc_tma_companion_and_drift.md, plans/20260504-1300h_qe_fidelity_speedup_systematic_test.md

### HAFISCAL_TM_A_INDEXED
**Default:** unset (off at the read site) — but canonical-ON for production multipliers: do_all.py Step-5a prefixes `HAFISCAL_TM_A_INDEXED=1` unless `HAFISCAL_QE_FIDELITY=1`
**Values:** `1` | `true` | `yes` = a-indexed; anything else = m-indexed
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalMAIN_reduced.py (sets `Run_Dict['tm_a_indexed']=True`); set to 1 by Code/HA-Models/do_all.py (Step 5a), Code/HA-Models/FromPandemicCode/run_step5a_only.py, Code/HA-Models/scripts/run_with_tma_companion.py
**Purpose:** Enable a-indexed TM — the BUG-033 splurge-in-budget fix. Routes baseline + experiments through tm_methods' `_a` variants, eliminating the ξ-variance collapse that structurally biases m-indexed multipliers by 15–25% under splurge-in-budget. a-indexed is the canonical (BUG-033-faithful) method for the production multiplier; m-indexed survives only as the `HAFISCAL_QE_FIDELITY=1` legacy mode and as a fast fallback (a-indexed Baseline Step-5a is ~22.5 h with the bug_fix encoding vs ~25 min m-indexed). NOTE: the in-code comment cites the stale path "BUGS_private/HAFiscal_tm_a_indexed_refactor/"; the actual doc is the BUG-033 file below.
**Refs:** BUGS_private/HAFiscal_BUG-033_tm_a_indexed_refactor.md, Code/HA-Models/do_all.py (Step 5a), conclusions_private/2026-04-29_doob-vs-bst-vs-mc-step5-multipliers-three-way.md

### HAFISCAL_TM_CFUNC_OFFSET
**Default:** `mc`
**Values:** `mc` | `tm` (anything else raises ValueError)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (module-level), Code/HA-Models/FromPandemicCode/test_bug041_cfunc_offset.py, Code/HA-Models/solution_cache/keys.py (component of the solution-cache numerical key)
**Purpose:** BUG-041 fix — which `Cratio_path` index the TM-a uses for ADF and cFunc-state lookup at period t (the 1-period offset vs MC). `mc` (default, matches the QE-published MC convention): use Cratio_path[t−1] at period t (one-period lag); at t=0 uses Cratio_path[0] (matches MC's mill_rule special-case for Shk_idx=0). `tm` (legacy TM-a convention; pre-BUG-041 behavior): use Cratio_path[t] at period t (no lag) — kept for byte-identical reproduction of pre-fix TM-a output. The fix closed the Check multiplier MC-vs-TM residual from ~15% to ~1.7%. Prints an override notice when set.
**Refs:** BUGS_private/HAFiscal_BUG-041_TM_CFunc_cell_offset_one_period.md, conclusions_private/2026-05-05_RESOLVED_mc_vs_tm_multiplier_mystery.md

### HAFISCAL_TM_FANOUT_GRID
**Default:** `0` (off)
**Values:** `1` = on; anything else = off. Only honored for auto-built grids (ignored when a custom `dist_aGrid` is injected)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (`build_tm_agg_fiscal_a`)
**Purpose:** OPT-IN replacement of the exp-mult grid with the top-down FAN-OUT grid built from the agent's own solved cFunc: step down from aMax by 1/s of the worst-case ψ down-reach a′_lo(a) so every node has ≥s accessible downward cells by construction, then hand off to a dense packing below a_handoff. aCount becomes an OUTPUT (~131–154 pts for the college cap atom vs the exp-mult 200); the fan-out grid is connectivity-complete, so the mixing refinement is skipped. CAVEAT (2026-06-10 re-estimation gate): the default packing is tuned for TAIL accuracy/connectivity and UNDER-RESOLVES the low-wealth BULK — it biases bulk statistics (e.g. the college medianLWPI, which lives at a~1.1) ~3.8% low vs a 2000-node reference; matching exp-mult(200)'s bulk accuracy needs n_lo~80–150 (204–274 pts, MORE than 200), so this is NOT a cheaper calibration grid. Adoption for calibration was evaluated and REJECTED. Use for TAIL-sensitive studies (upper wealth quantiles, aMax sizing) only. Tunables: `HAFISCAL_TM_FANOUT_S`, `HAFISCAL_TM_FANOUT_HANDOFF`.
**Refs:** plans/20260609_ensure_connected_TM_mixing.md, Code/HA-Models/tm_mixing_diagnostic.py (module docstring)

### HAFISCAL_TM_FANOUT_HANDOFF
**Default:** `10`
**Values:** float (the handoff asset level a_handoff)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (only consulted when `HAFISCAL_TM_FANOUT_GRID=1`)
**Purpose:** Handoff point of the fan-out grid: dense packing below it, ψ-down-reach stepping above. handoff=10, NOT 20: the cap-atom accuracy sweep (2026-06-10) showed handoff=20 with the 30-pt packing under-resolves the low-wealth bulk (frac-below-10 off 14.7% vs a 2000-node reference), while handoff=10 (154 pts) is within ≤1.93% on EVERY stat (E[a], median, p90, p999, mass fractions) and dominates exp-mult(200) (max 10% off).
**Refs:** plans/20260609_ensure_connected_TM_mixing.md

### HAFISCAL_TM_FANOUT_S
**Default:** `2`
**Values:** float ≥ 1 (downward-connectivity multiplicity)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (only consulted when `HAFISCAL_TM_FANOUT_GRID=1`)
**Purpose:** Step divisor of the fan-out grid: each step down from aMax is 1/s of the worst-case ψ down-reach a′_lo(a), so every node has ≥s accessible downward cells by construction (s=2 → at least two live downward edges per node).
**Refs:** plans/20260609_ensure_connected_TM_mixing.md

### HAFISCAL_TM_MCOUNT
**Default:** unset; per-site fallbacks differ — `100` in the Step-5a multiplier driver AggFiscalMAIN_reduced.py (`--fast-reproduce` coarsens to `40`) and in welfare6_tm.py; `50` in tm_methods `compute_baseline_tm_data`; `200` in welfare6_scenario.py, run_hybrid_welfare6.py, and welfare6_reconcile_sweep.py (setdefault)
**Values:** positive int
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalMAIN_reduced.py, Code/HA-Models/FromPandemicCode/tm_methods.py, Code/HA-Models/FromPandemicCode/welfare6_tm.py, Code/HA-Models/FromPandemicCode/welfare6_scenario.py, Code/HA-Models/FromPandemicCode/run_hybrid_welfare6.py, Code/HA-Models/welfare6_reconcile_sweep.py
**Purpose:** Override the TM AGGREGATION grid size — the distribution grid (m-indexed: mCount; a-indexed: the aCount passed to `build_tm_agg_fiscal_a`), NOT the solver grid. Introduced for the D-6 test of whether refining the TM aggregation grid shrinks the MC-vs-TM-a multiplier residual; now the general grid knob for the Step-5a multiplier run (Run_Dict['tm_mCount'], default 100; `--fast-reproduce` → 40) and the welfare-6 TM baseline/ergodic-init builds. Both AggFiscalMAIN_reduced.py and tm_methods.py print an override notice when the env var is set.
**UPDATED 2026-06-13 (supersedes the earlier "unify to 50" ruling — that was wrong-direction).** Despite the `MCOUNT` name (a fossil from the retired m-indexed TM), this flag is the **live a-indexed (TM-a) aggregation grid `aCount`**: `compute_baseline_tm_data` passes it straight into `build_tm_agg_fiscal_a(agent, aCount=mCount, …)` whenever `tm_a_indexed=True` (canonical). `aCount` provenance audit: headline Step-5a multipliers use **100** (var unset in do_all/run_step5a_only → `AggFiscalMAIN_reduced.py` fallback); welfare-6 TM uses **200**; `tm_methods` standalone default **50**; the builder's own default is **200** ("aCount=200 (was 100) keeps upper grid cells from becoming too sparse with the wider aMax"); only `welfare6_reconcile_sweep.py` sets it (200). So the 50/100/200 spread is partly **accuracy-driven, not pure drift** — and **unifying DOWN to 50 would coarsen the production grid and INCREASE tail-truncation bias** (worse with the canonical `aMax=1300`). Decision split into: (R1) a name-only rename `HAFISCAL_TM_MCOUNT`→`HAFISCAL_TM_ACOUNT` (inert, defaults preserved) and (R2) a separate, owner-gated default-unification that, if done, goes UP to a converged value via candidate→`promote-tables` — never to 50. See `plans/20260613-1755h_tm-mcount-to-acount-rename.md`.
**Refs:** conclusions_private/2026-05-13_tm_a_grid_College_beta_het.md, conclusions_private/2026-05-15_A1_Baseline_TM-a_vs_MC.md

### HAFISCAL_TM_MIXING_GRID
**Default:** `1` (on)
**Values:** `1` = on; anything else = off (exact exp-mult grid). Only consulted for auto-built grids, when `HAFISCAL_TM_FANOUT_GRID` is off and the discretized ψ log-range target > 0
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (`build_tm_agg_fiscal_a`)
**Purpose:** DEFAULT-ON correctness safety net: Alt-3 mixing refinement of the auto-built exp-mult grid — subdivide tail intervals so the local log-spacing < the discretized perm-shock log-range, guaranteeing the discretized TM MIXES (Perron-Frobenius irreducibility; collapsed rows → reducible / ill-conditioned ergodic that is a grid artifact). At the corrected safety=1.0 it adds 0 nodes on the production grid (a byte-identical no-op there); kept for coarser grids, where the auto-repair emits a loud warning reporting how many tail nodes were inserted and what aCount would avoid the repair. Toggle off (exact exp-mult grid): `HAFISCAL_TM_MIXING_GRID=0` — NOT recommended. Custom injected `dist_aGrid` values are never modified, only checked (warn-only). Refinement floor and target are tuned by `HAFISCAL_MIXING_APOL_TOL` and `HAFISCAL_MIXING_SAFETY`.
**Refs:** plans/20260609_ensure_connected_TM_mixing.md, Code/HA-Models/tm_mixing_diagnostic.py (module docstring)


## MC & Shuffle

Context shared by several entries below: the **canonical solution approach (Plan A, 2026-06-10)**
is installed by the `EstimParameters.py` canonical block (lines 30–40) via `os.environ.setdefault`,
so explicit env overrides still win. `EstimParameters` is imported by every entry point
(`Parameters.py`, `welfare6_scenario.py`, `EstimAggFiscalMAIN.py`) before any of these vars are read
at runtime. **Escape hatch:** `HAFISCAL_QE_FIDELITY=1` skips the whole block, so each flag falls back
to its call-site (legacy/QE) default. Decision source:
`conclusions_private/2026-06-10_welfare_method_unified_MC.md` — canonical welfare = MC + CRN +
stratified-shuffle for ALL welfare cells (only `ui_norec` excluded, 0/0 by construction).

### HAFISCAL_AGENTCOUNT_C
**Default:** unset (empty = no override; cohort N falls back to `AgentCountTotal × data_EducShares[2] × pmv[b]`)
**Values:** positive integer — TOTAL N for the College cohort across all `DiscFacCount` β-atoms; per-atom count is `floor(N_cohort × pmv[b])`
**Status:** live
**Read by:** `Code/HA-Models/FromPandemicCode/Simulate.py:304`, `welfare6_scenario.py:308` (behavioral reads); presence-checks (any of D/H/C set ⇒ triggers edu-share auto-rescale): `AggFiscalModel.py:1982,2110`, `tm_methods.py:1367,2669,2991,3095`, `jax_mc_ad_multicohort.py:230`; cache-key member: `solution_cache/keys.py:45`
**Purpose:** Per-cohort MC agent-count override (Phase H-0 origin). Used for welfare quota configs — Baseline 1× quota C=17640 (paper-precision per `2026-05-08_welfare6_baseline_convergence.md`), 5× brute-force. Setting ANY of D/H/C makes per-type `pop_rescale_factor ≠ 1` and (under `HAFISCAL_AGGREGATE_BY_EDU_SHARE=auto`) switches aggregation to edu-share-respecting weights (BUG-042). In the solution-cache key (numerical).
**Refs:** BUGS_private/HAFiscal_BUG-042_edu_share_aggregation_under_cohort_N_override.md; plans/20260506-1640h_edu_share_aggregation_correction.md; conclusions_private/BUG-044_baseline_minA_FINAL.md, BUG-044_baseline_welfare6_FINAL.md, BUG-044_reduced_run_quota_exact.md

### HAFISCAL_AGENTCOUNT_D
**Default:** unset (empty = no override; falls back to `AgentCountTotal × data_EducShares[0] × pmv[b]`)
**Values:** positive integer — TOTAL N for the Dropout cohort across its β-atoms; per-atom `floor(N_cohort × pmv[b])`
**Status:** live
**Read by:** `Code/HA-Models/FromPandemicCode/Simulate.py:302`, `welfare6_scenario.py:306` (behavioral); presence-checks: `AggFiscalModel.py:1982,2110`, `tm_methods.py:1367,2669,2991,3095`, `jax_mc_ad_multicohort.py:229`; cache-key member: `solution_cache/keys.py:43`
**Purpose:** Same mechanism as `HAFISCAL_AGENTCOUNT_C`, for the Dropout cohort. Baseline 1× quota D=4900. Triggers BUG-042 edu-share auto-rescale when set. In the solution-cache key.
**Refs:** BUGS_private/HAFiscal_BUG-042_edu_share_aggregation_under_cohort_N_override.md; plans/20260506-1640h_edu_share_aggregation_correction.md; conclusions_private/BUG-044_baseline_minA_FINAL.md, BUG-044_baseline_welfare6_FINAL.md, BUG-044_reduced_run_quota_exact.md

### HAFISCAL_AGENTCOUNT_H
**Default:** unset (empty = no override; falls back to `AgentCountTotal × data_EducShares[1] × pmv[b]`)
**Values:** positive integer — TOTAL N for the Highschool cohort across its β-atoms; per-atom `floor(N_cohort × pmv[b])`
**Status:** live
**Read by:** `Code/HA-Models/FromPandemicCode/Simulate.py:303`, `welfare6_scenario.py:307` (behavioral); presence-checks: `AggFiscalModel.py:1982,2110`, `tm_methods.py:1367,2669,2991,3095`, `jax_mc_ad_multicohort.py:229`; cache-key member: `solution_cache/keys.py:44`
**Purpose:** Same mechanism as `HAFISCAL_AGENTCOUNT_C`, for the Highschool cohort. Baseline 1× quota HS=9800. Triggers BUG-042 edu-share auto-rescale when set. In the solution-cache key.
**Refs:** BUGS_private/HAFiscal_BUG-042_edu_share_aggregation_under_cohort_N_override.md; plans/20260506-1640h_edu_share_aggregation_correction.md; conclusions_private/BUG-044_baseline_minA_FINAL.md, BUG-044_baseline_welfare6_FINAL.md, BUG-044_reduced_run_quota_exact.md

### HAFISCAL_AGENTCOUNT_TOTAL
**Default:** unset
**Values:** integer (intended total agent count, e.g. `160000` for Baseline 5×)
**Status:** deprecated (was: diagnostic) — owner ruling 2026-06-13. Echo-only with NO behavioral consumer and no history of one. Do NOT use it in recipes; use the `--agent-count-total` CLI arg of `welfare6_scenario.py` or the `HAFISCAL_AGENTCOUNT_{D,H,C}` env trio instead.
**Read by:** `Code/HA-Models/FromPandemicCode/jax_mc_baseline_5x_bench.py:24` — **echo-only** (printed into the bench log; never consumed behaviorally)
**Purpose:** Documentation-only echo of the intended total-N for a benchmark run. **This flag has NO behavioral consumer and never had one** (verified `git log -S` across all branches: the only commit ever touching it is the bench-file creation, 89d177c5). The "brute-force 5×" recipe cited in memory/agendas as `HAFISCAL_AGENTCOUNT_TOTAL=160000` is actually implemented by either (a) the `--agent-count-total` CLI arg of `welfare6_scenario.py` (line 829 → `build_and_solve(agent_count_total=...)`, which overrides `AgentCountTotal` and splits by edu shares), or (b) the `HAFISCAL_AGENTCOUNT_{D,H,C}` env trio.
**RESOLVED 2026-06-13 (owner ruling: deprecate).** Marked deprecated (see Status). The brute-force-5× recipe should use `--agent-count-total` / the `HAFISCAL_AGENTCOUNT_{D,H,C}` trio. Follow-up (not blocking): correct the stale recipe wording in `agenda_2026_06_03.md:196`, `agenda_2026_06_11_DRAFT.md:127`, and memory `project_welfare6_brute_force_5x_paper_precision`.
**Refs:** conclusions_private/2026-06-10_welfare_method_unified_MC.md (brute-force-5× named as the unbiased alternative to stratified-shuffle); conclusions_private/_FINAL_RESULTS_baseline_5x_4seed.md; BUGS_private/HAFiscal_BUG-042_*.md, HAFiscal_BUG-043_*.md

### HAFISCAL_AGGREGATE_BY_EDU_SHARE
**Default:** `auto`
**Values:** `auto` (rescale ONLY when any `HAFISCAL_AGENTCOUNT_{D,H,C}` override is set) | `on`/`1`/`true` (always rescale) | anything else, e.g. `off` (never rescale)
**Status:** live
**Read by:** `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:1979` (`mill_rule`, AD inner-loop aggregation), `AggFiscalModel.py:2107` (`run_experiment` final aggregation), `tm_methods.py:1364,2666,2988,3092` (TM aggregation paths), `jax_mc_ad_multicohort.py:227` (JAX-AD weights mode); cache-key member: `solution_cache/keys.py:40`
**Purpose:** BUG-042 fix. Under a cohort-N override the raw per-agent sum no longer respects `data_EducShares`; this applies per-type `pop_rescale_factor` weights (= standard_AgentCount / actual_AgentCount) so aggregates (AggCons, AggIncome, Cratio) match population proportions. Under standard config all factors are exactly 1.0, so `auto` is a no-op — behavior identical whether or not overrides exist elsewhere. Fixing this closed the noAD MC-vs-TM residual to ~zero and ~7–25% of the AD residual. In the solution-cache key (numerical).
**Refs:** BUGS_private/HAFiscal_BUG-042_edu_share_aggregation_under_cohort_N_override.md; plans/20260506-1640h_edu_share_aggregation_correction.md; conclusions_private/2026-05-06_FINAL_edu_share_aggregation_and_remaining_AD_residual.md, 2026-05-06_FINAL_AD_loop_residual_is_finite_N_MC_artifact.md

### HAFISCAL_INCOME_SHUFFLE
**Default:** `''` (off)
**Values:** `1` (on) | anything else (off)
**Status:** live
**Read by:** `Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py:771`, `Simulate.py:352`, `welfare6_scenario.py:345` — each sets the `income_shuffle` attr on all agent types; consumed by HARK 0.17's sim path (`HARK/ConsumptionSaving/ConsMarkovModel.py:1055-1060`: income-shock draws with deterministic expected frequencies instead of iid draws)
**Purpose:** Opt-in MC variance reduction on per-period income-shock draws (deterministic shock frequencies within each Markov cell). Companion to `HAFISCAL_MC_SHUFFLE` but NOT part of the canonical Plan-A block (no setdefault; remains off unless explicitly enabled). Requires N ≥ per-cohort minimum-occupancy threshold for full determinism (see minimum-replicates plan).
**Refs:** plans/20260408-1024h_minimum-replicates-for-shuffle.md; plans/20260425-1015h_reproduce-self-documenting-runs.md; conclusions_private/2026-05-11_shuffle_ui_welfare_crn_breakdown.md; implementation commits a3ec91af

### HAFISCAL_MARKOV_SHUFFLE
**Default:** `''` (off)
**Values:** `1` (on) | anything else (off)
**Status:** live
**Read by:** `Code/HA-Models/FromPandemicCode/Simulate.py:353`, `welfare6_scenario.py:346` — set the `markov_shuffle` attr on all agent types; consumed by HARK's sim path (`HARK/ConsumptionSaving/ConsMarkovModel.py:776,1007`: per-period Markov-state transitions drawn via `MarkovProcess.draw(..., shuffle=True)` — quota-matched counts instead of iid draws)
**Purpose:** Opt-in MC variance reduction on HARK-internal per-period Markov transitions (the normal `simulate()`/`make_history` path — distinct from `HAFISCAL_MC_SHUFFLE`, which governs HAFiscal's own experiment shock-history construction). Not set in `EstimAggFiscalMAIN.py` (that entry point wires only mc_shuffle + income_shuffle). Not part of the canonical Plan-A block.
**Refs:** conclusions_private/2026-05-04_h0-shuffle-validation-and-recalibration-leverage.md; conclusions_private/2026-05-11_shuffle_ui_welfare_crn_breakdown.md

### HAFISCAL_MC_PLVL_INIT
**Default:** `analytic_markov`
**Values:** `analytic_markov` | `analytic_markov_conditional` | `analytic_employed` | `legacy_synthetic`
**Status:** live
**Read by:** `Code/HA-Models/FromPandemicCode/Simulate.py` (TM-init block, `mc_use_tm_init=True` path) and `tm_methods.initialize_mc_from_tm_ergodic` (kept in sync) — selects how each agent type's MC `pLvl` cross-section is seeded; also overridable via `Run_Dict['mc_plvl_init']`.
**Purpose:** Selects the permanent-income marginal of the MC initial cross-section (the `(j, aNrm)` seed always comes from the TM-a ergodic). The marginal modes draw `N=AgentCount` **stratified** representative `pLvl` values (invert the analytic ergodic mixture CDF at quantiles `(i-0.5)/N`) and **randomly permute** them across agents so `pLvl` attaches independently of the agent's `(j, aNrm)` *and* age draw (the `pLvl ⊥ aNrm` modeling assumption); N distinct values, `O(1/N)` discretization error.
- `analytic_markov` (default) is the **unemployment-aware** ergodic: a per-`(age, employment-state)` Gaussian mixture built from the exact Markov recursion `tm_methods._pLvl_markov_moment_recursion` (per-state growth `G_j`, per-state log-shock variance, BUG-003 deterministic newborn, the agent's actual `MrkvArray`). By construction it reproduces `compute_log_p_moments_exact` (the existing exact mean/var of `log p`) to machine precision — i.e. the seed matches the *true* with-unemployment ergodic to first/second moments (Tier A; the exact within-cohort `(age, employed-count)` shape, Tier B, is deferred).
- `analytic_markov_conditional` uses the **same** per-`(age, state)` recursion cells but draws each agent's `pLvl` from *its own* `(age, base-Mrkv-state)` cell (`tm_methods.sample_pLvl_conditional_markov`) rather than from the pooled marginal — so the seeded `pLvl` is **correlated with the agent's age and employment state** instead of independent of them. This roughly halves the `var(log p)` warmup *overshoot* the pooled marginal exhibits (independent seeding decorrelates `pLvl` from `(age, state)`; the warmup then re-correlates it, transiently overshooting). Still `pLvl ⊥ aNrm` *within* a state — the within-state `a`–`p` correlation is the TM-ap joint, not modeled here. **CAVEAT (2026-06-13): not recommended at production per-cohort N.** Conditioning fragments `N` across ~`T_age·J` (~200) cells, leaving only ~`N/200` agents/cell; this defeats stratification (small-`k` quantiles truncate the Gaussian tails → cell variance biased low) and is noisy for random draws, so the *init* aggregate `var(log p)` undershoots (≈−12% at N=1500 HS_Only) — worse than the pooled marginal, which stratifies all `N` in one pass and is init-exact (≈−0.1%). Both seeds converge to the same finite-population-noise floor after warmup; the pooled marginal (default) is the better seed at realistic `N`.
- `analytic_employed` is the EMPLOYED-ONLY mixture (G_emp growth, employed perm-shock variance, all age periods employed — no unemployment). Use when you want the no-unemployment benchmark.
- `legacy_synthetic` keeps the older per-age random draw that folds the TM ergodic unemployment rate into growth and shock-variance (bit-identical to pre-2026-06-13 behavior).
`analytic_markov`/`analytic_employed` feed `tm_methods.sample_pLvl_steady_state(..., pLvl_dist=)` → `_pLvl_markov_mixture_components` / `_pLvl_mixture_components`; `analytic_markov_conditional` calls `tm_methods.sample_pLvl_conditional_markov` directly. All share component math with `compute_pLvl_distribution` / `compute_log_p_moments_exact` (BUG-003 first-step-deterministic; BUG-019 (1-u) variance scaling).
**Refs:** conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md

### HAFISCAL_MC_SHUFFLE
**Default:** `1` (ON — canonical, set by `EstimParameters.py:31` `os.environ.setdefault`, which every entry point imports). Under `HAFISCAL_QE_FIDELITY=1` the setdefault is skipped and the call-site default `''` (OFF) applies — the legacy/published-QE world.
**Values:** `1` (on) | anything else (off)
**Status:** live
**Read by:** `Code/HA-Models/FromPandemicCode/EstimParameters.py:31` (setdefault), `EstimAggFiscalMAIN.py:770`, `Simulate.py:351`, `welfare6_scenario.py:344` — each sets the `mc_shuffle` attr on all agent types; consumed at `AggFiscalModel.py:2082` (`AggregateDemandEconomy.run_experiment` dispatches to `AggFiscalType._hit_with_recession_shock_shuffled`, def at line 839)
**Purpose:** Master switch for the deterministic (shuffled) construction of experiment Markov shock histories: state-transition counts match expected frequencies instead of iid per-agent draws, eliminating sampling noise on state counts so MC aggregates match TM's analytical fractions. Canonical welfare method = MC + CRN + stratified-shuffle (decision 2026-06-10); this flag is the "shuffle ON" leg, with the transition algorithm chosen by `HAFISCAL_SHUFFLE_MRKV_TRANSITION` and newborn handling by `HAFISCAL_SHUFFLE_NEWBORN_FIX`. Because the setdefault lives in `EstimParameters`, the ON default applies to ALL MC paths that import it (Step-5 `Simulate.py`, welfare6, `EstimAggFiscalMAIN.py`) unless overridden or under QE_FIDELITY. Requires N ≥ per-cohort minimum-occupancy threshold for full determinism (Smoke_Test N=100 may be below threshold).
**Config-category:** **BUG-FIX, not a discretionary "variance-reduction" choice.** Despite the "variance-reduction" wording above, reliable UI welfare is a *correctness requirement*: without stratified-shuffle the UI welfare cells swing 27–29% between replicates (the `1x↔2x` count noise) — numbers unreliable to the point of meaningless. BUG-044/HARK PR #1776 makes the per-state counts exact and the cells reliable. Therefore this stays **ON in BOTH `default` AND `as-corrected`** (it is mandatory in every world; it is NOT reverted in the bug-fixed-counterfactual world). Owner ruling 2026-06-13; see `conclusions_private/20260613_config-worlds-definition-default-legacy.md`.
**Refs:** conclusions_private/2026-06-10_welfare_method_unified_MC.md (decision); conclusions_private/20260613_config-worlds-definition-default-legacy.md (config-category ruling); plans/20260408-1024h_minimum-replicates-for-shuffle.md; plans/20260408-1213h_single-cohort-plus-shuffle-implementation.md; plans/20260610_post_merge_canonicalize_default_solution.md; conclusions_private/2026-05-11_shuffle_ui_welfare_crn_breakdown.md

### HAFISCAL_MC_SPLURGE
**Default:** `0.2461138828477288` (the HARK-0.14.1 splurge estimate)
**Values:** float (splurge factor)
**Status:** diagnostic
**Read by:** `Code/HA-Models/FromPandemicCode/EstimParameters.py:117` — only consumed when MC-determinism-test mode is active (`HAFISCAL_MC_DETERMINISM_TEST=1` or `--mc-test` in argv; see that flag's entry in the diagnostics section)
**Purpose:** Cross-version (HARK 0.14.1 vs 0.17.0) determinism testing: overrides the Step-1-estimated `Splurge` with a fixed canonical value so both versions start bit-identically. Inert in normal runs (the gate flag is off by default).
**Refs:** (no plans/BUGS/conclusions refs found; gate documented at `EstimParameters.py:45-48` and `mc_determinism_test.py`)

### HAFISCAL_MC_WARMUP
**Default:** `''` (unset → Run_Dict's `mc_warmup`, normally 24)
**Values:** non-negative integer (number of warmup periods)
**Status:** live
**Read by:** `Code/HA-Models/FromPandemicCode/Simulate.py` (TM-init block) — overrides the post-init warmup length. (welfare6 / `run_hybrid_welfare6.py` use the separate `HAFISCAL_WELFARE6_MC_WARMUP` for the same purpose on the `initialize_mc_from_tm_ergodic` path.)
**Purpose:** After the MC cross-section is seeded from the TM-a ergodic `(j, aNrm)` + the analytic `pLvl` marginal, a short warmup lets residual joint mismatch (the a–p correlation, which the seed omits) settle. This flag exposes that length so the warmup-vs-consequence trade-off can be measured. **Measured (2026-06-13, HS_Only MC consequence sweep):** with `pLvl` seeded at its steady state, there is *no detectable systematic warmup transient* in the 10y multipliers — the step-to-step change is flat in warmup length (~0.5–0.7% at every step including 48→96), i.e. an MC noise floor (~0.5–0.9% at N≈2635), not convergence. warmup=0 is already within ~1% of any longer warmup; runs are bit-deterministic given the seed. So warmup length is **not** accuracy-binding; tighter precision is an N / seed-averaging question. **Production default stays 24** (cheap, comfortably in the flat regime). See conclusions §15.
**Refs:** conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md (§15)

### HAFISCAL_MORTALITY_OFF
**Default:** `''` (off — mortality active)
**Values:** `1` (disable all mortality) | anything else (off)
**Status:** diagnostic
**Read by:** `Code/HA-Models/FromPandemicCode/welfare6_scenario.py:358` — sets the `mortality_off` attr on all agents; consumed in `AggFiscalModel.py` (`sim_death` returns all-False at ~line 593; `initialize_sim` skips age-distribution init at ~line 548)
**Purpose:** Diagnostic switch that turns off death/replacement entirely, used for shuffle-vs-nonshuffle asymptotic-convergence verification under a simplified deterministic-income model (combine with `HAFISCAL_PERM_DURING_UNEMP=off`). Distorts the model (no newborn turnover) — never for production numbers.
**Refs:** conclusions_private/BUG-044_asymptotic_convergence_test.md; conclusions_private/BUG-044_systematic_bias_confirmed.md

### HAFISCAL_NORMALIZE_PLVL
**Default:** `''` (off)
**Values:** `1` | `true` | `yes` (on) | anything else (off)
**Status:** diagnostic
**Read by:** `Code/HA-Models/FromPandemicCode/Simulate.py:39` — when on, agent types are built from `NormalizedAggFiscalType` / `NormalizedDualAggFiscalType` (`AggFiscalModel.py:1906,1910`, the `HAFiscalNormalizationMixin`); silently falls back to the plain classes if the import fails
**Purpose:** Opt-in per-period E[pLvl] normalization to remove the MC permanent-income-shock drift identified in `runs/phase_a2_baseline_drift_findings.md`. A diagnostic counter-drift device, not the production answer to drift (production practice: measure and report drift vs the TM-a companion — see the drift flags in the diagnostics section).
**Refs:** runs/phase_a2_baseline_drift_findings.md (no plans/BUGS/conclusions refs found)

### HAFISCAL_PERM_DURING_UNEMP
**Default:** unset/empty = `on` (silent default: Harmenberg-style — unemployed agents draw the same PermShk ψ as employed, enabling pLvl ⊥ state factorization)
**Values:** `on`/`1`/`true`/`yes` | `off`/`0`/`false`/`no` (PermShk≡1 while unemployed — the published HAFiscal-QE assumption, set by the qe_fidelity reproduce profiles) | any other non-empty value → `ValueError`
**Status:** live
**Read by:** `Code/HA-Models/FromPandemicCode/EstimParameters.py:342` → sets `perm_shocks_during_unemployment`, which shapes the unemployed-state `IncShkDstn` (income-process construction)
**Purpose:** Whether unemployed agents receive permanent (ψ) shocks. DISTINCT from `HAFISCAL_PLVL_GROWS_DURING_UNEMP` (which controls the growth factor G during unemployment, default off): this one controls the stochastic ψ draw (default on). Profile-dependent: qe_fidelity sets `off` to match published QE. NOT in the solution-cache env whitelist, but its numerical effect is still captured in the cache key because `keys.py` hashes `IncShkDstn` atoms+probs directly (keys.py:170-176).
**Refs:** plans/20260503-1655h_perm_shocks_during_unemp_config_split.md; plans/20260504-1450h_qe_fidelity_fast_profile.md; conclusions_private/2026-05-04_qe_fidelity_full_vs_QE_published.md; conclusions_private/2026-05-08_FINAL_ESC_MC_to_CDC_TM_migration_complete.md

### HAFISCAL_PLVL_GROWS_DURING_UNEMP
**Default:** `off` (QE-published convention: unemployed pLvl is FROZEN — no G, and no ψ under `perm_shocks_during_unemployment=False`)
**Values:** `on`/`1`/`true`/`yes` (unemployed pLvl grows at G — the Harmenberg-factorizable convention required for pLvl ⊥ state) | anything else = off
**Status:** live
**Read by:** `Code/HA-Models/FromPandemicCode/EstimParameters.py:331` (+ membership print at :334) → sets `unemp_pLvl_grows_like_employed` / `PermGroFac_unemp`, consumed by both MC and TM-a income processes; cache-key member: `solution_cache/keys.py:38`
**Purpose:** BUG-040 fix. MC's `PermShk=1.0` for the unemployed silently dropped G while TM-a applied G uniformly — the two methods were on DIFFERENT model conventions. This flag unifies them under one explicit convention; both settings are internally consistent. Default `off` matches what the published QE numbers actually compute. (Fixing the inconsistency did NOT close the 13% Check multiplier residual — that was BUG-041.) In the solution-cache key (numerical).
**Refs:** BUGS_private/HAFiscal_BUG-040_pLvl_during_unemp_silent_inconsistency.md; BUGS_private/HARK+HAFiscal_TM_vs_MC_bug_index.md; conclusions_private/2026-05-05_RESOLVED_mc_vs_tm_multiplier_mystery.md; conclusions_private/2026-05-05_bug040_fix_does_not_close_multiplier_residual.md

### HAFISCAL_SEED_OFFSET
**Default:** `0`
**Values:** integer (added to each agent type's RNG seed: `ThisType.seed = n + offset`)
**Status:** diagnostic
**Read by:** `Code/HA-Models/FromPandemicCode/Simulate.py:311` (Step-5 multiplier-MC agent construction only)
**Purpose:** Shifts all per-type RNG seeds for multi-seed replication of Step-5 MC runs (introduced for Phase H-0 shuffle validation, which needed 3+ seed variants). Multi-seed runs are how the mandatory SE on any reported MC bias is computed (SD/√S across offsets); CRN holds within one offset. NOTE: the welfare-6 path does NOT read this env var — `welfare6_scenario.py` has its own `--seed-offset` CLI arg (stride 10000 per offset, line 326).
**Refs:** conclusions_private/2026-05-04_h0-shuffle-validation-and-recalibration-leverage.md

### HAFISCAL_SHUFFLE_MRKV_TRANSITION
**Default:** `stratified` (canonical, set by `EstimParameters.py:32` `os.environ.setdefault`). Under `HAFISCAL_QE_FIDELITY=1` the setdefault is skipped and the call-site default `shuffle` applies (legacy/QE world).
**Values:** `stratified` (BUG-044 fix: rank-based stratified sampling — quota-EXACT per-state counts AND per-agent assignment by draw rank, so it is CRN-coupled with iid via the shared `unemployment_draw_fixed_hist`; asymptotically equivalent to iid by Glivenko–Cantelli) | `iid` (per-agent searchsorted draws, CRN-coupled but no quota exactness — diagnostic reference) | `shuffle` or anything else (plain `MarkovProcess.draw(..., shuffle=True)` with per-period seed)
**Status:** live
**Read by:** `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:921` (inside `_hit_with_recession_shock_shuffled` — only consulted when `HAFISCAL_MC_SHUFFLE` is on); canonical setdefault `EstimParameters.py:32`; cache-key member: `solution_cache/keys.py:42`
**Purpose:** Selects the per-period Markov-transition algorithm used by the shuffled MC shock-history construction. **DANGER — the plain `shuffle` value is the +8.26%-UI-bias footgun:** plain shuffle scrambles per-agent identity across experiments, breaking the CRN coupling that the convex MU-weighted welfare difference depends on → ui_rec biased +8.26% (and +3.76%/+6.59% in earlier BUG-044 measurements). `stratified` (with HARK PR #1776's assignment-step fix) keeps the quota-exactness benefit while preserving CRN: shuffle-vs-nonshuffle agree at ui_rec +0.05%, ui_rec_AD +0.19% at Baseline. This is what makes UI welfare reportable (the earlier "deprecate UI welfare" is superseded). Do NOT set `shuffle` except to reproduce the legacy QE world (use `HAFISCAL_QE_FIDELITY=1` for that wholesale). In the solution-cache key (numerical).
**Config-category:** the `stratified` *value* is part of the **BUG-FIX** (reliable UI welfare; see `HAFISCAL_MC_SHUFFLE` above) — `stratified` stays in BOTH `default` AND `as-corrected`. What is NEVER selectable is the plain `shuffle` value (the +8.26%-UI footgun). So the config axis here is binary in practice: `stratified` (every world) vs the QE-repro escape hatch. Owner ruling 2026-06-13; see `conclusions_private/20260613_config-worlds-definition-default-legacy.md`.
**Refs:** conclusions_private/2026-06-10_welfare_method_unified_MC.md (decision; §"What we are NOT using"); conclusions_private/20260613_config-worlds-definition-default-legacy.md (config-category ruling); conclusions_private/BUG-044_asymptotic_convergence_test.md, BUG-044_baseline_minA_FINAL.md; plans/20260610_post_merge_canonicalize_default_solution.md; HARK PR #1776

### HAFISCAL_SHUFFLE_NEWBORN_FIX
**Default:** `transition` (canonical, set by `EstimParameters.py:33` `os.environ.setdefault`). Under `HAFISCAL_QE_FIDELITY=1` the setdefault is skipped and the call-site default `off` applies (legacy/QE world).
**Values:** `transition`/`on`/`1`/`true` (newborns transition normally per the conditional Markov array — the canonical, BUG-044-validated choice) | `off`/`0`/`false` (original behavior: newborns frozen at their post-spike state) | `emp` (newborns forced to micro=0, employed) | unknown values → warn + fall back to `off`
**Status:** live
**Read by:** `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:994` (inside `_hit_with_recession_shock_shuffled`'s per-period loop — only consulted when `HAFISCAL_MC_SHUFFLE` is on); canonical setdefault `EstimParameters.py:33`
**Purpose:** How newborn agents (t_age==0) get their Markov state inside the shuffled shock-history construction. The legacy `off` preserved newborns at the post-spike state (wrong in the marginal distribution). `transition` matches the non-shuffle marginals. NOTE: the in-code comment at `AggFiscalModel.py:986-992` ("welfare CRN broken, bias INCREASES on UI cells" for `transition`) is STALE — it describes behavior under the plain-`shuffle` transition mode and predates the stratified fix; the canonical combination stratified + transition is the validated production config (ui_rec +0.05% vs non-shuffle). Not in the solution-cache env whitelist (its effect is in the forward sim, and the companion `SHUFFLE_MRKV_TRANSITION` IS keyed).
**Config-category:** **BUG-FIX** companion of the stratified-shuffle fix (the newborn marginal-distribution correction). Stays `transition` in BOTH `default` AND `as-corrected`. Owner ruling 2026-06-13; see `conclusions_private/20260613_config-worlds-definition-default-legacy.md`.
**Refs:** conclusions_private/2026-06-10_welfare_method_unified_MC.md (canonical flag set listed in §"UI is reportable"); conclusions_private/20260613_config-worlds-definition-default-legacy.md (config-category ruling); conclusions_private/BUG-044_baseline_minA_FINAL.md, BUG-044_baseline_welfare6_FINAL.md


## Welfare-6

### HAFISCAL_CHECK_BUCKETS
**Default:** `50` (empty/unparseable/<1 falls back to 50)
**Values:** integer ≥ 1
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py
**Purpose:** Number of pLvl quantile buckets for the TM-side stimulus-Check construction (`_compute_check_buckets`): the check's income phase-out makes the integrand p·c(m+g(p),j) with g(p) non-constant, breaking Harmenberg p-linearity, so TM must discretize the pLvl distribution — one transition matrix per bucket, mass-weighted. BUG-022 fix raised the default 5→50: 5 buckets put the phase-out kink (pLvl=25) inside one bucket, biasing the norec-check TM multiplier ~+3.3-3.9%; 50 is within 0.07% of n=200 (converged) at negligible cost. Bucket Riemann error decays ~1/n². Swept by `Code/HA-Models/welfare6_reconcile_sweep.py` (R-2; sets the var for its TM subprocesses). The φ(pLvl) bucketing is also the diagnosed structural limit of bucketed-5D TM check_rec welfare (~+0.9% vs MC) — use MC for the check welfare cell.
**Refs:** BUGS_private/HAFiscal_BUG-022_check_bucket_discretization.md, history/20260331-mathematical-derivations-TM-MC-convergence.md §13.5.1, plans/20260409-1552h_tm_mc_baseline_discrepancy_debug.md, conclusions_private/2026-06-08_overnight_check_rec_reconciliation.md

### HAFISCAL_IS_FORCE_LOW_ANRM
**Default:** unset (no override)
**Values:** float (forced aNrm value) | unset
**Status:** deprecated (was: diagnostic) — owner ruling 2026-06-13. The active importance-sampling welfare pathway (`welfare6_scenario_IS.py`) is permanently superseded by the 2026-06-10 unified-MC + CRN + stratified-shuffle decision; this flag (and its module) are off the table for production.
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario_IS.py
**Purpose:** In the importance-sampling welfare driver (forced-unemployed intake, "sim B"), additionally force every agent's `aNrm_base` (and consistently `bNrm_base`, `mNrm_base`=aNrm+0.5) to the given value at intake. Built to test the asset-distribution-bias hypothesis for the ~+10% ui_rec IS bias: if forcing low aNrm closes it, the bias source is the employed-like asset distribution under the Markov-only override — confirmed; the conclusion was that IS needs joint (aNrm, pLvl, Mrkv) sampling. The whole active-IS welfare pathway was NOT adopted (2026-06-10 decision = unified MC + CRN + stratified-shuffle).
**Refs:** conclusions_private/_USER_RETURNS_README_2026-05-11.md, conclusions_private/2026-06-10_welfare_method_unified_MC.md
**RESOLVED 2026-06-13 (owner ruling: deprecate).** See Status — active IS is permanently off the table.

### HAFISCAL_WELFARE6_FIX_DUR_AVG
**Default:** `on`
**Values:** `on`/`1`/`true` (per-duration fix) | anything else (legacy duration-averaged)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/run_hybrid_welfare6.py, Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py
**Purpose:** BUG-046 fix in the welfare-6 aggregation: compute the welfare integrand (u(c_pol)−u(c_none))/MU(c_base) PER recession-duration panel, then weight by `rec_probs` — instead of the legacy (Jensen-biased) u(duration-AVERAGED cLvl). Applies only when `per_dur_cLvl_all_splurge` panels exist in both policy and counterfactual results (recession cells); no-recession cells use the single-panel path regardless. NPV terms are linear in cLvl so they are unaffected either way. Toggle off only to reproduce the pre-fix numbers.
**Refs:** BUGS_private/HAFiscal_BUG-046_welfare6_jensen_duration_average.md, conclusions_private/2026-05-16_BUG046_FINAL_summary.md, conclusions_private/2026-05-16_canonical_config_recommendation.md

### HAFISCAL_WELFARE6_MC_WARMUP
**Default:** `24`
**Values:** integer (warmup periods)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/run_hybrid_welfare6.py, Code/HA-Models/FromPandemicCode/welfare6_scenario.py
**Purpose:** Number of `sim_one_period` warmup periods passed to `initialize_mc_from_tm_ergodic` in the welfare6 BUG-052 ergodic warm-start (lets residual distributional mismatch settle after seeding MC at the TM-a ergodic; 24 quarters ≈ 2 business cycles, matching the tm_methods signature default). Scope note: this env var covers only the two welfare6 entry points — the multiplier pipeline (Simulate.py) takes the same parameter from `Run_Dict['mc_warmup']` instead, not from this var. Only consulted when HAFISCAL_WELFARE6_TM_INIT is on.
**Refs:** BUGS_private/HAFiscal_BUG-052_welfare6_cold_start_vs_ergodic_calibration.md (warm-start apparatus), Code/HA-Models/FromPandemicCode/tm_methods.py `initialize_mc_from_tm_ergodic`

### HAFISCAL_WELFARE6_TM_INIT
**Default:** `1` (ON)
**Values:** `0` (cold-start, off) | anything else (on)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/run_hybrid_welfare6.py, Code/HA-Models/FromPandemicCode/welfare6_scenario.py
**Purpose:** BUG-052 fix, DEFAULT ON since 2026-06-08: initialize the welfare-6 MC at the TM-a ergodic wealth distribution — the same warm-start the multiplier pipeline uses — instead of the cold a≈0 init. The β-calibration targets ergodic wealth (estimation burns in T_sim=T_age·2, settles to E[aNrm]≈0.31), so cold-start welfare was calibration-inconsistent (check_rec 1.0140 cold → 1.0196 ergodic, +0.55%). Sets `tm_a_indexed=True` on all agents, builds baseline TM data (`compute_baseline_tm_data`, mCount from HAFISCAL_TM_MCOUNT, measure from HAFISCAL_WELFARE6_TM_INIT_MEASURE), then `initialize_mc_from_tm_ergodic` with HAFISCAL_WELFARE6_MC_WARMUP periods; injected AFTER `make_history` / BEFORE `save_state` so `run_experiment`'s use_prestate restores the ergodic prestate. `0` = cold-start for isolation/paper-trail only — explicitly NOT a QE-reproduction goal (not part of HAFISCAL_QE_FIDELITY). Guard test: Code/HA-Models/test_welfare6_ergodic_init.py.
**Refs:** BUGS_private/HAFiscal_BUG-052_welfare6_cold_start_vs_ergodic_calibration.md, plans/20260608_ergodic_welfare_migration_plan.md, plans/20260608_plan_A_5D_welfare_extension.md, conclusions_private/2026-06-08_ergodic_welfare_bridge.md

### HAFISCAL_WELFARE6_TM_INIT_MEASURE
**Default:** `P`
**Values:** `Q` (Harmenberg permanent-income-neutral ergodic) | anything else = `P` (actual-agent measure)
**Status:** live (default `P`); the `Q` value is **deprecated** (owner ruling 2026-06-13) — it has no valid production use for seeding actual agents (the Q/Harmenberg ergodic is for TM aggregation, not real-agent init).
**Read by:** Code/HA-Models/FromPandemicCode/run_hybrid_welfare6.py, Code/HA-Models/FromPandemicCode/welfare6_scenario.py
**Purpose:** Which ergodic measure seeds the welfare-6 MC when HAFISCAL_WELFARE6_TM_INIT is on: `P` (default; `neutral_measure=False`) matches Simulate.py's `tm_neutral_measure` default and is correct for seeding ACTUAL agents — the Q/Harmenberg ergodic is for TM aggregation, not for real-agent initialization. Tested as a candidate explanation during the check_rec MC-vs-TM gap investigation and found to make no difference (P/Q identical there — red herring).
**Refs:** conclusions_private/2026-06-08_ergodic_welfare_bridge.md (warm-start wiring); inline comments at the two read sites
**RESOLVED 2026-06-13 (owner ruling: deprecate the `Q` value).** See Status; `P` remains the live default.

### HAFISCAL_PROV_CHILD
**Default:** unset (standalone runs emit their own per-scenario provenance sidecar)
**Values:** `1` = this process is a child of the parallel welfare-6 driver (suppress its own sidecar); anything else = standalone
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py (`main`, gates `_emit_provenance_sidecar`); set by Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py (child env, `_child_env`)
**Purpose:** Parent→child marker for the parallel welfare-6 pipeline. `run_welfare6_parallel.py` sets `HAFISCAL_PROV_CHILD=1` in each spawned `welfare6_scenario.py` child's environment so the child SKIPS writing its own per-scenario provenance sidecar; the parallel driver instead emits ONE aggregate sidecar next to the welfare-6 table (12 child sidecars in the scratch pickle dir — and 12× pip-freeze — would be redundant). A standalone `welfare6_scenario.py` run (flag unset) still writes its sidecar. (Note: the full `MC_PLVL_INIT` / `MC_WARMUP` entries are in the MC/Welfare section above.)
**Refs:** Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py (child-env block); Code/HA-Models/FromPandemicCode/welfare6_scenario.py (sidecar gate)


## JAX & Speedups

All flags in this section are opt-in toggles for the experimental JAX stack
(MC forward-sim kernel, AD outer loop, EGM solver). None are enabled by the
canonical Plan-A pipeline (the `EstimParameters.py` canonical block sets none
of them); the dev orchestrator `run_welfare6_parallel.py` turns several on for
its children. Two cross-cutting facts:

- **Paper-grade caveat (CLAUDE.md):** JAX-AD with independent RNG converges to
  a systematically different AD fixed point than HARK (25.4σ at the HS_Only
  `check_rec_AD` welfare cell); the ~6% welfare-cell gap is RNG-realization,
  not a kernel bug. Paper-grade welfare from the JAX stack goes through
  replay-v2 (`verify_welfare_replay.py`), not through these flags.
- **Parsing is inconsistent across the family** — the five `JAX_MC_*` flags
  and `USE_JAX_SOLVER` require the literal string `1` (so `=on`/`=true`
  silently do nothing), while the `USE_JAX_2B*`/`USE_JAX_MC*`/
  `HARK_REFSIM_FULL` flags accept `1`/`on`/`true` (case-insensitive).

This section reconciles and supersedes the flag table in
`Code/HA-Models/jax_mc_speedup/README.md` (which documents the five
`JAX_MC_*` speedup toggles + `USE_JAX_SOLVER`); per-flag parity numbers below
are from `plans/20260520_jax_mc_speedup_status.md`.

### HAFISCAL_HARK_REFSIM_FULL
**Default:** unset (fast path: 1-step ref sim)
**Values:** `1` | `on` | `true` = run the legacy full ~40-step forward sim; anything else = fast 1-step sim
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/jax_mc_ad_multicohort.py:130
**Purpose:** The JAX-AD auto-init (`_build_init_panels_via_hark_quick_sim`) runs a HARK no-AD reference sim to capture `history[0]` as the JAX kernel's t=0 init panel. `history[0]` is fully determined by `initialize_sim` + recession shock + 1 kernel step, so the default runs `make_history` for T_sim=1 only (~40 min → ~1 min at Baseline; verified bit-identical to the full sim at HS_Only). Setting this flag restores the full forward sim as a paranoia/regression safety net. Note the inverted sense: the flag *disables* the fast path. `run_welfare6_parallel.py:98` pops it from child envs as hygiene.
**Refs:** Code/HA-Models/FromPandemicCode/jax_mc_ad_multicohort.py:63-99 (docstring); CLAUDE.md "JAX MC kernel" (auto-init)

### HAFISCAL_JAX_MC_BATCH_TABLES
**Default:** `0`
**Values:** `0` | `1` (strict string compare — `on`/`true` are ignored)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/jax_mc_ad_multicohort.py:35 (module import time — set before importing)
**Purpose:** Speedup 1C — stacks all cohorts' cfunc tables into one tensor and does a single host→device transfer per AD iter (instead of one per cohort). Silently inert unless 1A (`HAFISCAL_JAX_MC_USE_2D_LIFT=1`) is also on (conjunction gate at jax_mc_ad_multicohort.py:492; no error). Skipped when 2A handles the cohorts. Speedup-only: parity 5.45e-8 vs baseline at HS_Only/Reduced_Run; deliberately excluded from the solution-cache key (solution_cache/keys.py:18-24).
**Refs:** plans/20260520_jax_mc_speedup_status.md; Code/HA-Models/jax_mc_speedup/README.md; conclusions_private/2026-05-20_jax_mc_speedup_and_cache.md, conclusions_private/2026-05-21_hark-jax_handoff.md

### HAFISCAL_JAX_MC_LAZY_PANEL
**Default:** `0`
**Values:** `0` | `1` (strict string compare)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/jax_mc_ad_multicohort.py:38 (module import time)
**Purpose:** Speedup 1D — skips `cLvl_panel` materialization on non-final AD iters (the panel is only needed for the welfare cells, computed after convergence; see the `materialize` gate at jax_mc_ad_multicohort.py:568). Requires 1A+1B on to matter; silently inert otherwise. Parity 2.25e-7 at HS_Only/Reduced_Run; excluded from the solution-cache key.
**Refs:** plans/20260520_jax_mc_speedup_status.md; Code/HA-Models/jax_mc_speedup/README.md; conclusions_private/2026-05-20_jax_mc_speedup_and_cache.md

### HAFISCAL_JAX_MC_USE_2D_LIFT
**Default:** `0`
**Values:** `0` | `1` (strict string compare)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/jax_mc_ad_multicohort.py:28 (module import time)
**Purpose:** Speedup 1A — replaces the per-period cFunc table rebuild with a bilinear-in-C `(m, C)` lift (≈3× fewer cFunc evaluations at Baseline). Foundation flag for the whole 1B/1C/1D/2A chain: every other `JAX_MC_*` speedup is conjunction-gated on this one and silently inert without it. Parity 2.25e-7 at HS_Only/Reduced_Run; excluded from the solution-cache key.
**Refs:** plans/20260520_jax_mc_speedup_status.md; Code/HA-Models/jax_mc_speedup/README.md; conclusions_private/2026-05-20_jax_mc_speedup_and_cache.md

### HAFISCAL_JAX_MC_VMAP_COHORTS
**Default:** `0`
**Values:** `0` | `1` (strict string compare)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/jax_mc_ad_multicohort.py:41 (module import time)
**Purpose:** Speedup 2A — runs ALL cohorts in one vmap'd JIT call (padding each cohort's N to max_N), replacing the per-cohort Python loop. Requires 1A+1B (gate at jax_mc_ad_multicohort.py:470) and is additionally auto-bypassed under `use_shuffle=True` and for policy scenarios (`recessionCheck`/`recessionTaxCut`); all bypasses silent. Parity 1.11e-7. Measured: 0.99× at HS_Only (1 cohort — overhead exceeds savings), 1.16× at Reduced_Run (all of 1A-2A on), est. 2-3× at Baseline (not measured as of the status plan). Excluded from the solution-cache key.
**Refs:** plans/20260520_jax_mc_speedup_status.md; Code/HA-Models/jax_mc_speedup/README.md; conclusions_private/2026-05-21_hark-jax_handoff.md

### HAFISCAL_JAX_MC_VMAP_SEEDS
**Default:** `0`
**Values:** `0` | `1` (strict string compare)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/jax_mc_ad_multicohort.py:31 (module import time)
**Purpose:** Speedup 1B — runs all MC seeds in one vmap'd JIT call per cohort instead of a Python loop over seeds. Requires 1A (gate at jax_mc_ad_multicohort.py:555) and is bypassed under `use_shuffle=True`; silently inert otherwise. Prerequisite for 1D and 2A. Parity 2.25e-7 at HS_Only/Reduced_Run; excluded from the solution-cache key.
**Refs:** plans/20260520_jax_mc_speedup_status.md; Code/HA-Models/jax_mc_speedup/README.md; conclusions_private/2026-05-20_jax_mc_speedup_and_cache.md

### HAFISCAL_REFSIM_PARALLEL
**Default:** unset (serial `eco_ref.solve()`)
**Values:** integer string N ≥ 2 = fork N cohort-solve workers; unset/`1`/non-digit = serial
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/jax_mc_ad_multicohort.py:106
**Purpose:** Cohort-parallel solve for the JAX-AD auto-init HARK ref sim: uses fork-based `parallel_solve.parallel_eco_solve` with plain HARK `solve_agent` in each worker (bypasses the 2B-aware persistent pool in `welfare6_scenario`). Only affects the one ref-sim solve inside `_build_init_panels_via_hark_quick_sim`; bit-identical output (cohort scheduling only). HAZARD: `run_welfare6_parallel.py:97` pops it from child envs because inheriting it into 4 concurrent children would cascade into 4×21 = 84 fork workers.
**Refs:** Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py:85-100 (hazard comment); memory project_parallel_solve_baseline_2026_05_19 (parallel_eco_solve provenance)

### HAFISCAL_AD_INIT_CACHE
**Default:** unset (off)
**Values:** `1` | `on` | `true` (case-insensitive) = on; additionally requires `HAFISCAL_USE_SOLUTION_CACHE=1`
**Status:** diagnostic (opt-in speedup; default path byte-unchanged)
**Read by:** Code/HA-Models/solution_cache/cache.py:247 (`_recession_init_cache_enabled`, gating `save_recession_init_cache`/`load_recession_init_cache`)
**Purpose:** Lever #1 — shared **recession-init solve cache**. The cold per-cohort recession EGM solve done by the JAX-AD init ref sim (`jax_mc_ad_multicohort._build_init_panels_via_hark_quick_sim`) is bit-identical to the no-AD recession scenario's solve (same shock_type, flat belief, same calibration) and is ~89% of the JAX-AD loop wall at Baseline (~1188 s). When on, `welfare6_scenario.run_recession` POPULATES a per-(parametrization, shock_type) cache (tagged `hark_solve_only`, distinct from the `ad_*` AD-converged cache) and the AD init CONSUMES it, skipping the redundant cold solve. Measured 9.35× AD-loop speedup at Baseline (1337 s → 143 s), bit-identical AggCons (rel 0.0). Best-effort + gated: any miss/failure falls back to the normal cold solve, never a wrong result. CAVEAT: under the concurrent welfare launcher the no-AD and AD children start together, so the in-pipeline win requires the no-AD recession scenarios to run/save BEFORE the AD ones (or a re-run that HITs the on-disk cache).
**Refs:** Code/HA-Models/FromPandemicCode/jax_mc_ad_multicohort.py:104 (consumer); Code/HA-Models/FromPandemicCode/welfare6_scenario.py:702 (producer); memory project_ad_speedup_gpu_fix_and_stale_cache

### HAFISCAL_USE_JAX_2B
**Default:** unset (off — HARK `solve_agent` iter loop)
**Values:** `1` | `on` | `true` (case-insensitive) = on
**Status:** live — **SANCTIONED for production welfare runs** (owner ruling 2026-06-13). Serial-2B at Baseline is paper-grade (recessionCheck rel diff −0.120%, 0.045% welfare-cell shift; conclusions_private/2026-05-22_morning_summary.md). Caveat: it is NOT bit-identical to HARK (~1e-3, worst 8.9e-3), so it is (correctly) IN the solution-cache key, and the CURRENTLY-FROZEN paper numbers were produced with HARK, not 2B. Using 2B to regenerate frozen outputs therefore still goes through the candidate→`promote-tables` workflow; sanctioning means the ~1e-3 deviation is accepted as production-grade.
**RESOLVED 2026-06-13 (owner ruling Q2: SANCTIONED for production — confirmed).** See Status. **Cleanup TODO (not a contradiction anymore):** a 2026-06-12 econ-mw code comment in `run_welfare6_parallel.py` (~:90-96) still labels 2B "DEV-ONLY" and that runner no longer `setdefault`s 2B into child envs. The owner confirmed the "sanctioned" ruling stands; the stale comment should be corrected and the child-env behavior reconciled to it. Tracked in plans/20260613-1830h_config-taxonomy-reconciliation-post-econ-mw-merge.md (Q2).
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py:2304 (`AggregateDemandEconomy.solve`); Code/HA-Models/FromPandemicCode/welfare6_scenario.py:94 (spawn-pool `_solve_agent_worker`); Code/HA-Models/jax_mc_speedup/jax_solver_iterated_drop_in.py:133 (`is_enabled`); Code/HA-Models/solution_cache/keys.py:62 (cache-key member)
**Purpose:** Speedup 2B — replaces HARK's per-agent `solve_agent` Python iter loop with the JAX-native `lax.while_loop` solve (`jax_solver_iterated_drop_in.solve_to_convergence_consumer_solution`), warm-start handling unchanged. 1.66× at Baseline end-to-end (3121s → 1885s). Parity vs HARK ~1e-3 (kernel-parity range, 8.9e-3 worst), NOT bit-identical — therefore IN the solution-cache key so 2B-solved and HARK-solved entries never cross-load. HARD GUARD (BUG-047 matched-pair): raises RuntimeError unless `HAFISCAL_PERMGROFAC_FIX=1`, because the 2B EGM kernel applies PermGroFac^(−CRRA) unconditionally (no legacy FIX=0 branch). `experiments/append.py:224` records it in run metadata; `welfare6_reconcile_sweep.py:69` and `test_welfare6_ergodic_init.py:38` pin it to `0`.
**Refs:** BUGS_private/HAFiscal_BUG-047_permgrofac_marginal_value_factor.md; conclusions_private/2026-05-21_morning_summary.md, conclusions_private/2026-05-22_morning_summary.md; Code/HA-Models/jax_mc_speedup/test_2B_while_loop_parity.py; CLAUDE.md (2B parity test bullet)

### HAFISCAL_USE_JAX_2B_THREADS
**Default:** `1` (no threading)
**Values:** integer ≥ 1 (non-integer raises ValueError at read)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py:2366 (serial-2B path only)
**Purpose:** When >1 and `HAFISCAL_USE_JAX_2B` is on (and `_VMAP` is not), solves cohorts via a `ThreadPoolExecutor` with N threads. JAX kernel calls release the GIL during dispatch+compute, so threads truly parallelize while sharing the JAX runtime/JIT cache/memory (vs ~17 GB RSS per process under process parallelism) — ~1.5-2× on the solve step at Baseline. `run_welfare6_parallel.py` sets 8 for CPU children, 2 for GPU children. Ignored when 2B is off or the vmap variant is active.
**Refs:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py:2360-2364 (rationale comment); Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py:102-128

### HAFISCAL_USE_JAX_2B_VERBOSE
**Default:** unset (quiet)
**Values:** `1` | `on` | `true` (case-insensitive) = verbose
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py:2322
**Purpose:** Logging only — passes `verbose=True` into the 2B solver calls (per-agent convergence progress). No numerical effect. Only consulted when `HAFISCAL_USE_JAX_2B` or `_VMAP` is on.
**Refs:** (none beyond read site)

### HAFISCAL_USE_JAX_2B_VMAP
**Default:** unset (off)
**Values:** `1` | `on` | `true` (case-insensitive) = on
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py:2305; Code/HA-Models/jax_mc_speedup/jax_solver_iterated_multicohort.py:362 (`is_enabled`); Code/HA-Models/solution_cache/keys.py:63 (cache-key member)
**Purpose:** Vmap-across-cohorts variant of 2B: solves ALL cohorts' Bellman iterations in one JIT call (`solve_all_cohorts_to_convergence_consumer_solutions`); takes precedence over the serial/threaded 2B path. Numerically equivalent to serial 2B (parity 4e-10) but kept in the cache key for forensics (different code path). PARKED — not a Baseline win: GPU OOM at 21-cohort all-at-once, CPU OOM (192 GB), and chunked vmap loses the win to iter-count spread (each chunk runs to its slowest cohort's iter count). Subject to the same BUG-047 PERMGROFAC_FIX=1 hard guard as 2B. `run_welfare6_parallel.py:99` pops it from child envs.
**Refs:** conclusions_private/2026-05-22_morning_summary.md ("Cohort vmap of 2B: not a Baseline win"); Code/HA-Models/solution_cache/keys.py:63-65

### HAFISCAL_USE_JAX_2B_VMAP_CHUNK
**Default:** unset (all cohorts in one vmap call)
**Values:** integer string = chunk size; non-digit/unset = unchunked
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py:2349 (only when `HAFISCAL_USE_JAX_2B_VMAP` is active)
**Purpose:** Bounds memory in the 2B vmap path by splitting the cohort vmap into chunks of N (the OOM mitigation for the 21-cohort all-at-once failure). Trade-off: chunking forfeits much of the vmap win because each chunk runs to the max iter count within the chunk.
**Refs:** conclusions_private/2026-05-22_morning_summary.md

### HAFISCAL_USE_JAX_MC
**Default:** unset (off — HARK MC AD loop)
**Values:** `1` | `on` | `true` (case-insensitive) = on
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py:696 (`run_recession_AD`)
**Purpose:** Routes the recession AD outer loop through the JAX multicohort MC driver (`cached_solve_ad_recession` → `solve_ad_recession_jax_multicohort`) instead of HARK MC (`cached_solve_ad_recession_hark`). Supported shock types: `recession`, `recessionUI`, `recessionCheck`, `recessionTaxCut` (the `JAX_AD_SUPPORTED_SCENARIOS` set at welfare6_scenario.py:703 — note the adjacent comment claiming Check/TaxCut are "not yet wired" is stale; all four shipped 2026-05-19). End-to-end ~1.9× at Baseline 5x. Requires `run_base()` to have populated `base_AggCons` (RuntimeError otherwise). CAVEAT: JAX-AD with independent RNG converges to a systematically different AD fixed point (25.4σ welfare-cell at HS_Only; ~6% gap is RNG-realization, not kernel error) — NOT paper-grade; use `verify_welfare_replay.py` (replay-v2) for paper-grade welfare. `run_welfare6_parallel.py:93` setdefaults it to `1` for its children; `test_jax_mc_ad_regression.py` is the regression harness.
**Refs:** CLAUDE.md "JAX MC kernel for forward simulation"; conclusions_private/2026-05-19_morning_jax_mc_overnight_report.md, conclusions_private/2026-05-19_jax_stratified_shuffle_design.md, conclusions_private/2026-05-20_jax_mc_speedup_and_cache.md

### HAFISCAL_USE_JAX_MC_REPLAY
**Default:** unset (off)
**Values:** `1` | `on` | `true` (case-insensitive) = on
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py:746 (post-AD in `run_recession_AD`; consumer: jax_mc_replay_production.verify_jax_replay_matches_hark)
**Purpose:** Verification-only side check — after the AD solve, re-runs the JAX kernel as a replay against HARK's captured `shock_history` + `sim_birth` outputs and prints bit-precision agreement (pass = max rel diff < 1e-3). Does NOT change any output. Only acts for `shock_type='recession'` (prints a skip message for others). Distinct from the standalone `verify_welfare_replay.py` CLI (the paper-grade replay-v2 welfare tool), which does not read this flag.
**Refs:** Code/HA-Models/FromPandemicCode/jax_mc_replay_production.py (module docstring); conclusions_private/2026-05-19_morning_jax_mc_overnight_report.md; memory project_jax_mc_rng_alignment_2026_05_19

### HAFISCAL_USE_JAX_SOLVER
**Default:** `0`
**Values:** `0` | `1` (strict string compare — `on`/`true` are ignored)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py:476 (`build_and_solve` installs on all agents); Code/HA-Models/FromPandemicCode/jax_solver_drop_in.py:314 (`maybe_install_via_env` — convenience helper with no in-scope caller)
**Purpose:** Replaces `agent.solve_one_period` with the JAX EGM kernel (P1-P6 validated <1e-3 vs HARK across all per-state cFunc evaluations at HS_Only recession, StateCount=132). HARK still drives the iter loop and convergence check — which is why it is ~4.6× SLOWER than HARK at recession scale (Python dispatch overhead per iter) and why, unlike 2B, it is EXCLUDED from the solution-cache key ("validated to give same converged cFunc", keys.py:23). Use only for kernel-correctness regression testing; real speedup is deferred to a JAX-native iter loop + GPU. Import failure degrades gracefully (prints, falls back to HARK). `jax_mc_speedup/combined_parallel_jax_test.py` validates it composes with cohort-parallel solve.
**Refs:** plans/20260519_jax_solver_port_plan.md; conclusions_private/2026-05-19_hark_solver_jax_port_feasibility.md; CLAUDE.md "JAX solver kernel (experimental, opt-in via env)"; Code/HA-Models/jax_mc_speedup/README.md


## Diagnostics

### HAFISCAL_DRIFT_DIAG_DIST
**Default:** `0`
**Values:** `1` (on) | anything else (off)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/Simulate.py
**Purpose:** Extra per-agent printout inside the MC⇄TM-a drift check (after TM-ergodic init + warmup): MC fraction of agents with aNrm below thresholds (1e-9…1.0) and aNrm percentiles (10/25/50/75/90), side-by-side with the TM-a ergodic percentiles. For diagnosing constraint-mass / distribution-shape mismatches that the headline drift metrics summarize away. No effect unless the drift test runs (see HAFISCAL_SKIP_DRIFT_TEST).
**Refs:** plans/20260503-1437h_mc_tma_companion_and_drift.md (drift-check apparatus)

### HAFISCAL_DRIFT_DIAG_POST_INIT
**Default:** `0`
**Values:** `1` (on) | anything else (off)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/Simulate.py
**Purpose:** Capture and print MC cross-section moments (mean/var log a, mass-at-zero, mean/var log p) IMMEDIATELY after the TM-ergodic MC initialization, BEFORE the warmup periods — distinguishes "init is wrong" from "warmup drifts away" when the post-warmup drift test fails. Also echoes the first few intended aNrm/aLvl/pLvl samples.
**Refs:** plans/20260503-1437h_mc_tma_companion_and_drift.md (drift-check apparatus)

### HAFISCAL_DRIFT_HARD_FAIL
**Default:** `1`
**Values:** `1` (raise RuntimeError on drift > threshold) | anything else (downgrade to WARNING)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/_tm_a_drift.py
**Purpose:** Failure mode of the MC⇄TM-a drift gate (`assess_and_report`), which runs by default after every TM-ergodic MC initialization (Simulate.py warm-start path). Per user direction 2026-05-03 the default is HARD-FAIL: drift beyond HAFISCAL_DRIFT_THRESHOLD aborts the run. Set `0` to downgrade to a warning. Note: `run_step5a_only.py` sets `0` in its qe-fidelity env defaults (warn-only); `scripts/run_with_tma_companion.py` sets `1` explicitly.
**Refs:** plans/20260503-1437h_mc_tma_companion_and_drift.md, plans/20260504-1300h_qe_fidelity_speedup_systematic_test.md

### HAFISCAL_DRIFT_THRESHOLD
**Default:** `0.03` (module constant `_DEFAULT_THRESHOLD`)
**Values:** float (fraction)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/_tm_a_drift.py
**Purpose:** Threshold for the MC⇄TM-a drift gate. Interpretation is metric-specific: PRIMARY = Lorenz-share drift at p20/40/60/80 in percentage points (threshold×100 → default ±3pp); the mean log(aNrm) absolute log-diff also uses ±threshold. log(a) moments and aNrm percentiles are reported but are NOT fail criteria (constraint-mass artifacts). **The pLvl moments (mean/var log(p)) no longer use this fixed threshold** — they use the N-aware statistical band (see `HAFISCAL_DRIFT_PLVL_NAWARE`). Used with HAFISCAL_DRIFT_HARD_FAIL.
**Refs:** plans/20260503-1437h_mc_tma_companion_and_drift.md

### HAFISCAL_DRIFT_PLVL_NAWARE
**Default:** `1` (ON — module constant `_PLVL_DRIFT_NAWARE`)
**Values:** `1` (N-aware band) | `0` (legacy fixed `HAFISCAL_DRIFT_THRESHOLD`)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/_tm_a_drift.py (`assess_and_report`)
**Purpose:** Makes the pLvl-moment drift gate (mean & var log(p)) N-aware instead of a fixed ±0.03. Accepts `|drift − center| ≤ z·scale/√N` (`z` from `HAFISCAL_DRIFT_PLVL_Z`), so a fixed 0.03 no longer spuriously hard-fails at production N. Calibrated 2026-06-13. Set `0` to restore the legacy fixed threshold. The PRIMARY aNrm Lorenz metric is unaffected.
**Refs:** conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md (§14)
**Added:** econ-mw merge 2026-06-13.

### HAFISCAL_DRIFT_PLVL_Z
**Default:** `3.090` (module constant `_PLVL_DRIFT_Z`; 0.2% two-sided standard-normal critical value)
**Values:** float
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/_tm_a_drift.py (`assess_and_report`)
**Purpose:** The standard-normal critical value setting the width of the N-aware pLvl drift band (`center ± z·scale/√N`). `3.090` ⇒ P(false-fail | correct calibration) ≈ 0.2% (owner direction 2026-06-13: keep the gate on but conservative; raw drift value always printed). Lower it for a stricter gate. Only used when `HAFISCAL_DRIFT_PLVL_NAWARE=1`.
**Refs:** conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md (§14)
**Added:** econ-mw merge 2026-06-13.

### HAFISCAL_FAST_GRIDS
**Default:** unset (off)
**Values:** `1`/`true`/`yes` (case-insensitive, on) | anything else (off)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/Parameters.py
**Purpose:** Coarsen solution grids for fast smoke/diagnostic runs: aXtraCount 48→24, PermShkCount 7→5, TranShkCount 7→5. Changes numerics — never use for production results; intended for asymptotic-equality and speed testing. Forwarded to subprocesses by run_step5a_only.py's passthrough list.
**Refs:** plans/20260403-1253h_asymptotic-equality-test-plan.md

### HAFISCAL_MC_DETERMINISM_TEST
**Default:** unset (off)
**Values:** `1` (on; the `--mc-test` CLI flag is equivalent) | anything else (off)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py, Code/HA-Models/FromPandemicCode/EstimParameters.py
**Purpose:** Cross-HARK-version (0.14.1-bugfixed vs 0.17.0-native) MC determinism harness for Step 2: skips the full discount-factor optimization, evaluates the objective at the optimizer's fixed initial values, reduces AgentCountTotal to 500, overrides Splurge to the canonical 0.14.1 value (via HAFISCAL_MC_SPLURGE), and writes per-agent results to JSON for comparison. Orchestrated by `Code/HA-Models/mc_determinism_test.py` (which sets this var in each version's subprocess; note its two codebase paths are hard-coded). Proves both versions produce identical MC results single-threaded with synchronized RNG.
**Refs:** plans/20260425-1252h_reproduce-full-codebase-critique.md, Code/HA-Models/mc_determinism_test.py module docstring

### HAFISCAL_PHASER_DUMP
**Default:** unset (off)
**Values:** `1` (on) | anything else (off)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py
**Purpose:** "PHASE-R" shuffle-bug investigation dumps (BUG-044 era, commit 2b189f27): prints Markov macro/micro state-count tallies (Counter dicts, tagged with agent seed) at three checkpoints of `hit_with_recession_shock` — entry (pre-spike), post-unemployment-spike, and post-first-transition — in BOTH the non-shuffle (`nshuf-*`) and shuffle (`shuf-*`) variants. Used to compare shuffle-vs-stochastic Mrkv transition realizations. Also gates (together with HAFISCAL_PHASER_GUTS) the per-source transition dump in `get_micro_markv_states_guts`.
**Refs:** conclusions_private/BUG-044_baseline_minA_FINAL.md and other conclusions_private/BUG-044_*.md (shuffle-bias investigation); commit 2b189f27

### HAFISCAL_PHASER_GUTS
**Default:** unset (off)
**Values:** `1` (on; only effective when HAFISCAL_PHASER_DUMP=1 as well) | anything else (off)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py
**Purpose:** Deeper, very verbose layer of the PHASE-R dumps: inside `get_micro_markv_states_guts` (every simulated period), prints per-(macro, source-micro) transition outcome distributions, source-state counts, and the active CondMrkvArrays row — for pinpointing exactly which transition cell mis-assigns agents. Requires HAFISCAL_PHASER_DUMP=1; the two are ANDed at the single read site.
**Refs:** conclusions_private/BUG-044_*.md (shuffle-bias investigation); commit 2b189f27

### HAFISCAL_RUN_SLOW_TESTS
**Default:** unset (slow test skipped)
**Values:** `1` (run) | anything else (skip)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/test_jax_mc_ad_regression.py
**Purpose:** pytest `skipif` gate for the slow JAX-vs-HARK AD regression test (subprocess-runs `jax_mc_ad_make_hark_ref.py` + `jax_mc_ad_solve_validate.py` at HS_Only and pins Cratio agreement within 2%). Skipped in CI by default; set `1` to opt in. Currently the only consumer is this one test module.
**Refs:** Code/HA-Models/FromPandemicCode/test_jax_mc_ad_regression.py docstring; CLAUDE.md "Diagnostic & validation tools"

### HAFISCAL_SKIP_DRIFT_TEST
**Default:** `0` (drift test runs)
**Values:** `1` (skip) | anything else (run)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/Simulate.py
**Purpose:** Skip the entire MC⇄TM-a drift measurement block (including the HAFISCAL_DRIFT_DIAG_DIST extras) that otherwise runs after TM-ergodic MC initialization + warmup. Debugging escape hatch only — drift measurement on MC runs is mandatory project policy; prefer HAFISCAL_DRIFT_HARD_FAIL=0 (measure but warn) over skipping.
**Refs:** plans/20260503-1437h_mc_tma_companion_and_drift.md

### HAFISCAL_TIERS
**Default:** `0`
**Values:** comma-separated tier integers, e.g. `0`, `0,1`, `0,1,2,3,4,5`
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/test_co_drift_sweep.py
**Purpose:** Selects which tiers of the BUG-038 College-cohort drift sweep cascade to run (standalone `main()` script, not collected as a pytest test despite the name). Tier 0 = §24.5-exact counterfactual at N=200k; higher tiers scale N (1/√N noise-floor fit), grid, T_age, shock atoms. Cascade halts at the first failing tier. Generic name — collision-prone; rename candidate at next touch.
**Refs:** plans/20260501-0809h_co-drift-sub-1pct-test-plan.md, BUGS_private/HAFiscal_BUG-038_T_age_cap_removal.md; commit aa185be4

---

## econ-mw merge (2026-06-13): flags re-filed

> The five env flags that arrived in the 2026-06-13 econ-mw integration merge
> (`HAFISCAL_MODE`, `HAFISCAL_MC_PLVL_INIT`, `HAFISCAL_MC_WARMUP`,
> `HAFISCAL_DRIFT_PLVL_NAWARE`, `HAFISCAL_DRIFT_PLVL_Z`) have been re-filed into
> their thematic sections above (Pipeline & Infrastructure, MC/Welfare-6, and
> Diagnostics respectively); each carries an **Added: econ-mw merge 2026-06-13**
> line. `HAFISCAL_MODE` was subsequently **renamed** to `HAFISCAL_MULTIPLIER_ENGINE`
> (values `tm`/`mc`) per owner ruling Q3 (2026-06-13), resolving the naming collision;
> `HAFISCAL_MODE` is retained as a deprecated alias for one cycle. See the
> config-taxonomy reconciliation
> (plans/20260613-1830h_config-taxonomy-reconciliation-post-econ-mw-merge.md).

<!-- end econ-mw re-filed flags -->

## Step-1 FTI (opt-in NAM/ATI solver)

Flags for the opt-in fast-time-iteration (Newton Arbitrage Method / Accelerated Time
Iteration) cFunc transplant in Step-1 (beta/splurge estimation). All `diagnostic`:
the default Step-1 path (EGM) is byte-identical when `HAFISCAL_STEP1_FTI` is unset.
Wiring: `Code/HA-Models/Target_AggMPCX_LiquWealth/fti_step1.py`; solver:
`Code/HA-Models/FromPandemicCode/hark_fti/`.

### HAFISCAL_STEP1_FTI
**Default:** `0` / unset (stock EGM Step-1 path; byte-identical)
**Values:** `1` = enable the FTI cFunc transplant; anything else = OFF
**Status:** diagnostic
**Read by:** Code/HA-Models/Target_AggMPCX_LiquWealth/fti_step1.py (`STEP1_FTI_ON`); Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py (solve/simulate seam); test_fti_step1.py
**Purpose:** Master opt-in switch for Step-1. When `1`, each discount-factor type is solved by EGM (host) and the equivalent `IndShockConsumerTypeFTI` solve is attempted; its `cFunc` is safe-grafted onto the KinkedR host (simulate/RNG path untouched) only if it converged and agrees with EGM, else EGM is kept (transparent fallback). Default OFF → original `multi_thread_commands([...'solve()'...])` line runs verbatim.
**Refs:** Code/HA-Models/Target_AggMPCX_LiquWealth/fti_step1.py; Code/HA-Models/FromPandemicCode/hark_fti/PROVENANCE.md; llorracc/fast-time-iteration plans/20260616-0553h_merge-fti-into-hafiscal-tm-vs-mc.md (Phase 2)

### HAFISCAL_FTI_METHOD
**Default:** `NAM`
**Values:** `NAM` | `ATI` | `NAMG` (case-insensitive; validated against `hark_fti.FTI_METHODS` + `NAMG`)
**Status:** diagnostic
**Read by:** Code/HA-Models/Target_AggMPCX_LiquWealth/fti_step1.py (`FTI_METHOD`)
**Purpose:** Selects which solver the Step-1 transplant uses. `NAM`/`ATI` are the per-call fast-time-iteration realizations (White's Newton Arbitrage Method / Winant's Accelerated Time Iteration — the same algorithm, two engineerings); both fall back to EGM at the GIC edge. `NAMG` is the opt-in GLOBAL Newton (`hark_fti.global_newton`): it removes the lagged-continuation outer loop so the most-patient (GPF-Mod≈0.999) discount-factor type converges in ~20 grid-independent Newton steps and the safe graft FIRES there (vs EGM fallback). NAMG sizes its own grid top via the closed-form `namg_auto_grid` (see `HAFISCAL_STEP1_FTI_AUTOEXTEND`). Only consulted when `HAFISCAL_STEP1_FTI=1`. NOTE: the EGM host is still solved (the simulator reads its full `ConsumerSolution`); NAMG currently swaps the *policy* (correctness), the full wall-clock win awaits driving the simulator from NAMG's own solution.
**Refs:** Code/HA-Models/FromPandemicCode/hark_fti/PROVENANCE.md; conclusions_private/2026-06-16_gic-edge-global-newton-NAMG.md; llorracc/fast-time-iteration README.md

### HAFISCAL_FTI_REPO
**Default:** unset (auto-locate)
**Values:** filesystem path to a `fast-time-iteration` checkout that contains `hark_fti/`
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/_hark_fti_path.py (`find_fti_repo`)
**Purpose:** Opt-in override for locating the sibling `fast-time-iteration` repo so `import hark_fti` resolves. The generic FTI solvers were re-homed out of HAFiscal into the private `llorracc/fast-time-iteration` repo (2026-06-17, canonical home); HAFiscal consumes them only as a strictly opt-in import. `find_fti_repo()` checks `$HAFISCAL_FTI_REPO` first, then a sibling `../fast-time-iteration` checkout (and an editable `uv pip install -e` is found via the normal import path). The DEFAULT HAFiscal reproduction does not import `hark_fti` at all, so this is unset on the default path — set it only when running an opt-in FTI/NAM/NAMG site and the sibling isn't auto-found.
**Refs:** CLAUDE.md (FTI/NAM re-home banner); conclusions_private/2026-06-17_fti-generic-solvers-rehomed-to-fast-time-iteration.md

### HAFISCAL_STEP1_FTI_AUTOEXTEND
**Default:** `1` (the solver sizes its own grid top)
**Values:** `1` = let the solver auto-extend the grid top; `0` = solve on the host's grid
**Status:** diagnostic
**Read by:** Code/HA-Models/Target_AggMPCX_LiquWealth/fti_step1.py (`FTI_AUTOEXTEND`)
**Purpose:** Toggles the solver's grid-top auto-sizing. For `NAM`/`ATI` this is the discovery-based `autoExtendGridTop` form (~6×target). For `NAMG` it maps to the closed-form `namg_auto_grid` (top = `headroom/(1−GPF-Mod)`, floored; no discovery cycles — NAMG overrides backward induction so it cannot use `autoExtendGridTop`). Default ON because the patient (GIC-edge) discount-factor types need a grid top well above the default to converge accurately; OFF gives shared-knot parity with EGM on the host's grid (useful for parity checks). Only consulted when `HAFISCAL_STEP1_FTI=1`.
**Refs:** llorracc/fast-time-iteration memory/MEMORY.md (autoExtendGridTop); findings 20260615-1547h

### HAFISCAL_STEP1_FTI_MAXITERS
**Default:** `1000`
**Values:** positive integer (Newton-iteration budget for the safe-graft convergence guard)
**Status:** diagnostic
**Read by:** Code/HA-Models/Target_AggMPCX_LiquWealth/fti_step1.py (`GRAFT_MAX_ITERS`)
**Purpose:** Safe-graft convergence threshold: the FTI policy is grafted only if the solve converged in fewer than this many Newton iterations (converged moderate types use <~250; a non-converged GIC-edge solve hits the solver's ~5000 cap). Keeps the patient-type fallback to EGM automatic. Only consulted when `HAFISCAL_STEP1_FTI=1`.
**Refs:** Code/HA-Models/Target_AggMPCX_LiquWealth/fti_step1.py (`_fti_is_trustworthy`)

### HAFISCAL_STEP1_FTI_ATOL
**Default:** `5e-2`
**Values:** positive float (max allowed |cFunc_FTI − cFunc_EGM| on the resolved region)
**Status:** diagnostic
**Read by:** Code/HA-Models/Target_AggMPCX_LiquWealth/fti_step1.py (`GRAFT_ATOL`)
**Purpose:** Safe-graft agreement tolerance: the FTI policy is grafted only if it agrees with the EGM host to within this absolute tolerance on the resolved region above the borrowing constraint. Guarantees the opt-in ON result never departs from the EGM answer by more than this where ergodic mass lives. Only consulted when `HAFISCAL_STEP1_FTI=1`.
**Refs:** Code/HA-Models/Target_AggMPCX_LiquWealth/fti_step1.py (`_fti_is_trustworthy`)

### HAFISCAL_STEP1_FTI_FORCE
**Default:** `0` / unset (safe-graft guard active)
**Values:** `1` = graft unconditionally (skip convergence/agreement guard); else = guarded
**Status:** diagnostic
**Read by:** Code/HA-Models/Target_AggMPCX_LiquWealth/fti_step1.py (`GRAFT_FORCE`)
**Purpose:** Benchmarking escape hatch: graft the FTI policy even if it did not converge or disagrees with EGM. For Phase-3 speed/accuracy measurement of plain NAM/ATI on the patient types; never for production estimation. Only consulted when `HAFISCAL_STEP1_FTI=1`.
**Refs:** llorracc/fast-time-iteration plans/20260616-0553h_merge-fti-into-hafiscal-tm-vs-mc.md (Phase 3)

### HAFISCAL_STEP1_GIC_LEGACY
**Default:** `0` / unset (BUG-060 fix active: corrected GPF_out cap)
**Values:** `0` (corrected cap, default) | `1` (pre-BUG-060 legacy cap)
**Status:** live (bug-fix escape hatch; result-changing)
**Read by:** Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py (`FagerengObjFunc` GIC taper); test_fti_step1.py (`_tapered_betas`)
**Purpose:** Selects the Step-1 discount-factor GIC taper cap. Default (`0`) uses the **corrected** AGGREGATE-stationarity bound `GICmaxBeta = (Gamma_ind/(L·E[1/psi]))^rho / R` with the agent's *individual* `PermGroFac` (= 1.0) — the same `GPF_out`=1 boundary and multiplicative form as Step 2's `EstimParameters.py` (BUG-037 Change c). `1` restores the pre-BUG-060 cap `(1−L) + PermGroFacAgg^rho/R`, which used the *aggregate* `PermGroFacAgg` (≠1) and the old additive form (~0.00067 too loose). The fix re-tapers the top ~2 atoms (≤0.0006 in beta) and therefore slightly changes the estimated splurge — a Step-1 re-estimation + candidate promotion is required to fold the new value into production; the published QE numbers are preserved on the frozen tag. This is the AGGREGATE condition only; the most-patient atom's individual-target `GPF_in` stays >1 by design under either setting.
**Refs:** BUGS_private/HAFiscal_BUG-060_step1_gic_taper_aggregate_gamma_and_old_formula.md; BUGS_private/HAFiscal_BUG-037_pLvl_init_not_economy_average.md (Change c); conclusions_private/2026-06-16_gic-inside-vs-outside-individual-target-vs-tm-ergodic.md

### HAFISCAL_STEP2_KEEP_REDUNDANT_SOLVE
**Default:** unset (new fast behavior: the redundant cold re-solve is dropped)
**Values:** `1` = restore the legacy `'solve()'`-included command list; anything else = dropped
**Status:** live (read on the default Step-2 estimation path; results-preserving)
**Read by:** Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py:839 (`_baseline_commands()`)
**Purpose:** Each Step-2 (discount-factor) objective evaluation solved every agent twice — once **warm** via `AggDemandEconomy.solve()` (`solve_agent`, `from_solution=<prev NM iterate>`), then again **COLD** via the leading `'solve()'` in the `_mtc(... baseline_commands)` call (HARK `AgentType.solve()` ignores the warm prev solution). `_baseline_commands()` drops that leading `'solve()'` so the simulator consumes the already-converged warm solution (~21 redundant cold solves/eval removed at production N). Results-preserving: both solutions are converged to HARK's distance tol, so simulated moments differ only at O(tol), far below the Nelder-Mead resolution (`xtol=1e-2`) — the NM objective `distance` is identical to 2.3e-10 in the N=500 determinism test. Set `1` to restore the old cold-re-solve list for bisection / exact-legacy reproduction.
**Refs:** llorracc/fast-time-iteration findings/20260617-1030h_step2-drop-redundant-cold-resolve.md; findings/20260617-0130h_step2-anderson-speedup-assessment.md; plans/step2_solve_speedups (HAFiscal-Latest .cursor/plans)

### HAFISCAL_STEP2_NAMG
**Default:** `0` / unset (stock HARK EGM base solve; byte-identical)
**Values:** `1` = enable the multi-state global-Newton (NAMG) base solver; anything else = OFF
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py:2444 (`_step2_namg_enabled`, consumed in `AggregateDemandEconomy.solve`); Code/HA-Models/solution_cache/keys.py (cache-key member); Code/HA-Models/FromPandemicCode/fti_diagnostics/_poc_step2_anderson_qualify.py, .../_poc_step2_anderson_policy_parity.py (diagnostics; the POC file names retain the historical `anderson` token)
**Purpose:** Opt-in Step-2 speedup. When `1`, each **base / AD-off** agent's stationary policy is solved by the multi-state global-Newton solver (`hark_fti.global_newton_markov.solve_stationary_NAMG_markov(method='newton', c_init=<prior policy>)`; converges in ~11 Newton steps directly from the warm `c_init` — 0 Coleman warmup, no cold-seed M3 stall — to a MACHINE-PRECISION Euler root post the FTI decay-tail repair, vs the superseded Anderson ~2e-3 fixed-grid floor) instead of HARK EGM, then the 1-D-per-state policy is wrapped into the 2-D `c(m,Cratio)` `ConsumerSolution` the `AggFiscalType` simulator expects (AD-off ⇒ identical `Cgrid` slices). **Strictly additive / qualification-gated:** fires only when `num_macro_states==1` AND `permgrofac_fix_on()` (the NAMG kernel applies the `(PermGroFac·PermShk)^(-CRRA)` factor unconditionally — refusing FIX=0 is the BUG-047 matched-pair guard, same as `HAFISCAL_USE_JAX_2B`) AND `BoroCnstArt==0` AND uniform `LivPrb` AND per-state params map cleanly; recession/AD-on cells, non-convergence, or any error fall back to the exact EGM `solve_agent`. Policy parity ~3.56e-3 vs EGM on HS_Only — NOT bit-identical, and this is EGM's *own* gap from the true root (the global Newton is MORE accurate than EGM's floored 75-sweep policy, so it sits slightly further from EGM than the superseded Anderson 2.26e-3) ⇒ IN the solution-cache key so NAMG- and EGM-solved entries never cross-load; because the path is confined to `num_macro_states==1` (where the AD-on Step-5 cache is never used) the key entry is belt-and-suspenders. Default OFF ⇒ committed `DiscFacEstim_*` betas unchanged; enabling it for a real re-estimation is an IMPROVEMENT routed via candidate/promote. **History:** née `HAFISCAL_STEP2_ANDERSON` (the base-solve path first used a multi-state Anderson contraction; renamed 2026-06-21 when it was repointed at the global-Newton solver — the old flag survives as a deprecated alias below).
**Refs:** llorracc/fast-time-iteration findings/20260617-1200h_step2-anderson-base-solver-optin.md; findings/20260616-1700h_namg-anderson-beats-global-newton-multistate.md; BUGS_private/HAFiscal_BUG-047_permgrofac_marginal_value_factor.md; Code/HA-Models/FromPandemicCode/test_step2_namg_base_solver.py

### HAFISCAL_STEP2_ANDERSON
**Default:** `0` / unset
**Values:** `1` = enable the Step-2 NAMG base solver (deprecated spelling of `HAFISCAL_STEP2_NAMG`)
**Status:** deprecated
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py:2444 (`_step2_namg_enabled`, back-compat branch); Code/HA-Models/solution_cache/keys.py (cache-key member, kept so the alias also invalidates the cache)
**Purpose:** DEPRECATED alias of `HAFISCAL_STEP2_NAMG`, kept one cycle for back-compat. The Step-2 opt-in was renamed 2026-06-21 when the base-solve path was repointed from the original multi-state Anderson contraction to the global-Newton (NAMG) solver (`method='newton'`, a machine-precision Euler root). Setting `1` still enables the path but emits a `DeprecationWarning`; `HAFISCAL_STEP2_NAMG` takes precedence and does not warn. Slated for removal after one release cycle. See `### HAFISCAL_STEP2_NAMG`.
**Refs:** Code/HA-Models/FromPandemicCode/test_step2_namg_base_solver.py (`test_deprecated_anderson_alias`)

### HAFISCAL_STEP2_NAMG_VERBOSE
**Default:** `0` / unset (silent fallback)
**Values:** `1` = log each Step-2 NAMG→EGM fallback; anything else = silent
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py:2569 (`_try_solve_namg_base` exception handler); Code/HA-Models/FromPandemicCode/fti_diagnostics/_poc_step2_anderson_qualify.py
**Purpose:** Diagnostic logging for `HAFISCAL_STEP2_NAMG`. When `1`, `_try_solve_namg_base` prints the reason it fell back to EGM (qualification miss, non-convergence, or exception `repr`) instead of failing silently. No behavioral effect on the solve; only observability. Only meaningful when `HAFISCAL_STEP2_NAMG=1`.
**Refs:** llorracc/fast-time-iteration findings/20260617-1200h_step2-anderson-base-solver-optin.md

### HAFISCAL_SKIP_STEP2_NAMG_ITEST
**Default:** `0` / unset (the integration test runs)
**Values:** `1` = skip the slow build-the-economy integration tests; anything else = run
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/test_step2_namg_base_solver.py (`base_economy` fixture)
**Purpose:** Test-time escape hatch. The `test_step2_namg_base_solver.py` integration tests build + solve the real base estimation economy once (~40s via `EstimAggFiscalMAIN` with `HAFISCAL_SKIP_ESTIMATION=1`). Setting `1` skips that fixture (and the tests that depend on it) so the fast pure-function unit tests can run alone. No production effect — read only by the test suite.
**Refs:** Code/HA-Models/FromPandemicCode/test_step2_namg_base_solver.py

### HAFISCAL_AD_ANDERSON
**Default:** `0` / unset (stock damped-Picard AD outer loop; byte-identical)
**Values:** `1` = enable Anderson acceleration of the AD outer fixed-point loop; anything else = OFF
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py:2683 (`solve_ad_recession`; also `self.ad_anderson` attribute)
**Purpose:** Opt-in PoC speedup for the **aggregate-demand outer fixed point** (Step-5 recession/AD scenarios). The AD loop is a damped-Picard fixed point in the aggregate `CFunc`; when ON, `_ad_anderson_step` mixes the recent `CFunc`-parameter residual history via a tiny least-squares (`_cfunc_to_vec`/`_vec_to_cfunc`) to reach the SAME fixed point in fewer outer iterations. The map and convergence metric are unchanged; only the Old→next update differs. Strictly opt-in: default OFF ⇒ byte-identical loop (first iteration and singular windows fall back to plain Picard `x←G(x)`). PoC; not on any production path.
**Refs:** llorracc/fast-time-iteration findings/20260617-0130h_step2-anderson-speedup-assessment.md; findings/20260616-1700h_namg-anderson-beats-global-newton-multistate.md
