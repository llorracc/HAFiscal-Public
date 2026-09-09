#!/bin/bash
# P19 on xubuntark (2026-08-27 10:50; owner protocol §5e): the "+ no age cap" column's welfare battery under the CERTIFIED
# machinery -- default-world economics with the permanent shocks still OFF and the paper's UI window (calendar chain,
# stratified shuffle, own AD loops, HARK engine, equal-weight panel; no sharing). Its 5a is Baseline_uiL_permoff (m5).
# Seeds 0..4 -> Tables/Baseline_nocap_pkg_seed*. Own solves. Slow box: ~40-75 min/seed after the cold first.
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
LOG=$HOME/ui_ext_20260826; cd $FPC
echo "worktree at $(git -C $W rev-parse --short HEAD) $(date +%H:%M:%S)"
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_PERM_DURING_UNEMP=off HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark HAFISCAL_MC_WEIGHTED_TAIL=0
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
for K in 0 1 2 3 4; do T1=$(date +%s); stamp "w6[nocap_pkg] seed $K start"; $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_nocap_pkg_seed$K --table-dir Tables/Baseline_nocap_pkg_seed$K > $LOG/w6_nocap_pkg_seed$K.log 2>&1; stamp "w6[nocap_pkg] seed $K end rc=$? wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Baseline_nocap_pkg_seed$K 2>/dev/null | wc -l)"; grep -h "FAIL rc=" $LOG/w6_nocap_pkg_seed$K.log | head -2; done
echo "P19 XUB DONE $(date +%H:%M:%S)"
