#!/bin/bash
# P21 (dell; owner ruling 2026-08-27 12:10 -- welfare_engine default flipped hybrid -> hark): re-run the default world's uiA
# column (paper's UI window) under the NEW default: hark engine + AD-equilibrium sharing + the weighted-tail panel.
# Equilibria: the P17 republish (current keys). Seeds 0..4 -> Tables/Baseline_uiA_hark_seed*, band. Waits for P20 (the
# true-original arm) so the two never co-run on dell.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
until grep -q "P20 DELL DONE" $LOG/p20.out 2>/dev/null; do sleep 120; done
echo "P20 finished; starting P21 at HEAD $(git -C $REPO rev-parse --short HEAD) $(date +%H:%M:%S)"
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
for K in 0 1 2 3 4; do T1=$(date +%s); stamp "w6[uiA_hark] seed $K start"; $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_uiA_hark_seed$K --table-dir Tables/Baseline_uiA_hark_seed$K > $LOG/w6_uiA_hark_seed$K.log 2>&1; stamp "w6[uiA_hark] seed $K end rc=$? wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_uiA_hark_seed$K 2>/dev/null | wc -l)"; grep -h -m1 "welfare_engine\]" $LOG/w6_uiA_hark_seed$K.log | cut -c1-120; grep -h "FAIL rc=\|MISS " $LOG/w6_uiA_hark_seed$K.log | head -2; done
stamp "band[uiA_hark]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_uiA_hark_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_uiA_hark_S5_seed_band.tex 2>&1 | tail -11
echo "P21 DELL DONE $(date +%H:%M:%S)"
