#!/bin/bash
# BUG-093 fix validation (14:20): the null experiment under BOTH consistent constructions, Baseline default
# (uncapped): 'doob' (B: Doob start + p-weighted step; the new module default) and 'bst' (C: plain start + plain
# step). Expect null/base == 1.0000 at every atom under both; recession paths differ (the two Q-marginals weight
# the patient dynasties differently). Solver-accel flags set -> store HITs.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; HA=$REPO/Code/HA-Models; PY=$REPO/.venv/bin/python; OUT=$HA/rerun_logs/bug093; cd $HA
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
export HAFISCAL_POLICY_STORE_REQUIRE=0 HAFISCAL_WELFARE6_TM_INIT=0 JAX_PLATFORMS=cpu HAFISCAL_SOLVE_ACCEL=newton2d HAFISCAL_NEWTON2D_KERNEL=numba
run() { tag=$1; param=$2; shift 2; echo "=== $tag start $(date +%H:%M:%S)"; env "$@" $PY bug093_null_experiment_probe.py $param $OUT/$tag.json > $OUT/$tag.log 2>&1; rc=$?; echo "=== $tag end $(date +%H:%M:%S) rc=$rc"; grep -A10 "^\[probe\] .* world=" $OUT/$tag.log | head -10; grep -h "Traceback" -A8 $OUT/$tag.log | tail -8; }
run fix_Baseline_doob Baseline HAFISCAL_WORLD=default
run fix_Baseline_capped_doob Baseline HAFISCAL_WORLD=default HAFISCAL_T_AGE=200
# (bst arm validated 14:29: null 1.0000, d0 0.9893->0.9997)
echo "PROBE-QM DONE $(date +%H:%M:%S)"
