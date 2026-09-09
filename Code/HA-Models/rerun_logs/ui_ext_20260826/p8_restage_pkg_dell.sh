#!/bin/bash
# P8 (dell, 2026-08-26): after the as-corrected PACKAGE arm (P7) lands -- restage BUGFIXED onto it (owner ruling: the
# certified numerics package is always used in as-corrected), keep the paper's-engine arm as the reference/waterfall
# column, regenerate UPDATES.md + the annotated PDF (figures unchanged: IMPROVED is still B), archive, waterfall.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; HA=$REPO/Code/HA-Models; T=$FPC/Tables
WF=$REPO/conclusions_private/artifacts_20260823_wfix; A=$REPO/conclusions_private/artifacts_20260826_uiAB; LOG=$HA/rerun_logs/ui_ext_20260826
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
cd $REPO
for d in Baseline_ac_pkg Baseline_ac_pkg_seed0; do [ -s $T/$d/Multiplier_candidate.tex ] || [ -s $T/$d/welfare6_candidate.tex ] || { echo "MISSING $T/$d"; exit 2; }; done   # seeds 1-4 + band copied when present (rerun the copy lines after the battery)
stamp "BUGFIXED <- as-corrected under the certified package (5a + welfare seed 0; S=5 band)"
cp -p $WF/Multiplier_wfix.tex $A/Multiplier_wfix_previous_ac_legacy_20260826.tex; cp -p $WF/welfare6_wfix.tex $A/welfare6_wfix_previous_ac_legacy_nshuf_20260826.tex
cp -p $T/Baseline_ac_pkg/Multiplier_candidate.tex $WF/Multiplier_wfix.tex
cp -p $T/Baseline_ac_pkg_seed0/welfare6_candidate.tex $WF/welfare6_wfix.tex
[ -s $LOG/welfare6_ac_pkg_seed_band.tex ] && cp -p $LOG/welfare6_ac_pkg_seed_band.tex $WF/welfare6_seed_band.tex || echo "  (package band not yet available)"
for K in 0 1 2 3 4; do [ -s $T/Baseline_ac_pkg_seed$K/welfare6_parallel_summary.json ] && cp -p $T/Baseline_ac_pkg_seed$K/welfare6_parallel_summary.json $WF/welfare6_parallel_summary_ac_pkg_seed$K.json; done
cp -p $T/Baseline_ac_pkg_seed0/RUN_*.prov.json $T/Baseline_ac_pkg/RUN_*.prov.json $WF/ 2>/dev/null
stamp "archive"
mkdir -p $A/as-corrected-package; cp -p $T/Baseline_ac_pkg/Multiplier_candidate.tex $A/as-corrected-package/Multiplier_5a.tex; cp -p $T/Baseline_ac_pkg/RUN_*.prov.json $A/as-corrected-package/ 2>/dev/null
for K in 0 1 2 3 4; do [ -d $T/Baseline_ac_pkg_seed$K ] && { mkdir -p $A/as-corrected-package/seed$K; cp -p $T/Baseline_ac_pkg_seed$K/*.tex $T/Baseline_ac_pkg_seed$K/*.json $A/as-corrected-package/seed$K/; }; done
[ -s $LOG/welfare6_ac_pkg_seed_band.tex ] && cp -p $LOG/welfare6_ac_pkg_seed_band.tex $A/as-corrected-package/; cp -p $LOG/p7ac.out $LOG/p7cert.out $LOG/*.sh $LOG/*.py $A/ 2>/dev/null
stamp "waterfall"; $REPO/.venv/bin/python $HA/waterfall_table.py --out $A/waterfall_20260826.md | head -3
stamp "UPDATES.md + annotated PDF"
python3 $HA/updates_report.py 2>/dev/null | tail -1
pdflatex -interaction=nonstopmode -halt-on-error UPDATES-figures.tex > /dev/null && pdflatex -interaction=nonstopmode -halt-on-error UPDATES-figures.tex > /dev/null && echo "figures doc: $(pdfinfo UPDATES-figures.pdf | grep Pages)"
printf '%s\n' '\annotatedtablestrue' > @local/use-annotated-tables.ltx
timeout 1500 latexmk -g -jobname=HAFiscal-annotated HAFiscal.tex > $LOG/annotated-build-p8.log 2>&1; echo "latexmk rc=$?" >> $LOG/annotated-build-p8.log
rm -f @local/use-annotated-tables.ltx
tail -1 $LOG/annotated-build-p8.log; pdfinfo HAFiscal-annotated.pdf | grep Pages; echo "unresolved refs: $(pdftotext HAFiscal-annotated.pdf - 2>/dev/null | grep -c '??')"
cp -p HAFiscal-annotated.pdf $A/HAFiscal-annotated-20260826-uiAB.pdf; cp -p UPDATES-figures.pdf $A/; cp -p UPDATES.md $A/UPDATES-20260826-uiAB.md
echo "P8 RESTAGE DONE $(date +%H:%M:%S)"
