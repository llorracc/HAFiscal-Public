#!/bin/bash
# Close-out for the 2026-09-04 robustness-appendix re-run. Run once BOTH queues are terminal.
# Order matters: sweep and harvest before anything reads a glob, gate before anything is
# believed, and only then generate. Every step is idempotent.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest
PY=$REPO/.venv/bin/python
L=$REPO/Code/HA-Models/rerun_logs/appendix_20260904
OUT=/home/econ-ark/appendix_rerun_20260904
mkdir -p "$OUT"
cd "$REPO" || exit 9
exec > >(tee -a "$L/finish.out") 2>&1
echo "===== FINISH $(date '+%F %H:%M:%S') ====="

echo; echo "--- 0. regenerate the Baseline_uiB welfare summaries if they are not tonight's"
# Why: welfare6_parallel_summary.json is TRACKED, and a blanket `git checkout -- Tables` on
# 2026-09-04 22:50 (mine, restoring tracked files park() had moved) reverted tonight's uiB
# summaries to their August content. The C blocks read the UNTRACKED welfare4_candidate.tex
# and were unaffected; only the fifth block's welfare columns, which read the summary, were.
# The seeds are deterministic, so re-running reproduces them exactly -- and the guard below
# is the check. Skipped when the guard already passes.
if "$PY" -m pytest Code/HA-Models/test_robustness_appendix_ui_block.py::test_baseline_rows_reproduce_memo_section_5 \
     -q --no-header >/dev/null 2>&1; then
  echo "    memo guard already green -- summaries are current, skipping"
else
  echo "    memo guard red -- re-running the three Baseline_uiB welfare seeds (~33 min)"
  ( cd "$REPO/Code/HA-Models/FromPandemicCode" || exit 9
    export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration
    source "$L/env.sh"; export HAFISCAL_UI_EXTENSION_POLICY=history
    for K in 0 1 2; do
      echo "    uiB seed $K $(date +%H:%M:%S)"
      "$PY" run_welfare6_parallel.py --parametrization Baseline --seed-offset $K \
          --out-dir "welfare6_scenario_results_Baseline_uiB_seed$K" \
          --table-dir "Tables/Baseline_uiB_seed$K" > "$L/refresh_uiB_seed$K.log" 2>&1 \
          || { echo "    uiB seed $K FAILED - see $L/refresh_uiB_seed$K.log"; exit 9; }
    done ) || echo "    WARNING: uiB refresh failed; the fifth block's welfare columns stay stale"
fi

echo; echo "--- 1. harvest m5 (sweeps both trees, parks dell's stale copies, installs m5's calibrations)"
bash "$L/harvest_m5.sh" || { echo "HARVEST FAILED - stopping"; exit 9; }

echo; echo "--- 1b. restore ONLY the LOCKED tables (the rest waits until after the report)"
# Narrow on purpose. Restoring every deleted tracked file here would resurrect the four histB
# directories parked deliberately as out of scope (owner, 2026-09-04) -- their tracked summaries
# would come back and the histB rows would render August numbers instead of (pending). And a
# blanket restore also reverts MODIFIED files, undoing step 0. So: locked files only now,
# everything else in step 9, once the report has been generated from the parked state.
awk -F'\t' '/^[^#]/ && NF>1 {print $1}' LOCKED_TABLES.manifest | while read -r f; do
  [ -e "$f" ] || { git checkout -- "$f" 2>/dev/null && echo "    restored LOCKED $f"; }
done
echo "    locked files missing after restore: $(awk -F'\t' '/^[^#]/ && NF>1 {print $1}' LOCKED_TABLES.manifest | while read -r f; do [ -e "$f" ] || echo x; done | wc -l)"

echo; echo "--- 2. contamination gate (must be CLEAN apart from the deliberately parked histB rows)"
"$PY" "$L/check_glob_contamination.py" | tee "$OUT/contamination_$(date +%H%M).txt"

echo; echo "--- 3. appendix C tables: published beside candidate (the five blocks)"
"$PY" Code/HA-Models/robustness_appendix_tables.py --out "$OUT/after.md" --tex "$OUT/after_rows.tex" | tail -5

echo; echo "--- 4. estimates + C + W per arm against the published rows"
"$PY" Code/HA-Models/robustness_appendix_diff.py --md "$OUT/after_diff.md" | tail -3

echo; echo "--- 5. regenerate UPDATES.md (whole-document generator; never hand-edited)"
"$PY" Code/HA-Models/updates_report.py

echo; echo "--- 6. guards"
"$PY" -m pytest Code/HA-Models/test_robustness_appendix_ui_block.py \
     Code/HA-Models/test_updates_report_appendix.py Code/HA-Models/test_locked_tables.py \
     -q --no-header 2>&1 | tail -4

echo; echo "--- 7. what moved in UPDATES.md"
git diff --stat UPDATES.md

echo; echo "--- 8. arm inventory"
for a in Rfree_1005 Rfree_1015 CRRA3 LowerUBnoB LowerUBnoB_histB Rspell_4 ADElas Baseline Baseline_uiB Splurge0; do
  printf '  %-18s 5a=%-3s seeds=%s\n' "$a" \
    "$([ -f Code/HA-Models/FromPandemicCode/Tables/$a/Multiplier_candidate.tex ] && echo yes || echo NO)" \
    "$(ls -d Code/HA-Models/FromPandemicCode/Tables/${a}_seed* 2>/dev/null | wc -l)"
done
echo; echo "--- 9. restore the remaining tracked files park() displaced (report is generated)"
# Deletions only, and never inside a deliberately parked directory: a blanket
# `git checkout -- Tables` would also revert MODIFIED tracked files (tonight's welfare
# summaries), which is the 22:50 mistake.
git status --short Code/HA-Models/FromPandemicCode/Tables 2>/dev/null | grep '^ D' | sed 's|^ D ||' | while read -r f; do
  # out-of-scope histB arms (owner: leave parked), and Baseline_uiB seeds 3-4, which are the
  # August 5-seed battery: this run produced S=3, and wt.welfare() globs summaries, so leaving
  # them live would average five seeds into the fifth block's uiB row.
  case "$f" in */Rfree_1015_histB*|*/CRRA3_histB*|*/ADElas_histB*|*/Rfree_1005_histB*) continue;;
               */Baseline_uiB_seed3/*|*/Baseline_uiB_seed4/*) continue;; esac
  git checkout -- "$f" 2>/dev/null
done
echo "    still deleted (the out-of-scope histB arms, deliberately): $(git status --short Code/HA-Models/FromPandemicCode/Tables 2>/dev/null | grep -c '^ D')"
echo "    modified, left alone (tonight's results): $(git status --short Code/HA-Models/FromPandemicCode/Tables 2>/dev/null | grep -c '^ M')"

echo; echo "===== FINISH DONE $(date '+%F %H:%M:%S') ====="
echo "reports: $OUT/after.md  $OUT/after_diff.md   (before: $OUT/before_20260904.md)"
