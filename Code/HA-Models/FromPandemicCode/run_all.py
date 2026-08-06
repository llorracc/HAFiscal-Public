#!/usr/bin/env python
"""LEGACY two-pass runner: TM for multipliers, then the retired hybrid
welfare6 path.

Usage:
    python run_all.py                  # Reduced_Run (3 types, fast)
    python run_all.py --baseline       # Baseline (21 types, paper scale)

The CANONICAL pipeline is do_all.py (Step 5a = AggFiscalMAIN_reduced.py
--baseline for TM multipliers; Step 5b = run_welfare6_parallel.py --baseline
for MC welfare-6). This runner predates that split and its Pass 2 calls
run_hybrid_welfare6.py, retired 2026-06-12 (see its banner).

  Pass 1 (TM): Multiplier tables, cumulative multiplier figures, AD effects.
    Deterministic, ~30 min for Baseline.

  Pass 2 (MC): Welfare6 table via the legacy hybrid runner. NOTE: since the
    2026-06-10 canonical defaults (EstimParameters.py), this MC runs with
    shuffle ON (stratified Mrkv transition) unless HAFISCAL_QE_FIDELITY=1 —
    not the original "no shuffle" configuration this docstring once claimed.
    ~0.5% SE at N=10K, ~5 hours for Baseline with AD.

The welfare6 metric requires individual-level matching across experiments
(same agent i in policy vs base), which TM cannot provide. MC with CRN
gives precise welfare6 because idiosyncratic noise cancels in the
treatment effect Δu. See history/20260412-welfare6-TM-analysis.md.
"""

import os
import sys
import subprocess

script_dir = os.path.dirname(os.path.abspath(__file__))
python = sys.executable

# Pass through all command-line args
args = sys.argv[1:]

# Pass 1: TM multipliers and figures
print("=" * 60)
print("Pass 1: TM multipliers, figures, AD effects")
print("=" * 60)
cmd1 = [python, os.path.join(script_dir, "AggFiscalMAIN_reduced.py")] + args
env1 = os.environ.copy()
env1["HAFISCAL_SIM_METHOD"] = "TM"
env1["MPLBACKEND"] = "Agg"
ret1 = subprocess.run(cmd1, env=env1)
if ret1.returncode != 0:
    print(f"Pass 1 failed with exit code {ret1.returncode}")
    sys.exit(ret1.returncode)

# Pass 2: MC welfare6
print()
print("=" * 60)
print("Pass 2: MC welfare6 (canonical CRN + stratified-shuffle; QE_FIDELITY=1 = no-shuffle)")
print("=" * 60)
cmd2 = [python, os.path.join(script_dir, "run_hybrid_welfare6.py")] + args
env2 = os.environ.copy()
env2["MPLBACKEND"] = "Agg"
ret2 = subprocess.run(cmd2, env=env2)
if ret2.returncode != 0:
    print(f"Pass 2 failed with exit code {ret2.returncode}")
    sys.exit(ret2.returncode)

print()
print("=" * 60)
print("All done.")
print("=" * 60)
