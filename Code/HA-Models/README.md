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
> `mc` = the reliable stratified-**MC** cross-check (all bug fixes ON, aMax=1300;
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

# Step 2: Estimate discount factor distributions (~21-48 hours; see Step 2)
cd FromPandemicCode
python EstimAggFiscalMAIN.py

# Step 5a: TM multipliers (a-indexed canonical; ~22.5 h sequential)
cd FromPandemicCode
HAFISCAL_TM_A_INDEXED=1 python AggFiscalMAIN_reduced.py --baseline

# Step 5b: MC welfare-6 (parallel driver; ~1 h wall)
cd FromPandemicCode
python run_welfare6_parallel.py --baseline --table-dir Tables/Baseline
```

(The old single-phase Step-5 entry point `AggFiscalMAIN.py` was retired at
commit `c7e566d9`, 2026-04-08; see Step 5 below.)

## QE-Frozen Results and the Candidate Workflow

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
- **Runtime**: ~20 minutes (reported 2025-11); `do_all.py` budgets 30 min (2026-02)

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

- **Scripts**:
  - `HA-Fiscal-HANK-SAM.py` - Compute Jacobian matrices
  - `HA-Fiscal-HANK-SAM-to-python.py` - Run experiments
- **Purpose**: Robustness check using Sequence Space Jacobian methods
- **Output**:
  - Figure 5 (HANK-SAM policy comparisons, `../../Figures/HANK_IRFs.pdf`)
  - Jacobian matrices for dashboard: `HA_Fiscal_Jacs.obj`, `HA_Fiscal_Jacs_UI_extend_real.obj`
- **Runtime**: conflicting estimates on record — ~1 hour total (reported
  2025-11); `do_all.py` budgets ~12 h for the Jacobian computation plus ~1 h
  for the experiments (estimates set 2026-02). Jacobian wall time is strongly
  hardware-dependent.

### Step 5: Compare Fiscal Stimulus Policies

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
  - Legacy single-phase `AggFiscalMAIN.py`: ~65 hours (reported 2025-11; entry point retired 2026-04)
  - Step 5a: ~22.5 h sequential a-indexed + bug_fix encoding (do_all.py
    estimate, 2026-06); measured 9.45 h with forked-AD parallelism (2.4×,
    2026-06). m-indexed legacy (`HAFISCAL_QE_FIDELITY=1`) is ~50× faster
    (~25 min) but biased — see above.
  - Step 5b: ~1 h wall with the parallel driver (~6 h serial
    `run_hybrid_welfare6.py` equivalent; 2026-04)

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
| Figure 5 | `FromPandemicCode/HA-Fiscal-HANK-SAM-to-python.py` (Step 4; six panels a-f) | `../../Figures/HANK_IRFs.pdf` |
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
├── solution_cache/                    # Opt-in AD-converged solution cache (gitignored)
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
- **Markov unemployment**: Two states (employed/unemployed) with transitions
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
- **Figure 5**: `../../Figures/HANK_IRFs.pdf` (HANK-SAM comparisons)
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
| Step 4 | `HA-Fiscal-HANK-SAM*.py` | ~1 h (2025-11); ~12 h Jacobians + ~1 h experiments budget (2026-02) |
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
