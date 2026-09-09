#!/bin/bash
# Queue A (2026-08-28): arm 0 (published construction, frozen monolith) -> arm-0-vs-published-pickle comparison
# -> step-0d GE-only SS-source arms on arm 0's Jacobians -> arm 1 (+BUG-072 fix, monolith). Sequential.
LAD=/Users/ccarroll/ui_ext_20260826/hank_ladder_20260828
PY=/Users/ccarroll/GitHub/llorracc/HAFiscal-Latest/.venv/bin/python
cd "$LAD" || exit 1
echo "queue_A start $(date '+%F %T')"
./run_arm.sh arm0_published monolith
$PY compare_jacs.py qe_calib/HA_Fiscal_Jacs.obj arm0_published/HA_Fiscal_Jacs.obj "arm0(0.17, monolith, QE calib) vs PUBLISHED pickle (0.14.1)" > arm0_vs_published_pickle.txt 2>&1
GE_ONLY=1 ./run_arm.sh arm0_ss_jacs_c monolith HAFISCAL_HANK_SS_SOURCE=jacs_c
GE_ONLY=1 ./run_arm.sh arm0_ss_jacs monolith HAFISCAL_HANK_SS_SOURCE=jacs
./run_arm.sh arm1_zeroth_mono monolith HAFISCAL_STEP4_ZEROTH_FIX=1
echo "queue_A end $(date '+%F %T')"
