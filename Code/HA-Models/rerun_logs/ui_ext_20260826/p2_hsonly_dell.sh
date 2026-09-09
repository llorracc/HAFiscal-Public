#!/bin/bash
# P2 / gate G1 of plans/20260826-0800h_ui-extension-calendar-window-encoding_plan.md (dell, 2026-08-26):
# Improvement A's equivalence demonstration + the speedup measurement, at HS_Only.
#   Phase 1  four TM a-indexed multiplier programs (AggFiscalMAIN_reduced.py --hs-only), concurrently:
#            legacy (the paper's 4-state freeze) | window (calendar, 7 states, the paper's policy) |
#            bugfix (the 2026-05-16 six-state rule) | history (calendar, 6 states, Improvement B).
#            Deterministic TM: legacy vs window agree to solver tolerance on EVERY multiplier incl. UI;
#            they also populate the per-arm policy store the batteries load (strict store mode).
#   Phase 2a welfare batteries (own AD loops: AD_EQUILIBRIUM_SHARE=0, as in the May measurement):
#            exactness  = non-shuffled MC (MC_SHUFFLE=0), seed 0: legacy vs window, all 8 cells
#                         (the same draws map to relabeled states -> identical incomes; the residual
#                         is the solver's);
#            byte-id    = stratified shuffle (default), seed 0: history vs bugfix -- the non-UI cells
#                         share chain and incomes exactly (6 states) -> byte-identical.
#   Phase 2b speedup: stratified shuffle (default), seeds 0..5, legacy vs window -> the UI cells'
#            across-seed SE ratio at the same N (the number that goes in the catalog row).
# Launched in its own transient systemd unit (MemoryMax) per feedback_compute_in_own_systemd_unit.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; mkdir -p $LOG
cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
export HAFISCAL_DUR_WORKERS=1 HAFISCAL_QUIET_BETADISTR=1
echo "HEAD $(git -C $REPO rev-parse --short HEAD) (+ uncommitted P1 working tree) $(date +%H:%M:%S)"
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
arm_env() { case $1 in
  legacy)  echo "HAFISCAL_UI_STATE_ENCODING=legacy";;
  window)  echo "HAFISCAL_UI_STATE_ENCODING=calendar HAFISCAL_UI_EXTENSION_POLICY=window";;
  bugfix)  echo "HAFISCAL_UI_STATE_ENCODING=bug_fix";;
  history) echo "HAFISCAL_UI_STATE_ENCODING=calendar HAFISCAL_UI_EXTENSION_POLICY=history";;
esac; }
mult() { arm=$1; stamp "mult[$arm] start"; rm -rf Tables/HS_Only_ui_$arm Figures/HS_Only_ui_$arm
  env $(arm_env $arm) HAFISCAL_FIGS_SUFFIX=_ui_$arm $PY AggFiscalMAIN_reduced.py --hs-only > $LOG/mult_$arm.log 2>&1; rc=$?
  stamp "mult[$arm] end rc=$rc saved=$(grep -c 'policy-store\] SAVED' $LOG/mult_$arm.log)"; grep -h "Whole script took" $LOG/mult_$arm.log; }
for arm in legacy window bugfix history; do mult $arm & done; wait
stamp "phase 1 done"
w6() { arm=$1; K=$2; tag=$3; extra=$4; stamp "w6[$tag] seed $K start"
  env $(arm_env $arm) $extra HAFISCAL_AD_EQUILIBRIUM_SHARE=0 $PY run_welfare6_parallel.py --parametrization HS_Only --seed-offset $K --max-cpu-slots 3 --out-dir welfare6_scenario_results_HS_Only_${tag}_seed$K --table-dir Tables/HS_Only_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1; rc=$?
  stamp "w6[$tag] seed $K end rc=$rc tables=$(ls Tables/HS_Only_${tag}_seed$K 2>/dev/null | wc -l) miss-errors=$(grep -c 'MISS at' $LOG/w6_${tag}_seed$K.log)"; grep -h "FAIL rc=" $LOG/w6_${tag}_seed$K.log | head -3; }
w6 legacy 0 legacy_nshuf "HAFISCAL_MC_SHUFFLE=0" &
w6 window 0 window_nshuf "HAFISCAL_MC_SHUFFLE=0" &
w6 bugfix 0 bugfix "" &
w6 history 0 history "" &
wait
stamp "phase 2a done"
for K in 0 2 4; do
  w6 legacy $K legacy "" &
  w6 window $K window "" &
  w6 legacy $((K+1)) legacy "" &
  w6 window $((K+1)) window "" &
  wait
done
stamp "phase 2b done"
echo "P2 HS_ONLY DELL DONE $(date +%H:%M:%S)"
