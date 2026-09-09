#!/bin/bash
# P23 on ccarroll-m5 (2026-08-27 15:25; owner "go ahead and queue the sharing N-ladder for tonight"): CERTIFICATION TEST for
# AD-equilibrium sharing. The certified OWN-LOOP battery (default world, paper's UI window, calendar chain + stratified
# shuffle, HARK engine, no sharing, equal-weight panel = the package column Baseline_uiA_nshare, 1x = 10 000 agents) at 4x and
# 10x the panel, seeds 0,1 -> Tables/Baseline_uiA_nshare_N4_seed*, Baseline_uiA_nshare_N10_seed*. Compare tomorrow with the
# SHARED-equilibrium cells (Baseline_uiA, S=5): if the own-loop cells converge TOWARD the shared ones as N grows, the −1 %
# residual is the finite-N Monte Carlo AD fixed point and sharing is the more exact method (certified); if not, sharing leaves
# the world of record. 10x runs with --max-cpu-slots 3 (memory). Waits for P22 (the no-cap seeds).
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
LOG=$HOME/ui_ext_20260826
until grep -q "P22 M5 DONE" $HOME/p22_m5.out 2>/dev/null; do sleep 120; done
echo "P22 finished; starting P23 at $(git -C $W rev-parse --short HEAD) $(date +%H:%M:%S)"; cd $FPC
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark HAFISCAL_MC_WEIGHTED_TAIL=0
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
rung() { tag=$1; N=$2; slots=$3
  for K in 0 1; do T1=$(date +%s); stamp "w6[$tag N=$N] seed $K start"; $PY run_welfare6_parallel.py --baseline --seed-offset $K --agent-count-total $N --max-cpu-slots $slots --out-dir welfare6_scenario_results_Baseline_${tag}_seed$K --table-dir Tables/Baseline_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1; stamp "w6[$tag N=$N] seed $K end rc=$? wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_${tag}_seed$K 2>/dev/null | wc -l | tr -d " ")"; grep -h "FAIL rc=\|Killed\|MemoryError" $LOG/w6_${tag}_seed$K.log | head -2; done; }
rung uiA_nshare_N4 40000 6
rung uiA_nshare_N10 100000 3
echo "P23 M5 DONE $(date +%H:%M:%S)"
