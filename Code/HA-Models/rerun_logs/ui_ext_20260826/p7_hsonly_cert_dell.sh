#!/bin/bash
# P7 certification jobs at HS_Only (dell, 2026-08-26; light, runs beside the Baseline 5a):
#  (a) mechanism test for the TM's -0.3 % recessionUI outlay gap (legacy vs calendar): with unemployed pLvl growing at G
#      (HAFISCAL_PLVL_GROWS_DURING_UNEMP=on) the duration-dependence of a state's mean p disappears, so if the gap is the
#      state-level p-weight it must vanish. Default world, 5a only.
#  (b) the text-literal policy (6 extension... 2 extension states: HAFISCAL_UI_EXT_QUARTERS=2, continuation window):
#      5a + one non-shuffled battery seed vs the code-exact 7-state window (existing HS_Only_ui_window / window_nshuf_seed0).
#  (c) as-corrected HS_Only store entries: 5a under the package (world default) and under explicit legacy.
#  (d) the N-ladder: N in {1500, 6000, 24000} x {paper's engine: legacy + MC_SHUFFLE=0; package: world default} x seeds 0..5,
#      as-corrected world (own AD loops). Two batteries at a time.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_DUR_WORKERS=1 HAFISCAL_QUIET_BETADISTR=1
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
m5a() { tag=$1; shift; stamp "5a[$tag] start"; rm -rf Tables/HS_Only_$tag Figures/HS_Only_$tag; env "$@" HAFISCAL_FIGS_SUFFIX=_$tag $PY AggFiscalMAIN_reduced.py --hs-only > $LOG/5a_$tag.log 2>&1; stamp "5a[$tag] end rc=$?"; grep "AD effect)\|expenditure during" Tables/HS_Only_$tag/Multiplier_candidate.tex 2>/dev/null; }
# (a) mechanism
m5a uigrow_legacy HAFISCAL_WORLD=default HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_PLVL_GROWS_DURING_UNEMP=on &
m5a uigrow_window HAFISCAL_WORLD=default HAFISCAL_UI_STATE_ENCODING=calendar HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_PLVL_GROWS_DURING_UNEMP=on &
# (b) text-literal (2 extension states)
m5a uitext6 HAFISCAL_WORLD=default HAFISCAL_UI_STATE_ENCODING=calendar HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_UI_EXT_QUARTERS=2 &
# (c) as-corrected store entries
m5a ac_pkg HAFISCAL_WORLD=as-corrected &
wait
m5a ac_legacy HAFISCAL_WORLD=as-corrected HAFISCAL_UI_STATE_ENCODING=legacy
stamp "5a batch done"
w6() { tag=$1; K=$2; N=$3; shift 3; stamp "w6[$tag N=$N] seed $K start"; env "$@" $PY run_welfare6_parallel.py --parametrization HS_Only --seed-offset $K --agent-count-total $N --max-cpu-slots 3 --out-dir welfare6_scenario_results_HS_Only_${tag}_N${N}_seed$K --table-dir Tables/HS_Only_${tag}_N${N}_seed$K > $LOG/w6_${tag}_N${N}_seed$K.log 2>&1; stamp "w6[$tag N=$N] seed $K end rc=$? miss=$(grep -c 'MISS at' $LOG/w6_${tag}_N${N}_seed$K.log)"; }
# (b) text-literal welfare, non-shuffled seed 0 (pairs with window_nshuf_seed0)
w6 uitext6_nshuf 0 1500 HAFISCAL_WORLD=default HAFISCAL_UI_STATE_ENCODING=calendar HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_UI_EXT_QUARTERS=2 HAFISCAL_MC_SHUFFLE=0 HAFISCAL_AD_EQUILIBRIUM_SHARE=0
# (d) N-ladder
for N in 1500 6000 24000; do for K in 0 2 4; do
  w6 ac_paper $K $N HAFISCAL_WORLD=as-corrected HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_MC_SHUFFLE=0 &
  w6 ac_pkg $K $N HAFISCAL_WORLD=as-corrected &
  wait
  w6 ac_paper $((K+1)) $N HAFISCAL_WORLD=as-corrected HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_MC_SHUFFLE=0 &
  w6 ac_pkg $((K+1)) $N HAFISCAL_WORLD=as-corrected &
  wait
done; done
echo "P7 HSONLY CERT DONE $(date +%H:%M:%S)"
