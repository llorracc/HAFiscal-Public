#!/usr/bin/env bash
#
# stageA_leg.sh — run ONE world's Stage-A (β,∇) estimation on THIS machine in an
# EPHEMERAL git worktree, then auto-publish the candidate + provenance to a
# per-machine "leg" branch on the remote. ZERO impact on your main checkout
# (no branch switching, no dirty-tree hazards, no manual `git add -f`).
#
# This is half of the streamlined two-machine workflow; the other half is
# stageA_integrate.sh (merge both legs + promote). See the runbook:
#   plans/20260614_stageA-two-machine-STREAMLINED-RUNBOOK.md
#
# Usage:
#   bash stageA_leg.sh --world default        # e.g. on econ-mw
#   bash stageA_leg.sh --world as-corrected   # e.g. on ccarroll-m5
#
#   --world default|as-corrected   REQUIRED. Which world to estimate.
#   --machine LABEL                 Friendly host label used in the leg branch
#                                   name (default: lowercased `hostname -s`,
#                                   e.g. econ-mw, ccarroll-m5).
#   --base-branch NAME              Integration branch to fork from / push under
#                                   (default: $STAGEA_BASE_BRANCH or the
#                                   TM-vs-MC branch).
#   --run-splurge                   Recompute Step-1 splurge (default: reuse the
#                                   tracked shared splurge — it is perm-independent).
#   --dry-run                       Print every action; create the worktree and
#                                   show the launch command, but do NOT estimate
#                                   or push. (Worktree is still torn down.)
#   --keep-worktree                 Do not remove the worktree at the end (debug).
#   -h | --help
#
# Long-running: background the whole script and tail the log, e.g.
#   nohup bash stageA_leg.sh --world default > /tmp/stageA_leg.out 2>&1 &
#
set -eo pipefail

# ----------------------------------------------------------------------------
# config (env-overridable)
# ----------------------------------------------------------------------------
BASE_BRANCH="${STAGEA_BASE_BRANCH:-0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC}"
REMOTE="${STAGEA_REMOTE:-origin}"

WORLD=""
MACHINE=""
RUN_SPLURGE=0
DRYRUN=0
KEEP_WT=0
EXTRA=()

die()  { printf 'stageA_leg: ERROR: %s\n' "$*" >&2; exit 1; }
log()  { printf '[stageA_leg] %s\n' "$*"; }

usage() { sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; }

# ----------------------------------------------------------------------------
# args
# ----------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --world)        shift; [[ $# -gt 0 ]] || die "--world needs an argument"; WORLD="$1"; shift ;;
        --machine)      shift; [[ $# -gt 0 ]] || die "--machine needs an argument"; MACHINE="$1"; shift ;;
        --base-branch)  shift; [[ $# -gt 0 ]] || die "--base-branch needs an argument"; BASE_BRANCH="$1"; shift ;;
        --run-splurge)  RUN_SPLURGE=1; shift ;;
        --dry-run)      DRYRUN=1; shift ;;
        --keep-worktree) KEEP_WT=1; shift ;;
        --)             shift; while [[ $# -gt 0 ]]; do EXTRA+=("$1"); shift; done ;;
        -h|--help)      usage; exit 0 ;;
        *)              die "unknown argument: $1 (see --help)" ;;
    esac
done

[[ -n "$WORLD" ]] || die "--world is required (default | as-corrected)"
case "$WORLD" in
    default)      TOKEN="default";     SUF="_ESC" ;;
    as-corrected) TOKEN="ascorrected"; SUF="_ESC_ascorrected" ;;
    *) die "--world must be 'default' or 'as-corrected' (got '$WORLD')" ;;
esac

if [[ -z "$MACHINE" ]]; then
    MACHINE="$( (hostname -s 2>/dev/null || hostname 2>/dev/null || echo host) | tr '[:upper:]' '[:lower:]' )"
fi
LEG="${BASE_BRANCH}_${MACHINE}_${TOKEN}"

# ----------------------------------------------------------------------------
# locate the main checkout + a usable venv python
# ----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)" || die "not inside a git repo"

VENV_PY=""
if [[ -n "${PYTHON:-}" ]]; then
    VENV_PY="$PYTHON"
else
    for p in "$MAIN"/.venv/bin/python "$MAIN"/.venv-*/bin/python; do
        [[ -x "$p" ]] && { VENV_PY="$p"; break; }
    done
fi
[[ -n "$VENV_PY" ]] || { VENV_PY="python"; log "WARNING: no project venv found under $MAIN/.venv*; falling back to '\$PATH python'. Set PYTHON=... if wrong."; }

# ----------------------------------------------------------------------------
# core-maximization env (runbook §0 — identical, result-affecting knobs)
# ----------------------------------------------------------------------------
export HAFISCAL_PARALLEL_MULTISTART=1
export HAFISCAL_NUM_STARTS=4
# OMP-clean but affinity-AWARE core count: bare `nproc` honors an inherited
# OMP_NUM_THREADS cap (would throttle to e.g. 3 on a 32-thread box), so strip
# the OMP vars for the probe — but do NOT use `nproc --all`, which also
# ignores the cgroup cpuset: under SLURM (Rockfish) or taskset that reads the
# whole node instead of the allocation and oversubscribes the grant.
NPROC="$( (command -v nproc >/dev/null 2>&1 && env -u OMP_NUM_THREADS -u OMP_THREAD_LIMIT nproc) || sysctl -n hw.ncpu 2>/dev/null || echo 1 )"
BLAS_T=$(( NPROC/9 > 0 ? NPROC/9 : 1 ))
export OMP_NUM_THREADS="$BLAS_T" OPENBLAS_NUM_THREADS="$BLAS_T" MKL_NUM_THREADS="$BLAS_T"
export VECLIB_MAXIMUM_THREADS="$BLAS_T" NUMEXPR_NUM_THREADS="$BLAS_T"

log "================================================================"
log "world        : $WORLD  (perm_during_unemp=$([[ "$WORLD" == default ]] && echo on || echo off))"
log "machine      : $MACHINE"
log "base branch  : $BASE_BRANCH   (remote: $REMOTE)"
log "leg branch   : $LEG  (force-pushed on success)"
log "python       : $VENV_PY"
log "cores        : nproc=$NPROC  BLAS_threads=$BLAS_T  multistart=4"
log "splurge      : $([[ "$RUN_SPLURGE" -eq 1 ]] && echo 'recompute (--run-splurge)' || echo 'reuse tracked shared splurge')"
log "mode         : $([[ "$DRYRUN" -eq 1 ]] && echo 'DRY-RUN (no estimate, no push)' || echo 'RUN')"
log "================================================================"

# ----------------------------------------------------------------------------
# fetch + create an ephemeral worktree on a THROWAWAY local branch forked from
# the up-to-date remote base. (We push to the canonical leg name afterwards, so
# we never collide with a leg branch that may already be checked out in MAIN.)
# ----------------------------------------------------------------------------
log "fetching $REMOTE/$BASE_BRANCH ..."
git -C "$MAIN" fetch "$REMOTE" "$BASE_BRANCH"

WT="$(dirname "$MAIN")/_stageA_leg_${MACHINE}_${TOKEN}"
TMPBR="_stageA_wt_${MACHINE}_${TOKEN}_$$"

cleanup() {
    if [[ "$KEEP_WT" -eq 1 ]]; then
        log "keeping worktree at $WT (--keep-worktree)"
        return
    fi
    log "removing worktree $WT"
    git -C "$MAIN" worktree remove --force "$WT" >/dev/null 2>&1 || rm -rf "$WT"
    git -C "$MAIN" branch -D "$TMPBR" >/dev/null 2>&1 || true
    git -C "$MAIN" worktree prune >/dev/null 2>&1 || true
}
trap cleanup EXIT

log "creating ephemeral worktree at $WT (branch $TMPBR @ $REMOTE/$BASE_BRANCH)"
git -C "$MAIN" worktree remove --force "$WT" >/dev/null 2>&1 || true
rm -rf "$WT"
git -C "$MAIN" branch -D "$TMPBR" >/dev/null 2>&1 || true
git -C "$MAIN" worktree add -b "$TMPBR" "$WT" "$REMOTE/$BASE_BRANCH" >/dev/null

# convenience: let `source .venv/bin/activate` work inside the worktree too
if [[ "$VENV_PY" != "python" ]]; then
    VENV_ROOT="$(cd "$(dirname "$VENV_PY")/.." && pwd)"
    ln -snf "$VENV_ROOT" "$WT/.venv" 2>/dev/null || true
fi

# ----------------------------------------------------------------------------
# run the estimation inside the worktree
# ----------------------------------------------------------------------------
cd "$WT/Code/HA-Models"
mkdir -p stageA_two_machine_validation/logs
RUNLOG="stageA_two_machine_validation/logs/stageA_${MACHINE}_${WORLD}.log"

LAUNCH=(bash run_ascorrected_calibration.sh --run --world "$WORLD")
[[ "$RUN_SPLURGE" -eq 1 ]] || LAUNCH+=(--skip-splurge)
[[ ${#EXTRA[@]} -eq 0 ]] || LAUNCH+=("${EXTRA[@]}")

log "launch: PYTHON=$VENV_PY ${LAUNCH[*]}"
log "log:    $WT/Code/HA-Models/$RUNLOG"

if [[ "$DRYRUN" -eq 1 ]]; then
    log "DRY-RUN: skipping estimation + publish. Worktree is ready for inspection."
    [[ "$KEEP_WT" -eq 1 ]] && trap - EXIT
    exit 0
fi

START_TS="$(date +%s)"
PYTHON="$VENV_PY" "${LAUNCH[@]}" 2>&1 | tee "$RUNLOG"
ELAPSED=$(( $(date +%s) - START_TS ))
log "estimation finished in $(( ELAPSED/60 )) min $(( ELAPSED%60 )) s"

# ----------------------------------------------------------------------------
# verify the candidate(s) exist (runbook §6)
# ----------------------------------------------------------------------------
CAND="$(ls -t Results/DiscFacEstim_CRRA_*_R_*${SUF}_candidate.txt 2>/dev/null | head -1)"
[[ -n "$CAND" && -s "$CAND" ]] || die "no non-empty candidate matched Results/DiscFacEstim_CRRA_*_R_*${SUF}_candidate.txt — see $RUNLOG"
ALLRES="$(ls -t Results/AllResults_CRRA_*_R_*${SUF}_candidate.txt 2>/dev/null | head -1 || true)"
log "candidate    : $CAND"
[[ -n "$ALLRES" ]] && log "all-results  : $ALLRES" || log "all-results  : (none found; continuing)"

# locate the provenance emitted live by run_ascorrected_calibration.sh
PROV="$(ls -t Results/RUN_*.prov.json 2>/dev/null | head -1 || true)"
RUNID=""
if [[ -n "$PROV" ]]; then
    RUNID="$(basename "$PROV" .prov.json | sed 's/^RUN_//')"
    log "provenance   : $PROV  (run_id=$RUNID)"
else
    log "provenance   : WARNING — no RUN_*.prov.json found; publishing results without a sidecar"
fi

# ----------------------------------------------------------------------------
# publish: force-add the candidate + provenance, commit, push to the leg branch
# ----------------------------------------------------------------------------
cd "$WT"
# Paths are repo-root-relative (the candidate/AllResults/sidecar live under
# Code/HA-Models/Results/; the central manifest under reproduce/run-manifests/).
ADD=("Code/HA-Models/$CAND")
[[ -n "$ALLRES" ]] && ADD+=("Code/HA-Models/$ALLRES")
if [[ -n "$PROV" ]]; then
    ADD+=("Code/HA-Models/$PROV")
    [[ -f "reproduce/run-manifests/provrun_${RUNID}.json" ]]           && ADD+=("reproduce/run-manifests/provrun_${RUNID}.json")
    [[ -f "reproduce/run-manifests/provrun_${RUNID}_pip_freeze.txt" ]] && ADD+=("reproduce/run-manifests/provrun_${RUNID}_pip_freeze.txt")
fi

log "publishing ${#ADD[@]} file(s) to $LEG"
git -C "$WT" add -f "${ADD[@]}"

COMMIT_MSG="$(cat <<EOF
Stage A $WORLD candidate + provenance ($MACHINE)

world         : $WORLD (perm_during_unemp=$([[ "$WORLD" == default ]] && echo on || echo off))
machine       : $MACHINE
run_id        : ${RUNID:-none}
wall clock    : $(( ELAPSED/60 )) min $(( ELAPSED%60 )) s
core-max env  : HAFISCAL_PARALLEL_MULTISTART=1 HAFISCAL_NUM_STARTS=4 BLAS=$BLAS_T
base          : $BASE_BRANCH @ $(git -C "$WT" rev-parse --short=8 "$REMOTE/$BASE_BRANCH")

Produced by stageA_leg.sh in an ephemeral worktree. These are gitignored
_candidate artifacts force-added so they can travel to integration; do NOT
treat the leg branch as canonical. Promote via stageA_integrate.sh --promote.
EOF
)"
git -C "$WT" -c user.useConfigOnly=false commit -m "$COMMIT_MSG" >/dev/null
log "committed $(git -C "$WT" rev-parse --short=8 HEAD) on $TMPBR"

log "pushing -> $REMOTE/$LEG (force; per-machine scratch leg)"
git -C "$WT" push --force "$REMOTE" "HEAD:$LEG"

log "================================================================"
log "DONE. Leg published: $REMOTE/$LEG"
log "Betas:"
sed -n "s/.*'EducationGroup': \([0-9]\).*'beta': \([0-9.]*\).*/  edType \1  beta=\2/p" "$WT/Code/HA-Models/$CAND" || true
log ""
log "Next: on EITHER machine run the integrator once both legs are pushed:"
log "  bash Code/HA-Models/stageA_integrate.sh            # compare only (human gate)"
log "  bash Code/HA-Models/stageA_integrate.sh --promote  # promote + push $BASE_BRANCH"
log "================================================================"
