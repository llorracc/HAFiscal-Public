#!/bin/bash
# Report a queue's state from its log WITHOUT matching stale text.
#   queue_state.sh <logfile>   ->  prints RUNNING | DONE | HALTED | ABSENT
#
# Why this exists: the first fleet watcher grepped the whole log for
# "appendix queue done|HALT|GATE RED" and declared dell terminal while it was still on its last
# arm -- because the log is opened in APPEND mode and still contained a GATE RED line from a
# superseded run of the gate. Grepping a whole append-mode log for a terminal marker asks "has
# this ever finished?", not "has THIS run finished?".
#
# The fix is to look only at the slice after the LAST start marker, which every queue prints on
# entry. No new files, nothing to keep in sync, and it stays correct however many times the log
# is appended to.
set -u
LOG=${1:?usage: queue_state.sh <logfile>}
START='^===== appendix queue on .* start '
[ -f "$LOG" ] || { echo ABSENT; exit 0; }
SLICE=$(awk -v re="$START" '$0 ~ re {n=NR} {l[NR]=$0} END{if(n=="") n=1; for(i=n;i<=NR;i++) print l[i]}' "$LOG")
case "$SLICE" in
  *"===== appendix queue done"*) echo DONE ;;
  *"===== HALT on "*)            echo HALTED ;;
  *)                             echo RUNNING ;;
esac
