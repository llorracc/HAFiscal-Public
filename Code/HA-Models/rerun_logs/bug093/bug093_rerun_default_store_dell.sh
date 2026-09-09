#!/bin/bash
# 5a default world under the BUG-093 construction (doob default), SHARE=1, in the DEFAULT store: replaces the stale
# pre-fix equilibria of 06:30 (the Q-construction is now a producer convention -> REPLACING). Queued behind the
# as-corrected job (owner 2026-08-25 18:35). Tables/Baseline_default_doob.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/bug093/rerun_default_doob; mkdir -p $LOG; cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_WORLD=default HAFISCAL_AD_EQUILIBRIUM_SHARE=1 JAX_PLATFORMS=cpu
while systemctl --user is-active bug093-rerun-ac >/dev/null 2>&1; do sleep 120; done
echo "main checkout at $(git -C $REPO rev-parse --short HEAD) world=default store=DEFAULT q_method=default(doob) $(date +%H:%M:%S)"
echo "=== multiplier[default, SHARE=1, doob, default store] start $(date +%H:%M:%S)"; env HAFISCAL_FIGS_SUFFIX=_default_doob $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_default_doob.log 2>&1; rc=$?; echo "=== multiplier end rc=$rc $(date +%H:%M:%S)"
grep "Multiplier" Tables/Baseline_default_doob/Multiplier_candidate.tex 2>/dev/null | cut -c1-110
echo "   policy hits=$(grep -c 'policy-store\] HIT' $LOG/mult_default_doob.log) saved=$(grep -c 'policy-store\] SAVED' $LOG/mult_default_doob.log); equilibria: $(grep -ho 'ad-equilibrium\] \(SAVED\|KEPT\|REPLACING\)' $LOG/mult_default_doob.log | sort | uniq -c | tr '\n' ' ')"
grep -h "prescribed AD path" $LOG/mult_default_doob.log | head -4 | cut -c1-140
echo "RERUN-default-store DONE $(date +%H:%M:%S)"
