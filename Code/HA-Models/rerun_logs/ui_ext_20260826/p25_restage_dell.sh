#!/bin/bash
# P25 (dell, 2026-08-27; owner ruling 16:40: t_age_cap is a BUG_FIX -> the as-corrected world is UNCAPPED): re-stage the
# BUGFIXED artifacts (conclusions_private/artifacts_20260823_wfix/, read by updates_report.py via wfix_map.tsv) onto the uncapped
# corrected world = the chain's corrections column: multipliers from Baseline_uiL_permoff (5a: default economics with the
# shocks frozen, paper's UI window), welfare from Baseline_nocap_pkg (certified own-loop battery, S=5), calibration tables from
# the uncapped estimate (now the as-corrected calibration). The capped restage of 2026-08-26 is kept as *_previous_capped_*.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; HA=$REPO/Code/HA-Models; FPC=$HA/FromPandemicCode; T=$FPC/Tables; PY=$REPO/.venv/bin/python
WF=$REPO/conclusions_private/artifacts_20260823_wfix; A=$REPO/conclusions_private/artifacts_20260826_uiAB; LOG=$HA/rerun_logs/ui_ext_20260826
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
cd $REPO
for K in 0 1 2 3 4; do [ -s $T/Baseline_nocap_pkg_seed$K/welfare6_parallel_summary.json ] || { echo "MISSING nocap seed $K"; exit 2; }; done
[ -s $T/Baseline_uiL_permoff/Multiplier_candidate.tex ] || { echo "MISSING uiL_permoff 5a"; exit 2; }
stamp "band[nocap_pkg S=5]"; $PY $FPC/compute_welfare6_se_table.py --summaries $T/Baseline_nocap_pkg_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_nocap_pkg_S5_seed_band.tex 2>&1 | tail -11
stamp "BUGFIXED <- uncapped corrected world"
cp -p $WF/Multiplier_wfix.tex $A/Multiplier_wfix_previous_capped_20260827.tex; cp -p $WF/welfare6_wfix.tex $A/welfare6_wfix_previous_capped_20260827.tex
cp -p $WF/estimBetas_wfix.tex $A/estimBetas_wfix_previous_capped_20260827.tex; cp -p $WF/nonTargetedMoments_wfix.tex $A/nonTargetedMoments_wfix_previous_capped_20260827.tex
cp -p $T/Baseline_uiL_permoff/Multiplier_candidate.tex $WF/Multiplier_wfix.tex
cp -p $T/Baseline_nocap_pkg_seed0/welfare6_candidate.tex $WF/welfare6_wfix.tex
cp -p $LOG/welfare6_nocap_pkg_S5_seed_band.tex $WF/welfare6_seed_band.tex
for K in 0 1 2 3 4; do cp -p $T/Baseline_nocap_pkg_seed$K/welfare6_parallel_summary.json $WF/welfare6_parallel_summary_seed$K.json; done
cp -p $T/CRRA2/estimBetas_candidate.ltx $WF/estimBetas_wfix.tex; cp -p $T/CRRA2/nonTargetedMoments_candidate.ltx $WF/nonTargetedMoments_wfix.tex
cp -p $T/Baseline_uiL_permoff/RUN_*.prov.json $T/Baseline_nocap_pkg_seed0/RUN_*.prov.json $WF/ 2>/dev/null
cp -p $LOG/welfare6_nocap_pkg_S5_seed_band.tex $A/
stamp "UPDATES.md"; $PY $HA/updates_report.py 2>/dev/null | tail -1
stamp "waterfall + breakdown"; $PY $HA/waterfall_table.py --order original-code --out $A/waterfall_original-code_20260827.md --tex $A/waterfall_original-code_appendix_20260827.tex > /dev/null; $PY $HA/corrections_breakdown_table.py --out $A/corrections_breakdown_20260827.md > /dev/null
echo "P25 RESTAGE DONE $(date +%H:%M:%S)"
