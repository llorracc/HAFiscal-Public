#!/bin/bash
# Ladder extension (dell, 17:25): (1) six more seeds at N=24000 to test the +0.10% taxcut_rec_AD gap; (2) an N=96000 rung
# (seeds 0..5), one battery at a time (memory: the Baseline as-corrected battery runs alongside).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_DUR_WORKERS=1 HAFISCAL_QUIET_BETADISTR=1
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
w6() { tag=$1; K=$2; N=$3; shift 3; stamp "w6[$tag N=$N] seed $K start"; env "$@" $PY run_welfare6_parallel.py --parametrization HS_Only --seed-offset $K --agent-count-total $N --max-cpu-slots 3 --out-dir welfare6_scenario_results_HS_Only_${tag}_N${N}_seed$K --table-dir Tables/HS_Only_${tag}_N${N}_seed$K > $LOG/w6_${tag}_N${N}_seed$K.log 2>&1; stamp "w6[$tag N=$N] seed $K end rc=$? miss=$(grep -c 'MISS at' $LOG/w6_${tag}_N${N}_seed$K.log)"; }
for K in 6 8 10; do
  w6 ac_paper $K 24000 HAFISCAL_WORLD=as-corrected HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_MC_SHUFFLE=0 & w6 ac_pkg $K 24000 HAFISCAL_WORLD=as-corrected & wait
  w6 ac_paper $((K+1)) 24000 HAFISCAL_WORLD=as-corrected HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_MC_SHUFFLE=0 & w6 ac_pkg $((K+1)) 24000 HAFISCAL_WORLD=as-corrected & wait
done
stamp "N=24000 seeds 6-11 done"
for K in 0 1 2 3 4 5; do
  w6 ac_paper $K 96000 HAFISCAL_WORLD=as-corrected HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_MC_SHUFFLE=0
  w6 ac_pkg $K 96000 HAFISCAL_WORLD=as-corrected
done
echo "P7B LADDER MORE DONE $(date +%H:%M:%S)"
