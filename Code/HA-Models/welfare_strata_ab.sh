#!/bin/bash
# The income-strata A/B (owner 2026-09-07: "run the strata A/B on dell now"), one ARM per invocation.
#
# Question: what does HAFISCAL_SHUFFLE_MRKV_STRATA=p:5 (exact Markov-transition quotas within initial-
# income quintiles of each source state; Econ-1, 2026-08-28) do to the welfare cells' across-seed noise
# and to their means on the CURRENT default world (sharing on, weighted-tail panel, paper_capped, lambda
# 0.44)? Its 40 % UI-SE cut was measured once (08-28, S=5) on the Gini-0.70 panel under the old UI
# policy, with a +1.4 % mean shift at paired t~2, unresolved. NOTHING here adopts the knob: the arms
# write their own Tables/Baseline_strataAB_<arm>_seed<k>/; the band of record is untouched.
#
# Arms (every arm CRN-paired with the band of record: whole-cell seeds 0-4, same engine, same machine):
#   plainM   no strata, Madow rounding (HAFISCAL_SHUFFLE_MRKV_ROUNDING=madow). The strata path FORCES
#            Madow rounding, so "strata vs the record" would differ in two things; this arm isolates
#            the rounding (plainM vs record) and gives the knob its like-for-like control.
#   pstratM  HAFISCAL_SHUFFLE_MRKV_STRATA=p:5 (Madow implied): pstratM vs plainM = the knob alone.
# Env = the band of record's (verified byte-identical by rerun_logs/slotfix_20260907/accept_seed0.sh):
# default world, TM a-indexed, ATI, policy store in require-hit mode (no child may solve). Slots pinned
# to 3 so the two arms can run concurrently within the 40 GB unit caps (2 x 3 x ~5 GB).
#
# Usage: welfare_strata_ab.sh record|plainM|pstratM [TAG]        logs: rerun_logs/<TAG>/; marker DONE_<arm>
set -u
ARM=${1:?arm: record, plainM or pstratM}; TAG=${2:-strata_ab_$(date +%Y%m%d)}
HA=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd); REPO=$(builtin cd "$HA/../.." && pwd)
L=$HA/rerun_logs/$TAG; mkdir -p "$L"
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg JAX_PLATFORMS=cpu
export HAFISCAL_WORLD=default HAFISCAL_TM_A_INDEXED=1 HAFISCAL_STEP5_ATI=1
export HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=1 HAFISCAL_MAX_CPU_SLOTS=3
# Every arm pins BOTH flags: since the owner's 2026-09-07 adoption the catalog default is p:5 + madow,
# so an unset flag means the NEW engine, not the plain one (test_mrkv_strata_arm_pinning.py).
case "$ARM" in
  record)  export HAFISCAL_SHUFFLE_MRKV_STRATA= HAFISCAL_SHUFFLE_MRKV_ROUNDING=hamilton ;;
  plainM)  export HAFISCAL_SHUFFLE_MRKV_STRATA= HAFISCAL_SHUFFLE_MRKV_ROUNDING=madow ;;
  pstratM) export HAFISCAL_SHUFFLE_MRKV_STRATA=p:5 HAFISCAL_SHUFFLE_MRKV_ROUNDING=madow ;;
  *) echo "unknown arm $ARM"; exit 2 ;;
esac
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
builtin cd "$HA/FromPandemicCode" || exit 9
echo "===== strata A/B arm $ARM on $(hostname) start $(date '+%F %H:%M:%S') HEAD=$(git -C "$REPO" rev-parse --short HEAD) env: ROUNDING=${HAFISCAL_SHUFFLE_MRKV_ROUNDING:-<unset>} STRATA=${HAFISCAL_SHUFFLE_MRKV_STRATA:-<unset>}"
for K in 0 1 2 3 4; do
  echo "----- $ARM seed $K start $(date '+%H:%M:%S')"
  "$PY" run_welfare6_parallel.py --baseline --seed-offset "$K" \
      --out-dir "welfare6_scenario_results_Baseline_strataAB_${ARM}_seed${K}" \
      --table-dir "Tables/Baseline_strataAB_${ARM}_seed${K}" > "$L/w6_${ARM}_seed${K}.log" 2>&1
  rc=$?
  echo "----- $ARM seed $K rc=$rc $(date '+%H:%M:%S') $(grep -h 'Wall clock' "$L/w6_${ARM}_seed${K}.log")"
  [ $rc -ne 0 ] && { echo "HALT: see $L/w6_${ARM}_seed${K}.log"; echo FAIL > "$L/DONE_$ARM"; exit $rc; }
done
echo "===== arm $ARM done $(date '+%F %H:%M:%S')"; echo OK > "$L/DONE_$ARM"
