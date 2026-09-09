#!/usr/bin/env bash
# Phase-gated full-profile install rerun (owner-ruled 2026-08-22; overnight run).
#
# Pre-registration: plans_local/20260822-1400h_full-profile-rerun-preregistration.md
# Gates C1-C6; comparators + tolerances live in full_profile_rerun_gates.py.
# Scope: Steps 1, 2, 5a, 5b (S=3 seeds). Steps 3/4 excluded (robustness).
# Any gate failure HALTs the cascade (no later phase starts); nothing is promoted
# by this driver -- all locked-table writes land as _candidate siblings (QE freeze).
#
# Usage:
#   full_profile_rerun_driver.sh                # dry run: print the plan, touch nothing
#   full_profile_rerun_driver.sh --launch [--knots 0|8] [--from s1|s2|s5a|s5b] \
#                                [--allow-dirty] [--allow-s1-fallback]
#
# --knots: pins HAFISCAL_STEP1_TAIL_KNOTS for phase S1 only (the install-config
#   ruling from the 2026-08-22 seam A/B); omitted => repo default.
# --from: resume at a later phase after a fixed failure (earlier phases' outputs
#   must already be in place from the previous attempt).
#
# Protocol amendment (owner 2026-08-23): when a gate failure is PROVEN benign
# during the run (mechanical wiring, or stale comparators via an A/B at the
# comparator's producing commit), later computationally-independent phases may be
# run INFORMATIONALLY via --from + --allow-dirty — evidence appended to the
# pre-registration BEFORE launch, results labeled informational, nothing promoted,
# the disposition still an owner decision. Unproven failures keep the hard cascade.
set -u -o pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HA="$REPO/Code/HA-Models"
FPC="$HA/FromPandemicCode"
GATES="$HA/full_profile_rerun_gates.py"
TS="$(date +%Y%m%d-%H%M)"
LOGDIR="$HA/rerun_logs/$TS"
LAUNCH=0; KNOTS=""; FROM="s1"; ALLOW_DIRTY=0; ALLOW_FALLBACK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --launch) LAUNCH=1 ;;
    --knots) KNOTS="$2"; shift ;;
    --from) FROM="$2"; shift ;;
    --allow-dirty) ALLOW_DIRTY=1 ;;
    --allow-s1-fallback) ALLOW_FALLBACK=1 ;;
    *) echo "unknown arg: $1" >&2; exit 64 ;;
  esac
  shift
done

# ---- environment contract (C5/C6 + FTI production convention) ----
export PYTHONUNBUFFERED=1
export HAFISCAL_FTI_REPO="${HAFISCAL_FTI_REPO:-/home/shared/github/llorracc/fast-time-iteration}"
PY="$REPO/.venv/bin/python"

phase_rank() { case "$1" in s1) echo 1;; s2) echo 2;; s5a) echo 3;; s5b) echo 4;; *) echo 99;; esac; }
RANK_FROM=$(phase_rank "$FROM")
run_phase() { [ "$(phase_rank "$1")" -ge "$RANK_FROM" ]; }

echo "== full-profile rerun driver =="
echo "repo:        $REPO"
echo "python:      $PY"
echo "FTI repo:    $HAFISCAL_FTI_REPO"
echo "knots pin:   ${KNOTS:-<repo default>}"
echo "from phase:  $FROM"
echo "logs:        $LOGDIR"
echo "mode:        $([ $LAUNCH -eq 1 ] && echo LAUNCH || echo 'DRY RUN (pass --launch to execute)')"

# ---- preflight (checks run even in dry mode; mutations only under --launch) ----
fail() { echo "PREFLIGHT FAIL: $*" >&2; exit 65; }
[ -x "$PY" ] || fail "venv python not found at $PY (run: make sync)"
[ -d "$HAFISCAL_FTI_REPO" ] || fail "FTI repo missing at $HAFISCAL_FTI_REPO"
"$PY" -c "import sys,os; sys.path.insert(0, os.environ['HAFISCAL_FTI_REPO']); import hark_fti" \
  || fail "hark_fti not importable from \$HAFISCAL_FTI_REPO (FTI is mandatory on routed Step-2/5 paths)"
"$PY" -c "import ast; ast.parse(open('$GATES').read())" || fail "gate script unparseable"
cd "$REPO" || exit 65
DIRTY="$(git status --porcelain)"
if [ -n "$DIRTY" ] && [ $ALLOW_DIRTY -eq 0 ]; then
  fail "working tree dirty (C6 wants a tagged, clean commit); commit first or --allow-dirty"
fi
echo "preflight:   OK (HEAD $(git rev-parse --short HEAD), $([ -n "$DIRTY" ] && echo DIRTY || echo clean))"

if [ $LAUNCH -eq 0 ]; then
  echo; echo "Plan: S1(full-grid continuation, gates C1+A1-A3) -> S2(3 groups, C2)"
  echo "      -> S5a(TM multipliers, C3) -> S5b(welfare6 x3 seeds, C4) -> seed-band table"
  echo "Caches: solution_cache parked for the run (C5, cold), restored on exit."
  exit 0
fi

mkdir -p "$LOGDIR"
TAG="rerun-full-$TS"
git tag -a "$TAG" -m "full-profile install rerun launch (driver $TS)" 2>/dev/null \
  && echo "tagged:      $TAG" || echo "tag:         $TAG already exists (resume)"

# C5: cold caches -- park the DATA subdirs only. solution_cache/ is ALSO a code
# package (welfare6_scenario does `from solution_cache import cached_eco_solve`
# unconditionally), so moving the whole directory breaks the import (lesson
# 2026-08-23: seed 0 died on ModuleNotFoundError). Rule: a top-level subdir with
# no *.py files is cache data -> park it; .py-bearing dirs (the package itself,
# _armc_bench scratch) stay.
CACHE="$HA/solution_cache"; PARKED=""
if [ -d "$CACHE" ]; then
  PARKED="$CACHE/.parked-$TS"; mkdir -p "$PARKED"
  for d in "$CACHE"/*/; do
    [ -d "$d" ] || continue
    b="$(basename "$d")"
    case "$b" in .parked-*) continue;; esac
    if ! ls "$d"*.py >/dev/null 2>&1; then mv "$d" "$PARKED/"; fi
  done
  echo "caches:      data subdirs parked -> $PARKED ($(ls "$PARKED" 2>/dev/null | wc -l) dirs; package left importable)"
fi
restore_caches() {
  if [ -n "$PARKED" ] && [ -d "$PARKED" ]; then
    for d in "$PARKED"/*/; do
      [ -d "$d" ] || continue
      b="$(basename "$d")"
      if [ -d "$CACHE/$b" ]; then
        echo "caches:      NOT restoring $b (fresh entries written during the run); parked copy stays at $PARKED/$b"
      else
        mv "$d" "$CACHE/$b"
      fi
    done
    rmdir "$PARKED" 2>/dev/null && echo "caches:      restored" || echo "caches:      partial restore; see $PARKED"
  fi
}
trap restore_caches EXIT

halt() { echo; echo "!! HALT at phase $1: $2 (cascade stopped; later phases NOT run)"; exit 70; }
wall() { echo "[wall] phase $1: $(( ($2 + 30) / 60 )) min"; }

# ---------------- Phase S1: splurge estimation, full grid, continuation --------
if run_phase s1; then
  echo; echo "-- phase S1 (log: $LOGDIR/s1.log)"
  T0=$SECONDS
  ( cd "$HA" && env HAFISCAL_RUN_STEP_1=1 HAFISCAL_RUN_STEP_2=0 HAFISCAL_RUN_STEP_3=0 \
      HAFISCAL_RUN_STEP_4=0 HAFISCAL_RUN_STEP_5=0 \
      HAFISCAL_SOLVE_GRID_PROFILE=full \
      ${KNOTS:+HAFISCAL_STEP1_TAIL_KNOTS=$KNOTS} \
      OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
      "$PY" do_all.py ) > "$LOGDIR/s1.log" 2>&1
  RC=$?; wall s1 $((SECONDS - T0))
  [ $RC -eq 0 ] || halt s1 "do_all step 1 rc=$RC"
  # first-use-of-axis tripwire: PROFILE=full has never flowed through do_all before
  # tonight -- positively verify the FULL grid reached the solver (604/238 echo), since
  # a silently-dropped env var would run the fast grid (604/75) whose winner-wander
  # could still land inside A3.
  grep -q "aXtraMax/aXtraCount: 604/238" "$LOGDIR/s1.log" \
    || halt s1 "full-grid echo (604/238) absent from s1.log -- SOLVE_GRID_PROFILE=full did not reach the solver"
  "$PY" "$GATES" s1 --dir "$HA/Target_AggMPCX_LiquWealth" --log "$LOGDIR/s1.log" \
      $([ $ALLOW_FALLBACK -eq 1 ] && echo --allow-fallback) \
      | tee "$LOGDIR/s1.gate" ; GRC=${PIPESTATUS[0]}
  [ "$GRC" -eq 0 ] || halt s1 "gate C1/A1-A3 failed (see $LOGDIR/s1.gate)"
fi

# ---------------- Phase S2: discount-factor estimation, 3 groups ---------------
if run_phase s2; then
  echo; echo "-- phase S2 (log: $LOGDIR/s2.log)"
  T0=$SECONDS
  ( cd "$HA" && env HAFISCAL_RUN_STEP_1=0 HAFISCAL_RUN_STEP_2=1 HAFISCAL_RUN_STEP_3=0 \
      HAFISCAL_RUN_STEP_4=0 HAFISCAL_RUN_STEP_5=0 \
      "$PY" do_all.py ) > "$LOGDIR/s2.log" 2>&1
  RC=$?; wall s2 $((SECONDS - T0))
  [ $RC -eq 0 ] || halt s2 "do_all step 2 rc=$RC"
  # literal log-line match (lesson 2026-08-23: the first version grepped my own
  # paraphrase "ATI ROUTED"; the router actually prints "[step5-ati] ROUTED:")
  grep -q "\[step5-ati\] ROUTED:" "$LOGDIR/s2.log" || halt s2 "no '[step5-ati] ROUTED:' lines in log (FTI must be in use on qualified Step-2 solves)"
  "$PY" "$GATES" s2 --results "$HA/Results" | tee "$LOGDIR/s2.gate"; GRC=${PIPESTATUS[0]}
  [ "$GRC" -eq 0 ] || halt s2 "gate C2 failed (see $LOGDIR/s2.gate)"
fi

# ---------------- Phase S5a: TM multipliers ------------------------------------
if run_phase s5a; then
  echo; echo "-- phase S5a (log: $LOGDIR/s5a.log)"
  T0=$SECONDS
  ( cd "$HA" && env HAFISCAL_RUN_STEP_1=0 HAFISCAL_RUN_STEP_2=0 HAFISCAL_RUN_STEP_3=0 \
      HAFISCAL_RUN_STEP_4=0 HAFISCAL_RUN_STEP_5=1 HAFISCAL_RUN_STEP_5B=0 \
      "$PY" do_all.py ) > "$LOGDIR/s5a.log" 2>&1
  RC=$?; wall s5a $((SECONDS - T0))
  [ $RC -eq 0 ] || halt s5a "do_all step 5a rc=$RC"
  MTAB="$FPC/Tables/Baseline/Multiplier_candidate.tex"
  [ -f "$MTAB" ] || MTAB="$FPC/Tables/Baseline/Multiplier.tex"
  "$PY" "$GATES" s5a --table "$MTAB" | tee "$LOGDIR/s5a.gate"; GRC=${PIPESTATUS[0]}
  [ "$GRC" -eq 0 ] || halt s5a "gate C3 failed (see $LOGDIR/s5a.gate)"
fi

# ---------------- Phase S5b: welfare-6, S=3 seeds ------------------------------
if run_phase s5b; then
  FRESH=()
  for K in 0 1 2; do
    echo; echo "-- phase S5b seed $K (log: $LOGDIR/s5b_seed$K.log)"
    if [ "$K" -eq 0 ]; then
      # seed 0 = the canonical do_all shape: its table writes are the promotable
      # _candidate artifacts in Tables/Baseline (candidate-set convention).
      ODIR="welfare6_scenario_results_Baseline_reproduce"; TDIR="Tables/Baseline"
      SUMMARY="$FPC/Tables/Baseline/welfare6_parallel_summary.json"
      # keep the installed comparator before seed 0 overwrites it
      cp "$SUMMARY" "$LOGDIR/welfare6_summary_installed_ref.json" 2>/dev/null || true
    else
      ODIR="welfare6_scenario_results_Baseline_rerun_seed$K"; TDIR="Tables/Baseline_rerun_seed$K"
      SUMMARY="$FPC/$TDIR/welfare6_parallel_summary.json"
    fi
    T0=$SECONDS
    ( cd "$FPC" && "$PY" run_welfare6_parallel.py --baseline --seed-offset "$K" \
        --out-dir "$ODIR" --table-dir "$TDIR" ) > "$LOGDIR/s5b_seed$K.log" 2>&1
    RC=$?; wall "s5b_seed$K" $((SECONDS - T0))
    [ $RC -eq 0 ] || halt s5b "run_welfare6_parallel seed $K rc=$RC"
    FRESH+=("$SUMMARY")
  done
  # C4 as reformulated (D2, 2026-08-23): internal 3-seed band; external
  # comparisons (spine4 seed-2, published QE) are report material, not gates.
  "$PY" "$GATES" s5b --fresh "${FRESH[@]}" | tee "$LOGDIR/s5b.gate"; GRC=${PIPESTATUS[0]}
  [ "$GRC" -eq 0 ] || halt s5b "gate C4 failed (see $LOGDIR/s5b.gate)"
  # explicit seed-band aggregation (never inferred from one seed) — from the same
  # per-seed summaries the gate just consumed (--summaries, 2026-08-24; the raw-pickle
  # --seed-dirs mode printed an all-nan band whenever a seed's pickles were absent)
  ( cd "$FPC" && "$PY" compute_welfare6_se_table.py \
      --summaries "${FRESH[@]}" \
      --out "$LOGDIR/welfare6_seed_band.tex" ) >> "$LOGDIR/s5b_band.log" 2>&1 \
    || echo "[warn] seed-band table generation failed (see s5b_band.log) -- gates already passed"
fi

echo; echo "== ALL GATES PASSED =="
echo "Candidate artifacts staged (QE freeze intact -- promotion is a separate, reviewed step):"
echo "  git -C $REPO status --short   # review overwritten intermediates + _candidate tables"
echo "  logs + gate reports: $LOGDIR"
