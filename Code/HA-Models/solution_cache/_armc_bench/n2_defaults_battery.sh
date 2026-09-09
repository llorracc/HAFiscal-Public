#!/bin/bash
# Overnight 2026-08-07: FLAG-LESS defaults-validation battery — no
# HAFISCAL_SOLVE_ACCEL/KERNEL/WARM flags at all; the entry-point defaults
# (rulings R1-R3) must engage on their own. Census on (diagnostic only).
# Gates: rc=0, 12/12, 0 fallbacks, engagement present in every cell,
# corridor vs C3 (same engines, explicitly flagged there), peak < High.
TAG=${1:-n2_defaults}
SP=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/_armc_bench
FP=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode
PY=/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
L=$FP/welfare6_parallel_logs/Baseline
mkdir -p "$L/_pre_${TAG}_backup" && (mv "$L"/*.log "$L/_pre_${TAG}_backup/" 2>/dev/null || true)
cd "$FP" || exit 1
/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/mem_guard_run.sh env -i HOME="$HOME" PATH=/usr/bin:/bin USER=econ-ark LANG=C.UTF-8 \
  PYTHONUNBUFFERED=1 HAFISCAL_SOLVE_ACCEL_CENSUS=1 \
  "$PY" run_welfare6_parallel.py --baseline \
  --out-dir "$SP/${TAG}_out" --table-dir "$SP/${TAG}_tables" \
  > "$SP/${TAG}.log" 2>&1
rc=$?
echo "battery rc=$rc"
grep -a -E "Wall clock|Longest" "$SP/${TAG}.log"
echo "peak: $(grep -a -o 'children total [0-9.]* GiB' "$SP/${TAG}.log" | awk '{print $3}' | sort -rn | head -1) GiB"
echo "fallbacks: $(grep -hc 'falling back to plain' "$L"/*.log 2>/dev/null | paste -sd+ | bc)"
echo "engagement: $(grep -h 'warm_started=True' "$L"/*.log 2>/dev/null | wc -l) warm / $(grep -h -c 'method=newton2d' "$L"/*.log 2>/dev/null | paste -sd+ | bc) newton2d-lines"
echo "N2-DEFAULTS-DONE rc=$rc"
