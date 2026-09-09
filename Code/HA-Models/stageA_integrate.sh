#!/usr/bin/env bash
#
# stageA_integrate.sh — the OTHER half of the streamlined two-machine workflow.
# Run this ONCE, on either machine, after both machines have published their
# legs with stageA_leg.sh. It works entirely in an EPHEMERAL worktree on the
# integration branch (zero impact on your main checkout):
#
#   1. fetch every per-machine leg branch (${BASE}_<machine>_<world>),
#   2. pull each world's candidate + provenance into a clean worktree,
#   3. print the cross-world / cross-baseline comparison table (the human gate),
#   4. with --promote: copy candidate -> canonical for each world, commit one
#      consolidation commit (candidates + provenance travel force-added), and
#      push the integration branch.
#
# Without --promote it STOPS after the comparison so you can eyeball it
# (default β-shift surprises like the BUG-036 Dropout basin are why this gate
# exists). Re-run with --promote once the numbers look sensible.
#
# Usage:
#   bash stageA_integrate.sh                 # fetch legs + show comparison (no writes)
#   bash stageA_integrate.sh --promote       # ...then promote both worlds + push
#   bash stageA_integrate.sh --legs A,B      # only integrate these explicit leg branches
#
#   --promote            Promote candidate->canonical and push $BASE_BRANCH.
#   --base-branch NAME   Integration branch (default: $STAGEA_BASE_BRANCH or TM-vs-MC).
#   --legs A,B           Comma-separated leg branch names (default: auto-discover
#                        all ${BASE}_*_* remote branches).
#   --threshold PCT      Flag |Δβ| above this %% vs the existing canonical (default 0.5).
#   --keep-worktree      Do not remove the worktree at the end (debug).
#   -h | --help
#
set -eo pipefail

BASE_BRANCH="${STAGEA_BASE_BRANCH:-0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC}"
REMOTE="${STAGEA_REMOTE:-origin}"
PROMOTE=0
LEGS_ARG=""
THRESHOLD="0.5"
KEEP_WT=0

die()  { printf 'stageA_integrate: ERROR: %s\n' "$*" >&2; exit 1; }
log()  { printf '[stageA_integrate] %s\n' "$*"; }
usage() { sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --promote)      PROMOTE=1; shift ;;
        --base-branch)  shift; [[ $# -gt 0 ]] || die "--base-branch needs an argument"; BASE_BRANCH="$1"; shift ;;
        --legs)         shift; [[ $# -gt 0 ]] || die "--legs needs an argument"; LEGS_ARG="$1"; shift ;;
        --threshold)    shift; [[ $# -gt 0 ]] || die "--threshold needs an argument"; THRESHOLD="$1"; shift ;;
        --keep-worktree) KEEP_WT=1; shift ;;
        -h|--help)      usage; exit 0 ;;
        *)              die "unknown argument: $1 (see --help)" ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)" || die "not inside a git repo"

VENV_PY=""
if [[ -n "${PYTHON:-}" ]]; then VENV_PY="$PYTHON"; else
    for p in "$MAIN"/.venv/bin/python "$MAIN"/.venv-*/bin/python; do [[ -x "$p" ]] && { VENV_PY="$p"; break; }; done
fi
[[ -n "$VENV_PY" ]] || VENV_PY="$(command -v python3 || command -v python || echo python)"

# ----------------------------------------------------------------------------
# fetch + discover legs
# ----------------------------------------------------------------------------
log "fetching $REMOTE (base + leg branches) ..."
git -C "$MAIN" fetch --prune "$REMOTE" >/dev/null 2>&1 || git -C "$MAIN" fetch "$REMOTE"

LEGS=()
if [[ -n "$LEGS_ARG" ]]; then
    IFS=',' read -r -a LEGS <<< "$LEGS_ARG"
else
    while IFS= read -r ref; do
        [[ -n "$ref" ]] || continue
        LEGS+=("${ref#$REMOTE/}")
    done < <(git -C "$MAIN" for-each-ref --format='%(refname:short)' "refs/remotes/$REMOTE/${BASE_BRANCH}_*")
fi
[[ ${#LEGS[@]} -gt 0 ]] || die "no leg branches found matching ${BASE_BRANCH}_*  (run stageA_leg.sh on each machine first, or pass --legs)"

log "integration branch : $BASE_BRANCH"
log "legs discovered    : ${#LEGS[@]}"
for l in "${LEGS[@]}"; do log "    - $l"; done

# ----------------------------------------------------------------------------
# ephemeral worktree on the integration branch
# ----------------------------------------------------------------------------
WT="$(dirname "$MAIN")/_stageA_integrate"
TMPBR="_stageA_integrate_wt_$$"
cleanup() {
    if [[ "$KEEP_WT" -eq 1 ]]; then log "keeping worktree at $WT (--keep-worktree)"; return; fi
    log "removing worktree $WT"
    git -C "$MAIN" worktree remove --force "$WT" >/dev/null 2>&1 || rm -rf "$WT"
    git -C "$MAIN" branch -D "$TMPBR" >/dev/null 2>&1 || true
    git -C "$MAIN" worktree prune >/dev/null 2>&1 || true
}
trap cleanup EXIT

git -C "$MAIN" worktree remove --force "$WT" >/dev/null 2>&1 || true
rm -rf "$WT"
git -C "$MAIN" branch -D "$TMPBR" >/dev/null 2>&1 || true
log "creating worktree $WT @ $REMOTE/$BASE_BRANCH"
git -C "$MAIN" worktree add -b "$TMPBR" "$WT" "$REMOTE/$BASE_BRANCH" >/dev/null

# ----------------------------------------------------------------------------
# pull each leg's candidate + provenance into the worktree; remember world->files
# ----------------------------------------------------------------------------
# parallel arrays (bash 3.2 — no assoc arrays)
W_WORLD=(); W_SUF=(); W_CAND=(); W_CANON=(); W_LEG=()
for leg in "${LEGS[@]}"; do
    rem="${leg#${BASE_BRANCH}_}"
    token="${rem##*_}"
    machine="${rem%_*}"
    case "$token" in
        default)     world="default";      suf="_ESC" ;;
        ascorrected) world="as-corrected"; suf="_ESC_ascorrected" ;;
        *) log "skip leg '$leg' — unrecognized world token '$token'"; continue ;;
    esac

    # Pull ONLY this leg's _candidate + provenance artifacts — NEVER the canonical
    # (non-candidate) result files. A leg may be an ancestor of the base (older
    # canonical); pulling its canonical would clobber the base baseline and give a
    # false comparison. The canonical for the comparison always comes from base.
    # --diff-filter=d drops Deletions so every path is retrievable from the leg.
    mapfile_files=()
    while IFS= read -r f; do [[ -n "$f" ]] && mapfile_files+=("$f"); done < <(
        git -C "$WT" diff --name-only --diff-filter=d "$REMOTE/$BASE_BRANCH" "$REMOTE/$leg" -- \
            'Code/HA-Models/Results/*_candidate.txt' \
            'Code/HA-Models/Results/RUN_*.prov.json' \
            'reproduce/run-manifests/provrun_*' 2>/dev/null
    )
    [[ ${#mapfile_files[@]} -gt 0 ]] || { log "leg '$leg' (world=$world): no result/provenance files vs base — skipping"; continue; }

    log "leg '$leg' (machine=$machine, world=$world): pulling ${#mapfile_files[@]} file(s)"
    git -C "$WT" checkout "$REMOTE/$leg" -- "${mapfile_files[@]}"

    cand="$(ls -t "$WT"/Code/HA-Models/Results/DiscFacEstim_CRRA_*_R_*${suf}_candidate.txt 2>/dev/null | head -1 || true)"
    [[ -n "$cand" ]] || { log "  WARNING: leg '$leg' produced no DiscFacEstim*${suf}_candidate.txt; skipping world=$world"; continue; }
    canon="${cand/_candidate.txt/.txt}"

    W_WORLD+=("$world"); W_SUF+=("$suf"); W_CAND+=("$cand"); W_CANON+=("$canon"); W_LEG+=("$leg")
done

[[ ${#W_WORLD[@]} -gt 0 ]] || die "no NEW candidates found on any leg vs $BASE_BRANCH — either the legs haven't run yet, or they were already integrated/promoted into the base."

# ----------------------------------------------------------------------------
# comparison table (read-only; the human gate)
# ----------------------------------------------------------------------------
echo
echo "================================================================================"
echo " Stage-A comparison  (existing canonical on $BASE_BRANCH  vs  each leg candidate)"
echo "================================================================================"
for i in "${!W_WORLD[@]}"; do
    "$VENV_PY" - "${W_WORLD[$i]}" "${W_CANON[$i]}" "${W_CAND[$i]}" "$THRESHOLD" <<'PY'
import re, sys
world, canon, cand, thr = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])

def betas(path):
    out = {}
    try:
        txt = open(path).read()
    except OSError:
        return None
    for m in re.finditer(r"'EducationGroup'\s*:\s*(\d+).*?'beta'\s*:\s*([0-9.eE+-]+)", txt):
        out[int(m.group(1))] = float(m.group(2))
    return out

names = {0: "Dropout", 1: "HS", 2: "College"}
old = betas(canon)
new = betas(cand)
print()
print(f"  world = {world}")
print(f"    canonical : {canon}  {'(none yet — NEW world)' if old is None else ''}")
print(f"    candidate : {cand}")
if not new:
    print("    !! could not parse candidate betas")
    sys.exit(0)
print(f"    {'cohort':<9} {'canonical β':>13} {'candidate β':>13} {'Δβ %':>9}")
flagged = []
for g in sorted(new):
    nb = new[g]
    ob = (old or {}).get(g)
    if ob is None:
        print(f"    {names.get(g,g):<9} {'(none)':>13} {nb:>13.6f} {'NEW':>9}")
    else:
        pct = 100.0 * (nb - ob) / ob if ob else float('inf')
        mark = "  <== FLAG" if abs(pct) > thr else ""
        print(f"    {names.get(g,g):<9} {ob:>13.6f} {nb:>13.6f} {pct:>8.2f}%{mark}")
        if abs(pct) > thr:
            flagged.append((names.get(g, g), ob, nb, pct))
if flagged:
    print(f"    NOTE: {len(flagged)} cohort(s) move > {thr}% vs current canonical — confirm this is expected before promoting.")
PY
done
echo
echo "--------------------------------------------------------------------------------"

if [[ "$PROMOTE" -eq 0 ]]; then
    echo
    log "COMPARE-ONLY (no writes). Review the table above."
    log "If the numbers look sensible, promote with:"
    log "    bash Code/HA-Models/stageA_integrate.sh --promote"
    exit 0
fi

# ----------------------------------------------------------------------------
# --promote: candidate -> canonical, force-add travelling artifacts, commit, push
# ----------------------------------------------------------------------------
echo
log "PROMOTE: writing canonical baselines for ${#W_WORLD[@]} world(s)"
SUMMARY=""
for i in "${!W_WORLD[@]}"; do
    cand="${W_CAND[$i]}"; canon="${W_CANON[$i]}"; world="${W_WORLD[$i]}"
    log "  $world: $(basename "$cand")  ->  $(basename "$canon")"
    cp "$cand" "$canon"
    rel_canon="${canon#$WT/}"
    rel_cand="${cand#$WT/}"
    git -C "$WT" add "$rel_canon"
    git -C "$WT" add -f "$rel_cand"
    SUMMARY="${SUMMARY}  - ${world}: $(basename "$canon")\n"
done

# force-add everything the legs brought in (AllResults candidates + provenance),
# so the canonical baselines travel with their full provenance. Quote the
# patterns so git (not the shell) globs them relative to the worktree.
git -C "$WT" add -f 'Code/HA-Models/Results/AllResults_CRRA_*_R_*_candidate.txt' 2>/dev/null || true
git -C "$WT" add -f 'Code/HA-Models/Results/RUN_*.prov.json' 2>/dev/null || true
git -C "$WT" add -f 'reproduce/run-manifests/provrun_*.json' 'reproduce/run-manifests/provrun_*_pip_freeze.txt' 2>/dev/null || true

if git -C "$WT" diff --cached --quiet; then
    die "nothing staged to promote (already up to date?)"
fi

echo
log "staged for promotion:"
git -C "$WT" diff --cached --name-status | sed 's/^/    /'

COMMIT_MSG="$(printf 'Promote Stage-A baselines from two-machine legs\n\nWorlds promoted (candidate -> canonical):\n%b\nLegs integrated:\n%s\n\nProduced by stageA_integrate.sh --promote. Candidate files + provenance\nsidecars/manifests are force-added so the canonical baselines travel with\ntheir full run provenance. Review the comparison table in the run log.\n' \
    "$SUMMARY" "$(printf '  - %s\n' "${W_LEG[@]}")")"

git -C "$WT" -c user.useConfigOnly=false commit -m "$COMMIT_MSG" >/dev/null
NEWSHA="$(git -C "$WT" rev-parse --short=8 HEAD)"
log "committed $NEWSHA on $TMPBR"

log "pushing -> $REMOTE/$BASE_BRANCH"
git -C "$WT" push "$REMOTE" "HEAD:$BASE_BRANCH"

log "================================================================"
log "DONE. Promoted both worlds; $REMOTE/$BASE_BRANCH advanced to $NEWSHA."
log "Pull it into your main checkout when convenient:"
log "    git fetch $REMOTE && git merge --ff-only $REMOTE/$BASE_BRANCH"
log "================================================================"
