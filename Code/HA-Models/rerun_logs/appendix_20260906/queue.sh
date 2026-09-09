#!/bin/bash
# Run a list of appendix arms in sequence on this machine.
#   queue.sh <arm> [<arm> ...]        arms are "NAME" or "NAME:TAG:SUFFIX"
# Sequential on purpose: two TM multiplier programs sharing a box each run about three times
# slower, so overlapping them buys nothing.
set -u
L=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
echo "===== appendix queue on $(hostname) start $(date '+%F %H:%M:%S'): $*"
for spec in "$@"; do
  IFS=: read -r NAME TAG SFX <<< "$spec"
  bash "$L/arm.sh" "$NAME" "${TAG:-$NAME}" "${SFX:-}" 2>&1
  rc=$?
  [ $rc -ne 0 ] && echo "===== HALT on $spec rc=$rc $(date '+%F %H:%M:%S')" && exit $rc
done
echo "===== appendix queue done $(date '+%F %H:%M:%S')"
