#!/bin/bash
# P18 (dell, 2026-08-27; owner protocol §5e): the ORIGINAL MODEL on the current certified machinery, and the forward breakdown.
#  ORIG = the QE calibration (betas/GICx/splurge from ../HAFiscal-QE) and conventions: CDC interpretation, the legacy
#  PermGroFac solver regime (BUG-047 present), the published tail extrapolation (BUG-061/062 present), as-corrected world
#  (cap 200, shocks off, paper's UI window) -- run by today's code: exact TM evolution, ATI, the certified package (calendar
#  chain + stratified shuffle), own AD loops, HARK engine, equal-weight panel. Own solves (new keys).
#   arm orig      : 5a + seeds 0..4 + band           -> the chain's start column
#   arm orig_pgf  : ORIG + HAFISCAL_PERMGROFAC_FIX=1  (the solver fix, RAW, same QE calibration) -> breakdown row BUG-047
#   arm orig_pfx  : ORIG + HAFISCAL_PF_DECAY_EXTRAP=1 (the tail-extrapolation fix)             -> breakdown row BUG-061/062
#  Wall times are the timing measures (stamps + [solve-wall] lines).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
Q=/home/shared/github/llorracc/HAFiscal-QE/Code/HA-Models; LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
echo "HEAD $(git -C $REPO rev-parse --short HEAD) $(date +%H:%M:%S)"
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
ORIG=(HAFISCAL_WORLD=as-corrected HAFISCAL_INTERPRETATION=CDC HAFISCAL_PERMGROFAC_FIX=0 HAFISCAL_PF_DECAY_EXTRAP=0 HAFISCAL_DISCFAC_FILE=$Q/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt HAFISCAL_SPLURGE_FILE=$Q/Target_AggMPCX_LiquWealth/Result_AllTarget.txt)
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
arm() { tag=$1; nseeds=$2; shift 2
  T0=$(date +%s); stamp "5a[$tag] start"; env "${ORIG[@]}" "$@" HAFISCAL_FIGS_SUFFIX=_$tag $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_$tag.log 2>&1; rc=$?
  stamp "5a[$tag] end rc=$rc wall=$(( ($(date +%s)-T0)/60 ))min"; grep "AD effect)\|expenditure during" Tables/Baseline_$tag/Multiplier_candidate.tex 2>/dev/null; grep -h "solve-wall" $LOG/mult_$tag.log | tail -1 | cut -c1-120; [ $rc -eq 0 ] || return
  K=0; while [ $K -lt $nseeds ]; do T1=$(date +%s); stamp "w6[$tag] seed $K start"; env "${ORIG[@]}" "$@" $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${tag}_seed$K --table-dir Tables/Baseline_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1; stamp "w6[$tag] seed $K end rc=$? wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_${tag}_seed$K 2>/dev/null | wc -l)"; grep -h "FAIL rc=" $LOG/w6_${tag}_seed$K.log | head -2; K=$((K+1)); done; }
arm orig 5
stamp "band[orig]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_orig_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_orig_S5_seed_band.tex 2>&1 | tail -11
arm orig_pgf 2 HAFISCAL_PERMGROFAC_FIX=1
arm orig_pfx 2 HAFISCAL_PF_DECAY_EXTRAP=1
echo "P18 DELL DONE $(date +%H:%M:%S)"
