#!/bin/bash
# Econ-1 gate at HS_Only, part 2 (2026-08-28 09:05): seeds 3..9 for both arms (plain vs stratified 0.3) so the equal-expectation test has S = 10 per arm.
# under sharing needs them; (2) three seeds plain vs three seeds stratified (HAFISCAL_MC_STRATIFY_UNEMP=0.3); compare cells
# (expectation unchanged within SE; UI SE down). Everything through runq (launch_helpers.sh).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python; HA=$REPO/Code/HA-Models
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC; source $HA/launch_helpers.sh
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
until grep -q "E1 HSONLY GATE DONE" $LOG/e1_gate.out 2>/dev/null; do sleep 30; done
for MODE in plain strat; do
  [ $MODE = strat ] && export HAFISCAL_MC_STRATIFY_UNEMP=0.3 || unset HAFISCAL_MC_STRATIFY_UNEMP
  for K in 3 4 5 6 7 8 9; do T1=$(date +%s); stamp "w6[HS_Only $MODE] seed $K start"
    HAFISCAL_FIGS_SUFFIX=_uiA_gate runw6 --parametrization HS_Only --seed-offset $K --out-dir welfare6_scenario_results_HS_Only_gate_${MODE}_seed$K --table-dir Tables/HS_Only_gate_${MODE}_seed$K > $LOG/w6_HS_Only_gate_${MODE}_seed$K.log 2>&1; rc=$?
    stamp "w6[HS_Only $MODE] seed $K end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min"; done
done
echo "E1B HSONLY GATE DONE $(date +%H:%M:%S)"
