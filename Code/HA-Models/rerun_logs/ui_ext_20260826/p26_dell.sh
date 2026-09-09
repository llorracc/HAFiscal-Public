#!/bin/bash
# P26 (dell, 2026-08-27 17:35). Sharing certification, part 2. The N-ladder (P23, m5) showed the OWN-LOOP AD cells do not
# converge toward the SHARED cells as the panel grows (check_rec_AD +1.35/+1.47/+1.63 % at 1x/4x/10x agents, taxcut_rec_AD
# +1.07 % flat, SE <= 0.05 % at 10x) -> the residual is not Monte Carlo finite-N. The own-loop battery cannot carry the
# weighted-tail sampler (welfare6_scenario refuses), so the remaining split is on the SHARED side: vary the sampler's tail
# strata K (default 200) and the panel size at fixed K. If the shared cells move toward the own-loop ones with K, the
# residual is the sampler's; if flat, it is the TM equilibrium vs the MC's own fixed point. Waits for P24 (dell).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
until grep -q "P24 DELL DONE" $LOG/p24.out 2>/dev/null; do sleep 60; done
echo "P24 finished; starting P26 at HEAD $(git -C $REPO rev-parse --short HEAD) $(date +%H:%M:%S)"
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_AD_EQUILIBRIUM_SHARE=1 HAFISCAL_WELFARE_ENGINE=hark
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
rung() { tag=$1; K=$2; N=$3; NARG=(); [ "$N" != default ] && NARG=(--agent-count-total $N)
  for S in 0 1; do T1=$(date +%s); stamp "w6[$tag K=$K N=$N] seed $S start"
    env HAFISCAL_MC_WEIGHTED_TAIL=$K $PY run_welfare6_parallel.py --baseline --seed-offset $S "${NARG[@]}" --out-dir welfare6_scenario_results_Baseline_${tag}_seed$S --table-dir Tables/Baseline_${tag}_seed$S > $LOG/w6_${tag}_seed$S.log 2>&1; rc=$?
    stamp "w6[$tag K=$K N=$N] seed $S end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_${tag}_seed$S/*.tex 2>/dev/null | wc -l)"; done; }
rung uiA_wtK50   50   default
rung uiA_wtK800  800  default
rung uiA_wtK2000 2000 default
rung uiA_N4      200  40000
echo "P26 DELL DONE $(date +%H:%M:%S)"
