#!/bin/bash
# Econ-1 gate at HS_Only, part 5 (2026-08-28 09:50): the IID transition engine (HAFISCAL_SHUFFLE_MRKV_TRANSITION=iid, independent per-household draws) as the
# unbiased-by-construction reference for the plain stratified arm (whose Hamilton rounding is deterministic per (N_j, p)); 10 seeds.
# usage: e1f_hsonly_gate_dell.sh
set -u
MODES=${1:-iid}
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python; HA=$REPO/Code/HA-Models
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC; source $HA/launch_helpers.sh
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
for MODE in ${MODES//,/ }; do
  unset HAFISCAL_MC_STRATIFY_UNEMP HAFISCAL_SHUFFLE_MRKV_STRATA; export HAFISCAL_SHUFFLE_MRKV_TRANSITION=iid
  for K in 0 1 2 3 4 5 6 7 8 9; do T1=$(date +%s); stamp "w6[HS_Only $MODE] seed $K start"
    HAFISCAL_FIGS_SUFFIX=_uiA_gate runw6 --parametrization HS_Only --seed-offset $K --out-dir welfare6_scenario_results_HS_Only_gate_${MODE}_seed$K --table-dir Tables/HS_Only_gate_${MODE}_seed$K > $LOG/w6_HS_Only_gate_${MODE}_seed$K.log 2>&1; rc=$?
    stamp "w6[HS_Only $MODE] seed $K end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min"; done
done
echo "E1F HSONLY GATE DONE $(date +%H:%M:%S)"
