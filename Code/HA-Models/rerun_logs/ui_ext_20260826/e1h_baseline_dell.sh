#!/bin/bash
# Econ-1 Baseline arms (2026-08-28 10:00): S = 5 CRN-paired batteries under sharing (default world, paper's UI window; the
# shared equilibria of Tables/Baseline_uiA), one battery slot, SEQUENTIAL (two Baseline batteries + the 5a would press the
# 32 GB cgroup). Arms are read from e1h_queue.txt, one per line: "<MODE> [ENV=VAL ...]"; a line "END" stops the launcher.
#   plainH                                        the certified engine (Hamilton rounding)      -> Tables/Baseline_uiA_plainH_seed*
#   plainM HAFISCAL_SHUFFLE_MRKV_ROUNDING=madow   the plain path with Madow rounding
#   pstratM HAFISCAL_SHUFFLE_MRKV_STRATA=p:5      the income-strata lever (Madow on the strata path)
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python; HA=$REPO/Code/HA-Models
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; Q=$LOG/e1h_queue.txt; cd $FPC; source $HA/launch_helpers.sh
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
n=0
while :; do
  line=$(sed -n "$((n+1))p" $Q 2>/dev/null)
  if [ -z "$line" ]; then sleep 30; continue; fi
  n=$((n+1)); [ "$line" = "END" ] && break
  set -- $line; MODE=$1; shift
  unset HAFISCAL_SHUFFLE_MRKV_STRATA HAFISCAL_SHUFFLE_MRKV_ROUNDING HAFISCAL_MC_STRATIFY_UNEMP
  for kv in "$@"; do export "$kv"; done
  stamp "arm $MODE env: $*"
  for K in 0 1 2 3 4; do T1=$(date +%s); stamp "w6[Baseline uiA $MODE] seed $K start"
    runw6 --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_uiA_${MODE}_seed$K --table-dir Tables/Baseline_uiA_${MODE}_seed$K > $LOG/w6_Baseline_uiA_${MODE}_seed$K.log 2>&1; rc=$?
    stamp "w6[Baseline uiA $MODE] seed $K end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_uiA_${MODE}_seed$K 2>/dev/null | wc -l)"; grep -h "FAIL rc=\|MISS at\|equilibri.*not" $LOG/w6_Baseline_uiA_${MODE}_seed$K.log | head -2; done
  stamp "band[uiA $MODE S=5]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_uiA_${MODE}_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_uiA_${MODE}_S5_seed_band.tex 2>&1 | tail -11
  echo "E1H BASELINE $MODE DONE $(date +%H:%M:%S)"
done
echo "E1H BASELINE QUEUE DONE $(date +%H:%M:%S)"
