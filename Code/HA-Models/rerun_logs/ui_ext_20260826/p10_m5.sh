#!/bin/bash
# P10 on ccarroll-m5 (2026-08-26 23:00): queued behind P9 (the ladder half). Worktree ~/coldrun_ps stays at 97306779.
#  (C) the size of "permanent shocks in every employment state" at the model-changes step: the (A) column's economics under
#      the paper's numerics (legacy 4-state encoding, non-shuffled HARK MC, own AD loops) with HAFISCAL_PERM_DURING_UNEMP=off,
#      on the DEFAULT calibration (runtime-only sensitivity; the matched re-estimation runs on ccarroll). 5a -> Tables/
#      Baseline_uiL_permoff; battery seeds 0,1 -> Baseline_uiL_permoff_nshuf_seedK (+ seeds 2..4 on xubuntark) + band.
#  (B) the certified-numerics-only column of the default world: uiA's economics (window policy, calendar encoding, the
#      stratified shuffle) with NO other improvement -- own AD loops, HARK engine, equal-weight panel. Seeds 0..4 + band.
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
LOG=$HOME/ui_ext_20260826
until grep -q "P9 M5 DONE" $HOME/p9_m5.out 2>/dev/null; do sleep 120; done
echo "P9 finished; starting P10 at $(git -C $W rev-parse --short HEAD) $(date +%H:%M:%S)"; cd $FPC
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
w6() { tag=$1; K=$2; shift 2
  stamp "w6[$tag] seed $K start"; env "$@" $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${tag}_seed$K --table-dir Tables/Baseline_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1
  stamp "w6[$tag] seed $K end rc=$? tables=$(ls Tables/Baseline_${tag}_seed$K 2>/dev/null | wc -l | tr -d " ")"; grep mathcal Tables/Baseline_${tag}_seed$K/welfare6_candidate.tex 2>/dev/null | head -3; }
band() { tag=$1; out=$2; shift 2; stamp "band[$tag]"; $PY compute_welfare6_se_table.py --summaries "$@" --out $LOG/$out 2>&1 | tail -11; }
PERMOFF=(HAFISCAL_WORLD=default HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_PERM_DURING_UNEMP=off HAFISCAL_MC_SHUFFLE=0 HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark HAFISCAL_MC_WEIGHTED_TAIL=0)
stamp "5a[uiL_permoff] start"; env "${PERMOFF[@]}" HAFISCAL_FIGS_SUFFIX=_uiL_permoff $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_uiL_permoff.log 2>&1; rc=$?
stamp "5a[uiL_permoff] end rc=$rc"; grep "AD effect)\|expenditure during" Tables/Baseline_uiL_permoff/Multiplier_candidate.tex 2>/dev/null
for K in 0 1; do w6 uiL_permoff_nshuf $K "${PERMOFF[@]}"; done
band uiL_permoff_nshuf welfare6_uiL_permoff_nshuf_seed_band.tex Tables/Baseline_uiL_permoff_nshuf_seed{0,1}/welfare6_parallel_summary.json
PKGONLY=(HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark HAFISCAL_MC_WEIGHTED_TAIL=0)
for K in 0 1 2 3 4; do w6 uiA_nshare $K "${PKGONLY[@]}"; done
band uiA_nshare welfare6_uiA_nshare_S5_seed_band.tex Tables/Baseline_uiA_nshare_seed{0,1,2,3,4}/welfare6_parallel_summary.json
echo "P10 M5 DONE $(date +%H:%M:%S)"
