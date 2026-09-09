#!/usr/bin/env bash
# Unattended orchestrator: wait for Stage A (estimation) to finish, gate it,
# then drive the Stage B AD-off ladders for both worlds.
# Plan: plans/20260614_overnight-two-worlds-AD-off-validation-run.md
set -u

REPO="/home/shared/github/llorracc/HAFiscal-Latest"
HA="$REPO/Code/HA-Models"
FPC="$HA/FromPandemicCode"
LOGS="$HA/overnight_run_logs"
JOURNAL="$LOGS/JOURNAL.md"
PYTHON="$REPO/.venv/bin/python"
export PATH="$REPO/.venv/bin:$PATH"
STAGEA_PID="${1:-}"           # launcher PID to wait on (optional)

NONAD="base,Check,UI,TaxCut,recession,recessionUI,recessionCheck,recessionTaxCut"
PKLS="base Check UI TaxCut recession recessionUI recessionCheck recessionTaxCut"
CORES=$(nproc)
C_CHEAP=$(( CORES < 8 ? CORES : 8 ))
C_BASE=$(( CORES < 4 ? CORES : 4 ))

DEFAULT_BETAS="$HA/Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt"
ASCORR_BETAS="$HA/Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC_ascorrected.txt"
SPLURGE="$HA/Target_AggMPCX_LiquWealth/Result_AllTarget_ESC.txt"

jr () { echo "- $(date '+%m-%d %H:%M') $*" >> "$JOURNAL"; }
log () { echo "[orch $(date '+%H:%M:%S')] $*"; }

nonempty () { [ -s "$1" ]; }
# A betas file is usable only if it exists, is non-empty, AND is at least as
# new as the freshly-written splurge file (guards against STALE pre-run betas
# from earlier runs being mistaken for this run's output if Step 2 crashes).
betas_ok () { [ -s "$1" ] && [ -s "$SPLURGE" ] && [ ! "$1" -ot "$SPLURGE" ]; }

# ----------------------------------------------------------------------------
# Wait for Stage A: launcher process gone (if PID known) OR all outputs present.
# ----------------------------------------------------------------------------
log "orchestrator started; CORES=$CORES C_CHEAP=$C_CHEAP C_BASE=$C_BASE STAGEA_PID=$STAGEA_PID"
jr "orchestrate_stageB.sh started (waiting for Stage A; C_CHEAP=$C_CHEAP C_BASE=$C_BASE)"

while true; do
    alive=0
    if [ -n "$STAGEA_PID" ] && kill -0 "$STAGEA_PID" 2>/dev/null; then alive=1; fi
    have_default=$(betas_ok "$DEFAULT_BETAS" && echo 1 || echo 0)
    have_ascorr=$(betas_ok "$ASCORR_BETAS" && echo 1 || echo 0)
    have_splurge=$(nonempty "$SPLURGE" && echo 1 || echo 0)
    if [ "$alive" = "0" ]; then
        log "Stage A launcher no longer running. files: default=$have_default ascorr=$have_ascorr splurge=$have_splurge"
        break
    fi
    # also break early if everything is already produced (launcher tail work)
    if [ "$have_default$have_ascorr$have_splurge" = "111" ]; then
        log "all 3 Stage A outputs present while launcher still alive; waiting 120s for launcher to settle"
        sleep 120
    fi
    sleep 120
done

# ----------------------------------------------------------------------------
# Stage A gate
# ----------------------------------------------------------------------------
fatal_A=0
grep -qiE 'Traceback \(most recent call last\)' "$LOGS/stageA_estimation.log" 2>/dev/null && fatal_A=1
have_default=$(betas_ok "$DEFAULT_BETAS" && echo 1 || echo 0)
have_ascorr=$(betas_ok "$ASCORR_BETAS" && echo 1 || echo 0)
have_splurge=$(nonempty "$SPLURGE" && echo 1 || echo 0)
jr "Stage A gate: splurge=$have_splurge default_betas(fresh)=$have_default ascorr_betas(fresh)=$have_ascorr fatal_traceback=$fatal_A"
log "Stage A gate: splurge=$have_splurge default=$have_default ascorr=$have_ascorr fatal=$fatal_A"

WORLDS=""
if [ "$have_splurge" = "1" ] && [ "$have_default" = "1" ]; then WORLDS="default"; fi
if [ "$have_splurge" = "1" ] && [ "$have_ascorr" = "1" ]; then WORLDS="$WORLDS as-corrected"; fi
if [ -z "$WORLDS" ]; then
    jr "Stage A produced no usable (splurge+betas) world — STOP. Cannot run Stage B. See stageA_estimation.log."
    log "no usable world betas; stopping."
    exit 1
fi
jr "Stage A usable worlds for Stage B: [$WORLDS]"

# ----------------------------------------------------------------------------
# Stage B rung runner + §5 gate
# ----------------------------------------------------------------------------
# run_rung WORLD PARAM C [extra args...]
run_rung () {
    local world="$1" param="$2" C="$3"; shift 3
    local extra="$*"
    local drlog="$LOGS/stageB_${world}_${param}.log"
    jr "Stage B START world=$world param=$param C=$C extra='$extra'"
    log "run_rung world=$world param=$param C=$C extra='$extra'"
    ( cd "$FPC" && HAFISCAL_WORLD="$world" "$PYTHON" run_welfare6_parallel.py \
        --parametrization "$param" --scenarios "$NONAD" \
        --max-gpu-slots 0 --max-parallel "$C" --max-cpu-slots "$C" \
        --out-dir "welfare6_${world}_${param}" --table-dir "Tables/${world}_${param}" \
        $extra ) > "$drlog" 2>&1
    local rc=$?
    echo "$rc"
}

# gate_rung WORLD PARAM RC -> 0 pass / 1 fail
gate_rung () {
    local world="$1" param="$2" rc="$3"
    local drlog="$LOGS/stageB_${world}_${param}.log"
    local outdir="$FPC/welfare6_${world}_${param}"
    local fail=0 reason=""
    [ "$rc" = "0" ] || { fail=1; reason="rc=$rc"; }
    local missing=""
    for p in $PKLS; do [ -s "$outdir/$p.pkl" ] || missing="$missing $p"; done
    [ -n "$missing" ] && { fail=1; reason="$reason missing_pkls:$missing"; }
    grep -qE 'FAIL rc=' "$drlog" 2>/dev/null && { fail=1; reason="$reason FAIL_rc_line"; }
    if [ -d "$FPC/welfare6_parallel_logs/$param" ]; then
        grep -qlE 'Traceback \(most recent call last\)' "$FPC/welfare6_parallel_logs/$param"/*.log 2>/dev/null \
            && { fail=1; reason="$reason scenario_traceback"; }
    fi
    if [ "$fail" = "0" ]; then
        jr "Stage B GATE PASS world=$world param=$param (all 8 non-AD pkls; rc0; no FAIL/traceback)"
        return 0
    else
        jr "Stage B GATE FAIL world=$world param=$param :$reason"
        return 1
    fi
}

# ladder for one world: HS_Only -> Reduced_Run -> Baseline, gated. Baseline retries on failure.
ladder () {
    local world="$1"
    jr "=== Stage B ladder START world=$world ==="
    for param in HS_Only Reduced_Run; do
        local rc; rc=$(run_rung "$world" "$param" "$C_CHEAP")
        if ! gate_rung "$world" "$param" "$rc"; then
            jr "STOP ladder world=$world at $param (red rung; not escalating). See stageB_${world}_${param}.log"
            return 1
        fi
    done
    # Baseline (heavy) with RAM-aware retries
    local rc; rc=$(run_rung "$world" Baseline "$C_BASE")
    if gate_rung "$world" Baseline "$rc"; then jr "ladder world=$world COMPLETE through Baseline"; return 0; fi
    jr "Baseline FAIL world=$world C=$C_BASE — retry C=2 (RAM-conservative)"
    rc=$(run_rung "$world" Baseline 2)
    if gate_rung "$world" Baseline "$rc"; then jr "ladder world=$world COMPLETE (Baseline C=2)"; return 0; fi
    jr "Baseline FAIL world=$world C=2 — retry C=1 + --agent-count-total 5000"
    rc=$(run_rung "$world" Baseline 1 --agent-count-total 5000)
    if gate_rung "$world" Baseline "$rc"; then jr "ladder world=$world COMPLETE (Baseline C=1, N=5000)"; return 0; fi
    jr "Baseline RED world=$world after all retries — documented red rung. See stageB_${world}_Baseline.log"
    return 1
}

for w in $WORLDS; do
    ladder "$w" || true   # never let one world stop the other
done

jr "=== ORCHESTRATOR DONE. Worlds attempted: [$WORLDS]. See per-rung logs + gate lines above. ==="
log "orchestrator done."
