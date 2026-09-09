# P29 (2026-08-27 20:50; owner ruling 1: RE-ISSUE the appendix's 𝒞 welfare tables under the CRRA-consistent normalizer,
# BUG-082). The robustness configs re-run on the chain's final configuration -- the default world with the paper's UI
# window (uiA: every correction, permanent shocks in unemployment, sharing + weighted panel, hark engine, calendar chain +
# stratified shuffle) -- 5a (publishes the equilibria the battery consumes) + three welfare seeds each. Step-2 calibrations
# are NOT re-run: the installed ones (2026-08-20/21) are the same vintage as the Baseline calibration of record
# (DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt, 2026-08-20 18:10). CRRA1 stays parked (all College atoms violate the GIC cap;
# owner decision pending: drop the row or report the constrained fit). Previous Tables/<NAME> renamed *_pre_reissue_20260827.
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
cfg() { NAME=$1
  [ -d Tables/$NAME ] && [ ! -d Tables/${NAME}_pre_reissue_20260827 ] && mv Tables/$NAME Tables/${NAME}_pre_reissue_20260827
  T0=$(date +%s); stamp "5a[$NAME] start"; $PY AggFiscalMAIN_reduced.py --parametrization $NAME > $LOG/mult_$NAME.log 2>&1; rc=$?
  stamp "5a[$NAME] end rc=$rc wall=$(( ($(date +%s)-T0)/60 ))min"; grep "AD effect)\|expenditure during" Tables/$NAME/Multiplier_candidate.tex 2>/dev/null; [ $rc -eq 0 ] || return
  for K in 0 1 2; do T1=$(date +%s); stamp "w6[$NAME] seed $K start"
    $PY run_welfare6_parallel.py --parametrization $NAME --seed-offset $K --out-dir welfare6_scenario_results_${NAME}_seed$K --table-dir Tables/${NAME}_seed$K > $LOG/w6_${NAME}_seed$K.log 2>&1; rc=$?
    stamp "w6[$NAME] seed $K end rc=$rc wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/${NAME}_seed$K/*.tex 2>/dev/null | wc -l)"; done
  stamp "band[$NAME]"; $PY compute_welfare6_se_table.py --summaries Tables/${NAME}_seed{0,1,2}/welfare6_parallel_summary.json --out $LOG/welfare6_${NAME}_S3_seed_band.tex 2>&1 | tail -n 4; }
