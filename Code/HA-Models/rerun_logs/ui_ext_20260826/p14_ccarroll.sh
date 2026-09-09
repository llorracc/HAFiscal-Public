#!/bin/bash
# P14 on ccarroll (2026-08-27 01:50): the two ladder arms whose welfare seeds the STRICT policy store refused on dell -- under
# HAFISCAL_PF_DECAY_EXTRAP=0 (and, expected, HAFISCAL_PF_DECAY_Q=slope) the arm's own stored policies fail the one-sweep
# re-verification (relative move 3e-3 > 1e-3: the published extrapolation is not a fixed point of a fresh sweep), and with
# HAFISCAL_POLICY_STORE_REQUIRE=1 the battery must not solve. Here: as-corrected world, REQUIRE=0 (the battery solves its
# own policies under the arm's convention -- the same numerics as the arm's 5a), seeds 0,1 per arm. Waits for P12.
set -u
W=$HOME/coldrun_ps; FPC=$W/Code/HA-Models/FromPandemicCode; PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python
LOG=$HOME/ui_ext_20260826
until grep -q "P12 CCARROLL DONE" $LOG/p12_ccarroll.out 2>/dev/null; do sleep 60; done
echo "P12 finished; starting P14 $(date +%H:%M:%S)"; cd $FPC
export HAFISCAL_FTI_REPO=$HOME/GitHub/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0 HAFISCAL_WORLD=as-corrected
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
arm() { tag=$1; shift; for K in 0 1; do stamp "w6[$tag] seed $K start"; env "$@" $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${tag}_seed$K --table-dir Tables/Baseline_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1; stamp "w6[$tag] seed $K end rc=$? tables=$(ls Tables/Baseline_${tag}_seed$K 2>/dev/null | wc -l | tr -d " ")"; grep mathcal Tables/Baseline_${tag}_seed$K/welfare6_candidate.tex 2>/dev/null | head -3; done; }
arm ac_nofix_pfdecay HAFISCAL_PF_DECAY_EXTRAP=0
arm ac_nofix_pfq HAFISCAL_PF_DECAY_Q=slope
echo "P14 CCARROLL DONE $(date +%H:%M:%S)"
