#!/bin/bash
# G2 twin (dell, 2026-08-26): the DEFAULT world under the paper's 4-state encoding (HAFISCAL_UI_STATE_ENCODING=legacy,
# explicit env) -- Step 5a only -- so the Baseline A-vs-legacy comparison is same-world, same-vintage (the as-corrected
# legacy run differs in world settings too). Waits for P3 to finish (memory). Improvement B runs on m5 meanwhile.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826
until grep -q "P3 BASELINE DELL DONE" $LOG/p3.out 2>/dev/null; do sleep 60; done
echo "P3 finished; starting the legacy twin $(date +%H:%M:%S)"
cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
stamp "multiplier[default/legacy twin] start"; env HAFISCAL_WORLD=default HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_FIGS_SUFFIX=_uiL $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_default_legacy.log 2>&1; rc=$?
stamp "multiplier[default/legacy twin] end rc=$rc"; grep -h "ui-encoding\]" $LOG/mult_default_legacy.log | head -1; grep "AD effect)\|expenditure during" Tables/Baseline_uiL/Multiplier_candidate.tex 2>/dev/null
echo "LEGACY TWIN DELL DONE $(date +%H:%M:%S)"
