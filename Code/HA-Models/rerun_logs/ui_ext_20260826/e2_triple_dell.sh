#!/bin/bash
# Econ-2 same-seed TRIPLE at 1x (owner 2026-08-28 10:20: "cancel P32 and run the 1x same-seed triple instead"). Baseline,
# default world, paper's UI window, seeds 0-4, one code state:
#   shared      = Tables/Baseline_uiA_plainH_seed*   (the e1h arm: 5a's TM equilibrium installed; weighted-tail panel)  [already running]
#   nshareEW    = own AD loop, EQUAL-WEIGHT panel     (HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_MC_WEIGHTED_TAIL=0)
#   nshareW     = own AD loop, WEIGHTED-TAIL panel    (HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_MC_WEIGHTED_TAIL=200; guard lifted for the HARK path)
# The AD-converged cache is OFF for both own-loop arms (a cached 08-27 fixed point is not "the same code state").
# Pre-registered prediction (review 2026-08-28): |nshareW - nshareEW| <~ 0.3 % on check_rec_AD; the ~1 % gap to shared survives.
# Through runq (battery slot); one arm at a time; compare with econ1_gate_diagnostics.py compare Baseline_uiA plainH nshareEW,nshareW
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python; HA=$REPO/Code/HA-Models
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC; source $HA/launch_helpers.sh
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark HAFISCAL_USE_SOLUTION_CACHE=0
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
for MODE in nshareEW nshareW; do
  [ $MODE = nshareEW ] && export HAFISCAL_MC_WEIGHTED_TAIL=0 || export HAFISCAL_MC_WEIGHTED_TAIL=200
  stamp "arm $MODE (WEIGHTED_TAIL=$HAFISCAL_MC_WEIGHTED_TAIL)"
  for K in 0 1 2 3 4; do T1=$(date +%s); stamp "w6[Baseline uiA $MODE] seed $K start"
    runw6 --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_uiA_${MODE}_seed$K --table-dir Tables/Baseline_uiA_${MODE}_seed$K > $LOG/w6_Baseline_uiA_${MODE}_seed$K.log 2>&1; rc=$?
    stamp "w6[Baseline uiA $MODE] seed $K end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_uiA_${MODE}_seed$K 2>/dev/null | wc -l)"; grep -h "FAIL rc=\|NotImplemented\|Traceback" $LOG/w6_Baseline_uiA_${MODE}_seed$K.log | head -2; done
  stamp "band[uiA $MODE S=5]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_uiA_${MODE}_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_uiA_${MODE}_S5_seed_band.tex 2>&1 | tail -11
  echo "E2 TRIPLE $MODE DONE $(date +%H:%M:%S)"
done
echo "E2 TRIPLE DONE $(date +%H:%M:%S)"
