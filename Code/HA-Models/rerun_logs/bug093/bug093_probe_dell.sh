#!/bin/bash
# BUG-093 first probe (owner go-ahead 2026-08-25 ~12:55): the TM's NULL experiment per atom, three arms
# in one memory-capped unit: Baseline default (uncapped) -> Baseline HAFISCAL_T_AGE=200 -> Reduced_Run
# default. Expect the uncapped Baseline arm to show null/base != 1 at the most patient atoms and both
# other arms to be 1.0000 (the 5a artifacts return to base there). Same grids as 5a (mCount 100, Q).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; HA=$REPO/Code/HA-Models; PY=$REPO/.venv/bin/python
OUT=$HA/rerun_logs/bug093; cd $HA
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
export HAFISCAL_POLICY_STORE_REQUIRE=0 HAFISCAL_WELFARE6_TM_INIT=0 JAX_PLATFORMS=cpu
# run TAG PARAMETRIZATION [ENV=...]: the parametrization is explicit (13:58 fix: ${tag%%_*} cut Reduced_Run to "Reduced",
# which fell through to Baseline — the first arm-3 run was a bit-identical duplicate of arm 1)
run() { tag=$1; param=$2; shift 2; echo "=== $tag start $(date +%H:%M:%S)"; env "$@" $PY bug093_null_experiment_probe.py $param $OUT/$tag.json > $OUT/$tag.log 2>&1; rc=$?; echo "=== $tag end $(date +%H:%M:%S) rc=$rc"; grep -A40 "^\[probe\] .* world=" $OUT/$tag.log | head -34; grep -h "Traceback" -A6 $OUT/$tag.log | tail -6; }
export HAFISCAL_SOLVE_ACCEL=newton2d HAFISCAL_NEWTON2D_KERNEL=numba   # solver_accel.py's setdefaults: store HITs instead of cold solves
run Baseline_default    Baseline    HAFISCAL_WORLD=default
run Baseline_capped200  Baseline    HAFISCAL_WORLD=default HAFISCAL_T_AGE=200
run Reduced_Run_default Reduced_Run HAFISCAL_WORLD=default
echo "PROBE DONE $(date +%H:%M:%S)"
