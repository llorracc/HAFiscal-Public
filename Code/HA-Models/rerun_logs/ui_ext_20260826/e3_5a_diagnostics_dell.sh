#!/bin/bash
# Econ-3 / Econ-10(ii) diagnostic multiplier programs (owner 2026-08-28 10:33: "run both"), Baseline, default world, paper's
# UI window, ONE code state, through runq's 5a slot after the appendix arm (P29c). Equilibrium and belief PUBLISHING OFF:
# these arms have the same MODEL key as the tables of record and would otherwise REPLACE the stored equilibria
# ("the spending program is the authority").
#   ref28     : the production tier today (reference on this code state)                 -> Tables/Baseline_uiA_ref28
#   mcount200 : HAFISCAL_TM_MCOUNT=200 (distribution grid 100 -> 200; Econ-3's surviving run) -> Tables/Baseline_uiA_mcount200
#   tight     : HAFISCAL_STEP5_ATI=0 HAFISCAL_AD_CONVERGENCE_TOL=1e-3 (EGM, tight AD tol; Econ-10(ii)) -> Tables/Baseline_uiA_tight
# Expectations pre-registered: mcount200 |delta| <= 1e-3; tight composite |delta| <= 1e-3 (07-27 G-B: 7.0e-4).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python; HA=$REPO/Code/HA-Models
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC; source $HA/launch_helpers.sh
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_AD_BELIEF_PUBLISH=0
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
until grep -q "P29E DELL DONE" $LOG/p29e.out 2>/dev/null; do sleep 120; done; stamp "gate open (P29c done)"
run_arm() { local TAG=$1; shift; local T0=$(date +%s); stamp "5a[$TAG] start env: $*"
  env "$@" HAFISCAL_FIGS_SUFFIX=_uiA_$TAG "$PY" "$HA/runq.py" --class 5a -- "$PY" AggFiscalMAIN_reduced.py --baseline > $LOG/mult_uiA_$TAG.log 2>&1; local rc=$?
  stamp "5a[$TAG] end rc=$rc wall=$(( ($(date +%s)-T0)/60 ))min published=$(grep -c 'ad-equilibrium\] SAVED' $LOG/mult_uiA_$TAG.log)"; grep -h "AD effect)\|no AD effect)" Tables/Baseline_uiA_$TAG/Multiplier_candidate.tex 2>/dev/null; }
run_arm ref28
run_arm mcount200 HAFISCAL_TM_MCOUNT=200
run_arm tight HAFISCAL_STEP5_ATI=0 HAFISCAL_AD_CONVERGENCE_TOL=1e-3
echo "E3 5A DIAGNOSTICS DONE $(date +%H:%M:%S)"
