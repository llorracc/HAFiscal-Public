#!/bin/bash
# Rerun of the Baseline plainH seed 3 (killed by systemd-oomd 2026-08-28 11:28, rc=-9 on the AD scenarios); waits for the
# plainH arm to finish, then runs through runq and recomputes the S=5 band.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python; HA=$REPO/Code/HA-Models
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC; source $HA/launch_helpers.sh
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
until grep -q "E1H BASELINE plainH DONE" $LOG/e1h_baseline.out 2>/dev/null; do sleep 60; done
T1=$(date +%s); stamp "w6[Baseline uiA plainH] seed 3 start (rerun)"
runw6 --baseline --seed-offset 3 --out-dir welfare6_scenario_results_Baseline_uiA_plainH_seed3 --table-dir Tables/Baseline_uiA_plainH_seed3 > $LOG/w6_Baseline_uiA_plainH_seed3_rerun.log 2>&1; rc=$?
stamp "w6[Baseline uiA plainH] seed 3 end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_uiA_plainH_seed3 2>/dev/null | wc -l)"
stamp "band[uiA plainH S=5]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_uiA_plainH_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_uiA_plainH_S5_seed_band.tex 2>&1 | tail -11
echo "E1H3 PLAINH SEED3 DONE $(date +%H:%M:%S)"
