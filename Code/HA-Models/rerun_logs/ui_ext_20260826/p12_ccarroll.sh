#!/bin/bash
# P12 on ccarroll (2026-08-27 00:35): BUG-095 at the TABLE level. The default world in the uiA configuration (paper's UI
# window; AD-equilibrium sharing on = the default) on the CORRECTED perm-ON calibration (HAFISCAL_DISCFAC_FILE -> the
# s2_permon_fixed betas, assembled in the committed file's format; tracked Results/ untouched): 5a (publishes its own
# equilibria on this machine) + welfare seeds 0,1 -> Tables/Baseline_uiA_b095*. Compare with dell's Baseline_uiA (S=5).
# Waits for P11 (the perm-off control) to finish. Worktree ~/coldrun_ps at 421c6634.
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
LOG=$HOME/ui_ext_20260826; S2=$LOG/s2_permon_fixed
until grep -q "P11 CCARROLL DONE" $LOG/p11_ccarroll.out 2>/dev/null; do sleep 60; done
echo "P11 finished; starting P12 $(date +%H:%M:%S)"; cd $FPC
CAL=$S2/DiscFacEstim_CRRA_2.0_R_1.01_ESC_b095.txt
cat $S2/DiscFacEstim_CRRA_2.0_R_1.01_edType0_TM_a_ESC.txt $S2/DiscFacEstim_CRRA_2.0_R_1.01_edType1_TM_a_ESC.txt $S2/DiscFacEstim_CRRA_2.0_R_1.01_edType2_TM_a_ESC.txt > $CAL || { echo "P12 ABORT: corrected per-cohort files missing"; exit 10; }
printf "\nParameters: R = 1.01, CRRA = 2.0, IncUnemp = 0.7, IncUnempNoBenefits = 0.5, Splurge = 0.299869842312644\n" >> $CAL
echo "calibration in use:"; head -3 $CAL
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_DISCFAC_FILE=$CAL
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
stamp "5a[uiA_b095] start"; env HAFISCAL_FIGS_SUFFIX=_uiA_b095 $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_uiA_b095.log 2>&1; rc=$?
stamp "5a[uiA_b095] end rc=$rc"; echo "   betas reached the run: $(grep -c "0.7476\|0.74761" $LOG/mult_uiA_b095.log) log lines mention the corrected dropout beta"; grep "AD effect)\|expenditure during" Tables/Baseline_uiA_b095/Multiplier_candidate.tex 2>/dev/null; [ $rc -eq 0 ] || exit 11
for K in 0 1; do stamp "w6[uiA_b095] seed $K start"; $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_uiA_b095_seed$K --table-dir Tables/Baseline_uiA_b095_seed$K > $LOG/w6_uiA_b095_seed$K.log 2>&1; stamp "w6[uiA_b095] seed $K end rc=$? tables=$(ls Tables/Baseline_uiA_b095_seed$K 2>/dev/null | wc -l | tr -d " ")"; grep mathcal Tables/Baseline_uiA_b095_seed$K/welfare6_candidate.tex 2>/dev/null | head -3; done
echo "P12 CCARROLL DONE $(date +%H:%M:%S)"
