#!/bin/bash
# BUG-092 weighted-tail sampler, gates 0+1 (17:30): Baseline default world, K=0 (control) vs K=200 (q=0.01).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; HA=$REPO/Code/HA-Models; PY=$REPO/.venv/bin/python; OUT=$HA/rerun_logs/bug092_wt; cd $HA
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_WORLD=default
export HAFISCAL_POLICY_STORE_REQUIRE=0 JAX_PLATFORMS=cpu HAFISCAL_SOLVE_ACCEL=newton2d HAFISCAL_NEWTON2D_KERNEL=numba
K=${1:-0}; tag=wt_K$K; echo "=== $tag start $(date +%H:%M:%S)"
env HAFISCAL_MC_WEIGHTED_TAIL=$K $PY bug092_weighted_tail_probe.py Baseline $OUT/$tag.json > $OUT/$tag.log 2>&1; rc=$?
echo "=== $tag end $(date +%H:%M:%S) rc=$rc"; grep -E "^\[probe\]|^\[weighted-tail\]" $OUT/$tag.log | head -40 | cut -c1-200; grep -h "Traceback" -A8 $OUT/$tag.log | tail -8
echo "WT-PROBE-$K DONE $(date +%H:%M:%S)"
