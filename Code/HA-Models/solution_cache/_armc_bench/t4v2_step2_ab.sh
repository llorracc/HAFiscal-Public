#!/bin/bash
# T4 v2 (C3.5): Step-2 objective at the INSTALLED estimates via the
# module's OWN readback pass (HAFISCAL_SKIP_ESTIMATION_OPTIMIZE=1 — skips
# the optimizer, runs calcAllResults, which loads the calib-suffixed
# estimates and evaluates betas_obj_func_educ through the canonical
# machinery into AllResults*_candidate). v1's hand-rolled call read the
# UNSUFFIXED estimates file (stale CDC-era betas) and tripped the
# PF-decay guard — the calib-suffix trap, recorded.
SP=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/_armc_bench
FP=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode
PY=/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
MG=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/mem_guard_run.sh
RES=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/Results
cd "$FP" || exit 1

echo "=== T4 ARM A (flag-off) start $(date '+%H:%M') ==="
"$MG" env -i HOME="$HOME" PATH=/usr/bin:/bin USER=econ-ark LANG=C.UTF-8 \
  PYTHONUNBUFFERED=1 HAFISCAL_SKIP_ESTIMATION_OPTIMIZE=1 \
  "$PY" EstimAggFiscalMAIN.py > "$SP/t4v2_A.log" 2>&1
rc_a=$?
mkdir -p "$SP/t4v2_A_out"
cp "$RES"/AllResults*candidate* "$SP/t4v2_A_out/" 2>/dev/null
ls "$RES" | grep -i candidate | head -3 >> "$SP/t4v2_A.log"
echo "T4 ARM A rc=$rc_a done $(date '+%H:%M')"

echo "=== T4 ARM B (newton2d+numba) start $(date '+%H:%M') ==="
"$MG" env -i HOME="$HOME" PATH=/usr/bin:/bin USER=econ-ark LANG=C.UTF-8 \
  PYTHONUNBUFFERED=1 HAFISCAL_SKIP_ESTIMATION_OPTIMIZE=1 \
  HAFISCAL_SOLVE_ACCEL=newton2d HAFISCAL_NEWTON2D_KERNEL=numba \
  HAFISCAL_SOLVE_ACCEL_CENSUS=1 \
  "$PY" EstimAggFiscalMAIN.py > "$SP/t4v2_B.log" 2>&1
rc_b=$?
mkdir -p "$SP/t4v2_B_out"
cp "$RES"/AllResults*candidate* "$SP/t4v2_B_out/" 2>/dev/null
echo "T4 ARM B rc=$rc_b done $(date '+%H:%M')"
echo "T4V2-CHAIN-DONE rcA=$rc_a rcB=$rc_b"
