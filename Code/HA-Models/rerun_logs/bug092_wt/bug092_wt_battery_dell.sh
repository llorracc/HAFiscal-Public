#!/bin/bash
# BUG-092 weighted-tail sampler, gate 2 + cells: the welfare battery (seed 0) on the WEIGHTED panel, measuring the
# B (doob) equilibria (store policy_store_bug093_qdoob, SHARE=1). Usage: bug092_wt_battery_dell.sh <K> [seed]
set -u
K=${1:?K}; SEED=${2:-0}; tag=wtK${K}
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/bug092_wt/battery_$tag; mkdir -p $LOG; cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_WORLD=default
export HAFISCAL_AD_EQUILIBRIUM_SHARE=1 HAFISCAL_POLICY_STORE_DIR=$HOME/.cache/hafiscal/policy_store_bug093_qdoob HAFISCAL_TM_Q_METHOD=doob JAX_PLATFORMS=cpu
export HAFISCAL_MC_WEIGHTED_TAIL=$K
echo "=== welfare[default, SHARE=1, doob, $tag] seed $SEED start $(date +%H:%M:%S)"
$PY run_welfare6_parallel.py --baseline --seed-offset $SEED --out-dir welfare6_scenario_results_Baseline_${tag}_seed$SEED --table-dir Tables/Baseline_${tag}_seed$SEED > $LOG/w6_${tag}_seed$SEED.log 2>&1; rc=$?
echo "=== welfare seed $SEED end rc=$rc tables=$(ls Tables/Baseline_${tag}_seed$SEED 2>/dev/null | wc -l) $(date +%H:%M:%S)"
d=welfare6_parallel_logs/Baseline$([ $SEED = 0 ] || echo _seed$SEED); mkdir -p $LOG/w6logs_seed$SEED; cp -R $d/. $LOG/w6logs_seed$SEED/ 2>/dev/null
echo "   policy-store hits=$(grep -rh 'policy-store\] HIT' $d | wc -l) miss=$(grep -rl 'MISS at' $d | wc -l) | equilibrium HIT=$(grep -rh 'ad-equilibrium\] HIT' $d | wc -l) skipped-loops=$(grep -rh 'AD loop SKIPPED' $d | wc -l) | weighted-tail lines=$(grep -rh '^\[weighted-tail\]' $d | wc -l)"
grep -h "FAIL\|Traceback" $LOG/w6_${tag}_seed$SEED.log | head -3
echo "WT-BATTERY-$tag-$SEED DONE $(date +%H:%M:%S)"
