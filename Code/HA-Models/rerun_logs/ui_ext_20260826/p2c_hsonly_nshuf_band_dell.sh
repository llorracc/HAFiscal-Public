#!/bin/bash
# G1 addendum (dell, 2026-08-26): the NON-shuffled legacy band at HS_Only, seeds 1..5 (seed 0 exists: legacy_nshuf_seed0),
# so the three engines can be compared on the same cells: legacy+stratified (6 seeds), calendar+stratified (6), legacy
# non-shuffled (6). Same env as p2_hsonly_dell.sh's exactness arm (own AD loops, MC_SHUFFLE=0). Two batteries at a time.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1
export HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_MC_SHUFFLE=0 HAFISCAL_AD_EQUILIBRIUM_SHARE=0   # policy pinned: inert under legacy but part of the store key (12:04 entries were keyed with window)
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
w6() { K=$1; stamp "w6[legacy_nshuf] seed $K start"; $PY run_welfare6_parallel.py --parametrization HS_Only --seed-offset $K --max-cpu-slots 3 --out-dir welfare6_scenario_results_HS_Only_legacy_nshuf_seed$K --table-dir Tables/HS_Only_legacy_nshuf_seed$K > $LOG/w6_legacy_nshuf_seed$K.log 2>&1; stamp "w6[legacy_nshuf] seed $K end rc=$? miss=$(grep -c 'MISS at' $LOG/w6_legacy_nshuf_seed$K.log)"; }
w6 1 & w6 2 & wait; w6 3 & w6 4 & wait; w6 5
echo "P2C DONE $(date +%H:%M:%S)"
