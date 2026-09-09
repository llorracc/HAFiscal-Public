#!/bin/bash
# As-corrected world (T_age=200 + paper settings) under the BUG-093 construction (HAFISCAL_TM_Q_METHOD default 'doob')
# + the welfare battery S=3 on the shared equilibria, with the weighted-tail sampler as the battery's DEFAULT under
# sharing (owner 2026-08-25 18:20). Default store (as-corrected policies present from 08-24; equilibria keyed by world).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/bug093/rerun_ac_doob; mkdir -p $LOG; cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
export HAFISCAL_WORLD=as-corrected HAFISCAL_AD_EQUILIBRIUM_SHARE=1 JAX_PLATFORMS=cpu
ARM=ac_doob; stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
echo "main checkout at $(git -C $REPO rev-parse --short HEAD) world=as-corrected q_method=default(doob) weighted-tail=battery default"
stamp "multiplier[as-corrected, SHARE=1, doob] start"; env HAFISCAL_FIGS_SUFFIX=_$ARM $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_$ARM.log 2>&1; rc=$?; stamp "multiplier end rc=$rc"
grep "Multiplier" Tables/Baseline_$ARM/Multiplier_candidate.tex 2>/dev/null | cut -c1-110
echo "   policy hits=$(grep -c 'policy-store\] HIT' $LOG/mult_$ARM.log) saved=$(grep -c 'policy-store\] SAVED' $LOG/mult_$ARM.log); equilibria SAVED=$(grep -c 'ad-equilibrium\] SAVED' $LOG/mult_$ARM.log)"
grep -h "prescribed AD path" $LOG/mult_$ARM.log | head -4 | cut -c1-140
for K in 0 1 2; do
  stamp "welfare[as-corrected, SHARE=1, doob, weighted default] seed $K start"; $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${ARM}_seed$K --table-dir Tables/Baseline_${ARM}_seed$K > $LOG/w6_${ARM}_seed$K.log 2>&1; rc=$?
  stamp "welfare seed $K end rc=$rc tables=$(ls Tables/Baseline_${ARM}_seed$K 2>/dev/null | wc -l)"
  d=welfare6_parallel_logs/Baseline$([ $K = 0 ] || echo _seed$K); mkdir -p $LOG/w6logs_seed$K; cp -R $d/. $LOG/w6logs_seed$K/ 2>/dev/null
  echo "   policy-store hits=$(grep -rh 'policy-store\] HIT' $d | wc -l) miss=$(grep -rl 'MISS at' $d | wc -l) | equilibrium HIT=$(grep -rh 'ad-equilibrium\] HIT' $d | wc -l) skipped=$(grep -rh 'AD loop SKIPPED' $d | wc -l) | weighted-tail lines=$(grep -rh '^\[weighted-tail\]' $d | wc -l)"
done
echo "RERUN-$ARM DONE $(date +%H:%M:%S)"
