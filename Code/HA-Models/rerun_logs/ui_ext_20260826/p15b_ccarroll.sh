#!/bin/bash
# P15b on ccarroll (2026-08-27 03:40): P15 again with the MC engine's pLvl-drift gate downgraded to a WARNING. P15 hard-failed at
# 1x (agent_3: Lorenz p60 -3.3 pp, p80 -6.4 pp vs the +-3 pp threshold): the paper's engine at the paper's panel size under-
# disperses the cross-section -- the property we are measuring, so it is logged, not gated (HAFISCAL_DRIFT_HARD_FAIL=0).
# As-corrected world, HAFISCAL_MULTIPLIER_ENGINE=mc, 5a only -> Tables/Baseline_ac_mcmult; compare with Baseline_ac_pkg (TM).
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
LOG=$HOME/ui_ext_20260826; cd $FPC
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=as-corrected HAFISCAL_MULTIPLIER_ENGINE=mc HAFISCAL_DRIFT_HARD_FAIL=0
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
stamp "5a[ac_mcmult] start"; env HAFISCAL_FIGS_SUFFIX=_ac_mcmult $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_ac_mcmult.log 2>&1; rc=$?
stamp "5a[ac_mcmult] end rc=$rc"; grep -h "DRIFT\|drift=" $LOG/mult_ac_mcmult.log | head -6; grep "AD effect)\|expenditure during" Tables/Baseline_ac_mcmult/Multiplier_candidate.tex 2>/dev/null
echo "P15B CCARROLL DONE $(date +%H:%M:%S)"
