#!/bin/bash
# The BRIDGE ARM (owner 2026-09-07): the default world with the two settings that decouple the
# random streams across worlds switched OFF -- AD-equilibrium sharing and the weighted-tail
# panel sampler. Everything else is the default world's (calibration, lambda, UI policy, the
# onset-spike rule, the stratified shuffle).
#
# Why it exists. `default` and `as-corrected` differ in the panel sampler (weighted-tail vs
# equal-weight) and the AD path (shared TM equilibrium vs the battery's own loop). Both are
# IMPROVEMENTS, off in as-corrected by the world taxonomy, and both change how the random
# streams are consumed, so like-numbered seeds of the two worlds are NOT paired on the UI cells
# (per-seed difference SD ~= the unpaired expectation, measured 2026-09-07). This arm runs the
# default world with those two settings at their as-corrected values, so seed k here shares its
# panel draw and shock history with seed k of the as-corrected band; the world-to-world UI
# comparison then has a paired SE (~0.8 %) instead of the unpaired one (~2.3 %). The 08-29
# one-off that played this role (`Tables/Baseline_lam_nshare_seed*`) went stale because no
# driver owned it; this script is the owner. Consumed by welfare_band_compare.py.
#
# Pattern: rerun_logs/ascorrected_20260907/run_5b.sh (the as-corrected band of record), with
# the world flipped and the two decoupling settings pinned. HAFISCAL_TM_A_INDEXED / STEP5_ATI
# are entry-point-owned (stripping them falls back to OFF, BUG-033), so they are set here.
# NOT pinned: ONSET_SPIKE_T0_EXEMPT, UI_EXTENSION_POLICY, PERM_GROWTH_SCALE -- the catalog's
# default-world values apply; an explicit env would win over the catalog.
#
# Usage: welfare_bridge_arm.sh [TAG] [LOGDIR]      (default TAG=bridge_$(date +%Y%m%d))
# Seeds 0-4 sequential (S = 5, the standing rule); seed 0 solves the own-loop AD equilibria
# cold on a fresh solution cache, later seeds re-use them per RECONCILED-004.
set -u
HA=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(builtin cd "$HA/../.." && pwd)
TAG=${1:-bridge_$(date +%Y%m%d)}
LOGDIR=${2:-$HA/rerun_logs/$TAG}
mkdir -p "$LOGDIR"
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg JAX_PLATFORMS=cpu
export HAFISCAL_WORLD=default
export HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_MC_WEIGHTED_TAIL=0
# 2026-09-07 evening: the income-strata shuffle (p:5 + Madow rounding) became the default world's
# engine (owner ruling). It re-assigns transitions, so it is a third stream-changing improvement that
# as-corrected does not have; the bridge pins it OFF too (unset would now mean ON).
export HAFISCAL_SHUFFLE_MRKV_STRATA= HAFISCAL_SHUFFLE_MRKV_ROUNDING=hamilton
export HAFISCAL_TM_A_INDEXED=1 HAFISCAL_STEP5_ATI=1
export HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
builtin cd "$HA/FromPandemicCode" || exit 9
echo "===== bridge arm ($TAG) on $(hostname) start $(date '+%F %H:%M:%S') HEAD=$(git -C "$REPO" rev-parse --short HEAD)"
for K in 0 1 2 3 4; do
  echo "----- seed $K start $(date '+%H:%M:%S')"
  "$PY" run_welfare6_parallel.py --baseline --seed-offset "$K" \
      --out-dir "welfare6_scenario_results_Baseline_${TAG}_seed${K}" \
      --table-dir "Tables/Baseline_${TAG}_seed${K}" \
      > "$LOGDIR/w6_${TAG}_seed${K}.log" 2>&1
  rc=$?
  echo "----- seed $K rc=$rc $(date '+%H:%M:%S') tables=$(ls Tables/Baseline_${TAG}_seed${K} 2>/dev/null | wc -l)"
  [ $rc -ne 0 ] && { echo "HALT: see $LOGDIR/w6_${TAG}_seed${K}.log"; exit $rc; }
done
echo "----- across-seed SE table (--summaries: the mode that REFUSES on a missing seed)"
"$PY" compute_welfare6_se_table.py \
    --summaries Tables/Baseline_${TAG}_seed{0,1,2,3,4}/welfare6_parallel_summary.json \
    --out "$LOGDIR/welfare6_${TAG}_seed_band.tex" 2>&1 | tail -5
echo "===== bridge arm done $(date '+%F %H:%M:%S')"
