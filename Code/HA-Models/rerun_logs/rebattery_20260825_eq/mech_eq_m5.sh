#!/bin/bash
# Mechanism test for the default-world TM-vs-MC AD gap (check_rec_AD +4.4 % HARK-loop vs TM at Reduced_Run;
# as-corrected world agrees within 0.4 %). Two variants of the DEFAULT world, each: fresh store, 5a with
# SHARE=1 (publishes TM equilibria), W_hark (own HARK-MC loop, SHARE=0), W_eq (TM equilibrium, SHARE=1).
#   V1: HAFISCAL_PERM_DURING_UNEMP=off   (the as-corrected income convention; sole economic world difference)
#   V2: HAFISCAL_T_AGE=200               (the as-corrected age cap)
set -u
W=$HOME/coldrun_ps; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
OUT=$HOME/coldrun_ps_mech_eq; rm -rf $OUT; mkdir -p $OUT
cd $W/Code/HA-Models/FromPandemicCode
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
wrun() { tag=$1; shift; rm -rf $OUT/$tag; mkdir -p $OUT/$tag/logs; echo "=== $tag start $(date +%H:%M:%S)"; rm -rf ../solution_cache/Reduced_Run; env "$@" $PY run_welfare6_parallel.py --parametrization Reduced_Run --out-dir $OUT/$tag/out --table-dir $OUT/$tag/tables > $OUT/$tag.log 2>&1; echo "=== $tag end $(date +%H:%M:%S) rc=$? tables=$(ls $OUT/$tag/tables 2>/dev/null | wc -l | tr -d ' ')"; cp -R welfare6_parallel_logs/Reduced_Run/. $OUT/$tag/logs/ 2>/dev/null; echo "   equilibrium HIT=$(grep -rh 'ad-equilibrium\] HIT' $OUT/$tag/logs | wc -l | tr -d ' ') skipped=$(grep -rh 'AD loop SKIPPED' $OUT/$tag/logs | wc -l | tr -d ' ') miss=$(grep -rl 'MISS at' $OUT/$tag/logs | wc -l | tr -d ' ')"; }
mrun() { tag=$1; shift; echo "=== $tag (multiplier) start $(date +%H:%M:%S)"; rm -rf Tables/Reduced_Run Figures/Reduced_Run; env "$@" $PY AggFiscalMAIN_reduced.py > $OUT/$tag.log 2>&1; echo "=== $tag end $(date +%H:%M:%S) rc=$? equilibria SAVED=$(grep -c 'ad-equilibrium\] SAVED' $OUT/$tag.log)"; grep "(AD effect)" Tables/Reduced_Run/Multiplier_candidate.tex | cut -c1-100; }
for V in V1 V2; do
  case $V in V1) X="HAFISCAL_PERM_DURING_UNEMP=off";; V2) X="HAFISCAL_T_AGE=200";; esac
  S=$HOME/coldrun_ps_store_mech_$V; rm -rf $S
  echo "##### $V: default world + $X"
  mrun M_$V     HAFISCAL_POLICY_STORE_DIR=$S HAFISCAL_AD_EQUILIBRIUM_SHARE=1 $X
  wrun Wh_$V    HAFISCAL_POLICY_STORE_DIR=$S HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark $X
  wrun We_$V    HAFISCAL_POLICY_STORE_DIR=$S HAFISCAL_AD_EQUILIBRIUM_SHARE=1 $X
  echo "=== $V cells: HARK loop (Wh) vs TM equilibrium (We)"; $PY ~/bug090_cells.py $OUT We_$V Wh_$V
done
echo "MECH DONE $(date +%H:%M:%S)"
