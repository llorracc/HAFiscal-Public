#!/bin/bash
# Queue C (2026-08-28): re-run the two arms that crashed in queue B — legacy chains + HAFISCAL_HANK_PERMGROFAC=main
# hits a package defect (hh_setup.py normalizes the PE PermGroFac vector to the HANK's 6 states only in the
# per-education-chains branch; under the QE 4-state legacy encoding the solver indexes state 4 of a 4-vector).
# Remedy (env only, proven by probe_hh_setup.py: 295/295 Jacobian-stage inputs identical under Gamma==1 and under
# pe chains; [G_e]*6 delivered under legacy chains): HAFISCAL_UI_STATE_ENCODING=bug_fix (6 PE micro states).
LAD=/Users/ccarroll/ui_ext_20260826/hank_ladder_20260828
cd "$LAD" || exit 1
echo "queue_C waiting for queue_B $(date '+%F %T')"
until grep -q "queue_B end" queue_B.nohup 2>/dev/null; do sleep 60; done
echo "queue_C start $(date '+%F %T')"
rm -rf arm2_growth arm2b_growth_unempfrozen    # queue B's crashed runs (their GE ran on the stale arm-1p pickle)
PKG="HAFISCAL_STEP4_FAST_BACKWARD=1 HAFISCAL_PLVL_GROWS_DURING_UNEMP=on HAFISCAL_STEP4_ZEROTH_FIX=1"
R2="$PKG HAFISCAL_HANK_PERMGROFAC=main HAFISCAL_STEP4_TRANMAT_GROWTH=1 HAFISCAL_UI_STATE_ENCODING=bug_fix"
./run_arm.sh arm2_growth package $R2
R2B="$R2 HAFISCAL_PLVL_GROWS_DURING_UNEMP=off"
./run_arm.sh arm2b_growth_unempfrozen package $R2B
echo "queue_C end $(date '+%F %T')"
