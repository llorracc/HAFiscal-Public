#!/bin/bash
# BUG-092 localization variants (m5, Reduced_Run, welfare AD cells: HARK-engine own MC AD loop vs the
# TM equilibrium published by 5a). Reference points from 2026-08-25 night:
#   uncapped default world: HARK loop vs TM  check +4.4 %  (V0)
#   capped (T_AGE=200), cohort pi_Q:         check -0.3 %  (V2)
# Variants (one seam each):
#   VA  capped world + HAFISCAL_TM_Q_METHOD=doob         -> Doob baseline UNDER the cap
#   VB  uncapped world + HAFISCAL_TM_PROP_CAP_T_AGE=200  -> cap only in the AD-TM propagation
set -u
EXPECT=${1:?expected short HEAD}
W=$HOME/coldrun_ps; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
OUT=$HOME/coldrun_ps_bug092; rm -rf $OUT; mkdir -p $OUT
git -C $W checkout -q -- . ; git -C $W pull --ff-only origin 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC 2>&1 | tail -1
HEAD=$(git -C $W rev-parse --short HEAD); echo "worktree at $HEAD (expected $EXPECT)"; [ "$HEAD" = "$EXPECT" ] || { echo "ABORTED: HEAD mismatch"; echo "VARIANTS DONE"; exit 9; }
cd $W/Code/HA-Models/FromPandemicCode
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
wrun() { tag=$1; shift; rm -rf $OUT/$tag; mkdir -p $OUT/$tag/logs; echo "=== $tag start $(date +%H:%M:%S)"; rm -rf ../solution_cache/Reduced_Run; env "$@" $PY run_welfare6_parallel.py --parametrization Reduced_Run --out-dir $OUT/$tag/out --table-dir $OUT/$tag/tables > $OUT/$tag.log 2>&1; echo "=== $tag end $(date +%H:%M:%S) rc=$? tables=$(ls $OUT/$tag/tables 2>/dev/null | wc -l | tr -d ' ')"; cp -R welfare6_parallel_logs/Reduced_Run/. $OUT/$tag/logs/ 2>/dev/null; echo "   equilibrium HIT=$(grep -rh 'ad-equilibrium\] HIT' $OUT/$tag/logs | wc -l | tr -d ' ') skipped=$(grep -rh 'AD loop SKIPPED' $OUT/$tag/logs | wc -l | tr -d ' ') miss=$(grep -rl 'MISS at' $OUT/$tag/logs | wc -l | tr -d ' ')"; }
mrun() { tag=$1; shift; echo "=== $tag (multiplier) start $(date +%H:%M:%S)"; rm -rf Tables/Reduced_Run Figures/Reduced_Run; env "$@" $PY AggFiscalMAIN_reduced.py > $OUT/$tag.log 2>&1; echo "=== $tag end $(date +%H:%M:%S) rc=$? equilibria SAVED=$(grep -c 'ad-equilibrium\] SAVED' $OUT/$tag.log) knob-lines=$(grep -c 'HAFISCAL_TM_Q_METHOD\|HAFISCAL_TM_PROP_CAP' $OUT/$tag.log)"; grep "Multiplier" Tables/Reduced_Run/Multiplier_candidate.tex | cut -c1-100; mkdir -p $OUT/$tag; cp Tables/Reduced_Run/Multiplier_candidate.tex $OUT/$tag/ 2>/dev/null; }
for V in VA VB; do
  case $V in VA) X="HAFISCAL_T_AGE=200 HAFISCAL_TM_Q_METHOD=doob";; VB) X="HAFISCAL_TM_PROP_CAP_T_AGE=200";; esac
  S=$HOME/coldrun_ps_store_bug092_$V; rm -rf $S
  echo "##### $V: $X"
  mrun M_$V   HAFISCAL_POLICY_STORE_DIR=$S HAFISCAL_AD_EQUILIBRIUM_SHARE=1 $X
  wrun Wh_$V  HAFISCAL_POLICY_STORE_DIR=$S HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark $X
  wrun We_$V  HAFISCAL_POLICY_STORE_DIR=$S HAFISCAL_AD_EQUILIBRIUM_SHARE=1 $X
  echo "=== $V cells: TM equilibrium (We) vs HARK loop (Wh)"; $PY ~/bug090_cells.py $OUT We_$V Wh_$V
done
echo "VARIANTS DONE $(date +%H:%M:%S)"
