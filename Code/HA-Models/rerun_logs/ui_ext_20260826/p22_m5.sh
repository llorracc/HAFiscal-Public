#!/bin/bash
# P22 on ccarroll-m5 (2026-08-27 14:50): the "+ no age cap" column's battery seeds 1..4 under the certified machinery (seed 0
# ran on xubuntark, 246 min; moved here). Default-world economics with the permanent shocks OFF and the paper's UI window;
# calendar chain + stratified shuffle, own AD loops, HARK engine, equal-weight panel. Waits for P21 (uiB under hark).
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
LOG=$HOME/ui_ext_20260826
until grep -q "P21 M5 DONE" $HOME/p21_m5.out 2>/dev/null; do sleep 120; done
echo "P21 finished; starting P22 $(date +%H:%M:%S)"; cd $FPC
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_PERM_DURING_UNEMP=off HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark HAFISCAL_MC_WEIGHTED_TAIL=0
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
for K in 1 2 3 4; do T1=$(date +%s); stamp "w6[nocap_pkg] seed $K start"; $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_nocap_pkg_seed$K --table-dir Tables/Baseline_nocap_pkg_seed$K > $LOG/w6_nocap_pkg_seed$K.log 2>&1; stamp "w6[nocap_pkg] seed $K end rc=$? wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_nocap_pkg_seed$K 2>/dev/null | wc -l | tr -d " ")"; done
echo "P22 M5 DONE $(date +%H:%M:%S)"
