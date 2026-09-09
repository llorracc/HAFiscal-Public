# hark_migration_archive

Closed forensic + validation scripts from the **HARK 0.14.1 → 0.17.0 upgrade** —
the migration that produced the `v0.17.0-reproduction` release. **Archived
2026-06-07** to declutter `Code/HA-Models/` top level (45 → 27 `.py`).

The migration is **complete and verified** (the upgrade is tagged and a clean-clone
install was confirmed), so these are point-in-time validation forensics — **not**
part of the reproduction pipeline.

## What's here (18 `.py` + 2 dirs)
- `debug_*` (5) — step-by-step 0.14.1-vs-0.17.0 divergence traces (mpc, objective, rng, step1)
- `full_compare` / `full_version_comparison` / `full_reproduction_orchestrator` — cross-version comparison drivers
- `quick_compare`, `quicktest_config`, `quicktest_orchestrator` + `quicktest_steps/` — quick cross-version test harness
- `fulltest_steps/` — full cross-version test harness
- `grid_construction_diagnostic`, `grid_offset_diagnostic`, `hark_grid_compat` — grid-compatibility checks across HARK versions
- `solver_comparison_diagnostic` — solver-output comparison
- `test_hark_divergence` — HARK-version divergence test
- `validation_mwe`, `validation_phase3` — minimal-working-example + phase-3 validation

## Verification (2026-06-07)
An import-graph check confirmed **no live** `Code/HA-Models/` or `FromPandemicCode/`
file imports any archived module (the only references were intra-cluster, e.g.
`quicktest_orchestrator` → `quicktest_steps/`); `do_all.py` / reproduce scripts / CI
reference none of them; **0 dangling references** after the move. Live infrastructure
that also dates from the migration (`do_all.py`, `parallel_warmup.py`,
`hafiscal_progress.py`) was deliberately **kept**.

## Restoring
`git mv hark_migration_archive/<file> ../` (back to `Code/HA-Models/`). The scripts
assume `Code/HA-Models/` (or `FromPandemicCode/`) on the path.
