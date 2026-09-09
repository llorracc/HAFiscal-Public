#!/bin/bash
# Both arms of the BUG-122 Step-0 measurement, in order, on one machine.
#   run_pair.sh <tag> <scope...>            e.g. run_pair.sh base --baseline
#                                                run_pair.sh red --parametrization Reduced_Run
# Argument ORDER CHANGED 2026-09-07 (tag first, scope trailing) so that a two-token scope can be
# expressed; an old-style call is rejected rather than misread.
# Runs <tag>_off then <tag>_on. Strictly sequential: two TM multiplier programs sharing a box
# each run about three times slower, so overlapping them would buy nothing and cost the timings.
set -u
L=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
case "${1:-}" in --*) echo "run_pair.sh: argument order is now <tag> <scope...>; got '$1' first" >&2; exit 2;; esac
TAG=$1; shift
[ $# -ge 1 ] || { echo "run_pair.sh: no scope given (e.g. --baseline)" >&2; exit 2; }
echo "===== pair $TAG on $(hostname) scope=$* start $(date '+%F %H:%M:%S')"
for arm in off:0 on:1; do
  name=${arm%%:*}; ex=${arm##*:}
  bash "$L/run_arm.sh" "_${TAG}_${name}" "$ex" "$@" > "$L/${TAG}_${name}.log" 2>&1
  rc=$?
  echo "----- ${TAG}_${name} rc=$rc $(date '+%F %H:%M:%S')"
  [ $rc -ne 0 ] && { echo "HALT: ${TAG}_${name} failed, see $L/${TAG}_${name}.log"; exit $rc; }
done
echo "===== pair $TAG done $(date '+%F %H:%M:%S')"
