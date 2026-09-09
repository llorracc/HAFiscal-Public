#!/bin/bash
# P3 of plans/20260826-0800h_ui-extension-calendar-window-encoding_plan.md (dell, 2026-08-26): Baseline S=3, both worlds.
#   default world  = Improvement A as the catalog now resolves it (HAFISCAL_UI_STATE_ENCODING=calendar, policy window):
#                    Step 5a multiplier program (TM a-indexed; populates the policy store + publishes the equilibria),
#                    then Step 5b welfare battery seeds 0,1,2 (AD-equilibrium sharing ON = the default world's default).
#   as-corrected   = the paper's encoding and policy (legacy) as the catalog resolves it; same sequence. Its 2026-08-25
#                    runs embedded the 05-16 policy (bug_fix) and are superseded by these.
# Sequential (the 08-24 rebattery pattern), in one transient systemd unit with MemoryMax.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; mkdir -p $LOG
EXPECT=${1:?expected short HEAD}; HEAD=$(git -C $REPO rev-parse --short HEAD)
echo "main checkout at $HEAD (expected $EXPECT) $(date +%H:%M:%S)"; [ "$HEAD" = "$EXPECT" ] || { echo "ABORTED: HEAD mismatch"; exit 9; }
cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
mult() { world=$1; sfx=$2; stamp "multiplier[$world] start"; env HAFISCAL_WORLD=$world HAFISCAL_FIGS_SUFFIX=$sfx $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_$world.log 2>&1; rc=$?; stamp "multiplier[$world] end rc=$rc"; grep -h "ui-encoding\]" $LOG/mult_$world.log | head -1; grep "AD effect)" Tables/Baseline$sfx/Multiplier_candidate.tex 2>/dev/null | head -1; grep "expenditure during" Tables/Baseline$sfx/Multiplier_candidate.tex 2>/dev/null | head -1; grep -c "policy-store\] SAVED" $LOG/mult_$world.log; [ $rc -eq 0 ] || exit 10; }
w6() { world=$1; K=$2; tag=$3; stamp "welfare[$world] seed $K start"; env HAFISCAL_WORLD=$world $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${tag}_seed$K --table-dir Tables/Baseline_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1; rc=$?; stamp "welfare[$world] seed $K end rc=$rc tables=$(ls Tables/Baseline_${tag}_seed$K 2>/dev/null | wc -l) miss-errors=$(grep -c 'MISS at' $LOG/w6_${tag}_seed$K.log)"; grep -h "FAIL rc=" $LOG/w6_${tag}_seed$K.log | head -3; [ $rc -eq 0 ] || echo "   WELFARE FAILED (continuing to next seed)"; }
band() { tag=$1; stamp "band[$tag]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_${tag}_seed0/welfare6_parallel_summary.json Tables/Baseline_${tag}_seed1/welfare6_parallel_summary.json Tables/Baseline_${tag}_seed2/welfare6_parallel_summary.json --out $LOG/welfare6_${tag}_seed_band.tex 2>&1 | tail -12; }
mult default _uiA
for K in 0 1 2; do w6 default $K uiA; done
band uiA
mult as-corrected _ac_legacy
for K in 0 1 2; do w6 as-corrected $K ac_legacy; done
band ac_legacy
echo "P3 BASELINE DELL DONE $(date +%H:%M:%S)"
