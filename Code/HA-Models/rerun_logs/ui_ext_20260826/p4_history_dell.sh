#!/bin/bash
# P4 of plans/20260826-0800h_ui-extension-calendar-window-encoding_plan.md (dell, 2026-08-26): the default world under
# Improvement B (HAFISCAL_UI_EXTENSION_POLICY=history, EXPLICIT env so the catalog is not edited while P3 runs; the
# catalog flip to canonical='history' follows P3 and yields the same bytes -- setdefault vs explicit is the same value).
# Waits for P3's default-world multiplier program to finish (its battery + the as-corrected arm then overlap with these:
# ~16 + 7 processes at a time, ~40 GB), then: Step 5a (TM a-indexed; store + equilibria) -> Step 5b seeds 0,1,2 -> band.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826
EXPECT=${1:?expected short HEAD}; HEAD=$(git -C $REPO rev-parse --short HEAD)
echo "main checkout at $HEAD (expected $EXPECT) $(date +%H:%M:%S)"; [ "$HEAD" = "$EXPECT" ] || { echo "ABORTED: HEAD mismatch"; exit 9; }
until grep -q "P3 BASELINE DELL DONE" $LOG/p3.out 2>/dev/null; do sleep 60; done
echo "P3 finished; starting P4 $(date +%H:%M:%S)"
cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1
export HAFISCAL_UI_EXTENSION_POLICY=history
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
stamp "multiplier[default/history] start"; env HAFISCAL_WORLD=default HAFISCAL_FIGS_SUFFIX=_uiB $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_default_history.log 2>&1; rc=$?
stamp "multiplier[default/history] end rc=$rc"; grep -h "ui-encoding\]" $LOG/mult_default_history.log | head -1; grep "AD effect)\|expenditure during" Tables/Baseline_uiB/Multiplier_candidate.tex 2>/dev/null; [ $rc -eq 0 ] || exit 10
for K in 0 1 2; do stamp "welfare[default/history] seed $K start"; env HAFISCAL_WORLD=default $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_uiB_seed$K --table-dir Tables/Baseline_uiB_seed$K > $LOG/w6_uiB_seed$K.log 2>&1; rc=$?; stamp "welfare[default/history] seed $K end rc=$rc tables=$(ls Tables/Baseline_uiB_seed$K 2>/dev/null | wc -l) miss-errors=$(grep -c 'MISS at' $LOG/w6_uiB_seed$K.log)"; done
stamp "band[uiB]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_uiB_seed0/welfare6_parallel_summary.json Tables/Baseline_uiB_seed1/welfare6_parallel_summary.json Tables/Baseline_uiB_seed2/welfare6_parallel_summary.json --out $LOG/welfare6_uiB_seed_band.tex 2>&1 | tail -12
echo "P4 HISTORY DELL DONE $(date +%H:%M:%S)"
