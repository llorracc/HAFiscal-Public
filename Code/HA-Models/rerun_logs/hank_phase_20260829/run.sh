#!/usr/bin/env bash
# HANK block (Step 4) on the EARNINGS-PHASE calibration (installed 2026-08-29), the revision conventions = the package defaults.
set -u
R=/Volumes/Sync/GitHub/llorracc/HAFiscal-Latest; OUT=$HOME/ui_ext_20260826/hank_phase_20260829; PY=$R/.venv/bin/python
cd $R || exit 9
export HAFISCAL_EARNINGS_PHASE_HAZARD=1/120 HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration HAFISCAL_QUIET_BETADISTR=1 PYTHONUNBUFFERED=1
export HAFISCAL_STEP4_ENGINE=package HAFISCAL_STEP4_FAST_BACKWARD=1 HAFISCAL_STEP4_SHOCK_FIX=1 HAFISCAL_STEP4_ZEROTH_FIX=1 HAFISCAL_STEP4_TRANMAT_GROWTH=1
export HAFISCAL_HANK_MULT_DUMP=$OUT/mult_dump.pkl HAFISCAL_HANK_SS_DUMP=$OUT/ss_dump.pkl
env | grep -E "^HAFISCAL" | sort > $OUT/env.txt; git rev-parse --short HEAD > $OUT/git_head.txt
echo "=== jacobians start $(date) ===" > $OUT/wall.txt
/usr/bin/time -l $PY Code/HA-Models/step4/run_jacobians.py > $OUT/jacobians.log 2>&1; RC=$?; echo "jacobians rc=$RC $(date)" >> $OUT/wall.txt
cp Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj $OUT/HA_Fiscal_Jacs.obj 2>/dev/null
/usr/bin/time -l $PY Code/HA-Models/step4/run_ge.py > $OUT/ge.log 2>&1; RC2=$?; echo "ge rc=$RC2 $(date)" >> $OUT/wall.txt
git checkout -- Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj 2>/dev/null
echo "HANK PHASE DONE rc=$RC/$RC2 $(date)" >> $OUT/wall.txt
