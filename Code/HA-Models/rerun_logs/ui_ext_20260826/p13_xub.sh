#!/bin/bash
# P13 on xubuntark (2026-08-27 01:20): the grid-top row of the attribution ladder in the UNCAPPED world. The default world in
# the uiA configuration (paper's UI window) with HAFISCAL_TM_AMAX=500 (the paper's distribution-grid top; BUG-084), 5a only --
# the TM multiplier program is the only consumer of the grid top (the capped-world ladder row was null; the uncapped
# College GIC-cap atom's tail is where 1300 was needed). Compare with dell's Tables/Baseline_uiA. Own solves (REQUIRE=0).
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
LOG=$HOME/ui_ext_20260826; cd $FPC
echo "worktree at $(git -C $W rev-parse --short HEAD) $(date +%H:%M:%S)"
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_TM_AMAX=500
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
stamp "5a[uiA_amax500] start"; env HAFISCAL_FIGS_SUFFIX=_uiA_amax500 $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_uiA_amax500.log 2>&1; rc=$?
stamp "5a[uiA_amax500] end rc=$rc"; grep "AD effect)\|expenditure during" Tables/Baseline_uiA_amax500/Multiplier_candidate.tex 2>/dev/null
echo "P13 XUB DONE $(date +%H:%M:%S)"
