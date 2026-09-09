#!/bin/bash
# Probe: why does the welfare battery MISS the equilibria 5a published? Runs ONE AD cell
# (recessionCheck_AD, Reduced_Run) against the gate's as-corrected store with SHARE=1 and
# strict mode, using the worktree's equilibrium_store.py (scp'd; NOT git-reverted here).
set -u
W=$HOME/coldrun_ps; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
SAC=$HOME/coldrun_ps_store_eq_ac; OUT=$HOME/coldrun_ps_probe_eq; rm -rf $OUT; mkdir -p $OUT
cd $W/Code/HA-Models/FromPandemicCode
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
echo "=== probe start $(date +%H:%M:%S)"
rm -rf ../solution_cache/Reduced_Run
env HAFISCAL_POLICY_STORE_DIR=$SAC HAFISCAL_AD_EQUILIBRIUM_SHARE=1 HAFISCAL_WORLD=as-corrected \
  $PY run_welfare6_parallel.py --parametrization Reduced_Run --scenarios recessionCheck_AD --out-dir $OUT/out --table-dir $OUT/tables > $OUT/probe.log 2>&1
echo "=== probe end $(date +%H:%M:%S) rc=$?"
grep -rh -A14 "ad-equilibrium\] MISS" welfare6_parallel_logs/Reduced_Run/ | head -40
ls $SAC/equilibrium/_misses/ 2>/dev/null
echo "PROBE DONE"
