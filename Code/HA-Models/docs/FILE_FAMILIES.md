# FILE_FAMILIES.md — duplicate-family manifest for `Code/HA-Models/`

**Purpose:** the per-family file manifest mandated by
`plans/20260611_family-manifests-and-archival-sweep.md` (Phase 0 deliverable, updated with
Phase-1 gate evidence and the executed Phase-2 Tier-1 moves). `FromPandemicCode/` accumulated
~278 .py files of which ~13 are production core; this document lets a reviewer tell canonical
from exploratory for every member of the duplicate families (welfare6, jax_mc/jax_solver,
phase*, harmenberg, diag/trace/run singletons, test_*), with evidence per row.

**Date:** 2026-06-11 · **Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_doc-rationalization`
· **Assembled at:** `b105fe7b` · **Move commits:** `4bfaa670` (batch W: 3 welfare6 files →
`welfare6_diagnostics_archive/`), `430a0a5b` (batch J: 7 jax files → `diagnostics_archive/`),
`b105fe7b` (batch M: 25 misc files → `diagnostics_archive/`).

**Policy (owner ruling 2026-06-11, binding): certainty-tiered, harvest-first.** Only Tier-1
files move — those passing the full quadruple bar: (a) superseded-by-documented-decision OR
iteration-history-with-named-successor; (b) reverse-import closure clean over `Code/**`
including tests; (c) doc-consumer grep clean over `conclusions_private/`, ACTIVE+STALLED
plans, `CLAUDE.md`, all `README*` (any blocking-class hit auto-demotes to keep — this gate's
absence caused the `welfare6_aggregator_stratified` archive-then-restore mistake); (d) no
`HARVEST` flag (files embodying a unique technique stay until the technique is lifted into
working tools or docs). Everything failing any bar **stays in place as Tier-2 with its
manifest row — that is the normal outcome, not a failure**. Files passing the full bar moved
unattended ("trust-the-bar"), one revertible commit per batch.

**Role vocabulary** (per row, post-Phase-1):

- **production** — reached by `do_all.py` / documented CLI / CLAUDE.md-documented entry; claim cites evidence.
- **live-support** — imported (or doc-glob-covered, or env-flag/registry-coupled) by production or by an active driver/test; not independently runnable as a paper step.
- **closed-candidate** — subject campaign closed; further split by verdict: `MOVED → <archive>/ (2026-06-11)` (passed all four bars) or `kept Tier-2 (<blocking bar>)`.
- **unknown** — zero consumers and zero closure evidence; kept by default (a file cannot Tier-1-move on absence of evidence).

## Summary

| family | files | production | live-support | kept Tier-2 | MOVED Tier-1 | HARVEST flags |
|---|---|---|---|---|---|---|
| §1 welfare6* (+ SE-trio helpers) | 32 | 5 | 12 | 12 | 3 → `welfare6_diagnostics_archive/` | 7 (+1 lite) |
| §2 jax_mc_* + jax_solver_* (FPC) | 72 | 3 | 32 | 30 | 7 → `diagnostics_archive/` | 2 |
| §3 phase* | 19 | 0 | 8 | 2 | 9 → `diagnostics_archive/` | 2 (+1 lite) |
| §4 harmenberg_* (live remnant) | 2 | 0 | 2 | 0 | 0 | 1 (refactor-target) |
| §5 misc singletons (diag/trace/…) | 23 (2 cross-listed) | 0 | 1 | 8 | 12 → `diagnostics_archive/` | 2 (+2 lite) |
| §6 run_* + *.sh | 13 (2 cross-listed) | 1 | 2 | 4 | 4 → `diagnostics_archive/` | 0 (+3 lite) |
| §7 test_* (catalog summary) | 76 | — (catalog-only this round) | — | — | 0 | 0 |
| §8a jax_mc_speedup/ | 11 | 0 | 8 | 3 | 0 | 0 |
| §8b jax_tm_mult/ | 3 | 0 | 0 | 3 | 0 | 0 |
| **TOTAL (unique)** | **247** | **9** | **65** | **62** | **35** | **14 full + 7 lite** |

Cross-listing: 4 files appear in two family tables and are counted once, under welfare6 —
`run_welfare6_parallel.py` + `run_hybrid_welfare6.py` (also §6), `compute_welfare6_se_table.py`
+ `diag_welfare6_se.py` (also §5). Caution anchor outside all families:
**`estim_phase2_tm_a.py` is PRODUCTION** (TM-a Step-2 estimator; imported by
`measure_gicfactor_tradeoff.py:57`, `_tm_a_backfill.py:83`, `mc_tm_dist_eval.py:73`;
subprocessed by `adaptive_grid_tm.py:99`; orchestrated by `reestimate_bug053_orchestrate.py`)
— despite the `phase2` infix it must NOT travel with the phase* family.

Pre-existing archives (precedent, not re-listed per row): `diagnostics_archive/` (74 .py before
this sweep, now 105 .py + 1 .sh), `welfare6_diagnostics_archive/` (22 before, now 25),
`hark_migration_archive/` (18). Each has a README with restore paths.

---

## §1 — welfare6* family (+ named helpers) — 32 files

Paths: `FPC/` = `Code/HA-Models/FromPandemicCode/`, `HM/` = `Code/HA-Models/`.
Phase-0 manifest updated with Phase-1 gate evidence (16 candidates gated — 12 closed-candidates
+ 4 unknowns, every hit itemized and classified). Family context:

1. **Production core:** `welfare6_scenario.py` (canonical MC welfare engine) +
   `run_welfare6_parallel.py` (do_all.py Step-5b) + `run_hybrid_welfare6.py` (serial CRN
   reference) + `welfare6_tm_joint5d{,_baseline}.py` (the TaxCut TM-a backup kernel + driver).
2. **2026-06-10 deprecation scope** (`conclusions_private/2026-06-10_welfare_method_unified_MC.md`):
   MC+CRN+stratified-shuffle is canonical for ALL welfare cells; `welfare6_tm.py` `bucket`
   method deprecated-for-welfare, `stratified` BROKEN for Check, its AD cells FAKE; IS pathway
   NOT used (+10% ui_rec bias); the only working TM-a welfare cross-check = joint-5D for TaxCut;
   ui_norec excluded everywhere (0/0 structural).
3. **Deprecation ≠ archival-certainty:** `welfare6_tm_bucket/_stratified` are imported
   UNCONDITIONALLY by `welfare6_tm.py` (lines 920/909), which feeds the ACTIVE Phase-C.1
   cross-check driver `HM/welfare6_tm_vs_mc.py` — all live-support.
4. **Seed-knowledge corrections (verified):** `welfare6_tm_aggregate.py` + `welfare6_tm_make_tex.py`
   have ZERO consumers (seed claimed production — contradicted); `welfare6_tm_joint5d_batch.py`
   is validation-harness-only; `welfare6_hybrid_table.py` survives as the BUG-051 regime-guard
   library, not as the superseded hybrid-table CLI.

| file | role (post Phase-1) | evidence | preservation-value |
|---|---|---|---|
| FPC/welfare6_scenario.py | **production** | do_all Step-5b engine: launched per-scenario by run_welfare6_parallel.py; CLAUDE.md documents its CLI (`--solve-workers`, cohort-parallel, solution cache); `build_and_solve` imported by welfare6_tm_joint5d_baseline.py:72, HM/welfare6_check_rec_bucketed5d.py:33, HM/welfare6_reconcile_sweep.py:108, HM/test_welfare6_ergodic_init.py + ~60 jax_mc/validate/bench harnesses; INDEX rows 54/110; last commit 2026-06-08 | Canonical; `build_and_solve` is the family's single solve entry point — keep |
| FPC/run_welfare6_parallel.py | **production** | do_all.py:189-196 ("5b: MC welfare-6 … `python run_welfare6_parallel.py --baseline`"); CLAUDE.md; reproduce/run-manifests/comp_full_20260421-1911 recipe; `welfare6_mc`/`ALL_SCENARIOS` imported by HM/welfare6_tm_vs_mc.py:47; 20+ code refs; 2026-06-02 | Canonical parallel driver; bit-identical-to-serial validation contract in docstring — keep |
| FPC/run_hybrid_welfare6.py | **production** | do_all_reduced.py:179-182; FPC/run_all.py Pass-2; reproduce/reproduce_computed_TM_and_MC.sh:180 ("Canonical CRN-paired welfare-6"); welfare6_scenario.py must mirror it bit-for-bit (docstring contract); BUG-052 ergodic-default fix touched it 2026-06-08 | Serial reference implementation backing the parallel driver's correctness claim — keep |
| FPC/welfare6_tm.py | live-support | TM-arm welfare driver; output pickle is the `--tm-pickle` input of ACTIVE Phase-C.1 driver HM/welfare6_tm_vs_mc.py; used in 2026-06-10 HS_Only cascade; BUT 2026-06-10 doc: bucket deprecated-for-welfare, stratified BROKEN, AD cells FAKE; imported by welfare6_tm_aggregate/_stratified, HM/welfare6_reconcile_sweep; 2026-05-19 | Embodies the b3-math analytical welfare formula (2026-05-09_welfare6_tm_a_option_b3_math.md); TM-arm of the cross-check — keep |
| FPC/welfare6_tm_bucket.py | live-support | Imported UNCONDITIONALLY by welfare6_tm.py:920 (`cells_bucket` is its "primary" output) → blocked from closure despite 2026-06-10 method-deprecation for welfare (φ(pLvl)-bucketing bias); 2026-05-10 | Bucket-aware Check-progressivity aggregation; method documented in conclusions; no independent harvest while import stands |
| FPC/welfare6_tm_stratified.py | live-support | Imported UNCONDITIONALLY by welfare6_tm.py:909 → blocked; method declared BROKEN for Check (check_norec=429) by 2026-06-10 doc; 2026-05-10 | Per-Markov-state stratified rep-agent formula (Path B); results superseded; keep only because of the import |
| FPC/welfare6_tm_aggregate.py | closed-candidate in substance — **kept Tier-2 (gate-3 class-(i): stale archive-README stays-claim)** | Phase-1 resolved the unknown: May-10-era post-processor of welfare6_tm pickles using the INDEP-STATE (marginal) aggregation judged "2× too high" (2026-05-10 FINAL; "kept for documentation" ×2). Gate 1 CLEAN (0 importers), gate 2 ZERO (not even self). Block: `welfare6_diagnostics_archive/README.md:13` names it canonical core ("stays") — stale; see Deferred unlocks | b3 formula lives in welfare6_tm.py + the b3-math doc; no HARVEST |
| FPC/welfare6_tm_joint.py | closed-candidate — **MOVED → welfare6_diagnostics_archive/ (2026-06-11)** | Bars: (a) phaseA-closure "(superseded)", successor welfare6_tm_joint5d.py (Phase A2, no anchor approximations); (b) only importers were 3 scripts already inside the archive (move co-locates and repairs them); (c) class-(iii) hits only (TJ design doc incl. its own removal prescription at :123); (d) no HARVEST. Last commit 8b82a511 2026-05-13 | b2/b3 anchor-variant evaluation fully documented in 2026-05-13_TJ_joint_asset_kernel_design.md |
| FPC/welfare6_tm_joint5d.py | **production** | THE TaxCut TM-a backup per 2026-06-10 decision ("only TM-a welfare cross-check that works … −0.14% — ACCEPTED"); `compute_joint_welfare5d` imported by joint5d_baseline:73, HM/welfare6_check_rec_bucketed5d.py:34, _batch + validate/bench/profile harnesses; 2026-06-08 | Asymptotically-correct 5-D coupled-state CRN welfare kernel with eq-labelled math (math_cheatsheet_tm_a_5D_welfare.md) — keep |
| FPC/welfare6_tm_joint5d_baseline.py | **production** | Maintained multi-cohort CLI driver for the 5-D kernel (--parametrization, cohort/duration Pools, GPU batching); imports welfare6_scenario.build_and_solve + joint5d kernel + jax_kernel (lines 72-78); plan 20260516_5D_ambitious (DONE); 2026-06-08. Caveat: ui_rec-oriented; the 2026-06-10 doc notes the TaxCut backup "has no CLI" — TaxCut use is via the kernel | The runnable entry for the TM backup; per-cohort weight aggregation — keep |
| FPC/welfare6_tm_joint5d_batch.py | live-support | Imported ONLY by validate_batch_vs_single.py + bench_batch_speedup.py (validation/bench); NOT in the production chain (GPU batching in joint5d_baseline comes from jax_kernel) — seed "production" claim contradicted; 2026-05-17 | Phase A.6 CPU β-atom batching (bit-identical mod summation order) — technique also lives in jax_kernel; no HARVEST |
| FPC/welfare6_tm_joint5d_full.py | closed-candidate — **MOVED → welfare6_diagnostics_archive/ (2026-06-11)** | Bars: (a) iteration-history-with-named-successor, in-code: joint5d_baseline.py:5 "Generalizes welfare6_tm_joint5d_full.py"; (b) zero importers; (c) class-(iii) inventory hits only; (d) no HARVEST. Last commit a9c692f9 2026-05-16 | HS_Only-only predecessor; per-duration Pool pattern carried into baseline |
| FPC/welfare6_tm_joint5d_jax.py | closed-candidate — **MOVED → welfare6_diagnostics_archive/ (2026-06-11)** | Bars: (a) B.1→B.2 lineage; successor welfare6_tm_joint5d_jax_kernel.py verified self-contained (does NOT import it); (b) zero importers; (c) one class-(v) glob hit — archive README:34 glob reworded to `welfare6_tm_joint5d_jax_kernel.py` at move time (README:44 records it); (d) no HARVEST | One-function-at-a-time port scaffold + FP32/FP64 toggle; superseded wholesale by the kernel |
| FPC/welfare6_tm_joint5d_jax_kernel.py | live-support | Conditionally imported by PRODUCTION joint5d_baseline (lines 76/78/333/335/400/403) + 10 validate/bench harnesses; INDEX row 114 (R5 (J,J,A,A,A) layout); GPU 75-221×; 2026-05-17 | 5-D GPU tensor reduction + cFunc→jnp.interp tabulation + R5 transpose-fusion fix — live, stays (HARVEST-grade if ever closed) |
| FPC/welfare6_aggregator_stratified.py | live-support | THE archive-then-restore precedent (gate-3 motivator, named in the plan); doc-consumers: conclusions_private/_FINAL_RESULTS_baseline_5x_4seed.md + session aggregation scripts + 2026-06-10 cascade doc; last commit 2026-06-10 (most recent in family); zero code importers but active doc/session consumption | Stratified post-processing + per-stratum welfare diagnostics over existing MC pickles; multi-seed aggregation used for FINAL results — keep, gate-3 protected |
| FPC/welfare6_aggregator_IS_combined.py | closed-candidate — **kept Tier-2 (HARVEST, bar d)** | Bars: (a) PASS — IS pathway explicitly NOT used per 2026-06-10 decision (+10% ui_rec joint-state sampling bias; memory project_welfare6_is_bias_diagnosis); (b) gate-1 CLEAN; (c) class-(iii) inventory only (_USER_RETURNS_README_2026-05-11:236); (d) **HARVEST blocks**. Pair with welfare6_scenario_IS.py — harvest/disposition together | **HARVEST** — stratified-IS estimator π_A·W_A + π_B·W_B with seed-paired variance estimation; unique in the codebase |
| FPC/welfare6_scenario_IS.py | closed-candidate — **kept Tier-2 (HARVEST, bar d)** | Bars: (a) PASS (same not-using-IS decision); (b) CLEAN (wrapper import of welfare6_scenario is OUTGOING); (c) class-(iii) only; (d) **HARVEST blocks**. Registry coupling: ENV_FLAGS.md:60,802,805 — sole read-site of `HAFISCAL_IS_FORCE_LOW_ANRM` (flagged "may merit deprecated"); any future move requires the Phase-3 registry reconcile (flag → `archived-only`) | **HARVEST** — forced-unemployed-intake importance sampling (post-burn-in intake-state modification, simA/simB protocol); the +10%-bias lesson is in memory, the intake mechanics only here |
| FPC/welfare6_hybrid_table.py | live-support | Live as a LIBRARY: BUG-051 regime guard (`capture_welfare6_regime`, `assert_welfare6_regimes_match`) + `write_tm_vs_mc_comparison` imported by ACTIVE HM/welfare6_tm_vs_mc.py:26 + HM/welfare6_tm_vs_mc_guard_test.py; mirrored by welfare6_scenario.py:948. ORIGINAL hybrid-table CLI role superseded by all-MC 2026-06-10 (paper's Tables/welfare6.tex now produced by the MC drivers); imports welfare6_tm_repagent_from_csvs:23; 2026-06-07 | Regime-guard library is the live core; hybrid-combination CLI is the superseded shell — keep (split candidate, not archive candidate) |
| FPC/welfare6_tm_make_tex.py | closed-candidate in substance — **kept Tier-2 (gate-3 class-(i): stale archive-README stays-claim)** | Phase-1 resolved the unknown: May-10-era emitter of Tables/welfare6_tm_repagent/{welfare6_tm_vs_mc,welfare6_tm_only}.tex — outputs exist but are ORPHANS (zero .tex sources reference them; repo-wide grep); practical successor = write_tm_vs_mc_comparison + HM/welfare6_tm_vs_mc.py (Phase C.1). Gates 1/2 clean. Block: `welfare6_diagnostics_archive/README.md:15` "paper output" stays-claim — stale; see Deferred unlocks. NAME-COLLISION note: its output `welfare6_tm_vs_mc.tex` collides with the HM driver name — all gate-3 hits disambiguated (2×.py driver in 2026-06-08 conclusions, 3×.tex output in _USER_RETURNS_README_2026-05-10) | tex-emission logic re-implemented in hybrid_table's comparison writer; no HARVEST |
| FPC/welfare6_tm_repagent_from_csvs.py | live-support | Imported by welfare6_hybrid_table.py:23 (used line 246 for the TM cells) + welfare6_tm_make_tex.py:24; rep-agent welfare method itself superseded (dilutes UI ~50%; 2026-06-10 all-MC) but the import from the live guard module blocks closure; 2026-05-10 | Cheap rep-agent welfare from existing TM Step-5 CSVs (no re-solve) — keep while imported |
| FPC/combine_seed_pickles.py | unknown — **kept Tier-2 (bar a unmet: no documented supersession)** | Phase-1 resolved: multi-seed POOLING utility (concats per-agent panels across `--seed-offset` dirs, feeds the pooled-N pathway). The across-seed SE protocol does NOT need it (compute_welfare6_se_table reads per-seed dirs directly; FINAL Baseline-5x aggregation ran via welfare6_aggregator_stratified). Gates 1/2/3 FULLY CLEAN (cleanest in family) — but zero closure evidence ⇒ cannot Tier-1-move on absence of evidence. Frozen 79db7ffc 2026-04-21. No mechanism overlap with aggregator_stratified (pools raw panels vs computes cells) | Protocol utility (pooled-point-estimate variant); if the owner rules the pooled pathway dead, document it first — then a clean candidate; no HARVEST |
| FPC/compute_welfare6_se_table.py | live-support (resolved from unknown) | The family's ONLY dedicated across-seed SE table CLI (SE = SD/√S, paper-consistent Welfare.py:277/284 formula; emits welfare6_SE.tex) = the standing "never report a bias without multi-seed SE" rule in CLI form; docstring carries the across-seed-vs-pooled-bootstrap verdict. Gate 1 verified CLEAN (imports argparse/pickle/pathlib/numpy ONLY — diagnostics_archive/README.md:36-37 "imports diag_welfare6_se" is FALSE at import level); past use: history/20260420_ui_recession_gap/welfare6_SE.tex; output not subfiled by the paper (protocol tooling) | Across-seed SE methodology tool — keep; cross-listed in §5 (counted here) |
| FPC/diag_welfare6_se.py | closed-candidate — **kept Tier-2 (gate-3 class-(i): recorded keep-decision on stale premise)** | Pooled-bootstrap SE diagnostic; approach judged inflated-on-rare-event-cells, superseded by across-seed SE (verdict in compute_welfare6_se_table docstring → bar (a) PASS). Gate 1 CLEAN (the one regex hit is prose); gate 2 = 4 docstring-mentions. Block: `diagnostics_archive/README.md:36-37` records a prior kept-not-archived decision on an "imports" premise that is stale (string-reference only); archiving only diag would also orphan 3 live cross-references — disposition the April SE trio together after correcting the README; see Deferred unlocks | CV(A_i) per-agent decomposition + N-required-for-1%-SE estimate; misc-manifest HARVEST-lite note (bootstrap-SE comparator that justified the across-seed method) — technique verdict already captured in successor docstring; cross-listed in §5 (counted here) |
| HM/welfare6_tm_vs_mc.py | live-support | Phase-C.1 unified TM-vs-MC comparison driver (BUG-051 matched-pair guard; 9-cell TM\|MC\|bias\|SE emission); imported by HM/welfare6_reconcile_sweep.py:42 + HM/welfare6_shuffle_eval.py; referenced by HM/test_env_flag_registry.py; built+validated per conclusions 2026-06-08_overnight_check_rec_reconciliation.md:26; 2026-06-07 | The unified cross-check driver the TM-welfare-apparatus map called for — keep |
| HM/welfare6_tm_vs_mc_guard_test.py | live-support | Unit test (synthetic, no model run) of the BUG-051 guard + bias/SE columns + ui_norec exclusion; referenced by HM/test_env_flag_registry.py; 2026-06-07 | Regression lock for the matched-pair guard — keep with its subject |
| HM/test_welfare6_ergodic_init.py | live-support | BUG-052 regression lock ("welfare-6 must start at ERGODIC wealth"); pytest `-m slow`; exercises welfare6_scenario build+solve + HAFISCAL_WELFARE6_TM_INIT; 2026-06-08 | Calibration-consistency lock for the production default — keep |
| HM/welfare6_ajpLvl_build.py | closed-candidate — **kept Tier-2 (HARVEST, bar d)** | Bars: (a) PASS (outcome in DONE plan 20260608_plan_A_5D_welfare_extension.md:74); (b) CLEAN; (c) class-(iv) only; (d) **HARVEST blocks**. Last commit ec41e920 2026-06-08 | **HARVEST** — forward-iterated ergodic joint P(a,j,pLvl) with cFunc dynamics + decisive E[aNrm\|pLvl-bucket]-vs-MC validation; THE core ingredient for the deferred 6-D provable TM-check (Plan C) |
| HM/welfare6_jpLvl.py | closed-candidate — **kept Tier-2 (HARVEST, bar d)** | Bars: (a) PASS (DONE plan 20260608_plan_A:62 — E[pLvl\|unemp] 3-7% below marginal, the BUG-040 freeze correlation); (b) CLEAN; (c) class-(iv) only; (d) **HARVEST blocks**. 8c963147 2026-06-08 | **HARVEST** — analytic (j × log-pLvl) Markov with unemployment pLvl-freeze; second Plan-C 6-D ingredient |
| HM/welfare6_jensen_test.py | closed-candidate — **kept Tier-2 (HARVEST + gate-3 class-(ii))** | Bars: (a) PASS (R-5 closed); (c) FAIL — conclusions 2026-06-08_overnight_check_rec_reconciliation.md:84,126 attribute recorded results to the file (results-record class); (d) **HARVEST**. Doubly blocked | **HARVEST** — reproduce-the-TM-collapse-ON-MC-PANELS decomposition (per-agent vs cohort-mean integrand on identical panels) — uniquely clean MC↔TM gap attribution |
| HM/welfare6_reconcile_sweep.py | closed-candidate — **kept Tier-2 (HARVEST + gate-3 class-(ii) + registry coupling)** | Bars: (a) PASS (R-0..R-4 + HALT recorded; INDEX:126); (c) FAIL — reconciliation doc:44 names it as the driver (reproduction-pointer); (d) **HARVEST**. ENV_FLAGS.md:484,630,633,795,926 registry coupling (HAFISCAL_USE_SOLUTION_CACHE, aCount fallback, HAFISCAL_CHECK_BUCKETS sweeper, 2B PERMGROFAC pin) — Phase-3 reconcile required if ever moved. Triply blocked | **HARVEST** — cache-aware, SE-gated (\|bias\|<0.25% w/ MC SE) convergence-sweep harness; reusable cascade-gating pattern |
| HM/welfare6_check_rec_bucketed5d.py | closed-candidate — **kept Tier-2 (HARVEST, bar d)** | Bars: (a) PASS (2026-06-10 decision: MC for Check, 6-D deferred, "do NOT patch the bucket apparatus"); (b) CLEAN; (c) class-(iv) only (structural-limit diagnosis lives in memory + decision doc without naming the file); (d) **HARVEST**. Newest stray (3152df6c 2026-06-09) | **HARVEST** — per-pLvl-bucket × 5-D-joint composition (closes the within-cell (a,j) Jensen gap; the 6-D stepping stone); also the run that produced the aMax=1300 production-grid evidence |
| HM/welfare6_shuffle_eval.py | closed-candidate — **kept Tier-2 (gate-3 class-(ii) auto-demote)** | Bars: (a) PASS-ish (shuffle settled by canonical Plan-A defaults: HAFISCAL_MC_SHUFFLE=1 + stratified, 2026-06-10); (b) PASS; (c) **FAIL** — reconciliation doc:28 attributes recorded shuffle-eval results to the file (same structure as the aggregator_stratified failure mode); (d) no HARVEST | Standard multi-seed shuffle-vs-noshuffle bias+SE scaffold; criterion (SE<0.25% AND \|bias\|<0.25%) documented |

**§1 counts:** production 5 · live-support 12 · kept Tier-2 12 (9 closed-candidates + 2 closed-in-substance + 1 unknown) · MOVED 3 · HARVEST 7 full (+1 lite cross-note on diag_welfare6_se).

**§1 Phase-1 corrections applied over Phase-0:** tm_aggregate and tm_make_tex resolved unknown→closed-in-substance (kept on stale README lines); compute_welfare6_se_table resolved unknown→live-support; combine_seed_pickles resolved unknown→unknown-kept (bar a); the 3 movers confirmed and executed; no new `welfare6_superseded_archive/` created (zero HM strays passed the bar — 5 HARVEST-blocked, 1 doc-hit-demoted).

---

## §2 — jax_mc_* + jax_solver_* (FromPandemicCode/) — 72 files

Scope: 71 `jax*` + `verify_welfare_replay.py` (the family's CLI entry). Subdirs
`jax_mc_speedup/` + `jax_tm_mult/` are §8. Pytest config note: `python_files = "test_*.py"`,
so the 19 `*_test.py` files are NOT auto-collected; only `test_jax_mc_ad_regression.py` (§7) is.
No separate Phase-1 evidence file for this family — the Phase-0 manifest itself ran the gates
for the Tier-1 batch (plan-explicit `diagnose1..7`, adjusted by evidence: 7 demoted on a
conclusions hit, 8 stays as chain terminal, co-move `jax_mc_ad_v2.py`); the executed batch J
(`430a0a5b`) matches it exactly.

Family verdicts: (1) production = 3 entries + a 13-module import closure; (2) the
`diagnose1..8` chain is linear iteration history of the Baseline-bias hunt (2026-05-18/19) —
1-6 gate-clean Tier-1 (MOVED), 7+8 kept on conclusions hits (8 = full-alignment terminal
proof, NOT a production dependency: `jax_mc_replay_production` imports `jax_mc_ad_replay_v2`
directly); (3) `jax_mc_ad_replay.py` (v1) import-blocked by kept files; (4) the 19 `*_test.py`
files are doc-consumer-covered BY GLOB (CLAUDE.md "Diagnostic & validation tools":
`jax_mc_*_test.py`, `jax_solver_*_test.py`) → live-support.

### §2a production (3)

| file | role (post Phase-1) | evidence | preservation-value |
|---|---|---|---|
| jax_mc_ad_multicohort.py | **production** | CLAUDE.md API example (multi-cohort JAX-AD); imported by `solution_cache/ad_cache.py:176,223`, `jax_mc_speedup/jax_mc_speedup_bench.py`; 10 family test/validate importers; plans/INDEX.md rows 20260518/20260604; 5 conclusion docs; mod 2026-06-02 (707L) | Core deliverable: multi-cohort JAX-AD outer loop (recession/UI/Check/TaxCut, auto-init, shuffle option) |
| jax_mc_replay_production.py | **production** | imported by `welfare6_scenario.py:749` under `HAFISCAL_USE_JAX_MC_REPLAY`; imports jax_mc_ad + hark_integration + ad_replay_v2; contains the productionized get_mortality shock/sim_birth capture; mod 2026-05-19 (232L) | Production wrapper for replay-v2 verification; the capture technique from make_ref_v4 lives here (harvest-DONE) |
| verify_welfare_replay.py | **production** | CLAUDE.md "Paper-grade welfare verification (replay-v2)" CLI section; invoked by 8 jax_mc_speedup .sh chains + reproduce/logs/overnight/run_chain.sh; mod 2026-05-21 | Paper-grade welfare spot-check CLI; reuses the jax_mc_welfare_replay_test harness (L75) |

### §2b live-support — production import closure (13)

| file | role (post Phase-1) | evidence | preservation-value |
|---|---|---|---|
| jax_mc_ad.py | live-support | imported by both production entries + all 8 diagnose scripts + ~12 tests (951L); 3 conclusion docs; mod 2026-05-20 | THE JAX AD-loop kernel (Phase 8.4); load-bearing |
| jax_mc_hark_integration.py | live-support | imported by ~32 family files incl. both production entries; `extract_recession_kernel_inputs` is the HARK→JAX bridge; mod 2026-05-19 (347L) | HARK-state extraction bridge; load-bearing |
| jax_mc_minimal.py | live-support | imported by jax_mc_hark_integration (production-transitive) + 7 others; 2 plans + 2 conclusions; the 2026-05-17 pilot kernel (592L) | Base JAX MC kernel; historical pilot doc value too |
| jax_mc_policy_scenarios.py | live-support | lazy-imported by jax_mc_ad_multicohort:53; referenced in welfare6_scenario.py:701 comment; check/taxcut validates import it | Check/TaxCut/UI policy income-override kernels |
| jax_mc_ad_shuffle.py | live-support | lazy-imported by jax_mc_ad_multicohort:46 (`use_shuffle=True` API per CLAUDE.md) | Stratified-shuffle AD kernel variant |
| jax_mc_shuffle.py | live-support | imported by jax_mc_ad_shuffle; conc 2026-05-19_jax_stratified_shuffle_design.md | JAX port of HARK PR#1776 stratified shuffle |
| jax_mc_ad_replay_v2.py | live-support | imported by jax_mc_replay_production:159, jax_mc_welfare_replay_test:23, diagnose8 + 3 replay tests | Replay-v2 kernel (full HARK alignment) — the paper-grade verification engine |
| jax_mc_welfare_replay_test.py | live-support | imported by production CLI verify_welfare_replay.py:75 ("reuse the proven harness"); conc 2026-05-19_overnight_session_summary.md | Welfare-cell replay harness; NOT a free-floating test — CLI dependency |
| jax_mc_ad_make_hark_ref.py | live-support | subprocess-run by pytest-collected test_jax_mc_ad_regression.py (slow-gated HAFISCAL_RUN_SLOW_TESTS=1) | HARK AD reference generator for the pinned regression |
| jax_mc_ad_solve_validate.py | live-support | subprocess-run by test_jax_mc_ad_regression.py; imports jax_mc_ad_solve | JAX-vs-HARK AD validation consumed by the regression test |
| jax_mc_ad_solve.py | live-support | imported by jax_mc_ad_solve_validate (test-reachable); single-cohort predecessor of multicohort (named in its docstring); conc FINAL_VALIDATION | Step 8.4 Phase B single-cohort AD loop; superseded for production but regression-test subject |
| jax_solver_drop_in.py | live-support | imported by welfare6_scenario.py:478 under HAFISCAL_USE_JAX_SOLVER (CLAUDE.md-documented flag) + 3 tests + 5 jax_mc_speedup modules; 2 plans; mod 2026-06-07 | JAX EGM solver drop-in (install_jax_solver) |
| jax_solver_kernel.py | live-support | imported by jax_solver_drop_in + jax_mc_speedup/jax_solver_iterated{,_drop_in,_multicohort}; 5 plans; BUGS_private/HAFiscal_BUG-047 doc; mod 2026-06-07 (341L) | The JAX EGM kernel itself; BUG-047 (PermGroFac factor) analysis anchor. Archiving FPC solver files would break jax_mc_speedup/ (reverse dependency across dirs) |

### §2c live-support — CLAUDE.md-documented diagnostic globs (19 `*_test.py`)

All: zero pytest collection (filename pattern mismatch), `__main__`-guard script style,
one-shot validations of landed features; doc-consumer hit BY GLOB (CLAUDE.md diagnostic-tools
section) → keep per owner ruling. Results harvested into the cited conclusion docs.

| file | role (post Phase-1) | evidence | preservation-value |
|---|---|---|---|
| jax_hark_interp_test.py | live-support | glob; 8 pytest-style `def test_` (renameable to `test_*.py` for CI); conc 2026-05-19_overnight_session_summary; mod 2026-06-07 (HARK interpolation_jax PR-adjacent) | 1e-10 JAX-vs-HARK interp parity suite; supports upstream HARK PR #1777 line |
| jax_mc_ad_check_test.py | live-support | glob; imports ad_multicohort; result: Check-under-AD parity (memory: complete-features 2026-05-19) | none beyond documented result |
| jax_mc_autoinit_test.py | live-support | glob; validates the auto-init fix (memory 2026-05-19) | none beyond documented result |
| jax_mc_deterministic_test.py | live-support | glob; conc 2026-05-18_jax_mc_residual_diagnostic.md | HARK-shock-injection technique, superseded by replay kernels |
| jax_mc_gap_h1_test.py | live-support | glob; H1 pLvl-growth hypothesis REJECTED (memory project_welfare_gap_systematic) | none — negative result documented |
| jax_mc_manyseed_bl_test.py | live-support | glob; Option-B many-seed SE at Baseline; reads ad_ref pickles | multi-seed SE harness (methodology now standing practice) |
| jax_mc_manyseed_noise_test.py | live-support | glob; HS_Only 100-seed variant | none beyond documented result |
| jax_mc_replay_hs_ui_test.py | live-support | glob; recessionUI replay-v2 sanity (memory: complete-features item 1) | none beyond documented result |
| jax_mc_replay_hs_v4_test.py | live-support | glob; conc 2026-05-19 morning report (full-alignment <0.1% at HS_Only) | none beyond documented result |
| jax_mc_replay_rr_v4_test.py | live-support | glob; Reduced_Run replay-v2 bit-precision check | none beyond documented result |
| jax_mc_scale_test.py | live-support | glob; conc 2026-05-18_overnight_jax_mc_pilot.md (127×/178× speedup numbers) | source of the pilot speedup claims |
| jax_mc_seed_variance_test.py | live-support | glob; 4-seed-set systematicity test → 25.4σ verdict (conc + memory) | the 25.4σ evidence script |
| jax_mc_shuffle_hs_test.py | live-support | glob; JAX-vs-HARK shuffle count parity (0.55% validation) | none beyond documented result |
| jax_mc_welfare_autoinit_test.py | live-support | glob; imports jax_mc_welfare_check_test; tier-1 cascade welfare cell w/ autoinit | none beyond documented result |
| jax_mc_welfare_check_test.py | live-support | glob; end-to-end check_rec_AD welfare cell JAX-vs-HARK; imported by welfare_autoinit_test | end-to-end welfare-cell harness pattern |
| jax_solver_drop_in_test.py | live-support | glob; CLAUDE.md P1-P6 suite (P5) | none beyond documented result |
| jax_solver_full_solve_test.py | live-support | glob; P6 integration (iterative solve path) | none beyond documented result |
| jax_solver_kernel_p4_test.py | live-support | glob; P4 multi-Markov recession validation; imports jax_solver_kernel_test | none beyond documented result |
| jax_solver_kernel_test.py | live-support | glob; P1-P3 kernel validation; imported by p4_test | none beyond documented result |

### §2d closed-candidate — kept Tier-2 (doc-consumer hit or import-blocked) (18)

| file | role (post Phase-1) | evidence | preservation-value |
|---|---|---|---|
| jax_mc_ad_bl_diagnose7_replay.py | closed-candidate — kept Tier-2 (conc hit) | zero reverse imports; named in conc 2026-05-19_morning_jax_mc_overnight_report.md → auto-demote per ruling (DEMOTED from the plan's expected diagnose1..7 batch) | none beyond documented result (RNG-aligned replay step of the chain) |
| jax_mc_ad_bl_diagnose8_replay_v4.py | closed-candidate — kept Tier-2 (chain FINAL + conc hit) | zero reverse imports; NOT referenced by production replay paths (replay_production imports ad_replay_v2 directly — verified); conc morning report | terminal proof: full RNG alignment closes Baseline bias to 0.003% |
| jax_mc_ad_bl_make_ref_v3.py | closed-candidate — kept Tier-2 (conc hit) | conc morning report; shock_history dump recipe | technique superseded by replay_production's built-in capture |
| jax_mc_ad_bl_make_ref_v4.py | closed-candidate — kept Tier-2 (conc hit) | conc morning report; get_mortality post-sim_birth capture hook | HARVEST-DONE: capture technique productionized in jax_mc_replay_production.py |
| jax_mc_ad_replay.py | closed-candidate — kept Tier-2 (import-blocked) | imported by kept files diagnose7:26 + jax_mc_replay_hs_sanity:23; superseded by ad_replay_v2 (v2 docstring names it) | replay-v1 (fixed newborn pool); superseded |
| jax_mc_3way_compare.py | closed-candidate — kept Tier-2 (conc hit + **HARVEST**) | conc morning report; reads TM-a pickle + welfare6_BL_ad_ref_v2 | **HARVEST**: TM-a vs HARK-MC vs JAX 3-way Cratio harness — directly reusable for this branch's TM-vs-MC validation |
| jax_mc_ad_cfunc_diag.py | closed-candidate — kept Tier-2 (conc hit) | conc 2026-05-18_jax_mc_FINAL_VALIDATION.md | none beyond documented result (pre-tabulation error bound) |
| jax_mc_cfunc_diag.py | closed-candidate — kept Tier-2 (conc hit) | conc 2026-05-18_overnight_jax_mc_pilot.md | none beyond documented result (cFunc lookup 10%-gap diagnosis) |
| jax_mc_debug_t0.py | closed-candidate — kept Tier-2 (conc hit) | conc overnight pilot | none beyond documented result |
| jax_mc_match_hark_init.py | closed-candidate — kept Tier-2 (conc hit) | conc overnight pilot | none — init-isolation step, superseded by full_init then replay |
| jax_mc_match_hark_full_init.py | closed-candidate — kept Tier-2 (conc hit) | conc 2026-05-18_jax_mc_residual_diagnostic.md | none — superseded by replay |
| jax_mc_trace_pLvl.py | closed-candidate — kept Tier-2 (conc hit) | conc residual_diagnostic | agent-by-agent T×N trajectory-diff harness (modest reuse value) |
| jax_mc_multicohort.py | closed-candidate — kept Tier-2 (conc hit + importer) | conc overnight pilot; imported by jax_mc_recession_validate_RR; NOT used by jax_mc_ad_multicohort (verified import list) | pre-AD multicohort lineage; superseded by jax_mc_ad_multicohort |
| jax_mc_recession.py | closed-candidate — kept Tier-2 (conc+plan hits + importers) | plans/20260518_step8_recession_scenarios_design.md (DONE); conc FINAL_VALIDATION; imported by jax_mc_multicohort + recession_validate | pre-AD recession kernel; superseded by jax_mc_ad |
| jax_mc_replay_hs_sanity.py | closed-candidate — kept Tier-2 (conc hit) | conc morning report; imports ad_replay (v1) | none beyond documented result |
| jax_mc_taxcut_validate.py | closed-candidate — kept Tier-2 (conc hit) | conc FINAL_VALIDATION; imports policy_scenarios + hark_integration | none beyond documented result |
| jax_mc_test_A_numpy_rng.py | closed-candidate — kept Tier-2 (conc hit) | conc FINAL_VALIDATION; NOT glob-covered (ends `_rng.py`) | numpy-RNG-injection-into-JAX technique (Threefry-vs-MT isolation); documented |
| jax_mc_test_B_fresh_newborn.py | closed-candidate — kept Tier-2 (conc hit) | conc FINAL_VALIDATION; NOT glob-covered | fresh-per-period newborn-draw technique; documented |

### §2e closed-candidate — gate-clean roster (19: 7 MOVED this round, 12 remain)

| file | role (post Phase-1) | evidence | preservation-value |
|---|---|---|---|
| jax_mc_ad_bl_diagnose.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | Bars: (a) iteration history, chain documented in conc 2026-05-19 morning report, terminal = diagnose8; (b) zero reverse imports incl. tests (verified import-line grep); (c) only doc hit = the sweep plan's own candidate list (class-iv, non-blocking); (d) no HARVEST | none — step 1 of documented chain |
| jax_mc_ad_bl_diagnose2.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | zero refs anywhere; same bars | none — step 2 (kernel-vs-AD-loop isolation) |
| jax_mc_ad_bl_diagnose3_fp64.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | zero refs; same bars | none — FP64 hypothesis test, result in morning report |
| jax_mc_ad_bl_diagnose4_newborn.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | zero refs; imports jax_mc_ad_v2 → co-move pair honored | none — newborn-mrkv hypothesis |
| jax_mc_ad_bl_diagnose5_tage.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | zero refs; reads welfare6_BL_ad_ref_v2 pickle | none — t_age0 alignment test |
| jax_mc_ad_bl_diagnose6_combined.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | zero refs; same bars | none — combined-fix test |
| jax_mc_ad_v2.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11, co-move with diagnose4)** | imported ONLY by diagnose4:13 (verified); kernel variant for Test 2; pair not split | none — variant superseded by jax_mc_ad |
| jax_mc_ad_bl_make_ref_v2.py | closed-candidate — kept Tier-2 (gate-clean, future-round candidate) | zero refs; one-shot ref generator (t_age_t0 dump) for the diagnose chain; not in this round's plan-explicit batch | none — recipe superseded |
| jax_mc_ad_bl_make_ref_v5.py | closed-candidate — kept Tier-2 (gate-clean but **HARVEST**, bar d) | zero refs; "full AD convergence (no MAX_ITER cap) for TM-vs-MC apples-to-apples" | **HARVEST**: uncapped full-AD-convergence reference recipe — directly relevant to this branch's TM-vs-MC comparisons |
| jax_mc_ad_validate.py | closed-candidate — kept Tier-2 (gate-clean, future-round candidate) | zero refs; Step 8.4 kernel-vs-HARK-converged validation | none beyond documented result |
| jax_mc_ad_multicohort_validate.py | closed-candidate — kept Tier-2 (gate-clean, future-round candidate) | zero refs; Step 11 Reduced_Run validation (result in memory/conclusions) | none beyond documented result |
| jax_mc_ad_check_debug.py | closed-candidate — kept Tier-2 (gate-clean, future-round candidate) | zero refs; surgical Check-under-AD debug | none beyond documented result |
| jax_mc_baseline_5x_bench.py | closed-candidate — kept Tier-2 (gate-clean, future-round candidate) | zero refs; wall-time bench (numbers in CLAUDE.md perf section / conclusions) | none beyond documented result |
| jax_mc_check_validate.py | closed-candidate — kept Tier-2 (gate-clean, future-round candidate) | zero refs; Check scenario + check_norec welfare validation | none beyond documented result |
| jax_mc_init_compare.py | closed-candidate — kept Tier-2 (gate-clean, future-round candidate) | zero refs; aNrm_base vs history[0] diagnostic | none |
| jax_mc_recession_validate.py | closed-candidate — kept Tier-2 (gate-clean, future-round candidate) | zero refs; imports kept jax_mc_recession (archived-script-imports-kept-module OK per archive sys.path convention) | none beyond documented result |
| jax_mc_recession_validate_RR.py | closed-candidate — kept Tier-2 (gate-clean, future-round candidate) | zero refs; imports kept jax_mc_multicohort | none beyond documented result |
| jax_mc_welfare_gap_investigate.py | closed-candidate — kept Tier-2 (gate-clean, future-round candidate) | zero refs; period-by-period gap accumulation (result in memory project_welfare_gap_systematic + conclusions) | none beyond documented result |
| jax_solver_recession_bench.py | closed-candidate — kept Tier-2 (gate-clean, future-round candidate) | zero refs; StateCount=132 solve bench → the "4.6× slower" verdict (CLAUDE.md JAX-solver section cites it) | source of the 4.6×-slower number; number already in CLAUDE.md |

**§2 counts:** production 3 · live-support 32 (13 closure + 19 glob) · kept Tier-2 30 (18 doc-hit/import-blocked + 12 gate-clean remainder) · MOVED 7 · HARVEST 2 (3way_compare, make_ref_v5; harvest-DONE noted for make_ref_v4 and the RNG-isolation trio).

---

## §3 — phase* (19 files)

Completed-validation drivers from three closed campaigns: (a) **TM scale-up phases 0-5**
(plan 20260329-1853h DONE, INDEX:14; status RECORD 20260330-0812h "phases 1-5 complete",
INDEX:15); (b) **P-vs-Q (Harmenberg) revalidation** (INDEX:23, 87 DONE → conclusion
2026-04-28_mc-confirms-tm-p-is-accurate…); (c) **CDC-vs-ESC kernel comparison** (INDEX:84
DONE → conclusion 2026-04-28_cdc-esc-asset-rule-is-2pp).

Phase-1 ruling applied (overrides Phase-0's broader reading): mentions in the RECORD status
doc 20260330-0812h are non-gate hits (INDEX.md:8 defines RECORD = reference-not-plan; closed
plans reference all previously-archived scripts, so RECORD hits cannot block without freezing
the sweep) → phase1_3types/phase2_21types/phase3/phase4/phase5 MOVE. The seed claim "phase2_*
files import harmenberg_doob_tier1{,_esc}" is FALSE in the current tree (verified; §4).

| file | role (post Phase-1) | evidence | preservation-value |
|---|---|---|---|
| phase0_convergence_validation.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | campaign (a) DONE/RECORD; g1=0, g2=0, g3=0; pattern superseded by adaptive_grid_tm.py + asymptotic-equality driver; last substantive touch 2026-04-05 | MC N-sweep + TM mCount-sweep convergence harness. Low |
| phase1_3types_validation.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | campaign (a) DONE; only mention = RECORD status doc (non-gate per Phase-1 ruling) | 3-type differenced-policy-effect validation pattern. Low |
| phase1_pertype_diag.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | campaign (a) DONE; BUG-023 closed (BUGS_private trail only); g1/g2/g3 = 0 | per-edu-type NPV error decomposition. Low |
| phase2_21types_validation.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | campaign (a) DONE; RECORD-doc mention only | no-deepcopy MC re-run technique (run_experiment state-restore) noted in docstring. Low |
| phase3_recession_avg_validation.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | campaign (a) DONE; RECORD-doc mention only | duration-probability-weighted averaging vs production Simulate flow. Low |
| phase4_baseline_params_validation.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | campaign (a) DONE; RECORD-doc mention only | long-horizon (act_T=400) pLvl_factor drift test. Low |
| phase5_pipeline_test.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | campaign (a) DONE; function covered by do_all_reduced.py/reproduce_min; NOT pytest-collected (`*_test.py` suffix, 0 `def test_`) | sim_method='both' + Output_Results smoke. Low |
| phase01_P_Q_MC_comparison.py | closed-candidate — **kept Tier-2 (HARVEST, bar d)** | campaign (b) DONE; g1/g2/g3 = 0; math ref → history/20260331-mathematical-derivations-harmenberg.md + BST appendix | **HARVEST**: 3-way TM-P vs TM-Q vs MC (200K×3, TM-ergodic init + warmup) comparison harness — the cleanest same-economy multi-method jig in the repo |
| phase01_P_vs_Q_comparison.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | campaign (b) DONE ("in-file status: done" per INDEX:23); subset of phase01_P_Q_MC_comparison (kept, HARVEST); g1/g2/g3 = 0 | TM-only P/Q comparison; subset of the above. Low |
| phase_harm_neutral_mc.py | closed-candidate — **kept Tier-2 (HARVEST-lite)** | no importers/refs/doc hits; superseded by HARK `dual_measure` + DualMeasureMixin (INDEX:17,21 DONE); in misc Phase-1 HARVEST-blocked list | HARVEST-lite: Harmenberg-neutral MC with scalar `pLvl_factor(t)` population aggregation (Theorem-1 application) — technique now in HARK fork, this is the standalone exposition |
| phase2_baseline_cdc_vs_esc.py | live-support | touched by BUG-051 fix commit c4e36882 2026-06-05 ("(1-ς) household correction") — used to validate the ESC-kernel fix; cross-cited by phase2_check docstring; NOT imported by test_phase2_drivers.py | CDC≈ESC-at-baseline invariant driver. Moderate (BUG-051 regression relevance) |
| phase2_check_cdc_vs_esc.py | live-support | **imported by test_phase2_drivers.py** (real pytest, 14 tests: smoke+invariants for 6 drivers); plan 20260428-1252h doc hit | Check-multiplier CDC/ESC jig via production wrappers. Moderate |
| phase2_taxcut_cdc_vs_esc.py | live-support | imported by test_phase2_drivers.py | Low-moderate |
| phase2_ui_cdc_vs_esc.py | live-support | imported by test_phase2_drivers.py | documents UI's CondMrkvArrays/transition_ub mechanics in docstring. Low-moderate |
| phase2_recession_cdc_vs_esc.py | live-support | imported by test_phase2_drivers.py; conclusions hit: 2026-04-28_strict-policy-multiplier-isolates-policy-from-recession.md | origin of the strict-policy-multiplier convention (resolved Check sign flip). Moderate |
| phase2_multibeta_cdc_vs_esc.py | live-support | imported by test_phase2_drivers.py; plan doc hit | 7-β-atom pmv-weighted AgentCount technique. Low-moderate |
| phase2_multicohort_cdc_vs_esc.py | live-support | imported by test_phase2_drivers.py | 21-type population per-capita normalization (EducShares×pmv). Low-moderate |
| phase2_percohort_cdc_vs_esc.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | campaign (c) DONE; NOT imported by test_phase2_drivers.py (verified); only mention = BUGS_private forensic notes (non-gate); one-off decomposition of the 2pp ESC>CDC gap by edu group | per-cohort gap decomposition pattern. Low |
| phase2_AD_one_scenario.py | live-support — **kept (also HARVEST)** | conclusions hits: 2026-04-28_qe-style-ad-multiplier-uses-asymmetric-numerator-denominator.md (cites its `--full_averaging`/`--no_ad`) + 2026-05-19_morning_jax_mc_overnight_report.md:160 ("the full AD-aware TM solver `run_ad_tm` … is used by phase2_AD_one_scenario.py"); no in-repo launcher (driven manually) | **HARVEST**: the only standalone exemplar of `tm_methods.run_ad_tm` (Phase-1 CFunc training + Phase-2 eval) outside the welfare6_tm wiring; QE-style asymmetric-multiplier reference implementation |

**§3 counts:** production 0 · live-support 8 · kept Tier-2 2 · MOVED 9 · HARVEST 2 full (+1 lite).
(Note: the Phase-0 roll-up line said "9 live-support / 10 closed"; the row-level data —
authoritative — gives 8 live-support / 11 closed-candidate. Corrected here.)

---

## §4 — harmenberg_* (2 live files; 19 already archived)

Already archived (verified in `diagnostics_archive/`): `diag_harmenberg_mc,
harmenberg_cohort_drift_test, harmenberg_doob_co_diag, harmenberg_doob_drift_test,
harmenberg_doob_high_beta_diag, harmenberg_doob_init_test, harmenberg_doob_long_T,
harmenberg_doob_tail_chars, harmenberg_doob_test, harmenberg_doob_tier_a,
harmenberg_doob_tier_a_wide, harmenberg_doob_tier_c, harmenberg_grid_sweep,
harmenberg_mc_diag, harmenberg_mc_vs_tm, harmenberg_pi_q_test, harmenberg_tier0,
harmenberg_tier_A, harmenberg_tier_B` (×19).

Seed-knowledge correction (verified): NO `phase*` file imports `harmenberg_doob_tier1{,_esc}`
— the live importers are `Code/HA-Models/mc_tsim_convergence.py` plus two test files (below);
`phase01_*` only cite "harmenberg" in docstring math references.

| file | role (post Phase-1) | evidence | preservation-value |
|---|---|---|---|
| harmenberg_doob_tier1.py | live-support (LIVE — do not move) | imported by `Code/HA-Models/mc_tsim_convergence.py:49` (`setup_context, build_agent_for, run_mc_capture_aj`), `test_co_drift_sweep.py:31`, `test_qtwisted_cohort_capped.py:35,85,297`, `harmenberg_doob_tier1_esc.py:9`; +2 archived importers (archive scripts reach back into FromPandemicCode); conclusions hits 2026-04-28_doob-cascade-gate-results.md + 2026-05-01_co-drift-* ×2; named in the umbrella plan | **HARVEST (as refactor target)**: its `setup_context`/`build_agent_for` pair became a de-facto shared fixture library for one-cohort TM/MC experiments — candidate for promotion into a proper helper module rather than archival |
| harmenberg_doob_tier1_esc.py | live-support | 14-line wrapper (`from harmenberg_doob_tier1 import main`, ESC env + interpretation='ESC'); documented in `Code/HA-Models/docs/ENV_FLAGS.md:112` as a setdefault-ESC driver; conclusions hit 2026-04-28_doob-cascade-gate-results.md; touched 2026-06-07 (PR-readiness 2c826a05) | trivial wrapper; value = documented ESC matched-pair example. Low |

**§4 counts:** production 0 · live-support 2 · kept Tier-2 0 · MOVED 0 · HARVEST 1 (refactor-target).

---

## §5 — misc singletons: diag_/diagnose_/trace_/analyze_/investigate_/bench_/extract_/compute_ (23 files; 2 cross-listed)

Era clusters: March TM-UI/TM-MC debugging (2026-03-22 cohort), April welfare-gap attribution,
2026-05-04 multiplier-residual D-series (mystery RESOLVED 2026-05-05, BUG-040/041), May
5D/JAX benches. Cross-listed with §1 (counted there): `compute_welfare6_se_table.py`,
`diag_welfare6_se.py`.

| file | role (post Phase-1) | evidence | preservation-value |
|---|---|---|---|
| analyze_splurge_isolation.py | closed-candidate — **kept Tier-2 (file-dependency coupling)** | g1=0 but g2=2 **file-dependency** hits: bisect_welfare.sh:21,70 `cp`s it into bisection worktrees → co-moves only when that (kept, HARVEST-lite) script moves; bisection plan DONE (INDEX:49) | ς-channel isolation (same β/∇, BUG-031 fixed, only ς differs). Low |
| analyze_welfare_gap.py | closed-candidate — **kept Tier-2 (HARVEST-lite)** | 0 importers; docstring-cited by mc_welfare_diagnostic.py:10; doc hits: 3 welfare-asymmetry plans, all DONE/SUPERSEDED (INDEX:46-48); in Phase-1 HARVEST-blocked list | HARVEST-lite: analytic welfare identity `W_6 = 1 + (M_inf^w − M_inf) − Q^w + O(Δ³)` for CRRA=2 — derivation-backed decomposition not recorded elsewhere in code |
| bench_5d_jax_saturation.py | closed-candidate — **kept Tier-2 (HARVEST, bar d)** | 0 importers/refs/doc hits; commit 618f3c37 2026-05-16 (5D Phase A/B era) | **HARVEST**: vmap-vs-iterate GPU-saturation micro-bench on synthetic 5D kernel — measured basis for "GPU only ~2× for TM marginals; GPU stays for welfare" (memory project_no_jax_tm_multiplier_why) |
| bench_batch_speedup.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | Bars: (a) documented negative decision — reproduce/logs/5D_parallel/A6_implementation_findings.md "0.95× speedup (NEGATIVE)", batching rejected; (b) 0 importers; (c) clean (the 2 A6-findings mentions are provenance of the recorded result); (d) no HARVEST | negative-result evidence preserved in the findings doc; script itself low |
| compute_welfare6_control_variate.py | closed-candidate — **kept Tier-2 (HARVEST, bar d)** | imports compute_welfare6_mc_l2; doc hits: INDEX:62 (DONE — "CV ineffective for UI → multi-seed plan") + 3 DONE plans | **HARVEST**: full control-variate welfare estimator (MC + TM-based CV) — the plan's own example of a variance-reduction trick worth lifting; superseded operationally by multi-seed CRN but unique |
| compute_welfare6_mc_l2.py | closed-candidate — **kept Tier-2 (pairs with CV)** | imported ONLY by compute_welfare6_control_variate.py — the two move/stay together; 2 DONE-plan doc hits | L2-decomposition of W^U from bootstrap-source panels. Moderate (CV dependency) |
| compute_welfare6_se_table.py | live-support — *cross-listed: counted under §1* | see §1 row (resolved unknown→live-support; the across-seed SE CLI) | — |
| diag_comprehensive_tm_mc.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | superseded by test_asymptotic_equality_revised.py (INDEX:24,31 DONE); g1/g2/g3 = 0 (CHANGELOG_0170_MIGRATION.md:236 = frozen historical inventory, non-gate) | all-8-experiment TM-vs-MC NPV harness. Low |
| diag_welfare6_se.py | closed-candidate — *cross-listed: counted under §1* | see §1 row (kept Tier-2 on diagnostics_archive/README.md:36-37 recorded keep-decision; stale "imports" premise) | HARVEST-lite note recorded in §1 row |
| diagnose_burnin.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | March campaign closed; superseded by asymptotic-equality ladder (INDEX:19-31 DONE); g1/g2/g3 = 0 | burn-in-length sweep pattern. Low |
| diagnose_cons_gap.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | iteration-history-with-named-successor (cleanest Tier-1 pattern): diagnose_cons_gap2.py:4 "Previous diagnose_cons_gap.py had a bug"; the successor co-moved (next row); test_cons_gap_fix.py:5 mention is docstring-only — the test KEEPS (it regression-tests the production mNrm-preservation fix, imports production modules only) | Low |
| diagnose_cons_gap2.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | end of closed iteration chain; fix regression-covered by KEPT test_cons_gap_fix.py; g1/g2/g3 = 0 | TM `_apply_micro_transition` mNrm-preservation hypothesis test. Low |
| diagnose_distributions.py | closed-candidate — **kept Tier-2 (HARVEST-lite)** | 0 everything; March cohort; in Phase-1 HARVEST-blocked list | HARVEST-lite: distribution-level (histogram-on-TM-grid) TM-vs-MC comparison instead of means — pattern reused conceptually in later drift gates |
| diagnose_mc_convergence.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | March campaign closed; superseded by asymptotic-equality ladder; g1/g2/g3 = 0 | N-sweep TE convergence for rare-state (UB) effects. Low |
| diagnose_mc_tm_bias.py | closed-candidate — **kept Tier-2 (gate-3 conclusions hit, auto-demote)** | conclusions_private/2026-05-04_mc-tm-multiplier-residual-mechanism-diagnostics.md:88 cites it as a diagnostic script; D-series root; subject RESOLVED 2026-05-05 (BUG-040/041) | D-series steady-state-vs-response bias bisection design. Low-moderate (cited) |
| diagnose_tm_ui.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | March TM-UI debugging closed (BUG-023 era); g1/g2/g3 = 0 | known-answer analytical micro-transition tests. Low |
| extract_h0_diagnostic.py | closed-candidate — **kept Tier-2 (gate-3 conclusions hits ×2, auto-demote)** | conclusions 2026-05-04_h0-shuffle-validation…:36 "Detailed per-run extraction script: …extract_h0_diagnostic.py" + 2026-05-04 mechanism doc:88 | h0 treat/control pickle post-processor. Low |
| extract_mc_tm_multipliers.py | live-support | conclusions hit **2026-06-05** MC_vs_TM_bottomline_crosscheck.md (recent use) + 2026-05-04 mechanism doc + plans/results_20260504_speedup-test-matrix.md | side-by-side MC/TM multiplier extractor from sim_method='both' pickles — recurring crosscheck tool. Moderate |
| investigate_recession_check.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | subject resolved via BUG-030/040/041 chain; only refs = docstring mentions in 2 already-archived scripts (co-located after move) + BUGS_private index; g1/g3 = 0 | high-res TM + bucket sweep experiment design. Low |
| trace_minimal.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | March campaign closed; g1/g2/g3 = 0 (boundary regex excludes trace_minimal2 hits) | period-0 UI TE trace. Low |
| trace_minimal2.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | March campaign closed; g1/g2/g3 = 0 | splurge/non-splurge TE decomposition trace. Low |
| trace_period1_tm_init_vs_tm_operator_composer.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | composer POC closed (debug/20260323-1312h record); no test imports it (test_mortality_fix_poc_composer.py imports production modules only — verified) | one-step TM-operator vs MC-step comparison from identical injection. Low |
| trace_unemployment.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | March campaign closed; no-simulation walkthrough; g1/g2/g3 = 0 | code-logic walkthrough pattern. Low |
| _tm_a_drift.py | **live-support** (**econ-mw merge 2026-06-13**; does not match the §5 prefixes — listed here as the catch-all support singleton) | The MC⇄TM-a drift gate (`assess_and_report`): consumed by the production `Simulate.py` warm-start path; gated by `HAFISCAL_DRIFT_HARD_FAIL` / `HAFISCAL_DRIFT_THRESHOLD` / `HAFISCAL_DRIFT_PLVL_NAWARE` / `HAFISCAL_DRIFT_PLVL_Z` (all live in ENV_FLAGS.md); tested by `test_drift_uses_exact_moments.py` (§7) | Mandatory production quality gate (Lorenz-share + N-aware pLvl-moment drift); keep |

**§5 counts (22 unique, +1 econ-mw merge):** production 0 · live-support 2 (extract_mc_tm_multipliers, _tm_a_drift) ·
kept Tier-2 8 · MOVED 12 · HARVEST 2 full (+2 lite).

---

## §6 — run_* drivers + *.sh (10 .py + 3 .sh; 2 cross-listed)

Cross-listed with §1 (counted there): `run_welfare6_parallel.py`, `run_hybrid_welfare6.py`
(both **production**; full rows in §1). Documented-entry-point split: documented =
run_welfare6_parallel (do_all 5b + READMEs + CLAUDE.md), run_hybrid_welfare6 (do_all_reduced
+ reproduce_computed_TM_and_MC.sh), run_phase2_parallel (orchestrators + scripts/),
run_step5a_only & run_all (ENV_FLAGS.md only); one-off = the rest.

| file | role (post Phase-1) | evidence | preservation-value |
|---|---|---|---|
| run_welfare6_parallel.py | **production** — *cross-listed: counted under §1* | do_all.py:191-195 Step 5b (`--baseline`); Code/README.md:63,207,465 + Code/HA-Models/README.md:58,139,190 + CLAUDE.md:90; run-manifest comp_full_20260421-1911; imported by 8 files incl. welfare6_hybrid_table, welfare6_tm_vs_mc, test_auto_parallel_plan; 2026-06-02 OOM fix | canonical MC welfare-6 parallel runner; Table 7 producer |
| run_hybrid_welfare6.py | **production** — *cross-listed: counted under §1* | do_all_reduced.py:160,179-182; reproduce/reproduce_computed_TM_and_MC.sh:174-180; welfare6_scenario.py:6-13 stay-in-sync contract; BUG-052 fix 2026-06-08 (c12a7bda) | serial CRN-paired welfare-6 reference path |
| run_phase2_parallel.py | **production** | imported by `Code/HA-Models/reest_permgrofac_hybrid.py:60`; subprocessed by `reestimate_bug053_orchestrate.py:141`; documented wrapper target in `scripts/run_with_tma_companion.py:38`; protocol referenced from EstimAggFiscalMAIN.py:1186,1218,1361 + estim_phase2_tm_a.py:450; conclusions: QE-comparison + qe_fidelity_full docs | per-edType subprocess Step-2 estimation wrapper + canonical-file merge logic (the only implementation of the merge protocol) |
| run_step5a_only.py | live-support | 6 mentions in ENV_FLAGS.md (incl. QE_FIDELITY_DEFAULTS behavior + zombie-flag note :54,:396); conclusions 2026-05-03_HAFiscal-QE-vs-current-comparison.md; plans 20260504-* (DONE era) | the qe-fidelity Step-5a wrapper with env-passthrough list; reference for QE-fidelity env defaults |
| run_all.py | live-support | ENV_FLAGS.md:460 lists it as a HAFISCAL_SIM_METHOD=TM setter; plan 20260418-1237h (DONE); NOT referenced by do_all/READMEs/reproduce | single-entry hybrid TM+MC pipeline runner (`--baseline`); overlaps do_all Step-5. Low-moderate |
| run_optc_param.py | closed-candidate — **kept Tier-2 (ENV_FLAGS/registry coupling, auto-demote)** | ENV_FLAGS.md:354 documents its HAFISCAL_NO_FORK setdefault site; ENV_FLAGS.md is consumed by ACTIVE plan 20260611_env-flag-registry.md → doc-consumer coupling; revisit after a Phase-3 registry reconcile. "Option C" era closed (pre-rename 079e65ab) | single-parametrization robustness runner with published estimates. Low |
| run_mc_crn_validation.py | closed-candidate — **kept Tier-2 (HARVEST-lite)** | cited as CRN-safety evidence in run_welfare6_parallel.py:9 docstring; plans 20260418-1237h ×2 (DONE; merged 26c012f9); in Phase-1 HARVEST-blocked list | HARVEST-lite: subprocess-determinism validation pattern (two independent children + in-parent anchor, element-wise pickle compare) |
| run_reduced_tm_a_indexed.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | purpose (TM-a vs TM-m output compare) superseded by production adoption of a-indexed TM (BUG-033 fix, INDEX:52 DONE); single plan mention is in a DONE plan (comparative aside); g1/g2 = 0 | TM-a vs TM-m output comparison runner. Low |
| run_full_tm_ad.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | function absorbed into production Simulate sim_method='TM' path; mentions only in debug/ + BUGS_private forensic notes (non-gate); 2026-03-24 | first full TM+AD Baseline run vs published QE. Low |
| run_full_tm_timing.py | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | 2026-03-22 timing probe; TM scale-up campaign concluded (INDEX:14/15); g1/g2/g3 = 0 | Low |
| bisect_welfare.sh | closed-candidate — **kept Tier-2 (HARVEST-lite)** | plan 20260418-1053h_welfare-drop-bisection DONE (INDEX:49; resolved by 2026-04-20 bit-identical conclusion); depends on mc_welfare_diagnostic.py + copies analyze_splurge_isolation.py into per-commit worktrees (coupling recorded in both rows) | HARVEST-lite: worktree-per-checkpoint bisection harness injecting a fixed diagnostic into each historical commit — reusable forensic pattern |
| launch_track_a_prime.sh | closed-candidate — **MOVED → diagnostics_archive/ (2026-06-11)** | Track-A′ UI-recession-gap investigation DONE (INDEX:61 → history/20260420-ui-recession-gap-resolution.md); only refs = DONE plan + history/ record. First .sh in diagnostics_archive (README notes it) | Track-A′ full-master-config attribution run. Low |
| run_welfare_attribution.sh | closed-candidate — **kept Tier-2 (HARVEST-lite)** | plan 20260417-1242h_…_v2.md:175 specifies it; v2 SUPERSEDED→v3 DONE (INDEX:46-48); in Phase-1 HARVEST-blocked list | HARVEST-lite: clean 4-run (A/B/C/D) one-factor-at-a-time attribution matrix design |
| reestimate_bug053_orchestrate.py | closed-candidate — **kept Tier-2 (one-off orchestrator; executed 2026-06-09)** | The BUG-053 (GIC-shave-on-GPF) re-estimation chain orchestrator: subprocesses `run_phase2_parallel.py:141` + drives `adaptive_grid_tm.py` `production_aMax()` → `HAFISCAL_TM_AMAX=1300`; referenced from §1 caution anchor + the §6 run_phase2_parallel row; cross-ref BUGS_private/HAFiscal_BUG-053_*.md | One-off re-calibration driver behind the current DiscFac estimates; keep as paper-trail until BUG-053 chain is archived |

**§6 counts (12 unique, +1 econ-mw merge):** production 1 (run_phase2_parallel) · live-support 2 ·
kept Tier-2 5 · MOVED 4 (3 .py + 1 .sh) · HARVEST 0 full (+3 lite).

---

## §7 — test_* (76 files, catalog summary — no per-file rows this round)

1. **66/76 import production modules at module level** (Parameters/EstimParameters: 51;
   AggFiscalModel/tm_methods/Simulate similar counts) — the collection-error class:
   `Parameters.py` reads `sys.argv`, so most patch `sys.argv` at module top before importing.
2. **Only 20/76 are real pytest files** (≥1 `def test_`); **56 are script-style** (0 test
   functions). Of those 56, **18 have `__main__` guards** (import-inert-ish) but **38 have NO
   guard** — pytest collection of `Code/` executes their full simulation scripts (e.g.
   `test_convergence.py`, `test_tm_baseline.py` — the latter is CLAUDE.md's own single-test
   example). ~~Standing repo-level hazard~~ **CLOSED 2026-06-12**: a repo-root `conftest.py`
   now `collect_ignore`s the known script-style/broken-at-import `test_*.py` files plus the
   archived harnesses (`hark_migration_archive/`, `reproduce/version-comparison/`,
   `reproduce/upgrade-validation/`), so `pytest Code/ reproduce/` (= `make test`) collects
   cleanly. Run the ignored scripts directly with `python` if needed.
3. **4 are hyphen-named** (`test_BUG-043_*.py`) — loadable via importlib (pytest can collect)
   but unimportable by the `import` statement; trace logic runs at top level on import and
   they hardcode the absolute path `/home/shared/github/llorracc/HAFiscal-Latest/...` —
   one-off scripts, not portable tests.
4. **Real-pytest core worth protecting:** `test_phase2_drivers.py` (14 tests; imports the 6
   phase2_*_cdc_vs_esc drivers — blocks/accompanies any move of those, see §3),
   `test_tm_a_indexed.py` (16), `test_aggfiscal_interpretation_attr.py` (7),
   `test_static_period_esc.py` (7), `test_phase1_l3a.py` (6; touched by the BUG-051 fix commit
   2026-06-05 — being maintained as an ESC regression), `test_esc_tm_kernel_smoke.py` /
   `test_build_period_tm_a_esc.py` (5 each), `test_auto_parallel_plan.py` (4; imports
   production run_welfare6_parallel), `test_saved_calibration_self_consistent.py`,
   `test_jax_mc_ad_regression.py` (the only pytest-collected jax test; subprocess-runs
   §2b's make_hark_ref + ad_solve_validate), `test_drift_uses_exact_moments.py`,
   `test_pLvl_steady_state_init.py` (**econ-mw merge 2026-06-13**; pytest for the
   analytic-Markov pLvl MC seed — `HAFISCAL_MC_PLVL_INIT` paths — cites
   `conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md`),
   `test_cdc_baseline_pin.py`.
5. **Co-archival pairings (~12, trigger = their subject moving):**
   `test_BUG-043_ui_extension_{monte_carlo,outliers,trace,validation}.py` ×4 (BUG-043 closed,
   implementation complete — subject is the production encoding/flag, so not movable yet);
   `test_cons_gap_fix.py` (↔ diagnose_cons_gap*, whose move already happened — the test
   STAYS: verified it imports production modules only and regression-tests the production
   mNrm-preservation fix; its docstring back-reference is now archive-stale, standard
   pattern); `test_co_drift_sweep.py` + `test_qtwisted_cohort_capped.py` (anchor the LIVE
   harmenberg_doob_tier1.py, §4); `test_glp1_ad_tm.py` / `test_glp1_convergence.py` /
   `test_glp2_ad_comparison.py` (March TM-AD era-mates but standalone — verified
   production-only imports); `test_mortality_fix_poc_composer.py` (composer POC closed; no
   import of the moved trace_period1_* candidate); `test_dual_mc_pipeline_phase1-4.py` ×4
   (phased iteration history of the dual_MC implementation; smoke variant +
   `test_dual_measure_*` could represent the feature).
6. **Phase-1 result for this round's batches: ZERO tests co-archived** (gate-1 was 0 globally
   — no test imports any mover).
7. **BUG-regression keepers despite closed bugs (flags still live):**
   `test_bug041_cfunc_offset.py` (HAFISCAL_TM_CFUNC_OFFSET),
   `test_bug037_quick_verify/wealth_fit.py` (Step-2 wealth-fit targets; wealth_fit docstring
   cites live estim_phase2_tm_a.py), `test_reduced_run_tm_harmenberg_flags.py`.

---

## §8 — subdirectories

### §8a — `Code/HA-Models/jax_mc_speedup/` (11 .py)

Created 2026-05-20 BECAUSE of the no-new-code-in-FromPandemicCode rule (its README says so);
depends on FromPandemicCode's `jax_solver_kernel`/`jax_solver_drop_in` via sys.path, and
`AggFiscalModel.py`/`welfare6_scenario.py` reverse-depend on it — **the two dirs are
import-coupled in both directions** (archiving FPC solver files would break this dir).

| file | role (post Phase-1) | evidence | preservation-value |
|---|---|---|---|
| jax_solver_iterated.py | live-support | imported by iterated_drop_in/multicohort/smoke/test_2B_*; plans 20260520_status (RECORD); conc 2026-06-05 GPU spike; 2B core (446L) | 2B lax.while_loop JAX-native iter loop |
| jax_solver_iterated_drop_in.py | live-support | imported by AggFiscalModel.py:2365 + welfare6_scenario.py:99 (env-gated 2B path) | production 2B integration shim |
| jax_solver_iterated_multicohort.py | live-support | imported by AggFiscalModel.py:2337 (use_2b_vmap path) | cohort-vmap 2B solve |
| jax_solver_iterated_smoke_test.py | live-support | smoke for iterated; conc 2026-05-20 | none |
| test_2B_while_loop_parity.py | live-support | CLAUDE.md-named parity test; plans/INDEX.md row 20260520 | canonical 2B parity gate |
| test_2B_vmap_parity.py | live-support | only parity gate for the AggFiscalModel vmap path; zero inbound refs | vmap-path parity gate |
| test_2B_scaled.py | live-support | run by overnight_phase{2,3,4,6}.sh; parametrized parity+timing | none |
| jax_mc_speedup_bench.py | live-support | run by 10 .sh chains; README + GPU_SETUP.md | bench harness for speedup variants |
| load_balance_bench.py | closed-candidate — kept Tier-2 (doc hits) | reproduce/logs/overnight/run_chain.sh + conc + README | none — 3.88× result documented |
| analyze_2B_speedup_curve.py | closed-candidate — kept Tier-2 (doc hits) | overnight_status.sh + 2 conc docs | log-consolidation utility |
| combined_parallel_jax_test.py | closed-candidate — kept Tier-2 (doc hits) | 2 conc docs + README; parallel-solve × JAX-solver compose check | none — result documented |

### §8b — `Code/HA-Models/jax_tm_mult/` (3 .py)

Self-contained Phase-0 spike for the JAX-GPU TM multiplier kernel; plan
`20260604_jax_gpu_tm_multiplier_kernel_plan.md` SHELVED by its own verdict (GPU only ~2×
because the TM marginal state is too small to saturate it). Keep as documented-dead dev dir
with README. The `phase0_harness` hit in `test_asymptotic_equality_revised.py` is a FALSE
POSITIVE (local function `phase0_harness_checks`).

| file | role (post Phase-1) | evidence | preservation-value |
|---|---|---|---|
| phase0_harness.py | closed-candidate — kept Tier-2 (plan hit) | plans/20260604 (DONE/SHELVED by own verdict) | Phase-0 GPU-feasibility spike harness; verdict (~2× only) in memory project_no_jax_tm_multiplier_why |
| bench_pr_solver.py | closed-candidate — kept Tier-2 (dir README context) | zero refs; HARK PR#1779 AggShockMarkovJAX bench step 1 | none — verdict documented |
| bench_pr_solver_sweep.py | closed-candidate — kept Tier-2 (dir README context) | zero refs; StateCount sweep step 2 | none — verdict documented |

### §8c — `Code/HA-Models/dolo_plus_validation/` (6 .py) — econ-mw merge 2026-06-13

The YAML↔code validation harness for the dolo-plus household-stage spec
(`HAFiscal-doloplus-draft.yaml` + the equation-tag registry). Appeared in the
directory trees (`ARCHITECTURE.md`, `Code/HA-Models/README.md`) but had no
manifest rows until the econ-mw merge added the registry-checking layer.
Tied to plans `20260611_doloplus-eqn-tag-registry.md` and the doloplus
integration/spec-gap plans (see `plans/INDEX.md`) and to
`HAFiscal-doloplus-spec-decisions.md`.

| file | role | evidence | preservation-value |
|---|---|---|---|
| check_eqn_registry.py | **live-support** (econ-mw merge) | CLI checker for the equation-tag registry; plan `20260611_doloplus-eqn-tag-registry.md` | YAML↔code equation-tag consistency gate |
| test_eqn_registry.py | **live-support** (econ-mw merge) | pytest wrapper over `check_eqn_registry.py` | registry regression lock |
| test_yaml_vs_code_cfunc.py | **live-support** (econ-mw merge) | pytest: YAML cFunc vs HAFiscal code | spec-vs-code cFunc parity |
| conftest.py | **live-support** (econ-mw merge) | pytest fixtures for the validation suite | test infra |
| check_vs_hafiscal_code.py | **live-support** | YAML-vs-HAFiscal-code cross-check driver (modified in merge) | spec↔code divergence driver |
| test_euler_at_point.py | **live-support** | per-point Euler-equation check (modified in merge) | numerical spec validation |

---

## HARVEST backlog

These files embody a technique/result judged worth lifting into working tools or docs.
**A HARVEST flag blocks the file's move until the harvest is done** (bar d). Full flags (14):

| # | file | technique to harvest (one line) |
|---|---|---|
| 1 | FPC/welfare6_scenario_IS.py | Forced-unemployed-intake importance sampling: post-burn-in intake-state modification with the simA/simB protocol (the documented +10% joint-state-bias lesson lives in memory; the intake mechanics only here) |
| 2 | FPC/welfare6_aggregator_IS_combined.py | Stratified-IS estimator π_A·W_A + π_B·W_B with seed-paired variance estimation — unique IS-combination machinery; harvest as a pair with #1 |
| 3 | HM/welfare6_ajpLvl_build.py | Forward-iterated ergodic joint P(a,j,pLvl) with cFunc dynamics + decisive E[aNrm\|pLvl-bucket]-vs-MC validation — Plan-C 6-D provable-TM-check ingredient #1 |
| 4 | HM/welfare6_jpLvl.py | Analytic (j × log-pLvl) Markov with unemployment pLvl-freeze — Plan-C 6-D ingredient #2 |
| 5 | HM/welfare6_jensen_test.py | Reproduce-the-TM-collapse-ON-MC-PANELS decomposition (per-agent vs cohort-mean integrand on identical panels) — uniquely clean MC↔TM gap attribution |
| 6 | HM/welfare6_reconcile_sweep.py | Cache-aware, SE-gated (\|bias\|<0.25% with MC SE) convergence-sweep harness — reusable cascade-gating pattern |
| 7 | HM/welfare6_check_rec_bucketed5d.py | Per-pLvl-bucket × 5-D-joint composition (closes the within-cell (a,j) Jensen gap; the 6-D stepping stone); also the aMax=1300 production-grid evidence run |
| 8 | FPC/jax_mc_3way_compare.py | TM-a vs HARK-MC vs JAX three-way Cratio comparison harness — directly reusable for this branch's TM-vs-MC validation |
| 9 | FPC/jax_mc_ad_bl_make_ref_v5.py | Uncapped (no MAX_ITER) full-AD-convergence HARK reference recipe, built expressly for TM-vs-MC apples-to-apples |
| 10 | FPC/phase01_P_Q_MC_comparison.py | 3-way TM-P vs TM-Q vs MC (200K×3, TM-ergodic init + warmup) same-economy multi-method comparison jig — cleanest in the repo |
| 11 | FPC/phase2_AD_one_scenario.py | The only standalone exemplar of `tm_methods.run_ad_tm` (Phase-1 CFunc training + Phase-2 eval) outside welfare6_tm wiring; QE-style asymmetric-multiplier reference implementation |
| 12 | FPC/bench_5d_jax_saturation.py | vmap-vs-iterate GPU-saturation micro-bench on a synthetic 5-D kernel — the measured basis for "GPU ~2× for TM marginals, GPU stays for welfare" |
| 13 | FPC/compute_welfare6_control_variate.py (+ pair compute_welfare6_mc_l2.py) | Full control-variate welfare estimator (MC + TM-based CV) with L2 decomposition of W^U — the variance-reduction trick the sweep plan itself names as harvest-worthy |
| 14 | FPC/harmenberg_doob_tier1.py | Refactor-target (LIVE file — harvest = promotion, not archival): lift `setup_context`/`build_agent_for` into a proper shared fixture/helper module for one-cohort TM/MC experiments |

HARVEST-lite (7 — preserve the idea, lower urgency; lite flags also held files back this round):

| file | technique |
|---|---|
| FPC/analyze_welfare_gap.py | Analytic welfare identity `W_6 = 1 + (M_inf^w − M_inf) − Q^w + O(Δ³)` for CRRA=2 — derivation-backed decomposition not recorded elsewhere in code |
| FPC/diag_welfare6_se.py | Per-agent discounted-utility-contribution pooled-bootstrap SE — the comparator that justified across-seed SE (verdict already captured in compute_welfare6_se_table's docstring; the binding block is the README line, see Deferred unlocks) |
| FPC/diagnose_distributions.py | Distribution-level (histogram-on-TM-grid) TM-vs-MC comparison instead of means |
| FPC/phase_harm_neutral_mc.py | Standalone exposition of Harmenberg-neutral MC with scalar `pLvl_factor(t)` population aggregation (technique now in the HARK fork) |
| FPC/run_mc_crn_validation.py | Subprocess-determinism CRN validation (two independent children + in-parent anchor, element-wise pickle compare) |
| FPC/bisect_welfare.sh | Worktree-per-checkpoint bisection harness injecting a fixed diagnostic into each historical commit (couples analyze_splurge_isolation.py + mc_welfare_diagnostic.py) |
| FPC/run_welfare_attribution.sh | Clean 4-run (A/B/C/D) one-factor-at-a-time attribution matrix design |

Harvest-DONE (recorded, no flag): `jax_mc_ad_bl_make_ref_v4.py`'s get_mortality
post-sim_birth capture → productionized in `jax_mc_replay_production.py`; the RNG-isolation
trio (`jax_mc_test_A_numpy_rng` / `jax_mc_test_B_fresh_newborn` / `jax_mc_deterministic_test`)
→ documented in conclusions_private/2026-05-18_jax_mc_FINAL_VALIDATION.md.

---

## Deferred unlocks (next-round opportunities)

### 1. Three files blocked ONLY by stale archive-README lines

One README-correcting commit (owner-visible) unlocks a 2-3 file batch next round:

- **FPC/welfare6_tm_aggregate.py** — blocked by `welfare6_diagnostics_archive/README.md:13`
  ("Canonical core they were validating (stays in `FromPandemicCode/`): … `welfare6_tm.py` +
  `welfare6_tm_aggregate.py` — analytical TM-a welfare-6 (all cells)"). Stale: it has ZERO
  consumers and its indep-state aggregation was judged 2×-biased ("kept for documentation",
  2026-05-10 FINAL). Correct line 13 (and reconcile the two May-10 keep notes), then it is a
  clean candidate.
- **FPC/welfare6_tm_make_tex.py** — blocked by `welfare6_diagnostics_archive/README.md:15`
  ("`welfare6_hybrid_table.py` / `welfare6_tm_make_tex.py` — paper output"). Stale: its
  `Tables/welfare6_tm_repagent/` outputs are orphans (zero .tex sources reference them); the
  live paper-output path is the MC drivers + `write_tm_vs_mc_comparison`. The orphan Tables/
  artifacts could be swept with it. (Disambiguation already done: doc hits for
  "welfare6_tm_vs_mc" split 2×.py-driver vs 3×.tex-output, no misattribution.)
- **FPC/diag_welfare6_se.py** — blocked by `diagnostics_archive/README.md:36-37` ("…caught
  `diag_welfare6_se`, which a live `compute_welfare6_se_table.py` imports — so it was
  **kept**, not archived"). The "imports" premise is FALSE at import level (string/docstring
  reference only; verified against compute_welfare6_se_table's full import list, unchanged
  since 2026-04-21). Correct the line, then disposition the April SE trio
  (`combine_seed_pickles` / `compute_welfare6_se_table` / `diag_welfare6_se`) together —
  combine_seed_pickles additionally needs a documented owner ruling that the pooled-N pathway
  is dead (bar a), and compute_welfare6_se_table stays (live across-seed SE CLI).

### 2. Strays needing a family owner (future manifest pass)

- `mc_welfare_diagnostic.py` — dependency of kept bisect_welfare.sh (travels with it).
- `validate_*` prefix family: `validate_mc_crn.py` (↔ run_mc_crn_validation),
  `validate_tm_check.py`, `validate_tm_taxcut.py`, `validate_batch_vs_single.py` (imports
  welfare6_tm_joint5d_batch) — cited beside movers in CHANGELOG/A6 findings; outside all
  assigned prefixes this round.
- `aggregate_stratified_bench.py` — imports production run_welfare6_parallel; unowned.

### 3. jax gate-clean roster — future-round Tier-1 candidates

The §2e roster of **19 gate-clean closed-candidates** passed all grep gates in Phase 0;
**7 moved this round** (the plan-explicit batch: diagnose1-6 + co-move jax_mc_ad_v2). The
remaining **12** are queued for a future round after per-file bar-(a) write-ups:
11 unblocked — `jax_mc_ad_bl_make_ref_v2`, `jax_mc_ad_validate`,
`jax_mc_ad_multicohort_validate`, `jax_mc_ad_check_debug`, `jax_mc_baseline_5x_bench`,
`jax_mc_check_validate`, `jax_mc_init_compare`, `jax_mc_recession_validate`,
`jax_mc_recession_validate_RR`, `jax_mc_welfare_gap_investigate`,
`jax_solver_recession_bench` — plus `jax_mc_ad_bl_make_ref_v5` (gate-clean but
HARVEST-blocked, backlog #9).

### 4. Registry/coupling reconciles required before any future move

`welfare6_scenario_IS.py` (sole read-site of `HAFISCAL_IS_FORCE_LOW_ANRM`, flagged "may merit
deprecated") and `welfare6_reconcile_sweep.py` (4 ENV_FLAGS.md entries) are HARVEST-blocked
this round; if they ever move, run the sweep plan's Phase-3 registry reconcile
(`test_env_flag_registry.py`; flags whose only read sites moved → Status `archived-only`).
`run_optc_param.py` (ENV_FLAGS.md:354) likewise revisits only after a registry reconcile.

---

*Maintained as part of `plans/20260611_family-manifests-and-archival-sweep.md`. Update rows
when files move, are harvested, or gain/lose consumers; archive READMEs carry the per-move
what/why/verification/restore-path records.*



