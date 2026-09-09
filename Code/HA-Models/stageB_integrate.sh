#!/usr/bin/env bash
#
# stageB_integrate.sh — aggregate the Stage-B AD-off smoke results from both
# machines' leg branches into one pass/fail matrix. Read-only: Stage-B smoke is
# a pipeline VALIDATION, so there is nothing to promote — this just fetches each
# leg's status report and prints a combined verdict.
#
# Companion: stageB_leg.sh, stageB_drive.sh. Runbook:
#   plans/20260614_stageB-two-machine-STREAMLINED-RUNBOOK.md
#
# Usage:
#   bash stageB_integrate.sh
#   bash stageB_integrate.sh --legs A,B          # explicit leg branches
#   --base-branch NAME   Integration branch (default: $STAGEA_BASE_BRANCH or TM-vs-MC).
#   --full               Also print each world's full status report.
#   -h | --help
#
set -eo pipefail

BASE_BRANCH="${STAGEA_BASE_BRANCH:-0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC}"
REMOTE="${STAGEA_REMOTE:-origin}"
LEGS_ARG=""
FULL=0

die()  { printf 'stageB_integrate: ERROR: %s\n' "$*" >&2; exit 1; }
log()  { printf '[stageB_integrate] %s\n' "$*"; }
usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --base-branch)  shift; [[ $# -gt 0 ]] || die "--base-branch needs an argument"; BASE_BRANCH="$1"; shift ;;
        --legs)         shift; [[ $# -gt 0 ]] || die "--legs needs an argument"; LEGS_ARG="$1"; shift ;;
        --full)         FULL=1; shift ;;
        -h|--help)      usage; exit 0 ;;
        *)              die "unknown argument: $1 (see --help)" ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)" || die "not inside a git repo"

log "fetching $REMOTE (Stage-B leg branches) ..."
git -C "$MAIN" fetch --prune "$REMOTE" >/dev/null 2>&1 || git -C "$MAIN" fetch "$REMOTE"

LEGS=()
if [[ -n "$LEGS_ARG" ]]; then
    IFS=',' read -r -a LEGS <<< "$LEGS_ARG"
else
    while IFS= read -r ref; do
        [[ -n "$ref" ]] || continue
        LEGS+=("${ref#$REMOTE/}")
    done < <(git -C "$MAIN" for-each-ref --format='%(refname:short)' "refs/remotes/$REMOTE/${BASE_BRANCH}_*_stageB")
fi
[[ ${#LEGS[@]} -gt 0 ]] || die "no Stage-B leg branches found matching ${BASE_BRANCH}_*_stageB (run stageB_leg.sh on each machine first)"

log "Stage-B legs discovered: ${#LEGS[@]}"
for l in "${LEGS[@]}"; do log "    - $l"; done

echo
echo "================================================================================"
echo " Stage-B AD-off smoke — two-machine aggregate (base: $BASE_BRANCH)"
echo "================================================================================"
printf "  %-13s %-13s %-22s %s\n" "world" "machine" "ladder" "leg"
echo "  --------------------------------------------------------------------------------"

ANY_FAIL=0
FULL_REPORTS=""
for leg in "${LEGS[@]}"; do
    rem="${leg%_stageB}"; rem="${rem#${BASE_BRANCH}_}"
    token="${rem##*_}"; machine="${rem%_*}"
    case "$token" in
        default)     world="default" ;;
        ascorrected) world="as-corrected" ;;
        *) log "skip leg '$leg' — unrecognized world token '$token'"; continue ;;
    esac
    # locate + read this leg's status report
    spath="$(git -C "$MAIN" ls-tree -r --name-only "$REMOTE/$leg" -- "Code/HA-Models/stageB_two_machine_validation/" 2>/dev/null | grep -E 'status_.*\.md$' | head -1 || true)"
    if [[ -z "$spath" ]]; then
        printf "  %-13s %-13s %-22s %s\n" "$world" "$machine" "(no status report)" "$leg"
        ANY_FAIL=1
        continue
    fi
    report="$(git -C "$MAIN" show "$REMOTE/$leg:$spath" 2>/dev/null || true)"
    ladder="$(printf '%s\n' "$report" | sed -n 's/^- ladder *: *//p' | head -1)"
    [[ -n "$ladder" ]] || ladder="(unknown)"
    printf "  %-13s %-13s %-22s %s\n" "$world" "$machine" "$ladder" "$leg"
    printf '%s\n' "$ladder" | grep -qi 'PASSED' || ANY_FAIL=1
    FULL_REPORTS="${FULL_REPORTS}
--- $world ($machine) : $spath ---
${report}
"
done
echo "  --------------------------------------------------------------------------------"

if [[ "$FULL" -eq 1 ]]; then
    echo
    echo "================================ full reports =================================="
    printf '%s\n' "$FULL_REPORTS"
fi

echo
if [[ "$ANY_FAIL" -eq 0 ]]; then
    log "VERDICT: both worlds' AD-off ladders PASSED. Pipeline validated end-to-end."
    log "(This is a smoke validation — NOT QE-comparable. QE numbers need AD-on welfare + Step-5a TM multipliers.)"
else
    log "VERDICT: at least one world did NOT fully pass — see the matrix above (re-run with --full for details)."
    exit 2
fi
