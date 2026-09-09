# Heterogeneous Agent Models for HAFiscal

This directory contains the core computational code for the heterogeneous agent models used in "Welfare and Spending Effects of Consumption Stimulus Policies" by Carroll, Crawley, Du, Frankovic, and Tretvoll (2025).

> **Authoritative for: pipeline steps, runtimes, outputs.**
> This README is the single source of truth for the 5-step computational pipeline.
> `CLAUDE.md`, `ARCHITECTURE.md`, `do_all-README.md`, and the step comments in
> `do_all.py` carry only short summaries that point here. Where this document and
> the code disagree, the code (`do_all.py` and the scripts it invokes) is the
> arbiter — please file an issue or fix this README.

## Quick Start

### Running the Complete Pipeline

```bash
# Run all computational steps (4-5 days)
python do_all.py

# Or run minimal validation (~1 hour)
python reproduce_min.py
```

### Step Toggles (environment variables read by `do_all.py`)

> Full registry of **all** `HAFISCAL_*` environment flags:
> [`docs/ENV_FLAGS.md`](docs/ENV_FLAGS.md) — kept complete (and the count current)
> by the guard test `test_env_flag_registry.py`.
>
> **Multiplier engine (METHOD axis, IMPROVEMENT-001):** `./reproduce.sh --multiplier-engine tm|mc`
> (or `HAFISCAL_MULTIPLIER_ENGINE`) selects the **multiplier engine** — `tm` = TM a-indexed,
> `mc` = the reliable stratified-**MC** cross-check (all bug fixes ON, TM distribution-grid
> top `dist_aGrid_max`=1300 via `HAFISCAL_TM_AMAX`;
> NOT QE fidelity, NOT the `as-corrected` world). Renamed 2026-06-13 from `HAFISCAL_MODE`
> (`--mode default|legacy` kept as a deprecated alias). Related new flags:
> `HAFISCAL_MC_PLVL_INIT` (analytic-Markov MC pLvl seed), `HAFISCAL_MC_WARMUP`,
> `HAFISCAL_DRIFT_PLVL_{NAWARE,Z}` (N-aware MC⇄TM-a drift gate). See `docs/ENV_FLAGS.md`
> and `../../conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md`.
>
> **Verification level (VERIFY axis, reuse-fidelity):** `./reproduce.sh --complete` /
> `--byte-identical` (or `HAFISCAL_VERIFY_LEVEL=numeric|complete|byte`) selects how hard a
> run double-checks any REUSED solution (AD cache, belief seed, warm start). `numeric`
> (default) = the numerically-equivalent standard — fast, and the default path is
> byte-identical to pre-flag code. `complete` adds the opt-in double-checks (multi-seed
> drift+SE headline, re-solve-and-compare, the de-biased one-step Gate A); `byte` adds
> byte-exact reuse. Orthogonal to the METHOD/WORLD axes. Spec:
> `../../plans/20260622_reuse-fidelity-verification-flag-taxonomy.md`; reader:
> `verify_level.py`. (Consumers wired incrementally — component 1 surface is live.)

Each step can be switched off via `HAFISCAL_RUN_STEP_{1,2,3,4,5}=false`.
Defaults preserve the historical behaviour: **steps 1, 2, 4, 5 on; step 3 off**
(Step 3 produces Online-Appendix robustness results).

- `HAFISCAL_RUN_STEP_5B=false` — skip the MC welfare-6 phase (Step 5b) while
  keeping the TM multipliers (Step 5a): the "multipliers only" /
  `qe_fidelity_fast` pattern.
- `HAFISCAL_QE_FIDELITY=1` — revert Step 5a to the published (legacy)
  m-indexed transition matrix instead of the canonical a-indexed one
  (BUG-033 fix; see Step 5 below).

### Running Individual Steps

```bash
# Step 1: Estimate splurge factor (~20-30 minutes)
cd Target_AggMPCX_LiquWealth
python Estimation_BetaNablaSplurge.py

# Step 2: Estimate discount factor distributions (~15 min under the
# TM-ergodic default engine; ~21-48 h only under the legacy MC engine — see Step 2)
cd FromPandemicCode
python EstimAggFiscalMAIN.py

# Step 5a: TM multipliers (a-indexed canonical; ~45-110 min under the S2+
# entry-point default tier — 45.5 min measured 2026-07-27 at Baseline
# [conclusions_private/2026-07-27_belief-consistent-world_epoch_evidence.md];
# the old "~22.5 h sequential" figure was the pre-S2+/pre-cache era)
cd FromPandemicCode
HAFISCAL_TM_A_INDEXED=1 python AggFiscalMAIN_reduced.py --baseline

# Step 5b: MC welfare-6 (parallel driver; ~13 min steady-state wall with
# warm caches [anchor5 2026-08-02, all-12 byte-identical]; ~42 min first
# battery on a fresh cache; ~54 min pre-R1-R4b certified hybrid)
cd FromPandemicCode
python run_welfare6_parallel.py --baseline --table-dir Tables/Baseline
```

(The old single-phase Step-5 entry point `AggFiscalMAIN.py` was retired at
commit `c7e566d9`, 2026-04-08; see Step 5 below.)

## QE-Frozen Results and the Candidate Workflow

### Annotated build, changed-figure comparisons and the published-axes lock (2026-08-26)

`make pdf-annotated` renders the FROZEN text with an `[UPDATED …]` badge on every table and
figure panel that current code changes (`Code/HA-Models/updates_report.py` generates
`UPDATES.md` — columns PUBLISHED / BUGFIXED / IMPROVED (+ DRAFT only where the text shows a
transitional vintage) and a "What changed" inventory — plus the badge map). Changed figures
of the PUBLISHED paper (QE 17(3), Figures 1–6; the no-splurge appendix is supplemental) get
one page each in `UPDATES-figures.pdf`: the published file from `../HAFiscal-QE` beside the
improved candidate, **on the published figure's axes** — the candidate is regenerated under
`HAFISCAL_FIG_AXES_LOCK` (default on): `Code/HA-Models/fig_axes.py` recovers each published
figure's axis limits from its PDF geometry into `fig_axes_published.json`
(`python Code/HA-Models/fig_axes.py build`) and `generated_output.py` applies them to the
live matplotlib figure before saving; data beyond the published range is clipped and reported
(`FromPandemicCode/Figures/axes_lock_report.json`, quoted on the comparison page). The
figure badges in the annotated PDF link to the comparison pages (keep the two PDFs together).
The online appendix (`Subfiles/Appendix-Robustness.tex`, hand-typed 𝒞 tables; hidden inside the
main PDF, rendered standalone as the tracked `Subfiles/Appendix-Robustness.pdf`) is never
replaced (owner 2026-08-28 17:10): `UPDATES.md` carries a section "Online appendix — robustness
tables" — the published rows beside the re-issued candidates, rendered through
`robustness_appendix_tables.py`'s own row builders — and `make pdf-annotated` also writes
`Subfiles/Appendix-Robustness-annotated.pdf`, badged once at its section head by the style file
(no hook in the appendix source; nothing promoted).
Re-plot candidates without re-simulating: `Output_Results(...)` from a run's saved pickles
(Figures 4, 6), `HA-Fiscal-HANK-SAM-to-python.py` (Figure 5, from the saved Jacobians),
`CreateLPfig.py` / `CreateIMPCfig.py` (Figures 2, 3), and
`HAFISCAL_STEP1_RUN_ESTIMATION=0 Estimation_BetaNablaSplurge.py` (Figure 1).

The QE-published numbers (from `HAFiscal-QE@5aa25fb`, the accepted version)
are **frozen**: every paper-rendered generated table and figure is listed in
`LOCKED_TABLES.manifest` (repo root) with its SHA-256, and both the
pre-commit hook (`.githooks/pre-commit`) and
`Code/HA-Models/test_locked_tables.py` reject changes to those files.
Authority: `plans/20260611_qe-baseline-freeze-and-candidate-lock_plan.md`.

How it works day-to-day:

- **Regeneration never overwrites frozen files.** All generator scripts route
  writes through `FromPandemicCode/generated_output.py`, which appends a
  `_candidate` suffix (e.g. `Multiplier_candidate.tex`,
  `IMPCs_both_candidate.pdf`). Candidates are gitignored. Intermediate
  results (`Results/AllResults_*.txt`, `DiscFacDistributions_*.txt`, Step-2
  estimate files) are candidate-suffixed too; readers
  (`_interpretation.resolve_path`, `generated_output.input_path`) prefer a
  fresh `_candidate` sibling so regenerated results flow down the pipeline.
- **Preview a paper built from candidates:** `make pdf-candidate` (compiles
  `HAFiscal.pdf` reading `_candidate` tables/figures where they exist, frozen
  files elsewhere; PREGENERATED watermark marks frozen content).
- **Promote candidates to frozen** (deliberate, reviewed):
  `HAFISCAL_UNLOCK=1 make promote-tables` — shows numeric diffs, flags prose
  that quotes changed values, asks per-file confirmation, copies candidate
  over frozen (`HAFISCAL_PROMOTE=1` semantics), and updates the manifest.
- **Verify integrity:** `make test-locked` (45 files, hash check).
- **Override** (e.g. deliberate baseline change): set `HAFISCAL_UNLOCK=1` on
  the commit and update `LOCKED_TABLES.manifest` in the same commit.

## Computational Pipeline

The model estimation and policy analysis follows a 5-step pipeline controlled by `do_all.py`:

### Step 1: Estimate Splurge Factor

- **Script**: `Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py`
- **Purpose**: Jointly estimate discount factor distribution (Beta, Nabla) and splurge factor
- **Targets**: Aggregate MPC and liquid wealth distribution from SCF 2004
- **Output**:
  - Figure 1 (paper: `../../Figures/splurge_estimation.pdf`; panels built in `Target_AggMPCX_LiquWealth/Figures/`)
  - Table 1 (`Target_AggMPCX_LiquWealth/Figures/MPC_WealthQuartiles_Table.tex`)
  - Estimated parameters saved as `Target_AggMPCX_LiquWealth/Result_AllTarget*.txt` for later steps
- **Runtime**: ~20 minutes (reported 2025-11); `do_all.py` budgets 30 min (2026-02).
  Since the 2026-08-21/22 grid-only default (hermite60 basis + 8 solved tail knots to
  6× + measured-Q attach) a single start runs ~6–8 min. **The canonical search protocol
  is the CONTINUATION (owner ruling 2026-08-22, `HAFISCAL_STEP1_PROTOCOL`):** stage 1 =
  cold 4-start multistart of the ς=0 restricted problem (basin certification; writes the
  Splurge-0 SoR as a by-product), stage 2 = one joint descent continued from (0, β̂₀,
  ∇̂₀) — deterministic, ~25 min sequential at the fast default grid. The 8-start
  dispersed multistart is the demoted certification instrument (`=multistart`; run per
  calibration change and at install time), ≈45–70 min sequential at the fast grid.
  **Stage-1 acceptance = unanimity OR f-tie (D4 default since 2026-08-23):** the
  full-grid ς=0 valley is flat (~1e-5-relative f), so parameter unanimity alone
  mis-reads one basin as many; the f-tie arm (relative f-range ≤1e-4, derivation in
  `step1_stage1_acceptance.py`) accepts it and min-f selects the continuation point —
  the install-grade S1 runs the ~40-min continuation shape at full. A genuine basin
  split (6e-4-class f-gap) still falls back to the dispersed battery, loudly.

**Install-at-full doctrine (owner-adopted 2026-08-22).** Estimation batteries come in
two kinds. *Exploration* (A/B arms, robustness probes, diagnostics) uses the fast
default above — winner wander of ±0.4% ς / ±1% ∇ among near-tie stops is immaterial to
delta questions at those scales. *Installation* — any battery whose min-f winner will
be written into a consumed Source-of-Record (`Result_AllTarget*.txt`, per-γ
`Result_CRRA_*.txt`, `Result_AllTarget_Splurge0.txt`, Step-2 `DiscFacEstim_*`) — MUST
run with `HAFISCAL_SOLVE_GRID_PROFILE=full` (~35 min if sharded across starts;
~2h30 as the single sequential process the do_all path runs) and, per the 2026-08-22
seam A/B, pin `HAFISCAL_STEP1_TAIL_KNOTS=0` (knots-at-full deliver nothing measurable;
the certified install lineage is knotless): measured on 2026-08-22,
the full-profile winner reproduces the fine-grid optimum to ≤0.01% on every parameter
(f to 7 digits) with a clear f-margin over occasional straggler stops. Evidence + the
full assessment: `conclusions_private/2026-08-22_s1-default-setup-assessment.md`.

### Step 2: Estimate Discount Factor Distributions  

- **Script**: `FromPandemicCode/estim_phase2_tm_a.py` (TM-ergodic engine — the DEFAULT
  since 2026-06-23). `EstimAggFiscalMAIN.py` (MC forward-panel) is the opt-in alternative
  via `HAFISCAL_STEP2_SIM_ENGINE=mc`. Both estimate the same β (validated to ≤0.06% across
  all three cohorts; `conclusions_private/2026-06-23_step2-default-flip-to-tm-ergodic.md`);
  TM-ergodic is ~10–21× faster.
- **Purpose**: Estimate separate discount factor distributions for three education groups
- **Method**: Simulated Method of Moments matching consumption drop upon UI exit (the
  wealth moments are computed by the TM-ergodic stationary distribution by default; the
  MC panel under `=mc`)
- **Post-processing run by `do_all.py`**:
  - `CreateLPfig.py` (Figure 2, Lorenz points / lifecycle profiles)
  - `CreateIMPCfig.py` (Figure 3, intertemporal MPC figures)
  - `estimBetas_tabular_generate.py` (beta-estimation tables)
  - `nonTargetedMoments_tabular_generate.py` (non-targeted-moments tables)
- **Output**:
  - Figure 2 (`FromPandemicCode/LorenzPoints_CRRA_2.0_R_1.01.pdf`)
  - Figure 3 (IMPC figures, `FromPandemicCode/IMPCs_*.pdf`)
  - Estimated parameters for each education group (`Results/DiscFacEstim_*.txt`)
  - Results written to `Results/AllResults_CRRA_2.0_R_1.01.txt`
- **Runtime**: DEFAULT (TM-ergodic) ≈15 min for a full cross-machine run (≈3.5–15 min/group,
  one group per machine via `reproduce/cross_machine_step2.py --engine tm`), or minutes to
  ~1 h single-machine. The MC opt-in (`HAFISCAL_STEP2_SIM_ENGINE=mc`) is ~21 h (≈7 h/group);
  `do_all.py`'s progress tracker still budgets ~48 h for the MC path. Actual wall time is
  strongly hardware-dependent; record runs in `../../reproduce/benchmarks/`.

### Step 3: Robustness with Splurge=0 (Optional — off by default)

- **Script**: the Step-2 engine (default `estim_phase2_tm_a.py`; `EstimAggFiscalMAIN.py`
  under `HAFISCAL_STEP2_SIM_ENGINE=mc`) with Splurge=0:
  `python estim_phase2_tm_a.py 1.01 2.0 0.7 0.5 0`
  (argument order: interest rate, risk aversion, replacement rate w/ benefits,
  replacement rate w/o benefits, splurge)
- **Purpose**: Online appendix robustness check with zero splurge
- **Default**: skipped; enable with `HAFISCAL_RUN_STEP_3=true`
- **Output**: Alternative parametrization results (`Results/AllResults_CRRA_2.0_R_1.01_Splurge0.txt`)
- **Runtime**: Similar to Step 2 (~21 h reported 2025-11; ~48 h budgeted 2026-02)

### Step 4: HANK-SAM Model Robustness

- **Engines** (L4 split, 2026-08-09 — `do_all.py` Step 4 invokes the
  `Code/HA-Models/step4/` entry scripts, the single dispatch point):
  - **live package engine** `Code/HA-Models/step4/` (default):
    `run_jacobians.py` → `hh_setup`+`jacobians` (household fake-news
    Jacobians, 168 (educ × β × instrument) cells; writes
    `HA_Fiscal_Jacs.obj` incl. the weighted steady-state aggregates
    `C_ss_weighted`/`A_ss_weighted`), then `run_ge.py` → `ge`+`figures`
    (sequence-jacobian 1.0.0: IRFs + multipliers for the three policies
    × three monetary rules). Fixed semantics are STRUCTURAL here
    (BUG-071 clean distribution construction, BUG-072 direct zeroth
    column, BUG-073 education-specific growth).
  - **frozen QE-fidelity engine** — the historical monolith pair
    `HA-Fiscal-HANK-SAM.py` + `HA-Fiscal-HANK-SAM-to-python.py`
    (FromPandemicCode): routed automatically under
    `HAFISCAL_QE_FIDELITY=1` (published construction, bugs included,
    bit-for-bit — FAST_BACKWARD defaults off there) or the historical
    escapes `HAFISCAL_STEP4_SHOCK_FIX=0`/`ZEROTH_FIX=0`, or explicitly
    via `HAFISCAL_STEP4_ENGINE=monolith`. Do not refactor the frozen
    pair; live changes go in the package.
- **Purpose**: Section-5 robustness check using Sequence Space Jacobian
  methods
- **Output**:
  - the six paper figures composed by `Figures/HANK_IRFs.tex`
    (`FromPandemicCode/Figures/HANK_{transfer,UI,tax}_{IRF,multiplier}.pdf`,
    candidate-routed) — NOT the orphaned root `Figures/HANK_IRFs.pdf`
  - `Results_HANK/multipliers_across_horizon_w_splurge.obj`, consumed by
    Step 5's `Output_Results.py` for `Cumulative_multipliers_withHank`
    (the Step-4→Step-5 dependency)
  - `HA_Fiscal_Jacs.obj` (also read by `dashboard/`; the sibling
    `HA_Fiscal_Jacs_UI_extend_real.obj` has NO in-tree producer and is
    only read by the dashboards)
- **Runtime**: **~13 min for the Jacobians + ~13 s for the experiments**
  (2026-08-09, i9-13900K, `HAFISCAL_STEP4_FAST_BACKWARD=1` default; the
  2,950 s → 796 s rebuild lineage is in
  `plans/20260808-1638h_step4-jacobian-rebuild_plan.md`). Historical
  walls: ~64 min (2026-08-03, pre-rebuild), "~12 h" (0.14-era budget).
  NOTE: Step 4 was BROKEN at HEAD from the 0.14.1→0.17.0 upgrade until
  2026-08-03 (BUG-069); its solves consumed stale pre-scaling shocks
  through the published era (BUG-071, fixed default-ON 2026-08-08); the
  fake-news s=0 column omitted the date-0 behavioral response (BUG-072,
  ADOPTED default-ON 2026-08-09); the households discarded the PE
  education-specific growth calibration (BUG-073, ADOPTED default-ON
  2026-08-09). The default Section-5 configuration carries all three
  fixes; `HAFISCAL_QE_FIDELITY=1` reproduces the published construction
  with all three bugs included.
- **Flags**: `HAFISCAL_STEP4_{ENGINE, SHOCK_FIX, FAST_TRANMAT,
  FAST_BACKWARD, ZEROTH_FIX, SKIP_INSTRUMENTS, FASTEOP}` + the
  `HAFISCAL_HANK_*` A/B arms — all in `docs/ENV_FLAGS.md`. The GE
  stage's audit ledger lives in
  `conclusions_private/2026-08-09_hank-sam-scoping-dossier.md`.

### Step 5: Compare Fiscal Stimulus Policies

> **One equilibrium (owner ruling 2026-08-25).** In the `default` world Step 5b (MC welfare-6)
> no longer iterates its own aggregate-demand fixed point: it installs the AD equilibrium Step 5a
> (TM multipliers) converged and published into the policy store (`HAFISCAL_AD_EQUILIBRIUM_SHARE`,
> class IMPROVEMENT in `config/catalog.py`), measures on the weighted-tail household panel
> (`HAFISCAL_MC_WEIGHTED_TAIL=200`), and solves nothing. Consequences: run 5a before 5b for the same
> world/parametrization (a missing equilibrium is an error, not a silent fall-back); the battery is
> ~3x faster; the multiplier and welfare tables share one equilibrium. The `as-corrected` world keeps
> the paper's own-loop battery unless `HAFISCAL_AD_EQUILIBRIUM_SHARE=1` is set explicitly.

> **Seed pairing across bands (owner 2026-09-07: "put pairing to work").** Every band runs whole-cell
> seeds 0..4, so seed k of two runs starts from one random state; a same-engine code change keeps the
> two PAIRED (per-seed differences scatter ~5x less than independent draws), while a change to the
> panel sampler or the AD path decouples the UI cells (default vs as-corrected). Tools, SST
> `welfare_band_compare.py`: `make welfare-compare A=… B=…` (paired table: mean difference, paired
> and unpaired SE, pairing verdict per cell); `make welfare-reference [WORLD=…]` blesses a band as this
> machine's reference (untracked `welfare_reference/<world>/`); `make welfare-check` runs the
> SEED-PAIRED C4 gate against it (`full_profile_rerun_gates.py s5b --reference-band`: UI 5 %,
> check_rec_AD 1.5 %, check_rec 1 %, quiet 0.5 % on the mean paired difference, behind a quiet-cell
> pairing probe and a per-cell resolution rule of >= 4 paired SEs) — the only gate that sees an error
> hitting every seed alike; the internal band (`s5b --fresh` alone) is a broken-seed detector at four
> deviation-SDs (UI 14 %). `make welfare-bridge` (`welfare_bridge_arm.sh`) runs the default world with
> sharing and the weighted-tail panel OFF so the world-to-world comparison is paired with as-corrected.
> A DECOUPLED/UNPAIRED verdict means a model or sampler change: adjudicate it, then re-bless.
> Owned drivers: `welfare_band_of_record.sh` (seed 0 → `Tables/Baseline`, seeds 0–4 → `Tables/Baseline_seed<k>`, nothing
> pinned but the entry-point flags, so the run itself proves the catalog defaults reach the computation) and
> `welfare_appendix_bands.sh` (the six robustness-appendix bands at S = 3). The default world's MC engine is the paper's
> plain quota-exact shuffle with Hamilton rounding — the certified engine — in BOTH worlds. The income-quintile strata
> shuffle with Madow rounding (catalog rows `shuffle_mrkv_strata` / `shuffle_mrkv_rounding`) was the default world's engine
> from 2026-09-07 21:48 to 2026-09-08 and was REVERTED by the owner ("Revert to plain Hamilton — restore from history and
> re-bless"): at Baseline's occupancy the estimand depends on the number of strata (p:2 − p:5 = −0.89 % ± 0.20 % on the UI
> cell, z 4.6), i.e. it moved the published point estimate to reduce an unpublished seed SE. Both knobs stay OPT-IN;
> decision record `conclusions_private/2026-09-08_strata-shuffle-revert-to-plain-hamilton_decision.md`. A driver whose arm
> means either engine PINS `HAFISCAL_SHUFFLE_MRKV_STRATA` and `HAFISCAL_SHUFFLE_MRKV_ROUNDING` explicitly
> (`test_mrkv_strata_arm_pinning.py`).

> **The UI extension: two improvements, neither a bug fix (owner 2026-08-26).** The published code's
> 4-state freeze (`HAFISCAL_UI_STATE_ENCODING=legacy`, the `as-corrected` world) implements the
> paper's UI paragraph exactly; BUG-043 is withdrawn (`RECONCILED_private/RECONCILED-005_*`).
> **A** — `calendar` (the `default` world): the extension delivered as INCOME at explicit
> extension states on the plain chain in every scenario (7 micro states under the paper's window:
> the freeze holds the onset cohort for three transitions), the paper's policy unchanged —
> `Code/HA-Models/test_ui_extension_schedule.py` proves legacy ≡ calendar row for row; result-neutral
> (TM multipliers to 3 decimals, MC cells to 5e-5; gate record
> `conclusions_private/2026-08-26_ui-extension_gate-G1_HS_Only.md`). **B** — the policy axis
> `HAFISCAL_UI_EXTENSION_POLICY` (`window` = the paper's; `history` = enactment lag 1, open entry,
> hard stop after t=8, +2 quarters/spell — what federal extensions actually did): results change by
> design. Rule SST: `Code/HA-Models/ui_extension_rule.py`; per-parameter overrides
> `HAFISCAL_UI_EXT_{ENACT_LAG,END,ENTRY,QUARTERS}` (`docs/ENV_FLAGS.md`). The 2026-05-16 `bug_fix`
> value (u3Q/u4Q paid iff the current macro state is a recession) is a different policy, kept only for
> reproducing the 05-16..08-26 numbers.

- **Purpose**: Welfare and spending analysis of three policies:
  - UI benefit extension
  - Stimulus checks (lump-sum transfers)
  - Payroll tax cuts
- **Entry points** (two phases; the old single-phase `AggFiscalMAIN.py` was
  retired at commit `c7e566d9`, 2026-04-08 — the two-phase flow is the
  post-splurge-budget-identity-bugfix equivalent used in the April 2026
  production runs):
  - **Step 5a — TM multipliers**: `AggFiscalMAIN_reduced.py --baseline`,
    run with `HAFISCAL_TM_A_INDEXED=1` (a-indexed transition matrix is
    canonical per the BUG-033 fix; the m-indexed TM is structurally 15-25%
    biased under splurge-in-budget because `m` is not a sufficient statistic.
    `HAFISCAL_QE_FIDELITY=1` reverts to the published m-indexed method).
  - **Step 5b — MC welfare-6**: `run_welfare6_parallel.py --baseline
    --table-dir Tables/Baseline` (parallel driver, auto-budgeted workers;
    uses the paper's fixed AD=0 `NPV_AddInc` denominator — see
    `../../history/20260420-ui-recession-gap-resolution.md`).
    Skippable via `HAFISCAL_RUN_STEP_5B=false`.
    **Engine: `hark` (HARK's own Monte Carlo, owner ruling 2026-08-27),
    resolved by `welfare_engine.py`; the HYBRID replay-fed JAX-AD bundle
    (default from 2026-08-02 to 2026-08-27) is opt-in via
    `HAFISCAL_WELFARE_ENGINE=hybrid` — never certified against the all-HARK
    battery (a CRN-paired −0.5…−1.3 % residual on the AD cells that later
    proved to be sharing's own TM-vs-MC gap), and INERT under
    AD-equilibrium sharing (identical to 4 decimals), which removed the AD
    loop it accelerated. Battery of record: ~9.3 min/seed under sharing
    (2026-09-07). History: `plans/20260802-0300h_canonical-hybrid-default_plan.md`.
- **Output**:
  - Figure 4 (six subfigures showing policy effects; paper:
    `../../Figures/Policyrelrecession.pdf`)
  - Figure 6 (HANK vs HA-model multiplier comparison, uses Step 4 results;
    paper: `../../Figures/HANK_multipliers.pdf` — this is why Step 4 runs
    before Step 5)
  - Table 6 (`FromPandemicCode/Tables/Baseline/Multiplier.tex` + `.ltx`, Step 5a)
  - Table 7 (`FromPandemicCode/Tables/Baseline/welfare6.tex`, Step 5b)
  - Table 8 (`Tables/Splurge0/welfare6_SplurgeComp.tex`; requires the Step 3
    robustness estimation)
  - The published QE-era outputs lived in `FromPandemicCode/Tables/CRRA2/`;
    the current two-phase flow writes to `Tables/Baseline/`.
- **Runtime** (dated claims; hardware-dependent):
  - Step 5a **current**: **45.5 min** at Baseline under the S2+ entry-point
    default tier (K=1/c96/ATI/tol 1e-2; measured 2026-07-27, epoch evidence
    doc); 110.8 min under the shipped-grid tier (K=3/c192/tol 1e-3).
  - Step 5a historical: ~22.5 h sequential a-indexed (do_all.py estimate,
    2026-06, pre-S2+/pre-cache); 9.45 h with forked-AD parallelism (2.4×,
    2026-06). m-indexed legacy (`HAFISCAL_QE_FIDELITY=1`) is ~25 min but
    biased — see above. Legacy single-phase `AggFiscalMAIN.py`: ~65 h
    (reported 2025-11; entry point retired 2026-04).
  - **2026-08-26 measured (dell, sharing default, doob, weighted-tail panel):** Step 5a
    Baseline **43 min** warm policy store / ~52 min cold (m5, +95 policy solves); Step 5b
    **9.4 min per seed** (the AD loops are skipped under sharing; the sampler's
    mixture-table cache removed ~6 min of per-child setup — 35 min/seed before it);
    as-corrected (own AD loop) ~13 min/seed. Candidate set = 5a + S=3 ≈ 1 h 10 per world.
    Step 1 ≈ 23 min (COBYQA battery, seeds concurrent), Step 2 ≈ 40 min (3 groups in
    parallel on one machine), Step 4 ≈ 10 min ⇒ full `do_all.py` ≈ 2 h warm / 2 h 15 cold.
  - Step 5b: **13.1 min steady-state** bare-default battery (measured
    2026-08-02 anchor5, all-12 pkls byte-identical to the certified
    canon; caches warm — first battery on a fresh cache ~42 min). Wall
    lineage 72 (all-HARK) -> 54 (hybrid) -> 13.1 (R1+R2 tables, R3
    base-share, R4b policy-solve cache); ~72 min under
    `HAFISCAL_WELFARE_ENGINE=hark`. See plans/20260802-1900h §5.

## Paper Table/Figure Provenance (Replication Mapping)

Step-by-step mapping from paper exhibits to the code that produces them
(merged from the former `do_all-README.md`, 2024-2025 QE era; re-verified
against the current tree 2026-06-11 — exact code line numbers from the QE-era
doc have drifted and are omitted; line references into **results text files**
are structural and kept).

**Note**: The optimization-based code should be deterministic, but small
environment differences can produce small numerical differences; differences in
Steps 1-2 propagate to all later steps.

### Tables

| Exhibit | Produced by | Output |
|---|---|---|
| Table 1 | `Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py` (Step 1) | `Target_AggMPCX_LiquWealth/Figures/MPC_WealthQuartiles_Table.tex` (the QE-era doc said `images/`; the code writes to `Figures/`) |
| Table 2, Panel A | Not generated in code (summarizes text parameters; values in `FromPandemicCode/EstimParameters.py`; exception: κ = ADelasticity in `FromPandemicCode/Parameters.py`) | — |
| Table 2, Panel B | Lines 1-3: `Code/Empirical/make_liquid_wealth.py`; lines 3-6 not generated (values in `EstimParameters.py`) | — |
| Table 3 (all panels) | Not generated in code (values in `FromPandemicCode/Parameters.py`) | — |
| Table 4, Panel A | Step 2 master results file | `Results/AllResults_CRRA_2.0_R_1.01.txt`, lines 4 & 10; 14 & 20; 24 & 30 |
| Table 4, Panel B | Line 1: `Code/Empirical/make_liquid_wealth.py`; line 2: master results file lines 5, 15, 25 | — |
| Table 5, Panel A | Line 1: `make_liquid_wealth.py`; lines 2-3: master results file lines 37 & 45 | — |
| Table 5, Panel B | Line 1: `make_liquid_wealth.py`; lines 2-3: master results file lines 38 & 44 | — |
| Table 6 | Step 5a (`AggFiscalMAIN_reduced.py --baseline` → `Output_Results.py`; QE-era: `AggFiscalMAIN.py`, retired) | `FromPandemicCode/Tables/Baseline/Multiplier.tex` (QE-era: `Tables/CRRA2/Multiplier.tex`) |
| Table 7 | Step 5b (`run_welfare6_parallel.py --baseline`; QE-era: `AggFiscalMAIN.py` → `Welfare.py`) | `FromPandemicCode/Tables/Baseline/welfare6.tex` (QE-era: `Tables/CRRA2/welfare6.tex`) |
| Table 8 | Step 5 with Step-3 (Splurge=0) results (`Welfare.py`) | `FromPandemicCode/Tables/Splurge0/welfare6_SplurgeComp.tex` |
| Table 9 | Parametrization table — no computational results | — |

The master results file `Results/AllResults_CRRA_2.0_R_1.01.txt` is written by
`FromPandemicCode/EstimAggFiscalMAIN.py` (Step 2); values from it are manually
transcribed into the paper tables.

### Figures

| Exhibit | Produced by | Output |
|---|---|---|
| Figure 1 | `Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py` (Step 1) | `../../Figures/splurge_estimation.pdf` |
| Figure 2 | `FromPandemicCode/CreateLPfig.py` (Step 2 post-processing) | `FromPandemicCode/LorenzPoints_CRRA_2.0_R_1.01.pdf` |
| Figure 3(a) | QE-era: `CreateMPCfig.py` (since removed from the tree); current Step 2 runs `CreateIMPCfig.py` for the IMPC panels | `../../Figures/untargetedMoments.pdf` |
| Figure 3(b) | `FromPandemicCode/EvalConsDropUponUILeave.py` | `../../Figures/untargetedMoments.pdf` |
| Figure 4 | Step 5a → `Output_Results.py` (six subfigures; QE-era: `AggFiscalMAIN.py`) | `../../Figures/Policyrelrecession.pdf` |
| Figure 5 | `FromPandemicCode/HA-Fiscal-HANK-SAM-to-python.py` (Step 4; six panels a-f) | `Figures/HANK_IRFs.tex` composing `FromPandemicCode/Figures/HANK_{transfer,UI,tax}_{IRF,multiplier}.pdf` (the root `Figures/HANK_IRFs.pdf` is an orphaned 2026-03 artifact) |
| Figure 6 | Step 5 → `Output_Results.py`, using Step-4 results (QE-era: `AggFiscalMAIN.py`) | `../../Figures/HANK_multipliers.pdf` |

**Data reference**: Board of Governors of the Federal Reserve System. 2007.
Survey of Consumer Finances (SCF), 2004 Summary Extract Public Data Dataset.
<https://www.federalreserve.gov/econres/scf_2004.htm>

## Directory Structure

```
Code/HA-Models/                        # (selected entries)
├── do_all.py                          # Main pipeline script
├── do_all_reduced.py                  # Reduced-scale pipeline for fast validation
├── reproduce_min.py                   # Quick validation script
├── Results/                           # Text files with numerical results
│   └── AllResults_CRRA_2.0_R_1.01.txt
├── Results_canonical/                 # Canonical/pinned results snapshots
├── Target_AggMPCX_LiquWealth/        # Step 1: Estimate splurge
│   ├── Estimation_BetaNablaSplurge.py
│   └── ...
├── FromPandemicCode/                  # Steps 2-5: Main analysis
│   ├── EstimAggFiscalMAIN.py         # Step 2: Estimation
│   ├── AggFiscalMAIN_reduced.py      # Step 5a: TM multipliers (AggFiscalMAIN.py retired 2026-04)
│   ├── run_welfare6_parallel.py      # Step 5b: MC welfare-6 (parallel driver)
│   ├── AggFiscalModel.py             # Model class definitions
│   ├── EstimParameters.py            # Calibrated parameters
│   ├── CreateLPfig.py                # Generate Figure 2
│   ├── CreateIMPCfig.py              # Generate Figure 3
│   ├── Output_Results.py             # Generate Figure 4, Table 6
│   ├── Welfare.py                    # Generate Figure 6 inputs, Table 7
│   ├── FiscalTools.py                # Utility functions
│   ├── tm_methods.py                 # Transition-matrix methods
│   ├── Figures/                      # Generated figure files (per parametrization)
│   │   ├── Baseline/                 # Current production
│   │   ├── CRRA2_PVSame/             # Equal present value
│   │   └── ...                       # Other parametrizations
│   └── Tables/                       # Generated table files (per parametrization)
│       ├── Baseline/                 # Current production
│       ├── CRRA2/                    # QE-era published location
│       └── ...                       # Other parametrizations
├── solution_cache/                    # Caches (data gitignored): the shared solved-POLICY store
│                                      #   (policy_store.py — every cold household rule solved once,
│                                      #   guarded HITs; plans_local/20260824-1530h) + the AD-converged
│                                      #   solution caches
├── jax_mc_speedup/, jax_tm_mult/      # JAX acceleration kernels + tests
├── dolo_plus_validation/              # Dolo-plus YAML model validation
├── experiments/, scripts/             # Diagnostics and helper scripts
└── diagnostics_archive/, hark_migration_archive/,
    welfare6_diagnostics_archive/      # Archived diagnostics (historical)
```

## Key Python Modules

### Model Definition

- **`AggFiscalModel.py`**: Core model classes
  - `AggFiscalType`: Individual agent type with fiscal parameters
  - `AggregateDemandEconomy`: Market with aggregate demand externality
- **`ConsMarkovModel.py`**: Consumer model with Markov unemployment transitions
- **`EstimAggFiscalModel.py`**: Estimation-specific model variants

### Estimation and Calibration

- **`EstimAggFiscalMAIN.py`**: Main estimation script (Step 2)
- **`EstimParameters.py`**: Calibrated parameter values
- **`EstimSetupEconomy.py`**: Economy setup for estimation

### Policy Analysis

- **`AggFiscalMAIN_reduced.py`**: Step 5a entry point (TM multipliers; with
  `--baseline` runs the paper-scale Baseline parametrization). The former
  main entry point `AggFiscalMAIN.py` was retired at commit `c7e566d9` (2026-04-08).
- **`run_welfare6_parallel.py`**: Step 5b entry point (MC welfare-6, parallel driver)
- **`Output_Results.py`**: Generate policy comparison results and figures
- **`Welfare.py`**: Welfare calculations and comparisons

### Utilities

- **`FiscalTools.py`**: Helper functions for fiscal policy analysis
- **`Clean_Folders.py`**: Cleanup utility for the RETIRED flag-driven robustness scheme — now exits with a retirement notice (see note below)
- **`CreateLPfig.py`**: Generate lifecycle profile figures
- **`CreateIMPCfig.py`**: Generate impulse response figures

### Intelligent Cleanup (SST Pattern) — RETIRED

`Clean_Folders.py` implemented flag-driven cleanup by parsing `Run_*_robustness`
flags from `AggFiscalMAIN.py` (the then-SST) and deleting large files in the
`Figures/` directories of disabled robustness checks.

> **Retired (owner ruling 2026-06-12)**: `AggFiscalMAIN.py` was retired at
> commit `c7e566d9` (2026-04) and its successor `AggFiscalMAIN_reduced.py`
> carries no `Run_*_robustness` flags — robustness/sensitivity runs are now
> parametrization-driven (e.g. `welfare6_scenario.py --parametrization CRRA1`).
> `Clean_Folders.py` now points at `AggFiscalMAIN_reduced.py`, finds no flags,
> prints a retirement notice, and exits cleanly without deleting anything.
> Delete unwanted `Figures/<param>/` directories directly if needed.
> Historical design docs: `CLEANUP-SST-PATTERN.md`, `CLEANUP-USAGE.md`.

## Model Features

### Three Education Groups
The model includes separate agent types for:

- **Dropout** (<12 years education)
- **HighSchool** (12 years education)  
- **College** (>12 years education)

Each group has:

- Different income processes
- Different unemployment risks
- Different unemployment benefit replacement rates
- Estimated discount factor distributions

### Key Economic Features

- **Heterogeneous agents**: Idiosyncratic income and unemployment risk
- **Incomplete markets**: Agents cannot fully insure against shocks
- **Liquid wealth**: Excludes "splurge" portion of assets
- **Markov unemployment**: employed + unemployment-duration states (u1Q, u2Q with regular benefits, then the extension states, then no benefits): 7 micro states in both worlds (`calendar` encoding + the paper's `window` policy; owner 2026-08-28 "window everywhere"), 6 under `calendar` + the `history` policy (the robustness-appendix arm), 4 under `legacy` (the paper's own code, reference arm) — see Step 5 above
- **Aggregate demand**: Output responds to aggregate consumption
- **Fiscal policies**: UI extensions, transfers, tax cuts

### Model Parametrizations

The code supports multiple parametrizations (historically controlled by flags in
the retired `AggFiscalMAIN.py`; now selected via `AggFiscalMAIN_reduced.py`
CLI flags / `Run_Dict` and the welfare drivers' `--parametrization`):

| Parametrization | CRRA | Interest Rate | Use Case |
|-----------------|------|---------------|----------|
| **CRRA2** (Baseline) | 2.0 | 1.01 | Main results |
| **CRRA2_PVSame** | 2.0 | 1.01 | Equal present value comparison |
| **Splurge0** | 2.0 | 1.01 | Zero splurge robustness |
| **CRRA1** | 1.0 | 1.01 | Low risk aversion |
| **CRRA3** | 3.0 | 1.01 | High risk aversion |
| **Rfree_1005** | 2.0 | 1.005 | Low interest rate |
| **Rfree_1015** | 2.0 | 1.015 | High interest rate |
| **ADElas** | 2.0 | 1.01 | Alternative AD elasticity |
| **LowerUBnoB** | 2.0 | 1.01 | Lower UB, no benefits cap |

## Dependencies

### Required Python Packages

Pinned in the repo-root `pyproject.toml` (authoritative); highlights:

- **econ-ark (HARK)** — 0.17.x, pinned via `[tool.uv.sources]` (git ref or
  local editable checkout depending on branch)
- **numpy** >= 1.24, < 2 - Numerical computing (numpy 2.x not supported)
- **scipy** - Scientific computing and optimization
- **matplotlib** - Plotting
- **pandas** - Data manipulation
- **numba** >= 0.57 - JIT compilation (constrains Python to 3.10/3.11)
- **sequence-jacobian** == 1.0.0 - Sequence space Jacobian methods (Step 4)

### Installation

```bash
# Using UV (recommended)
cd ../..  # Return to repository root
uv sync

# Or using conda
conda env create -f environment.yml
conda activate HAFiscal
```

## Output Files

See **Paper Table/Figure Provenance** above for the authoritative
exhibit-by-exhibit mapping. Summary:

### Figures
Working figures are saved in `FromPandemicCode/Figures/` organized by
parametrization (current production: `Figures/Baseline/`); the paper's figure
files live in the repo-root `Figures/` directory:

- **Figure 1**: `../../Figures/splurge_estimation.pdf`
- **Figure 2**: `FromPandemicCode/LorenzPoints_CRRA_2.0_R_1.01.pdf`
- **Figure 3**: `../../Figures/untargetedMoments.pdf` (+ `FromPandemicCode/IMPCs_*.pdf`)
- **Figure 4**: `../../Figures/Policyrelrecession.pdf` (six subfigures from `Output_Results.py`)
- **Figure 5**: `Figures/HANK_IRFs.tex` → `FromPandemicCode/Figures/HANK_{transfer,UI,tax}_{IRF,multiplier}.pdf` (HANK-SAM comparisons)
- **Figure 6**: `../../Figures/HANK_multipliers.pdf` (HANK vs HA multipliers)

### Tables
Generated LaTeX tables are saved in `FromPandemicCode/Tables/` organized by
parametrization (current production: `Tables/Baseline/`; QE-era published
location was `Tables/CRRA2/`):

- **Table 1**: `Target_AggMPCX_LiquWealth/Figures/MPC_WealthQuartiles_Table.tex`
- **Table 6**: `Tables/Baseline/Multiplier.tex` (fiscal multipliers, Step 5a)
- **Table 7**: `Tables/Baseline/welfare6.tex` (welfare comparisons, Step 5b)
- **Table 8**: `Tables/Splurge0/welfare6_SplurgeComp.tex` (splurge-robustness comparison)

### Results Files
Numerical results are written to text files in `Results/`:

- **AllResults_CRRA_2.0_R_1.01.txt**: Main estimation results (written by `EstimAggFiscalMAIN.py`)
- Values from these files are manually transcribed into paper tables

## Running Time Estimates

Runtime claims on record, with dates (older reference hardware: 8-core CPU,
16GB RAM, NVMe SSD; `do_all.py` budget figures set 2026-02 unless noted):

| Task | Script | Runtime claims (dated) |
|------|--------|------------------------|
| **Complete Pipeline** | `do_all.py` | 4-5 days (2025-11) |
| **Minimal Validation** | `reproduce_min.py` | ~1 hour (2025-11) |
| Step 1 | `Estimation_BetaNablaSplurge.py` | ~20 min (2025-11); 30 min budget (2026-02) |
| Step 2 | `EstimAggFiscalMAIN.py` | ~21 h (2025-11); ~48 h budget (2026-02) |
| Step 3 | `EstimAggFiscalMAIN.py` (Splurge=0) | same as Step 2 |
| Step 4 | `HA-Fiscal-HANK-SAM*.py` | ~13 min + 13 s (2026-08-09 rebuild); ~64 min (2026-08-03); ~12 h budget (0.14-era) |
| Step 5a | `AggFiscalMAIN_reduced.py --baseline` (a-indexed) | ~22.5 h sequential (2026-06); 9.45 h measured forked-AD (2026-06); ~25 min m-indexed legacy (biased; `HAFISCAL_QE_FIDELITY=1`) |
| Step 5b | `run_welfare6_parallel.py --baseline` | ~1 h wall parallel; ~6 h serial (2026-04) |
| Step 5 (legacy) | `AggFiscalMAIN.py` (retired 2026-04) | ~65 h (2025-11) |

Actual runtimes vary significantly based on hardware. See `../../reproduce/benchmarks/` for detailed timing information.

## Implementation Details

### Liquid Wealth Calculation
Under the CDC (consumer-doing-consultation) interpretation, the household's
post-splurge end-of-period assets are tracked directly by `state_now["aLvl"]`:

```python
liquid_wealth = ThisType.state_now["aLvl"]
```

(Prior to the BUG-034 fix this was written as `(1 - ThisType.Splurge) * ThisType.state_now["aLvl"]`,
which double-subtracted splurge under CDC dynamics. The CDC asset rule already
deducts the splurge inside `get_poststates`, so the multiplication was incorrect.)

### Agent Type Organization
Agent types are organized in arrays:

```python
# For each education group, multiple discount factors
num_agents = num_education_types * DiscFacCount
# Example: 3 education types × 7 discount factors = 21 agent types
```

### Path Handling
Scripts detect their execution context and adjust paths:

```python
if os.path.basename(os.getcwd()) == "FromPandemicCode":
    # Running from within FromPandemicCode/
    results_dir = "../Results/"
else:
    # Running from repository root or HA-Models/
    results_dir = "Code/HA-Models/Results/"
```

### Deterministic Results
Optimization routines use fixed random seeds for reproducibility, but small environmental differences (BLAS library, compiler optimizations) may cause minor numerical variations.

### Default Tail Numerics (2026-07-23)

Above the solve grid's top knot, every consumption function is extrapolated as
the perfect-foresight line minus a power-law gap:
`c(m) = MPCmin*(m + h) - gap(m)`, with `MPCmin` and human wealth `h` analytical
from primitives and `gap` a power law in the shifted abscissa `(m + h)`. One
scalar is estimated per state-slice: the exponent Q, measured by two log-log
secants over the top three solved knots (the attach uses Q2, the most local
secant; Q2−Q1 is a drift advisory only, never a second parameter). Kesten/theory
roots from primitives are diagnostic context only — never in the attach.
Preconditions (also default): the per-group solve-grid top `K*hbar` at K=3
(≈467/551/591 for Dropout/HS/College) with count basis 192, density-held
(`grid_sizing.solve_grid_count`).

Four named regimes select the tail behavior:

| regime | selection | tail |
|--------|-----------|------|
| **default** | (nothing to set) | powerlaw, measured two-secant Q, K·h̄ top, count 192 (`HAFISCAL_PF_DECAY_EXTRAP=1`, `HAFISCAL_PF_DECAY_Q=measured`) |
| **as-corrected** | `HAFISCAL_WORLD=as-corrected` | powerlaw fix only, no improvements: slope-fitted Q at the legacy top-40 / count-48 grid (`HAFISCAL_PF_DECAY_Q=slope`) |
| **exp-diagnostic** | `HAFISCAL_PF_DECAY_EXTRAP=exp` | the PR-3-era exponential form; diagnostic opt-out for T-cascade / RECONCILED-002 reproduction |
| **as-shipped-QE-repro** | `HAFISCAL_PF_DECAY_EXTRAP=0` | the published naive-linear extrapolation; reserved for QE reproduction only |

Certification of record (2026-07-23 bridge test vs a 50,000-top truth solve):
the constant measured-Q tail from the production grid top projects `c` to
≤6e-5 (subcritical atoms) / ≤3e-4 (GIC-cap atom) relative error out to 75×
the grid top. Machine source of truth for the settings:
`config/catalog.py` (`pf_decay_extrap`, `pf_decay_q_measured`); flag details in
`docs/ENV_FLAGS.md`; evidence and derivations in
`conclusions_private/2026-07-23_solve_grid_count_convergence.md`,
`plans/20260723_measured-q-tail-default-finalization_plan.md`, and
`RECONCILED_private/RECONCILED-002_pf-decay-exp-vs-powerlaw-form.md`.

## Troubleshooting

### Import Errors

```bash
# Reinstall the pinned environment (do NOT `pip install econ-ark --upgrade`:
# HARK is pinned to a specific 0.17.x ref in pyproject.toml)
cd ../..
uv sync
```

### Memory Issues

```bash
# Reduce number of simulated agents in EstimParameters.py
AgentCount = 5000  # Default: 10000

# Or increase system swap space
```

### Long Run Times

```bash
# Use reduced version for faster testing
python AggFiscalMAIN_reduced.py

# Or run minimal validation
python reproduce_min.py
```

### Missing Output Files

```bash
# Make sure you've run prior steps
python do_all.py  # Runs all steps in order

# Or run steps individually
cd Target_AggMPCX_LiquWealth
python Estimation_BetaNablaSplurge.py
cd ../FromPandemicCode
python EstimAggFiscalMAIN.py
HAFISCAL_TM_A_INDEXED=1 python AggFiscalMAIN_reduced.py --baseline
python run_welfare6_parallel.py --baseline --table-dir Tables/Baseline
```

## Additional Documentation

- **`do_all-README.md`**: pointer stub — its table/figure provenance content
  was merged into the **Paper Table/Figure Provenance** section above (2026-06-11)
- **`../../README.md`**: Main replication documentation
- **`../../ARCHITECTURE.md`**: Human-facing repo navigation / architecture overview
- **`../../docs/`**: Technical documentation
- **`../../reproduce/README.md`**: Reproduction scripts documentation

## References

- **Paper**: Carroll, Crawley, Du, Frankovic, Tretvoll (2025). "Welfare and Spending Effects of Consumption Stimulus Policies"
- **HARK Documentation**: <https://hark.readthedocs.io/>
- **Econ-ARK**: <https://econ-ark.org/>

---

**Last Updated**: 2026-06-11 (canonical pipeline doc; absorbed `do_all-README.md` provenance mapping; verified against `do_all.py`)  
**Version**: 3.0  
**Contact**: See paper for author contact information

## Compute queue (`runq.py`, 2026-08-28)

Launch every multiplier program, welfare battery and Step-2 estimation through the per-machine queue so arms wait for a
slot instead of contending (two 5a programs on dell ran ~3× slower EACH on 2026-08-27/28):

```bash
python Code/HA-Models/runq.py --class 5a -- python AggFiscalMAIN_reduced.py --baseline
python Code/HA-Models/runq.py --class battery -- python run_welfare6_parallel.py --baseline --seed-offset 0 ...
python Code/HA-Models/runq.py status            # slots, holders, waiters on this host
python Code/HA-Models/eta.py --plan 5a:2,battery:6   # expected wall from the launcher stamps
source Code/HA-Models/launch_helpers.sh           # run5a / runw6 / runs2_groups wrappers for launchers
```
Capacity per host lives in `runq.CAPACITY` (dell: one 5a, two batteries, one Step 2); `HAFISCAL_RUNQ=0` bypasses;
`HAFISCAL_RUNQ_SLOTS_<CLASS>` overrides. Flags: `docs/ENV_FLAGS.md`.

