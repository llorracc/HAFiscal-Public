#!/bin/bash
# The N-LADDER for the income-strata shuffle's asymptotic certification (owner 2026-09-07, overnight).
#
# The Econ-1 plan's standard for a certified-numerics row: the stratified draw is an exact re-weighting,
# so the CRN-paired difference between the strata engine (pstratM: HAFISCAL_SHUFFLE_MRKV_STRATA=p:5, Madow)
# and its like-for-like control (plainM: no strata, Madow) must VANISH as the panel grows -- the same limit,
# not a point-wise match. Two scopes, one per panel sampler the two worlds use:
#   baseline  Baseline, default world under sharing with the weighted-tail panel (the default world's own
#             sampler), N = 10000, 40000, 100000 households (1x, 4x, 10x; the 08-27 ladder's rungs), store in
#             require-hit mode (N does not enter the policy key; Step 5a warmed it). Runs on m5.
#   hsonly    HS_Only, own AD loop and the EQUAL-WEIGHT panel (as-corrected's sampler), N = 1500, 6000, 24000,
#             96000 (the 08-26 as-corrected ladder's rungs); the store may be cold for HS_Only, so no
#             require-hit. Runs on dell after the appendix finish chain.
# Both arms pin BOTH flags (unset now means the new engine). Seeds 0-2 per rung, CRN-paired across arms.
# Output: Tables/<param>_nladder_<arm>_N<n>_seed<k>/; report: strata_nladder_report.py.
# Usage: welfare_strata_nladder.sh baseline|hsonly [TAG]      logs rerun_logs/<TAG>/; marker DONE (OK|FAIL)
set -u
SCOPE=${1:?scope: baseline or hsonly}; TAG=${2:-nladder_${SCOPE}_$(date +%Y%m%d)}
HA=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd); REPO=$(builtin cd "$HA/../.." && pwd)
L=$HA/rerun_logs/$TAG; mkdir -p "$L"
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg JAX_PLATFORMS=cpu
export HAFISCAL_WORLD=default HAFISCAL_TM_A_INDEXED=1 HAFISCAL_STEP5_ATI=1 HAFISCAL_QUIET_BETADISTR=1
case "$SCOPE" in
  baseline) PARAM=Baseline; NS="10000 40000 100000"; export HAFISCAL_POLICY_STORE_REQUIRE=1 ;;
  hsonly)   PARAM=HS_Only;  NS="1500 6000 24000 96000"; export HAFISCAL_POLICY_STORE_REQUIRE=0
            export HAFISCAL_AD_EQUILIBRIUM_SHARE=0 HAFISCAL_MC_WEIGHTED_TAIL=0 ;;
  *) echo "unknown scope $SCOPE"; exit 2 ;;
esac
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
builtin cd "$HA/FromPandemicCode" || exit 9
echo "===== N-ladder $SCOPE ($TAG) on $(hostname) start $(date '+%F %H:%M:%S') HEAD=$(git -C "$REPO" rev-parse --short HEAD) N={$NS}"
for N in $NS; do
  for ARM in plainM pstratM; do
    ( case "$ARM" in
        plainM)  export HAFISCAL_SHUFFLE_MRKV_STRATA= HAFISCAL_SHUFFLE_MRKV_ROUNDING=madow ;;
        pstratM) export HAFISCAL_SHUFFLE_MRKV_STRATA=p:5 HAFISCAL_SHUFFLE_MRKV_ROUNDING=madow ;;
      esac
      for K in 0 1 2; do
        T="${PARAM}_nladder_${ARM}_N${N}_seed${K}"
        [ -f "Tables/$T/welfare6_parallel_summary.json" ] && { echo "----- $T exists, skipped"; continue; }
        echo "----- $T start $(date '+%H:%M:%S')"
        "$PY" run_welfare6_parallel.py --parametrization "$PARAM" --agent-count-total "$N" --seed-offset "$K" \
            --out-dir "welfare6_scenario_results_$T" --table-dir "Tables/$T" > "$L/w6_$T.log" 2>&1
        rc=$?; echo "----- $T rc=$rc $(date '+%H:%M:%S') $(grep -h 'Wall clock' "$L/w6_$T.log")"
        [ $rc -ne 0 ] && { echo "HALT: see $L/w6_$T.log"; exit 9; }
      done
      true ) || { echo FAIL > "$L/DONE"; exit 9; }   # `true`: the loop's last test is FALSE on success (bit 2026-09-07 23:13)
  done
done
echo "===== N-ladder $SCOPE done $(date '+%F %H:%M:%S')"; echo OK > "$L/DONE"
