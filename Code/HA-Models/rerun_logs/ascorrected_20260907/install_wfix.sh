#!/bin/bash
# Install the refreshed as-corrected multiplier table as the BUGFIXED source artifact,
# following the convention documented in artifacts_20260823_wfix/README.md:
#   - the current file lives at Multiplier_wfix.tex
#   - the one it replaces is kept as Multiplier_wfix_previous_<stamp>.tex
#   - a dated section is appended to the README naming the producing run
set -eu
REPO=/home/shared/github/llorracc/HAFiscal-Latest
A=$REPO/conclusions_private/artifacts_20260823_wfix
SRC=$REPO/Code/HA-Models/FromPandemicCode/Tables/Baseline_ac_20260907/Multiplier_candidate.tex
[ -f "$SRC" ] || { echo "no source table at $SRC" >&2; exit 2; }
STAMP=$(date -r "$A/Multiplier_wfix.tex" +%Y%m%d)
cp -p "$A/Multiplier_wfix.tex" "$A/Multiplier_wfix_previous_${STAMP}.tex"
cp -p "$SRC" "$A/Multiplier_wfix.tex"
echo "archived  -> Multiplier_wfix_previous_${STAMP}.tex"
echo "installed <- $SRC"
grep 'AD effect)' "$A/Multiplier_wfix.tex"
