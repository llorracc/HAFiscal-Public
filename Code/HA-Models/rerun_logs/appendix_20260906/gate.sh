#!/bin/bash
# Release the appendix queue only if today's defaults left the ESTIMATION untouched.
#
# The queue re-runs Steps 5a and 5b only, on the calibrations of 2026-09-04/05, because neither
# of today's corrections should reach the estimation: the UI policy is read only in recessionUI
# and a Step-2 estimate is invariant to it, and the onset spike exists only in a recession, which
# the estimation economy never runs. That is an argument, not a measurement -- so this gate makes
# the chain-of-record do_all measure it. Steps 1 and 2 there run under the new defaults and write
# these same files. The comparison is a TOLERANCE, not byte-identity: an optimizer's argmin is not
# bit-reproducible across a change in array shapes even when the objective is economically
# identical, and the chain did change shape (seven micro states to six). The first cut of this
# gate compared bytes and went red on the ELEVENTH significant figure -- see gate.py.
# If the calibration moves beyond tolerance, THE QUEUE IS WRONG and every arm needs its Step 2 back.
set -u
L=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(builtin cd "$L/../../../.." && pwd)
CHAIN="$REPO/Code/HA-Models/rerun_logs/chain_of_record_20260906/chain.out"

echo "=== waiting for the chain of record to clear Step 2 ..."
while ! grep -qE "Step 3|Step 4|do_all rc=" "$CHAIN" 2>/dev/null; do sleep 120; done
echo "=== chain reached: $(grep -oE 'Step [0-9][a-z]?' "$CHAIN" | tail -1) at $(date '+%F %H:%M:%S')"

PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
"$PY" "$L/gate.py" --tol 1e-6 || exit 9
