"""Repo-root pytest collection guard.

`pytest Code/ reproduce/` is the documented test gate (CLAUDE.md, `make test`),
but the tree also contains script-style files named `test_*.py` that are NOT
pytest suites: standalone diagnostics that execute full model solves (or call
`sys.exit`) at import time, plus archived harnesses that require sibling
checkouts. FILE_FAMILIES.md §7 catalogs the hazard. This conftest keeps them
out of collection so the gate stays green and collection stays side-effect-free.

Run any of these directly (`python path/to/script.py`) — they still work.
"""

import os

# Pin the numba pool size for the whole pytest run, before any test imports
# numba. Every production entry point already pins NUMBA_NUM_THREADS=1
# (welfare6_scenario.py, AggFiscalMAIN_reduced.py — process-parallelism owns
# the cores); without a harness-level pin, collection order decides whether
# numba's pool launches at 1 or at cpu_count, and numba >= 0.67 raises on the
# mismatch ("Cannot set NUMBA_NUM_THREADS to a different value once the
# threads have been launched"). setdefault: an explicit env override wins.
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

# The shared solved-policy store is default-ON (2026-08-24) at the per-user
# ~/.cache/hafiscal/policy_store. A pytest session must never write test-sized
# solves into the real store (six HS_Only test entries landed there the first
# time the gate ran under the default), so point the whole session at a fresh
# temporary store. Tests that exercise the SOLVER path additionally set
# HAFISCAL_POLICY_STORE=0 themselves (test_step5_ati_wiring.py), because within
# one session the first solve's entry would otherwise be served to later tests.
# setdefault: an explicit HAFISCAL_POLICY_STORE_DIR still wins.
import tempfile  # noqa: E402

os.environ.setdefault(
    "HAFISCAL_POLICY_STORE_DIR",
    tempfile.mkdtemp(prefix="hafiscal-policy-store-pytest-"))

# Archived / external-checkout harnesses (whole directories).
collect_ignore_glob = [
    "Code/HA-Models/hark_migration_archive/*",
    "reproduce/version-comparison/*",
    "reproduce/upgrade-validation/*",
]

# Standalone scripts misnamed test_*.py: run sims at import, parse sys.argv,
# use HARK-0.14-era APIs, or call sys.exit at module level (FILE_FAMILIES.md §7).
collect_ignore = [
    "Code/HA-Models/test_single_objective_eval.py",
] + [
    f"Code/HA-Models/FromPandemicCode/{name}"
    for name in [
        "test_affected_set_diagnosis.py",
        "test_bug037_quick_verify.py",
        "test_bug037_wealth_fit.py",
        "test_cohort_ergodic.py",
        "test_cons_gap_fix.py",
        "test_convergence.py",
        "test_convergence_ui_cons.py",
        "test_cross_cfunc.py",
        "test_final_convergence.py",
        "test_first_period_trace.py",
        "test_fraction_only.py",
        "test_full_period_init.py",
        "test_glp1_ad_tm.py",           # runs a full Simulate() at import; under the session's empty
                                        # policy store + welfare6_scenario's module-level REQUIRE=1
                                        # it dies on a store MISS (found 2026-09-04)
        "test_glp1_convergence.py",
        "test_glp2_ad_comparison.py",
        "test_halfstep_ui.py",
        "test_halfstep_verify.py",
        "test_mc_sample_size_estimation.py",
        "test_mcount_sweep.py",
        "test_pLvl_factorization.py",
        "test_pLvl_hypothesis.py",
        "test_perstate_decomp.py",
        "test_shuffle_hs_precision.py",
        "test_shuffle_tm_comparison.py",
        "test_shuffle_variance_reduction.py",
        "test_strat_diff.py",
        "test_targeted_shift.py",
        "test_threeway.py",
        "test_tm_baseline.py",
        "test_tm_building_blocks.py",
        "test_tm_microsteps.py",
        "test_tm_recession_single.py",
    ]
]
