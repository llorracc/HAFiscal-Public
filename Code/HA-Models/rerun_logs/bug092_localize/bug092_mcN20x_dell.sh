#!/bin/bash
# BUG-092 large-N convergence test, SECOND point (2026-08-25 ~12:00). The 40x arm of
# bug092_largeN_dell.sh was OOM-killed at 11:12 -- 13 python processes at 7-12 GB RSS each
# (4 shock-type fork workers x 4 duration-fork children, HAFISCAL_DUR_WORKERS auto = ncpu//8),
# 60 GB RAM + 8 GB swap exhausted -- and systemd's OOMPolicy=stop then took the whole tmux pane
# scope, Claude session included, down with it. This rerun: 20x agents (Reduced_Run 1x = D 465 /
# H 2635 / C 1900), the inner duration fork OFF (HAFISCAL_DUR_WORKERS=1 -> only the 4 shock
# workers, ~8-10 GB each), launched in its OWN transient systemd unit with MemoryMax so a
# blow-up can only kill this run:
#   systemd-run --user --unit=bug092-mcN20x -p MemoryMax=50G -p MemorySwapMax=2G -p OOMPolicy=continue \
#     --collect /bin/bash -c 'bash <this file> > largeN20x_dell.out 2>&1'
# Same readout as the 10x arm: multiplier rows, pLvl drift lines, base AggCons level vs the TM's
# converged run (Figures/Reduced_Run_tm_uncapped; 1x MC 1.160, 10x 1.029). The Cratio-peak lines
# are printed for the record only -- that comparison was WITHDRAWN at 11:05 (TM records its
# belief/state path, MC the realized AggCons/base ratio; not comparable objects).
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; PY=$REPO/.venv/bin/python
OUT=$REPO/Code/HA-Models/rerun_logs/bug092_localize; mkdir -p $OUT
cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1
export HAFISCAL_POLICY_STORE_DIR=$HOME/.cache/hafiscal/policy_store_bug092 HAFISCAL_DRIFT_HARD_FAIL=0
export HAFISCAL_DUR_WORKERS=1
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
for MULT in 20; do
  D=$((465*MULT)); H=$((2635*MULT)); C=$((1900*MULT)); tag=mcN${MULT}x_uncapped
  stamp "$tag start (D=$D H=$H C=$C, DUR_WORKERS=1)"; rm -rf Tables/Reduced_Run_$tag Figures/Reduced_Run_$tag
  env HAFISCAL_AGENTCOUNT_D=$D HAFISCAL_AGENTCOUNT_H=$H HAFISCAL_AGENTCOUNT_C=$C HAFISCAL_MULTIPLIER_ENGINE=mc HAFISCAL_SIM_METHOD=MC HAFISCAL_FIGS_SUFFIX=_$tag $PY AggFiscalMAIN_reduced.py > $OUT/$tag.log 2>&1; rc=$?
  stamp "$tag end rc=$rc"; grep "Multiplier" Tables/Reduced_Run_$tag/Multiplier_candidate.tex 2>/dev/null | cut -c1-110
  grep -h "\[drift" $OUT/$tag.log | grep -i "log(p)" | head -6 | cut -c1-150; grep -h "Traceback" -A3 $OUT/$tag.log | tail -3 | cut -c1-150
  $PY - $tag <<'EOF'
import pickle, sys, numpy as np
tag = sys.argv[1]
def L(t, name): return pickle.load(open(f"Figures/Reduced_Run_{t}/{name}.csv", "rb"))
try:
    bT, bM = L("tm_uncapped", "base_results"), L(tag, "base_results")
    cT, cM = np.asarray(bT["AggCons"], float)[:8].mean(), np.asarray(bM["AggCons"], float)[:8].mean()
    print(f"   base AggCons per 1x-population: TM {cT:.1f}  MC({tag}) {cM:.1f}  -> TM/MC = {cT/cM:.3f}  (1x MC was 1.160; 10x 1.029)")
    for pol in ("recession", "recessionCheck", "recessionUI"):
        aT, aM = L("tm_uncapped", f"{pol}_all_results_AD"), L(tag, f"{pol}_all_results_AD")
        pk = lambda lst: np.mean([np.abs(np.asarray(r["Cratio_hist"], float)[:8] - 1).max() for r in lst[:3]])
        print(f"   [record only, comparison withdrawn] {pol:16s} peak |Cratio-1|: TM {pk(aT):.4f}  MC {pk(aM):.4f}")
except Exception as e:
    print("   compare failed:", e)
EOF
done
echo "LARGEN20 DONE $(date +%H:%M:%S)"
