#!/bin/bash
# P27 (dell, 2026-08-27 18:35): K-ladder part 2. K above the sampler cap is inert at 1x (K=800 byte-identical to K=200), so the
# Cap rule (tm_methods.py ~7731): K_eff = min(K, max(2, N_i // 4)); at Baseline 1x N_i = 10000/21 ~ 476 -> K_eff = 119 for any K >= 119,
# so the K axis only exists at larger panels: 4x (N_i ~ 1905, cap 476) and 10x (N_i ~ 4762, cap 1190). Rungs below: 4x@K200, 4x@K50, 10x@K200.
# converge toward the SHARED cells as the panel grows (check_rec_AD +1.35/+1.47/+1.63 % at 1x/4x/10x agents, taxcut_rec_AD
# +1.07 % flat, SE <= 0.05 % at 10x) -> the residual is not Monte Carlo finite-N. The own-loop battery cannot carry the
# weighted-tail sampler (welfare6_scenario refuses), so the remaining split is on the SHARED side: vary the sampler's tail
# strata K (default 200) and the panel size at fixed K. If the shared cells move toward the own-loop ones with K, the
# residual is the sampler's; if flat, it is the TM equilibrium vs the MC's own fixed point. Waits for P24 (dell).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
until grep -q "P26 STOPPED" $LOG/p26.out 2>/dev/null; do sleep 60; done
echo "P26 stopped; starting P27 at HEAD $(git -C $REPO rev-parse --short HEAD) $(date +%H:%M:%S)"
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_AD_EQUILIBRIUM_SHARE=1 HAFISCAL_WELFARE_ENGINE=hark
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
rung() { tag=$1; K=$2; N=$3; NARG=(); [ "$N" != default ] && NARG=(--agent-count-total $N)
  for S in 0 1; do T1=$(date +%s); stamp "w6[$tag K=$K N=$N] seed $S start"
    env HAFISCAL_MC_WEIGHTED_TAIL=$K $PY run_welfare6_parallel.py --baseline --seed-offset $S "${NARG[@]}" --out-dir welfare6_scenario_results_Baseline_${tag}_seed$S --table-dir Tables/Baseline_${tag}_seed$S > $LOG/w6_${tag}_seed$S.log 2>&1; rc=$?
    stamp "w6[$tag K=$K N=$N] seed $S end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_${tag}_seed$S/*.tex 2>/dev/null | wc -l)"; done; }
rung uiA_N4      200  40000
rung uiA_N4_wtK50 50  40000
rung uiA_N10     200  100000
echo "P27 DELL DONE $(date +%H:%M:%S)"
