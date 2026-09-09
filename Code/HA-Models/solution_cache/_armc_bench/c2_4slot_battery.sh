#!/bin/bash
# C2 (plan 20260807-0919h): 4-slot COLD Reduced_Run battery under
# newton2d — the slot-count arm. Differs from the 2-slot (200 min) and
# 3-slot (190 min) references in ONE thing: HAFISCAL_MAX_CPU_SLOTS=4
# (envelope-11 default would plan 3). Warm-payload OFF (C3 adds it).
# Gates: rc=0, 12/12 cells, 0 fallbacks, peak < MemoryHigh 40, welfare
# corridor vs flag-off baselines, wall vs 190/200-min references.
TAG=${1:-c2_4slot}
SP=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/_armc_bench
FP=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode
PY=/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
L=$FP/welfare6_parallel_logs/Baseline
mkdir -p "$L/_pre_${TAG}_backup" && (mv "$L"/*.log "$L/_pre_${TAG}_backup/" 2>/dev/null || true)
cd "$FP" || exit 1
/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/mem_guard_run.sh env -i HOME="$HOME" PATH=/usr/bin:/bin USER=econ-ark LANG=C.UTF-8 \
  PYTHONUNBUFFERED=1 \
  HAFISCAL_SOLVE_ACCEL=newton2d HAFISCAL_SOLVE_ACCEL_VERBOSE=1 HAFISCAL_SOLVE_ACCEL_CENSUS=1 \
  HAFISCAL_MAX_CPU_SLOTS=4 \
  "$PY" run_welfare6_parallel.py --baseline \
  --out-dir "$SP/${TAG}_out" --table-dir "$SP/${TAG}_tables" \
  > "$SP/${TAG}.log" 2>&1
rc=$?
echo "battery rc=$rc"
grep -E "Wall clock|Longest" "$SP/${TAG}.log"
echo "peak children-total: $(grep -o 'children total [0-9.]* GiB' "$SP/${TAG}.log" | awk '{print $3}' | sort -rn | head -1) GiB (High=40)"
echo "fallbacks: $(grep -hc 'falling back to plain' "$L"/*.log 2>/dev/null | paste -sd+ | bc)"
