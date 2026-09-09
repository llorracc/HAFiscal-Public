#!/bin/bash
# gamma = 3 arm (robustness appendix, risk-aversion block) on the current defaults.
# Follows ~/coldrun_2026-08/crra_chain.sh of 2026-08-20 exactly, minus the retired G2:
#   G1  Step-1 arm at gamma=3, 8 concurrent grid shards -> min-f merge -> Result_CRRA_3.0{,_ESC}.txt
#   G2  RETIRED 2026-08-20 23:30 (BUG-084): production_dist_aGrid_max's "beta=1.01 clips to the
#       cap" premise is stale under the aggregate-cusp cap and it returned 19,900 at every gamma.
#       Every appendix row runs on the production 1300; the College top atom's tail is LOGGED (G3b).
#   G3  Step 2 at gamma=3 with the re-estimated splurge passed as argv[5]
#   G4  fit-table pass (AllResults_*, the Lorenz CRRA figure's input; BUG-080 workaround)
#   G5  the arm itself: 5a + three welfare seeds
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest
PY=$REPO/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/appendix_20260904
export HAFISCAL_FTI_REPO=${HAFISCAL_FTI_REPO:-/home/shared/github/llorracc/fast-time-iteration}
source $LOG/env.sh; source $LOG/common.sh
unset HAFISCAL_SPLURGE_FILE          # gamma=3 resolves its own Result_CRRA_3.0 (Parameters.py:105)
NSTART=8                             # legend: "Multistart grid (CRRA=3): 8 startpoints"
G=3; STEM=Result_CRRA_${G}.0; DSTEM=DiscFacEstim_CRRA_${G}.0_R_1.01
stamp "CRRA3 chain start"

# ---- G1: Step-1 shards --------------------------------------------------------------------
if [ ! -f "$LOG/crra3_s1.done" ]; then
  builtin cd "$S1DIR" || { fail crra3_s1cd; exit 9; }
  [ -f "${STEM}_ESC.txt" ] && cp -p "${STEM}_ESC.txt" "${STEM}_ESC_${SUF}.txt"
  rm -f "${STEM}_startpoint"*"_ESC.txt"
  PIDS=""; for K in $(seq 1 $NSTART); do
    env HAFISCAL_STEP1_MULTISTART=1 HAFISCAL_STEP1_PLOT=0 HAFISCAL_STEP1_RUN_ESTIMATION=0 \
        HAFISCAL_STEP1_OTHER_CRRA="$G" HAFISCAL_STEP1_START_SUBSET="$K" \
        OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
        "$PY" Estimation_BetaNablaSplurge.py > "$LOG/crra3_s1_${K}.log" 2>&1 &
    PIDS="$PIDS $!"; done
  rc=0; for p in $PIDS; do wait "$p" || rc=1; done
  [ $rc -eq 0 ] || { fail crra3_s1; exit 9; }
  "$PY" - "$LOG" "$S1DIR" "$G" "$NSTART" <<'PYEOF' || { fail crra3_s1merge; exit 9; }
import re, sys, os
LOG, S1, G, N = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
stem = "Result_CRRA_%.1f" % float(G)
rx = re.compile(r"^([0-9.eE+-]+) ([0-9.eE+-]+) ([0-9.eE+-]+) ([0-9.eE+-]+)\s*$", re.M)
best, seen = None, 0
for k in range(1, N + 1):
    log = os.path.join(LOG, f"crra3_s1_{k}.log"); res = os.path.join(S1, f"{stem}_startpoint{k}_ESC.txt")
    if not (os.path.exists(log) and os.path.exists(res)):
        print(f"MERGE: missing start {k}"); continue
    rows = rx.findall(open(log).read())
    if not rows: print(f"MERGE: no eval rows in start {k}"); sys.exit(9)
    fmin = min(float(r[3]) for r in rows); d = eval(open(res).read())
    if 'Error' in d: print(f"  start {k}: Error result, skipped"); continue
    seen += 1; print(f"  start {k}: f_min={fmin:.10g}  {d}  ({len(rows)} evals)")
    if best is None or fmin < best[0]: best = (fmin, k, d)
if best is None or seen < N - 2:
    print(f"MERGE: only {seen} of {N} error-free starts -- not a battery"); sys.exit(9)
print(f"CRRA3 WINNER: start {best[1]}  f={best[0]:.10g}  {best[2]}")
print("  2026-08-20 reference (pre-lambda): 8/8 in one basin, splurge 0.3009 / beta 0.9656 / nabla 0.0472, f 0.00168")
for name in (f"{stem}.txt", f"{stem}_ESC.txt"):
    open(os.path.join(S1, name), "w").write(repr(best[2])); print(f"  canonical written: {name}")
PYEOF
  done_ crra3_s1
fi
SPL=$("$PY" -c "import sys; print(eval(open(sys.argv[1]).read())['splurge'])" "$S1DIR/${STEM}_ESC.txt") || { fail crra3_spl; exit 9; }
echo "  CRRA=3 splurge: $SPL"

# ---- G3: Step 2 at gamma=3 ------------------------------------------------------------------
park CRRA3 "$DSTEM"
s2 CRRA3 "$DSTEM" 1.01 3.0 0.7 0.5 "$SPL" || exit 9

# ---- G3b: tail diagnostic of the estimated College top atom (BUG-084 replacement for G2) -----
builtin cd "$FPC" || exit 9
"$PY" - "$SPL" "$RES/${DSTEM}_ESC.txt" <<'PYEOF' 2>&1 | tail -n 3
import sys, os, re
SPL, CAL = sys.argv[1], sys.argv[2]
sys.argv = ["estim", "1.01", "3.0", "0.7", "0.5", SPL]
sys.path.insert(0, os.path.abspath(".."))
import numpy as np, EstimParameters as ep, adaptive_grid_tm as ag
row = [l for l in open(CAL) if "'EducationGroup': 2" in l][0]
b = float(re.search(r"'beta': ([0-9.eE+-]+)", row).group(1)); n = float(re.search(r"'nabla': ([0-9.eE+-]+)", row).group(1))
grid, mass, beta_top = ag.college_top_ergodic(b, n, 20000.0, interpretation="ESC", aCount=4000)
cdf = np.cumsum(mass); cdf /= cdf[-1]
q = float(np.interp(1 - 1e-4, cdf, grid)); above = float(mass[grid > 1300].sum())
print(f"[tail-diag CRRA=3] College top atom beta_top={beta_top:.6f} (cap {ep.gic_capped_beta(2, ep.theGICfactor):.6f}): "
      f"q(1-1e-4)={q:.0f}, mass above 1300 = {above:.2e}  (main spec at gamma=2, pre-lambda: 8968, 3.0e-3)")
PYEOF

# ---- G4: fit-table pass (Lorenz CRRA figure's input) ----------------------------------------
if [ ! -f "$LOG/crra3_allresults.done" ]; then
  stamp "G4[CRRA3] fit-table pass"
  HAFISCAL_NM_IN_PLACE=0 HAFISCAL_SKIP_ESTIMATION_OPTIMIZE=1 "$PY" EstimAggFiscalMAIN.py 1.01 3.0 0.7 0.5 "$SPL" \
      > "$LOG/crra3_allresults.log" 2>&1 || { fail crra3_allresults; exit 9; }
  done_ crra3_allresults
fi

# ---- G5: the arm ----------------------------------------------------------------------------
cfg CRRA3 || exit 9
stamp "CRRA3 chain done"
