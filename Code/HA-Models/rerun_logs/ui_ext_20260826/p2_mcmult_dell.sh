#!/bin/bash
# P2 addendum: the MC multiplier engine (HAFISCAL_MULTIPLIER_ENGINE=mc, agent-level pLvl) on the legacy/window pair
# at HS_Only -- to show the 0.3 % TM outlay gap is the a-indexed TM's state-level E[p] weighting, not the encoding.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
export HAFISCAL_DUR_WORKERS=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_DRIFT_HARD_FAIL=0
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
arm_env() { case $1 in legacy) echo "HAFISCAL_UI_STATE_ENCODING=legacy";; window) echo "HAFISCAL_UI_STATE_ENCODING=calendar HAFISCAL_UI_EXTENSION_POLICY=window";; esac; }
mult() { arm=$1; stamp "mcmult[$arm] start"; rm -rf Tables/HS_Only_uimc_$arm Figures/HS_Only_uimc_$arm
  env $(arm_env $arm) HAFISCAL_MULTIPLIER_ENGINE=mc HAFISCAL_SIM_METHOD=MC HAFISCAL_FIGS_SUFFIX=_uimc_$arm $PY AggFiscalMAIN_reduced.py --hs-only > $LOG/mcmult_$arm.log 2>&1; rc=$?
  stamp "mcmult[$arm] end rc=$rc"; grep -h "Whole script took" $LOG/mcmult_$arm.log; }
mult legacy & mult window & wait
echo "P2 MCMULT DONE $(date +%H:%M:%S)"
