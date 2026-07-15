#!/usr/bin/env bash
#
# stageB_leg.sh — run ONE world's Stage-B AD-OFF smoke ladder on THIS machine in
# an EPHEMERAL git worktree, then publish a pass/fail status report + provenance
# to a per-machine leg branch on the remote. ZERO impact on your main checkout.
#
# Stage B = the welfare-6 / policy pipeline. This runs the cheap->expensive smoke
# ladder HS_Only -> Reduced_Run -> Baseline, AD OFF (8 non-AD scenarios), gated:
# it escalates to the next rung only if the current rung PASSES (runbook §5).
# It is a pipeline VALIDATION, not a QE-number production run (AD-off does not
# write welfare6.tex — that is expected). Stage B reads the Stage-A betas already
# promoted on the integration branch for both worlds.
#
# Companion: stageB_integrate.sh (pass/fail matrix across both worlds),
# stageB_drive.sh (ssh orchestrator). Runbook:
#   plans/20260614_stageB-two-machine-STREAMLINED-RUNBOOK.md
# Underlying spec: plans/20260614_overnight-two-worlds-AD-off-validation-run.md
#
# Usage:
#   nohup bash stageB_leg.sh --world default      > /tmp/stageB_leg.out 2>&1 &
#   nohup bash stageB_leg.sh --world as-corrected > /tmp/stageB_leg.out 2>&1 &
#
#   --world default|as-corrected   REQUIRED.
#   --machine LABEL                Host label in the leg branch (default: hostname -s).
#   --rungs A,B,C                  Ladder rungs (default: HS_Only,Reduced_Run,Baseline).
#   --scenarios LIST               Comma scenario subset (default: the 8 non-AD scenarios).
#   --smoke                        QUICK plumbing test: HS_Only rung + base,recession only
#                                  (overridable by an explicit --rungs / --scenarios). Use
#                                  this to validate the whole flow end-to-end in minutes.
#   --base-branch NAME             Integration branch (default: $STAGEA_BASE_BRANCH or TM-vs-MC).
#   --dry-run                      Create the worktree + print the plan; no compute, no push.
#   --keep-worktree                Keep the worktree (and its pickles) for inspection.
#   -- <args>                      Extra args passed through to run_welfare6_parallel.py.
#
set -eo pipefail

BASE_BRANCH="${STAGEA_BASE_BRANCH:-0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC}"
REMOTE="${STAGEA_REMOTE:-origin}"

DEFAULT_NONAD="base,Check,UI,TaxCut,recession,recessionUI,recessionCheck,recessionTaxCut"
DEFAULT_RUNGS="HS_Only,Reduced_Run,Baseline"

WORLD=""
MACHINE=""
RUNGS="$DEFAULT_RUNGS"
RUNGS_SET=0
SCENARIOS=""        # empty => DEFAULT_NONAD (or the smoke default if --smoke)
SMOKE=0
DRYRUN=0
KEEP_WT=0
EXTRA=()

die()  { printf 'stageB_leg: ERROR: %s\n' "$*" >&2; exit 1; }
log()  { printf '[stageB_leg] %s\n' "$*"; }
usage() { sed -n '2,38p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --world)        shift; [[ $# -gt 0 ]] || die "--world needs an argument"; WORLD="$1"; shift ;;
        --machine)      shift; [[ $# -gt 0 ]] || die "--machine needs an argument"; MACHINE="$1"; shift ;;
        --rungs)        shift; [[ $# -gt 0 ]] || die "--rungs needs an argument"; RUNGS="$1"; RUNGS_SET=1; shift ;;
        --scenarios)    shift; [[ $# -gt 0 ]] || die "--scenarios needs an argument"; SCENARIOS="$1"; shift ;;
        --smoke)        SMOKE=1; shift ;;
        --base-branch)  shift; [[ $# -gt 0 ]] || die "--base-branch needs an argument"; BASE_BRANCH="$1"; shift ;;
        --dry-run)      DRYRUN=1; shift ;;
        --keep-worktree) KEEP_WT=1; shift ;;
        --)             shift; while [[ $# -gt 0 ]]; do EXTRA+=("$1"); shift; done ;;
        -h|--help)      usage; exit 0 ;;
        *)              die "unknown argument: $1 (see --help)" ;;
    esac
done

[[ -n "$WORLD" ]] || die "--world is required (default | as-corrected)"
case "$WORLD" in
    default)      TOKEN="default" ;;
    as-corrected) TOKEN="ascorrected" ;;
    *) die "--world must be 'default' or 'as-corrected' (got '$WORLD')" ;;
esac
[[ -n "$MACHINE" ]] || MACHINE="$( (hostname -s 2>/dev/null || hostname 2>/dev/null || echo host) | tr '[:upper:]' '[:lower:]' )"
LEG="${BASE_BRANCH}_${MACHINE}_${TOKEN}_stageB"

# --smoke: cheapest possible plumbing test; explicit --rungs / --scenarios still win.
if [[ "$SMOKE" -eq 1 ]]; then
    [[ "$RUNGS_SET" -eq 1 ]] || RUNGS="HS_Only"
    [[ -n "$SCENARIOS" ]]    || SCENARIOS="base,recession"
fi

# Scenario set + dynamic pickle gate (NSCEN), so a subset never false-fails the gate.
NONAD="${SCENARIOS:-$DEFAULT_NONAD}"
PICKLES="$(printf '%s' "$NONAD" | tr ',' ' ')"
NSCEN="$(printf '%s\n' "$PICKLES" | wc -w | tr -d ' ')"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)" || die "not inside a git repo"

VENV_PY=""
if [[ -n "${PYTHON:-}" ]]; then VENV_PY="$PYTHON"; else
    for p in "$MAIN"/.venv/bin/python "$MAIN"/.venv-*/bin/python; do [[ -x "$p" ]] && { VENV_PY="$p"; break; }; done
fi
[[ -n "$VENV_PY" ]] || { VENV_PY="python"; log "WARNING: no project venv under $MAIN/.venv*; using \$PATH python. Set PYTHON=... if wrong."; }

# Use the true VM core count (`nproc --all`), NOT bare `nproc`: GNU nproc honors an
# inherited OMP_NUM_THREADS cap and would silently throttle concurrency (e.g. 3 on a
# 32-thread box when launched from a shell that exported OMP_NUM_THREADS=3).
NPROC="$( (command -v nproc >/dev/null 2>&1 && nproc --all) || sysctl -n hw.ncpu 2>/dev/null || echo 1 )"
C_CHEAP=$(( NPROC < 8 ? NPROC : 8 ))
C_BASE=$(( NPROC < 4 ? NPROC : 4 ))
[[ "$C_CHEAP" -ge 1 ]] || C_CHEAP=1
[[ "$C_BASE"  -ge 1 ]] || C_BASE=1
# Per-worker BLAS cap so the C parallel scenario processes don't oversubscribe the box.
BLAS_T=$(( NPROC / C_CHEAP > 0 ? NPROC / C_CHEAP : 1 ))
export OMP_NUM_THREADS="$BLAS_T" OPENBLAS_NUM_THREADS="$BLAS_T" MKL_NUM_THREADS="$BLAS_T" NUMEXPR_NUM_THREADS="$BLAS_T"

log "================================================================"
log "world        : $WORLD  (perm_during_unemp=$([[ "$WORLD" == default ]] && echo on || echo off))"
log "machine      : $MACHINE"
log "ladder       : $RUNGS   (AD OFF; ${NSCEN} scenarios: $NONAD)$([[ "$SMOKE" -eq 1 ]] && echo '   [SMOKE]')"
log "base branch  : $BASE_BRANCH   (remote: $REMOTE)"
log "leg branch   : $LEG  (force-pushed on success)"
log "python       : $VENV_PY"
log "cores        : nproc(all)=$NPROC  C_cheap=$C_CHEAP  C_baseline=$C_BASE  BLAS_threads=$BLAS_T  (--max-gpu-slots 0)"
log "mode         : $([[ "$DRYRUN" -eq 1 ]] && echo 'DRY-RUN (no compute, no push)' || echo 'RUN')"
log "================================================================"

log "fetching $REMOTE/$BASE_BRANCH ..."
git -C "$MAIN" fetch "$REMOTE" "$BASE_BRANCH"

WT="$(dirname "$MAIN")/_stageB_leg_${MACHINE}_${TOKEN}"
TMPBR="_stageB_wt_${MACHINE}_${TOKEN}_$$"
cleanup() {
    if [[ "$KEEP_WT" -eq 1 ]]; then log "keeping worktree at $WT (--keep-worktree)"; return; fi
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
if [[ "$VENV_PY" != "python" ]]; then
    ln -snf "$(cd "$(dirname "$VENV_PY")/.." && pwd)" "$WT/.venv" 2>/dev/null || true
fi

# Stage-A gate: the world's betas must exist on the branch (Stage B reads them).
SUF="$([[ "$WORLD" == default ]] && echo _ESC || echo _ESC_ascorrected)"
BETAS="$WT/Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01${SUF}.txt"
[[ -f "$BETAS" ]] || log "WARNING: $BETAS not found on $BASE_BRANCH — Stage B may warn/fall back (run Stage A first)."

STATUS_REL="Code/HA-Models/stageB_two_machine_validation/status_${MACHINE}_${WORLD}.md"
LOGDIR_REL="Code/HA-Models/stageB_two_machine_validation/logs"
mkdir -p "$WT/$LOGDIR_REL"

# IFS-split the rung list
OLD_IFS="$IFS"; IFS=','; read -r -a RUNG_ARR <<< "$RUNGS"; IFS="$OLD_IFS"

if [[ "$DRYRUN" -eq 1 ]]; then
    log "DRY-RUN plan (per rung): HAFISCAL_WORLD=$WORLD $VENV_PY run_welfare6_parallel.py \\"
    for r in "${RUNG_ARR[@]}"; do
        cc=$([[ "$r" == Baseline ]] && echo "$C_BASE" || echo "$C_CHEAP")
        log "    --parametrization $r --scenarios $NONAD --max-gpu-slots 0 --max-parallel $cc --max-cpu-slots $cc --out-dir welfare6_${WORLD}_${r} --table-dir Tables/${WORLD}_${r}"
    done
    log "DRY-RUN: skipping compute + publish."
    [[ "$KEEP_WT" -eq 1 ]] && trap - EXIT
    exit 0
fi

cd "$WT/Code/HA-Models/FromPandemicCode"

RUNG_MSG=""
run_rung() {  # $1=param $2=C  -> 0 pass / 1 fail; sets RUNG_MSG
    local param="$1" C="$2"
    local outdir="welfare6_${WORLD}_${param}"
    local tabdir="Tables/${WORLD}_${param}"
    local rlog="../stageB_two_machine_validation/logs/stageB_${WORLD}_${param}.log"
    local t0; t0=$(date +%s)
    set +e
    HAFISCAL_WORLD="$WORLD" "$VENV_PY" run_welfare6_parallel.py \
        --parametrization "$param" --scenarios "$NONAD" \
        --max-gpu-slots 0 --max-parallel "$C" --max-cpu-slots "$C" \
        --out-dir "$outdir" --table-dir "$tabdir" "${EXTRA[@]}" \
        > "$rlog" 2>&1
    local rc=$?
    set -e
    local dt=$(( $(date +%s) - t0 ))
    local have=0 miss=0 p
    for p in $PICKLES; do
        if [[ -f "$outdir/$p.pkl" ]]; then have=$((have+1)); else miss=$((miss+1)); fi
    done
    local tb=0
    if ls welfare6_parallel_logs/"$param"/*.log >/dev/null 2>&1; then
        grep -lq "Traceback" welfare6_parallel_logs/"$param"/*.log 2>/dev/null && tb=1
    fi
    local failrc=0
    grep -q "FAIL rc=" "$rlog" 2>/dev/null && failrc=1
    if [[ "$rc" -eq 0 && "$miss" -eq 0 && "$tb" -eq 0 && "$failrc" -eq 0 ]]; then
        RUNG_MSG="PASS  ($((dt/60))m$((dt%60))s, ${have}/${NSCEN} pickles)"
        return 0
    fi
    RUNG_MSG="FAIL  (rc=$rc, pickles ${have}/${NSCEN}, traceback=$tb, failrc=$failrc, $((dt/60))m$((dt%60))s) — see $(basename "$rlog")"
    return 1
}

# run the ladder, gated
LADDER_OK=1
declare -a REPORT_LINES
START_ALL=$(date +%s)
for param in "${RUNG_ARR[@]}"; do
    cc=$([[ "$param" == Baseline ]] && echo "$C_BASE" || echo "$C_CHEAP")
    log "---- rung $param (C=$cc) START ----"
    if run_rung "$param" "$cc"; then
        log "rung $param: $RUNG_MSG"
        REPORT_LINES+=("  $(printf '%-12s' "$param") : $RUNG_MSG")
    else
        log "rung $param: $RUNG_MSG  -> STOPPING ladder (no escalation)"
        REPORT_LINES+=("  $(printf '%-12s' "$param") : $RUNG_MSG")
        LADDER_OK=0
        break
    fi
done
ELAPSED_ALL=$(( $(date +%s) - START_ALL ))

# write the status report
{
    echo "# Stage B (AD-off smoke) — $MACHINE / $WORLD$([[ "$SMOKE" -eq 1 ]] && echo '  [--smoke]')"
    echo
    echo "- generated  : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "- base       : $BASE_BRANCH @ $(git -C "$WT" rev-parse --short=8 "$REMOTE/$BASE_BRANCH")"
    echo "- world      : $WORLD (perm_during_unemp=$([[ "$WORLD" == default ]] && echo on || echo off))"
    echo "- mode       : $([[ "$SMOKE" -eq 1 ]] && echo 'SMOKE (quick plumbing test — NOT a full ladder)' || echo 'full AD-off ladder')"
    echo "- cores      : nproc(all)=$NPROC  C_cheap=$C_CHEAP  C_baseline=$C_BASE  BLAS_threads=$BLAS_T"
    echo "- rungs      : $RUNGS"
    echo "- scenarios  : $NONAD (${NSCEN}; AD OFF)"
    echo "- total wall : $((ELAPSED_ALL/60))m$((ELAPSED_ALL%60))s"
    echo "- ladder     : $([[ "$LADDER_OK" -eq 1 ]] && echo 'ALL RUNGS PASSED' || echo 'STOPPED at a failing rung')"
    echo
    echo "## rungs"
    for line in "${REPORT_LINES[@]}"; do echo "$line"; done
    echo
    echo "_Note: AD-off does not write welfare6.tex (needs all 12 scenarios); 'Missing pickles: [recession_AD, ...]' is expected, not a failure._"
} > "$WT/$STATUS_REL"

log "status report -> $WT/$STATUS_REL"
cat "$WT/$STATUS_REL" | sed 's/^/    /'

# locate provenance emitted by run_welfare6_parallel.py (if any)
PROV="$(ls -t "$WT"/Code/HA-Models/Results/RUN_*.prov.json 2>/dev/null | head -1 || true)"
RUNID=""
[[ -n "$PROV" ]] && RUNID="$(basename "$PROV" .prov.json | sed 's/^RUN_//')"

# ----------------------------------------------------------------------------
# publish: status report + per-rung driver logs + provenance (NOT pickles)
# ----------------------------------------------------------------------------
cd "$WT"
ADD=("$STATUS_REL")
while IFS= read -r f; do [[ -n "$f" ]] && ADD+=("$f"); done < <(cd "$WT" && ls "$LOGDIR_REL"/stageB_${WORLD}_*.log 2>/dev/null || true)
if [[ -n "$PROV" ]]; then
    ADD+=("Code/HA-Models/Results/$(basename "$PROV")")
    [[ -f "reproduce/run-manifests/provrun_${RUNID}.json" ]]           && ADD+=("reproduce/run-manifests/provrun_${RUNID}.json")
    [[ -f "reproduce/run-manifests/provrun_${RUNID}_pip_freeze.txt" ]] && ADD+=("reproduce/run-manifests/provrun_${RUNID}_pip_freeze.txt")
fi

log "publishing ${#ADD[@]} file(s) to $LEG"
git -C "$WT" add -f "${ADD[@]}"
COMMIT_MSG="$(cat <<EOF
Stage B AD-off smoke status + provenance ($MACHINE / $WORLD)

world   : $WORLD
machine : $MACHINE
ladder  : $RUNGS
result  : $([[ "$LADDER_OK" -eq 1 ]] && echo 'all rungs passed' || echo 'stopped at a failing rung')
run_id  : ${RUNID:-none}
base    : $BASE_BRANCH @ $(git -C "$WT" rev-parse --short=8 "$REMOTE/$BASE_BRANCH")

Validation smoke (AD off) produced by stageB_leg.sh in an ephemeral worktree.
Pickles/tables are NOT published (large / incomplete for AD-off); the status
report + driver logs + provenance are. Aggregate via stageB_integrate.sh.
EOF
)"
git -C "$WT" -c user.useConfigOnly=false commit -m "$COMMIT_MSG" >/dev/null
log "committed $(git -C "$WT" rev-parse --short=8 HEAD) on $TMPBR"
log "pushing -> $REMOTE/$LEG (force; per-machine scratch leg)"
git -C "$WT" push --force "$REMOTE" "HEAD:$LEG"

log "================================================================"
log "DONE. Stage-B leg published: $REMOTE/$LEG  (ladder $([[ "$LADDER_OK" -eq 1 ]] && echo PASSED || echo STOPPED))"
log "Aggregate both worlds with:  bash Code/HA-Models/stageB_integrate.sh"
log "================================================================"
[[ "$LADDER_OK" -eq 1 ]] || exit 2
