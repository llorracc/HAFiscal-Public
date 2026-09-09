#!/bin/bash
# AD-equilibrium sharing gate (ccarroll-m5, Reduced_Run), both worlds:
#   M_eq[_ac]      multiplier entry, SHARE=1, fresh store  -> policies + 4 equilibrium entries
#   W_ref[_ac]     welfare battery, SHARE=0 on that store  -> loads policies, runs its own MC AD loop (reference)
#   W_eq[_ac]      welfare battery, SHARE=1 on that store  -> installs the 4 equilibria, SKIPS every AD loop
#   W_eq_empty     welfare battery, SHARE=1 on a copy of the store WITHOUT equilibrium entries -> must FAIL loudly
# Report: W_eq vs W_ref cells (= the TM-vs-MC AD fixed-point gap at Reduced_Run); AD-loop skips; misses.
set -u
EXPECT=${1:?expected short HEAD}
W=$HOME/coldrun_ps; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
OUT=$HOME/coldrun_ps_gate_eq; S=$HOME/coldrun_ps_store_eq; SAC=$HOME/coldrun_ps_store_eq_ac; SNOEQ=$HOME/coldrun_ps_store_eq_noeq
rm -rf $OUT $S $SAC $SNOEQ; mkdir -p $OUT
git -C $W checkout -q -- . ; git -C $W pull --ff-only origin 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC 2>&1 | tail -1
HEAD=$(git -C $W rev-parse --short HEAD); echo "worktree at $HEAD (expected $EXPECT)"
[ "$HEAD" = "$EXPECT" ] || { echo "GATE ABORTED: HEAD $HEAD != $EXPECT"; echo "GATE DONE"; exit 9; }
cd $W/Code/HA-Models/FromPandemicCode
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
AC="HAFISCAL_WORLD=as-corrected"
wrun() { tag=$1; shift; rm -rf $OUT/$tag; mkdir -p $OUT/$tag/logs; echo "=== $tag (welfare) start $(date +%H:%M:%S)"; rm -rf ../solution_cache/Reduced_Run; env "$@" $PY run_welfare6_parallel.py --parametrization Reduced_Run --out-dir $OUT/$tag/out --table-dir $OUT/$tag/tables > $OUT/$tag.log 2>&1; echo "=== $tag end $(date +%H:%M:%S) rc=$? tables=$(ls $OUT/$tag/tables 2>/dev/null | wc -l | tr -d ' ')"; cp -R welfare6_parallel_logs/Reduced_Run/. $OUT/$tag/logs/ 2>/dev/null; echo "   policy-store: hits=$(grep -rh 'policy-store\] HIT' $OUT/$tag/logs | wc -l | tr -d ' ') saved=$(grep -rh 'policy-store\] SAVED' $OUT/$tag/logs | wc -l | tr -d ' ') miss=$(grep -rl 'MISS at' $OUT/$tag/logs | wc -l | tr -d ' ') | equilibrium: HIT=$(grep -rh 'ad-equilibrium\] HIT' $OUT/$tag/logs | wc -l | tr -d ' ') skipped-loops=$(grep -rh 'AD loop SKIPPED' $OUT/$tag/logs | wc -l | tr -d ' ') AD-solves=$(grep -rh 'AD solve took' $OUT/$tag/logs | wc -l | tr -d ' ')"; grep -rh "ad-equilibrium\] MISS\|RuntimeError: \[ad-equilibrium\]" $OUT/$tag/logs | head -1 | cut -c1-160; grep -h "FAIL rc=" $OUT/$tag.log | head -2; }
mrun() { tag=$1; shift; rm -rf $OUT/$tag; mkdir -p $OUT/$tag; echo "=== $tag (multiplier) start $(date +%H:%M:%S)"; rm -rf Tables/Reduced_Run Figures/Reduced_Run; env "$@" $PY AggFiscalMAIN_reduced.py > $OUT/$tag.log 2>&1; echo "=== $tag end $(date +%H:%M:%S) rc=$?"; cp -R Tables/Reduced_Run $OUT/$tag/Tables 2>/dev/null; echo "   equilibrium SAVED: $(grep -c 'ad-equilibrium\] SAVED' $OUT/$tag.log); policy SAVED: $(grep -c 'policy-store\] SAVED' $OUT/$tag.log)"; grep -h "ad-equilibrium\] save skipped\|Traceback" $OUT/$tag.log | head -2 | cut -c1-160; }
mrun M_eq        HAFISCAL_POLICY_STORE_DIR=$S   HAFISCAL_AD_EQUILIBRIUM_SHARE=1
wrun W_ref       HAFISCAL_POLICY_STORE_DIR=$S   HAFISCAL_AD_EQUILIBRIUM_SHARE=0
wrun W_eq        HAFISCAL_POLICY_STORE_DIR=$S   HAFISCAL_AD_EQUILIBRIUM_SHARE=1
cp -R $S $SNOEQ && rm -rf $SNOEQ/equilibrium
wrun W_eq_empty  HAFISCAL_POLICY_STORE_DIR=$SNOEQ HAFISCAL_AD_EQUILIBRIUM_SHARE=1
mrun M_eq_ac     HAFISCAL_POLICY_STORE_DIR=$SAC HAFISCAL_AD_EQUILIBRIUM_SHARE=1 $AC
wrun W_ref_ac    HAFISCAL_POLICY_STORE_DIR=$SAC HAFISCAL_AD_EQUILIBRIUM_SHARE=0 $AC
wrun W_eq_ac     HAFISCAL_POLICY_STORE_DIR=$SAC HAFISCAL_AD_EQUILIBRIUM_SHARE=1 $AC
echo "=== cells: W_eq vs W_ref (default) and W_eq_ac vs W_ref_ac (as-corrected) = TM-vs-MC AD equilibrium gap"
$PY ~/bug090_cells.py $OUT W_ref W_eq; $PY ~/bug090_cells.py $OUT W_ref_ac W_eq_ac
echo "=== store contents"; for st in $S $SAC; do echo "$(basename $st): policies=$(find $st -path '*/equilibrium' -prune -o -name '*.pkl' -print | wc -l | tr -d ' ') equilibria=$(ls $st/equilibrium/*/*.pkl 2>/dev/null | wc -l | tr -d ' ')"; done
echo "GATE DONE $(date +%H:%M:%S)"
