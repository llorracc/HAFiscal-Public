#!/bin/bash
# BUG-092 Test C, MC arms redone: HAFISCAL_MULTIPLIER_ENGINE=mc alone did NOT switch the engine when
# AggFiscalMAIN_reduced.py is invoked directly (its Run_Dict reads HAFISCAL_SIM_METHOD before
# EstimParameters' setdefault runs) — the first attempt produced TM tables byte-identical to the tm arm.
# Pass HAFISCAL_SIM_METHOD=MC explicitly (what reproduce/reproduce_computed_mc_only.sh does).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
OUT=$REPO/Code/HA-Models/rerun_logs/bug092_localize; mkdir -p $OUT
cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
export HAFISCAL_POLICY_STORE_DIR=$HOME/.cache/hafiscal/policy_store_bug092
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
for CAP in uncapped capped; do
  X=""; [ $CAP = capped ] && X="HAFISCAL_T_AGE=200"
  tag=mc2_${CAP}; stamp "$tag start"; rm -rf Tables/Reduced_Run_$tag Figures/Reduced_Run_$tag
  env $X HAFISCAL_MULTIPLIER_ENGINE=mc HAFISCAL_SIM_METHOD=MC HAFISCAL_FIGS_SUFFIX=_$tag $PY AggFiscalMAIN_reduced.py > $OUT/$tag.log 2>&1; rc=$?
  stamp "$tag end rc=$rc"; grep "Multiplier" Tables/Reduced_Run_$tag/Multiplier_candidate.tex 2>/dev/null | cut -c1-110
  echo "   sim_method lines: $(grep -c 'sim_method\|Monte Carlo\|MC simulation' $OUT/$tag.log)"; grep -h "\[drift" $OUT/$tag.log | grep -i "log(p)" | head -8 | cut -c1-160
done
echo "=== summary: check column (no-AD, AD): TM vs MC, uncapped vs capped"
for CAP in uncapped capped; do for ENG in tm mc2; do f=Tables/Reduced_Run_${ENG}_${CAP}/Multiplier_candidate.tex; [ -f $f ] && echo "$ENG $CAP: noAD=$(grep 'no AD effect' $f | grep -o '&[^&]*' | head -1 | tr -d '& ') AD=$(grep '(AD effect)' $f | grep -o '&[^&]*' | head -1 | tr -d '& ')"; done; done
echo "TESTC2 DONE $(date +%H:%M:%S)"
