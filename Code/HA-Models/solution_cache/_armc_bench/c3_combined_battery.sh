#!/bin/bash
# C3 (plan 20260807-0919h): the COMBINED arm — cold Reduced_Run battery
# under newton2d + numba kernel + warm-payload threading, 3 slots (the
# numba-arm envelope caution: cold numba solo peaked 10.8 vs envelope 11).
# Gates: rc=0, 12/12, 0 fallbacks, peak < MemoryHigh, corridor vs the
# certified cold references (expect ~1e-8 class from the warm seed),
# wall vs C2's 152.3 min / the 190/200 references.
TAG=${1:-c3_combined}
SP=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/_armc_bench
FP=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode
PY=/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
L=$FP/welfare6_parallel_logs/Baseline
mkdir -p "$L/_pre_${TAG}_backup" && (mv "$L"/*.log "$L/_pre_${TAG}_backup/" 2>/dev/null || true)
cd "$FP" || exit 1
/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/mem_guard_run.sh env -i HOME="$HOME" PATH=/usr/bin:/bin USER=econ-ark LANG=C.UTF-8 \
  PYTHONUNBUFFERED=1 \
  HAFISCAL_SOLVE_ACCEL=newton2d HAFISCAL_SOLVE_ACCEL_VERBOSE=1 HAFISCAL_SOLVE_ACCEL_CENSUS=1 \
  HAFISCAL_NEWTON2D_KERNEL=numba HAFISCAL_NEWTON2D_WARM_PAYLOAD=1 \
  HAFISCAL_MAX_CPU_SLOTS=3 \
  "$PY" run_welfare6_parallel.py --baseline \
  --out-dir "$SP/${TAG}_out" --table-dir "$SP/${TAG}_tables" \
  > "$SP/${TAG}.log" 2>&1
rc=$?
echo "battery rc=$rc"
grep -a -E "Wall clock|Longest" "$SP/${TAG}.log"
echo "peak children-total: $(grep -a -o 'children total [0-9.]* GiB' "$SP/${TAG}.log" | awk '{print $3}' | sort -rn | head -1) GiB (High=40)"
echo "fallbacks: $(grep -hc 'falling back to plain' "$L"/*.log 2>/dev/null | paste -sd+ | bc)"
echo "warm engagement: $(grep -h 'warm_started=True' "$L"/*.log 2>/dev/null | wc -l) True / $(grep -h 'warm_started=False' "$L"/*.log 2>/dev/null | wc -l) False"
