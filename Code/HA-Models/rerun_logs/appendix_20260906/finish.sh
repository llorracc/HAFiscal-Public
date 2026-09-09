#!/bin/bash
# Close-out for the 2026-09-06/07 appendix re-run. Run once BOTH queues and the S=5 band are
# terminal. Order matters: harvest before anything reads a glob, gate before anything is believed,
# and only then generate. Every step is idempotent.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest
PY=$REPO/.venv/bin/python
L=$REPO/Code/HA-Models/rerun_logs/appendix_20260906
OUT=${1:-$L/report}
mkdir -p "$OUT"
builtin cd "$REPO" || exit 9
echo "===== FINISH $(date '+%F %H:%M:%S')"

echo; echo "--- 0. every arm ran with the a-indexed engine? (the defect that invalidated the first cut)"
bad=0
for f in "$L"/mult_*.log; do
  a=$(basename "$f" .log); a=${a#mult_}
  # the equilibrium store records the producer's real environment; the sidecar could not be
  # trusted on this field before the BUG-124 fix, so read the store's line instead
  if grep -qE "\[ad-equilibrium\] (SAVED|REPLACING|KEPT)[^[]*TM_A_INDEXED=1" "$f" 2>/dev/null; then
    echo "    OK   $a"
  else
    echo "    ??   $a -- no TM_A_INDEXED=1 in its equilibrium-store lines; CHECK BEFORE BELIEVING"
    bad=$((bad+1))
  fi
done
[ $bad -gt 0 ] && echo "    ^ $bad arm(s) unverified -- do not generate a report from them"

echo; echo "--- 1. harvest m5's arms into this tree (so every comparison is computed in one place)"
bash "$L/harvest_m5.sh" 2>/dev/null || echo "    (no harvest script; m5 arms must be copied by hand)"

echo; echo "--- 2. the arms, against their parked predecessors"
builtin cd "$REPO/Code/HA-Models/FromPandemicCode" || exit 9
for a in Rspell_4 ADElas CRRA3 Splurge0 Baseline_uiB Rfree_1005 Rfree_1015 LowerUBnoB LowerUBnoB_histB; do
  new=$(sed -n 5p "Tables/$a/Multiplier_candidate.tex" 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | tr '\n' ' ')
  old=$(sed -n 5p "Tables/_parked_20260906/$a/Multiplier_candidate.tex" 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | tr '\n' ' ')
  s=$(ls -d Tables/${a}_seed* 2>/dev/null | wc -l)
  printf "    %-18s parked: %-22s now: %-22s S=%s\n" "$a" "${old:-(none)}" "${new:-(PENDING)}" "$s"
done

echo; echo "--- 3. the appendix tables (published beside candidate)"
builtin cd "$REPO" || exit 9
"$PY" Code/HA-Models/robustness_appendix_tables.py --out "$OUT/after.md" --tex "$OUT/after_rows.tex" | tail -4

echo; echo "--- 4. estimates + C + W per arm against the published rows"
"$PY" Code/HA-Models/robustness_appendix_diff.py --md "$OUT/after_diff.md" | tail -3

echo; echo "--- 5. regenerate UPDATES.md through the same row builders"
"$PY" Code/HA-Models/updates_report.py | tail -2

echo; echo "--- 6. guards"
"$PY" -m pytest Code/HA-Models/test_robustness_appendix_ui_block.py \
     Code/HA-Models/test_updates_report_appendix.py Code/HA-Models/test_locked_tables.py \
     -q --no-header 2>&1 | tail -3

echo; echo "===== FINISH DONE $(date '+%F %H:%M:%S')   reports in $OUT"
