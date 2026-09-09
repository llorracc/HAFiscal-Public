#!/bin/bash
# P7 (dell, 2026-08-26): the as-corrected world under the CERTIFIED NUMERICS PACKAGE (the catalog now resolves it:
# calendar + the paper's window policy + stratified shuffle) -- Step 5a (7 states) then Step 5b seeds 0..4 (own AD loops:
# ad_equilibrium_share is off in as-corrected) then the 5-seed band. Pairs with the paper's-engine arm (m5, non-shuffled
# legacy, seeds 0..4) for the certification and the waterfall.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826
echo "HEAD $(git -C $REPO rev-parse --short HEAD) $(date +%H:%M:%S)"; cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_WORLD=as-corrected
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
stamp "multiplier[as-corrected/package] start"; env HAFISCAL_FIGS_SUFFIX=_ac_pkg $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_ac_pkg.log 2>&1; rc=$?
stamp "multiplier[as-corrected/package] end rc=$rc"; grep -h "ui-encoding\]" $LOG/mult_ac_pkg.log | head -1; grep "AD effect)\|expenditure during" Tables/Baseline_ac_pkg/Multiplier_candidate.tex 2>/dev/null; [ $rc -eq 0 ] || exit 10
for K in 0 1 2 3 4; do stamp "welfare[as-corrected/package] seed $K start"; $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_ac_pkg_seed$K --table-dir Tables/Baseline_ac_pkg_seed$K > $LOG/w6_ac_pkg_seed$K.log 2>&1; rc=$?; stamp "welfare[as-corrected/package] seed $K end rc=$rc tables=$(ls Tables/Baseline_ac_pkg_seed$K 2>/dev/null | wc -l) miss-errors=$(grep -c 'MISS at' $LOG/w6_ac_pkg_seed$K.log)"; grep mathcal Tables/Baseline_ac_pkg_seed$K/welfare6_candidate.tex 2>/dev/null; done
stamp "band[ac_pkg]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_ac_pkg_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_ac_pkg_seed_band.tex 2>&1 | tail -12
echo "P7 AC PACKAGE DELL DONE $(date +%H:%M:%S)"
