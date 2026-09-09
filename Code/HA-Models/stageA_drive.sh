#!/usr/bin/env bash
#
# stageA_drive.sh — OPTIONAL single-terminal orchestrator for the two-machine
# Stage-A workflow. Run it from EITHER machine: it auto-detects which LEGS_SPEC
# entry is the local box (by repo path; see is_local_leg) and runs that leg
# in-process — no ssh-to-self — while genuinely remote legs are ssh-launched.
# It then waits for both legs to publish to the remote and runs
# stageA_integrate.sh locally. Requires passwordless ssh to the REMOTE box only.
#
# This is a convenience wrapper. If ssh between the boxes is awkward, just run
# stageA_leg.sh by hand on each machine and stageA_integrate.sh once — that is
# the documented baseline workflow (see the runbook).
#
# Config: a shell file (default ./stageA_drive.conf, or --config PATH) defining
#   STAGEA_BASE_BRANCH="..."           # optional; else the TM-vs-MC default
#   LEGS_SPEC=(                         # one entry per machine:
#     "ssh_target|repo_dir|world|machine_label"
#     ...
#   )
# See stageA_drive.conf.example.
#
# Usage:
#   bash stageA_drive.sh                  # launch both legs, wait, then compare
#   bash stageA_drive.sh --promote        # ...and promote after the legs land
#   bash stageA_drive.sh --launch-only    # just kick off the remote legs
#   bash stageA_drive.sh --integrate-only # skip launching; just wait + integrate
#   bash stageA_drive.sh --config PATH
#   --poll-secs N   (default 120)   --timeout-mins N   (default 720)
#
set -eo pipefail

CONFIG="./stageA_drive.conf"
PROMOTE=0
LAUNCH_ONLY=0
INTEGRATE_ONLY=0
POLL_SECS=120
TIMEOUT_MINS=720
REMOTE="${STAGEA_REMOTE:-origin}"

die() { printf 'stageA_drive: ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[stageA_drive] %s\n' "$*"; }
usage() { sed -n '2,33p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)        shift; CONFIG="$1"; shift ;;
        --promote)       PROMOTE=1; shift ;;
        --launch-only)   LAUNCH_ONLY=1; shift ;;
        --integrate-only) INTEGRATE_ONLY=1; shift ;;
        --poll-secs)     shift; POLL_SECS="$1"; shift ;;
        --timeout-mins)  shift; TIMEOUT_MINS="$1"; shift ;;
        -h|--help)       usage; exit 0 ;;
        *)               die "unknown argument: $1 (see --help)" ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
MAIN_REAL="$(realpath "$MAIN" 2>/dev/null || echo "$MAIN")"

# A leg refers to THIS machine when its ssh_target is an explicit local token,
# or its repo_dir resolves to the checkout we're running from. The mac and linux
# repo paths are mutually exclusive, so exactly one leg matches on each box —
# which lets the SAME config + driver run from EITHER machine: the local leg
# runs in-process (no ssh-to-self), only genuinely remote legs use ssh.
is_local_leg() {  # args: ssh_target repo_dir
    local tgt="$1" dir="$2" rp
    case "$tgt" in local|localhost|self|127.0.0.1) return 0 ;; esac
    rp="$(realpath "$dir" 2>/dev/null || true)"
    [[ -n "$rp" && "$rp" == "$MAIN_REAL" ]]
}

[[ -f "$CONFIG" ]] || die "config not found: $CONFIG (copy stageA_drive.conf.example and edit it, or pass --config)"
# shellcheck disable=SC1090
source "$CONFIG"
BASE_BRANCH="${STAGEA_BASE_BRANCH:-0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC}"
[[ ${#LEGS_SPEC[@]} -gt 0 ]] || die "LEGS_SPEC is empty in $CONFIG"

# parse specs into parallel arrays
S_SSH=(); S_DIR=(); S_WORLD=(); S_MACHINE=(); S_LEG=(); S_BASESHA=()
for spec in "${LEGS_SPEC[@]}"; do
    IFS='|' read -r tgt dir world machine <<< "$spec"
    [[ -n "$tgt" && -n "$dir" && -n "$world" && -n "$machine" ]] || die "bad LEGS_SPEC entry: '$spec' (need ssh_target|repo_dir|world|machine_label)"
    case "$world" in
        default)     tok="default" ;;
        as-corrected) tok="ascorrected" ;;
        *) die "world must be default|as-corrected in spec '$spec'" ;;
    esac
    S_SSH+=("$tgt"); S_DIR+=("$dir"); S_WORLD+=("$world"); S_MACHINE+=("$machine")
    S_LEG+=("${BASE_BRANCH}_${machine}_${tok}")
done

leg_sha() { git -C "$MAIN" ls-remote "$REMOTE" "refs/heads/$1" 2>/dev/null | awk '{print $1}'; }

# ----------------------------------------------------------------------------
# launch remote legs
# ----------------------------------------------------------------------------
if [[ "$INTEGRATE_ONLY" -eq 0 ]]; then
    for i in "${!S_SSH[@]}"; do
        leg="${S_LEG[$i]}"
        S_BASESHA[$i]="$(leg_sha "$leg")"
        logrel="stageA_two_machine_validation/logs/drive_${S_MACHINE[$i]}_${S_WORLD[$i]}.out"
        if is_local_leg "${S_SSH[$i]}" "${S_DIR[$i]}"; then
            log "launching leg LOCALLY (this machine, no ssh) : world=${S_WORLD[$i]} machine=${S_MACHINE[$i]}"
            log "   (baseline $leg sha=${S_BASESHA[$i]:-<none>})"
            ( cd "${S_DIR[$i]}" && mkdir -p stageA_two_machine_validation/logs \
                && nohup bash Code/HA-Models/stageA_leg.sh \
                     --world "${S_WORLD[$i]}" --machine "${S_MACHINE[$i]}" --base-branch "$BASE_BRANCH" \
                     </dev/null > "$logrel" 2>&1 & echo "   local pid $!" ) \
                || die "local launch failed in ${S_DIR[$i]}"
        else
            log "launching leg on ${S_SSH[$i]} via ssh : world=${S_WORLD[$i]} machine=${S_MACHINE[$i]}"
            log "   (baseline $leg sha=${S_BASESHA[$i]:-<none>})"
            remote_cmd="cd '${S_DIR[$i]}' && mkdir -p stageA_two_machine_validation/logs && nohup bash Code/HA-Models/stageA_leg.sh --world '${S_WORLD[$i]}' --machine '${S_MACHINE[$i]}' --base-branch '$BASE_BRANCH' </dev/null > '$logrel' 2>&1 & echo \"remote pid \$!\""
            # shellcheck disable=SC2029
            ssh "${S_SSH[$i]}" "bash -lc \"$remote_cmd\"" || die "ssh launch failed for ${S_SSH[$i]}"
        fi
    done
    log "all legs launched."
    [[ "$LAUNCH_ONLY" -eq 1 ]] && { log "--launch-only: not waiting. Re-run with --integrate-only later."; exit 0; }
else
    for i in "${!S_LEG[@]}"; do S_BASESHA[$i]=""; done
fi

# ----------------------------------------------------------------------------
# wait for both legs to advance on the remote
# ----------------------------------------------------------------------------
log "waiting for ${#S_LEG[@]} leg(s) to publish (poll ${POLL_SECS}s, timeout ${TIMEOUT_MINS}min)"
deadline=$(( $(date +%s) + TIMEOUT_MINS*60 ))
while :; do
    git -C "$MAIN" fetch --prune "$REMOTE" >/dev/null 2>&1 || true
    pending=0
    for i in "${!S_LEG[@]}"; do
        cur="$(leg_sha "${S_LEG[$i]}")"
        if [[ -z "$cur" || "$cur" == "${S_BASESHA[$i]}" ]]; then
            pending=$((pending+1))
        fi
    done
    [[ "$pending" -eq 0 ]] && { log "all legs published."; break; }
    [[ $(date +%s) -lt $deadline ]] || die "timeout waiting for $pending leg(s) — check the remote drive_*.out logs"
    log "  $pending leg(s) still running; sleeping ${POLL_SECS}s ..."
    sleep "$POLL_SECS"
done

# ----------------------------------------------------------------------------
# integrate locally
# ----------------------------------------------------------------------------
INT=(bash "$SCRIPT_DIR/stageA_integrate.sh" --base-branch "$BASE_BRANCH")
[[ "$PROMOTE" -eq 1 ]] && INT+=(--promote)
log "running: ${INT[*]}"
"${INT[@]}"
