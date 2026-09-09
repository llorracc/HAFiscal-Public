#!/bin/bash
# Harvest the 2026-08-25 Baseline S=3 welfare battery on the SHARED AD EQUILIBRIUM (P6):
#   harvest_rebattery_eq.sh default      : dell's Tables/Baseline_eq_seed{0,1,2} -> band gate, SE table,
#                                          tex band, artifact set, shift vs the r2 (own-AD-loop) battery
#   harvest_rebattery_eq.sh as-corrected : pull m5's Tables/Baseline_ac_eq_seed{K}, same
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; HA=$REPO/Code/HA-Models
PY=$REPO/.venv/bin/python; T=$FPC/Tables; A=$REPO/conclusions_private/artifacts_20260825_rebattery_eq
R2=$REPO/conclusions_private/artifacts_20260825_rebattery
cd $REPO
world_harvest() {
  W=$1; case $W in default) tag=eq; rtag=r2;; as-corrected) tag=ac_eq; rtag=ac_r2;; esac
  mkdir -p $A/$W
  if [ "$W" = as-corrected ]; then
    echo "=== pull m5 seeds 0,1,2 -> Tables/Baseline_ac_eq_seed{K} $(date +%H:%M:%S)"
    for K in 0 1 2; do mkdir -p $T/Baseline_ac_eq_seed$K; ssh ccarroll-m5 "cd ~/coldrun_ps/Code/HA-Models/FromPandemicCode/Tables/Baseline_ac_eq_seed$K && tar cf - ." | tar xf - -C $T/Baseline_ac_eq_seed$K 2>/dev/null; echo "  seed$K: $(ls $T/Baseline_ac_eq_seed$K | tr '\n' ' ')"; done
    for K in 0 1 2; do mkdir -p $A/$W/w6logs_seed$K; ssh ccarroll-m5 "cd ~/rebattery_20260825_eq_ac && tar cf - w6logs_seed$K mult_ac.log w6_ac_eq_seed$K.log 2>/dev/null" | tar xf - -C $A/$W 2>/dev/null; done
    LOGD=$A/$W
  else
    LOGD=$HA/rerun_logs/rebattery_20260825_eq
  fi
  for K in 0 1 2; do [ -s $T/Baseline_${tag}_seed$K/welfare6_parallel_summary.json ] || { echo "MISSING Baseline_${tag}_seed$K summary"; return 1; }; done
  S="$T/Baseline_${tag}_seed0/welfare6_parallel_summary.json $T/Baseline_${tag}_seed1/welfare6_parallel_summary.json $T/Baseline_${tag}_seed2/welfare6_parallel_summary.json"
  echo "=== $W: the multiplier program's publish + the welfare battery's consumption"
  ml=$(ls $LOGD/mult_*.log 2>/dev/null | head -1); [ -n "$ml" ] && echo "  5a: policy hits=$(grep -c 'policy-store\] HIT' $ml) saved=$(grep -c 'policy-store\] SAVED' $ml) equilibria SAVED=$(grep -c 'ad-equilibrium\] SAVED' $ml) KEPT=$(grep -c 'ad-equilibrium\] KEPT' $ml) REPLACING=$(grep -c 'ad-equilibrium\] REPLACING' $ml)"
  for K in 0 1 2; do d=$LOGD/w6logs_seed$K; echo "  welfare seed$K: policy hits=$(grep -rh 'policy-store\] HIT' $d | wc -l) saved=$(grep -rh 'policy-store\] SAVED' $d | wc -l) miss-errors=$(grep -rl 'MISS at' $d | wc -l) | equilibrium HIT=$(grep -rh 'ad-equilibrium\] HIT' $d | wc -l) AD loops SKIPPED=$(grep -rh 'AD loop SKIPPED' $d | wc -l) AD solves=$(grep -rh 'AD solve took' $d | wc -l)"; done
  grep -rh "AD loop SKIPPED" $LOGD/w6logs_seed0 | head -1 | cut -c1-200
  echo "=== $W: C4 internal 3-seed band gate"; $PY $HA/full_profile_rerun_gates.py s5b --fresh $S > $A/$W/band.gate 2>&1; grep -E "GATE|FAIL" $A/$W/band.gate | head -4; echo "  ok cells: $(grep -c "\[ok\]" $A/$W/band.gate)"
  echo "=== $W: across-seed SE table"; (cd $FPC && $PY compute_welfare6_se_table.py --summaries $S --out $A/$W/welfare6_seed_band.tex) | tail -10
  echo "=== $W: tex-level band"; (cd $HA && $PY welfare6_seedband.py --label "$W world, Baseline S=3 on the SHARED AD equilibrium (5a TM), strict store, 2026-08-25" --out $A/$W/welfare6 $T/Baseline_${tag}_seed0/welfare6_candidate.tex $T/Baseline_${tag}_seed1/welfare6_candidate.tex $T/Baseline_${tag}_seed2/welfare6_candidate.tex) | grep -E "Largest"
  for K in 0 1 2; do mkdir -p $A/$W/seed$K; cp -p $T/Baseline_${tag}_seed$K/*.tex $T/Baseline_${tag}_seed$K/*.json $A/$W/seed$K/ 2>/dev/null; done
  echo "=== $W seed 0 table:"; grep 'mathcal' $T/Baseline_${tag}_seed0/welfare6_candidate.tex
  echo "=== $W cells per seed (eq battery) and shift vs the r2 battery (own MC AD loop per seed):"
  R="$R2/$W/seed0/welfare6_parallel_summary.json $R2/$W/seed1/welfare6_parallel_summary.json $R2/$W/seed2/welfare6_parallel_summary.json"
  $PY - $S -- $R <<'EOF' | tee $A/$W/shift_vs_r2.txt
import json, sys, math
args = sys.argv[1:]; i = args.index("--"); eq_p, r2_p = args[:i], args[i+1:]
eq = [json.load(open(p))["welfare6"] for p in eq_p]
r2 = [json.load(open(p))["welfare6"] for p in r2_p if __import__("os").path.exists(p)]
keys = [k for k in eq[0] if k != "ui_norec"]
def stats(v):
    m = sum(v)/len(v); sd = math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1)) if len(v) > 1 else float("nan")
    return m, sd/math.sqrt(len(v)) if len(v) > 1 else float("nan")
print(f"{'cell':16s}" + "".join(f"{'eq s'+str(i):>11s}" for i in range(len(eq))) + f"{'eq mean':>11s}{'eq SE%':>8s}" + (f"{'r2 mean':>11s}{'r2 SE%':>8s}{'shift%':>9s}" if r2 else ""))
for k in keys:
    v = [r[k] for r in eq]; m, se = stats(v)
    line = f"{k:16s}" + "".join(f"{x:11.6f}" for x in v) + f"{m:11.6f}{100*se/m:8.3f}"
    if r2:
        w = [r[k] for r in r2 if k in r]; m2, se2 = stats(w)
        line += f"{m2:11.6f}{100*se2/m2:8.3f}{100*(m-m2)/m2:+9.3f}"
    print(line)
EOF
}
case ${1:?mode} in as-corrected|default) world_harvest $1;; esac
echo "HARVEST-EQ[$1] DONE $(date +%H:%M:%S)"
