#!/bin/bash
# P17 (dell, 2026-08-27 03:50): republish the uiA equilibria under the CURRENT keys, then uiA seeds 3,4. P16's seeds passed the
# policy store (REQUIRE=0) but the AD-equilibrium store MISSED: the entries published by the 12:20 uiA 5a carry the five
# UI-policy env vars in their key, which fix_keys_inert_policy_vars.py removed from the whitelist that afternoon; on a miss the
# battery (correctly) refuses to run the weighted-tail panel through its own AD loop. The 5a is the deterministic TM program,
# so the republished equilibria are byte-identical to the 12:20 ones and seeds 3,4 are the same computation as seeds 0-2.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
until grep -q "P16 DELL DONE" $LOG/p16.out 2>/dev/null; do sleep 30; done
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1
export HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
stamp "5a[uiA republish] start"; env HAFISCAL_FIGS_SUFFIX=_uiA_repub $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_uiA_repub.log 2>&1; rc=$?
stamp "5a[uiA republish] end rc=$rc equilibria SAVED=$(grep -c 'ad-equilibrium\] SAVED' $LOG/mult_uiA_repub.log)"; grep "AD effect)" Tables/Baseline_uiA_repub/Multiplier_candidate.tex 2>/dev/null; diff <(grep "Multiplier\|Share" Tables/Baseline_uiA/Multiplier_candidate.tex) <(grep "Multiplier\|Share" Tables/Baseline_uiA_repub/Multiplier_candidate.tex) > /dev/null && echo "   republished multiplier table IDENTICAL to the 12:20 one" || echo "   WARNING: republished multiplier table differs from the 12:20 one"; [ $rc -eq 0 ] || exit 10
for K in 3 4; do stamp "w6[uiA] seed $K start"; $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_uiA_seed$K --table-dir Tables/Baseline_uiA_seed$K > $LOG/w6_uiA_seed$K.log 2>&1; stamp "w6[uiA] seed $K end rc=$? tables=$(ls Tables/Baseline_uiA_seed$K 2>/dev/null | wc -l)"; grep -h "FAIL rc=\|MISS " $LOG/w6_uiA_seed$K.log | head -2; done
stamp "band[uiA S=5]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_uiA_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_uiA_S5_seed_band.tex 2>&1 | tail -11
echo "P17 DELL DONE $(date +%H:%M:%S)"
