#!/bin/bash
# P9 (dell, 2026-08-26 evening; owner: "construct all"): (1) the IMPROVEMENTS-ONLY waterfall column -- the as-corrected
# world with every runtime IMPROVEMENT opted in by explicit env (hybrid welfare engine, AD-equilibrium sharing, weighted-tail
# panel; the certified package is already on; estimation-only improvements are inert here) and the MODIFICATIONS at the
# paper's values (age cap 200, no perm shocks in unemployment, the paper's UI window); 5a + S=5.
# (2) the BUG-FIX ATTRIBUTION LADDER, dell's half: as-corrected (the BUGFIXED engine) with ONE bug fix at its paper (buggy)
# value per arm: welfare6_fix_dur_avg=off | pf_decay_extrap=0 | pf_decay_q=slope. 5a + seeds 0,1 each. (m5 runs the other half.)
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826; cd $FPC
echo "HEAD $(git -C $REPO rev-parse --short HEAD) $(date +%H:%M:%S)"
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_WORLD=as-corrected
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
arm() { tag=$1; nseeds=$2; shift 2   # remaining args: env overrides
  stamp "5a[$tag] start"; env "$@" HAFISCAL_FIGS_SUFFIX=_$tag $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_$tag.log 2>&1; rc=$?
  stamp "5a[$tag] end rc=$rc"; grep "AD effect)\|expenditure during" Tables/Baseline_$tag/Multiplier_candidate.tex 2>/dev/null; [ $rc -eq 0 ] || return
  K=0; while [ $K -lt $nseeds ]; do stamp "w6[$tag] seed $K start"; env "$@" $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${tag}_seed$K --table-dir Tables/Baseline_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1; stamp "w6[$tag] seed $K end rc=$? tables=$(ls Tables/Baseline_${tag}_seed$K 2>/dev/null | wc -l) miss=$(grep -c 'MISS at' $LOG/w6_${tag}_seed$K.log)"; grep mathcal Tables/Baseline_${tag}_seed$K/welfare6_candidate.tex 2>/dev/null | head -3; K=$((K+1)); done; }
arm ac_impr 5 HAFISCAL_WELFARE_ENGINE=hybrid HAFISCAL_AD_EQUILIBRIUM_SHARE=1
stamp "band[ac_impr]"; $PY compute_welfare6_se_table.py --summaries Tables/Baseline_ac_impr_seed{0,1,2,3,4}/welfare6_parallel_summary.json --out $LOG/welfare6_ac_impr_seed_band.tex 2>&1 | tail -11
arm ac_nofix_welfare6dur 2 HAFISCAL_WELFARE6_FIX_DUR_AVG=off
arm ac_nofix_pfdecay 2 HAFISCAL_PF_DECAY_EXTRAP=0
arm ac_nofix_pfq 2 HAFISCAL_PF_DECAY_Q=slope
echo "P9 DELL DONE $(date +%H:%M:%S)"
