#!/bin/bash
# Baseline S=3 welfare battery on the SHARED AD EQUILIBRIUM (P6), ccarroll-m5, as-corrected world.
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
LOG=$HOME/rebattery_20260825_eq_ac; mkdir -p $LOG
EXPECT=${1:?expected short HEAD}
git -C $W checkout -q -- . ; git -C $W pull --ff-only origin 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC 2>&1 | tail -1
HEAD=$(git -C $W rev-parse --short HEAD); echo "worktree at $HEAD (expected $EXPECT) $(date +%H:%M:%S)"; [ "$HEAD" = "$EXPECT" ] || { echo "ABORTED: HEAD mismatch"; exit 9; }
cd $FPC
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_WORLD=as-corrected HAFISCAL_AD_EQUILIBRIUM_SHARE=1
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
stamp "multiplier[as-corrected, SHARE=1] start"; env HAFISCAL_FIGS_SUFFIX=_ac_eq $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_ac.log 2>&1; rc=$?; stamp "multiplier end rc=$rc"
grep "AD effect)" Tables/Baseline_ac_eq/Multiplier_candidate.tex | head -1; echo "   policy hits=$(grep -c 'policy-store\] HIT' $LOG/mult_ac.log) saved=$(grep -c 'policy-store\] SAVED' $LOG/mult_ac.log); equilibria SAVED=$(grep -c 'ad-equilibrium\] SAVED' $LOG/mult_ac.log)"; grep -h "ad-equilibrium\] save skipped" $LOG/mult_ac.log | head -2; [ $rc -eq 0 ] || exit 10
for K in 0 1 2; do
  stamp "welfare[as-corrected, SHARE=1] seed $K start"; $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_ac_eq_seed$K --table-dir Tables/Baseline_ac_eq_seed$K > $LOG/w6_ac_eq_seed$K.log 2>&1; rc=$?; stamp "welfare seed $K end rc=$rc tables=$(ls Tables/Baseline_ac_eq_seed$K 2>/dev/null | wc -l | tr -d ' ')"
  d=welfare6_parallel_logs/Baseline$([ $K = 0 ] || echo _seed$K); mkdir -p $LOG/w6logs_seed$K; cp -R $d/. $LOG/w6logs_seed$K/ 2>/dev/null
  echo "   policy-store hits=$(grep -rh 'policy-store\] HIT' $d | wc -l | tr -d ' ') saved=$(grep -rh 'policy-store\] SAVED' $d | wc -l | tr -d ' ') miss=$(grep -rl 'MISS at' $d | wc -l | tr -d ' ') | equilibrium HIT=$(grep -rh 'ad-equilibrium\] HIT' $d | wc -l | tr -d ' ') skipped-loops=$(grep -rh 'AD loop SKIPPED' $d | wc -l | tr -d ' ') AD-solves=$(grep -rh 'AD solve took' $d | wc -l | tr -d ' ')"; grep -h "FAIL rc=" $LOG/w6_ac_eq_seed$K.log | head -2
done
echo "REBATTERY-EQ M5 DONE $(date +%H:%M:%S)"
