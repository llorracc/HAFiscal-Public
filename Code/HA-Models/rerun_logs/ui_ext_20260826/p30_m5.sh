#!/bin/bash
# P30 on ccarroll-m5 (2026-08-27 23:00; owner "go ahead with all of it"). After P29 M5: (B5) the two m5 appendix configs under the HISTORY UI policy (B): LowerUBnoB_histB, CRRA3_histB.
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
RES=$W/Code/HA-Models/Results; LOG=$HOME/ui_ext_20260826; mkdir -p $LOG
until grep -q "P29 M5 DONE" $HOME/p29_m5.out 2>/dev/null; do sleep 120; done
cd $FPC; source $HOME/p29_common.sh
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window
echo "P30 M5 starting at $(git -C $W rev-parse --short HEAD) $(date +%H:%M:%S)"
# --- B4 DROPPED 2026-08-27 23:20: the gamma = 1 row was already removed by an owner ruling of 2026-08-21 (Subfiles/Appendix-Robustness.tex
#     lines 143-152: at log utility no configuration satisfies the GIC and matches the wealth targets; BUG-086). Nothing to run.
# --- B5 (m5 share): the history UI policy
export HAFISCAL_UI_EXTENSION_POLICY=history
cfgB() { NAME=$1; TAG=${NAME}_histB
  T0=$(date +%s); stamp "5a[$TAG] start"; HAFISCAL_FIGS_SUFFIX=_histB $PY AggFiscalMAIN_reduced.py --parametrization $NAME > $LOG/mult_$TAG.log 2>&1; rc=$?
  stamp "5a[$TAG] end rc=$rc wall=$(( ($(date +%s)-T0)/60 ))min"; grep "AD effect)\|expenditure during" Tables/$TAG/Multiplier_candidate.tex 2>/dev/null; [ $rc -eq 0 ] || return
  for K in 0 1 2; do T1=$(date +%s); stamp "w6[$TAG] seed $K start"
    $PY run_welfare6_parallel.py --parametrization $NAME --seed-offset $K --out-dir welfare6_scenario_results_${TAG}_seed$K --table-dir Tables/${TAG}_seed$K > $LOG/w6_${TAG}_seed$K.log 2>&1; rc=$?
    stamp "w6[$TAG] seed $K end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/${TAG}_seed$K/*.tex 2>/dev/null | wc -l)"; done
  stamp "band[$TAG]"; $PY compute_welfare6_se_table.py --summaries Tables/${TAG}_seed{0,1,2}/welfare6_parallel_summary.json --out $LOG/welfare6_${TAG}_S3_seed_band.tex 2>&1 | tail -n 4; }
cfgB LowerUBnoB; cfgB CRRA3
echo "P30 M5 DONE $(date +%H:%M:%S)"
