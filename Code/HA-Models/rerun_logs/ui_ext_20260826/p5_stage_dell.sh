#!/bin/bash
# P5 of plans/20260826-0800h_ui-extension-calendar-window-encoding_plan.md (dell, 2026-08-26): restage the candidate set.
#   IMPROVED  (default world = Improvement B 'history' on A)  <- Tables/Baseline_uiB (5a), Tables/Baseline_uiB_seed{0,1,2} (5b)
#   BUGFIXED  (as-corrected = the paper's encoding + policy)  <- Tables/Baseline_ac_legacy (5a), Tables/Baseline_ac_legacy_seed{0,1,2}
#   A reference (default world under the paper's policy)      <- Tables/Baseline_uiA*, archived only (the G2 gate, not staged)
# Mirrors rerun_logs/rebattery_20260824/harvest_rebattery.sh (stage) + the 08-26 figure regeneration (published axes lock)
# + post_regen (UPDATES.md, UPDATES-figures.pdf, annotated PDF). No promotion (owner-gated).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; HA=$REPO/Code/HA-Models
PY=$REPO/.venv/bin/python; T=$FPC/Tables; F=$FPC/Figures
WF=$REPO/conclusions_private/artifacts_20260823_wfix; A=$REPO/conclusions_private/artifacts_20260826_uiAB
LOG=$HA/rerun_logs/ui_ext_20260826
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
cd $REPO
stamp "pull Improvement B's Baseline run from m5 (Tables + Figures/Baseline_uiB; one-machine S=3 on the mac)"
for d in Tables/Baseline_uiB Tables/Baseline_uiB_seed0 Tables/Baseline_uiB_seed1 Tables/Baseline_uiB_seed2 Figures/Baseline_uiB Tables/Baseline_ac_legacy_nshuf_seed0 Tables/Baseline_ac_legacy_nshuf_seed1 Tables/Baseline_ac_legacy_nshuf_seed2; do
  if ssh ccarroll-m5 "test -d ~/coldrun_ps/Code/HA-Models/FromPandemicCode/$d"; then mkdir -p $FPC/$d; ssh ccarroll-m5 "cd ~/coldrun_ps/Code/HA-Models/FromPandemicCode/$d && tar cf - ." | tar xf - -C $FPC/$d; echo "  $d: $(ls $FPC/$d | wc -l) files"; else echo "  $d: not on m5 (yet)"; fi; done
scp -q ccarroll-m5:~/ui_ext_20260826/welfare6_uiB_seed_band.tex $LOG/welfare6_uiB_seed_band.tex; scp -q ccarroll-m5:~/ui_ext_20260826/welfare6_ac_legacy_nshuf_seed_band.tex $LOG/welfare6_ac_legacy_nshuf_seed_band.tex; scp -q ccarroll-m5:~/p3b_ac_nshuf_m5.out $LOG/p3b_m5.out; scp -q "ccarroll-m5:~/ui_ext_20260826/*.log" $LOG/m5_ 2>/dev/null; scp -q ccarroll-m5:~/p4_history_m5.out $LOG/p4_m5.out
for d in Baseline_uiB Baseline_uiB_seed0 Baseline_uiB_seed1 Baseline_uiB_seed2 Baseline_ac_legacy Baseline_ac_legacy_nshuf_seed0 Baseline_ac_legacy_seed0 Baseline_uiA Baseline_uiA_seed0; do   # nshuf seeds 1,2 optional (band copied when present)
  [ -s $T/$d/Multiplier_candidate.tex ] || [ -s $T/$d/welfare6_candidate.tex ] || { echo "MISSING $T/$d"; exit 2; }; done
mkdir -p $A/default $A/as-corrected $A/A-window
stamp "archive the previous candidates"
cp -p $T/CRRA2/Multiplier_candidate.tex $A/Multiplier_candidate_previous_20260825.tex
cp -p $T/CRRA2/welfare6_candidate.tex $A/welfare6_candidate_previous_20260825.tex
cp -p $WF/Multiplier_wfix.tex $A/Multiplier_wfix_previous_20260825.tex; cp -p $WF/welfare6_wfix.tex $A/welfare6_wfix_previous_20260825.tex
stamp "IMPROVED <- default world under B (seed 0 welfare; 5a multiplier)"
cp -p $T/Baseline_uiB/Multiplier_candidate.tex $T/CRRA2/Multiplier_candidate.tex
cp -p $T/Baseline_uiB_seed0/welfare6_candidate.tex $T/CRRA2/welfare6_candidate.tex
cp -p $T/Baseline_uiB_seed0/welfare4_candidate.tex $T/CRRA2/welfare4_candidate.tex 2>/dev/null
stamp "BUGFIXED <- as-corrected world under legacy: 5a from dell; welfare from the NON-shuffled battery (m5; the paper's engine --"
stamp "   the stratified shuffle's coupling breaks under the freeze: ui_norec 2.28 / 5.90 on dell's stratified seeds 0 / 1)"
cp -p $T/Baseline_ac_legacy/Multiplier_candidate.tex $WF/Multiplier_wfix.tex
cp -p $T/Baseline_ac_legacy_nshuf_seed0/welfare6_candidate.tex $WF/welfare6_wfix.tex
[ -s $LOG/welfare6_ac_legacy_nshuf_seed_band.tex ] && cp -p $LOG/welfare6_ac_legacy_nshuf_seed_band.tex $WF/welfare6_seed_band.tex || echo "  (nshuf band not yet available; welfare6_seed_band.tex left as the previous vintage -- rerun the copy when m5 finishes)"
for K in 0 1 2; do [ -s $T/Baseline_ac_legacy_nshuf_seed$K/welfare6_parallel_summary.json ] && cp -p $T/Baseline_ac_legacy_nshuf_seed$K/welfare6_parallel_summary.json $WF/welfare6_parallel_summary_ac_legacy_nshuf_seed$K.json; done
cp -p $T/Baseline_ac_legacy_nshuf_seed0/RUN_*.prov.json $WF/ 2>/dev/null
cp -p $T/Baseline_ac_legacy/RUN_*.prov.json $WF/ 2>/dev/null
stamp "archive set"
for W in uiB:default ac_legacy_nshuf:as-corrected ac_legacy:as-corrected-stratified-broken uiA:A-window; do tag=${W%%:*}; dst=${W##*:}; mkdir -p $A/$dst
  cp -p $T/Baseline_$tag/Multiplier_candidate.tex $A/$dst/Multiplier_5a.tex 2>/dev/null; cp -p $T/Baseline_$tag/RUN_*.prov.json $A/$dst/ 2>/dev/null
  for K in 0 1 2; do [ -d $T/Baseline_${tag}_seed$K ] && { mkdir -p $A/$dst/seed$K; cp -p $T/Baseline_${tag}_seed$K/*.tex $T/Baseline_${tag}_seed$K/*.json $A/$dst/seed$K/ 2>/dev/null; }; done
  [ -s $LOG/welfare6_${tag}_seed_band.tex ] && cp -p $LOG/welfare6_${tag}_seed_band.tex $A/$dst/; done
cp -p $LOG/*.sh $LOG/*.out $A/ 2>/dev/null
stamp "candidate figures from the B run (published axes lock)"
rm -rf $F/Baseline_cand_previous_20260825 && mv $F/Baseline_cand $F/Baseline_cand_previous_20260825 && mkdir -p $F/Baseline_cand && cp -p $F/Baseline_uiB/* $F/Baseline_cand/
export PYTHONUNBUFFERED=1 HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=history
rm -f $F/axes_lock_report.json
cd $FPC && $PY - <<'PYEOF' 2>&1 | grep -E "fig-axes|Traceback|Error" | head -20
import os, sys
sys.argv = ["Output_Results.py"]
from Output_Results import Output_Results
here = os.path.dirname(os.path.abspath("Output_Results.py"))
Output_Results(here + "/Figures/Baseline_cand/", here + "/Figures/", "/tmp/claude-1000/-home-shared-github-llorracc-HAFiscal-Latest/f91dfb72-4520-415e-95d4-8c433281596b/scratchpad/or_tables_p5/", Parametrization="Baseline")
PYEOF
echo "Output_Results rc=${PIPESTATUS[0]}"; cd $REPO
stamp "UPDATES.md + UPDATES-figures.pdf + annotated PDF"
python3 Code/HA-Models/updates_report.py | tail -1
pdflatex -interaction=nonstopmode -halt-on-error UPDATES-figures.tex > /dev/null && pdflatex -interaction=nonstopmode -halt-on-error UPDATES-figures.tex > /dev/null && echo "figures doc: $(pdfinfo UPDATES-figures.pdf | grep Pages)"
printf '%s\n' '\annotatedtablestrue' > @local/use-annotated-tables.ltx
timeout 1500 latexmk -g -jobname=HAFiscal-annotated HAFiscal.tex > $LOG/annotated-build.log 2>&1; echo "latexmk rc=$?" >> $LOG/annotated-build.log
rm -f @local/use-annotated-tables.ltx
tail -1 $LOG/annotated-build.log; pdfinfo HAFiscal-annotated.pdf | grep Pages
cp -p HAFiscal-annotated.pdf $A/HAFiscal-annotated-20260826-uiAB.pdf; cp -p UPDATES-figures.pdf $A/; cp -p UPDATES.md $A/UPDATES-20260826-uiAB.md
echo "P5 STAGE DONE $(date +%H:%M:%S)"
