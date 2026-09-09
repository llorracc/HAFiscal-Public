#!/bin/bash
# P29d (2026-08-28 10:30): re-run the Rfree_1015 welfare seeds that failed under P29c because the 5a's four equilibria were
# published under a stale solver-source key (BUG-096); after `rekey_equilibria.py --apply` they HIT. Seeds given as args
# (default 0 1); through runq. Same env as p29c.
set -u
SEEDS=${@:-0 1}
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python; HA=$REPO/Code/HA-Models
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC; source $HA/launch_helpers.sh
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
NAME=Rfree_1015
for K in $SEEDS; do T1=$(date +%s); stamp "w6[$NAME] seed $K start (rerun)"
  runw6 --parametrization $NAME --seed-offset $K --out-dir welfare6_scenario_results_${NAME}_seed$K --table-dir Tables/${NAME}_seed$K > $LOG/w6_${NAME}_seed${K}_rerun.log 2>&1; rc=$?
  stamp "w6[$NAME] seed $K end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/${NAME}_seed$K/*.tex 2>/dev/null | wc -l)"; grep -h "FAIL rc=\|MISS " $LOG/w6_${NAME}_seed${K}_rerun.log | head -2; done
echo "P29D DELL DONE $(date +%H:%M:%S)"
