#!/bin/bash
# P11 on ccarroll (2026-08-27 00:00): BUG-095 materiality. The CORRECTED TM-ergodic Step-2 estimator (unemployed income
# process through the SST) run (a) in the default world (perm shocks ON in unemployment -- the calibration the default
# world SHOULD have) and (b) with HAFISCAL_PERM_DURING_UNEMP=off (control: must reproduce the committed betas, which BUG-095
# showed are perm-off estimates). Three cohorts concurrently per run; outputs to scratch dirs (HAFISCAL_RESULTS_OUT_DIR);
# the tracked calibration is never touched. Worktree ~/coldrun_ps detached at 421c6634.
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
LOG=$HOME/ui_ext_20260826; cd $FPC
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_WORLD=default
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
run() { tag=$1; shift; S2=$LOG/$tag; mkdir -p $S2; stamp "S2[$tag] start"
  for E in 0 1 2; do env "$@" HAFISCAL_EDTYPES=$E HAFISCAL_RESULTS_OUT_DIR=$S2 $PY estim_phase2_tm_a.py > $S2/s2_edType$E.log 2>&1 & done; wait
  grep -h "step2-unemp-incshk" $S2/s2_edType2.log | head -1
  cat $S2/DiscFacEstim_CRRA_2.0_R_1.01_edType{0,1,2}_TM_a_ESC.txt 2>/dev/null || echo "S2[$tag] FAILED: per-cohort files missing"
  stamp "S2[$tag] end"; }
run s2_permon_fixed
run s2_permoff_fixed HAFISCAL_PERM_DURING_UNEMP=off
echo "committed default-world betas for comparison:"; head -3 $W/Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt
echo "P11 CCARROLL DONE $(date +%H:%M:%S)"
