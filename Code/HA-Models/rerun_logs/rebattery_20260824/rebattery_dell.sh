#!/bin/bash
# Baseline S=3 welfare re-battery (BUG-090 + BUG-091), dell: default world seeds 0,1,2, then the
# as-corrected multiplier populate + as-corrected seed 2 (m5 does as-corrected seeds 0,1).
# Strict store mode is the welfare entry point's default: each world's multiplier program runs
# FIRST on this machine to populate ~/.cache/hafiscal/policy_store; the welfare batteries only load.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode
PY=$REPO/.venv/bin/python; LOG=$REPO/Code/HA-Models/rerun_logs/rebattery_20260824; mkdir -p $LOG
EXPECT=${1:?expected short HEAD}; HEAD=$(git -C $REPO rev-parse --short HEAD)
echo "main checkout at $HEAD (expected $EXPECT) $(date +%H:%M:%S)"; [ "$HEAD" = "$EXPECT" ] || { echo "ABORTED: HEAD mismatch"; exit 9; }
cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
mult() { world=$1; sfx=$2; stamp "multiplier[$world] start"; env HAFISCAL_WORLD=$world HAFISCAL_FIGS_SUFFIX=$sfx $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_$world.log 2>&1; rc=$?; stamp "multiplier[$world] end rc=$rc"; grep "AD effect)" Tables/Baseline$sfx/Multiplier_candidate.tex 2>/dev/null | head -1; grep -c "policy-store\] SAVED" $LOG/mult_$world.log; [ $rc -eq 0 ] || exit 10; }
w6() { world=$1; K=$2; tag=$3; stamp "welfare[$world] seed $K start"; env HAFISCAL_WORLD=$world $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${tag}_seed$K --table-dir Tables/Baseline_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1; rc=$?; stamp "welfare[$world] seed $K end rc=$rc tables=$(ls Tables/Baseline_${tag}_seed$K 2>/dev/null | wc -l)"; mkdir -p $LOG/w6logs_${tag}_seed$K; cp -R welfare6_parallel_logs/Baseline/. $LOG/w6logs_${tag}_seed$K/ 2>/dev/null; echo "   store: hits=$(grep -rh 'policy-store\] HIT' $LOG/w6logs_${tag}_seed$K | wc -l) saved=$(grep -rh 'policy-store\] SAVED' $LOG/w6logs_${tag}_seed$K | wc -l) miss-errors=$(grep -rh 'MISS at' $LOG/w6logs_${tag}_seed$K | wc -l)"; grep -h "FAIL rc=" $LOG/w6_${tag}_seed$K.log | head -3; [ $rc -eq 0 ] || echo "   WELFARE FAILED (continuing to next seed)"; }
mult default _r2
for K in 0 1 2; do w6 default $K r2; done
mult as-corrected _ac_r2
w6 as-corrected 2 ac_r2
stamp "default-world band"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_r2_seed0/welfare6_parallel_summary.json Tables/Baseline_r2_seed1/welfare6_parallel_summary.json Tables/Baseline_r2_seed2/welfare6_parallel_summary.json --out $LOG/welfare6_r2_seed_band.tex 2>&1 | tail -12
echo "REBATTERY DELL DONE $(date +%H:%M:%S)"
