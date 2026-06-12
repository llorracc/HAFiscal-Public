# diagnostics_archive

Closed-case diagnostic, parity, and tier-validation scripts from the **MC-vs-TM /
Harmenberg-Doob / discount-factor-estimation investigation** (BUG-015 … BUG-051,
the D-1…D-14 multiplier-residual hunt, the shuffle/CRN work, the Harmenberg
neutral-measure & Doob tier sweeps). **Archived 2026-06-06 (Phase R, tier 2)** to
declutter `Code/HA-Models/FromPandemicCode/`.

These are **not** part of the reproduction pipeline and nothing live imports them
— see the verification below. The investigations they served are concluded; their
conclusions live in `conclusions_private/` and `BUGS_private/`.

## What's here (74 files)
- `diag_*` (51) — per-bug / per-phase diagnostics (D-12…D-14 multiplier residual,
  pLvl/permgrofac/shuffle/warmup/cratio, QE-comparison, local-minima, etc.)
- `harmenberg_*` (18) — Harmenberg neutral-measure & Doob tier sweeps, drift/init
  tests, grid sweep, mc-vs-tm 1-agent checks. (The **live** anchors
  `harmenberg_doob_tier1{,_esc}.py` stay in `FromPandemicCode/`.)
- `parity_*` (4) — single-policy / single-type parity checks. (`parity_solo_pol_linear.py`
  stays — it's a shared helper still imported by the test suite.)
- `welfare6_tm_repagent.py` — superseded methodology variant (production uses
  `welfare6_tm_aggregate` + the 5D kernel / MC+CRN+IS).

> **Restored 2026-06-06 (adversarial review):** `welfare6_aggregator_stratified.py`
> was originally archived here but is referenced by four documented run-instructions
> in `conclusions_private/` (Baseline-5×-seeds aggregation, via `sys.path.insert`).
> Restored to `FromPandemicCode/` as the conservative call — its supersession is
> contestable and it has documented consumers.

## Verification (Phase R tier 2)
A reverse-import-graph reachability analysis protected the closure of all
production/canonical/active roots (`do_all`, `AggFiscalMAIN`, the canonical welfare
core, the comparison drivers, the Doob anchors, the JAX production drivers). The
archived set is the strict fixpoint with **no file outside it importing any member**
and **no subprocess/string reference** from a production root. An independent
`grep` dangling-check confirmed 0 broken references (and caught `diag_welfare6_se`,
which a live `compute_welfare6_se_table.py` imports — so it was **kept**, not archived).

## Restoring one
`git mv diagnostics_archive/<file> ../FromPandemicCode/` — these scripts import
`FromPandemicCode` siblings and assume that dir as cwd / `sys.path`, so they must
live there to run.

## Batch J 2026-06-11 (doc-rationalization, plans/20260611_family-manifests-and-archival-sweep.md)
JAX-AD Baseline-bias diagnosis iteration history (May 2026), superseded by `jax_mc_ad_bl_diagnose8_replay_v4.py`
(final, KEPT live) and the productionized replay path (`jax_mc_replay_production.py`): `jax_mc_ad_bl_diagnose.py`,
`diagnose2`, `diagnose3_fp64`, `diagnose4_newborn`, `diagnose5_tage`, `diagnose6_combined` + co-moved
`jax_mc_ad_v2.py` (sole importer was diagnose4). `diagnose7` KEPT (conclusions-doc consumer). Quadruple-bar
gated (zero reverse imports incl. tests; zero active-doc consumers; successor documented; no HARVEST).
Evidence: Code/HA-Models/docs/FILE_FAMILIES.md. Restore: `git mv` back; scripts assume FromPandemicCode/ cwd.

## Batch M 2026-06-11 (doc-rationalization, plans/20260611_family-manifests-and-archival-sweep.md)
Closed validation campaigns + one-off diagnostics, quadruple-bar gated (zero reverse imports incl. tests;
campaign closures cited in plans/INDEX.md + conclusions_private/; no HARVEST flags): the phase-validation
drivers phase0_convergence_validation, phase1_3types_validation, phase1_pertype_diag, phase2_21types_validation,
phase3_recession_avg_validation, phase4_baseline_params_validation, phase5_pipeline_test, phase01_P_vs_Q_comparison,
phase2_percohort_cdc_vs_esc; diagnostics bench_batch_speedup, diag_comprehensive_tm_mc (stale for 6-state
encoding — IndexError at recessionTaxCut setup, superseded by welfare6_tm_vs_mc.py driver), diagnose_burnin,
diagnose_cons_gap, diagnose_cons_gap2, diagnose_mc_convergence, diagnose_tm_ui, investigate_recession_check,
trace_minimal, trace_minimal2, trace_period1_tm_init_vs_tm_operator_composer, trace_unemployment; one-off
drivers run_full_tm_ad, run_full_tm_timing, run_reduced_tm_a_indexed; and launch_track_a_prime.sh — the
FIRST .sh in this archive. test_cons_gap_fix.py KEPT live (imports production modules, not the subjects).
Evidence: Code/HA-Models/docs/FILE_FAMILIES.md. Restore: `git mv` back; scripts assume FromPandemicCode/ cwd.
