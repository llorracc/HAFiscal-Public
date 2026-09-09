#!/bin/bash
# The no-splurge (Splurge=0) appendix -- Subfiles/Appendix-NoSplurge.tex -- on the current
# defaults. Follows ~/coldrun_2026-08/nosplurge_run.sh of 2026-08-20, whose outputs are the
# stale ones (Results/*Splurge0* 08-20, Tables/Splurge0 08-23), with the per-seed table dirs
# that run corrected mid-flight and the pickle copy its N4 needed.
#   N1  Step-1 splurge=0 arm, FOUR grid shards (not nine -- shards 5-9 IndexError) -> merge
#   N2  Step 3: the Step-2 engine at splurge=0, three concurrent education groups -> assemble
#   N3  fit-table pass + Lorenz/IMPC figures + the Step-1 _splurge0 comparison figures
#   N4  Splurge0 multipliers (LEGACY-LAYOUT TRAP: Output_Results' Splurge0 branch reads the
#       baseline multiplier pickles from the top-level Figures/, the baseline run writes them
#       to Figures/Baseline/ -- copy them across first or the run fails late)
#   N5  Splurge0 welfare battery, S=3, per-seed dirs
#   N6  welfare6-SplurgeComp composed from the Baseline and Splurge0 welfare6 tables
# NOT produced: UIextension_CompSplurge0.pdf (needs base_results_full, an MC-path pickle the
# TM runs do not save) -- flagged, not silently skipped.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest
PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/appendix_20260904
export HAFISCAL_FTI_REPO=${HAFISCAL_FTI_REPO:-/home/shared/github/llorracc/fast-time-iteration}
source $LOG/env.sh; source $LOG/common.sh
unset HAFISCAL_SPLURGE_FILE
stamp "NOSPLURGE chain start"

# ---- N1: Step-1 splurge=0 arm ---------------------------------------------------------------
if [ ! -f "$LOG/ns_s1.done" ]; then
  builtin cd "$S1DIR" || { fail ns_s1cd; exit 9; }
  for f in Result_AllTarget_Splurge0.txt Result_AllTarget_Splurge0_ESC.txt; do
    [ -f "$f" ] && [ ! -f "${f%.txt}_${SUF}.txt" ] && cp -p "$f" "${f%.txt}_${SUF}.txt"
  done
  rm -f Result_AllTarget_Splurge0_startpoint*.txt
  PIDS=""; for K in 1 2 3 4; do
    env HAFISCAL_STEP1_MULTISTART=1 HAFISCAL_STEP1_PLOT=0 HAFISCAL_STEP1_RUN_ESTIMATION=0 \
        HAFISCAL_STEP1_SPLURGE0=1 HAFISCAL_STEP1_START_SUBSET="$K" \
        OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
        "$PY" Estimation_BetaNablaSplurge.py > "$LOG/ns_s1_${K}.log" 2>&1 &
    PIDS="$PIDS $!"; done
  rc=0; for p in $PIDS; do wait "$p" || rc=1; done
  [ $rc -eq 0 ] || { fail ns_s1; exit 9; }
  "$PY" - "$LOG" "$S1DIR" <<'PYEOF' || { fail ns_s1merge; exit 9; }
import re, sys, os
LOG, S1 = sys.argv[1], sys.argv[2]
rx = re.compile(r"^([0-9.eE+-]+) ([0-9.eE+-]+) ([0-9.eE+-]+) ([0-9.eE+-]+)\s*$", re.M)
best = None
for k in range(1, 5):
    log = os.path.join(LOG, f"ns_s1_{k}.log"); res = os.path.join(S1, f"Result_AllTarget_Splurge0_startpoint{k}.txt")
    if not (os.path.exists(log) and os.path.exists(res)):
        print(f"N1 MERGE: missing start {k}"); continue
    rows = rx.findall(open(log).read())
    if not rows: print(f"N1 MERGE: no eval rows in start {k}"); sys.exit(9)
    fmin = min(float(r[3]) for r in rows); d = eval(open(res).read())
    if 'Error' in d: print(f"  start {k}: Error result, skipped"); continue
    print(f"  start {k}: f_min={fmin:.10g}  {d}  ({len(rows)} evals)")
    if best is None or fmin < best[0]: best = (fmin, k, d)
if best is None: print("N1 MERGE: no error-free start"); sys.exit(9)
d = dict(best[2]); d.setdefault('splurge', 0)   # the arm's dict has no 'splurge' key; consumers require it
print(f"N1 WINNER: start {best[1]}  f={best[0]:.10g}  {d}")
print("  2026-08-20 reference (pre-lambda): start 4, (beta 0.9263754, nabla 0.0900113), f 0.0165038")
for name in ("Result_AllTarget_Splurge0.txt", "Result_AllTarget_Splurge0_ESC.txt"):
    open(os.path.join(S1, name), "w").write(repr(d)); print(f"  canonical written: {name}")
PYEOF
  done_ ns_s1
fi

# ---- N2: Step 3 -----------------------------------------------------------------------------
DSTEM=DiscFacEstim_CRRA_2.0_R_1.01_Splurge0
for f in "$RES/${DSTEM}_ESC.txt" "$RES/${DSTEM}_TM_a_ESC.txt"; do
  [ -f "$f" ] && [ ! -f "${f%.txt}_${SUF}.txt" ] && cp -p "$f" "${f%.txt}_${SUF}.txt"
done
s2 Splurge0 "$DSTEM" 1.01 2.0 0.7 0.5 0 || exit 9

# ---- N3: fit-table pass + figures ------------------------------------------------------------
if [ ! -f "$LOG/ns_post.done" ]; then
  builtin cd "$FPC" || { fail ns_postcd; exit 9; }
  stamp "N3 fit-table pass (NM_IN_PLACE=0, BUG-080)"
  HAFISCAL_NM_IN_PLACE=0 HAFISCAL_SKIP_ESTIMATION_OPTIMIZE=1 "$PY" EstimAggFiscalMAIN.py 1.01 2.0 0.7 0.5 0 \
      > "$LOG/ns_allresults.log" 2>&1 || { fail ns_allresults; exit 9; }
  for s in CreateLPfig.py CreateIMPCfig.py; do
    stamp "N3 $s"; "$PY" "$s" > "$LOG/ns_${s%.py}.log" 2>&1 || { fail ns_${s%.py}; exit 9; }
  done
  builtin cd "$S1DIR" || { fail ns_s1cd2; exit 9; }
  stamp "N3 Step-1 output section (both arms -> the _splurge0 comparison figures)"
  env HAFISCAL_STEP1_RUN_ESTIMATION=0 HAFISCAL_STEP1_PLOT=1 "$PY" Estimation_BetaNablaSplurge.py \
      > "$LOG/ns_s1_plots.log" 2>&1 || { fail ns_s1plots; exit 9; }
  done_ ns_post
fi

# ---- N4: Splurge0 multipliers ------------------------------------------------------------------
builtin cd "$FPC" || exit 9
if [ ! -f "$LOG/Splurge0_s5a.done" ]; then
  park Splurge0
  cp -p Figures/Baseline/C_Multiplier_Baseline_Results.csv Figures/Baseline/NPV_Multiplier_Baseline_Results.csv Figures/ \
      || { fail ns_pickles; exit 9; }
  T0=$(date +%s); stamp "5a[Splurge0] start"
  HAFISCAL_TM_A_INDEXED=1 "$PY" AggFiscalMAIN_reduced.py --splurge0 > "$LOG/mult_Splurge0.log" 2>&1 || { fail Splurge0_s5a; exit 9; }
  stamp "5a[Splurge0] end wall=$(( ($(date +%s)-T0)/60 ))min"
  grep "AD effect)" Tables/Splurge0/Multiplier_candidate.tex 2>/dev/null
  done_ Splurge0_s5a
fi

# ---- N5: Splurge0 welfare, S=3 -------------------------------------------------------------------
for K in 0 1 2; do
  [ -f "$LOG/Splurge0_s5b_seed$K.done" ] && continue
  T1=$(date +%s); stamp "w6[Splurge0] seed $K start"
  "$PY" run_welfare6_parallel.py --parametrization Splurge0 --seed-offset $K \
      --out-dir "welfare6_scenario_results_Splurge0_seed$K" --table-dir "Tables/Splurge0_seed$K" \
      > "$LOG/w6_Splurge0_seed$K.log" 2>&1 || { fail Splurge0_s5b_seed$K; exit 9; }
  stamp "w6[Splurge0] seed $K end wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/Splurge0_seed$K/*.tex 2>/dev/null | wc -l)"
  done_ Splurge0_s5b_seed$K
done
"$PY" compute_welfare6_se_table.py --summaries Tables/Splurge0_seed{0,1,2}/welfare6_parallel_summary.json \
    --out "$LOG/welfare6_Splurge0_S3_seed_band.tex" 2>&1 | tail -n 4

# ---- N6: the comparison table (seed 0 of each arm, the battery's own format) -----------------------
"$PY" "$REPO/Code/HA-Models/welfare6_splurgecomp.py" \
    --baseline "$FPC/Tables/Baseline/welfare6_candidate.tex" \
    --splurge0 "$FPC/Tables/Splurge0_seed0/welfare6_candidate.tex" \
    --out "$FPC/Tables/Splurge0/welfare6-SplurgeComp.tex" > "$LOG/ns_n6.log" 2>&1 || { fail ns_n6; exit 9; }
done_ ns_n6
echo "NOTE: UIextension_CompSplurge0.pdf NOT produced -- needs base_results_full (MC-path pickle) for both arms."
stamp "NOSPLURGE chain done"
