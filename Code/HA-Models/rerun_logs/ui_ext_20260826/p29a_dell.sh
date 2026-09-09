#!/bin/bash
# P29a (dell). See p29_common.sh. Stream a: Rfree_1005 -> Rspell_4 (starts now, alongside P28); stream b: Rfree_1015 -> ADElas (after P28).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC; source $LOG/p29_common.sh
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window
echo "P29a starting at HEAD $(git -C $REPO rev-parse --short HEAD) $(date +%H:%M:%S)"
cfg Rfree_1005; cfg Rspell_4
echo "P29A DELL DONE $(date +%H:%M:%S)"
