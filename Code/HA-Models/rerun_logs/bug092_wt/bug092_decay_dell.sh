#!/bin/bash
set -u; K=${1:-0}; REPO=/home/shared/github/llorracc/HAFiscal-Latest; HA=$REPO/Code/HA-Models; PY=$REPO/.venv/bin/python; OUT=$HA/rerun_logs/bug092_wt; cd $HA
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_WORLD=default HAFISCAL_POLICY_STORE_REQUIRE=0 JAX_PLATFORMS=cpu HAFISCAL_SOLVE_ACCEL=newton2d HAFISCAL_NEWTON2D_KERNEL=numba
echo "=== decay K=$K start $(date +%H:%M:%S)"; env HAFISCAL_MC_WEIGHTED_TAIL=$K $PY bug092_warmup_decay_probe.py $OUT/decay_K$K.json > $OUT/decay_K$K.log 2>&1; echo "=== decay K=$K end rc=$? $(date +%H:%M:%S)"; grep "^t=" $OUT/decay_K$K.log | cut -c1-140; grep -h Traceback -A6 $OUT/decay_K$K.log | tail -6; echo "DECAY-$K DONE"
