#!/bin/bash
# Refresh the LEGACY-LAYOUT baseline pickles that Output_Results.py's Splurge0 comparison reads.
#
# Output_Results.py:387 loads `C_Multiplier_Baseline_Results` from `Abs_Path + '/Figures/'` -- the
# TOP LEVEL -- while every baseline run writes to `Figures/Baseline/`. So the no-splurge comparison
# figure plots the current Splurge0 arm against whatever baseline happens to be sitting at the top
# level, which on 2026-09-06 was the 2026-09-03 vintage: a mixed-vintage exhibit, the same class of
# error as the appendix's fifth block reading new multipliers against old welfare seeds.
#
# The real fix is for that branch to read Figures/Baseline/; this is the established workaround
# (see the no-splurge chain's run notes) and it is idempotent. Run it BEFORE the Splurge0 arm.
set -u
FPC=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")/../../FromPandemicCode" && pwd)
n=0
for f in C_Multiplier_Baseline_Results.csv NPV_Multiplier_Baseline_Results.csv; do
  src="$FPC/Figures/Baseline/$f"; dst="$FPC/Figures/$f"
  [ -f "$src" ] || { echo "  MISSING $src -- run the Baseline arm first"; exit 9; }
  if [ -f "$dst" ] && cmp -s "$src" "$dst"; then echo "  already current: $f"; continue; fi
  [ -f "$dst" ] && cp -p "$dst" "$dst.pre_bug122_$(date +%Y%m%d)" && echo "  kept the old one as $f.pre_bug122_$(date +%Y%m%d)"
  cp -p "$src" "$dst" && echo "  refreshed $f  ($(date -r "$src" '+%F %H:%M') vintage)" && n=$((n+1))
done
echo "  $n file(s) refreshed from Figures/Baseline/"
