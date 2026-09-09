#!/usr/bin/env bash
# run on ccarroll-m5: reproduce + diagnose the PF-decay guard trip (BUG-080 under the earnings phase)
set -u
REPO=/Volumes/Sync/GitHub/llorracc/HAFiscal-Latest
OUT=/tmp/probe_bug080
mkdir -p "$OUT"
cd "$REPO/Code/HA-Models/FromPandemicCode" || exit 2
PY="$REPO/.venv/bin/python"

export HAFISCAL_FTI_REPO="$HOME/GitHub/llorracc/fast-time-iteration"
export HAFISCAL_CHECK_MARKOV_INPUTS=1 HAFISCAL_STEP5_ATI=1 HAFISCAL_QUIET_BETADISTR=1
export PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 MKL_NUM_THREADS=1
SPL=/tmp/spine5_Result_AllTarget_ESC.txt
DFE=/tmp/spine5_DiscFacEstim_CRRA_2.0_R_1.01_TM_a_ESC.txt

echo "== git: $(git -C "$REPO" rev-parse HEAD)  $(date)"

# (d) background: the VERBATIM failing pass -- EstimAggFiscalMAIN.py calcAllResults with the staged S2 estimates
#     staged where calcAllResults reads them: Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC_candidate.txt (gitignored)
cp "$DFE" "$REPO/Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC_candidate.txt"
( echo "--- EstimAggFiscalMAIN.py SKIP_ESTIMATION_OPTIMIZE=1 phase=1/120 $(date)";
  env HAFISCAL_EARNINGS_PHASE_HAZARD=1/120 HAFISCAL_SPLURGE_FILE="$SPL" HAFISCAL_DISCFAC_FILE="$DFE" \
      HAFISCAL_SKIP_ESTIMATION_OPTIMIZE=1 "$PY" EstimAggFiscalMAIN.py; echo "--- exit=$? $(date)" ) \
  > "$OUT/estim_main_phase.log" 2>&1 &
PID_D=$!

# (c) background: the slow probe arms (guard-free warm descent + cold guard-ON EGM at the new beta)
( env HAFISCAL_EARNINGS_PHASE_HAZARD=1/120 HAFISCAL_SPLURGE_FILE="$SPL" HAFISCAL_DISCFAC_FILE="$DFE" \
      "$PY" ../probe_pf_guard_bug080_phase.py --descent --cold-egm; echo "--- exit=$? $(date)" ) \
  > "$OUT/probe_phase_full.out" 2>&1 &
PID_C=$!

# (a) foreground: the phase probe, sections A-D
env HAFISCAL_EARNINGS_PHASE_HAZARD=1/120 HAFISCAL_SPLURGE_FILE="$SPL" HAFISCAL_DISCFAC_FILE="$DFE" \
    "$PY" ../probe_pf_guard_bug080_phase.py > "$OUT/probe_phase.out" 2>&1
echo "== (a) phase probe exit=$?  $(date)"

# (b) foreground: hazard 0 against the checkout's defaults (what spine4's post2 did on 2026-08-20)
env -u HAFISCAL_SPLURGE_FILE -u HAFISCAL_DISCFAC_FILE HAFISCAL_EARNINGS_PHASE_HAZARD=0 \
    "$PY" ../probe_pf_guard_bug080_phase.py --discfac-file "$REPO/Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt" \
    > "$OUT/probe_h0.out" 2>&1
echo "== (b) hazard-0 probe exit=$?  $(date)"
echo "== background pids: estim_main=$PID_D probe_full=$PID_C"
