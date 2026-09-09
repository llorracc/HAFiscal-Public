#!/bin/bash
# BUG-092 weighted-tail: E[p] ratio vs PRODUCTION warm-up length (HAFISCAL_WELFARE6_MC_WARMUP) at Baseline default.
set -u; K=${1:?K}; WU=${2:?warmup}; tag=wt_K${K}_wu$WU
REPO=/home/shared/github/llorracc/HAFiscal-Latest; HA=$REPO/Code/HA-Models; PY=$REPO/.venv/bin/python; OUT=$HA/rerun_logs/bug092_wt; cd $HA
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_WORLD=default HAFISCAL_POLICY_STORE_REQUIRE=0 JAX_PLATFORMS=cpu HAFISCAL_SOLVE_ACCEL=newton2d HAFISCAL_NEWTON2D_KERNEL=numba
echo "=== $tag start $(date +%H:%M:%S)"; env HAFISCAL_MC_WEIGHTED_TAIL=$K HAFISCAL_WELFARE6_MC_WARMUP=$WU $PY bug092_weighted_tail_probe.py Baseline $OUT/$tag.json > $OUT/$tag.log 2>&1; rc=$?
echo "=== $tag end rc=$rc $(date +%H:%M:%S)"; grep -E "^\[probe\] (population|base AggCons per)" $OUT/$tag.log | cut -c1-160; grep -h Traceback -A6 $OUT/$tag.log | tail -6; echo "SWEEP-$tag DONE"
