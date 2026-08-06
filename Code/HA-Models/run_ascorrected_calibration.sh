#!/usr/bin/env bash
#
# run_ascorrected_calibration.sh — launch the revised (default + as-corrected)
# calibration re-estimation, exactly per the frozen owner-ruled spec:
#   plans/20260614_as-corrected-calibration-run-spec.md
#
# The two worlds differ on EXACTLY ONE economic axis (perm_during_unemp):
#   default      -> HAFISCAL_PERM_DURING_UNEMP=on   (via HAFISCAL_WORLD=default)
#   as-corrected -> HAFISCAL_PERM_DURING_UNEMP=off  (via HAFISCAL_WORLD=as-corrected)
# Everything else is held identical in both worlds (owner rulings 2026-06-13/14):
#   interpretation = ESC          (now the production default; set explicit for clarity)
#   gicx           = hardcoded    (2-D; result-neutral; same in both)
#   nm_tol         = 1e-3         (HAFISCAL_NM_XATOL/FATOL; same in both)
#   NM start       = cold         (HAFISCAL_NM_START_FROM_SAVED=0)
#   bug-fixes      = all ON       (theGICfactor=0.9995, GIC_SHAVE_ON_GPF, PERMGROFAC_FIX,
#                                  6-state UI, a-indexed TM, stratified shuffle, aMax=1300)
#
# Scope (owner ruling scope=both): re-estimate Step 1 (splurge, SHARED — run ONCE,
# perm-independent) + Step 2 (beta,nabla — run per world).
#
# Output (world-suffixed, non-clobbering):
#   default      -> Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt
#   as-corrected -> Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC_ascorrected.txt
#   splurge      -> Target_AggMPCX_LiquWealth/Result_AllTarget_ESC.txt (shared; not world-tagged)
#
# Compute (slow path): Step 1 ~30 min (once); Step 2 ~48 h per world (cohort-parallel
# across edTypes via run_phase2_parallel.py shortens wall time to ~longest cohort).
#
# SAFETY: this is a MULTI-DAY run. By default this script only PRINTS the plan
# (dry-run). Pass --run to actually execute.
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Original invocation (captured before arg parsing consumes "$@"), for provenance.
ORIG_ARGV="run_ascorrected_calibration.sh $*"

# ---- defaults ----
WORLDS_ARG="both"
SKIP_SPLURGE=0
DO_RUN=0
PARALLEL_WORLDS=0

usage() {
    cat <<'USAGE'
Usage: run_ascorrected_calibration.sh [--run] [--world default|as-corrected|both]
                                      [--skip-splurge] [--parallel-worlds]

  --run               Actually execute (default: dry-run — print the plan only).
  --world WORLD       Which world(s) to (re)estimate Step 2 for. Default: both.
  --skip-splurge      Skip Step 1 (reuse the existing ESC splurge on disk).
  --parallel-worlds   Run both worlds' Step 2 CONCURRENTLY after the shared
                      splurge (uses ~2x the cores: 3 edType procs/world = 6
                      total). BLAS is pinned to 1 thread/process to avoid
                      oversubscription. Needs ~2x RAM; use only on a box with
                      enough cores AND memory. No-op unless --world both.
  -h, --help          Show this help.

Core use: within ONE world, Step 2 is 3-way parallel (one subprocess per
education type; in-process HARK parallelism is intentionally disabled — joblib
OOM recursion). --parallel-worlds is the lever to use more than 3 cores during
estimation. (Step 1 splurge is single-process and brief.)

Spec: plans/20260614_as-corrected-calibration-run-spec.md
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --run) DO_RUN=1; shift ;;
        --world)
            shift
            [[ $# -gt 0 ]] || { echo "ERROR: --world needs an argument" >&2; exit 1; }
            WORLDS_ARG="$1"; shift ;;
        --skip-splurge) SKIP_SPLURGE=1; shift ;;
        --parallel-worlds) PARALLEL_WORLDS=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
done

case "$WORLDS_ARG" in
    default)      WORLDS=("default") ;;
    as-corrected) WORLDS=("as-corrected") ;;
    both)         WORLDS=("default" "as-corrected") ;;
    *) echo "ERROR: --world must be default | as-corrected | both (got '$WORLDS_ARG')" >&2; exit 1 ;;
esac

# ---- common spec env (exported to all child processes) ----
export HAFISCAL_INTERPRETATION=ESC      # production default anyway; explicit for provenance
export HAFISCAL_GICX_MODE=hardcoded     # 2-D, result-neutral, both worlds
export HAFISCAL_NM_XATOL=1e-3           # owner ruling nm_tol=1e-3 (both worlds)
export HAFISCAL_NM_FATOL=1e-3
export HAFISCAL_NM_START_FROM_SAVED=0   # cold NM starts (both worlds)

# When running both worlds concurrently, pin BLAS to 1 thread/process so the
# 6 concurrent edType subprocesses don't oversubscribe the cores (N procs ×
# M BLAS threads = thrash). Harmless to the sequential path's throughput
# (the bottleneck is the per-period EGM solve loop, not BLAS), but only set
# it when we actually fan out, to keep the default path byte-for-byte legacy.
if [[ "$PARALLEL_WORLDS" -eq 1 ]]; then
    export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
    export VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1
fi

PY="${PYTHON:-python}"

log() { printf '[ascorrected-calib] %s\n' "$*"; }

run_or_echo() {
    # Print the command; execute only under --run.
    log "+ $*"
    if [[ "$DO_RUN" -eq 1 ]]; then
        "$@"
    fi
}

# Emit a run-provenance sidecar + central manifest for a completed world's
# Stage-A outputs (best-effort; never aborts the run). See provenance.py.
emit_provenance() {
    local w="$1" suf
    [[ "$DO_RUN" -eq 1 ]] || return 0
    [[ -f provenance.py ]] || { log "provenance.py not found; skipping provenance for world=$w"; return 0; }
    if [[ "$w" == default ]]; then suf="_ESC"; else suf="_ESC_ascorrected"; fi
    log "provenance: emitting sidecar + manifest for world=$w"
    HAFISCAL_WORLD="$w" "$PY" provenance.py emit \
        --output-dir Results \
        --output-dir Target_AggMPCX_LiquWealth \
        --output-root "Results/DiscFacEstim_CRRA_2.0_R_1.01${suf}_candidate.txt" \
        --output-root "Results/AllResults_CRRA_2.0_R_1.01${suf}_candidate.txt" \
        --output-root "Target_AggMPCX_LiquWealth/Result_AllTarget_ESC.txt" \
        --command "$ORIG_ARGV" \
        --label "stageA-${w}" \
        || log "provenance emit failed (non-fatal) for world=$w"
}

log "================================================================"
log "Revised calibration run — spec plans/20260614_as-corrected-calibration-run-spec.md"
log "mode          : $([[ "$DO_RUN" -eq 1 ]] && echo 'RUN (executing)' || echo 'DRY-RUN (plan only; pass --run to execute)')"
log "worlds (Step2): ${WORLDS[*]}$([[ "$PARALLEL_WORLDS" -eq 1 && "${#WORLDS[@]}" -gt 1 ]] && echo ' (CONCURRENT; BLAS pinned to 1)' || echo ' (sequential)')"
log "skip splurge  : $([[ "$SKIP_SPLURGE" -eq 1 ]] && echo yes || echo no)"
log "common env    : HAFISCAL_INTERPRETATION=ESC GICX_MODE=hardcoded NM_XATOL=NM_FATOL=1e-3 NM_START_FROM_SAVED=0"
log "================================================================"

# ---- Step 1: splurge (SHARED — run ONCE; perm_during_unemp-independent) ----
if [[ "$SKIP_SPLURGE" -eq 1 ]]; then
    log "Step 1 (splurge): SKIPPED (--skip-splurge); reusing existing ESC splurge on disk."
else
    log "Step 1 (splurge, ESC, shared) -> Target_AggMPCX_LiquWealth/Result_AllTarget_ESC.txt"
    (
        cd Target_AggMPCX_LiquWealth
        run_or_echo "$PY" Estimation_BetaNablaSplurge.py
    )
fi

# ---- Step 2: (beta, nabla) per world ----
_world_target() {  # echo the canonical DiscFacEstim path for a world
    if [[ "$1" == default ]]; then
        echo "Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt"
    else
        echo "Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC_ascorrected.txt"
    fi
}

if [[ "$PARALLEL_WORLDS" -eq 1 && "${#WORLDS[@]}" -gt 1 ]]; then
    log "----------------------------------------------------------------"
    log "Step 2 (beta,nabla) — ${#WORLDS[@]} worlds CONCURRENT (~$(( ${#WORLDS[@]} * 3 )) edType procs); logs in overnight_run_logs/"
    pids=(); pworlds=()
    for w in "${WORLDS[@]}"; do
        log "  -> world=$w (perm=$([[ "$w" == default ]] && echo on || echo off)) -> $(_world_target "$w")"
        if [[ "$DO_RUN" -eq 1 ]]; then
            mkdir -p overnight_run_logs
            ( cd FromPandemicCode && HAFISCAL_WORLD="$w" "$PY" run_phase2_parallel.py ) \
                > "overnight_run_logs/stageA_step2_${w}.log" 2>&1 &
            pids+=("$!"); pworlds+=("$w")
            log "    + launched pid $! -> overnight_run_logs/stageA_step2_${w}.log"
        else
            log "    + (dry-run) HAFISCAL_WORLD=$w $PY run_phase2_parallel.py  (would background)"
        fi
    done
    step2_fail=0
    for i in "${!pids[@]}"; do
        if wait "${pids[$i]}"; then
            log "  world=${pworlds[$i]} Step 2 OK"
            emit_provenance "${pworlds[$i]}"
        else
            log "  world=${pworlds[$i]} Step 2 FAILED (see overnight_run_logs/stageA_step2_${pworlds[$i]}.log)"
            step2_fail=1
        fi
    done
    [[ "$step2_fail" -eq 0 ]] || { log "Step 2 had failures; aborting."; exit 1; }
else
    for w in "${WORLDS[@]}"; do
        log "----------------------------------------------------------------"
        log "Step 2 (beta,nabla) — world=$w (HAFISCAL_PERM_DURING_UNEMP=$([[ "$w" == default ]] && echo on || echo off))"
        log "  -> $(_world_target "$w")"
        (
            cd FromPandemicCode
            HAFISCAL_WORLD="$w" run_or_echo "$PY" run_phase2_parallel.py
        )
        emit_provenance "$w"
    done
fi

log "================================================================"
if [[ "$DO_RUN" -eq 1 ]]; then
    log "DONE. Next: verify default@1e-3 vs the existing betas; wire as-corrected loading;"
    log "      then Q4 phase 2 (delete HAFISCAL_QE_FIDELITY). See the run spec §6."
else
    log "DRY-RUN complete. Re-run with --run to execute (MULTI-DAY)."
fi
log "================================================================"
