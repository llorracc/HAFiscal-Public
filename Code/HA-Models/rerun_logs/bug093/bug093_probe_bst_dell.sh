#!/bin/bash
# BUG-093 probe arm 4 (13:35): the minimal consistent fix, tested with ZERO code change — HAFISCAL_TM_Q_METHOD=bst
# makes compute_baseline_tm_data start the experiments from the plain Q-kernel ergodic, i.e. the SAME object
# run_experiment_tm uses for the base level and the same kernel propagate_experiment_tm_a advances with.
# Expect null/base == 1.0000 at every atom and t. Solver-accel flags set (solver_accel.py's setdefaults), so the
# S=252 atoms HIT 5a's store entries instead of cold-solving (arm 1 lesson).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; HA=$REPO/Code/HA-Models; PY=$REPO/.venv/bin/python
OUT=$HA/rerun_logs/bug093; cd $HA
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
export HAFISCAL_POLICY_STORE_REQUIRE=0 HAFISCAL_WELFARE6_TM_INIT=0 JAX_PLATFORMS=cpu
export HAFISCAL_SOLVE_ACCEL=newton2d HAFISCAL_NEWTON2D_KERNEL=numba
tag=Baseline_default_qbst; echo "=== $tag start $(date +%H:%M:%S)"
env HAFISCAL_WORLD=default HAFISCAL_TM_Q_METHOD=bst $PY bug093_null_experiment_probe.py Baseline $OUT/$tag.json > $OUT/$tag.log 2>&1; rc=$?
echo "=== $tag end $(date +%H:%M:%S) rc=$rc"; grep -A40 "^\[probe\] .* world=" $OUT/$tag.log | head -34; grep -h "Traceback" -A6 $OUT/$tag.log | tail -6
echo "store: $(grep -c 'policy-store\] HIT' $OUT/$tag.log) HIT / $(grep -c 'policy-store\] SAVED' $OUT/$tag.log) SAVED"
echo "PROBE-BST DONE $(date +%H:%M:%S)"
