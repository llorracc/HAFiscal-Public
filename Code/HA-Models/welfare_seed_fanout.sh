#!/usr/bin/env bash
# Cross-machine S=3 welfare fan-out (owner-ruled 2026-08-23: "do seed-spreading first").
#
# Farms run_welfare6_parallel seeds across machines -- seed 0 on THIS machine,
# seeds 1/2 on remote hosts -- then harvests the remote table dirs, runs the C4
# internal-band gate, and builds the cross-seed SE table. Certified basis: the
# 2026-08-23 m5 parity arm (identical seed-0 run on macOS-ARM matched dell to
# <=1.99e-4 per cell -- two orders below the seed band), so platform variation
# cannot masquerade as seed variation at gate resolution.
#
# Usage:
#   welfare_seed_fanout.sh --tag <label> [--repo-dir <local-repo>] \
#       [--world default|as-corrected] [--remotes "host1 host2"] [--cold]
#
# Contract: local repo and every remote's ~/GitHub/llorracc/HAFiscal-Latest are
# at the SAME commit (checked, fatal if not); remotes have the canonical FTI
# checkout (the welfare path is ATI-on, unavailability FATAL by owner ruling).
set -u -o pipefail

TAG=""; RDIR="/home/shared/github/llorracc/HAFiscal-Latest"; WORLD="default"
REMOTES="ccarroll-m5 ccarroll"; COLD=0
while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG="$2"; shift;;
    --repo-dir) RDIR="$2"; shift;;
    --world) WORLD="$2"; shift;;
    --remotes) REMOTES="$2"; shift;;
    --cold) COLD=1;;
    *) echo "unknown arg $1" >&2; exit 64;;
  esac; shift
done
[ -n "$TAG" ] || { echo "--tag required" >&2; exit 64; }
LOCAL_SHA=$(git -C "$RDIR" rev-parse HEAD) || exit 65
FPC="$RDIR/Code/HA-Models/FromPandemicCode"
LOGD="$HOME/fanout_${TAG}"; mkdir -p "$LOGD"
echo "== welfare seed fan-out: tag=$TAG world=$WORLD cold=$COLD sha=${LOCAL_SHA:0:8}"
echo "   local=$RDIR  remotes=$REMOTES  logs=$LOGD"

park_cmd='
park_data() {  # park no-.py cache subdirs (package-safe; idempotent)
  local C="$1/Code/HA-Models/solution_cache" P
  [ -d "$C" ] || return 0
  P="$C/.parked-fanout"; mkdir -p "$P"
  for d in "$C"/*/; do
    [ -d "$d" ] || continue
    b="$(basename "$d")"; case "$b" in .parked-*) continue;; esac
    ls "$d"*.py >/dev/null 2>&1 || mv "$d" "$P/" 2>/dev/null
  done
}'

# --- launch remote seeds 1..N ---
i=0; RHOSTS=(); RPIDS=()
for H in $REMOTES; do
  i=$((i+1)); K=$i
  echo "-- seed $K -> $H"
  ssh "$H" "bash -s" > "$LOGD/seed${K}_${H}.launch" 2>&1 << REOF &
set -u
export PATH="/opt/homebrew/bin:\$HOME/.local/bin:\$PATH"
R=\$HOME/GitHub/llorracc/HAFiscal-Latest
SHA=\$(git -C "\$R" rev-parse HEAD)
[ "\$SHA" = "$LOCAL_SHA" ] || { echo "COMMIT MISMATCH: \$SHA != $LOCAL_SHA"; exit 66; }
$park_cmd
[ "$COLD" = "1" ] && park_data "\$R"
cd "\$R/Code/HA-Models/FromPandemicCode" || exit 65
env PYTHONUNBUFFERED=1 HAFISCAL_WORLD=$WORLD "\$R/.venv/bin/python" run_welfare6_parallel.py \
  --baseline --seed-offset $K \
  --out-dir welfare6_scenario_results_Baseline_${TAG}_seed$K \
  --table-dir Tables/Baseline_${TAG}_seed$K > \$HOME/fanout_${TAG}_seed$K.log 2>&1
echo "rc=\$?"
REOF
  RPIDS+=($!); RHOSTS+=("$H")
done

# --- seed 0 locally ---
echo "-- seed 0 -> local ($RDIR)"
eval "$park_cmd"; [ "$COLD" = "1" ] && park_data "$RDIR"
( cd "$FPC" && env PYTHONUNBUFFERED=1 HAFISCAL_WORLD=$WORLD "$RDIR/.venv/bin/python" \
    run_welfare6_parallel.py --baseline --seed-offset 0 \
    --out-dir "welfare6_scenario_results_Baseline_${TAG}_seed0" \
    --table-dir "Tables/Baseline_${TAG}_seed0" ) > "$LOGD/seed0_local.log" 2>&1
RC0=$?
echo "   seed 0 rc=$RC0"

# --- wait for remotes, harvest ---
FAIL=$RC0
for j in "${!RPIDS[@]}"; do
  wait "${RPIDS[$j]}"; RRC=$?
  K=$((j+1)); H="${RHOSTS[$j]}"
  grep -q "rc=0" "$LOGD/seed${K}_${H}.launch" || RRC=1
  echo "   seed $K ($H) rc=$RRC"
  FAIL=$((FAIL + RRC))
  scp -q -r "$H:GitHub/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Tables/Baseline_${TAG}_seed$K" \
      "$FPC/Tables/" || FAIL=$((FAIL+1))
done
[ "$FAIL" -eq 0 ] || { echo "FANOUT FAILED ($FAIL); logs in $LOGD"; exit 70; }

# --- gate (internal 3-seed band) + SE table ---
"$RDIR/.venv/bin/python" "$RDIR/Code/HA-Models/full_profile_rerun_gates.py" s5b --fresh \
  "$FPC/Tables/Baseline_${TAG}_seed0/welfare6_parallel_summary.json" \
  "$FPC/Tables/Baseline_${TAG}_seed1/welfare6_parallel_summary.json" \
  "$FPC/Tables/Baseline_${TAG}_seed2/welfare6_parallel_summary.json" \
  | tee "$LOGD/band.gate"; GRC=${PIPESTATUS[0]}
# --summaries (2026-08-24): the SE table is computed from the three seeds' own
# summary cells — the remote seeds return their summary, not their raw pickles,
# so the former --seed-dirs (raw-pickle) mode saw only seed 0 here and printed an
# all-nan band for the accert fan-out. The generator now refuses missing seeds.
( cd "$FPC" && "$RDIR/.venv/bin/python" compute_welfare6_se_table.py \
    --summaries "$FPC/Tables/Baseline_${TAG}_seed0/welfare6_parallel_summary.json" \
                "$FPC/Tables/Baseline_${TAG}_seed1/welfare6_parallel_summary.json" \
                "$FPC/Tables/Baseline_${TAG}_seed2/welfare6_parallel_summary.json" \
    --out "$LOGD/welfare6_seed_band.tex" ) >> "$LOGD/band.log" 2>&1 \
  || echo "[warn] seed-band SE table generation FAILED (see $LOGD/band.log)"
echo "== fan-out complete: band gate rc=$GRC; artifacts $LOGD + Tables/Baseline_${TAG}_seed{0,1,2}"
exit "$GRC"
