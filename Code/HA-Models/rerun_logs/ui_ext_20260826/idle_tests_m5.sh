#!/bin/bash
# Idle-box tests on ccarroll-m5 (2026-08-28): A6 bit-identity (parallel_solve_test.py), the A5 gate pair
# (HAFISCAL_LEGACY_TAXCUT_ATOM=1: tax-cut cells move, everything else byte-identical), Econ-4's real dropout stencil.
# Through runq (INTERACTIVE host: the headroom gate defers if the Mac is busy). Sequential.
set -u
REPO=$HOME/GitHub/llorracc/HAFiscal-Latest; HA=$REPO/Code/HA-Models; FPC=$HA/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$HOME/ui_ext_20260826; mkdir -p $LOG; cd $FPC
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 MKL_NUM_THREADS=1
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
echo "idle tests on $(hostname) at $(git -C $REPO rev-parse --short HEAD) $(date +%H:%M:%S)"
T0=$(date +%s); stamp "parallel_solve_test start"; $PY $HA/runq.py --class any -- $PY parallel_solve_test.py > $LOG/idle_parallel_solve_test.log 2>&1; rc=$?
stamp "parallel_solve_test end rc=$rc wall=$(( ($(date +%s)-T0)/60 ))min"; grep -i "identical\|bit\|PASS\|FAIL\|mismatch" $LOG/idle_parallel_solve_test.log | tail -3
T0=$(date +%s); stamp "A5 gate pair start"; cd $HA; $PY runq.py --class any -- $PY step5a_parallel_gate.py --toggle HAFISCAL_LEGACY_TAXCUT_ATOM=1 --expect-changed TaxCut --expect-unchanged '*' --out-base $LOG/g5a > $LOG/idle_a5_gate.log 2>&1; rc=$?
stamp "A5 gate pair end rc=$rc wall=$(( ($(date +%s)-T0)/60 ))min"; grep -E "verdict|PASS|FAIL|IDENTICAL|DIFFERS|NO-MATCH" $LOG/idle_a5_gate.log | tail -12
T0=$(date +%s); stamp "Econ-4 dropout stencil start"; $PY runq.py --class any -- $PY step2_curvature.py --educ 0 --out-dir $LOG/curvature > $LOG/idle_econ4_curvature.log 2>&1; rc=$?
stamp "Econ-4 dropout stencil end rc=$rc wall=$(( ($(date +%s)-T0)/60 ))min"; tail -25 $LOG/idle_econ4_curvature.log
echo "IDLE TESTS M5 DONE $(date +%H:%M:%S)"
