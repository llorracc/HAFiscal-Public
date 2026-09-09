#!/bin/bash
# P10 on ccarroll (2026-08-26 23:15): the MATCHED perm-shock arm. (1) Re-estimate the discount factors (Step 2, TM-ergodic
# engine, the three cohorts concurrently) under the default world's economics with HAFISCAL_PERM_DURING_UNEMP=off, outputs
# redirected to a scratch dir (HAFISCAL_RESULTS_OUT_DIR -- the tracked Results/ are never touched; splurge stays the shared
# value, as in both worlds). (2) The (A)-column engine -- legacy 4-state encoding, non-shuffled HARK MC, own AD loops -- on THAT
# calibration (HAFISCAL_DISCFAC_FILE): 5a -> Tables/Baseline_uiL_permoff_matched; battery seeds 0,1 -> ..._nshuf_seedK + band.
# Compare with m5's runtime-only arm (uiL_permoff) to see whether the re-estimation matters. Worktree ~/coldrun_ps (detached
# at dell's 5633bd43).
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
LOG=$HOME/ui_ext_20260826; S2=$LOG/s2_permoff; mkdir -p $S2; cd $FPC
echo "worktree at $(git -C $W rev-parse --short HEAD) $(date +%H:%M:%S)"
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_WORLD=default HAFISCAL_PERM_DURING_UNEMP=off
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
w6() { tag=$1; K=$2; shift 2
  stamp "w6[$tag] seed $K start"; env "$@" $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${tag}_seed$K --table-dir Tables/Baseline_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1
  stamp "w6[$tag] seed $K end rc=$? tables=$(ls Tables/Baseline_${tag}_seed$K 2>/dev/null | wc -l | tr -d " ")"; grep mathcal Tables/Baseline_${tag}_seed$K/welfare6_candidate.tex 2>/dev/null | head -3; }
band() { tag=$1; out=$2; shift 2; stamp "band[$tag]"; $PY compute_welfare6_se_table.py --summaries "$@" --out $LOG/$out 2>&1 | tail -11; }
stamp "S2[permoff] start (3 cohorts concurrently)"
for E in 0 1 2; do env HAFISCAL_EDTYPES=$E HAFISCAL_RESULTS_OUT_DIR=$S2 $PY estim_phase2_tm_a.py > $S2/s2_edType$E.log 2>&1 & done; wait
for E in 0 1 2; do echo "   edType$E last line: $(tail -1 $S2/s2_edType$E.log | cut -c1-120)"; done
CAL=$S2/DiscFacEstim_CRRA_2.0_R_1.01_TM_a_ESC_permoff.txt
cat $S2/DiscFacEstim_CRRA_2.0_R_1.01_edType0_TM_a_ESC.txt $S2/DiscFacEstim_CRRA_2.0_R_1.01_edType1_TM_a_ESC.txt $S2/DiscFacEstim_CRRA_2.0_R_1.01_edType2_TM_a_ESC.txt > $CAL || { echo "S2 FAILED: per-cohort files missing"; exit 10; }
printf "\nParameters: R = 1.01, CRRA = 2.0, IncUnemp = 0.7, IncUnempNoBenefits = 0.5, Splurge = shared; matched re-estimation under HAFISCAL_PERM_DURING_UNEMP=off, default world, %s\n" "$(date +%F)" >> $CAL
stamp "S2[permoff] end"; cat $CAL; echo "   default-world betas for comparison:"; head -3 $W/Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt
export HAFISCAL_DISCFAC_FILE=$CAL
ARM=(HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_MC_SHUFFLE=0 HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark HAFISCAL_MC_WEIGHTED_TAIL=0)
stamp "5a[uiL_permoff_matched] start"; env "${ARM[@]}" HAFISCAL_FIGS_SUFFIX=_uiL_permoff_matched $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_uiL_permoff_matched.log 2>&1; rc=$?
stamp "5a[uiL_permoff_matched] end rc=$rc"; grep "AD effect)\|expenditure during" Tables/Baseline_uiL_permoff_matched/Multiplier_candidate.tex 2>/dev/null
for K in 0 1; do w6 uiL_permoff_matched_nshuf $K "${ARM[@]}"; done
band uiL_permoff_matched_nshuf welfare6_uiL_permoff_matched_nshuf_seed_band.tex Tables/Baseline_uiL_permoff_matched_nshuf_seed{0,1}/welfare6_parallel_summary.json
echo "P10 CCARROLL DONE $(date +%H:%M:%S)"
