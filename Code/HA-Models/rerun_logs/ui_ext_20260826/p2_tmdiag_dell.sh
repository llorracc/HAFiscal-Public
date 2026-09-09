#!/bin/bash
# P2 diagnostic: where does the TM's 0.3 % recessionUI outlay gap (legacy vs window, t=1..3) come from?
#   bst  = plain kernel instead of the Doob p-weighted step (HAFISCAL_TM_Q_METHOD=bst)
#   egm  = plain EGM instead of the ATI/newton solver (HAFISCAL_STEP5_ATI=0)
# If the gap vanishes under bst -> Doob/Q-measure; under egm -> solver tolerance; else transport.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
export HAFISCAL_DUR_WORKERS=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE=0
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
arm_env() { case $1 in legacy) echo "HAFISCAL_UI_STATE_ENCODING=legacy";; window) echo "HAFISCAL_UI_STATE_ENCODING=calendar HAFISCAL_UI_EXTENSION_POLICY=window";; esac; }
run() { arm=$1; tag=$2; extra=$3; stamp "$tag[$arm] start"; rm -rf Tables/HS_Only_${tag}_$arm Figures/HS_Only_${tag}_$arm
  env $(arm_env $arm) $extra HAFISCAL_FIGS_SUFFIX=_${tag}_$arm $PY AggFiscalMAIN_reduced.py --hs-only > $LOG/${tag}_$arm.log 2>&1; rc=$?; stamp "$tag[$arm] end rc=$rc"; }
run legacy uibst "HAFISCAL_TM_Q_METHOD=bst" & run window uibst "HAFISCAL_TM_Q_METHOD=bst" &
run legacy uiegm "HAFISCAL_STEP5_ATI=0" & run window uiegm "HAFISCAL_STEP5_ATI=0" &
wait; echo "TMDIAG DONE $(date +%H:%M:%S)"
