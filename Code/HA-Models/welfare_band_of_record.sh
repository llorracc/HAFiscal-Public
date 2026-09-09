#!/bin/bash
# The default world's welfare BAND OF RECORD (owner 2026-09-07): seed 0 into Tables/Baseline (the point
# table of record, as do_all's Step 5b writes it) and whole-cell seeds 0-4 into Tables/Baseline_seed<k>
# (the across-seed band: the SE table, the C4 gates, the paired reference). Every setting comes from the
# catalog through the world block -- this driver pins NOTHING but the entry-point-owned flags
# (HAFISCAL_TM_A_INDEXED / HAFISCAL_STEP5_ATI, which fall back to OFF when stripped, BUG-033) -- so a
# run of it IS the test that the catalog's defaults reach the computation. The acceptance step below
# reads each seed's provenance sidecar and asserts the engine of record -- since the owner's 2026-09-08
# revert, the plain shuffle with Hamilton rounding: HAFISCAL_SHUFFLE_MRKV_STRATA='' and
# HAFISCAL_SHUFFLE_MRKV_ROUNDING='hamilton' (conclusions_private/2026-09-08_strata-shuffle-revert-to-
# plain-hamilton_decision.md). From 2026-09-07 21:48 to 2026-09-08 the step compared against the pinned
# pstratM arm of rerun_logs/strata_ab_20260907/ instead; that arm is a record, not a reference.
#
# Store in require-hit mode: Step 5a must have warmed the policy store for this calibration (a MISS is
# an error, never a silent cold solve), which also lets the slot planner use the warm envelope.
#
# Usage: welfare_band_of_record.sh [TAG]      logs: rerun_logs/<TAG>/; marker DONE (OK|FAIL)
set -u
HA=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd); REPO=$(builtin cd "$HA/../.." && pwd)
TAG=${1:-band_$(date +%Y%m%d_%H%M)}; L=$HA/rerun_logs/$TAG; mkdir -p "$L"
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg JAX_PLATFORMS=cpu
export HAFISCAL_WORLD=default HAFISCAL_TM_A_INDEXED=1 HAFISCAL_STEP5_ATI=1
export HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=1
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
builtin cd "$HA/FromPandemicCode" || exit 9
echo "===== band of record ($TAG) on $(hostname) start $(date '+%F %H:%M:%S') HEAD=$(git -C "$REPO" rev-parse --short HEAD)"
echo "----- point table: seed 0 -> Tables/Baseline $(date '+%H:%M:%S')"
"$PY" run_welfare6_parallel.py --baseline --seed-offset 0 \
    --out-dir welfare6_scenario_results_Baseline --table-dir Tables/Baseline > "$L/w6_point_seed0.log" 2>&1
rc=$?; echo "----- point rc=$rc $(date '+%H:%M:%S') $(grep -h 'Wall clock' "$L/w6_point_seed0.log")"
[ $rc -ne 0 ] && { echo "HALT: see $L/w6_point_seed0.log"; echo FAIL > "$L/DONE"; exit $rc; }
for K in 0 1 2 3 4; do
  "$PY" run_welfare6_parallel.py --baseline --seed-offset "$K" \
      --out-dir "welfare6_scenario_results_Baseline_seed${K}" --table-dir "Tables/Baseline_seed${K}" \
      > "$L/w6_seed${K}.log" 2>&1
  rc=$?; echo "----- seed $K rc=$rc $(date '+%H:%M:%S') $(grep -h 'Wall clock' "$L/w6_seed${K}.log")"
  [ $rc -ne 0 ] && { echo "HALT: see $L/w6_seed${K}.log"; echo FAIL > "$L/DONE"; exit $rc; }
done
echo "----- across-seed SE table"
"$PY" compute_welfare6_se_table.py --summaries Tables/Baseline_seed{0,1,2,3,4}/welfare6_parallel_summary.json \
    --out "$L/welfare6_seed_band.tex" 2>&1 | tail -6
echo "----- acceptance: every seed's sidecar must record the engine of record (plain shuffle, Hamilton rounding)"
"$PY" - <<'PYEOF'
import glob, json, os
want = {"HAFISCAL_SHUFFLE_MRKV_STRATA": "", "HAFISCAL_SHUFFLE_MRKV_ROUNDING": "hamilton", "HAFISCAL_WORLD": "default"}
bad = 0
for d in ["Tables/Baseline"] + [f"Tables/Baseline_seed{k}" for k in range(5)]:
    scs = sorted(glob.glob(os.path.join(d, "RUN_*.prov.json")), key=os.path.getmtime)
    if not scs:
        bad += 1; print(f"  {d}: no provenance sidecar"); continue
    j = json.load(open(scs[-1])); env = dict(j.get("resolved_config", {}).get("env", {})); env.update(j.get("set_flags", {}))
    for k, v in want.items():
        got = env.get(k, "")
        if (got or "") != v:
            bad += 1; print(f"  {d}: {k}={got!r} (want {v!r})")
print(f"sidecars checked 6: engine-of-record violations {bad}")
raise SystemExit(0 if bad == 0 else 2)
PYEOF
rc=$?; echo "----- acceptance $([ $rc -eq 0 ] && echo PASS || echo FAIL)"
[ $rc -ne 0 ] && { echo FAIL > "$L/DONE"; exit $rc; }
echo "===== band of record done $(date '+%F %H:%M:%S')"; echo OK > "$L/DONE"
