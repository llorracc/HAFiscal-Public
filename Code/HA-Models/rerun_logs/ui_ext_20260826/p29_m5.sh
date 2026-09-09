#!/bin/bash
# P29 on ccarroll-m5. See p29_common.sh (copied alongside). LowerUBnoB -> CRRA3. Fast-forwards the worktree to the pushed HEAD first.
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
LOG=$HOME/ui_ext_20260826; mkdir -p $LOG
cd $W && git fetch -q origin 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC && git checkout -q --detach FETCH_HEAD && echo "worktree at $(git rev-parse --short HEAD)"
cd $FPC; source $HOME/p29_common.sh
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window
echo "P29 M5 starting $(date +%H:%M:%S)"
cfg LowerUBnoB; cfg CRRA3
echo "P29 M5 DONE $(date +%H:%M:%S)"
