#!/bin/bash
# P21 on ccarroll-m5 (owner ruling 2026-08-27 12:10: welfare_engine default hybrid -> hark): the default world's uiB column
# (history policy) under the NEW default: hark + sharing + weighted-tail panel. Waits for this machine's P18, then fetches
# dell's HEAD (the flip), republishes the uiB equilibria under the current keys (5a, deterministic; identity check against
# the 13:24 table), then seeds 0..4 -> Tables/Baseline_uiB_hark_seed*, band.
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
LOG=$HOME/ui_ext_20260826
until grep -q "P18 M5 DONE" $HOME/p18_m5.out 2>/dev/null; do sleep 120; done
git -C $W checkout -q -- . ; git -C $W fetch -q ssh://jhu-dell/home/shared/github/llorracc/HAFiscal-Latest 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC 2>&1 | tail -1; git -C $W checkout -q --detach FETCH_HEAD
echo "P18 finished; P21 at $(git -C $W rev-parse --short HEAD) $(date +%H:%M:%S)"; cd $FPC
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=history
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
T0=$(date +%s); stamp "5a[uiB republish] start"; env HAFISCAL_FIGS_SUFFIX=_uiB_repub $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_uiB_repub.log 2>&1; rc=$?
stamp "5a[uiB republish] end rc=$rc wall=$(( ($(date +%s)-T0)/60 ))min"; diff <(grep "Multiplier\|Share" Tables/Baseline_uiB/Multiplier_candidate.tex) <(grep "Multiplier\|Share" Tables/Baseline_uiB_repub/Multiplier_candidate.tex) > /dev/null && echo "   republished uiB table IDENTICAL" || echo "   WARNING: republished uiB table differs"; [ $rc -eq 0 ] || exit 10
for K in 0 1 2 3 4; do T1=$(date +%s); stamp "w6[uiB_hark] seed $K start"; $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_uiB_hark_seed$K --table-dir Tables/Baseline_uiB_hark_seed$K > $LOG/w6_uiB_hark_seed$K.log 2>&1; stamp "w6[uiB_hark] seed $K end rc=$? wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_uiB_hark_seed$K 2>/dev/null | wc -l | tr -d " ")"; grep -h "FAIL rc=\|MISS " $LOG/w6_uiB_hark_seed$K.log | head -2; done
stamp "band[uiB_hark]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_uiB_hark_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_uiB_hark_S5_seed_band.tex 2>&1 | tail -11
echo "P21 M5 DONE $(date +%H:%M:%S)"
