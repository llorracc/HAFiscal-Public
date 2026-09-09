#!/bin/bash
# P5 part 1 (overlapping the as-corrected battery): pull Improvement B's Baseline run from m5 and regenerate the
# candidate figures from its 5a pickles on the published axes. Idempotent; p5_stage_dell.sh repeats it harmlessly.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python; F=$FPC/Figures
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
stamp "pull B from m5"
for d in Tables/Baseline_uiB Tables/Baseline_uiB_seed0 Tables/Baseline_uiB_seed1 Tables/Baseline_uiB_seed2 Figures/Baseline_uiB; do
  mkdir -p $FPC/$d; ssh ccarroll-m5 "cd ~/coldrun_ps/Code/HA-Models/FromPandemicCode/$d && tar cf - ." | tar xf - -C $FPC/$d; echo "  $d: $(ls $FPC/$d | wc -l) files"; done
scp -q ccarroll-m5:~/ui_ext_20260826/welfare6_uiB_seed_band.tex $LOG/welfare6_uiB_seed_band.tex; scp -q ccarroll-m5:~/p4_history_m5.out $LOG/p4_m5.out; mkdir -p $LOG/m5logs; scp -q "ccarroll-m5:~/ui_ext_20260826/*.log" $LOG/m5logs/ 2>/dev/null
stamp "candidate figures from B (published axes lock)"
rm -rf $F/Baseline_cand_previous_20260825; [ -d $F/Baseline_cand ] && mv $F/Baseline_cand $F/Baseline_cand_previous_20260825; mkdir -p $F/Baseline_cand && cp -p $F/Baseline_uiB/* $F/Baseline_cand/
export PYTHONUNBUFFERED=1 HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=history HAFISCAL_QUIET_BETADISTR=1
rm -f $F/axes_lock_report.json
cd $FPC && $PY - <<'PYEOF' 2>&1 | grep -E "fig-axes|Traceback|Error" | head -20
import os, sys
sys.argv = ["Output_Results.py"]
from Output_Results import Output_Results
here = os.path.dirname(os.path.abspath("Output_Results.py"))
Output_Results(here + "/Figures/Baseline_cand/", here + "/Figures/", "/tmp/claude-1000/-home-shared-github-llorracc-HAFiscal-Latest/f91dfb72-4520-415e-95d4-8c433281596b/scratchpad/or_tables_p5/", Parametrization="Baseline")
PYEOF
echo "Output_Results rc=${PIPESTATUS[0]}"; ls -la $F/Cumulative_multiplier_UI_candidate.pdf $F/recession_UI_relrecession_candidate.pdf 2>/dev/null | awk '{print $6,$7,$8,$9}'
echo "P5A DONE $(date +%H:%M:%S)"
