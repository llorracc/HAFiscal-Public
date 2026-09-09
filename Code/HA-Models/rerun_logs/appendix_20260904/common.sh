# Robustness-appendix re-run on the CURRENT defaults (2026-09-04). Shared stage functions.
#
# Why: every appendix arm on disk was produced 2026-08-20..28, i.e. BEFORE the lambda = 0.44
# growth downscaling bundled with the cap removal (installed 2026-08-29, fc1daf94) and before
# the BUG-120/121 calibration fix (2026-09-03). p29_common.sh of 2026-08-27 says in its own
# header "Step-2 calibrations are NOT re-run: the installed ones (2026-08-20/21) are the same
# vintage as the Baseline calibration of record" -- true then, false the moment lambda landed.
# So this run re-estimates each arm's own (beta, nabla) first (owner ruling 2026-09-04), which
# is what p29 did not do; the 5a/5b stages below are p29_common.sh's cfg/cfgB unchanged.
#
# Layout expected by Code/HA-Models/robustness_appendix_tables.py:
#   window arm  -> Tables/<NAME>/Multiplier_candidate.tex, Tables/<NAME>_seed{0,1,2}/welfare4_candidate.tex
#   history arm -> Tables/<NAME>_histB{,_seed{0,1,2}}          (HAFISCAL_FIGS_SUFFIX=_histB)
# Previous artefacts are moved aside as *_pre_lambda_20260904, never deleted.
set -u
: "${REPO:?}" "${PY:?}" "${LOG:?}"
FPC="$REPO/Code/HA-Models/FromPandemicCode"
RES="$REPO/Code/HA-Models/Results"
S1DIR="$REPO/Code/HA-Models/Target_AggMPCX_LiquWealth"
SUF=pre_lambda_20260904
PARKDIR="Tables/_parked_20260904"
REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo /home/shared/github/llorracc/HAFiscal-Latest)}"

stamp() { echo "=== $1 $(date +%F\ %H:%M:%S)"; }
fail()  { echo "=== HALT at $1 $(date +%F\ %H:%M:%S) ==="; touch "$LOG/$1.failed"; }
done_() { touch "$LOG/$1.done"; }

# ---- park an arm's previous artefacts (5a dir, welfare seed dirs, calibration) -------------
park() { local NAME=$1 STEM=${2:-}
  # idempotent: a resumed queue must not park what it has already produced
  [ -f "$LOG/${NAME}_parked.done" ] && { echo "  park[$NAME] already done"; return 0; }
  # Parked artefacts move OUT of the Tables/ glob namespace, into a subdirectory.
  # Renaming in place (the 2026-09-04 first cut) left Tables/<NAME>_seed0_<SUF>, which still
  # matches the readers' "<NAME>_seed*" glob -- config_cells then averaged the fresh seeds
  # together with the parked pre-lambda ones (Rspell_4 came back S=6, AD check 2.345 instead
  # of 3.194). A subdirectory cannot match, because glob does not recurse.
  mkdir -p "$PARKDIR"
  for d in "Tables/$NAME" Tables/${NAME}_seed*; do
    [ -d "$d" ] || continue
    case "$d" in Tables/_parked_*) continue;; esac
    [ -e "$PARKDIR/$(basename "$d")_$SUF" ] && continue
    mv "$d" "$PARKDIR/$(basename "$d")_$SUF" && echo "  parked $d -> $PARKDIR/"
  done
  # An arm directory holds TRACKED artefacts as well as run outputs (Tables/ADElas has 12,
  # Tables/Splurge0 has 22 of which 2 are in LOCKED_TABLES.manifest). Moving the directory
  # therefore deletes committed files from the working tree and breaks test_locked_tables.
  # Restore anything tracked straight back from HEAD: the parked copy is kept, the frozen
  # files stay where the guards expect them, and untracked candidates are not touched.
  git -C "$REPO_ROOT" checkout -- Code/HA-Models/FromPandemicCode/Tables 2>/dev/null || true
  touch "$LOG/${NAME}_parked.done"
  [ -n "$STEM" ] || return 0
  for f in "$RES/${STEM}_ESC.txt" "$RES/${STEM}_TM_a_ESC.txt"; do
    [ -f "$f" ] && [ ! -f "${f%.txt}_$SUF.txt" ] && cp -p "$f" "${f%.txt}_$SUF.txt" && echo "  parked $(basename $f)"
  done; return 0
}

# ---- Step 2: three concurrent per-education cold 4-start COBYQA, then assemble --------------
# s2 <tag> <stem> <argv...>   argv = Rfree CRRA IncUnemp IncUnempNoBenefits [Splurge]
s2() { local TAG=$1 STEM=$2; shift 2
  [ -f "$LOG/${TAG}_s2.done" ] && { echo "  s2[$TAG] already done"; return 0; }
  builtin cd "$FPC" || { fail ${TAG}_s2cd; return 9; }
  local T0=$(date +%s); stamp "s2[$TAG] start (args: $*)"
  local PIDS="" rc=0 E
  for E in 0 1 2; do
    rm -f "$RES/${STEM}_edType${E}_TM_a_ESC.txt"
    env HAFISCAL_EDTYPES=$E HAFISCAL_NUM_STARTS=4 HAFISCAL_NM_START_FROM_SAVED=0 HAFISCAL_NM_LOG_EVERY=1 \
        OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
        "$PY" estim_phase2_tm_a.py "$@" > "$LOG/${TAG}_s2g${E}.log" 2>&1 &
    PIDS="$PIDS $!"
  done
  for p in $PIDS; do wait "$p" || rc=1; done
  [ $rc -eq 0 ] || { fail ${TAG}_s2; return 9; }
  # A search end that BINDS is a procedure artifact, not an estimate (BUG-083): surface it.
  grep -h "NABLA_AT_BOX\|MAXFEV_HIT" "$LOG"/${TAG}_s2g*.log | tail -n 5
  "$PY" - "$RES" "$STEM" <<'PYEOF' || { fail ${TAG}_s2assemble; return 9; }
import os, re, sys
RES, STEM = sys.argv[1], sys.argv[2]
rows, params_line = [], None
for g in (0, 1, 2):
    p = os.path.join(RES, f"{STEM}_edType{g}_TM_a_ESC.txt")
    if not os.path.exists(p):
        print(f"ASSEMBLE: missing {p}"); sys.exit(9)
    txt = open(p).read()
    m = re.search(r"^\{'EducationGroup':\s*%d.*\}$" % g, txt, re.M)
    if not m:
        print(f"ASSEMBLE: no edType {g} row in {p}"); sys.exit(9)
    rows.append(m.group(0))
    pm = re.search(r"^Parameters:.*$", txt, re.M)
    if pm: params_line = pm.group(0)
out = "\n".join(rows) + "\n\n" + (params_line or "") + "\n"
for name in (f"{STEM}_TM_a_ESC.txt", f"{STEM}_ESC.txt"):
    open(os.path.join(RES, name), "w").write(out)
print("ASSEMBLED:"); print(out)
PYEOF
  stamp "s2[$TAG] end wall=$(( ($(date +%s)-T0)/60 ))min"; done_ ${TAG}_s2
}

# ---- Step 5a + three welfare seeds + the seed band (p29_common.sh cfg, unchanged) -----------
cfg() { local NAME=$1 TAG=${2:-$1} SFX=${3:-}
  builtin cd "$FPC" || { fail ${TAG}_cd; return 9; }
  if [ ! -f "$LOG/${TAG}_s5a.done" ]; then
    local T0=$(date +%s); stamp "5a[$TAG] start"
    env ${SFX:+HAFISCAL_FIGS_SUFFIX=$SFX} "$PY" AggFiscalMAIN_reduced.py --parametrization "$NAME" > "$LOG/mult_$TAG.log" 2>&1 || { fail ${TAG}_s5a; return 9; }
    stamp "5a[$TAG] end wall=$(( ($(date +%s)-T0)/60 ))min"
    grep "AD effect)\|expenditure during" "Tables/$TAG/Multiplier_candidate.tex" 2>/dev/null
    done_ ${TAG}_s5a
  fi
  local K
  for K in 0 1 2; do
    [ -f "$LOG/${TAG}_s5b_seed$K.done" ] && continue
    local T1=$(date +%s); stamp "w6[$TAG] seed $K start"
    "$PY" run_welfare6_parallel.py --parametrization "$NAME" --seed-offset $K \
        --out-dir "welfare6_scenario_results_${TAG}_seed$K" --table-dir "Tables/${TAG}_seed$K" \
        > "$LOG/w6_${TAG}_seed$K.log" 2>&1 || { fail ${TAG}_s5b_seed$K; return 9; }
    stamp "w6[$TAG] seed $K end wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/${TAG}_seed$K/*.tex 2>/dev/null | wc -l)"
    done_ ${TAG}_s5b_seed$K
  done
  stamp "band[$TAG]"
  "$PY" compute_welfare6_se_table.py --summaries Tables/${TAG}_seed{0,1,2}/welfare6_parallel_summary.json \
      --out "$LOG/welfare6_${TAG}_S3_seed_band.tex" 2>&1 | tail -n 4
  done_ ${TAG}
}

# the history-policy arm of the same config (fifth appendix block, Econ-7)
cfgB() { local rc=0
  export HAFISCAL_UI_EXTENSION_POLICY=history
  cfg "$1" "${1}_histB" _histB || rc=$?
  export HAFISCAL_UI_EXTENSION_POLICY=window
  return $rc; }
