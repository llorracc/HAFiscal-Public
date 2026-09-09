#!/bin/bash
# P24 (dell, 2026-08-27 16:10; owner: report a corrected bug AFTER its re-estimation, not the raw effect and the re-estimation
# separately). BUG-047 with its MATCHED re-estimation on the ORIGINAL model: Step 2 (TM-ergodic estimator) under the corrected
# solver (HAFISCAL_PERMGROFAC_FIX=1) with every OTHER convention the paper's (CDC, published 40/48 grid + linear extrapolation,
# published atom clip, QE splurge 0.246, cap 200, shocks off), outputs to a scratch dir (tracked Results/ untouched); then
# 5a + seeds 0,1 on that calibration -> Tables/Baseline_orig_pgf_reest*. Compared with Baseline_orig (+BUG-023 fix) this row is
# "what the solver correction does after re-estimation". Waits for P21 (uiA under hark).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
Q=/home/shared/github/llorracc/HAFiscal-QE/Code/HA-Models; LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; S2=$LOG/s2_orig_pgf; mkdir -p $S2; cd $FPC
until grep -q "P21 DELL DONE" $LOG/p21.out 2>/dev/null; do sleep 120; done
echo "P21 finished; starting P24 at HEAD $(git -C $REPO rev-parse --short HEAD) $(date +%H:%M:%S)"
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
ORIGF=(HAFISCAL_WORLD=as-corrected HAFISCAL_INTERPRETATION=CDC HAFISCAL_PERMGROFAC_FIX=1 HAFISCAL_PF_DECAY_EXTRAP=0 HAFISCAL_PF_DECAY_Q=slope HAFISCAL_GIC_SHAVE_ON_GPF=0 HAFISCAL_SPLURGE_FILE=$Q/Target_AggMPCX_LiquWealth/Result_AllTarget.txt)
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
T0=$(date +%s); stamp "S2[orig_pgf_reest] start (3 cohorts concurrently; warm start from the QE betas)"
for E in 0 1 2; do env "${ORIGF[@]}" HAFISCAL_DISCFAC_FILE=$Q/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt HAFISCAL_NM_START_FROM_SAVED=1 HAFISCAL_EDTYPES=$E HAFISCAL_RESULTS_OUT_DIR=$S2 $PY estim_phase2_tm_a.py > $S2/s2_edType$E.log 2>&1 & done; wait
stamp "S2[orig_pgf_reest] end wall=$(( ($(date +%s)-T0)/60 ))min"; grep -h "step2-unemp-incshk" $S2/s2_edType2.log | head -1 | cut -c1-100
CAL=$S2/DiscFacEstim_CRRA_2.0_R_1.01_orig_pgf_reest.txt
ls $S2/*.txt; cat $S2/DiscFacEstim_CRRA_2.0_R_1.01_edType0*.txt $S2/DiscFacEstim_CRRA_2.0_R_1.01_edType1*.txt $S2/DiscFacEstim_CRRA_2.0_R_1.01_edType2*.txt > $CAL 2>/dev/null || { echo "S2 FAILED: per-cohort files missing"; exit 10; }
printf "\nParameters: R = 1.01, CRRA = 2.0, IncUnemp = 0.7, IncUnempNoBenefits = 0.5, Splurge = 0.24611389063967778\n" >> $CAL; echo "calibration:"; head -3 $CAL; echo "QE betas for comparison:"; head -3 $Q/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt
T1=$(date +%s); stamp "5a[orig_pgf_reest] start"; env "${ORIGF[@]}" HAFISCAL_DISCFAC_FILE=$CAL HAFISCAL_FIGS_SUFFIX=_orig_pgf_reest $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_orig_pgf_reest.log 2>&1; rc=$?
stamp "5a[orig_pgf_reest] end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min"; grep "AD effect)\|expenditure during" Tables/Baseline_orig_pgf_reest/Multiplier_candidate.tex 2>/dev/null; [ $rc -eq 0 ] || exit 11
for K in 0 1; do T2=$(date +%s); stamp "w6[orig_pgf_reest] seed $K start"; env "${ORIGF[@]}" HAFISCAL_DISCFAC_FILE=$CAL $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_orig_pgf_reest_seed$K --table-dir Tables/Baseline_orig_pgf_reest_seed$K > $LOG/w6_orig_pgf_reest_seed$K.log 2>&1; stamp "w6[orig_pgf_reest] seed $K end rc=$? wall=$(( ($(date +%s)-T2)/60 ))min tables=$(ls Tables/Baseline_orig_pgf_reest_seed$K 2>/dev/null | wc -l)"; done
echo "P24 DELL DONE $(date +%H:%M:%S)"
