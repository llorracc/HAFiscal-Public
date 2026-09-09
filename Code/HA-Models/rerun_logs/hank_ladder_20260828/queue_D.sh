#!/bin/bash
# Queue D (2026-08-28): arm 5c = arm 5b's Jacobians + the GE stage with the calibration's own splurge. In the package's
# ge.py, HAFISCAL_QE_FIDELITY=1 forces splurge = 0.3 regardless of HAFISCAL_HANK_SPLURGE, so arm 5b's "calib" delta did
# not take; here QE_FIDELITY is unset for the GE stage only (Jacobians reused in place from arm 5b). GE-only, ~8 s.
LAD=/Users/ccarroll/ui_ext_20260826/hank_ladder_20260828
ROOT=/Users/ccarroll/GitHub/llorracc/HAFiscal-Latest
cd "$LAD" || exit 1
until grep -q "queue_C end" queue_C.nohup 2>/dev/null; do sleep 60; done
echo "queue_D start $(date '+%F %T')"
cp arm5b_live_conv/HA_Fiscal_Jacs.obj "$ROOT/Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj"
PKG="HAFISCAL_STEP4_FAST_BACKWARD=1 HAFISCAL_PLVL_GROWS_DURING_UNEMP=on HAFISCAL_STEP4_ZEROTH_FIX=1"
R5B="$PKG HAFISCAL_HANK_PERMGROFAC=main HAFISCAL_STEP4_TRANMAT_GROWTH=1 HAFISCAL_HANK_UNEMP_CHAINS=pe HAFISCAL_HANK_TAXCUT_FINANCING=household HAFISCAL_HANK_SS_SOURCE=jacs_c HAFISCAL_HANK_MULT_REGIME=consistent HAFISCAL_HANK_SPLURGE=calib HAFISCAL_HANK_SPLURGE_BYEDUC=1 HAFISCAL_HANK_UNEMP_PSI=main"
GE_ONLY=1 ./run_arm.sh arm5c_calib_splurge package $R5B HAFISCAL_QE_FIDELITY=
echo "queue_D end $(date '+%F %T')"
