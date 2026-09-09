#!/bin/bash
# P29c (dell, 2026-08-28 09:00): the three window-policy appendix configs whose dell runs deadlocked or never started
# (Rfree_1015 hung 01:41-08:58, Rspell_4 hung 03:18-07:07 then paused; ADElas not started) — sequential through runq with
# the thread pins (launch_helpers.sh). Then P32 (own-loop 40x) follows via its gate on "P29C DELL DONE".
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python; HA=$REPO/Code/HA-Models
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC; source $HA/launch_helpers.sh
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
cfg() { NAME=$1
  T0=$(date +%s); stamp "5a[$NAME] start"; run5a --parametrization $NAME > $LOG/mult_$NAME.log 2>&1; rc=$?
  stamp "5a[$NAME] end rc=$rc wall=$(( ($(date +%s)-T0)/60 ))min"; grep "AD effect)\|expenditure during" Tables/$NAME/Multiplier_candidate.tex 2>/dev/null; [ $rc -eq 0 ] || return
  for K in 0 1 2; do T1=$(date +%s); stamp "w6[$NAME] seed $K start"
    runw6 --parametrization $NAME --seed-offset $K --out-dir welfare6_scenario_results_${NAME}_seed$K --table-dir Tables/${NAME}_seed$K > $LOG/w6_${NAME}_seed$K.log 2>&1; rc=$?
    stamp "w6[$NAME] seed $K end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/${NAME}_seed$K/*.tex 2>/dev/null | wc -l)"; done
  stamp "band[$NAME]"; $PY compute_welfare6_se_table.py --summaries Tables/${NAME}_seed{0,1,2}/welfare6_parallel_summary.json --out $LOG/welfare6_${NAME}_S3_seed_band.tex 2>&1 | tail -n 4; }
echo "P29c starting at $(git -C $REPO rev-parse --short HEAD) $(date +%H:%M:%S)"
cfg Rfree_1015; cfg Rspell_4; cfg ADElas
echo "P29C DELL DONE $(date +%H:%M:%S)"
