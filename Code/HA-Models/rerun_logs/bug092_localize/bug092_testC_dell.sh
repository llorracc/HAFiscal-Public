#!/bin/bash
# BUG-092 Test C (dell, Reduced_Run, default world): the multiplier program under BOTH engines
# (TM a-indexed vs the reliable-MC METHOD axis), uncapped and capped (T_age=200). Localizes the
# check-specific TM-vs-MC discrepancy to the NO-AD response if it is already there without any
# AD loop (then the site is the check delivery / analytical pLvl model, not the AD equilibrium).
# The MC engine's log also carries the N-aware pLvl-moment drift diagnostic (mean/var log p).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
OUT=$REPO/Code/HA-Models/rerun_logs/bug092_localize; mkdir -p $OUT
cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
export HAFISCAL_POLICY_STORE_DIR=$HOME/.cache/hafiscal/policy_store_bug092
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
for CAP in uncapped capped; do
  X=""; [ $CAP = capped ] && X="HAFISCAL_T_AGE=200"
  for ENG in tm mc; do
    tag=${ENG}_${CAP}; stamp "$tag start"; rm -rf Tables/Reduced_Run_$tag Figures/Reduced_Run_$tag
    env $X HAFISCAL_MULTIPLIER_ENGINE=$ENG HAFISCAL_FIGS_SUFFIX=_$tag $PY AggFiscalMAIN_reduced.py > $OUT/$tag.log 2>&1; rc=$?
    stamp "$tag end rc=$rc"; grep "Multiplier" Tables/Reduced_Run_$tag/Multiplier_candidate.tex 2>/dev/null | cut -c1-110
    grep -h "drift\|pLvl.*mean\|var.*log" $OUT/$tag.log | grep -iv "warn" | head -6 | cut -c1-160
  done
done
echo "=== summary: check column, no-AD and AD rows, TM vs MC, uncapped vs capped"
for CAP in uncapped capped; do for ENG in tm mc; do f=Tables/Reduced_Run_${ENG}_${CAP}/Multiplier_candidate.tex; [ -f $f ] && echo "$ENG $CAP: $(grep 'no AD effect' $f | grep -o '&[^&]*' | head -1 | tr -d '& ') (noAD) $(grep '(AD effect)' $f | grep -o '&[^&]*' | head -1 | tr -d '& ') (AD)"; done; done
echo "TESTC DONE $(date +%H:%M:%S)"
