#!/bin/bash
# BUG-093 probe arm 3 (re-run 13:58): Reduced_Run, default world — world/parametrization control (expected null ≈ 1.000).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; HA=$REPO/Code/HA-Models; PY=$REPO/.venv/bin/python; OUT=$HA/rerun_logs/bug093; cd $HA
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
export HAFISCAL_POLICY_STORE_REQUIRE=0 HAFISCAL_WELFARE6_TM_INIT=0 JAX_PLATFORMS=cpu HAFISCAL_SOLVE_ACCEL=newton2d HAFISCAL_NEWTON2D_KERNEL=numba
tag=Reduced_Run_default; echo "=== $tag start $(date +%H:%M:%S)"
env HAFISCAL_WORLD=default $PY bug093_null_experiment_probe.py Reduced_Run $OUT/$tag.json > $OUT/$tag.log 2>&1; rc=$?
echo "=== $tag end $(date +%H:%M:%S) rc=$rc"; grep -A12 "^\[probe\] .* world=" $OUT/$tag.log | head -12; grep -h "Traceback" -A6 $OUT/$tag.log | tail -6
echo "PROBE-RR DONE $(date +%H:%M:%S)"
