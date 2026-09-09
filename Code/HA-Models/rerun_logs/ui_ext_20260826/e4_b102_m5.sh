#!/usr/bin/env bash
# e4_b102_m5.sh — BUG-102 A/B on ccarroll-m5 (2026-08-29): the fixed replay path (applied permanent shock = psi x
# PermGroFac[realized state]; the unemployed no longer inherit the employed growth) vs the pre-fix own-loop reference
# `Baseline_uiA_nshareEW_seed0-4` (the equal-weight own AD loop of the 08-28 triple, same seeds, same conventions —
# ONE difference: the fix). Own loop because m5's store holds no published Baseline equilibria (the diagnostic 5a arms
# ran with publishing off). Compare on dell: econ1_gate_diagnostics.py compare Baseline_uiA nshareEW b102EW.
set -u
REPO=$HOME/GitHub/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python; HA=$REPO/Code/HA-Models
LOG=$HOME/ui_ext_20260826; mkdir -p $LOG; cd $FPC; source $HA/launch_helpers.sh
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark HAFISCAL_USE_SOLUTION_CACHE=0
export HAFISCAL_MC_WEIGHTED_TAIL=0 HAFISCAL_REPLAY_PERSTATE_GROWTH=1
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
MODE=b102EW
stamp "arm $MODE (BUG-102 fix ON, equal-weight own loop; tree $(git -C $REPO rev-parse --short HEAD))"
for K in 0 1 2 3 4; do T1=$(date +%s); stamp "w6[Baseline uiA $MODE] seed $K start"
  runw6 --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_uiA_${MODE}_seed$K --table-dir Tables/Baseline_uiA_${MODE}_seed$K > $LOG/w6_Baseline_uiA_${MODE}_seed$K.log 2>&1; rc=$?
  stamp "w6[Baseline uiA $MODE] seed $K end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_uiA_${MODE}_seed$K 2>/dev/null | wc -l)"; grep -h "FAIL rc=\|NotImplemented\|Traceback" $LOG/w6_Baseline_uiA_${MODE}_seed$K.log | head -2
done
stamp "band[uiA $MODE S=5]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_uiA_${MODE}_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_uiA_${MODE}_S5_seed_band.tex 2>&1 | tail -12
echo "E4 B102 DONE $(date +%H:%M:%S) on $(hostname)"
