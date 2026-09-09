#!/bin/bash
# P31 (dell; rebalanced 2026-08-28 05:05): two appendix configs under the HISTORY UI policy (B), SEQUENTIAL after both P29 streams
# (co-running 5a arms on dell oversubscribe the box: ~4 h each instead of ~70 min); Rfree_1015/ADElas moved to m5 (p31_m5.sh). Outputs Tables/<NAME>_histB*, so the appendix can follow whichever policy the main tables adopt.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC; source $LOG/p29_common.sh
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=history
cfgB() { NAME=$1; TAG=${NAME}_histB
  T0=$(date +%s); stamp "5a[$TAG] start"; HAFISCAL_FIGS_SUFFIX=_histB $PY AggFiscalMAIN_reduced.py --parametrization $NAME > $LOG/mult_$TAG.log 2>&1; rc=$?
  stamp "5a[$TAG] end rc=$rc wall=$(( ($(date +%s)-T0)/60 ))min"; grep "AD effect)\|expenditure during" Tables/$TAG/Multiplier_candidate.tex 2>/dev/null; [ $rc -eq 0 ] || return
  for K in 0 1 2; do T1=$(date +%s); stamp "w6[$TAG] seed $K start"
    $PY run_welfare6_parallel.py --parametrization $NAME --seed-offset $K --out-dir welfare6_scenario_results_${TAG}_seed$K --table-dir Tables/${TAG}_seed$K > $LOG/w6_${TAG}_seed$K.log 2>&1; rc=$?
    stamp "w6[$TAG] seed $K end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/${TAG}_seed$K/*.tex 2>/dev/null | wc -l)"; done
  stamp "band[$TAG]"; $PY compute_welfare6_se_table.py --summaries Tables/${TAG}_seed{0,1,2}/welfare6_parallel_summary.json --out $LOG/welfare6_${TAG}_S3_seed_band.tex 2>&1 | tail -n 4; }
until grep -q "P29B DELL DONE" $LOG/p29b.out 2>/dev/null && grep -q "P29A DELL DONE" $LOG/p29a.out 2>/dev/null; do sleep 120; done
echo "P29 finished; P31 starting at $(git -C $REPO rev-parse --short HEAD) $(date +%H:%M:%S)"
cfgB Rfree_1005; cfgB Rspell_4
echo "P31 DELL DONE $(date +%H:%M:%S)"
