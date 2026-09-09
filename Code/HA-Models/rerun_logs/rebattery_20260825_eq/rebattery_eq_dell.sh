#!/bin/bash
# Baseline S=3 welfare battery on the SHARED AD EQUILIBRIUM (P6), dell, default world:
#   1. multiplier program with HAFISCAL_AD_EQUILIBRIUM_SHARE=1 (policies all hit; publishes the
#      4 recession scenarios' equilibria into ~/.cache/hafiscal/policy_store/equilibrium)
#   2. welfare seeds 0,1,2 with SHARE=1: every AD loop skipped; strict mode throughout
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode
PY=$REPO/.venv/bin/python; LOG=$REPO/Code/HA-Models/rerun_logs/rebattery_20260825_eq; mkdir -p $LOG
EXPECT=${1:?expected short HEAD}; HEAD=$(git -C $REPO rev-parse --short HEAD)
echo "main checkout at $HEAD (expected $EXPECT) $(date +%H:%M:%S)"; [ "$HEAD" = "$EXPECT" ] || { echo "ABORTED: HEAD mismatch"; exit 9; }
cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_WORLD=default HAFISCAL_AD_EQUILIBRIUM_SHARE=1
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
stamp "multiplier[default, SHARE=1] start"; env HAFISCAL_FIGS_SUFFIX=_eq $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_default.log 2>&1; rc=$?; stamp "multiplier end rc=$rc"
grep "AD effect)" Tables/Baseline_eq/Multiplier_candidate.tex | head -1; echo "   policy hits=$(grep -c 'policy-store\] HIT' $LOG/mult_default.log) saved=$(grep -c 'policy-store\] SAVED' $LOG/mult_default.log); equilibria SAVED=$(grep -c 'ad-equilibrium\] SAVED' $LOG/mult_default.log)"; grep -h "ad-equilibrium\] save skipped" $LOG/mult_default.log | head -2; [ $rc -eq 0 ] || exit 10
for K in 0 1 2; do
  stamp "welfare[default, SHARE=1] seed $K start"; $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_eq_seed$K --table-dir Tables/Baseline_eq_seed$K > $LOG/w6_eq_seed$K.log 2>&1; rc=$?; stamp "welfare seed $K end rc=$rc tables=$(ls Tables/Baseline_eq_seed$K 2>/dev/null | wc -l)"
  d=welfare6_parallel_logs/Baseline$([ $K = 0 ] || echo _seed$K); mkdir -p $LOG/w6logs_seed$K; cp -R $d/. $LOG/w6logs_seed$K/ 2>/dev/null
  echo "   policy-store hits=$(grep -rh 'policy-store\] HIT' $d | wc -l) saved=$(grep -rh 'policy-store\] SAVED' $d | wc -l) miss=$(grep -rl 'MISS at' $d | wc -l) | equilibrium HIT=$(grep -rh 'ad-equilibrium\] HIT' $d | wc -l) skipped-loops=$(grep -rh 'AD loop SKIPPED' $d | wc -l) AD-solves=$(grep -rh 'AD solve took' $d | wc -l)"; grep -h "FAIL rc=" $LOG/w6_eq_seed$K.log | head -2
done
echo "REBATTERY-EQ DELL DONE $(date +%H:%M:%S)"
