#!/bin/bash
# m5 queue, robustness-appendix re-run on the current defaults (2026-09-04).
# Runs in the LOCAL-disk cold-run clone (never the synced ~/GitHub volume), which is at
# e35736a3 -- computationally identical to HEAD (the only later code changes are
# coldrun_verdict.py and hank_incidence_by_educ.py, neither on a run path) and already holds
# a current-defaults Baseline reading 1.318/1.250/1.086, the same as dell's.
# LowerUBnoB_histB follows LowerUBnoB on this machine so it inherits that calibration directly.
set -u
REPO=$HOME/hafiscal-coldrun-fixedtree-20260903
PY=$HOME/GitHub/llorracc/HAFiscal-Latest/.venv/bin/python
LOG=$REPO/Code/HA-Models/rerun_logs/appendix_20260904
mkdir -p "$LOG"
export HAFISCAL_FTI_REPO=${HAFISCAL_FTI_REPO:-$HOME/GitHub/llorracc/fast-time-iteration}
export HAFISCAL_POLICY_STORE_DIR=$REPO/appendix_store
source $LOG/env.sh; source $LOG/common.sh
exec >> "$LOG/m5.out" 2>&1
echo "===== M5 QUEUE start $(date +%F\ %H:%M:%S) at $(git -C $REPO rev-parse --short HEAD) on $(uname -n) ====="

builtin cd "$REPO/Code/HA-Models/FromPandemicCode" || exit 9

# --- m5 upgrade gate (multiplier engine) AND publication of the AD equilibria ----------------
# The welfare battery runs under ad_equilibrium_share, so its four AD scenarios CONSUME the
# equilibria that the spending program (5a) publishes into the policy store; with this queue's
# own store they must be published here first (the 2026-09-03 cold run put its equilibria in
# that run's coldrun_store, which is keyed to that run, not to this one). Running 5a here also
# gives m5 the same byte-for-byte post-upgrade check dell got on this engine: the multipliers
# must reproduce this clone's 2026-09-03 Tables/Baseline/Multiplier_candidate.tex exactly.
if [ ! -f "$LOG/Baseline_s5a.done" ]; then
  T0=$(date +%s); stamp "5a[Baseline] start (m5 upgrade gate + AD-equilibrium publication)"
  env HAFISCAL_FIGS_SUFFIX=_upgradecheck "$PY" AggFiscalMAIN_reduced.py --parametrization Baseline \
      > "$LOG/gate_5a_Baseline.log" 2>&1 || { fail Baseline_s5a; exit 9; }
  stamp "5a[Baseline] end wall=$(( ($(date +%s)-T0)/60 ))min"
  A=Tables/Baseline/Multiplier_candidate.tex; B=Tables/Baseline_upgradecheck/Multiplier_candidate.tex
  if cmp -s "$A" "$B"; then
    echo "UPGRADE GATE (multipliers) PASSED on $(uname -n): 5a reproduces the 2026-09-03 record"
    grep "AD effect)" "$B"
  else
    echo "UPGRADE GATE (multipliers) FAILED on $(uname -n)"; diff "$A" "$B" | head -20
    fail upgrade_gate_mult; exit 9
  fi
  done_ Baseline_s5a
fi

# --- this machine's own Baseline reference, S=3, into Baseline_seed{0,1,2} ------------------
# Seed 0 is ALSO the post-upgrade reproduction gate for the welfare path: this clone's
# Tables/Baseline holds the 2026-09-03 seed-0 tables, so Baseline_seed0 must match them.
for K in 0 1 2; do
  [ -f "$LOG/Baseline_s5b_seed$K.done" ] && continue
  stamp "w6[Baseline] seed $K start"
  "$PY" run_welfare6_parallel.py --parametrization Baseline --seed-offset $K \
      --out-dir "welfare6_scenario_results_Baseline_seed$K" --table-dir "Tables/Baseline_seed$K" \
      > "$LOG/w6_Baseline_seed$K.log" 2>&1 || { fail Baseline_s5b_seed$K; exit 9; }
  stamp "w6[Baseline] seed $K end tables=$(ls Tables/Baseline_seed$K/*.tex 2>/dev/null | wc -l)"
  done_ Baseline_s5b_seed$K
done

# post-upgrade gate: seed 0 must reproduce the 2026-09-03 tables byte-for-byte (no timestamps
# in these tabulars, so cmp is a valid identity test). A difference here is the system upgrade
# and everything downstream would be uninterpretable -- HALT (cascade-gate rule).
for f in welfare4_candidate.tex welfare6_candidate.tex; do
  if ! cmp -s "Tables/Baseline/$f" "Tables/Baseline_seed0/$f"; then
    echo "UPGRADE GATE FAILED: Tables/Baseline_seed0/$f differs from the 2026-09-03 Tables/Baseline/$f"
    diff "Tables/Baseline/$f" "Tables/Baseline_seed0/$f" | head -20
    fail upgrade_gate; exit 9
  fi
done
echo "UPGRADE GATE PASSED on $(uname -n): Baseline welfare seed 0 reproduces the 2026-09-03 tables byte-for-byte"

# --- the three re-estimated arms -----------------------------------------------------------
park Rfree_1005 DiscFacEstim_CRRA_2.0_R_1.005
s2  Rfree_1005  DiscFacEstim_CRRA_2.0_R_1.005  1.005 2.0 0.7 0.5 || exit 9
cfg Rfree_1005 || exit 9

park Rfree_1015 DiscFacEstim_CRRA_2.0_R_1.015
s2  Rfree_1015  DiscFacEstim_CRRA_2.0_R_1.015  1.015 2.0 0.7 0.5 || exit 9
cfg Rfree_1015 || exit 9

park LowerUBnoB DiscFacEstim_CRRA_2.0_R_1.01_altBenefits
s2  LowerUBnoB  DiscFacEstim_CRRA_2.0_R_1.01_altBenefits  1.01 2.0 0.3 0.15 || exit 9
cfg  LowerUBnoB || exit 9
park LowerUBnoB_histB
cfgB LowerUBnoB || exit 9

echo "===== M5 QUEUE DONE $(date +%F\ %H:%M:%S) ====="
