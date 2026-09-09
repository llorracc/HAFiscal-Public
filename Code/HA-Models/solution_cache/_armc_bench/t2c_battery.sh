#!/bin/bash
# T2c (owner acceptance, plan §C5): cold Reduced_Run battery under
# HAFISCAL_SOLVE_ACCEL=newton2d; cell-level compare vs the cold flag-off
# baseline (flagoff_warm_base_out). newton2d keys the solution cache, so
# solve-bearing caches MISS automatically (genuinely cold on the solver).
TAG=${1:-t2c_newton2d}; METHOD=${2:-newton2d}
SP=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/_armc_bench
FP=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode
PY=/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
H=$FP/welfare6_scenario_results_Baseline_hybrid
L=$FP/welfare6_parallel_logs/Baseline
mkdir -p "$L/_pre_${TAG}_backup" && (mv "$L"/*.log "$L/_pre_${TAG}_backup/" 2>/dev/null || true)
cd "$FP" || exit 1
/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/mem_guard_run.sh env -i HOME="$HOME" PATH=/usr/bin:/bin USER=econ-ark LANG=C.UTF-8 \
  PYTHONUNBUFFERED=1 \
  HAFISCAL_SOLVE_ACCEL="$METHOD" HAFISCAL_SOLVE_ACCEL_VERBOSE=1 \
  "$PY" run_welfare6_parallel.py --baseline \
  --out-dir "$SP/${TAG}_out" --table-dir "$SP/${TAG}_tables" \
  > "$SP/${TAG}.log" 2>&1
rc=$?
echo "battery rc=$rc  (method=$METHOD)"
grep -E "Wall clock|Longest" "$SP/${TAG}.log"
echo "=== accel engagement ==="
grep -h "solve_accel" "$L"/*.log 2>/dev/null | sort | uniq -c | sort -rn | head -6
grep -hc "falling back to plain" "$L"/*.log 2>/dev/null | paste -sd+ | bc | xargs echo "fallback count:"
echo "=== cell-level compare vs t0 cold baseline (rel diffs; NOT expected identical) ==="
for f in base Check UI TaxCut recession recessionUI recessionCheck recessionTaxCut recession_AD recessionUI_AD recessionCheck_AD recessionTaxCut_AD; do
  echo "--- $f"
  "$PY" "$H/pkl_diff.py" "$SP/flagoff_warm_base_out/$f.pkl" "$SP/${TAG}_out/$f.pkl" 2>&1 | tail -3
done
