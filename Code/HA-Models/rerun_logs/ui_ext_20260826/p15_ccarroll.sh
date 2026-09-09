#!/bin/bash
# P15 on ccarroll (2026-08-27 03:35): the PAPER'S MULTIPLIER ENGINE on the corrected model. The attribution ladder showed the
# toggleable published-path defects explain < 1 % of the published -> corrected multiplier move (+3.5 % check, +6.5 % tax
# cut); the rest must be the METHOD (exact TM engine vs the paper's MC engine) and the re-estimated calibration. Direct
# measurement: as-corrected world, HAFISCAL_MULTIPLIER_ENGINE=mc (the reliable stratified-MC engine; valid in the capped
# world -- Test C2 passed the drift gate there), 5a only -> Tables/Baseline_ac_mcmult. Compare with Tables/Baseline_ac_pkg
# (TM engine, same world): the difference IS the engine. Worktree ~/coldrun_ps at 421c6634.
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
LOG=$HOME/ui_ext_20260826; cd $FPC
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=as-corrected HAFISCAL_MULTIPLIER_ENGINE=mc
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
stamp "5a[ac_mcmult] start"; env HAFISCAL_FIGS_SUFFIX=_ac_mcmult $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_ac_mcmult.log 2>&1; rc=$?
stamp "5a[ac_mcmult] end rc=$rc"; grep -h "engine\]\|drift" $LOG/mult_ac_mcmult.log | head -3; grep "AD effect)\|expenditure during" Tables/Baseline_ac_mcmult/Multiplier_candidate.tex 2>/dev/null
echo "P15 CCARROLL DONE $(date +%H:%M:%S)"
