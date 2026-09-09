#!/bin/bash
# P16 (dell, 2026-08-27 03:45): uiA seeds 3,4 again with HAFISCAL_POLICY_STORE_REQUIRE=0. P10's attempt hit a strict-store MISS:
# the uiA 5a (12:20) populated the store under the OLD key whitelist (the UI-policy vars were removed from the key ~16:00), so
# the battery's new keys find nothing. REQUIRE=0 lets the battery solve its own policies -- the store's HIT guarantee is byte-
# identity with a fresh solve, so seeds 3,4 are the same computation as 0-2. Then the S=5 band.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_POLICY_STORE_REQUIRE=0
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
for K in 3 4; do stamp "w6[uiA] seed $K start"; $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_uiA_seed$K --table-dir Tables/Baseline_uiA_seed$K > $LOG/w6_uiA_seed$K.log 2>&1; stamp "w6[uiA] seed $K end rc=$? tables=$(ls Tables/Baseline_uiA_seed$K 2>/dev/null | wc -l)"; grep -h "FAIL rc=\|MISS at\|equilibri.*not" $LOG/w6_uiA_seed$K.log | head -2; done
stamp "band[uiA S=5]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_uiA_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_uiA_S5_seed_band.tex 2>&1 | tail -11
echo "P16 DELL DONE $(date +%H:%M:%S)"
