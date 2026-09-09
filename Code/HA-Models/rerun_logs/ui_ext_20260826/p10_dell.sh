#!/bin/bash
# P10 (dell, 2026-08-26 23:00; owner: "queue them behind P9"): the method-first waterfall's missing column + the S=5 top-up.
#  (A) "+model changes, paper's numerics" column: DEFAULT-world economics (no age wall, permanent shocks in every employment
#      state, the matched default calibration, the paper's UI window) under the PAPER'S numerics -- legacy 4-state encoding,
#      non-shuffled HARK MC, own AD loops (no equilibrium sharing, equal-weight panel). Its 5a is Tables/Baseline_uiL (the
#      15:51 legacy twin; the simulation path is unchanged since 8812c3af under explicit env). Battery seeds 0..4 -> band.
#  (B) uiA seeds 3,4 (default world, paper's window policy, sharing ON as in seeds 0-2; the policy is now explicit because the
#      catalog canonical flipped to 'history' at P4 -- setdefault vs explicit is the same value) -> S=5 band.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/ui_ext_20260826
until grep -q "P9 DELL DONE" $LOG/p9.out 2>/dev/null; do sleep 120; done
echo "P9 finished; starting P10 at HEAD $(git -C $REPO rev-parse --short HEAD) $(date +%H:%M:%S)"; cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
w6() { tag=$1; K=$2; shift 2
  stamp "w6[$tag] seed $K start"; env "$@" $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${tag}_seed$K --table-dir Tables/Baseline_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1
  stamp "w6[$tag] seed $K end rc=$? tables=$(ls Tables/Baseline_${tag}_seed$K 2>/dev/null | wc -l) miss=$(grep -c 'MISS at' $LOG/w6_${tag}_seed$K.log)"; grep mathcal Tables/Baseline_${tag}_seed$K/welfare6_candidate.tex 2>/dev/null | head -3; }
band() { tag=$1; out=$2; shift 2; stamp "band[$tag]"; $PY compute_welfare6_se_table.py --summaries "$@" --out $LOG/$out 2>&1 | tail -11; }
PAPERNUM=(HAFISCAL_WORLD=default HAFISCAL_UI_STATE_ENCODING=legacy HAFISCAL_UI_EXTENSION_POLICY=window HAFISCAL_MC_SHUFFLE=0 HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_WELFARE_ENGINE=hark HAFISCAL_MC_WEIGHTED_TAIL=0 HAFISCAL_POLICY_STORE_REQUIRE=0)
for K in 0 1 2 3 4; do w6 uiL_nshuf $K "${PAPERNUM[@]}"; done
band uiL_nshuf welfare6_uiL_nshuf_S5_seed_band.tex Tables/Baseline_uiL_nshuf_seed{0,1,2,3,4}/welfare6_parallel_summary.json
for K in 3 4; do w6 uiA $K HAFISCAL_WORLD=default HAFISCAL_UI_EXTENSION_POLICY=window; done
band uiA welfare6_uiA_S5_seed_band.tex Tables/Baseline_uiA_seed{0,1,2,3,4}/welfare6_parallel_summary.json
echo "P10 DELL DONE $(date +%H:%M:%S)"
