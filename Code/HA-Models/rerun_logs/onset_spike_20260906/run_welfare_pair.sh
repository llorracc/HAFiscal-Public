#!/bin/bash
# The welfare (Step 5b) half of the BUG-122 Step-0 measurement, both arms, S seeds each.
#   run_welfare_pair.sh <parametrization> <tag> [S]     e.g. run_welfare_pair.sh Baseline base 3
#
# Each arm consumes ITS OWN stored AD equilibrium: the store keys on the onset-spike flag since
# 2026-09-06, so the flag-ON battery cannot silently be handed the flag-OFF equilibrium. Run the
# matching 5a pair on this machine first -- equilibria are per-machine and the battery solves
# nothing under AD-equilibrium sharing.
#
# Per-seed --out-dir/--table-dir on every invocation: without them each seed overwrites the last
# and an "S = 3" claim is really S = 1. TAG is in the directory name too (2026-09-07): it used
# to name only the logs, so two batteries of one parametrization differing in S -- or in
# anything else -- collided in the table tree while their logs looked separate.
set -u
L=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(builtin cd "$L/../../../.." && pwd)
PARAM=$1; TAG=$2; S=${3:-3}
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
source "$L/env.sh"
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration" \
         "$HOME/github/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
builtin cd "$REPO/Code/HA-Models/FromPandemicCode" || exit 9
echo "===== welfare pair $TAG ($PARAM, S=$S) on $(hostname) start $(date '+%F %H:%M:%S')"
for arm in off:0 on:1; do
  name=${arm%%:*}; ex=${arm##*:}
  for k in $(seq 0 $((S-1))); do
    # Pin the arm EXPLICITLY, both ways: since 2026-09-06 the flag is a catalog default (ON),
    # so unsetting it selects ON and the "off" arm would silently be a second on arm.
    export HAFISCAL_ONSET_SPIKE_T0_EXEMPT="$ex"
    echo "----- ${TAG}_${name} seed $k $(date '+%H:%M:%S')"
    "$PY" run_welfare6_parallel.py --parametrization "$PARAM" --seed-offset "$k" \
        --out-dir "welfare6_scenario_results_${PARAM}_${TAG}_os${name}_seed${k}" \
        --table-dir "Tables/${PARAM}_${TAG}_os${name}_seed${k}" \
        > "$L/welf_${TAG}_${name}_seed${k}.log" 2>&1
    rc=$?
    echo "      rc=$rc $(date '+%H:%M:%S')"
    [ $rc -ne 0 ] && { echo "HALT: see $L/welf_${TAG}_${name}_seed${k}.log"; exit $rc; }
  done
done
echo "===== welfare pair $TAG done $(date '+%F %H:%M:%S')"
