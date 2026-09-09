#!/bin/bash
# C3.5 / T3 Step-5a smoke (plan 20260807-0919h): A/B multipliers,
# flag-off vs newton2d+numba, serialized on an idle box. Gate: per-policy
# multiplier deltas vs the 2.89e-3 noise floor (compared interactively
# from the stashed per-arm outputs).
SP=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/_armc_bench
FP=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode
PY=/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
MG=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/mem_guard_run.sh
cd "$FP" || exit 1

echo "=== ARM A (flag-off) start $(date '+%H:%M') ==="
"$MG" env -i HOME="$HOME" PATH=/usr/bin:/bin USER=econ-ark LANG=C.UTF-8 \
  PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 \
  "$PY" AggFiscalMAIN_reduced.py --baseline \
  > "$SP/c35_step5a_A.log" 2>&1
rc_a=$?
mkdir -p "$SP/c35_step5a_A_out"
cp -r Tables/Baseline/. "$SP/c35_step5a_A_out/" 2>/dev/null
cp Figures/Baseline/base_results.csv "$SP/c35_step5a_A_out/" 2>/dev/null
echo "ARM A rc=$rc_a done $(date '+%H:%M')"

echo "=== ARM B (newton2d+numba) start $(date '+%H:%M') ==="
"$MG" env -i HOME="$HOME" PATH=/usr/bin:/bin USER=econ-ark LANG=C.UTF-8 \
  PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 \
  HAFISCAL_SOLVE_ACCEL=newton2d HAFISCAL_NEWTON2D_KERNEL=numba \
  HAFISCAL_SOLVE_ACCEL_CENSUS=1 \
  "$PY" AggFiscalMAIN_reduced.py --baseline \
  > "$SP/c35_step5a_B.log" 2>&1
rc_b=$?
mkdir -p "$SP/c35_step5a_B_out"
cp -r Tables/Baseline/. "$SP/c35_step5a_B_out/" 2>/dev/null
cp Figures/Baseline/base_results.csv "$SP/c35_step5a_B_out/" 2>/dev/null
echo "ARM B rc=$rc_b done $(date '+%H:%M')"
echo "T3-SMOKE-CHAIN-DONE rcA=$rc_a rcB=$rc_b"
