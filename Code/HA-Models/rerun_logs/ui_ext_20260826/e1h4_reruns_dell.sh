#!/bin/bash
# Reruns after the 11:35 systemd-oomd wipe of the tmux scope (which killed the e1h and p29d launchers mid-seed):
# Baseline plainH seeds 3 and 4 (the Econ-1 reference / Econ-2 shared arm), then Rfree_1015 seeds 0 and 1 (the appendix
# config whose 5a equilibria were re-keyed, BUG-096). Sequential through runq (dell battery capacity 1). Recomputes both
# S bands and appends the marker the e1h2 gate waits for.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python; HA=$REPO/Code/HA-Models
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC; source $HA/launch_helpers.sh
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
for K in 2 3 4; do T1=$(date +%s); stamp "w6[Baseline uiA plainH] seed $K start (rerun; BUG-098)"
  runw6 --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_uiA_plainH_seed$K --table-dir Tables/Baseline_uiA_plainH_seed$K > $LOG/w6_Baseline_uiA_plainH_seed${K}_rerun.log 2>&1; rc=$?
  stamp "w6[Baseline uiA plainH] seed $K end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_uiA_plainH_seed$K 2>/dev/null | wc -l)"; grep -h "FAIL rc=" $LOG/w6_Baseline_uiA_plainH_seed${K}_rerun.log | head -2; done
stamp "band[uiA plainH S=5]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_uiA_plainH_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_uiA_plainH_S5_seed_band.tex 2>&1 | tail -11
echo "E1H BASELINE plainH DONE $(date +%H:%M:%S) (reruns of seeds 3-4 via e1h4)" | tee -a $LOG/e1h_baseline.out
NAME=Rfree_1015
for K in 0 1 2; do T1=$(date +%s); stamp "w6[$NAME] seed $K start (rerun; BUG-098)"
  runw6 --parametrization $NAME --seed-offset $K --out-dir welfare6_scenario_results_${NAME}_seed$K --table-dir Tables/${NAME}_seed$K > $LOG/w6_${NAME}_seed${K}_rerun.log 2>&1; rc=$?
  stamp "w6[$NAME] seed $K end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/${NAME}_seed$K/*.tex 2>/dev/null | wc -l)"; grep -h "FAIL rc=\|MISS " $LOG/w6_${NAME}_seed${K}_rerun.log | head -2; done
stamp "band[$NAME S=3]"; $PY compute_welfare6_se_table.py --summaries Tables/${NAME}_seed{0,1,2}/welfare6_parallel_summary.json --out $LOG/welfare6_${NAME}_S3_seed_band.tex 2>&1 | tail -4
echo "E1H4 RERUNS DONE $(date +%H:%M:%S)"
