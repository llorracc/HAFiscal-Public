#!/bin/bash
# P32 (dell, 2026-08-27 23:45; C6 follow-up). The shared-vs-own-loop gap is localized to the CHECK scenario's AD amplification
# (AD/noAD 1.383 shared vs 1.400-1.410 own-loop; no-AD responses identical; the recession's own AD contraction agrees). The
# own-loop panel's income level is 9-15 % below the analytical level (equal-weight sampling of the uncapped tail; ~N^-0.2), which
# raises the check's share of the panel's aggregate by 9-17 % -- the right sign and order. Decisive test: an own-loop panel at 40x
# (level bias ~ -5 %): if the amplification gap falls to ~+0.7 % the level is the mechanism. Waits for P31 (dell).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
until grep -q "P29C DELL DONE" $LOG/p29c.out 2>/dev/null; do sleep 180; done
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark HAFISCAL_MC_WEIGHTED_TAIL=0
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
echo "P29c finished (P31 dell leg cancelled: appendix follows the paper's window policy, owner 2026-08-28); P32 starting $(date +%H:%M:%S)"
T1=$(date +%s); stamp "w6[uiA_nshare_N40 N=400000] seed 0 start"
$PY run_welfare6_parallel.py --baseline --seed-offset 0 --agent-count-total 400000 --max-cpu-slots 3 --out-dir welfare6_scenario_results_Baseline_uiA_nshare_N40_seed0 --table-dir Tables/Baseline_uiA_nshare_N40_seed0 > $LOG/w6_uiA_nshare_N40_seed0.log 2>&1; rc=$?
stamp "w6[uiA_nshare_N40] seed 0 end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min"
echo "P32 DELL DONE $(date +%H:%M:%S)"
