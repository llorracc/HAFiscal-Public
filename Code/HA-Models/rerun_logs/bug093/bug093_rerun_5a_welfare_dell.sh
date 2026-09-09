#!/bin/bash
# BUG-093 re-run (owner: "try B and C", no age cap): Step 5a Baseline default world + welfare battery (S=3) under
# BOTH consistent Q-constructions, each with ITS OWN policy/equilibrium store (the equilibrium key is the MODEL,
# so the two arms would otherwise overwrite each other's entries — "last producer wins"):
#   qdoob = HAFISCAL_TM_Q_METHOD=doob (B; the new module default)   qbst = HAFISCAL_TM_Q_METHOD=bst (C)
# Usage: bug093_rerun_5a_welfare_dell.sh <qdoob|qbst>   (run the two arms as separate units, concurrently)
set -u
ARM=${1:?qdoob|qbst}; case $ARM in qdoob) QM=doob;; qbst) QM=bst;; *) echo "bad arm"; exit 2;; esac
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/bug093/rerun_$ARM; mkdir -p $LOG
STORE=$HOME/.cache/hafiscal/policy_store_bug093_$ARM
if [ ! -d $STORE ]; then rsync -a --exclude 'equilibrium/' $HOME/.cache/hafiscal/policy_store/ $STORE/; fi   # policy entries (HITs), no equilibria
cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_WORLD=default
export HAFISCAL_AD_EQUILIBRIUM_SHARE=1 HAFISCAL_POLICY_STORE_DIR=$STORE HAFISCAL_TM_Q_METHOD=$QM JAX_PLATFORMS=cpu
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
echo "main checkout at $(git -C $REPO rev-parse --short HEAD) arm=$ARM q_method=$QM store=$STORE"
stamp "multiplier[default, SHARE=1, $ARM] start"; env HAFISCAL_FIGS_SUFFIX=_$ARM $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_$ARM.log 2>&1; rc=$?; stamp "multiplier end rc=$rc"
grep "Multiplier" Tables/Baseline_$ARM/Multiplier_candidate.tex 2>/dev/null | cut -c1-110
echo "   policy hits=$(grep -c 'policy-store\] HIT' $LOG/mult_$ARM.log) saved=$(grep -c 'policy-store\] SAVED' $LOG/mult_$ARM.log); equilibria SAVED=$(grep -c 'ad-equilibrium\] SAVED' $LOG/mult_$ARM.log)"
grep -h "prescribed AD path" $LOG/mult_$ARM.log | head -4 | cut -c1-140
for K in 0 1 2; do
  stamp "welfare[default, SHARE=1, $ARM] seed $K start"; $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${ARM}_seed$K --table-dir Tables/Baseline_${ARM}_seed$K > $LOG/w6_${ARM}_seed$K.log 2>&1; rc=$?
  stamp "welfare seed $K end rc=$rc tables=$(ls Tables/Baseline_${ARM}_seed$K 2>/dev/null | wc -l)"
  d=welfare6_parallel_logs/Baseline$([ $K = 0 ] || echo _seed$K); mkdir -p $LOG/w6logs_seed$K; cp -R $d/. $LOG/w6logs_seed$K/ 2>/dev/null
  echo "   policy-store hits=$(grep -rh 'policy-store\] HIT' $d | wc -l) saved=$(grep -rh 'policy-store\] SAVED' $d | wc -l) miss=$(grep -rl 'MISS at' $d | wc -l) | equilibrium HIT=$(grep -rh 'ad-equilibrium\] HIT' $d | wc -l) skipped-loops=$(grep -rh 'AD loop SKIPPED' $d | wc -l)"
done
echo "RERUN-$ARM DONE $(date +%H:%M:%S)"
