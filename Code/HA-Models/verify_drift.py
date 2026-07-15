#!/usr/bin/env python3
"""verify_drift.py — the ``--complete`` multi-seed cross-section drift + SE companion.

Thread-2 component 2 of the reuse-fidelity verification taxonomy. When the VERIFY axis is
at >= ``complete`` (``HAFISCAL_VERIFY_LEVEL=complete|byte``, surfaced by ``reproduce.sh
--complete`` / ``--byte-identical``), the welfare step runs a MULTI-SEED companion of the
cheap ``base`` (no-recession) cell and reports the 4-moment cross-section drift WITH a
cross-seed standard error — the standing rule that an MC drift is never reported without a
multi-seed SE (a robust drift signal whose ``|mean|`` exceeds ~2x its SE is a real
ergodic-departure; within the SE it is sampling noise).

WHY the SE companion is the compute ``--complete`` buys: a single MC welfare run shows the
raw drift of the simulated population vs the TM-a ergodic it was warm-started at, but one
seed cannot separate a real ergodic-departure from MC sampling noise (the overnight
single-seed ~8% asset "drift" was the high tail of per-seed noise; the seed-stable signal
is the ~+3% ``var(log pLvl)`` income-spread). So ``--complete`` runs the SAME base cell at
``>=4`` seed-offsets — differing ONLY in RNG seed, identical calibration/scale/flags — and
reports mean +/- SE.

Division of labour:
  * this module owns the VERIFY-axis pieces — the gate (``should_run``), the seed count
    (``n_seeds``), and the headline report wrapper (``report_multiseed``);
  * the seed LAUNCH is done by ``run_welfare6_parallel.launch_scenarios`` (so the companion
    base cells are built byte-for-byte the way the main run built its base cell, differing
    only in seed) — kept there to avoid a circular import and to reuse the exact arg path;
  * the 4-moment + SE MATH lives in ``welfare_drift_report.py``.

Best-effort: the companion is ADDITIVE observability, run AFTER the welfare result is
computed and saved. A failure here prints abundant diagnostics and DEGRADES — it never
aborts the welfare run (the primary result already stands).

Env knob: ``HAFISCAL_VERIFY_DRIFT_SEEDS`` (default 4, floor 2) — number of seed-offsets.

Spec:   plans/20260622_reuse-fidelity-verification-flag-taxonomy.md
Build:  plans/20260622_thread2-flag-taxonomy-build-execution-plan.md (component 2)
Tool:   welfare_drift_report.py (the 4-moment / multi-seed-SE computation)
Reader: verify_level.py (the VERIFY axis)
"""
from __future__ import annotations

import os
import sys

import verify_level
import welfare_drift_report

DRIFT_SEEDS_ENV = "HAFISCAL_VERIFY_DRIFT_SEEDS"
_DEFAULT_SEEDS = 4
_MIN_SEEDS = 2  # an SE needs >= 2 samples

_BANNER = "=" * 78


def should_run():
    """True iff the VERIFY axis is at >= complete (so the drift companion should run)."""
    return verify_level.verify_at_least(verify_level.COMPLETE)


def n_seeds():
    """Number of seed-offsets for the SE.

    From ``HAFISCAL_VERIFY_DRIFT_SEEDS`` (default 4), floored at 2 (an SE needs >=2
    samples). A non-int or sub-floor value warns and falls back (never raises)."""
    raw = os.environ.get(DRIFT_SEEDS_ENV, "").strip()
    if not raw:
        return _DEFAULT_SEEDS
    try:
        n = int(raw)
    except ValueError:
        print(f"[verify_drift] WARNING: {DRIFT_SEEDS_ENV}={raw!r} is not an int; "
              f"using {_DEFAULT_SEEDS}.", file=sys.stderr)
        return _DEFAULT_SEEDS
    if n < _MIN_SEEDS:
        print(f"[verify_drift] WARNING: {DRIFT_SEEDS_ENV}={n} < {_MIN_SEEDS} "
              f"(an SE needs >=2 seeds); using {_MIN_SEEDS}.", file=sys.stderr)
        return _MIN_SEEDS
    return n


def report_multiseed(dirs, label="welfare base cell"):
    """Run the multi-seed drift+SE report over ``dirs`` inside a clear headline banner.

    ``dirs`` = one welfare result-dir per seed-offset (each holds a ``base.pkl`` with the
    ``aNrm_all_bs`` / ``pLvl_all_bs`` panels). Returns the ``multiseed_report`` rc (0 ok,
    1 = no common cell / too few dirs), or 1 on any error — best-effort: prints abundant
    diagnostics, never raises (the welfare result this annotates already stands)."""
    dirs = list(dirs)
    print(f"\n{_BANNER}")
    print(f"VERIFY (--complete): multi-seed MC cross-section drift + SE  [{label}]")
    print(f"  {len(dirs)} seed-offset result-dir(s); |mean|/SE > 2 => REAL drift, not noise.")
    print("  (standing rule: an MC drift is never reported without a multi-seed SE)")
    print(_BANNER)
    if len(dirs) < 2:
        print(f"[verify_drift] WARNING: only {len(dirs)} seed-dir(s); an SE needs >= 2. "
              f"Skipping the SE report (dirs={dirs}).", file=sys.stderr)
        return 1
    try:
        return welfare_drift_report.multiseed_report(dirs)
    except Exception as e:  # best-effort: degrade with abundant diagnostics, never abort
        import traceback
        print("\n[verify_drift] WARNING: the multi-seed drift report FAILED — the welfare "
              "result STANDS (this is an additive verification step). Diagnostics:",
              file=sys.stderr)
        print(f"  error: {type(e).__name__}: {e}", file=sys.stderr)
        print(f"  dirs : {dirs}", file=sys.stderr)
        traceback.print_exc()
        return 1


def main(argv=None):
    """Standalone: report the multi-seed drift+SE over already-produced result-dirs.

    The in-pipeline path (run_welfare6_parallel's hook) launches the seeds then calls
    report_multiseed; this CLI is for re-reporting over existing seed-dirs."""
    import argparse
    p = argparse.ArgumentParser(
        description="Multi-seed MC cross-section drift + SE over welfare result-dirs.")
    p.add_argument("dirs", nargs="+",
                   help=">= 2 welfare result-dirs (one per seed-offset).")
    p.add_argument("--label", default="welfare base cell",
                   help="label for the report banner")
    args = p.parse_args(argv)
    return report_multiseed(args.dirs, label=args.label)


if __name__ == "__main__":
    raise SystemExit(main())
