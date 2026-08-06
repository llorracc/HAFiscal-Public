# HAFISCAL_* environment-flag registry

**Single authoritative registry** of every `HAFISCAL_*` environment variable read by
`Code/HA-Models/**/*.py`. 127 flags. Generated 2026-06-11 at commit `e6859407`
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
| `HAFISCAL_TM_MCOUNT` | **Superseded** — it is the live TM-a `aCount` (not the dead m-indexed knob); earlier "unify to 50" was wrong-direction (would coarsen prod grid). Owner ruling 2026-07-25: the FLAG spelling is retained (the R1 flag-rename is dropped); the lying CODE parameter was renamed instead (`compute_baseline_tm_data`/`run_experiment_tm` now take `dist_aGrid_count`). R2 default study still deferred | ✅ code param renamed 2026-07-25; flag spelling kept (owner-ratified); R2 default study deferred |

**Remaining follow-ups (not owner-review questions):**
- `HAFISCAL_TM_MCOUNT`: the R1 flag-rename (→`HAFISCAL_TM_ACOUNT`) was DROPPED by
  owner ruling 2026-07-25 — the flag spelling stays; the honest name landed in the
  CODE instead (`dist_aGrid_count` parameter). Still open, separately and
  owner-gated: study the production default (UP to a converged value, NOT down
  to 50). See `plans/20260613-1755h_tm-mcount-to-acount-rename.md`.
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
**Default:** unset — the legacy (top-40) paths use the QE-era base `48`; under the extended-grid default paths (measured-Q K·h̄ / `SOLVE_AMAX`) the count-scaling BASIS defaults to **192** (count-converged; owner pre-approved ruling 2026-07-23 — the HS_Only pipeline probe measured C192 at +0.4 min over C48). Setting this env overrides the basis everywhere; a code-level count override (e.g. `FAST_GRIDS` → 24) also wins.
**Values:** positive integer
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (base-count get + membership-print); Code/HA-Models/FromPandemicCode/Parameters.py (Step-5 base-count mirror); Code/HA-Models/grid_sizing.py (`resolve_solve_grid`, the SST policy since 2026-07-24 — the membership guard that blocks the basis-192 promotion)
**Purpose:** Overrides `aXtraCount`, the base number of end-of-period asset gridpoints above the minimum in the household solver's `aXtraGrid`. Prints `[axtra-override] ...` when set. Used for solver-grid-convergence sweeps; production leaves it unset. Numerically load-bearing when set, but no cache-key gap: `solution_cache` keys on the resulting `aXtraGrid` contents directly. **Count-convergence finding (2026-07-23):** the default 48 is NOT count-converged — cFunc errors converge ~2nd-order in count (production-count errors ~3e-3 default / ~1-2e-2 local2-candidate vs 192-count ~4e-4/2e-3), the Step-2 objective at fixed production (β,∇) moves materially 48→96 and is stable 96→192, and the local2 two-secant Q/drift measurement is noise-dominated at 48 (silent at 192). β itself is count-stable (≤~0.3%). The local2 candidate-spec proposal bundles `HAFISCAL_AXTRA_COUNT=192`. Speed cost is trivial at solve level (sub-linear).
**Refs:** conclusions_private/2026-07-23_solve_grid_count_convergence.md; plans/20260722_local-two-secant-tail-q_plan.md §1d

### HAFISCAL_ENDOGENOUS_GRID
**Default:** `0` (off; the legacy single hand-set `aXtraMax=40` is shared by all education groups)
**Values:** truthy `1` = on; `0`/empty/`false`/`False` = off
**Status:** diagnostic
**Read by:** Code/HA-Models/grid_sizing.py (`resolve_solve_grid`, the SST policy since 2026-07-24; the branch fires only for callers passing `allow_endogenous=True` — EstimParameters. Parameters/Step-1 never enable it, preserving their historical semantics)
**Purpose:** Opt-in: size the household SOLVE grid `aXtraMax` ENDOGENOUSLY, PER education group, to the PF-asymptote (decay) extrapolation reach of that group's most-patient (GIC-cap) atom — `aXtraMax_e = ln(C1/bar)/MPCmin(gic_capped_beta(e))` via `grid_sizing.solve_grid_aMax` (College≈256, HS≈240, Dropout≈205 vs the legacy 40). MPCmin keys off the RIC (return patience), defined even when the growth/GIC-Mod conditions fail — so it is robust. Default OFF ⟹ byte-for-byte unchanged (the per-group writes are 40→40 no-ops and `grid_sizing` is never imported). Tunable via `HAFISCAL_GRID_C1`/`HAFISCAL_GRID_BAR`; an explicit `HAFISCAL_SOLVE_AMAX` overrides it. The TM DISTRIBUTION grid is sized separately by `adaptive_grid_tm.production_dist_aGrid_max()` (1300); `grid_sizing.tm_dist_aGrid_max` is that grid's analytic cross-check / GIC-Mod-failure fallback.
**Refs:** Code/HA-Models/grid_sizing.py; prompts_local/2026-06-24_grid-sizing-experiments-journal.md; plans/immutable-mixing-ripple.md

### HAFISCAL_SOLVE_AMAX
**Default:** unset (then `HAFISCAL_ENDOGENOUS_GRID` decides; else the legacy `aXtraMax=40`)
**Values:** float (top of the household solve `aXtraGrid`, applied to ALL education groups)
**Status:** diagnostic
**Read by:** Code/HA-Models/grid_sizing.py (`resolve_solve_grid`, the SST policy since 2026-07-24 — highest precedence), consumed by EstimParameters.py, FromPandemicCode/Parameters.py (Step-5) and Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py (Step-1, F7)
**Purpose:** Explicit single-value override of the household SOLVE-grid `aXtraMax` for all education groups. Highest precedence (beats both the endogenous path and the legacy 40). The solve-grid companion to the TM-grid `HAFISCAL_TM_AMAX`; for solver-grid convergence sweeps or forcing a specific solve range.
**Refs:** Code/HA-Models/grid_sizing.py; prompts_local/2026-06-24_grid-sizing-experiments-journal.md

### HAFISCAL_GRID_C1
**Default:** `grid_sizing.SOLVE_C1` (`0.04`)
**Values:** float `> bar` (the decay-curve prefactor in `err(m) ≈ C1·exp(−MPCmin·m)`)
**Status:** diagnostic
**Read by:** Code/HA-Models/grid_sizing.py (`resolve_solve_grid` endogenous branch, the SST policy since 2026-07-24; read only when the branch fires)
**Purpose:** Diagnostic knob for the endogenous SOLVE grid — the measured decay prefactor in `aXtraMax = ln(C1/bar)/MPCmin`. Re-derive via `scratchpad/exp3_decay_realG.py` (measured ≈0.034, rounded up to 0.04 so the grid is never undersized).
**Refs:** Code/HA-Models/grid_sizing.py (`SOLVE_C1`); prompts_local/2026-06-24_grid-sizing-experiments-journal.md (E3)

### HAFISCAL_GRID_BAR
**Default:** `grid_sizing.SOLVE_BAR` (`0.01`)
**Values:** float in `(0, C1)` (target max relative decay-extrapolation error over `[aXtraMax, dist_aGrid_max]`)
**Status:** diagnostic
**Read by:** Code/HA-Models/grid_sizing.py (`resolve_solve_grid` endogenous branch, the SST policy since 2026-07-24; read only when the branch fires)
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
**Default:** **PRODUCTION default = `ESC`** (owner ruling Q5, wired 2026-06-14): `EstimParameters.py` sets `os.environ.setdefault(HAFISCAL_INTERPRETATION, 'ESC')` UNCONDITIONALLY in the canonical block (applies even under `HAFISCAL_QE_FIDELITY=1`, since the published-QE world is ESC), so every entry point runs ESC unless the env says otherwise. CDC is now an explicit opt-in (`reproduce.sh` `production_*`/`tm_*`/`mc_*` profiles export CDC and, being explicit, win). The **library** code-literal default in `_interpretation.py` stays `'CDC'` (conservative for direct importers + its unit tests). Precedence: explicit kwarg > env var > EstimParameters setdefault(`ESC`) > library code-literal(`CDC`). Guarded entry points still call `get_interpretation(require=True)` and **refuse to default**. Since BUG-054 Option A (2026-07-27), `Estimation_BetaNablaSplurge.py` mirrors the same `setdefault('ESC')` at the Step-1 entry point; Step-1 output routes per interpretation (`suffix_path` → `Result_AllTarget_ESC.txt` / `_CDC.txt`) and the bare `Result_AllTarget.txt` is a symlink to the `_ESC` file. NOTE for the era-pinned CDC profiles (`production_*`/`tm_*`/`mc_*` in reproduce.sh): they consume `_CDC`, whose bytes since the owner's D3 ruling (2026-07-27) are the noise-free TM re-derivation (ς 0.25982), no longer the April-era 0.25710 — exact era reproduction of those profiles' historical baselines needs the git-history bytes.
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
**Default:** `1` — **ON (power-law) since 2026-07-23** (owner ruling: the 2026-07-05 default-OFF was a temporary exploration; unset now ⟹ the power-law decay tail + the K·h̄ solve top via the measured-Q default below. The legacy naive-linear world is the explicit opt-out `0`.) **World taxonomy (owner FINAL ruling 2026-07-23, after a same-day deliberation that briefly routed as-corrected through `exp`):** the published naive-linear WAS the bug, so **the power-law restoration is itself the fix — `1` in BOTH worlds** (machine SoT: `config/catalog.py` `pf_decay_extrap`); the as-corrected world differs only on the IMPROVEMENT axis (`Q=slope` ⟹ top-40, count-48). `exp` = diagnostic opt-out only (the PR-3-era form, kept for T-cascade/RECONCILED-002 reproduction); `0` = as-shipped, reserved for QE reproduction.
**Values:** `0` / `''` / `false` / `False` = OFF (legacy bare `LinearInterp(m_temp, c_temp)`, naive-linear extrapolation above the top grid point — the BUG-061/062 error path, kept for legacy/QE reproduction); unset or any truthy value (e.g. `1`, `powerlaw`) = ON with the **power-law** decay tail (`powerlaw_decay.PowerLawDecayLinearInterp`, the HAFiscal-local mirror of the HARK-PR `LinearInterp(decay_extrap_form='powerlaw')`; theory-correct per the 2026-06-24 derivation §8 — **the ON-form default since 2026-07-05**, owner acceptance of the T0–T3+T1b cascade verdict, RECONCILED-002); the literal `exp` = ON with the legacy **exponential** decay (the original PR-3 form; opt-out kept for before/after reproduction). CACHE NOTE: solution-cache entries key on the RAW flag value, so pre-2026-07-05 `1`-keyed entries were EXPONENTIAL-solved and were purged at the flip (a post-flip `1` run must not HIT them)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py — two read sites: `solve_agg_cons_markov_alt` (the 2D-slice decay attach + Carroll-Kimball HALT) and `AggFiscalType.update_solution_terminal` (the constrained-PF backward-induction start, owner insight 2026-06-24); both call the shared module-level helper `compute_pf_decay_limits` so terminal and slice-attach use identical limits. Also (F1 everywhere-audit, 2026-07-23/24): `_step2_namg_enabled` (the NAMG tail guard), Code/HA-Models/step1_powerlaw_tail.py (`powerlaw_form_active` — the shared gating predicate; NOTE its Step-1 rewrap is NOT wired: the F1.4 neutrality gate measured |dObj/Obj|=2.04e-2, not neutral, port reverted — Step-1 keeps HARK-native exp by dated convention), Code/HA-Models/Target_AggMPCX_LiquWealth/fti_step1.py (`POWERLAW_ACTIVE` — the FTI tail router), and Code/HA-Models/jax_mc_speedup/jax2b_powerlaw_tail.py (the JAX-2B attach gate).
**Purpose:** BUG-062 / PR-3 — opt-in per-Markov-state PF (perfect-foresight) decay extrapolation for the 2D AggShock consumption function. When ON, each per-state cFunc slice gets `slope_limit=MPCmin` and `intercept_limit=MPCmin*h_AD[n][i]`, so it decays to the affine PF asymptote `c_bar_i(m)=MPCmin*(m+h)` instead of following the last segment's slope forever. MPCmin is from `mom_bounds.compute_mpc_min` with mortality-as-impatience `DiscFac*LivPrb` (C-independent); h is the Markov-JOINT human wealth from `mom_bounds.solve_markov_human_wealth`. **AD-AWARE h (owner directive 2026-06-24):** the human wealth is AD-augmented and **C-dependent** — for each aggregate-consumption slice `n` (Cgrid[n]) the per-state income is scaled by `ADFunc(Cgrid[n], RecState_j)` (`= Cgrid[n]**ADelasticity` in recession states, `1` otherwise) BEFORE the human-wealth fixed point, so the PF tail of a recession regime reflects the AD income drop instead of using base income. `RecState_j = floor(j/num_base_MrkvStates)%2==1`. The aggregate C driving ADFunc is HELD at the slice value Cgrid[n] for the integration (documented approximation; the recession's mean-reversion is carried by the macro transitions already in MrkvArray). In the **baseline / `ADelasticity==0`, ADFunc≡1**, so `h_AD` is C-flat and equals the base joint-h for every slice — the AD code reduces EXACTLY (bit-identical) to the base-h version (verified). **Constrained-PF start (owner refinement 2026-06-24):** the backward induction is STARTED from the (now C-dependent) constrained PF terminal `c0_i(m,C)=min(m, MPCmin*(m+h_AD[n(C)][i]))` instead of HARK's consume-everything `c(m)=m` (built with `LowerEnvelope2D(IdentityFunction, LinearInterpOnInterp1D(per-C PFlines, Cgrid))`). By Carroll-Kimball precaution + Bellman monotonicity, every backward iterate then stays at/below the PF line, so the slice loop's HALT becomes the literal slope-independent invariant "above the line ⇒ impossible" (the old c=m start needed a transient-skip because consume-everything sits above the line at high m). The infinite-horizon fixed point is unique, so the start changes only the TRANSIENT path, not the converged cFunc (verified: PF-start vs c=m-start agree to 2.7e-10 at a 1e-12 solve tolerance). Guards: an FHWC/RIC fallback (RIC fails ⇒ MPCmin≤0, or FHWC fails ⇒ any non-finite h_AD ⇒ warn once + revert to legacy no-limit / consume-everything terminal) plus the Carroll-Kimball (1996) concavity HALT (`ValueError` if any solved top knot lies above the AD-aware PF line — theoretically impossible in a correct solve; owner ruling 2026-06-24: HALT, do not silently fall back). Default OFF ⇒ byte-for-byte unchanged. Couples to `HAFISCAL_ENDOGENOUS_GRID` (most valuable with the extended grid).
**Note (2026-07-05):** now in the `solution_cache/keys.py` `_HAFISCAL_NUMERICAL_ENV_VARS` whitelist (closes the known gap; one-time dev-cache key rewrite). The **HARK PR** (`fix-aggshock-pf-decay-extrap` worktree, commits `208f78f1`/`fed6f368`+) carries the canonical upstream machinery and uses the **power-law** decay form (`LinearInterp(decay_extrap_form='powerlaw')`, per `conclusions_private/2026-06-24_buffer-stock-decay-power-law-derivation.md` §8); this HAFiscal-local path still attaches HARK's legacy **exponential** decay — switching it to power-law is a pending owner decision (validation: `Code/HA-Models/decay_form/harness_powerlaw_extrap.py`).
**Refs:** plans/20260624_hark-2d-markov-extrapolation-fix.md (PR-3; authors BUG-062 on landing); BUGS_private/HAFiscal_BUG-061_solve_grid_aXtraMax_hardcoded_and_2D_aggshock_naive_extrap.md (layer-ii root cause); Code/HA-Models/mom_bounds.py (`solve_markov_human_wealth`, `compute_mpc_min`); Code/HA-Models/test_pf_asymptote_decay.py (regression test)

### HAFISCAL_PF_DECAY_Q
**Default:** `measured` — **the measured two-secant Q is the default since 2026-07-23** (with the default-ON flip; `local2` is an accepted legacy ALIAS of `measured` — the owner retired that name because it recalls the abandoned augment-two-points design)
**Values:** `slope` (the tail exponent from the top-knot level+slope pair, `Q = B·(x_top+h)`; selecting it also keeps the LEGACY 40/48 solve grid) | `measured` / alias `local2` (owner design 2026-07-22: per-slice Q from TWO log-log secants over three EXISTING top knots — attach `Q := Q2` the upper/most-local secant; `Q2−Q1` = the drift diagnostic; falls back to `slope` per-slice with a one-shot warning when leverage/guards fail)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py (`solve_agg_cons_markov_alt`, the local2 gate next to the `_pf_slice_ctor` selection); Code/HA-Models/FromPandemicCode/EstimParameters.py (the local2 K·h̄ solve-top rule trigger); Code/HA-Models/FromPandemicCode/Parameters.py (the Step-5 mirror of that rule, 2026-07-22 — so the candidate config reaches the multiplier pipeline's solve grids); estimator: Code/HA-Models/local_q_tail.py; also (F1, 2026-07-23) Code/HA-Models/step1_powerlaw_tail.py (`measured_q_active` — shared Q-source predicate; its Step-1 rewrap is unwired per the F1.4 neutrality-gate revert) and Code/HA-Models/jax_mc_speedup/jax2b_powerlaw_tail.py (the JAX-2B attach's Q-source gate)
**Purpose:** Locally-estimated power-law tail exponent per the 2026-07-21/22 measurements (the in-range effective exponent matches NO closed-form theory anchor: strip atom ≈0.56–0.63 vs q_det=13.9/q*=1.37/min(1,q*)=1). Only meaningful with the powerlaw decay form (`HAFISCAL_PF_DECAY_EXTRAP=powerlaw`; ignored with a warning under `exp`). Requires the K·h̄ solve-top rule for identifiability — at the legacy `aXtraMax=40 ≪ h≈197` the secants have no `(x+h)` log-leverage — AND adequate solve-grid COUNT: at the base count 48 the measured Q is biased ~−0.10 by top-knot spacing (count-converged at base ≈192: cap-atom Q ≈0.58 at the K=3 top, rising ~+0.05/e-fold with grid top toward the theory pin; 2026-07-23 count correction). Drift advisory tolerance: `HAFISCAL_PF_DECAY_DRIFT_TOL`. Verify + warn, NEVER iterate (owner rejected a grow-until-tolerance re-solve loop).
**Refs:** plans/20260722_local-two-secant-tail-q_plan.md; Code/HA-Models/local_q_tail.py; decay_form prototype (two-secant vs deep truth)

### HAFISCAL_PF_DECAY_DRIFT_TOL
**Default:** `0.05`
**Values:** float — advisory tolerance on the windowed two-secant drift per e-fold of `ln(x+h)`; calibrated so that passing implies ~1e-4-class far-field consumption extrapolation error (deep-truth prototype, 2026-07-22). **Semantics change (F5, 2026-07-23):** the drift is now measured on INTERIOR windows that EXCLUDE the final solved knot (same two-secant estimator, window shifted down one knot) — the dual-process sliding-window profiles localized ~+0.07 of endpoint noise/bias to last-knot windows where interior regressions are clean, so the advisory no longer alarms on endpoint noise. The ATTACH exponent is unaffected (still the endpoint-inclusive most-local upper secant Q2). With <4 usable knots the diagnostic falls back to the legacy top-window `(Q2−Q1)`/e-fold (`drift_window='legacy-top'`)
**Status:** diagnostic
**Read by:** Code/HA-Models/local_q_tail.py (`maybe_warn_drift`, called once per `solve_agg_cons_markov_alt` return under the measured-Q path; since 2026-07-23 it keys on per-invocation ROUNDS and fires only on a STABILIZED converged plateau — ≥3 consecutive rounds within ±10% — never on a transient early iterate, the wart fix)
**Purpose:** The "verify + warn" half of the measured-Q design: if the local exponent is still drifting faster than this at the grid top, a one-shot warning advises raising the solve-grid resolution. FIRST lever: `HAFISCAL_AXTRA_COUNT` (top-knot SPACING is the dominant drift contaminant at the base count 48 — the diagnostic is ~4× inflated there and silent at 192; 2026-07-23 count correction); then `HAFISCAL_PF_DECAY_AMAX_MULT`/`HAFISCAL_SOLVE_AMAX`. At adequate count the diagnostic measures the TRUE (small, upward ~0.05/e-fold) location-drift. **Interpretation heuristic (2026-07-23):** drift `d` ⟹ the constant-Q tail's log-gap error over the used extrapolation span `s = ln((m_use+h̄)/(m_top+h̄))` is ≈ `½·d·s²`; relative c-error ≈ that × (gap/c at m_use). For the production geometry (top 591 → TM top 1300, s≈0.64) the calibrated conversion is c-error ≈ `2e-3·d`, and aggregate results damp that by another ~1e-3 (the ergodic mass beyond the solve top) — so even d≈1 is invisible at the 1e-3 multiplier gate. The 0.05 tolerance is a MEASUREMENT-QUALITY dial (is the quoted Q stable where you quote it?), not a results alarm. Never HALTs, never triggers re-solves.
**Refs:** plans/20260722_local-two-secant-tail-q_plan.md

### HAFISCAL_PF_DECAY_AMAX_MULT
**Default:** `3`
**Values:** float K in the per-group solve-top rule `aXtraMax_g = K·h̄_g`, `h̄_g = Γ_g/(R−Γ_g)` (employed-state PF human wealth, from primitives — no solve needed). K=3 ⟹ dropout/HS/College ≈ 467/551/590 (vs legacy 40). Owner ruling 2026-07-22: default 3. (Count correction 2026-07-23: the real-4-state-agent advisory firing at K=3 was solve-grid COUNT noise, silent at `HAFISCAL_AXTRA_COUNT=192` — count, not K, is the silencing lever; K=3 stands. `conclusions_private/2026-07-23_solve_grid_count_convergence.md`)
**Status:** diagnostic
**Read by:** Code/HA-Models/grid_sizing.py (`resolve_solve_grid`'s K·h̄ branch — the SST policy since 2026-07-24; fires only when `powerlaw_measured_active` and nothing of higher precedence claims the grid), consumed by EstimParameters.py, FromPandemicCode/Parameters.py (Step-5; endogenous never enabled there) and Estimation_BetaNablaSplurge.py (Step-1, F7: h̄≈201.5 ⟹ top 604.48/count 238 from the 20/20 anchors)
**Purpose:** The rule-of-thumb half of the local2 design (owner revision 2026-07-22, replacing the rejected grow-until-tolerance loop): one solve, no iteration; `grid_sizing.solve_grid_count` holds near-zero grid density so the moment-relevant region keeps its resolution (the E4/E5 β-shift lesson).
**Refs:** plans/20260722_local-two-secant-tail-q_plan.md; Code/HA-Models/grid_sizing.py

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

### HAFISCAL_SKIP_ERGODICITY_GUARD
**Default:** `0` (guard active)
**Values:** `1` = bypass the guard (diagnostics only); anything else = active
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (`assert_mortality_inclusive_ergodicity`, called at the top of `compute_baseline_tm_data`)
**Purpose:** Escape hatch for the mortality-inclusive ergodicity HALT guard (owner order 2026-07-25). The guard verifies, at TM-ergodic build time, that every atom satisfies the GIC-with-Liv existence condition (population GPF_out < 1 — the same object the BUG-053 cap shaves to `theGICfactor`): GPF_out ≥ 1 means no finite-mean ergodic wealth distribution exists even with mortality, so building a TM "ergodic" would be meaningless — power iteration would just pile mass at the distribution-grid top (`dist_aGrid_max`, the HAFISCAL_TM_AMAX-set bound) and return a truncation artifact — and execution HALTS with a RuntimeError. Exact path compares β against `EstimParameters.gic_capped_beta(educ, 1.0)` (loader convention); fallback path computes GPF_out from the agent's own attributes (≈2e-4 convention offset, halting at ≥1.0 with a WARN band at [0.9996, 1.0)). Set `1` only to diagnose a deliberately mis-calibrated model.
**Refs:** BUGS_private BUG-053; conclusions_private/2026-06-16_gic-inside-vs-outside-individual-target-vs-tm-ergodic.md; Code/HA-Models/test_tm_ergodicity_guard.py; conclusions_private/2026-07-24_speed_deepdive_p0p1.md

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

### HAFISCAL_UI_INCOME_WIRING
**Default:** `on` (Simulate.py; raises `ValueError` on any value other than `on`/`off`)
**Values:** `on` = under `bug_fix` (6-state) encoding, the U3/U4 extension micro-states are assigned WITH-benefits income (`IncShkDstn_unemp`) at RECESSION macro states when building `IncShkDstn_recessionUI` — so `recessionUI` differs from `recession` by the extension income and the UI multiplier is finite. `off` = restore the pre-fix plain copy `IncShkDstn_recessionUI = IncShkDstn_recession`, which under `bug_fix` makes recessionUI IDENTICAL to recession ⇒ UI multiplier 0/0 = `nan`.
**Status:** live (BUG-050 fix, 2026-07-26)
**Read by:** Code/HA-Models/FromPandemicCode/Simulate.py (the `IncShkDstn_recessionUI` construction)
**Purpose:** BUG-050 fix toggle. Under LEGACY (4-state) encoding the plain copy was correct — the extension is delivered through a different `MrkvArray_recessionUI` freeze-window — so the legacy branch is untouched and byte-identical (`_n_extension == 0`). Under `bug_fix` the extension must be delivered as INCOME, and the missing wiring produced a silent 0/0. Default ON because the value it replaces is `nan`, so nothing usable can regress ([[feedback_error_vs_sample_changes]]).
**Validated:** Reduced K=1/c96 a-indexed — UI_AD `nan` → **1.43699**; Check_AD/TaxCut_AD/Check_1st/TaxCut_1st **bit-identical** (0.000e+00); the `Output_Results.py` BUG-050 guard fires 0× with the fix and 1× under `=off`. Construction MIRRORS the already-validated welfare path (`welfare6_scenario.py:431-447`) so multiplier and welfare agree by construction.
**Refs:** BUGS_private/HAFiscal_BUG-050_recessionUI_income_not_wired.md; BUGS_private/HAFiscal_BUG-043_ui_extension_under_delivers_for_during_recession_unemployment.md; BUGS_private/HAFiscal_BUG-048_recessionTaxCut_6state_crash.md

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

### HAFISCAL_STEP5A_PARALLEL_SOLVE
**Default:** unset (byte-identical stock `eco.solve()` at every Step-5a solve site)
**Values:** unset/`0`/`off` = off; `auto` = budgeted worker count; positive integer = workers per economy solve (taken as-is, mirroring `HAFISCAL_DUR_WORKERS`)
**Status:** diagnostic
**Read by:** Code/HA-Models/step5a_parallel_solve.py (the wrapper + budgeting; module docstring is the detailed spec), consumed at Code/HA-Models/FromPandemicCode/Simulate.py's five explicit solve sites; Code/HA-Models/step5a_parallel_gate.py (gate harness)
**Purpose:** Opt-in cohort-parallel economy solve for **Step-5a** (the multiplier pipeline), routing Simulate.py's five solve sites ('initial' in the pre-fork parent; 'norec_*', 'nonad_*', 'adtm_*', 'first_*' inside the outer shock-type fork children) through the fork-based `parallel_solve.parallel_eco_solve` engine — the same machinery validated bit-identical at 3.88× in the welfare context. **`HAFISCAL_PARALLEL_SOLVE` does NOT affect Step-5a; only this flag does** (that was the gap this scout closed, R8 item 8). **`auto` budgeting composes with the existing fans instead of multiplying them:** `min(n_cohorts, ncpu)` in the pre-fork parent, `max(1, min(n_cohorts, ncpu // 8))` inside a shock-fork child — the same divisor-8 model `_fork_dispatch_durations`/`HAFISCAL_DUR_WORKERS` already encodes, and the solve pool lives only during `eco.solve()`, which completes before that child's duration fork starts. An INTEGER value bypasses that budgeting and therefore multiplies with the outer shock fork (up to 7 children) — budget the product yourself. Requires the entry-point BLAS pins (present since the 2026-07-07 oversubscription fix). Falls back LOUDLY to stock `eco.solve()` when any of `HAFISCAL_USE_JAX_2B(_VMAP)`, `HAFISCAL_STEP2_NAMG`/`_ANDERSON`, `HAFISCAL_STEP5_ATI` is on (the fork worker runs plain HARK `solve_agent` only). Does NOT cover the AD loop's internal re-solves (`run_ad_tm` Phase-1 training) or `run_experiment_tm`'s per-agent solves. HS_Only gates (bit-identity + end-to-end output identity) passed; Reduced/Baseline wall A/B is the next rung, owner-gated.
**Refs:** plans/20260724_speed-defaults-deep-dive_plan.md §R8 item 8; Code/HA-Models/step5a_parallel_solve.py; CLAUDE.md "Cohort-parallel HARK solves"

### HAFISCAL_STEP5A_FORCE_POOL
**Default:** unset (off)
**Values:** `1` = route the wrapped solve through the fork pool even when the worker clamp lands at 1
**Status:** diagnostic
**Read by:** Code/HA-Models/step5a_parallel_solve.py; Code/HA-Models/step5a_parallel_gate.py
**Purpose:** TEST-ONLY. HS_Only's Step-5a economy has a single cohort (`DiscFacCount=1`), so the worker clamp would otherwise take the sequential fallback and the bit-identity gate would validate nothing. This forces the pool path so the gate exercises real fork/pickle round-tripping. Never set in production.
**Refs:** plans/20260724_speed-defaults-deep-dive_plan.md §R8 item 8

### HAFISCAL_STEP5A_SOLVE_PROBE_DIR
**Default:** unset (no probe dumps)
**Values:** a directory path
**Status:** diagnostic
**Read by:** Code/HA-Models/step5a_parallel_solve.py; Code/HA-Models/step5a_parallel_gate.py
**Purpose:** TEST-ONLY. When set, every wrapped solve (flag on OR off) dumps a deterministic pickle of per-agent, per-state cFunc evaluations on a fixed 320-point m-grid (dense body + log-spaced tail to m=3000, past `dist_aGrid_max`=1300) — the byte-compare artifact for the bit-identity gates, following the `parallel_solve_test.py` precedent. Never set in production.
**Refs:** plans/20260724_speed-defaults-deep-dive_plan.md §R8 item 8

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
**Purpose:** Plan-1 Leg B consume side. When on (and a matching AD-belief sidecar exists), Step-5b seeds `eco.CFunc` + each `agent.CFunc` from the sidecar then calls `solve_ad_recession` UNCHANGED (no verify/skip/assert-and-accept) — the loop converges to its own fixed point from the warm seed in fewer iterations. Soft-gated on a regime/calibration fingerprint mismatch (mismatch → ignore sidecar → flat path; never a correctness hazard). OFF (default) ⇒ `run_recession_AD` byte-identical to today. **PAYOFF MEASURED 2026-07-25 (R8 items 5+6) — and the old "speedup-inert" note is now only HALF true.** A seed-aware reset DOES exist: `solve_ad_recession` honors `eco._ad_warm_start` (AggFiscalModel.py:3311, landed e368b8af 2026-06-22), skipping the flat reset at the top of the call and re-applying the seed after `self.update()` (which unconditionally rebuilds a flat CFunc) — i.e. the seed survives BOTH clobber points when that attribute is armed. Four-cell HS_Only recession bench (`Code/HA-Models/ad_seed_anderson_fourcell_bench.py`, maxit=15 cutoff=1e-3): cold **6** AD iterations → seeded **1** (max|ΔCratio| 1.3e-5, max|ΔCFunc| 1.2e-5); AD-Anderson alone 6 → 4; the two composed = 1 (a converged same-scenario seed terminates in one iteration at both tolerances, so Anderson never engages — its value is on cold/far starts). `Code/HA-Models/test_ad_seed_reset_regression.py` (5 tests) locks the contract in both directions: attribute absent/False ⇒ the flat reset runs unchanged and a pre-set `eco.CFunc` is DISCARDED (byte-identical to a clean cold call). **END-TO-END VERIFIED 2026-08-03 on BOTH engines** (overnight R6b arc): (a) the hybrid replay engine now honors the armed seed — it previously clobbered it at two points (`switch_shock_type`'s calc_CFunc + the identity reset), which is why the flag was inert under the production default; certified 5→1 iterations, cell deltas bench-class (AggCons 5.3e-7), anchor7 all-seeded battery 12/12 with the flat-started internal control byte-identical; (b) the Step-5a TM path consumes via `Simulate.py`'s SEED (TM) arm + `run_ad_tm`, which must seed BOTH halves of its iteration state — the belief AND the Cratio path (`_cratio_path_from_seed_CFunc`; belief-only seeding measured inert) — certified 4→1 iterations, `Multiplier_candidate.tex` CHARACTER-IDENTICAL cold-vs-seeded, Step 5a 44.0→38.1 min. Converged beliefs self-publish as sidecars from both engines (welfare `run_recession_AD` post-restore + the existing Step-5a sites; one sidecar slot per (parametrization, shock_type) — cross-engine overwrite is benign, warm-start-only). Remains **default-OFF**: the end-to-end pipeline gain (~12–14%) sat below the 2026-08-02 overnight "majors" bar; the flip is an owner decision with the evidence table in `conclusions_private/2026-08-03_overnight-majors-structural-speedups.md`.
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
**Purpose:** Distribution-grid size (the aCount of `build_tm_agg_fiscal_a`) for the Step-2 TM-a discount-factor estimation. The dist grid is ~1% of the per-eval cost (the per-atom solves dominate and are aCount-independent), and the pooled group MEDIAN — a calibration target — carries a ~1.5% quantization bias at aCount=200 that converges by ~1600 (jitter 1.49% → 0.06% vs an N=6400 reference; driven by the two GIC-cap atoms' fat tails). Finer dist grid = nearly-free accuracy on the median target; Lorenz targets are grid-robust either way. Distinct from `HAFISCAL_TM_MCOUNT` (the Step-5 / welfare-6 TM aggregation grid). Cross-ref (2026-07-25): both flags are the same CLASS of knob — a `dist_aGrid_count` (a-indexed distribution-grid size; the code parameter of `compute_baseline_tm_data`/`run_experiment_tm` carries that name since the 2026-07-25 rename) — with different scopes: this flag sizes the Step-2 estimator's dist grid, `HAFISCAL_TM_MCOUNT` the Step-5/welfare-6 one. Flag values and semantics are untouched by the rename; the deferred R2 value-unification study is UNCHANGED.
**Refs:** plans/20260609_ensure_connected_TM_mixing.md

### HAFISCAL_TM_AD_TIMING
**Default:** `lagged`
**Values:** `lagged` | `contemporaneous`
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (module-level)
**Purpose:** Override TM-a's ad_timing — which RecState the aggregate-demand factor uses. `lagged` (default, matches MC's QE convention): RecState[s−1] for ADF[s]. `contemporaneous`: RecState[s] for ADF[s] — diagnostic only; this is the wrong-timing variant whose MC analogue (mill_rule using the wrong RecState at the recession→recovery transition) caused BUG-030's ~11% excess AD amplification. Prints an override notice when set.
**Refs:** BUGS_private/HAFiscal_BUG-030_mill_rule_RecState_timing.md

### HAFISCAL_PARITY_CAP
**Default:** `0` (the cap-atom parity gate is SKIPPED — opt-in per the owner ruling 2026-07-24 "as an opt-in not as the default way to do things")
**Values:** `1` = run the gate; anything else = skip
**Status:** diagnostic
**Read by:** Code/HA-Models/toolmap/test_tm_ergodic_parity_cap.py
**Purpose:** Opt-in switch for the College-inclusive GIC-cap-atom TM-vs-MC parity gate: seed MC from the TM-a ergodic via the production warm-start path (`initialize_mc_from_tm_ergodic`) at the two effective College cap atoms, free-run a production-scale window, and require the panel's tail-robust quantiles (median, p90; bands 10% = 2× the dev-measured seed spread) to stay on the ergodic. The gate's TM side DERIVES the distribution-grid top (`dist_aGrid_max`) by the default method (`adaptive_grid_tm.production_dist_aGrid_max()`; an explicit pre-import `HAFISCAL_TM_AMAX` wins) rather than hardwiring a frozen number. Covers the configuration the default HS_Only parity gate deliberately does not (near-critical atoms). Runs a full Baseline 21-type solve (~1.5–4 min), hence opt-in.
**Refs:** Code/HA-Models/toolmap/test_tm_ergodic_parity.py (the default-scope gate); conclusions_private/2026-07-24_speed_deepdive_p0p1.md; plans/20260724_step1-tm-a-simulation_plan.md (gate S1)

### HAFISCAL_PARITY_CAP_WINDOW
**Default:** `40` (quarters)
**Values:** non-negative integer (free-run window length after the warm-start)
**Status:** diagnostic
**Read by:** Code/HA-Models/toolmap/test_tm_ergodic_parity_cap.py
**Purpose:** Length of the post-warm-start MC free-run window in the opt-in cap-atom parity gate. 40 ≈ the production experiment scale; the gate's documented bands were measured at this window, on the gate's DERIVED distribution-grid top (`dist_aGrid_max`=2900 under the current default numerics). The gate's `__main__` dev mode also probes W∈{0,12,80} (W=80 showed a possible slow tail-relaxation onset — assigned to the Step-1 TM-a plan's drift gates, not this regression gate).
**Refs:** Code/HA-Models/toolmap/test_tm_ergodic_parity_cap.py (docstring, TOLERANCE RATIONALE)

### HAFISCAL_DIST_TOP_MODE
**Default:** `global` — today's resolution, byte-for-byte: the `HAFISCAL_TM_AMAX` env override, else the legacy in-code `500.0`
**Values:** `global` | `per_atom` (anything else raises ValueError at the read site)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (`build_tm_agg_fiscal_a`, consulted only when the `dist_aGrid_max` argument is None — explicit callers bypass the mode entirely), Code/HA-Models/solution_cache/keys.py (component of the solution-cache numerical key)
**Purpose:** Selects HOW the TM distribution-grid top (`dist_aGrid_max`) is resolved when no explicit value is passed (dist-grid-top scoping plan, component B). `global` (default): one top for every agent — the incumbent `HAFISCAL_TM_AMAX`-else-500 path, sized offline to the GIC-cap atom by `production_dist_aGrid_max()`. `per_atom`: each agent's own top via `adaptive_grid_tm.per_atom_dist_aGrid_max(agent)` — the (1−1e-4) **WEALTH-weighted** ergodic-aNrm quantile of the atom itself on the module's covering grid, rounded up to 100 like the incumbent and memoized per (β, key params) so the 21 production types compute once per process. Evidence for per-atom + wealth integrand (plan P2): the truncation knee is ATOM-specific (dropout/HS ~300–500 vs College >1300 at count 200) and the estimands integrate wealth, which a fat tail carries above T as T^(1−α) — population mass is the wrong integrand; per-atom tails are clean single-α Kesten tails (α solves L·E[(Þ_Γ/ψ)^α]=1) while pooled exponents drift with the window (mixture artifact). Semantics: NO silent floor at the global top (per-atom means per-atom — thin atoms genuinely get short grids); `HAFISCAL_TM_AMAX` is NOT consulted under `per_atom` (EstimParameters setdefaults it to 1300, so an env fallback would silently swallow the mode); the derived top is logged per agent at DEBUG level; derivation is at Cratio=1.0 (a STATIONARY sizing rule — experiment TMs reuse the baseline `dist_aGrid`). This is the per-atom-top plumbing of the plan's P3 R-c×R-d recommendation; the analytic tail-bucket (R-d) is a separate component. In the solution-cache key per the ATI engine-selection precedent (a resolution-PATH selector whose effect is not visible in the hashed static params).
**Refs:** plans/20260726_dist-grid-top-scoping_plan.md (P0–P3; ε ruling 4%/2%/1%), Code/HA-Models/adaptive_grid_tm.py (`per_atom_dist_aGrid_max` docstring), conclusions_private/2026-06-16_gic-inside-vs-outside-individual-target-vs-tm-ergodic.md (per-atom exponent equation, mortality as tail stabilizer)

### HAFISCAL_TM_AMAX
**Default:** `1300` (canonical, via `os.environ.setdefault` in the EstimParameters.py canonical block — skipped under `HAFISCAL_QE_FIDELITY=1`; the in-code fallback when the env var is unset AND no `dist_aGrid_max` argument is passed is the legacy `500`). **STALENESS FLAG (2026-07-25, owner decision pending):** the frozen 1300 was derived 2026-06-09 under the as-shipped NAIVE-LINEAR tail (the derivation reproduces it exactly there: q=1224→1300); under the current default numerics (power-law measured-Q + K·h̄ grids) `production_dist_aGrid_max()` now returns **2900** (exp: 2300), and at 1300 the grid truncates 5.6e-4 of cap-atom mass carrying **2.9% of cap-atom wealth**. Re-freezing the canonical (jointly with `HAFISCAL_TM_ACOUNT` — wider range at fixed count coarsens spacing) is a production-numerics OWNER decision (candidate-routed cascade). The opt-in cap parity gate already derives instead of hardwiring (owner ruling 2026-07-25).
**Values:** float — the **distribution-grid top (`dist_aGrid_max`)** of the TM-a asset grid, aNrm units. (Owner ruling 2026-07-25: the object is `dist_aGrid_max`, extending HARK-upstream naming; the bare `aMax` spelling collided with the solve grid's `aXtraMax`. The FLAG keeps its `HAFISCAL_TM_AMAX` spelling — owner-ratified, it already carries the TM_ prefix.)
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/EstimParameters.py (canonical setdefault site), Code/HA-Models/FromPandemicCode/tm_methods.py (`build_tm_agg_fiscal_a`, consulted only when the `dist_aGrid_max` argument is None AND `HAFISCAL_DIST_TOP_MODE` is `global` (the default) — explicit callers bypass the env, and `per_atom` mode derives the top instead (see that entry); `aMax=` remains one deprecation cycle as a warning kwarg alias), Code/HA-Models/tm_mixing_diagnostic.py, Code/HA-Models/validate_mixing_ergodic.py
**Purpose:** Sets the distribution-grid top (`dist_aGrid_max`) of the TM-a asset grid. From the EstimParameters canonical block, verbatim: "dist_aGrid_max=1300 (the TM distribution-grid top; HAFISCAL_TM_AMAX) is NOT a magic number: the TM grid must cover the MOST-PATIENT College discount-factor atom (the GIC-cap atom, GPF=theGICfactor=0.9995 under BUG-053) — its ergodic aNrm tail is the binding constraint; 1300 = production_dist_aGrid_max()." `production_dist_aGrid_max()` (Code/HA-Models/adaptive_grid_tm.py; renamed 2026-07-25 from `production_aMax`, which survives one cycle as a deprecated warning alias) sizes the grid to the GIC-cap atom — β-INDEPENDENT, so no chicken-and-egg with the (β,∇) estimation — by interpolating the cap atom's ergodic CDF on a large covering grid; it replaced the broken `iterate()` trim/grow loop (a non-convergent 2-cycle). A 500 top truncates the cap atom's tail (biasing the College high-wealth agents); re-derive via `production_dist_aGrid_max()` if the calibration / theGICfactor changes. `HAFISCAL_QE_FIDELITY=1` skips the setdefault, reverting to the legacy 500 for reproducing the published-QE world (500 was itself the fix for an earlier top-of-50 tail-truncation bias, ~30% K/Y at high β).
**Refs:** Code/HA-Models/FromPandemicCode/EstimParameters.py (canonical block), Code/HA-Models/adaptive_grid_tm.py (`production_dist_aGrid_max`), plans/20260610_post_merge_canonicalize_default_solution.md, conclusions_private/2026-06-10_welfare_method_unified_MC.md

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
**Purpose:** Override the TM AGGREGATION grid size — it sizes the a-indexed DISTRIBUTION grid on the production path (code parameter now **`dist_aGrid_count`** in `compute_baseline_tm_data` / `run_experiment_tm`, renamed 2026-07-25 from the lying `mCount`; on the legacy m-indexed dispatch it sizes that kernel's honest `mCount`), NOT the solver grid. The M-era `MCOUNT` flag name is historical — **the flag spelling is retained by owner ruling (2026-07-25)**; do not rename env flags. Introduced for the D-6 test of whether refining the TM aggregation grid shrinks the MC-vs-TM-a multiplier residual; now the general grid knob for the Step-5a multiplier run (Run_Dict['tm_mCount'], default 100; `--fast-reproduce` → 40) and the welfare-6 TM baseline/ergodic-init builds. Both AggFiscalMAIN_reduced.py and tm_methods.py print an override notice when the env var is set. Cross-ref: `HAFISCAL_TM_ACOUNT` is the same class of knob (a dist_aGrid_count-class grid size) scoped to the Step-2 estimator's dist grid; this flag covers Step-5 / welfare-6. Flag values and semantics untouched by the rename; the deferred R2 value-unification study is UNCHANGED.
**UPDATED 2026-06-13 (supersedes the earlier "unify to 50" ruling — that was wrong-direction).** Despite the `MCOUNT` name (a fossil from the retired m-indexed TM), this flag is the **live a-indexed (TM-a) aggregation grid `aCount`**: `compute_baseline_tm_data` passes it straight into `build_tm_agg_fiscal_a(agent, aCount=dist_aGrid_count, …)` whenever `tm_a_indexed=True` (canonical; the parameter was spelled `mCount` before the 2026-07-25 rename). `aCount` provenance audit: headline Step-5a multipliers use **100** (var unset in do_all/run_step5a_only → `AggFiscalMAIN_reduced.py` fallback); welfare-6 TM uses **200**; `tm_methods` standalone default **50**; the builder's own default is **200** ("aCount=200 (was 100) keeps upper grid cells from becoming too sparse with the wider aMax"); only `welfare6_reconcile_sweep.py` sets it (200). So the 50/100/200 spread is partly **accuracy-driven, not pure drift** — and **unifying DOWN to 50 would coarsen the production grid and INCREASE tail-truncation bias** (worse with the canonical `aMax=1300`). Decision split into: (R1) a name-only rename `HAFISCAL_TM_MCOUNT`→`HAFISCAL_TM_ACOUNT` (inert, defaults preserved) — **SUPERSEDED on the flag-spelling point by the 2026-07-25 owner ruling: the flag spelling is RETAINED; the honest name went into the code parameter (`dist_aGrid_count`) instead** — and (R2) a separate, owner-gated default-unification that, if done, goes UP to a converged value via candidate→`promote-tables` — never to 50 (R2 UNCHANGED by the rename). See `plans/20260613-1755h_tm-mcount-to-acount-rename.md`.
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
**Purpose:** BUG-052 fix, DEFAULT ON since 2026-06-08: initialize the welfare-6 MC at the TM-a ergodic wealth distribution — the same warm-start the multiplier pipeline uses — instead of the cold a≈0 init. The β-calibration targets ergodic wealth (estimation burns in T_sim=T_age·2, settles to E[aNrm]≈0.31), so cold-start welfare was calibration-inconsistent (check_rec 1.0140 cold → 1.0196 ergodic, +0.55%). Sets `tm_a_indexed=True` on all agents, builds baseline TM data (`compute_baseline_tm_data`, dist_aGrid_count from HAFISCAL_TM_MCOUNT, measure from HAFISCAL_WELFARE6_TM_INIT_MEASURE), then `initialize_mc_from_tm_ergodic` with HAFISCAL_WELFARE6_MC_WARMUP periods; injected AFTER `make_history` / BEFORE `save_state` so `run_experiment`'s use_prestate restores the ergodic prestate. `0` = cold-start for isolation/paper-trail only — explicitly NOT a QE-reproduction goal (not part of HAFISCAL_QE_FIDELITY). Guard test: Code/HA-Models/test_welfare6_ergodic_init.py.
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
**Purpose:** Parent→child marker for the parallel welfare-6 pipeline. `run_welfare6_parallel.py` sets `HAFISCAL_PROV_CHILD=1` in each spawned `welfare6_scenario.py` child's environment so the child SKIPS writing its own per-scenario provenance sidecar; the parallel driver instead emits ONE aggregate sidecar next to the welfare-6 table (12 child sidecars in the scratch pickle dir — and 12× pip-freeze — would be redundant). A standalone `welfare6_scenario.py` run (flag unset) still writes its sidecar. Since schema v2 (2026-08-04) a suppressed child instead dumps its REUSE LEDGER as a dotfile fragment (`.reuse_<pid>.json`) in its out-dir, which the driver ingests into the aggregate sidecar's `reuse` block (events tagged `source_child`). (Note: the full `MC_PLVL_INIT` / `MC_WARMUP` entries are in the MC/Welfare section above.)
**Refs:** Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py (child-env block + fragment ingest); Code/HA-Models/FromPandemicCode/welfare6_scenario.py (sidecar gate + fragment dump); Code/HA-Models/provenance.py (`dump_reuse_fragment`/`ingest_reuse_fragments`)

### HAFISCAL_SLICE_INTERP
**Default:** `linear` (byte-identical to the historical path — certified by the 12-pkl battery gate 2026-08-03)
**Values:** `linear` | `hermite` (EGM-exact-MPC cubic Hermite slices; requires the power-law form, i.e. `powerlaw_form_active()`)
**Status:** diagnostic (experimental opt-in; T2a arm of plans/20260803-2030h_gridpoint-reduction-hermite_plan.md; adoption is a T4 owner decision)
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py (`solve_agg_cons_markov_alt`, per-solve)
**Purpose:** Selects the per-C-slice 1D interpolant of the C-conditional consumption function. `hermite` adds an end-of-period vPP pass (mixing the conditional `MargValueFuncCRRA.derivativeX` — every BUG-047/AD/transition factor inherited from loop 1), computes exact knot MPCs from the envelope condition `c'(m)=dcda/(dcda+1)`, applies a Fritsch–Carlson monotonicity clamp only where violated (the constraint-kink interval), and builds `PowerLawDecayCubicHermiteInterp` slices carrying the same certified power-law tail. Motivation: the gridlab frontier measured in-solver LINEAR error ~10× above the same knots' representation capacity (EGM feedback amplification), so the in-iteration interpolant governs; Hermite targets production-class accuracy at ~1/4 the gridpoints.
**Refs:** Code/HA-Models/powerlaw_decay.py (`PowerLawDecayCubicHermiteInterp`); plans/20260803-2030h_gridpoint-reduction-hermite_plan.md §3/§3a

### HAFISCAL_SOLVE_ACCEL
**Default:** unset (plain `solve_agent` successive approximation — the historical path, byte-identical when unset)
**Values:** `aitken` | `anderson` | `newton2d` | `off`
**Status:** diagnostic (opt-in; T-gates of plans/20260804-0745h_universal-solver-acceleration_plan.md; per-step default-ON is an owner decision)
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py (`AggregateDemandEconomy.solve` → `_solve_accel_method`/`_try_solve_accel`)
**Purpose:** `newton2d` = the arm-(c) composite-block consumed Newton (build_composite_edges + solve_stationary_consumed_blocks; plan §C7-§C8). Routes the general-case consumption-function solves — including the C-conditional recession/AD family (136–175 plain iterations each) that the NAMG/ATI branches cannot take — through the generic accelerated fixed-point driver (`hark_fti.accel_driver` via the `Code/HA-Models/solver_accel.py` glue). Jumps are functional linear combinations of REAL plain-step outputs; convergence is only ever declared on the production `distance_metric` between consecutive real outputs, and the installed solution is a real plain-step output. Safety contract identical to `HAFISCAL_STEP5_ATI`: non-convergence or any error falls back to the exact plain `solve_agent`; nothing imports `hark_fti` unless the flag is ON. Same fixed point, different stopping iterate ⇒ keys the solution cache (`solution_cache/keys.py`).
**Companions:** `HAFISCAL_SOLVE_ACCEL_VERBOSE=1` prints per-solve steps/jumps/final-distance.
**Refs:** plans/20260804-0745h_universal-solver-acceleration_plan.md; fast-time-iteration `hark_fti/accel_driver.py` (Tier-C, licence-clean)

### HAFISCAL_SOLVE_ACCEL_VERBOSE
**Default:** `0`
**Values:** `0` | `1`
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py (`_try_solve_accel`)
**Purpose:** Per-solve one-line accounting (steps, accepted jumps, final production-metric distance) for the accelerated solve route. Only consulted when `HAFISCAL_SOLVE_ACCEL` is active.
**Refs:** plans/20260804-0745h_universal-solver-acceleration_plan.md


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

### HAFISCAL_JAX_MC_STRATIFIED
**Default:** unset (off — the kernel draws iid multinomial Mrkv transitions)
**Values:** `1` | `on` | `true` (case-insensitive) = on
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py (`run_recession_AD`, the `cached_solve_ad_recession` call)
**Purpose:** Fix A of the JAX-AD draw-structure plan: passes `use_shuffle=True` so the JAX-AD kernel routes through the stratified-shuffle Mrkv-transition path (`jax_mc_ad_shuffle`, gate at jax_mc_ad_multicohort.py:645-647), matching the production HARK scheme (`HAFISCAL_SHUFFLE_MRKV_TRANSITION=stratified`, canonical since BUG-044 — the same knob class once moved UI welfare +8.26%). The G1 discriminator for the Check/TaxCut AD-cell engine offsets (z=−3.7/−9.7 outside the S=4 seed band). Result-affecting, but keyed for free: `use_shuffle` is already hashed into the AD cache key, so stratified and iid runs cannot cross-hit. COSTS the 1A/2A vmap fast paths (gates at jax_mc_ad_multicohort.py:528,614) — measurement lever until G4 rules on the graduated configuration.
**Refs:** plans/20260731-0940h_jaxad-draw-structure-fix_plan.md §3-A; conclusions_private/2026-07-31_overnight-hybrid-finalization.md §1; memory jaxad-draw-structure-diagnosis

### HAFISCAL_JAX_MC_NEWBORN_POOL_N
**Default:** `10000`
**Values:** positive integer (pool size per cohort)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/jax_mc_ad_multicohort.py (module import, `_NB_POOL_N`; both `draw_newborn_pool_from_agent` call sites)
**Purpose:** Fix B discriminator of the JAX-AD draw-structure plan. The kernel draws ONE newborn pool per cohort and reuses it for every death, so the pool's sampling error is FROZEN — a persistent wealth-distribution perturbation, the lead suspect for the Check/TaxCut AD-cell engine offsets after G1 refuted the stratification mechanism (2026-07-31). If the frozen-pool error is the mechanism, the offsets must shrink ~1/√pool_N (10k→200k ⇒ ~4.5×) — a quantitative signature, not a yes/no. Result-affecting for the AD SIMULATION but sim-only (does not touch cFuncs), so it is deliberately **NOT in any cache key**: adding it to the env whitelist invalidates every key (tried and reverted 2026-07-31 — the forced global MISS exposed a latent fresh-solve 'no solution stored' bug in `cached_eco_solve`, now on the bug ledger to file). DISCIPLINE: any run varying this flag MUST quarantine `ad_*`/`ad_belief` first (all plan harnesses do) or a stale default-pool AD entry can cross-load.
**Refs:** plans/20260731-0940h_jaxad-draw-structure-fix_plan.md §3-B + §0b ruling A3; memory jaxad-draw-structure-diagnosis

### HAFISCAL_JAX_MC_SEED_COUNT
**Default:** `4`
**Values:** positive integer (number of kernel seed-streams averaged per AD iteration)
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py (`run_recession_AD`, builds the `seeds` tuple)
**Purpose:** G2b ensemble sub-hypothesis test of the JAX-AD draw-structure plan. The kernel historically averages 4 seed-streams per AD iteration; HARK-AD iterates on ONE materialized realization. If the averaging shifts the AD fixed point (a Jensen effect through the nonlinear map), `SEED_COUNT=1` should land the Check/TaxCut AD cells HARK-like (~−0.03); if they stay put, the offset is realization-structure proper and the replay-fed Fix C is the confirmed route. Keyed for free: the value expresses itself through the `seeds` tuple, which is hashed into the AD cache key. Default 4 reproduces the historical `(0,1,2,3)` exactly.
**Refs:** plans/20260731-0940h_jaxad-draw-structure-fix_plan.md §3 + execution record; memory jaxad-draw-structure-diagnosis

### HAFISCAL_CPU_RESERVE_CORES
**Default:** unset → **2** (owner revision 2026-08-02; was `clamp(cores/8,2,4)`) — clamped to cores−1 on tiny machines
**Values:** non-negative integer (clamped to cores−1)
**Status:** live
**Read by:** Code/HA-Models/machine_profile.py (`plan_welfare6_slots`)
**Purpose:** Cores left untrammeled for the system while a battery runs (owner directive 2026-08-02: the machine must stay responsive under full load). Feeds BOTH the slot count and the inner per-child worker budgets (`_auto_parallel_plan` divides usable, not total, cores). Set `0` to restore the pre-reserve full-width plan (e.g. on a dedicated compute box).
**Refs:** Code/HA-Models/test_machine_profile.py; plans/20260802-0300h_canonical-hybrid-default_plan.md

### HAFISCAL_MAX_CPU_SLOTS
**Default:** unset → resolved by the machine probe: `usable = cores − 2` (system reserve, default 2), then `clamp(min(usable//4, mem_gb//7), 1, 8)` — 32c/60GB resolves to 7 slots × 4-core budgets with 2 cores reserved (the 53-54 min certified wall was measured pre-reserve at 8 slots; the pre-probe hardwired 2 encoded the retired JAX-2B ~17GB/child era)
**Values:** positive integer (floor 1 enforced)
**Status:** live
**Read by:** Code/HA-Models/machine_profile.py (`plan_welfare6_slots`), consumed by run_welfare6_parallel (CLI `--max-cpu-slots` wins over this env var; env wins over the probe)
**Purpose:** Override the probed max concurrent CPU children for the welfare-6 battery on machines where the probe's formula misjudges (e.g. shared boxes). Introduced 2026-08-02 with the machine-resource probe so the same code tailors itself to a 16-core laptop or a 32-thread workstation without edits.
**Refs:** plans/20260802-0300h_canonical-hybrid-default_plan.md; Code/HA-Models/test_machine_profile.py

### HAFISCAL_MAX_GPU_SLOTS
**Default:** unset → probe resolves 0 REGARDLESS of GPU presence (the GPU lane is VALUELESS at battery scale by measurement — device-invariant results at 1e-15 and per-iteration wall parity ~30 s GPU ≡ CPU, verified with backend logging 2026-08-02 after the earlier 'CUDA delivery void' was re-adjudicated as a slot-arithmetic + missing-observability mislabel; 0 also spares GPU-less machines the CUDA-env hard-fail). The opt-in path itself WORKS as labeled: `[jax-replay-ad] jax backend: gpu devices=[CudaDevice(id=0)]` self-documents every run
**Values:** non-negative integer
**Status:** live
**Read by:** Code/HA-Models/machine_profile.py (`plan_welfare6_slots`), consumed by run_welfare6_parallel (CLI `--max-gpu-slots` wins; env wins over the probe)
**Purpose:** Explicit opt-in for GPU battery children (dev arms only). >1 risks GPU contention (registry lesson L3: 2 workers on the 16GB RTX 4080 measured −16% wall).
**Refs:** conclusions_private/2026-08-01_jaxad-graduation.md §4 (GPU verdicts); plans/20260802-0300h_canonical-hybrid-default_plan.md

### HAFISCAL_WELFARE_ENGINE
**Default:** unset → resolves to `hybrid` (the canonical default since 2026-08-02) unless `HAFISCAL_QE_FIDELITY=1` or `HAFISCAL_WORLD=as-corrected` (those resolve to `hark`)
**Values:** `hybrid` | `hark` (explicit value always wins, including over the world guard; invalid values raise)
**Status:** live (owner rulings 2026-08-02: successor-plan rows 2+3+3b accepted)
**Read by:** Code/HA-Models/welfare_engine.py (`resolve_welfare_engine` / `apply_welfare_engine_defaults`); applied by run_welfare6_parallel `_child_env` and the welfare6_scenario entry point
**Purpose:** One-knob selection of the welfare-6 pipeline engine. `hybrid` setdefaults the certified bundle — `HAFISCAL_USE_JAX_MC`, `_UNCAPPED`, `HAFISCAL_JAX_MC_REPLAY_AD`, `HAFISCAL_REPLAY_CRATIO_PREV`, `HAFISCAL_REPLAY_PRESOLVE_CACHE`+`HAFISCAL_AD_INIT_CACHE` (the co-gate pair), `HAFISCAL_USE_SOLUTION_CACHE` — giving the replay-fed JAX-AD engine (AD stage ~4×; measured 54-min Baseline battery) with explicit per-flag env overrides still winning. `hark` hard-clears the arc flags: the pre-arc all-HARK path, bit-identity-proven vs the pre-arc reference. The world guard keeps the hybrid engine (an owner-adopted IMPROVEMENT) out of `as-corrected`/QE-fidelity runs. Residual vs all-HARK: CRN-paired −0.5…−1.3% on AD cells, unattributed after 9 refutations, owner-accepted under sig-figs 2026-08-02. **Platform pin (2026-08-02):** the resolver also `setdefault`s `JAX_PLATFORMS=cpu` for BOTH engines — the certified numbers are CPU-kernel numbers, and a bare `welfare6_scenario` single on a GPU box otherwise auto-initializes CUDA, whose reduction topology shifts the AD fixed point at ULP scale (deterministic 1e-15-class panel deltas vs the CPU canon, growing with recession dwell). Explicit `JAX_PLATFORMS` (the GPU opt-in) still wins.
**Refs:** plans/20260802-0300h_canonical-hybrid-default_plan.md; plans/20260802-0030h_optimized-hybrid-system_plan.md §2 rulings ledger; conclusions_private/2026-08-01_jaxad-graduation.md

### HAFISCAL_JAX_MC_REPLAY_AD
**Default:** unset (off standalone); **DEFAULT-ON under the hybrid welfare engine** (canonical default 2026-08-02; see `HAFISCAL_WELFARE_ENGINE`)
**Values:** `1` | `on` | `true` (case-insensitive) = on
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py (`run_recession_AD`, JAX branch — takes precedence over the multicohort kernel)
**Purpose:** Fix C of the JAX-AD draw-structure plan: replay-fed AD. Routes the AD fixed-point iteration through `Code/HA-Models/jax_mc_replay_ad.solve_ad_recession_jax_replay` — HARK's exact update rule (same MacroCFunc rebuild, damping, convergence metric, belief-consistency rollback) with the per-iteration forward sim done by the compiled replay kernel (`simulate_jax_replay_v2`) fed HARK's CAPTURED exogenous panel (one capture per shock_type via a 1-iteration HARK AD dispatch; capture proven ADF-independent, plan §0a). No kernel PRNG: seeds/stratified/pool knobs are inert; whole-cell reseeds flow through the agent seeds the capture inherits. Removes the draw-structure offset by construction (replay-v2 premise: −0.62% at Baseline Check). CAVEATS: v1 BYPASSES the AD solution cache (quarantine-independent but do not mix with cached ad_* results — measurement harnesses quarantine anyway); enables jax x64 globally in-process; capture costs one extra HARK forward pass (~2–4 min at Baseline) plus the solve warm-start write-back it inherits.
**Refs:** plans/20260731-0940h_jaxad-draw-structure-fix_plan.md §3-C + §0a; memory jaxad-draw-structure-diagnosis

### HAFISCAL_REPLAY_CAPTURE_DUMP
**Default:** unset (off)
**Values:** filesystem path for an `np.savez` archive
**Status:** diagnostic
**Read by:** Code/HA-Models/jax_mc_replay_ad.py (`capture_exogenous_panel`)
**Purpose:** Dumps the capture's economy-level tracked histories (`AggDemandFac`/`AggDemandFacPrev`/`Cratio`/`CratioPrev`; the `*Prev` entries ARE the transacted series — mill_rule stashes `sow_state` before overwriting it, AggFiscalModel.py:2383-2384). CAVEAT: at the default `iters=1` capture the dispatch runs at the identity-CFunc reset (AggFiscalModel.py:3362), where mill sows `CratioNext = CFunc(C_real) = 1.0` identically — the Cratio dumps are vacuously 1.0; a discriminating dump needs an `iters>=2` capture. The 2026-08-02 C-argument question was settled by code reading instead (BUG-066; plan §0a 00:50 entry).
**Refs:** plans/20260731-0940h_jaxad-draw-structure-fix_plan.md §0a; BUGS_private/HAFiscal_BUG-066_cratio_sow_init_dead_key.md

### HAFISCAL_REPLAY_CRATIO_PREV
**Default:** unset (off standalone); **DEFAULT-ON under the hybrid welfare engine** (canonical default 2026-08-02; see `HAFISCAL_WELFARE_ENGINE`) (adopted row 3b)
**Values:** `1` | `on` | `true` (case-insensitive) = on
**Status:** diagnostic
**Read by:** Code/HA-Models/jax_mc_replay_ad.py (`solve_ad_recession_jax_replay`)
**Purpose:** C-argument timing fix, adjudicated by code reading 2026-08-02 (plan §0a 00:50 entry): HARK's sim evaluates cFunc(m, C) at the PREVIOUSLY-SOWN aggregate Cratio (mill_rule sows `CFunc[s_{t-1}][s_t](C_realized_t)` for t+1, AggFiscalModel.py:2378/2400), with head 1.0 because run_experiment's intended intercept-init writes the DEAD key `'CratioNow'` (BUG-066). With the flag on, the tables' C argument is exactly that sown series `[1.0, C_obs[0], ..., C_obs[T-2]]` (head corrected from `C_obs[0]` at b55a2d3f). ADF construction unchanged (its shift keeps the LIVE-key head `ADF_path[0]`, faithfully reproducing HARK's internally inconsistent t=0). Default-off pending the pre-registered cell gate (Check > 1.3675) and owner adoption.
**Refs:** BUGS_private/HAFiscal_BUG-066_cratio_sow_init_dead_key.md; conclusions_private/2026-08-01_jaxad-graduation.md §4 residual disposition

### HAFISCAL_REPLAY_PRESOLVE_CACHE
**Default:** unset (off standalone); **DEFAULT-ON under the hybrid welfare engine** (canonical default 2026-08-02; see `HAFISCAL_WELFARE_ENGINE`) (adopted row 3; the bundle carries the AD_INIT_CACHE co-gate pair)
**Values:** `1` | `on` | `true` (case-insensitive) = on
**Status:** diagnostic
**Read by:** Code/HA-Models/jax_mc_replay_ad.py (`capture_exogenous_panel`)
**Purpose:** Loads the `hark_solve_only` recession-init cache into the capture's eco_ref BEFORE the 1-iteration HARK dispatch, warm-starting its ~550 s identity-belief presolve (successor-plan row 3; projected battery 71→~52 min). Result-neutral for the captured exogenous panel BY CONSTRUCTION (shock histories and sim_birth draws are RNG-only, solve-independent) — unlike the old auto-init cache case; the AD loop re-solves under its own belief regardless. Requires `HAFISCAL_USE_SOLUTION_CACHE=1` **AND `HAFISCAL_AD_INIT_CACHE=1`** — the load routes through `load_recession_init_cache`, whose own enable-gate checks both (`solution_cache/cache.py:346-350`); with only PRESOLVE_CACHE set, the load is a SILENT no-op (found 2026-08-02: NIGHT3's N5 pair ran miss-vs-miss, so its "identical" verdict validated the disabled path only). The producer (no-AD twin save) is the same `HAFISCAL_AD_INIT_CACHE=1`. Engagement evidence is the `[recession-init-cache] HIT` log line; HIT-path fidelity rests on the init-cache 1e-5 dossier plus the capture panel's by-construction RNG-independence.
**Refs:** plans/20260802-0030h_optimized-hybrid-system_plan.md §2 row 3; the init-cache 1e-5 dossier (conclusions_private/2026-07-31_overnight-hybrid-finalization.md §2)

### HAFISCAL_TABLE_RESTRICT
**Default:** unset → ON (state-restricted per-period tables, R2 2026-08-02)
**Values:** `off` | `0` = revert to full (T, n_combined, M) tables; anything else/unset = restricted
**Status:** live
**Read by:** Code/HA-Models/jax_mc_replay_ad.py (`solve_ad_recession_jax_replay`), feeding `extract_cfunc_table_per_period(macro_path=, J=)` and the kernel's `restricted` gather
**Purpose:** R2 of the structural-speedups ladder: the deterministic experiment path occupies exactly ONE macro state per period (verified on production captures), so per-period tables need only that macro's J=6 micro rows instead of all n_combined=252 — a 42× row cut on the dominant AD-iteration stage. The one-macro-per-period invariant is GUARDED per captured panel at run time; any violation (e.g. a future StickyE lagged-perception world) falls back to full tables with a loud warning, so correctness is unconditional and the restriction is purely an optimization.
**Refs:** plans/20260802-1900h_structural-speedups-analysis_plan.md (R2)

### HAFISCAL_TABLE_EXTRACT
**Default:** unset → the FAST batched extractor (default since 2026-08-02)
**Values:** `legacy` = the historical per-(t,state) loop; anything else/unset = fast
**Status:** live
**Read by:** Code/HA-Models/FromPandemicCode/jax_mc_ad.py (`extract_cfunc_table_per_period`)
**Purpose:** Escape hatch for the table-extraction optimization. M0 measured the legacy build at 22.7 s of every 28 s replay-AD iteration (81%); the fast path applies two exact restructurings — unique-Cratio grouping and one batched interpolator call per state — bit-identical to the legacy loop by construction (elementwise interpolators, same query values and dtype; verified `np.array_equal` on a production cohort). Set `legacy` only to reproduce the pre-optimization walls.
**Refs:** plans/20260802-1400h_gpu-reevaluation-fp32-native_plan.md §5 (M0 + the bonus lead)

### HAFISCAL_REPLAY_STAGE_TIMES
**Default:** unset (off)
**Values:** `1` | `on` | `true` (case-insensitive) = on
**Status:** diagnostic
**Read by:** Code/HA-Models/jax_mc_replay_ad.py (`solve_ad_recession_jax_replay`)
**Purpose:** M0 of the GPU re-evaluation plan — prints the per-iteration wall decomposition (`solve= tables= kernel= rest=`) of the replay AD loop, establishing the Amdahl denominator that bounds any device-side speedup (the kernel share is the only part a GPU can touch).
**Refs:** plans/20260802-1400h_gpu-reevaluation-fp32-native_plan.md §1 (M0)

### HAFISCAL_REPLAY_FP32
**Default:** unset (off — panel runs float64)
**Values:** `1` | `on` | `true` (case-insensitive) = on
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/jax_mc_ad_replay_v2.py (`simulate_jax_replay_v2` dtype resolution); Code/HA-Models/jax_mc_replay_ad.py (logged in the backend line)
**Purpose:** GPU-roadmap gate G0 — the float32 tolerance arm. Runs the replay kernel's per-agent panel (states, tables, interpolation) in float32 while the per-period aggregate reductions stay float64 (mixed precision; naive fp32 sums over ~2e5 agents would lose digits the welfare cells cannot spare). The replay kernel is deterministic given the captured panel, so an fp64-vs-fp32 pair isolates precision effects alone; the acceptance ruler is the 1–2e-5 path-differential spec and the CRN-paired cell scatter (±0.0003). Purpose: certify (or refute) an fp32 tolerance budget as the prerequisite for any future device-resident GPU port (RTX-class FP64 is 1/64th of FP32 throughput).
**Refs:** conclusions_private/2026-08-01_jaxad-graduation.md §7 (device re-adjudication); plans/20260802-0030h_optimized-hybrid-system_plan.md row 4

### HAFISCAL_REPLAY_KNOT_TABLES
**Default:** unset (off)
**Values:** `1` | `on` | `true` (case-insensitive) = on
**Status:** diagnostic
**Read by:** Code/HA-Models/jax_mc_replay_ad.py (`solve_ad_recession_jax_replay`)
**Purpose:** Knot-aligned replay-AD tables (owner-directed 2026-08-01). Linear interpolation of a table sampled from a piecewise-linear function is EXACT except in cells straddling the function's own knots; HARK's cFunc is `LowerEnvelope2D` over LinearInterp-family components, so the table grid becomes: base grid ∪ recursively-extracted component m-knots (cached per cohort; knot locations are solve-grid-derived and iteration-invariant) ∪ a 300-point geomspace low-m patch bounding the per-(t,state) envelope-crossing error (crossings can't all be shared-grid nodes without an ~800 MB table). Targets the paired −0.5…−1.3% AD-cell residual of the replay-fed engine vs all-HARK (the last term after BUG-065 + Prev-ADF). Same kernel, same interpolation rule — only the node set changes; node count ≈ comparable to the 500-point base.
**Refs:** plans/20260731-0940h_jaxad-draw-structure-fix_plan.md §0a; conclusions_private/2026-08-01_jaxad-graduation.md

### HAFISCAL_REPLAY_MGRID_DENSIFY
**Default:** `1` (off — the kernel's native m_grid)
**Values:** positive integer k; k>1 inserts k−1 midpoints per m_grid interval (endpoints/geometry preserved) for the replay-AD cFunc tables
**Status:** diagnostic
**Read by:** Code/HA-Models/jax_mc_replay_ad.py (`solve_ad_recession_jax_replay`)
**Purpose:** Map-evaluation fidelity discriminator for the replay-fed AD loop (Fix C diagnosis 2026-08-01): the kernel evaluates policies through per-period cFunc tables interpolated on m_grid while HARK evaluates cFuncs exactly; path-DIFFERENTIAL errors of ~5e-5 from this interpolation move the AD welfare cells by percents (ratio-of-small-differences amplification — measured: iid +5.9e-5 / replay −7.0e-5 differential deviations map onto +0.035/−0.033 cell offsets with matching signs). If a denser table moves the replay Check cell >50% back toward all-HARK (pre-registered), interpolation dominates the remaining fidelity gap and density (or exact evaluation) becomes the graduation lever. Table build cost scales ~linearly in k per AD iteration.
**Refs:** plans/20260731-0940h_jaxad-draw-structure-fix_plan.md §0a execution record (2026-08-01)

### HAFISCAL_REFSIM_PARALLEL
**Default:** unset (serial `eco_ref.solve()`)
**Values:** integer string N ≥ 2 = fork N cohort-solve workers; unset/`1`/non-digit = serial
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/jax_mc_ad_multicohort.py:106
**Purpose:** Cohort-parallel solve for the JAX-AD auto-init HARK ref sim: uses fork-based `parallel_solve.parallel_eco_solve` with plain HARK `solve_agent` in each worker (bypasses the 2B-aware persistent pool in `welfare6_scenario`). Only affects the one ref-sim solve inside `_build_init_panels_via_hark_quick_sim`; bit-identical output (cohort scheduling only). HAZARD: `run_welfare6_parallel.py:97` pops it from child envs because inheriting it into 4 concurrent children would cascade into 4×21 = 84 fork workers.
**Refs:** Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py:85-100 (hazard comment); memory project_parallel_solve_baseline_2026_05_19 (parallel_eco_solve provenance)

### HAFISCAL_AD_SNIFF_TEST
**Default:** unset (off)
**Values:** `1` | `on` | `true` (case-insensitive) = on
**Status:** diagnostic — **slow-accurate tier only**; never wired into standard/fast.
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py:1013 (`run_recession_AD`)
**Purpose:** Runs ONE extra `eco.solve()` after the AD loop reports convergence, reports how far it moved the policy (max relative change of every agent's every Markov-state `cFunc` on a fixed 400-point grid), then **throws the test solution away and restores the prior cFunc**. That discard is the point: owner ruling 2026-07-29 is that a post-convergence solve is a *measurement of* convergence, not a correction to it, so the converged cFunc is kept regardless of the verdict. Warns when the move exceeds `HAFISCAL_AD_SNIFF_TOL`, which means the AD rule is not converged to the accuracy the tier claims. Before that ruling the extra solve happened by ACCIDENT on some paths only (`restore_ADsolution` does not refresh `MrkvArray_prev`), which is the defect BUG-064 finished closing.
**Refs:** BUGS_private/HAFiscal_BUG-064_duration_loop_redundant_resolve.md; memory ad-policy-convergence-standard

### HAFISCAL_AD_SNIFF_TOL
**Default:** `1e-2`
**Values:** float
**Status:** diagnostic (companion to `HAFISCAL_AD_SNIFF_TEST`; inert unless that is on)
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py:1026 (`run_recession_AD`)
**Purpose:** Verdict threshold for the sniff test: a move at or below it prints CONVERGED, above it prints NOT CONVERGED and raises a warning naming `HAFISCAL_AD_CONVERGENCE_TOL` as the first lever. Scale for choosing a value: MEASURED at Baseline `recessionCheck_AD`, one extra solve moved the policy by **1.5e-06 under HARK-AD** and **9.5e-03 under JAX-AD** — i.e. the default 1e-2 passes both, and a tolerance tight enough to separate the two engines is what `HAFISCAL_AD_POLISH_TOL` exists to equalise.
**Refs:** as HAFISCAL_AD_SNIFF_TEST

### HAFISCAL_AD_POLISH_TOL
**Default:** unset (off — production keeps the AD loop's converged cFunc)
**Values:** float, e.g. `1e-6` (empty/unset = off)
**Status:** diagnostic (A/B only). Production keeps the owner's 2026-07-29 rule: an extra solve after convergence is a SNIFF TEST, not a correction — discard it.
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py:992 (`run_recession_AD`)
**Purpose:** After AD convergence, repeat `eco.solve()` until one more solve moves the policy by less than this tolerance, measured as the max relative change of every agent's every Markov-state `cFunc` on a fixed 400-point grid. Exists because the AD loop's warm-started solves (1–2 Bellman iterations each) leave the policy a different distance from its fixed point depending on how the engine's rule path evolved — MEASURED at Baseline: HARK 1.5e-06 vs JAX 9.5e-03 from one extra solve. Comparing walls or outputs across engines without equalising this compares two different convergence targets, so cross-engine A/B work should set the same tolerance in both arms. Prints the per-iteration policy moves and the cost.
**Refs:** plans/20260729-1230h_hybrid-engine-and-jax-residual_plan.md (PLAN C, C1); memory ad-policy-convergence-standard

### HAFISCAL_AD_POLISH_MAXIT
**Default:** `12`
**Values:** integer ≥ 1
**Status:** diagnostic (companion to `HAFISCAL_AD_POLISH_TOL`; inert unless that is set)
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py:997 (`run_recession_AD`)
**Purpose:** Caps the number of extra post-convergence solves `HAFISCAL_AD_POLISH_TOL` will spend chasing its tolerance, so a tolerance the loop cannot reach costs a bounded amount rather than running away. Reaching the cap without meeting the tolerance is visible in the printed move list (the last value will still exceed the target).
**Refs:** as HAFISCAL_AD_POLISH_TOL

### HAFISCAL_DURATION_FORK
**Default:** `auto` (keep the duration pool even when JAX is loaded)
**Values:** `auto` (default) | `off` (force `duration_workers=1` whenever `jax` is in `sys.modules`)
**Status:** live — the default was FLIPPED 2026-07-30 from the old unconditional force-to-serial, which was measured to cost ~6.1x per AD scenario on a premise that no longer holds.
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py:711 (`_prob_weighted_rec`)
**Purpose:** Whether the recession-duration fork pool may run in a JAX-loaded process. `25fbff76` forced it to serial on two grounds, both since explained by other causes: the "15.7x JAX penalty" (3441.5 s vs 219.0 s at dw=2) was the wasted post-AD re-solve that only the JAX arm paid (BUG-064's AD-path twin, fixed 2026-07-29), and "the pool does not scale anyway" generalised a Reduced-scale non-AD sweep dominated by that same re-solve. The residual concern — `os.fork()` in a multithreaded process can inherit a lock held by a background thread — is real and silent, so it was MEASURED: Baseline `recessionCheck`, post-AD economy, JAX imported **and compiled** (102 live XLA threads), **3 repeats** at each width because a fork/thread deadlock is a race. Result: no hang, dw=1 361.8 s → dw=8 59.1 s = **6.12×**, a **single `AggCons` hash across all 8 runs**, and JAX-in-process costing **1.048×** at dw=8 (noise). The duration children never touch JAX — `run_experiment` is pure HARK/numpy — which is why the hazard does not bite. Set `off` if a hang ever appears on other hardware; the better fix would then be a spawn/forkserver pool, not a return to serial.
**Refs:** plans/20260730-1130h_revised-default-speed-profile_plan.md (R2); BUGS_private/HAFiscal_BUG-064_duration_loop_redundant_resolve.md; artifact welfare6_scenario_results_Baseline_hybrid/SUMMARY_R2.txt

### HAFISCAL_DURATION_RESOLVE
**Default:** unset (off — the duration loop never re-solves)
**Values:** `1` | `on` | `true` (case-insensitive) = on (restore the pre-BUG-064 behaviour)
**Status:** diagnostic A/B lever only. The default (off) is the FIX; turning it on reinstates a measured ~94% waste and is for before/after work exclusively.
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py:651 (`_prob_weighted_rec`)
**Purpose:** BUG-064. `run_experiment` calls `solve_if_changed()` per agent, which re-solves whenever `MrkvArray != MrkvArray_prev`; `switch_shock_type` swaps `MrkvArray` (6x6 base → 132x132 recession) and `Market.solve()` never updates `MrkvArray_prev`, so on the non-AD path the guard fired on the FIRST task of EVERY forked duration child — 21 agents, serially, per child. `_prob_weighted_rec` now syncs `MrkvArray_prev` in the parent before the fork, so every caller inherits it (`run_recession_AD` did the same thing at its own line since 2026-07-29; that line is now redundant and kept as documentation). MEASURED 2026-07-30, Baseline `recessionCheck`, solo box, dw=2: duration loop **3320.6 s → 208.0 s (16.0×)**, matching its AD twin's 208.0–238.7 s; ≈3.46 core-hours per welfare battery. **Result-neutral, not a trade:** the skipped re-solve reproduces the policy EXACTLY (measured policy move `0.000e+00` at both HS_Only and Baseline), and all result panels agree to 4.0e-16 (mean 3e-22) — floating-point summation order, not a difference. Setting this flag is therefore never appropriate outside an A/B.
**Refs:** BUGS_private/HAFiscal_BUG-064_duration_loop_redundant_resolve.md; plans/20260730-0900h_hark-vs-jax-duration-residual_diagnosis_plan.md §4; Code/HA-Models/FromPandemicCode/test_duration_no_resolve.py

### HAFISCAL_AD_INIT_CACHE
**Default:** unset (off standalone); **DEFAULT-ON under the hybrid welfare engine** (canonical default 2026-08-02; see `HAFISCAL_WELFARE_ENGINE`)
**Values:** `1` | `on` | `true` (case-insensitive) = on; additionally requires `HAFISCAL_USE_SOLUTION_CACHE=1`
**Status:** diagnostic (opt-in speedup; default path byte-unchanged)
**Read by:** Code/HA-Models/solution_cache/cache.py:247 (`_recession_init_cache_enabled`, gating `save_recession_init_cache`/`load_recession_init_cache`)
**Purpose:** Lever #1 — shared **recession-init solve cache**. The cold per-cohort recession EGM solve done by the JAX-AD init ref sim (`jax_mc_ad_multicohort._build_init_panels_via_hark_quick_sim`) is bit-identical to the no-AD recession scenario's solve (same shock_type, flat belief, same calibration) and is ~89% of the JAX-AD loop wall at Baseline (~1188 s). When on, `welfare6_scenario.run_recession` POPULATES a per-(parametrization, shock_type) cache (tagged `hark_solve_only`, distinct from the `ad_*` AD-converged cache) and the AD init CONSUMES it, skipping the redundant cold solve. Measured 9.35× AD-loop speedup at Baseline (1337 s → 143 s) and 3.5× on the AD stage (677.8 → 195.1 s, 2026-07-31 controlled gate). **NOT bit-neutral (corrects the earlier "bit-identical AggCons rel 0.0" claim):** the 2026-07-31 A/B (fresh same-night save, HIT verified, twice-reproduced to 0.000e+00 between treatments) shows a deterministic ~1e-5-class offset vs the uncached path — AggCons ≤3.4e-6, panels ~1e-5, same 6 AD iterations, divergence present from iter 1. Mechanism: the twin's converged solve is substituted for the ref-sim's own fresh solve; two warm-started fixed-point iterations stopped at tolerance from microscopically different states. Agreement 5–6 significant figures, ~3 orders below the S=4 seed band. Dossier: `conclusions_private/2026-07-31_overnight-hybrid-finalization.md` §2 + `welfare6_scenario_results_Baseline_hybrid/night_20260730/N1_ANALYSIS.md`. Best-effort + gated: any miss/failure falls back to the normal cold solve, never a wrong result. CAVEAT: under the concurrent welfare launcher the no-AD and AD children start together, so the in-pipeline win requires the no-AD recession scenarios to run/save BEFORE the AD ones (or a re-run that HITs the on-disk cache).
**Refs:** Code/HA-Models/FromPandemicCode/jax_mc_ad_multicohort.py:104 (consumer); Code/HA-Models/FromPandemicCode/welfare6_scenario.py:702 (producer); memory project_ad_speedup_gpu_fix_and_stale_cache

### HAFISCAL_AD_FULL_CACHE
**Default:** `on` under the master gate `HAFISCAL_USE_SOLUTION_CACHE=1` (the hybrid welfare bundle); additionally an EXPLICIT `1`|`on`|`true` activates it WITHOUT the master gate (the Step-5a entry point does not set the master gate; arming only ad_full there must not drag the other solve caches along)
**Values:** `off` | `0` | `false` = disable; `1` | `on` | `true` = explicit-affirmative; unset = master-gate default
**Status:** live (owner-adopted 2026-08-03; plan 20260803-1030h)
**Read by:** Code/HA-Models/solution_cache/cache.py (`_ad_full_enabled`, gating `save/load_ad_full_cache`); consumers/guards in Code/HA-Models/jax_mc_replay_ad.py (engine `jax_mc_replay_ad`, welfare default) and Code/HA-Models/FromPandemicCode/tm_methods.py `run_ad_tm` (engine `tm_a`, Step-5a trainings — entries keyed apart by the engine label)
**Purpose:** **Guarded wholesale AD-converged cache.** Stores the AD loop's converged, belief-consistent pair (belief `CFunc` + per-agent solutions) WHOLESALE (the byte-faithful `policy_full` pickle pattern — NOT the knot-extraction serializer, whose tail loss measured 7.2e-3 on installed solutions). On every HIT the replay engine runs the owner's ONE-ITERATION DOUBLE-CHECK: the loop starts from the cached belief, its first iteration is a fresh solve + one map step, and the guard verifies (amendment 2) the step against `max(2×tol, 2×producer_final_step)` and (amendment 1) the fresh policies against the CACHED policies (probe-grid max-rel, threshold 1e-3 — an order above solver-path noise ~1e-5, an order below the known corruption class 7.2e-3); on PASS the check's fresh work is DISCARDED and the cached state kept — **HIT outputs are byte-identical to the producer run** (a pure function of the cached state; gate-verified). On FAIL the entry is QUARANTINED (`.quarantined` rename) and the loop simply continues cold, republishing a fresh entry — corruption degrades to slowness, never to wrong numbers. Amendment 3: the producer's step series / final step / modulus estimate (outer AD map ρ≈0.25 measured) ride in the entry meta. Supersedes `HAFISCAL_AD_BELIEF_SEED` for the default path (strictly faster than the seed AND byte-deterministic). Wall-measurement harnesses must quarantine `ad_full*` entries exactly like `ad_*`. There is NO separate guard-off escape — the guard is constitutive of the adoption; `off` reverts to the cold loop. Decision record: conclusions_private/2026-08-03_ad-warmstart-dialogue-and-guarded-cache-ruling.md.
**Refs:** plans/20260803-1030h_guarded-wholesale-ad-cache_plan.md; plans/20260803-0900h_reuse-aware-provenance_plan.md (guard verdicts → sidecar)

### HAFISCAL_BASE_SHARE
**Default:** `on` (but only ACTIVE when the master gate `HAFISCAL_USE_SOLUTION_CACHE=1` is set — e.g. under the hybrid welfare engine's bundle; standalone default runs are unaffected)
**Values:** `off` | `0` | `false` (case-insensitive) = disable; anything else = on
**Status:** live (R3 of the structural-speedups ladder, 2026-08-02)
**Read by:** Code/HA-Models/solution_cache/cache.py (`_base_share_enabled`, gating `save_base_aggcons_cache`/`load_base_aggcons_cache`)
**Purpose:** **Base-run AggCons share.** Every welfare6 child used to re-simulate the no-policy `base` run before its scenario, solely to feed `AggEco.store_baseline(AggCons)` — 12 bit-identical base sims per battery, each ~60–150 s (contended) sitting on the child's serial prefix. The only cross-child consumers of that run are the AggCons T-vector (the AD loop's reference path + the recorded `Cratio_hist`); the panels serve only the base child's own pkl. So the base child (or any MISS-path child) PUBLISHES the vector under the SIM key (`gather_sim_inputs`: live per-cohort RNG seeds, shuffle/init-panel env switches, panel shape, EconomyMrkv_init, base_dict scalars) and non-base children LOAD it, calling `store_baseline` directly and skipping the base sim. Exact by construction: `store_baseline` snapshots the current solve state (which the base sim does not alter) and every `run_experiment` re-seeds its RNG streams, so downstream scenario panels are byte-unchanged (gated at adoption: pkl byte-identity vs the R2 anchor battery). Keying on live cohort seeds means different `--seed-offset` runs can never cross-load even through a mis-plumbed advisory offset. Best-effort: any failure or MISS falls back to computing the base run exactly as before. Engagement evidence: `[base-share] HIT`/`SAVED` log lines. First battery on a fresh cache: early-launched children race (compute redundantly, first atomic writer wins — by design, no blocking); late-launched children and all subsequent runs HIT.
**Refs:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py (`run_base` producer + `main()` consumer); plans/20260802-1900h_structural-speedups-analysis_plan.md (R3)

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

### HAFISCAL_JAX2B_ALLOW_NO_TAIL
**Default:** `0` / unset (the JAX-2B power-law tail attach is ON whenever the power-law PF-decay form is the effective default)
**Values:** `1` = skip the F1.1 post-solve power-law tail attach on the JAX-2B / 2B-vmap solve outputs (restores the pre-2026-07-23 legacy `_JAXcFuncWrap` with naive-linear above-top extrapolation — benchmarking/back-compat only); else = attach
**Status:** diagnostic
**Read by:** Code/HA-Models/jax_mc_speedup/jax2b_powerlaw_tail.py (`attach_enabled`; consumed by `jax_solver_iterated_drop_in.solve_to_convergence_consumer_solution` and `jax_solver_iterated_multicohort.solve_all_cohorts_to_convergence_consumer_solutions`)
**Purpose:** F1 everywhere-audit closure for the JAX-2B surface (owner pre-authorization (b), 2026-07-23): the 2B kernels wrap their solved tables in a pure-numpy interpolant whose above-grid extrapolation was NAIVE-LINEAR — a live default-path gap once the power-law tail became the default. The attach (`jax2b_powerlaw_tail.build_tail_solution`) mirrors the stock solver's per-(state, C-slice) `PowerLawDecayLinearInterp` construction — same `compute_pf_decay_limits` AD-aware (MPCmin, h_AD), same attach conditions, same measured-Q (`local_q_tail`) under `HAFISCAL_PF_DECAY_Q` — as an in-sample-bit-identical post-solve wrap (parity gates in `test_jax2b_powerlaw_tail.py`). One documented deviation: an above-PF-line top knot (stock = Carroll-Kimball HALT) warns + keeps naive-linear for that slice, because the 2B fixed point carries a ~kernel-parity offset that would make a hard HALT brittle. This flag is the escape hatch; it changes the produced cFunc above the grid top at fixed other flags, so it is IN the `solution_cache/keys.py` whitelist. Under `exp`/`0` forms there is no attach either (2B never had an exponential attach; that IS the legacy behavior).
**Refs:** plans/20260723_measured-q-tail-default-finalization_plan.md (F1); conclusions_private/2026-07-23_f1_everywhere_audit.md; Code/HA-Models/jax_mc_speedup/jax2b_powerlaw_tail.py

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
**Purpose:** Routes the recession AD outer loop through the JAX multicohort MC driver (`cached_solve_ad_recession` → `solve_ad_recession_jax_multicohort`) instead of HARK MC (`cached_solve_ad_recession_hark`). Supported shock types: `recession`, `recessionUI`, `recessionCheck`, `recessionTaxCut` (the `JAX_AD_SUPPORTED_SCENARIOS` set at welfare6_scenario.py:703 — note the adjacent comment claiming Check/TaxCut are "not yet wired" is stale; all four shipped 2026-05-19). End-to-end ~1.9× at Baseline 5x. Requires `run_base()` to have populated `base_AggCons` (RuntimeError otherwise). CAVEAT: JAX-AD with independent RNG converges to a systematically different AD fixed point (25.4σ welfare-cell at HS_Only; ~6% gap is RNG-realization, not kernel error; **Baseline S=4 whole-cell seed band 2026-07-31: the Check/TaxCut AD-cell offsets sit z=−3.7/−9.7 OUTSIDE the band — a real draw-structure effect, not seed noise; UI inside**) — NOT paper-grade; use `verify_welfare_replay.py` (replay-v2) for paper-grade welfare. `run_welfare6_parallel.py:93` setdefaults it to `1` for its children; `test_jax_mc_ad_regression.py` is the regression harness.
**Refs:** CLAUDE.md "JAX MC kernel for forward simulation"; conclusions_private/2026-05-19_morning_jax_mc_overnight_report.md, conclusions_private/2026-05-19_jax_stratified_shuffle_design.md, conclusions_private/2026-05-20_jax_mc_speedup_and_cache.md

### HAFISCAL_USE_JAX_MC_UNCAPPED
**Default:** unset (off standalone — under the uncapped belief-consistent world, `run_recession_AD` routes AD to HARK-AD and the JAX kernel refuses `T_age=None`); **DEFAULT-ON under the hybrid welfare engine** (canonical default 2026-08-02; see `HAFISCAL_WELFARE_ENGINE`)
**Values:** `1` | `on` | `true` (case-insensitive) = on
**Status:** diagnostic (EVAL/DEV opt-in; owner-ordered GPU evaluation, 2026-07-27 BUG-054 integration night)
**Read by:** Code/HA-Models/FromPandemicCode/welfare6_scenario.py (`run_recession_AD` routing bypass); Code/HA-Models/FromPandemicCode/jax_mc_ad_multicohort.py (guard site)
**Purpose:** Lets the JAX-MC AD kernel run the UNCAPPED world by substituting the tolerance-truncated effective age chain the TM engines use (`tm_methods.effective_age_chain_length`, survivorship ≤1e-9 beyond the buffer — the implied wall carries ~1e-9 mass, belief-consistent to tolerance). `T_age_max` is a jit-static kill threshold only, so the ~3300-quarter chain costs one recompile, no arrays. Purpose: measure whether the GPU is worth returning to the welfare loop under the new world (walls + welfare-cell deltas vs HARK-AD, expected in the known RNG-realization gap class). NOT production: the belief-consistent default remains HARK-AD; the JAX-AD RNG fixed-point caveat (see HAFISCAL_USE_JAX_MC) applies unchanged.
**Refs:** plans/20260727-1750h_bug054-esc-production-integration_plan.md; the HAFISCAL_USE_JAX_MC entry above

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
**Values:** `NAM` | `ATI` | `NAMG` | `AndersonEGM` (case-insensitive; validated against `hark_fti.FTI_METHODS` + `NAMG` + `AndersonEGM`)
**Status:** diagnostic
**Read by:** Code/HA-Models/Target_AggMPCX_LiquWealth/fti_step1.py (`FTI_METHOD`)
**Purpose:** Selects which solver the Step-1 transplant uses. `NAM`/`ATI` are the per-call fast-time-iteration realizations (White's Newton Arbitrage Method / Winant's Accelerated Time Iteration — the same algorithm, two engineerings); both fall back to EGM at the GIC edge. `NAMG` is the opt-in GLOBAL Newton (`hark_fti.global_newton`): it removes the lagged-continuation outer loop so the most-patient (GPF-Mod≈0.999) discount-factor type converges in ~20 grid-independent Newton steps and the safe graft FIRES there (vs EGM fallback). NAMG sizes its own grid top via the closed-form `namg_auto_grid` (see `HAFISCAL_STEP1_FTI_AUTOEXTEND`). Only consulted when `HAFISCAL_STEP1_FTI=1`. `AndersonEGM` is the licence-clean Tier-C Anderson-accelerated EGM. **Tail router (F1, 2026-07-23):** under the power-law PF-decay default, `AndersonEGM` is the ONLY routable method — the transplant solve runs `tail_form='powerlaw'` (`tail_Q=None` => hark_fti's slope-derived Q; an explicit Q threads via the `tail_Q` kwarg of `make_fti_type`/`transplant_fti_cfunc`/`solve_types_fti`), and the exp-pinned `NAM`/`ATI`/`NAMG` refuse loudly (import-time for the env-configured method, per-call for programmatic overrides) unless the legacy tail is explicit (`HAFISCAL_PF_DECAY_EXTRAP=exp`/`0`) or `HAFISCAL_FTI_ALLOW_TAIL_MISMATCH=1`. NOTE: the EGM host is still solved (the simulator reads its full `ConsumerSolution`) and keeps HARK-native exp tails under every form setting — the Step-1 tail convention per the F1.4 neutrality-gate revert (2026-07-24), so a routed Anderson-powerlaw graft faces an exp host and today falls back transparently at the trust gate; NAMG currently swaps the *policy* (correctness), the full wall-clock win awaits driving the simulator from NAMG's own solution.
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
**Default:** `1e-3` (tightened from `5e-2` 2026-07-23, meld plan P0: the old value masked the ~5e-3-class in-sample feedback of a wrong-tail solve — `decay_form/t0_out.txt` — while correct-tail solver parity is ~1e-9, so 1e-3 catches the mismatch class without false-positiving a healthy graft)
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

### HAFISCAL_FTI_ALLOW_TAIL_MISMATCH
**Default:** `0` / unset (the tail-form guard refuses)
**Values:** `1` = allow the exp-pinned FTI methods (`NAM`/`ATI`/`NAMG`) under the active power-law form AND disable the AndersonEGM powerlaw routing (deliberate mismatch benchmarking only); else = exp-pinned methods raise `RuntimeError` (import-time for the env method, per-call for overrides) while `AndersonEGM` routes
**Status:** diagnostic
**Read by:** Code/HA-Models/Target_AggMPCX_LiquWealth/fti_step1.py (the tail-form consistency guard, meld plan Phase-0 core; live since the 2026-07-23 `HAFISCAL_PF_DECAY_EXTRAP` default-ON flip)
**Purpose:** Escape hatch for the Phase-0 guard, KEPT after the guard became a ROUTER (F1, 2026-07-23; meld P1/P2 landed the power-law tail in hark_fti AndersonEGM at fast-time-iteration d474914): under the power-law default, `AndersonEGM` now ROUTES (`tail_form='powerlaw'`) instead of refusing, while the exp-pinned `NAM`/`ATI`/`NAMG` still refuse loudly. Setting `1` restores the PRE-ROUTER behavior everywhere for deliberate mismatch benchmarking: no refusal for any method AND no Anderson routing (the transplant solves exp-pinned as before the flip). Legal alternatives: run the legacy tail explicitly (`HAFISCAL_PF_DECAY_EXTRAP=exp` or `0`).
**Refs:** plans/20260723_powerlaw-tail-meld-execution_plan.md (P0); plans/20260716_anderson-powerlaw-tail-meld_plan.md (Phase 0)

### HAFISCAL_NAMG_ALLOW_TAIL_MISMATCH
**Default:** `0` / unset (the Step-2 NAMG tail-form guard refuses)
**Values:** `1` = allow `HAFISCAL_STEP2_NAMG=1` to proceed even though the power-law PF-decay form is active while the NAMG-Markov solver still attaches the legacy EXPONENTIAL tail (deliberate mismatch benchmarking only); else = `AggregateDemandEconomy._step2_namg_enabled` raises `RuntimeError` at `solve()` time
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py (`_step2_namg_enabled`, the Step-2 NAMG tail-form consistency guard — F1 everywhere-audit, 2026-07-23)
**Purpose:** Escape hatch for the Step-2 twin of the fti_step1 Phase-0 guard (`HAFISCAL_FTI_ALLOW_TAIL_MISMATCH`): under the measured-Q power-law default, the NAMG opt-in would silently produce exp-tailed base solutions where stock EGM attaches the power law. The guard refuses LOUDLY (not a silent EGM fallback — the user explicitly opted into NAMG); this flag permits the mismatch for benchmarking. Routing the P2 powerlaw-chain machinery through NAMG is not trivially available (Tier-G Newton kernel), so the refusal stands until that lands. NOT in the solution-cache key: it only converts a refusal-crash into a run — any run that produces output is already keyed by (`HAFISCAL_STEP2_NAMG`, `HAFISCAL_PF_DECAY_EXTRAP`), and the no-escape variant of that key combination can never write an entry. Legal alternatives: run the legacy tail explicitly (`HAFISCAL_PF_DECAY_EXTRAP=exp` or `0`).
**Refs:** plans/20260723_measured-q-tail-default-finalization_plan.md (F1); conclusions_private/2026-07-23_f1_everywhere_audit.md

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

### HAFISCAL_SKIP_JAX2B_TAIL_ITEST
**Default:** unset (the JAX-2B tail integration test runs)
**Values:** `1` = skip `jax_mc_speedup/test_jax2b_powerlaw_tail.py` at module level (it builds + solves the base estimation economy once, ~40s, plus two cold 2B solves)
**Status:** diagnostic
**Read by:** Code/HA-Models/jax_mc_speedup/test_jax2b_powerlaw_tail.py (module-level skip)
**Purpose:** Test-time escape hatch, mirroring `HAFISCAL_SKIP_STEP2_NAMG_ITEST`, so fast suites can skip the F1.1 JAX-2B power-law tail parity gates (economy build + JIT + two solves, ~2 min). No production effect — read only by the test file.
**Refs:** Code/HA-Models/jax_mc_speedup/test_jax2b_powerlaw_tail.py; plans/20260723_measured-q-tail-default-finalization_plan.md (F1)

### HAFISCAL_SKIP_STEP2_NAMG_ITEST
**Default:** `0` / unset (the integration test runs)
**Values:** `1` = skip the slow build-the-economy integration tests; anything else = run
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/test_step2_namg_base_solver.py (`base_economy` fixture)
**Purpose:** Test-time escape hatch. The `test_step2_namg_base_solver.py` integration tests build + solve the real base estimation economy once (~40s via `EstimAggFiscalMAIN` with `HAFISCAL_SKIP_ESTIMATION=1`). Setting `1` skips that fixture (and the tests that depend on it) so the fast pure-function unit tests can run alone. No production effect — read only by the test suite.
**Refs:** Code/HA-Models/FromPandemicCode/test_step2_namg_base_solver.py

### HAFISCAL_STEP5_ATI
**Default:** unset globally = off — **except the Step-2 ESTIMATION surface, which setdefaults `1` (owner ruling 2026-07-27: ATI-estimation is the default estimation mode — 3.05× per eval-set, 7-minute warm re-estimation; consistency β ~6 digits, worst ∇ 0.714% ≤ the 2% ∇ budget)** — and the Step-5a driver, which setdefaults `1` (tier ratification 2026-07-27). Explicit env always wins; `=0` restores EGM everywhere.
**Values:** `1` = enable the Step-5a ConsumedATI-Markov stationary solver for qualifying agents; anything else = OFF
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py:2922 (`_step5_ati_enabled`, consumed in `AggregateDemandEconomy.solve`); Code/HA-Models/solution_cache/keys.py (cache-key member); Code/HA-Models/test_step5_ati_wiring.py
**Purpose:** Opt-in Step-5a solve speedup (P4b of the power-law-tail meld, on the P4a GO verdict `conclusions_private/2026-07-23_meld_p4a_recession_scale_verdict.md`). When `1`, each qualifying agent's **cold AD-OFF** stationary Markov solve — base (S=6) AND recession-family (S=132/252) structures — is routed through the FTI `hark_fti.consumed_ati_markov.solve_stationary_ConsumedATI_markov(inner='gmres', tail_form='powerlaw', tail_q_mode='chain')` block-Newton solver instead of HARK's iterate-to-tolerance EGM loop, then wrapped into the 2-D `c(m,Cratio)` `ConsumerSolution` (AD-off ⇒ identical `Cgrid` slices; the NAMG wrap precedent). **Strictly additive / qualification-gated** (`_try_solve_ati_markov`): fires only on COLD solves (`from_solution is None` — warm re-solves are ~1-2-sweep EGM no-ops, e.g. the `run_ad_tm` Phase-1 training re-solves) AND `DiscFac >= HAFISCAL_STEP5_ATI_MIN_DISCFAC` (patience routing — the impatient tier loses, P4a caveat 1) AND AD-OFF (`num_macro_states==1` or `ADFunc` identity; AD-ON solves need the genuine 2-D feedback policy and stay EGM) AND `permgrofac_fix_on()` (the kernel applies `(PermGroFac·PermShk)^(-CRRA)` unconditionally — the BUG-047 matched-pair guard, same as NAMG/JAX-2B) AND `BoroCnstArt==0` AND uniform `Rfree`/`LivPrb`; any miss, non-convergence, or exception falls back to the exact EGM path (logged `[step5-ati]`). Parity class (two tiers, measured 2026-07-23): within the consumed(a) formulation the solve is same-fixed-point exact (P4a consumed(a) parity 3.4e-11–7.0e-10 vs the deep power-law Picard reference at S=132/252, fnorm machine-class); ACROSS formulations the converged ATI and production-EGM policies differ ~2e-4 sup-norm, kink-adjacent at low m (the wiring prepends a=0 to the solver grid, collapsing what would otherwise be a ~1e-3 = `aXtraGrid[0]` constrained-region segment error — the `parity_erg_ati_vs_egm` ≈ 9.4–9.9e-4 recorded in every P4a JSON row) plus ~2e-5-class far-tail (chain-Q vs measured-Q attach) — NOT bit-identical ⇒ IN the solution-cache key so ATI- and EGM-solved entries never cross-load; end-to-end to be gated at |Δ|≤1e-3 on Reduced AD multipliers by the P4b A/B. **Validation status (updated 2026-07-25; the 2026-07-23 "gate DEFERRED" wording is SUPERSEDED — the gate subsequently RAN): the Reduced A/B multiplier gate PASSED 2026-07-24** — arm B (ATI: 23.15 min vs stock 26.46 min; 8 agents ROUTED, 0 fallbacks) vs the banked arm A via `t1c_compare_decay_forms.py`: worst |Δmult| **4.1e-5** (AD) / 2.0e-5 (no-AD), ~24× inside the 1e-3 gate (deferred-gate completion section, P4b findings doc). The flag is VALIDATED for opt-in at Reduced scope; Baseline-scope confirmation pending (can ride the parked default-vs-legacy legs); the default-ON decision is queued as speed-program P4 row 1 (`plans/20260724_speed-defaults-deep-dive_plan.md` §R4). Measured wins at S=132 (1-thread): 2.19× at College central, 3.66× at the GIC cap (P4a), losses below the threshold. Lazy import via `_hark_fti_path`; without a `fast-time-iteration` checkout the attempt falls back to EGM cleanly.
**Refs:** plans/20260723_powerlaw-tail-meld-execution_plan.md §5 (P4b); conclusions_private/2026-07-23_meld_p4a_recession_scale_verdict.md; conclusions_private/2026-07-23_meld_p4b_step5_ati_wiring.md; Code/HA-Models/test_step5_ati_wiring.py

### HAFISCAL_STEP5_ATI_MIN_DISCFAC
**Default:** unset ⇒ `0.97`
**Values:** float — minimum `DiscFac` for an agent to take the `HAFISCAL_STEP5_ATI` accelerated path (agents below it keep EGM); non-float ⇒ warn + `0.97`
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py:2929 (`_step5_ati_min_discfac`, consumed in `_try_solve_ati_markov`); Code/HA-Models/solution_cache/keys.py (cache-key member)
**Purpose:** Patience-routing threshold for `HAFISCAL_STEP5_ATI` (P4a caveat 1: ConsumedATI's fixed per-solve overhead exceeds the whole EGM solve for impatient atoms — nothing to accelerate at ~141 sweeps). The default 0.97 sits just below the measured win-crossover: the P4b crossover bench (2026-07-23, real Reduced_Run recession structures at S=132, 1-thread production regime, FTI d474914) put the stock-EGM/ATI wall ratio at 1× near β≈0.973 (College structure: 0.58×@0.958, 0.82×@0.968, 1.17×@0.978, 2.19×@0.99193) and β≈0.969 (HS structure: 0.51×@0.93518, 0.68×@0.958, 1.25×@0.978); ATI outer iterations are flat in β (11-15), so the ratio is driven by EGM's β-driven sweep count. Because the threshold selects WHICH atoms' solutions come from which engine, it is in the solution-cache key (same never-cross-load class as the on/off flag). Only meaningful when `HAFISCAL_STEP5_ATI=1`.
**Refs:** conclusions_private/2026-07-23_meld_p4b_step5_ati_wiring.md (crossover table); conclusions_private/2026-07-23_meld_p4a_recession_scale_verdict.md (caveat 1)

### HAFISCAL_SKIP_STEP5_ATI_ITEST
**Default:** `0` / unset (the integration tests run)
**Values:** `1` = skip the build-the-economy Step-5 ATI wiring tests; anything else = run
**Status:** diagnostic
**Read by:** Code/HA-Models/test_step5_ati_wiring.py (module-level `pytestmark`)
**Purpose:** Test-time escape hatch, mirroring `HAFISCAL_SKIP_STEP2_NAMG_ITEST`. The `test_step5_ati_wiring.py` tests construct a real HS_Only `AggFiscalType` economy once (~1-2 min via the P4a harness's construction-only path) and run several cold base solves; setting `1` skips the whole module so fast suites can run alone. No production effect — read only by the test file.
**Refs:** Code/HA-Models/test_step5_ati_wiring.py

### HAFISCAL_AD_ANDERSON
**Default:** `0` / unset (stock damped-Picard AD outer loop; byte-identical)
**Values:** `1` = enable Anderson acceleration of the AD outer fixed-point loop; anything else = OFF
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/AggFiscalModel.py:2683 (`solve_ad_recession`; also `self.ad_anderson` attribute)
**Purpose:** Opt-in PoC speedup for the **aggregate-demand outer fixed point** (Step-5 recession/AD scenarios). The AD loop is a damped-Picard fixed point in the aggregate `CFunc`; when ON, `_ad_anderson_step` mixes the recent `CFunc`-parameter residual history via a tiny least-squares (`_cfunc_to_vec`/`_vec_to_cfunc`) to reach the SAME fixed point in fewer outer iterations. The map and convergence metric are unchanged; only the Old→next update differs. Strictly opt-in: default OFF ⇒ byte-identical loop (first iteration and singular windows fall back to plain Picard `x←G(x)`). PoC; not on any production path.
**Refs:** llorracc/fast-time-iteration findings/20260617-0130h_step2-anderson-speedup-assessment.md; findings/20260616-1700h_namg-anderson-beats-global-newton-multistate.md

### HAFISCAL_DIST_TAIL_BUCKET
**Default:** `off` / unset (byte-identical: the flag-off branch runs the unchanged per-(j,a) ergodic pooling)
**Values:** `off` (default) | `on` (= `pile`) | `pile` | `anchored`; unrecognized values warn and stay OFF
**Status:** diagnostic
**Read by:** Code/HA-Models/FromPandemicCode/estim_phase2_tm_a.py (per-agent pooling loop inside `betas_obj_func_educ_tm_a`; lazily path-loads Code/HA-Models/decay_form/disttop_tail_bucket.py)
**Purpose:** Opt-in R-d **per-atom analytic Pareto tail-bucket** for the Step-2 TM-a estimation read-out. The TM lottery piles all ergodic mass above the dist-grid top (`dist_aGrid_max`) into the top node — mass total right, location wrong — truncating the wealth integrals (College Lorenz targets, E[a], top shares); grid height cannot fix the cap atom's fat tail (deep wealth decay ~T^(1−α), α≈1.5, so halving the error costs ~5× in top — the ε ruling 4%/2%/1% makes STANDARD/REFERENCE grid-infeasible). When on, each ATOM's marginal ergodic gets its top-node pile replaced by a discretized truncated-Pareto tail above its own grid top, exponent = the atom's OWN measured tail alpha (local log-ccdf fit on [top/6, top/2]; primary per the standing local-measurement rule), falling back to the atom's Kesten root — α solving L·E[(Þ_Γ/ψ)^α]=1 — via `per_atom_alpha.py` (absent/incompatible module ⟹ warn-once, measured-only; unresolvable alpha ⟹ conservative raw append). PER-ATOM because the pooled exponent drifts with window height (mixture artifact) — the pooled v2 `pile` under-corrected (+0.80%, consistency FAIL) and v3 `anchored` over-corrected (−3.18%); per-atom the two variants should nearly AGREE, which is the battery's variant-agreement gate (both variants kept for exactly that test). Mass-preserving; applied before the pooled concatenate, so the ESC (1−ς) household correction and all downstream estimand math are unchanged.
**Refs:** plans/20260726_dist-grid-top-scoping_plan.md (§R-d prototype, ε ruling, R-c×R-d recommendation); Code/HA-Models/decay_form/disttop_tail_bucket.py; conclusions_private/2026-06-16_gic-inside-vs-outside-individual-target-vs-tm-ergodic.md

### HAFISCAL_DIST_TAIL_STATE
**Default:** `off` globally — but **EPOCH 2026-07-27: the default-world ESTIMATION surface setdefaults `on`** at the `estim_phase2_tm_a` entry point (the installed calibration was estimated with it; `as-corrected` estimation keeps `off`). The Step-5a path keeps `off` (refuses tail TMs by scope; measured top-indifferent at 3e-5). Explicit env always wins.
**Values:** `off` | `0` | `''` (off) | `on` | `1` (on); any other value raises ValueError at the read site (precedent: `HAFISCAL_DIST_TOP_MODE`)
**Status:** diagnostic
**Cache-key:** `path` (build-PATH selector — TM-side outputs differ at identical hashed static params; same class as `HAFISCAL_DIST_TOP_MODE`)
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py (`_dist_tail_state_enabled`, consumed by `build_tm_agg_fiscal_a` (build dispatch + guards + `_tm_a_cache` disable), `build_experiment_period_tm_a` / `propagate_experiment_tm_a` (refuse at entry), `tail_state_readout`); Code/HA-Models/FromPandemicCode/estim_phase2_tm_a.py (read-out branch in `betas_obj_func_educ_tm_a`); Code/HA-Models/solution_cache/keys.py (cache-key member); lazily imports Code/HA-Models/dist_tail_state.py
**Purpose:** Opt-in P4′ **dynamics-level analytic Pareto tail state** for the a-indexed baseline-ergodic TM (scope **TS-1**: baseline-ergodic build + estimation read-out ONLY). One tail state T_j per micro state is appended to the state space (TM becomes `(A+1)*J`, layout `j*(A+1)+i`, T_j at `i=A`): INFLOW = the mass the lottery currently clips to the top grid node (`a_next >= dist_aGrid[-1]` — the boundary belongs to T's support); OUTFLOW = death→newborn culling exactly as ordinary states (newborns at the grid bottom; NewBornDist carries zero tail mass) plus shock-driven re-entry — per destination j′ and shock atom s with per-survivor multiplier `m = (R·β·L_raw)^(1/ρ)/(Γ_j′·ψ_s)`, all mass stays for `m≥1`, else `P(stay)=m^α` with the returning `1−m^α` landing as a truncated Pareto(α) on `[mX, X)` lotteried onto the grid (mass- and mean-preserving). α INPUT = the **T_age-SPLIT per-atom Kesten root** (culling at `L_eff=_effective_LivPrb(...)`, discounting at `β·L_raw` inside the CRRA root; `per_atom_alpha.kesten_alpha(β·L_raw/L_eff, ..., LivPrb=L_eff)` ≈ 2.163 at the cap atom) — deliberate owner-recorded deviation from measured-α-primary: measurement at low tops is corrupted by the very truncation being removed; the ladder-flatness gate is the measured validation. Read-out for moments only: the pooled tail mass expands into K=12 log-spaced Pareto segments plus a closed-form **terminal atom** (mass `span^-α` at `α/(α−1)·span·X`; exactly mean-preserving at any span), via `tail_state_readout`. Guards: ESC-only, Cratio=1-only, `neutral_measure=False`-only, uniform R/LivPrb across micro states, α ∈ (1,20) plausibility band (else per-atom DISABLE → standard A*J build, with a `m_top<1e-8` materiality tripwire at read-out), mutual exclusion with `HAFISCAL_DIST_TAIL_BUCKET`, `HAFISCAL_TM_A_CACHE` disabled while on; the experiment/Step-5a path (top-indifferent at 3e-5) **refuses loudly** at entry and on any handed-in `(A+1)*J` distribution. Known quantified residual: the frozen-Pareto one-state law overstates stationary tail mass ~+9% at the cap atom (≈+0.3% of College wealth at X=1300) — pre-registered as the expected ladder-offset profile.
**Refs:** plans/20260726_dist-grid-top-scoping_plan.md (§P4′ TAIL STATE + gate); conclusions_private/2026-07-26_peratom_battery_verdict.md (owner rulings); Code/HA-Models/dist_tail_state.py (module docstring = the implementation map of the DERIVATION note); Code/HA-Models/per_atom_alpha.py (Kesten root); Code/HA-Models/test_tail_state.py

### HAFISCAL_T_AGE
**Default:** unset = **UNCAPPED** (`T_age=None`, both Baseline and Reduced) — **EPOCH 2026-07-27**: the belief-consistent perpetual-youth world is the default (agents' constant-hazard beliefs = the actual process). The QE-era cap (`200` = die at 75; Crawley 2022 commit 770d4d04, BUG-038-restored) is restored by `HAFISCAL_T_AGE=200` or by `HAFISCAL_WORLD=as-corrected` (catalog-applied).
**Values:** `none`|`off`|`0` = NO maximum age (perpetual youth exactly as the paper's text describes — the cap is documented nowhere in the paper); positive integer = that cap in quarters (e.g. `280` ≈ die by 95, `320` ≈ 105, having entered at 25).
**Status:** live (owner decision 2026-07-26; default flip scheduled for the tail-state calibration epoch)
**Read by:** Code/HA-Models/FromPandemicCode/Parameters.py (both `T_age` assignment sites + the `T_sim=2·T_age` burn-in guard, 400 when uncapped); Code/HA-Models/FromPandemicCode/EstimParameters.py (the estimation-surface `init_dropout` dict); consumers handle `None` via `tm_methods._effective_LivPrb` (exact: L_eff→L_raw) and `tm_methods.effective_age_chain_length` (tolerance-truncated age chains replacing the legacy hardcoded-400 fallback that discarded ~8% of survivors); `jax_mc_ad_multicohort` REFUSES `None` loudly (the JAX-MC kernel has no uncapped mode; its old `or 100` idiom would have silently reintroduced a 100-quarter cap). In `solution_cache/keys.py`.
**Purpose:** The memoryless LivPrb=1−1/160 has a long age tail, so the 200-quarter wall executes **28.5% of every cohort** (effective quarterly mortality 0.875% vs raw 0.625%) and thins the wealth tail (cap-atom Kesten α 2.1634 capped vs 1.7793 uncapped — the T_age-SPLIT root discovered in the tail-state derivation, `decay_form/tail_state_DERIVATION_20260726.md`). Removing it makes code match paper text, fattens the top tail toward the empirical US α≈1.5, and removes an undocumented, unanalyzed mortality channel. RESULT-MOVING: deliberate model change (IMPROVEMENT class, not a bug — the QE code intended it), `as-corrected` keeps 200; the default flip rides the tail-state epoch with its matched Step-2 re-estimation.
**Refs:** conclusions_private/2026-07-26_peratom_battery_verdict.md (addendum); plans/20260726_dist-grid-top-scoping_plan.md; BUGS_private/HAFiscal_BUG-038_T_age_cap_removal.md

### HAFISCAL_STEP1_SIM_ENGINE
**Default:** `tm` — **Stage B, owner order 2026-07-27 ("I want all MC outside the welfare context gone")**: the lottery EXPERIMENT is fully DETERMINISTIC (moment-cell two-arm adjoint propagation on (a-node × conditional-p-atom) cells — the owner-corrected g1/g2 design, NO 2-D joint state; exact average over the four win-quarters; bit-identical repeat evals). **Full-target consistency at the production winner: 0.0111485 vs mc 0.0111479 — 0.006%** (the moment-cell experiment is an essentially exact replacement; the earlier 3.1% belonged to the superseded bucket-cells version). Wealth targets under the default come from the DIST form (`HAFISCAL_STEP1_WEALTH_FORM=dist`, gate PASSED 2026-07-27) — engine `tm` runs no panel at all; the mc-800 burn-in panel is retired to the `panel` cross-check. Since BUG-054 Option A (2026-07-27) the TM kernels dispatch the asset rule on HAFISCAL_INTERPRETATION (CDC splurge-in-budget vs ESC plain optimizer rule, with the (1−ς) ESC wealth read-out on the K/Y numerator). `tm_init` = Stage-A seeding (build stepping stone; its seeded-panel wealth targets measure 0.035-class — do not use for calibration). `mc` = byte-identical legacy cross-check. Four implementation bugs were caught by the falsification protocol during the build (splurge-in-budget, a–age–pLvl coupling, the t=800 frame anchor, the burn-in/experiment mislabel).
**Values:** `mc` | `tm_init` (Stage A of the Step-1 TM-a plan: TM-ergodic panel seeding + `HAFISCAL_STEP1_WARMUP` quarters of MC warmup — kills the ~70%-of-eval burn-in AND the BUG-063 truncation of the stationary estimand; the 20-quarter lottery experiment stays MC/CRN) | `tm` (Stage B, deterministic target propagation — NOT BUILT, refuses loudly)
**Status:** live (wired 2026-07-27; owner-ordered acceleration of the estimation steps)
**Read by:** Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py (`_sim_burnin` dispatcher at all three solve-path branches); Code/HA-Models/step1_tm_init.py (the Stage-A machinery: single-state KinkedR aNrm TM with survival + newborn reinjection, ergodic by power iteration, age-geometric + exact lognormal pLvl-by-age seeding)
**Purpose:** BUG-063: mc-800 TRUNCATES the stationary estimand (f0 approaches its T→∞ plateau from below). Consistency criterion = plateau convergence, not point agreement with the truncated legacy value.
**Refs:** plans/20260724_step1-tm-a-simulation_plan.md; BUGS_private (BUG-063 record in conclusions_private/2026-07-24_speed_deepdive_p0p1.md)

### HAFISCAL_STEP1_WARMUP
**Default:** `40`
**Values:** non-negative integer (quarters of MC warmup after the TM-ergodic seed; only read under `HAFISCAL_STEP1_SIM_ENGINE=tm_init`)
**Status:** live
**Read by:** Estimation_BetaNablaSplurge.py
**Purpose:** restores the joint (a, age, pLvl) correlations that the marginal-product seeding omits (plan Stage A); the S3 probe sweeps it to demonstrate plateau convergence.
**Refs:** plans/20260724_step1-tm-a-simulation_plan.md

### HAFISCAL_STEP1_RUN_ESTIMATION
**Default:** `1` (run the estimation loop on import — legacy script behavior)
**Values:** `1` | `0` (=0: import-safe fixed-point evaluation mode — module loads, `FagerengObjFunc` callable, no estimation)
**Status:** live
**Read by:** Estimation_BetaNablaSplurge.py (`Run_estimation` gate)
**Purpose:** lets probes/harnesses evaluate the Step-1 objective at fixed parameters without triggering a multi-hour estimation (the S3 consistency probe pattern).
**Refs:** plans/20260724_step1-tm-a-simulation_plan.md

### HAFISCAL_STEP1_PLOT
**Default:** `1` (produce plots — legacy)
**Values:** `1` | `0` (skip plots; probe/CI mode)
**Status:** live
**Read by:** Estimation_BetaNablaSplurge.py (`Plot_Output` gate)
**Purpose:** companion to HAFISCAL_STEP1_RUN_ESTIMATION for headless probes.
**Refs:** plans/20260724_step1-tm-a-simulation_plan.md

### HAFISCAL_STEP1_TM_INIT_TREF
**Default:** `800`
**Values:** non-negative integer — the aggregate-frame anchor for the Step-1 `tm_init` seeding: pLvl and `PlvlAgg` are seeded at `PermGroFacAgg^(TREF − warmup)` so the lottery experiment starts at exactly the frame the legacy mc-800 procedure measured MPCs at (the estimand is NOT scale-free: the lottery is an absolute level, `Lnrm = Llvl/pLvl`, and `sim_birth` scales newborns by the current `PlvlAgg` — measured newborn intercept e^1.984 = G_agg^800).
**Status:** live
**Read by:** Code/HA-Models/step1_tm_init.py (`seed_and_warmup`)
**Purpose:** documents and pins the t=800 epoch convention embedded in the published Step-1 estimand; change it only as a deliberate estimand redefinition.
**Refs:** plans/20260724_step1-tm-a-simulation_plan.md

### HAFISCAL_STEP1_WEALTH_FORM
**Default:** `dist` — **GATE PASSED 2026-07-27 after the drill-down**: the failure was (1) a newborn-init attr bug (my modules read `aNrmInitMean` defaulting to 0.0 = newborn wealth e⁰=1.0, where the sim's priority falls through to `kLogInitMean=−11.51` ≈ 0 — a spurious +1.0/newborn injection the near-unit-root wealth process amplified into grid-converged, seed-robust +6–8% E[a] on every ordinary type) and (2) the top type's tail clip (fixed by HAFISCAL_STEP1_DIST_TOP_MULT). Post-fix: every moment inside the mc's multi-seed band (Lorenz ±2%, K/Y 7.009 in [6.989, 7.058]); full-target f0 0.00984 sits BELOW the mc seed band [0.011148, 0.011396] because the CRN seed lies farther from the data on K/Y than the seed-average — the tm is the noise-free law. Under this default, engine `tm` runs **NO PANEL AT ALL**: the last non-welfare MC (the burn-in) is retired. `panel` = the legacy mc-800 wealth-target cross-check.
**Values:** `dist` (default: Lorenz/K-Y in distribution form from the joint-moment ergodic (π, g1, g2) + conditional-lognormal read-out — no panel at all) | `panel` (the legacy mc-800 wealth-target cross-check; NOTE the SEEDED panel's wealth targets measured 0.035-class — worse than dist — and are not used by either value). The earlier failure narrative (Lorenz +11–16%, K/Y +2.4%, f0 0.0168) belonged to the SUPERSEDED two-moment version — resolved by the newborn-init fix, the per-cell moment recursions, and the extended top (see the Default line).
**Status:** live (gate-holding)
**Read by:** Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py; Code/HA-Models/step1_tm_targets.py
**Purpose:** stages the final step to a fully panel-free Step-1 behind its falsification gate instead of shipping a failing form as default.
**Refs:** plans/20260724_step1-tm-a-simulation_plan.md

### HAFISCAL_STEP1_DIST_TOP_MULT
**Default:** `10`
**Values:** float ≥1 — the wealth-target moment recursion's dist grid extends the solve-grid top by this factor (≤1 disables). The 2026-07-27 drill: the top β-type's ergodic reaches ~2100 vs the 604 solve-top; the clip under-counted its E[a] by 5.6% (K/Y −2%-class); ×10 closes it to −1.35%. The EXPERIMENT stays on the base grid (top-invariant, measured 1e-6-class).
**Status:** live
**Read by:** Code/HA-Models/step1_tm_targets.py (`_moments_grid`)
**Purpose:** the one genuine "more gridpoints" fix from the dist-form drill-down.
**Refs:** plans/20260724_step1-tm-a-simulation_plan.md

### HAFISCAL_STEP1_DIST_EXTRA
**Default:** `80`
**Values:** non-negative integer — geometric tail points added by the top extension.
**Status:** live
**Read by:** Code/HA-Models/step1_tm_targets.py (`_moments_grid`)
**Purpose:** companion to HAFISCAL_STEP1_DIST_TOP_MULT.
**Refs:** plans/20260724_step1-tm-a-simulation_plan.md
