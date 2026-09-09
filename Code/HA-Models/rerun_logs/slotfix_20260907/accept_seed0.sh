#!/bin/bash
# Acceptance for the slot fix (owner 2026-09-07): seed 0 of the default world's band of record,
# re-run WARM (HAFISCAL_POLICY_STORE_REQUIRE=1 -> the planner's warm envelope -> more scenario
# children at once), must be BYTE-IDENTICAL in every welfare cell to Tables/Baseline_seed0
# (the 09-07 band, planned cold at 3 slots). The duration pool was shown width-invariant on
# 2026-07-30 (one AggCons hash across dw=1..16); this re-verifies it at the slot level.
# Prints the planner's memory-plan line and the wall so the gain is measured, not assumed.
set -u
L=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(builtin cd "$L/../../../.." && pwd)
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg JAX_PLATFORMS=cpu
export HAFISCAL_WORLD=default
export HAFISCAL_TM_A_INDEXED=1 HAFISCAL_STEP5_ATI=1
export HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=1     # <- warm envelope by construction
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
builtin cd "$REPO/Code/HA-Models/FromPandemicCode" || exit 9
TAG=slotfix_20260907
echo "===== slot-fix acceptance: default seed 0, warm, on $(hostname) start $(date '+%F %H:%M:%S') HEAD=$(git -C "$REPO" rev-parse --short HEAD)"
T0=$(date +%s)
"$PY" run_welfare6_parallel.py --baseline --seed-offset 0 \
    --out-dir "welfare6_scenario_results_Baseline_${TAG}_seed0" \
    --table-dir "Tables/Baseline_${TAG}_seed0" > "$L/w6_${TAG}_seed0.log" 2>&1
rc=$?; T1=$(date +%s)
echo "----- rc=$rc wall=$((T1-T0))s  ($(( (T1-T0)/60 )) min)"
grep -h "memory plan\|^Slots:\|Wall clock" "$L/w6_${TAG}_seed0.log" | head -4
[ $rc -ne 0 ] && { echo "HALT: see $L/w6_${TAG}_seed0.log"; exit $rc; }
"$PY" - <<EOF
import json
a = json.load(open("Tables/Baseline_seed0/welfare6_parallel_summary.json"))["welfare6"]
b = json.load(open("Tables/Baseline_${TAG}_seed0/welfare6_parallel_summary.json"))["welfare6"]
bad = {k: (a[k], b.get(k)) for k in a if b.get(k) != a[k]}
print("cells compared:", len(a), " byte-identical:", len(a) - len(bad))
for k, (x, y) in bad.items():
    print(f"  DIFF {k}: record {x!r} vs warm {y!r}  rel {abs(y - x) / abs(x):.3e}")
raise SystemExit(0 if not bad else 2)
EOF
rc=$?; echo "===== acceptance $([ $rc -eq 0 ] && echo PASS: byte-identical || echo FAIL) $(date '+%H:%M:%S')"; exit $rc
