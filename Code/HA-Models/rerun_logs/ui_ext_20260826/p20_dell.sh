#!/bin/bash
# P20 (dell, 2026-08-27 11:40; owner protocol §5e) -- the ORIGINAL MODEL on the current certified machinery, CORRECTED:
# P18's `orig` arm ran under today's GIC cap rule, which clips the QE calibration's high-school top beta atom at 0.98195 where
# the QE rule leaves it at 0.99045 (dropout/college identical) -- HAFISCAL_GIC_SHAVE_ON_GPF=0 (BUG-053's legacy exponent)
# reproduces the QE atoms exactly (verified 11:35). ORIG = QE calibration (betas/GICx/splurge) + QE conventions: CDC, legacy
# PermGroFac solver regime (BUG-047 present), published tail extrapolation (BUG-061/062 present), QE beta-atom clip, cap 200,
# shocks off, paper's UI window -- run by today's code (exact TM evolution, certified 7-state chain + stratified shuffle,
# own AD loops, HARK engine, equal-weight panel; ATI refuses the legacy solver regime -> EGM, certified-equivalent).
#   orig_typo : ORIG + HAFISCAL_LEGACY_TAXCUT_ATOM=1 (the published tax-cut construction, BUG-023 present) = the TRUE original
#   orig      : ORIG (BUG-023 fixed)                                                                 = "+ BUG-023 fix" row
# + HAFISCAL_PF_DECAY_Q=slope (12:10): restores the QE solve grid 40/48 (the K-hbar rule gave 467-591); with extrapolation off the
# exponent is moot. 5a + seeds 0..4 + band each. Ends with "P20 DELL DONE" (P21 waits for it).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
Q=/home/shared/github/llorracc/HAFiscal-QE/Code/HA-Models; LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
echo "HEAD $(git -C $REPO rev-parse --short HEAD) $(date +%H:%M:%S)"
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
ORIG=(HAFISCAL_WORLD=as-corrected HAFISCAL_INTERPRETATION=CDC HAFISCAL_PERMGROFAC_FIX=0 HAFISCAL_PF_DECAY_EXTRAP=0 HAFISCAL_PF_DECAY_Q=slope HAFISCAL_GIC_SHAVE_ON_GPF=0 HAFISCAL_DISCFAC_FILE=$Q/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt HAFISCAL_SPLURGE_FILE=$Q/Target_AggMPCX_LiquWealth/Result_AllTarget.txt)
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
arm() { tag=$1; shift
  T0=$(date +%s); stamp "5a[$tag] start"; env "${ORIG[@]}" "$@" HAFISCAL_FIGS_SUFFIX=_$tag $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_$tag.log 2>&1; rc=$?
  stamp "5a[$tag] end rc=$rc wall=$(( ($(date +%s)-T0)/60 ))min"; grep -c "taxcut-atoms\] HAFISCAL_LEGACY_TAXCUT_ATOM=1" $LOG/mult_$tag.log; grep "AD effect)\|expenditure during" Tables/Baseline_$tag/Multiplier_candidate.tex 2>/dev/null; [ $rc -eq 0 ] || return
  for K in 0 1 2 3 4; do T1=$(date +%s); stamp "w6[$tag] seed $K start"; env "${ORIG[@]}" "$@" $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${tag}_seed$K --table-dir Tables/Baseline_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1; stamp "w6[$tag] seed $K end rc=$? wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_${tag}_seed$K 2>/dev/null | wc -l)"; grep -h "FAIL rc=" $LOG/w6_${tag}_seed$K.log | head -2; done
  stamp "band[$tag]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_${tag}_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_${tag}_S5_seed_band.tex 2>&1 | tail -11; }
rm -rf Tables/Baseline_orig Tables/Baseline_orig_seed* welfare6_scenario_results_Baseline_orig_seed* 2>/dev/null   # P18's invalid-rule outputs
arm orig_typo HAFISCAL_LEGACY_TAXCUT_ATOM=1
arm orig
echo "P20 DELL DONE $(date +%H:%M:%S)"
