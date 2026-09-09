#!/bin/bash
# BUG-092 Test C3: the MC multiplier engine, uncapped and capped, with the pLvl drift gate downgraded
# to a WARNING (HAFISCAL_DRIFT_HARD_FAIL=0): C2's uncapped run hard-failed the gate (MC var log p 2.5 %
# below the TM-analytical value, outside the N-aware band) — we want its multipliers AND its drift lines.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
OUT=$REPO/Code/HA-Models/rerun_logs/bug092_localize; mkdir -p $OUT
cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
export HAFISCAL_POLICY_STORE_DIR=$HOME/.cache/hafiscal/policy_store_bug092 HAFISCAL_DRIFT_HARD_FAIL=0
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
for CAP in uncapped capped; do
  X=""; [ $CAP = capped ] && X="HAFISCAL_T_AGE=200"
  tag=mc3_${CAP}; stamp "$tag start"; rm -rf Tables/Reduced_Run_$tag Figures/Reduced_Run_$tag
  env $X HAFISCAL_MULTIPLIER_ENGINE=mc HAFISCAL_SIM_METHOD=MC HAFISCAL_FIGS_SUFFIX=_$tag $PY AggFiscalMAIN_reduced.py > $OUT/$tag.log 2>&1; rc=$?
  stamp "$tag end rc=$rc"; grep "Multiplier" Tables/Reduced_Run_$tag/Multiplier_candidate.tex 2>/dev/null | cut -c1-110
  grep -h "\[drift" $OUT/$tag.log | grep -i "log(p)\|EXCEEDS\|pass" | head -9 | cut -c1-150
  grep -h "Traceback" -A3 $OUT/$tag.log | tail -3 | cut -c1-150
done
echo "=== summary: check column (no-AD, AD): TM vs MC, uncapped vs capped"
for CAP in uncapped capped; do for ENG in tm mc3; do f=Tables/Reduced_Run_${ENG}_${CAP}/Multiplier_candidate.tex; [ -f $f ] && echo "$ENG $CAP: noAD=$(grep 'no AD effect' $f | grep -o '&[^&]*' | head -1 | tr -d '& ') AD=$(grep '(AD effect)' $f | grep -o '&[^&]*' | head -1 | tr -d '& ')"; done; done
echo "TESTC3 DONE $(date +%H:%M:%S)"
