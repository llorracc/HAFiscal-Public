#!/bin/bash
# Step 5b (welfare-6) for the as-corrected world under the CURRENT defaults, S = 5.
#
# S = 5 is the standing rule, not a choice: the 2026-08-01 S=3 ruling was superseded by its
# own 2026-08-28 addendum ("S = 5 is plenty, SEs are a diagnostic not for the paper"), and
# config/catalog.py's `welfare_seed_count` carries canonical="5". Point table = seed 0;
# seeds 1-4 feed the SE table and the C4 band gate.
#
# Pattern from rerun_logs/ui_ext_20260826/p7_ac_package_dell.sh:14, PLUS the entry-point-owned
# flags that postdate it: HAFISCAL_TM_A_INDEXED / HAFISCAL_STEP5_ATI are owned by do_all's
# Step 5, not by the world catalog, so stripping them falls back to OFF (the m-indexed TM,
# 15-25 % multiplier bias, BUG-033) rather than to a default.
#
# NOT pinned on purpose: AD_EQUILIBRIUM_SHARE, ONSET_SPIKE_T0_EXEMPT, UI_EXTENSION_POLICY.
# The catalog resolves all three for this world (sharing OFF -> its own AD loop, which is
# what makes an as-corrected battery ~14 min/seed rather than ~9). An explicit env would
# WIN over the catalog, so pinning them here would silently defeat the world axis.
# Verified afterwards from each seed's provenance sidecar.
set -u
L=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(builtin cd "$L/../../../.." && pwd)
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg JAX_PLATFORMS=cpu
export HAFISCAL_WORLD=as-corrected
export HAFISCAL_TM_A_INDEXED=1 HAFISCAL_STEP5_ATI=1
export HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
builtin cd "$REPO/Code/HA-Models/FromPandemicCode" || exit 9
TAG=ac_20260907
echo "===== as-corrected 5b (S=5) on $(hostname) start $(date '+%F %H:%M:%S')"
for K in 0 1 2 3 4; do
  echo "----- seed $K start $(date '+%H:%M:%S')"
  "$PY" run_welfare6_parallel.py --baseline --seed-offset "$K" \
      --out-dir "welfare6_scenario_results_Baseline_${TAG}_seed${K}" \
      --table-dir "Tables/Baseline_${TAG}_seed${K}" \
      > "$L/w6_${TAG}_seed${K}.log" 2>&1
  rc=$?
  echo "----- seed $K rc=$rc $(date '+%H:%M:%S') tables=$(ls Tables/Baseline_${TAG}_seed${K} 2>/dev/null | wc -l)"
  [ $rc -ne 0 ] && { echo "HALT: see $L/w6_${TAG}_seed${K}.log"; exit $rc; }
done
echo "----- across-seed SE table (--summaries: the mode that REFUSES on a missing seed)"
"$PY" compute_welfare6_se_table.py \
    --summaries Tables/Baseline_${TAG}_seed{0,1,2,3,4}/welfare6_parallel_summary.json \
    --out "$L/welfare6_${TAG}_seed_band.tex" 2>&1 | tail -5
echo "===== as-corrected 5b done $(date '+%F %H:%M:%S')"
