# welfare6_diagnostics_archive

Closed-case diagnostic + validation scripts from the TM-welfare development era
(the BUG-043 "Jensen" welfare bug and the 5D coupled-state propagation
validation). **Archived 2026-06-06 (Phase R rationalization)** to declutter
`Code/HA-Models/FromPandemicCode/`, which had ~41 `welfare6*` files.

These are **not** part of the reproduction pipeline. They were one-off
diagnostics that have served their purpose — the bugs they chased are fixed and
the 5D kernel they validated is in production.

## Canonical core they were validating (stays in `FromPandemicCode/`)
- `welfare6_tm.py` + `welfare6_tm_aggregate.py` — analytical TM-a welfare-6 (all cells)
- `welfare6_tm_joint5d.py` + `_baseline` + `_batch` — exact 5D joint TM (ui_rec)
- `welfare6_hybrid_table.py` / `welfare6_tm_make_tex.py` — paper output

## What's here (22 files)
- `welfare6_5d_diag_*.py` — 5D-vs-MC per-cell / per-period / distribution diagnostics
- `welfare6_5d_vs_mc_perperiod.py` — per-period welfare-numerator comparison
- `welfare6_tm_joint5d_diag_*.py` — 5D propagation-correctness diagnostics
- `welfare6_tm_joint5d_test.py` — 5D smoke test
- `welfare6_tm_joint_diag{1,2}.py`, `_full.py`, `_test.py` — Phase T.J 2D-joint diagnostics (superseded by the 5D kernel)

## Restoring one
`git mv welfare6_diagnostics_archive/<file> ../FromPandemicCode/` — these scripts
import `FromPandemicCode` siblings (`tm_methods`, `welfare6_scenario`, …) and
assume that directory as cwd / `sys.path`, so they must live in
`FromPandemicCode/` to run.

## Verification (Phase R)
An import-graph check confirmed **no canonical/production driver imports any
archived file** before the move (0 blocks). Held back from this pass because they
have live dependents: `parity_*.py` (shared helper for 9 `diag_*`/`test_*` files)
and `welfare6_tm_joint5d_jax_kernel.py` (the kernel is imported by the canonical
`welfare6_tm_joint5d_baseline.py`).


## Batch 2026-06-11 (doc-rationalization, plans/20260611_family-manifests-and-archival-sweep.md)
Moved after the quadruple-bar gate (superseded-or-successor + zero reverse imports incl. tests +
zero active-doc consumers + no HARVEST flag), evidence in Code/HA-Models/docs/FILE_FAMILIES.md:
- `welfare6_tm_joint.py` — 2-D joint, superseded by the 5-D lineage; its only importers were 3 files
  already in this archive (co-located by this move).
- `welfare6_tm_joint5d_full.py` — generalized by `welfare6_tm_joint5d_baseline.py` (stated in its header).
- `welfare6_tm_joint5d_jax.py` — B.2 kernel superseded by `welfare6_tm_joint5d_jax_kernel.py` (which is
  what production imports); the old README glob here was amended accordingly.
Restore: `git mv` back to FromPandemicCode/. Scripts assume FromPandemicCode/ cwd/sys.path.
