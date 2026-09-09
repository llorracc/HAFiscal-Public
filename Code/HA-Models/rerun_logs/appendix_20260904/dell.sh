#!/bin/bash
# dell queue, robustness-appendix re-run on the current defaults (2026-09-04).
# Order is cheapest-first (cascade gate): Rspell_4 needs no re-estimation, so if it lands with
# sane multipliers the machinery is good before the expensive arms start. 5a stages never
# co-run on this box (two TM multiplier programs together run ~3x slower each).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest
PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/appendix_20260904
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration
source $LOG/env.sh; source $LOG/common.sh
exec >> "$LOG/dell.out" 2>&1
echo "===== DELL QUEUE start $(date +%F\ %H:%M:%S) at $(git -C $REPO rev-parse --short HEAD) on $(uname -n) ====="

# --- arms on the main calibration (no re-estimation) --------------------------------------
park Rspell_4; cfg Rspell_4 || exit 9
park ADElas;   cfg ADElas   || exit 9

# --- the fifth block's Baseline history arm (main calibration, history UI policy) ----------
# Named Baseline_uiB because that is what waterfall_table.ORDERS["ui-policy"] reads.
park Baseline_uiB
export HAFISCAL_UI_EXTENSION_POLICY=history
cfg Baseline Baseline_uiB _uiB || exit 9
export HAFISCAL_UI_EXTENSION_POLICY=window

# --- gamma = 3: its own Step 1 (splurge) and Step 2, then the arm ---------------------------
bash $LOG/crra3.sh || exit 9

# --- the no-splurge appendix ---------------------------------------------------------------
bash $LOG/nosplurge.sh || exit 9

echo "===== DELL QUEUE DONE $(date +%F\ %H:%M:%S) ====="
