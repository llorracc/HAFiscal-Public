#!/bin/bash
# The as-corrected fit-table pass + the two tabular generators, with the SAVE/RESTORE that
# the generators require.
#
# WHY THE SAVE/RESTORE. EstimAggFiscalMAIN writes a world-suffixed AllResults
# (_ESC_ascorrected_candidate.txt) -- that side is world-aware. The two tabular generators
# are NOT: estimBetas_tabular_generate.py and nonTargetedMoments_tabular_generate.py
# hard-code Tables/CRRA2/<name>.ltx with no world hook, so running them under
# HAFISCAL_WORLD=as-corrected would silently overwrite the DEFAULT world's staged
# candidates. So: copy the default pair aside, run, install the as-corrected output into
# the wfix artifact set, restore the default pair.
set -eu
L=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(builtin cd "$L/../../../.." && pwd)
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
FPC="$REPO/Code/HA-Models/FromPandemicCode"
T="$FPC/Tables/CRRA2"; WF="$REPO/conclusions_private/artifacts_20260823_wfix"
SAVE="$L/default_ltx_saved"; mkdir -p "$SAVE"
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
echo "=== 1. save the DEFAULT world's .ltx candidates"
for f in estimBetas_candidate.ltx nonTargetedMoments_candidate.ltx; do
  cp -p "$T/$f" "$SAVE/$f"; echo "    saved $f"
done
builtin cd "$FPC" || exit 9
echo "=== 2. as-corrected fit-table pass $(date '+%H:%M:%S')"
env -u HAFISCAL_EDTYPES HAFISCAL_WORLD=as-corrected \
    HAFISCAL_SKIP_ESTIMATION_OPTIMIZE=1 HAFISCAL_NM_IN_PLACE=0 \
    "$PY" EstimAggFiscalMAIN.py
echo "=== 3. as-corrected tabular generators $(date '+%H:%M:%S')"
for g in estimBetas_tabular_generate.py nonTargetedMoments_tabular_generate.py; do
  echo "--- $g"; env HAFISCAL_WORLD=as-corrected "$PY" "$g"
done
echo "=== 4. install into the wfix artifact set"
STAMP=$(date -r "$WF/estimBetas_wfix.tex" +%Y%m%d)
cp -p "$WF/estimBetas_wfix.tex"          "$WF/estimBetas_wfix_previous_${STAMP}.tex"
cp -p "$WF/nonTargetedMoments_wfix.tex"  "$WF/nonTargetedMoments_wfix_previous_${STAMP}.tex"
cp -p "$T/estimBetas_candidate.ltx"         "$WF/estimBetas_wfix.tex"
cp -p "$T/nonTargetedMoments_candidate.ltx" "$WF/nonTargetedMoments_wfix.tex"
echo "    installed (previous kept as *_previous_${STAMP}.tex)"
echo "=== 5. restore the DEFAULT world's .ltx candidates"
for f in estimBetas_candidate.ltx nonTargetedMoments_candidate.ltx; do
  cp -p "$SAVE/$f" "$T/$f"
  cmp -s "$SAVE/$f" "$T/$f" && echo "    restored+verified $f" || { echo "    RESTORE FAILED $f"; exit 9; }
done
echo "=== as-corrected fit pass done $(date '+%F %H:%M:%S')"
