#!/bin/bash
# P18 on ccarroll-m5 (2026-08-27 10:45; owner protocol §5e): the forward BREAKDOWN arms on the ORIGINAL model, in parallel with
# dell's start column. ORIG = the QE calibration (files copied from dell into ~/ui_ext_20260826/qe_calib/) and conventions
# (CDC, legacy PermGroFac solver regime, published tail extrapolation, as-corrected world) on the current certified machinery.
#   orig_pgf : ORIG + HAFISCAL_PERMGROFAC_FIX=1  (the solver fix, RAW: same QE calibration)  -> breakdown row BUG-047
#   orig_pfx : ORIG + HAFISCAL_PF_DECAY_EXTRAP=1 (the tail-extrapolation fix)               -> breakdown row BUG-061/062
# 5a + seeds 0,1 each; own solves. Worktree ~/coldrun_ps (97306779; the 5a/5b path is unchanged since).
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
LOG=$HOME/ui_ext_20260826; QC=$LOG/qe_calib; cd $FPC
echo "worktree at $(git -C $W rev-parse --short HEAD) $(date +%H:%M:%S)"
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
ORIG=(HAFISCAL_WORLD=as-corrected HAFISCAL_INTERPRETATION=CDC HAFISCAL_PERMGROFAC_FIX=0 HAFISCAL_PF_DECAY_EXTRAP=0 HAFISCAL_PF_DECAY_Q=slope HAFISCAL_GIC_SHAVE_ON_GPF=0 HAFISCAL_DISCFAC_FILE=$QC/DiscFacEstim_CRRA_2.0_R_1.01.txt HAFISCAL_SPLURGE_FILE=$QC/Result_AllTarget.txt)
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
arm() { tag=$1; nseeds=$2; shift 2
  T0=$(date +%s); stamp "5a[$tag] start"; env "${ORIG[@]}" "$@" HAFISCAL_FIGS_SUFFIX=_$tag $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_$tag.log 2>&1; rc=$?
  stamp "5a[$tag] end rc=$rc wall=$(( ($(date +%s)-T0)/60 ))min"; grep "AD effect)\|expenditure during" Tables/Baseline_$tag/Multiplier_candidate.tex 2>/dev/null; [ $rc -eq 0 ] || return
  K=0; while [ $K -lt $nseeds ]; do T1=$(date +%s); stamp "w6[$tag] seed $K start"; env "${ORIG[@]}" "$@" $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${tag}_seed$K --table-dir Tables/Baseline_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1; stamp "w6[$tag] seed $K end rc=$? wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_${tag}_seed$K 2>/dev/null | wc -l | tr -d " ")"; K=$((K+1)); done; }
arm orig_pgf 2 HAFISCAL_PERMGROFAC_FIX=1
arm orig_pfx 2 HAFISCAL_PF_DECAY_EXTRAP=1
echo "P18 M5 DONE $(date +%H:%M:%S)"
