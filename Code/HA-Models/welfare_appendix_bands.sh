#!/bin/bash
# The robustness-appendix welfare bands under the CURRENT default engine (owner 2026-09-07: the income-strata
# shuffle adopted -> every document exhibit onto one configuration). Six arms x seeds 0-2 (the appendix's
# S = 3), each into Tables/<TAG>_seed<k> exactly as rerun_logs/appendix_20260906/arm.sh wrote them; the
# previous vintage's summaries are snapshotted first. The history-policy arm (Baseline_uiB) pins the policy,
# as arm.sh did; nothing else is pinned but the entry-point-owned flags. Store in require-hit mode: every
# arm's Step 5a ran on this machine on 2026-09-07 (a MISS is an error, not a cold solve). The parked
# _histB arms are NOT re-run (owner: no robustness tables for the alternative policy).
# Usage: welfare_appendix_bands.sh [TAG]     logs rerun_logs/<TAG>/; marker DONE (OK|FAIL)
set -u
HA=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd); REPO=$(builtin cd "$HA/../.." && pwd)
TAG=${1:-appendix_adopt_$(date +%Y%m%d)}; L=$HA/rerun_logs/$TAG; mkdir -p "$L/before"
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg JAX_PLATFORMS=cpu
export HAFISCAL_WORLD=default HAFISCAL_TM_A_INDEXED=1 HAFISCAL_STEP5_ATI=1
export HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=${APPENDIX_REQUIRE:-1}
# APPENDIX_REQUIRE=0 lets a welfare child solve a policy the arm's Step 5a did not produce: on 2026-09-08 02:14 the
# UI scenario's S=252 agents MISSED on m5 right after that arm's 5a had run (open item: why 5a does not cover them).
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
builtin cd "$HA/FromPandemicCode" || exit 9
echo "===== appendix bands ($TAG) on $(hostname) start $(date '+%F %H:%M:%S') HEAD=$(git -C "$REPO" rev-parse --short HEAD)"
# APPENDIX_ARMS overrides the list ("NAME:TAG ..."): the Rfree_1005 / Rfree_1015 / LowerUBnoB arms were solved on m5 and
# harvested (rerun_logs/appendix_20260906/harvest_m5.sh), so dell's policy store has no policies for them -- a
# require-hit MISS in 8 s on 2026-09-07 23:36. Those three run on m5; ADElas / CRRA3 / Baseline_uiB on dell.
ARMS=${APPENDIX_ARMS:-"ADElas:ADElas CRRA3:CRRA3 Rfree_1005:Rfree_1005 Rfree_1015:Rfree_1015 LowerUBnoB:LowerUBnoB Baseline:Baseline_uiB"}
for pair in $ARMS; do
  NAME=${pair%%:*}; T=${pair##*:}
  for K in 0 1 2; do [ -f "Tables/${T}_seed$K/welfare6_parallel_summary.json" ] && [ ! -f "$L/before/${T}_seed$K/welfare6_parallel_summary.json" ] && { mkdir -p "$L/before/${T}_seed$K"; cp "Tables/${T}_seed$K/welfare6_parallel_summary.json" "$L/before/${T}_seed$K/"; }; done
done
for pair in $ARMS; do
  NAME=${pair%%:*}; T=${pair##*:}
  ( case "$T" in *_uiB|*_histB) export HAFISCAL_UI_EXTENSION_POLICY=historical; echo "  [arm] $T pins HAFISCAL_UI_EXTENSION_POLICY=historical";; esac
    # APPENDIX_RUN_5A=1: run the arm's Step 5a first (the multiplier program is the policy PRODUCER: its
    # cold solves fill this machine's store and publish the AD equilibria the welfare children import).
    # Needed when an arm's policies are not in this machine's store under the current solver source
    # (2026-09-07 23:40: Rfree_1005 / Rfree_1015 / LowerUBnoB missed on both machines). The 5a
    # invocation is rerun_logs/appendix_20260906/arm.sh's: FIGS_SUFFIX carries the tag for the
    # history-policy arm. 5a runs without require-hit; the seeds below keep it.
    if [ "${APPENDIX_RUN_5A:-0}" = 1 ] && [ ! -f "$L/${T}_s5a.done" ]; then
      SFX=""; case "$T" in Baseline_uiB) SFX=_uiB;; *_histB) SFX=_histB;; esac
      echo "----- $T Step 5a start $(date '+%H:%M:%S')"
      env ${SFX:+HAFISCAL_FIGS_SUFFIX=$SFX} HAFISCAL_POLICY_STORE_REQUIRE=0 "$PY" AggFiscalMAIN_reduced.py --parametrization "$NAME" > "$L/mult_$T.log" 2>&1
      rc=$?; echo "----- $T Step 5a rc=$rc $(date '+%H:%M:%S') $(grep -h 'AD effect)' "Tables/$T/Multiplier_candidate.tex" 2>/dev/null | head -1 | cut -c1-80)"
      [ $rc -ne 0 ] && { echo "HALT 5a: see $L/mult_$T.log"; exit 9; }
      touch "$L/${T}_s5a.done"
    fi
    for K in 0 1 2; do
      # resume only on a per-battery marker written after rc=0: a FAILED battery also prints 'Wall clock',
      # and an old summary from a previous vintage may still sit in the table dir (bit 2026-09-08 02:15)
      [ -f "$L/${T}_seed$K.done" ] && { echo "----- $T seed $K done earlier, skipped"; continue; }
      echo "----- $T seed $K start $(date '+%H:%M:%S')"
      "$PY" run_welfare6_parallel.py --parametrization "$NAME" --seed-offset $K \
          --out-dir "welfare6_scenario_results_${T}_seed$K" --table-dir "Tables/${T}_seed$K" > "$L/w6_${T}_seed$K.log" 2>&1
      rc=$?; echo "----- $T seed $K rc=$rc $(date '+%H:%M:%S') $(grep -h 'Wall clock' "$L/w6_${T}_seed$K.log")"
      [ $rc -ne 0 ] && { echo "HALT: see $L/w6_${T}_seed$K.log"; exit 9; }
      touch "$L/${T}_seed$K.done"
    done
    true ) || { echo FAIL > "$L/DONE"; exit 9; }   # `true`: the loop's last test is FALSE on success (bit 2026-09-07 23:13)
done
echo "===== appendix bands done $(date '+%F %H:%M:%S')"; echo OK > "$L/DONE"
