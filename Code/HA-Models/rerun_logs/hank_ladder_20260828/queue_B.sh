#!/bin/bash
# Queue B (2026-08-28): the package-engine arms, CUMULATIVE ladder; waits for queue A's last arm to finish.
# Every package arm carries HAFISCAL_PLVL_GROWS_DURING_UNEMP=on (the QE code's init dicts: PermGroFac uniform
# across states — verified 351/352 primitives equal; inert while HAFISCAL_HANK_PERMGROFAC=ones) and the L3b
# kernel (FAST_BACKWARD=1; ~1e-15 class vs the python path — arm 1p vs arm 1 measures engine+kernel together).
LAD=/Users/ccarroll/ui_ext_20260826/hank_ladder_20260828
cd "$LAD" || exit 1
echo "queue_B waiting for arm1_zeroth_mono $(date '+%F %T')"
until grep -q DONE arm1_zeroth_mono/wall.txt 2>/dev/null; do sleep 60; done
echo "queue_B start $(date '+%F %T')"
PKG="HAFISCAL_STEP4_FAST_BACKWARD=1 HAFISCAL_PLVL_GROWS_DURING_UNEMP=on HAFISCAL_STEP4_ZEROTH_FIX=1"
./run_arm.sh arm1p_zeroth_pkg package $PKG
R2="$PKG HAFISCAL_HANK_PERMGROFAC=main HAFISCAL_STEP4_TRANMAT_GROWTH=1"
./run_arm.sh arm2_growth package $R2
R3="$R2 HAFISCAL_HANK_UNEMP_CHAINS=pe"
./run_arm.sh arm3_pechains package $R3
R4="$R3 HAFISCAL_HANK_TAXCUT_FINANCING=household"
./run_arm.sh arm4_symfin package $R4
R5="$R4 HAFISCAL_HANK_SS_SOURCE=jacs_c HAFISCAL_HANK_MULT_REGIME=consistent"
./run_arm.sh arm5_revision_conv package $R5
# extra rows: 5b = + the remaining calibration-independent live conventions (splurge = the calibration's own
# value, by-educ overlay, PE psi during unemployment; GRIDS stays legacy — the QE PE solve grid is 40/48);
# 2b = arm 2 with the revision's frozen-unemployed-pLvl convention (Gamma_u = 1) as a sensitivity row.
R5B="$R5 HAFISCAL_HANK_SPLURGE=calib HAFISCAL_HANK_SPLURGE_BYEDUC=1 HAFISCAL_HANK_UNEMP_PSI=main"
./run_arm.sh arm5b_live_conv package $R5B
R2B="$R2 HAFISCAL_PLVL_GROWS_DURING_UNEMP=off"
./run_arm.sh arm2b_growth_unempfrozen package $R2B
echo "queue_B end $(date '+%F %T')"
