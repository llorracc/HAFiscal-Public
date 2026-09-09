#!/bin/bash
# kill stray battery/cell procs; safe: callers exec this FILE so their
# cmdline never contains the patterns (the thrice-burned self-match trap).
for pat in "run_welfare6_parallel.py" "welfare6_scenario.py" "spawn_main"; do
  pgrep -f "$pat" | grep -vw "$$" | xargs -r kill -9 2>/dev/null
done
exit 0
