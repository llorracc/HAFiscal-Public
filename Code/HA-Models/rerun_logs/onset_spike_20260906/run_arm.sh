#!/bin/bash
# One arm of the BUG-122 Step-0 measurement.
#   run_arm.sh <suffix> <exempt 0|1> <scope...>
# e.g. run_arm.sh _off 0 --hs-only
#      run_arm.sh _off 0 --parametrization Reduced_Run
# The scope is the TRAILING arguments, plural (2026-09-07): it used to be a single argument, so
# any two-token scope -- `--parametrization <name>` -- could not be expressed at all.
set -u
# Portable across the fleet: the repo root is found from this script's own location, and the
# interpreter from the repo's venv when there is one. Nothing here is machine-specific.
L=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(builtin cd "$L/../../../.." && pwd)
SUF=$1; EXEMPT=$2; shift 2
[ $# -ge 1 ] || { echo "run_arm.sh: no scope given (e.g. --baseline)" >&2; exit 2; }
source "$L/env.sh"
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration" \
         "$HOME/github/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
export HAFISCAL_FIGS_SUFFIX="$SUF"
# Pin the arm EXPLICITLY, both ways. Before 2026-09-06 leaving it unset meant OFF; now the
# catalog setdefaults it ON, so "export only when 1" would make BOTH arms the ON arm and the
# comparison would silently measure nothing.
case "$EXEMPT" in 0|1) ;; *) echo "run_arm.sh: exempt must be 0 or 1, got '$EXEMPT'" >&2; exit 2;; esac
export HAFISCAL_ONSET_SPIKE_T0_EXEMPT="$EXEMPT"
builtin cd "$REPO/Code/HA-Models/FromPandemicCode" || exit 9
echo "=== host $(hostname) repo $REPO"
echo "=== arm suffix=$SUF scope=$* exempt=$EXEMPT start $(date '+%F %H:%M:%S')"
"$PY" AggFiscalMAIN_reduced.py "$@"
rc=$?
echo "=== arm suffix=$SUF rc=$rc end $(date '+%F %H:%M:%S')"
exit $rc
