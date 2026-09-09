#!/bin/bash
# Gate C: the TM a-indexed multiplier engine (a different code path from Gate B's welfare
# battery) must reproduce the 2026-09-03 Tables/Baseline/Multiplier_candidate.tex byte for
# byte after the system upgrade. Writes to Tables/Baseline_upgradecheck (FIGS_SUFFIX) so the
# record is never touched. On PASS the dell appendix queue starts; on FAIL nothing does.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest
PY=$REPO/.venv/bin/python
L=$REPO/Code/HA-Models/rerun_logs/appendix_20260904
FPC=$REPO/Code/HA-Models/FromPandemicCode
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration
source $L/env.sh
cd $FPC || exit 9
echo "=== GATE C (5a Baseline reproduction) start $(date +%H:%M:%S)"
T0=$(date +%s)
env HAFISCAL_FIGS_SUFFIX=_upgradecheck "$PY" AggFiscalMAIN_reduced.py --parametrization Baseline > "$L/gateC_5a.log" 2>&1
rc=$?
echo "=== GATE C 5a end rc=$rc wall=$(( ($(date +%s)-T0)/60 ))min $(date +%H:%M:%S)"
[ $rc -eq 0 ] || { echo "GATE C FAILED: 5a exited $rc"; touch "$L/gateC.failed"; exit 9; }
A=Tables/Baseline/Multiplier_candidate.tex; B=Tables/Baseline_upgradecheck/Multiplier_candidate.tex
if cmp -s "$A" "$B"; then
  echo "GATE C PASSED: 5a Baseline reproduces the 2026-09-03 multipliers byte-for-byte"
  grep "AD effect)" "$B"
else
  echo "GATE C FAILED: multipliers differ from the 2026-09-03 record"; diff "$A" "$B" | head -20
  touch "$L/gateC.failed"; exit 9
fi
touch "$L/gateC.done"
echo "=== DELL QUEUE launching $(date +%H:%M:%S)"
exec bash "$L/dell.sh"
