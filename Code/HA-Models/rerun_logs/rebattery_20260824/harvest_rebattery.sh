#!/bin/bash
# Harvest the 2026-08-24/25 Baseline S=3 welfare re-battery (BUG-090 + BUG-091).
#   harvest_rebattery.sh as-corrected   : pull m5's seeds 0,1,2 into the main checkout, band gate,
#                                         SE table, tex band, artifact set
#   harvest_rebattery.sh default        : same for dell's seeds 0,1,2 (already in the main checkout)
#   harvest_rebattery.sh stage          : stage candidates (CURRENT + W-FIX), UPDATES.md + annotated PDF
#   harvest_rebattery.sh xplat          : dell's as-corrected seed 2 vs m5's (cross-platform replication)
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; HA=$REPO/Code/HA-Models
PY=$REPO/.venv/bin/python; T=$FPC/Tables; A=$REPO/conclusions_private/artifacts_20260825_rebattery
WF=$REPO/conclusions_private/artifacts_20260823_wfix; LOG=$HA/rerun_logs/rebattery_20260824
cd $REPO
world_harvest() {
  W=$1; case $W in default) tag=r2;; as-corrected) tag=ac_r2;; esac
  mkdir -p $A/$W
  if [ "$W" = as-corrected ]; then
    echo "=== pull m5 seeds 0,1,2 -> Tables/Baseline_ac_r2_seed{K} (m5 platform, one-machine S=3) $(date +%H:%M:%S)"
    for K in 0 1 2; do mkdir -p $T/Baseline_ac_r2_seed$K; ssh ccarroll-m5 "cd ~/coldrun_ps/Code/HA-Models/FromPandemicCode/Tables/Baseline_ac_r2_seed$K && tar cf - ." | tar xf - -C $T/Baseline_ac_r2_seed$K 2>/dev/null; echo "  seed$K: $(ls $T/Baseline_ac_r2_seed$K | tr '\n' ' ')"; done
  fi
  for K in 0 1 2; do [ -s $T/Baseline_${tag}_seed$K/welfare6_parallel_summary.json ] || { echo "MISSING Baseline_${tag}_seed$K summary"; return 1; }; done
  S="$T/Baseline_${tag}_seed0/welfare6_parallel_summary.json $T/Baseline_${tag}_seed1/welfare6_parallel_summary.json $T/Baseline_${tag}_seed2/welfare6_parallel_summary.json"
  echo "=== $W: C4 internal 3-seed band gate"; $PY $HA/full_profile_rerun_gates.py s5b --fresh $S > $A/$W/band.gate 2>&1; grep -E "GATE|FAIL" $A/$W/band.gate | head -4; grep -c "\[ok\]" $A/$W/band.gate
  echo "=== $W: across-seed SE table"; (cd $FPC && $PY compute_welfare6_se_table.py --summaries $S --out $A/$W/welfare6_seed_band.tex) | tail -10
  echo "=== $W: tex-level band"; (cd $HA && $PY welfare6_seedband.py --label "$W world, Baseline S=3, fixed solver + BUG-090/091 fixes, strict store, 2026-08-24/25" --out $A/$W/welfare6 $T/Baseline_${tag}_seed0/welfare6_candidate.tex $T/Baseline_${tag}_seed1/welfare6_candidate.tex $T/Baseline_${tag}_seed2/welfare6_candidate.tex) | grep -E "Largest"
  for K in 0 1 2; do mkdir -p $A/$W/seed$K; cp -p $T/Baseline_${tag}_seed$K/*.tex $T/Baseline_${tag}_seed$K/*.json $A/$W/seed$K/ 2>/dev/null; done
  if [ "$W" = default ]; then for K in 0 1 2; do d=$FPC/welfare6_parallel_logs/Baseline$([ $K = 0 ] || echo _seed$K); echo "  store stats seed$K: hits=$(grep -rh "policy-store\] HIT" $d | wc -l) saved=$(grep -rh "policy-store\] SAVED" $d | wc -l) miss-errors=$(grep -rl "MISS at" $d | wc -l) AD-cache HIT=$(grep -rh "HARK-AD\] HIT" $d | wc -l)"; done; fi
  echo "=== $W seed 0 table:"; grep 'mathcal' $T/Baseline_${tag}_seed0/welfare6_candidate.tex
  echo "=== $W cells per seed:"; $PY - $S <<'EOF'
import json, sys
rows = [json.load(open(p))["welfare6"] for p in sys.argv[1:]]
keys = [k for k in rows[0] if k != "ui_norec"]
print(f"{'cell':16s}" + "".join(f"{'seed'+str(i):>12s}" for i in range(len(rows))) + f"{'mean':>12s}{'SE%':>8s}")
import math
for k in keys:
    v = [r[k] for r in rows]; m = sum(v)/len(v); sd = math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1)); se = sd/math.sqrt(len(v))
    print(f"{k:16s}" + "".join(f"{x:12.6f}" for x in v) + f"{m:12.6f}{100*se/m:8.3f}")
EOF
}
stage() {
  echo "=== stage candidates $(date +%H:%M:%S)"
  mkdir -p $A/default $A/as-corrected
  [ -f $A/default/welfare6_candidate_CRRA2_previous_20260820.tex ] || cp -p $T/CRRA2/welfare6_candidate.tex $A/default/welfare6_candidate_CRRA2_previous_20260820.tex 2>/dev/null
  cp -p $T/Baseline_r2_seed0/welfare6_candidate.tex $T/CRRA2/welfare6_candidate.tex && echo "CURRENT welfare6 candidate <- default seed 0 (Tables/CRRA2/welfare6_candidate.tex, gitignored staging)"
  [ -f $WF/welfare6_wfix_20260824_pre-BUG090-091.tex ] || { cp -p $WF/welfare6_wfix.tex $WF/welfare6_wfix_20260824_pre-BUG090-091.tex; cp -p $WF/welfare6_seed_band.tex $WF/welfare6_seed_band_20260824_pre-BUG090-091.tex; }
  cp -p $T/Baseline_ac_r2_seed0/welfare6_candidate.tex $WF/welfare6_wfix.tex && echo "W-FIX welfare6 <- as-corrected seed 0"
  cp -p $A/as-corrected/welfare6_seed_band.tex $WF/welfare6_seed_band.tex
  for K in 0 1 2; do cp -p $T/Baseline_ac_r2_seed$K/welfare6_parallel_summary.json $WF/welfare6_parallel_summary_ac_r2_seed$K.json; done
  cp -p $T/Baseline_ac_r2_seed0/RUN_*.prov.json $WF/ 2>/dev/null
  echo "--- previous CURRENT (08-20 spine):"; grep 'mathcal' $A/default/welfare6_candidate_CRRA2_previous_20260820.tex 2>/dev/null
  echo "--- previous W-FIX (accert seed0):"; grep 'mathcal' $WF/welfare6_wfix_20260824_pre-BUG090-091.tex
  echo "=== UPDATES.md + annotated PDF"; (cd $REPO && timeout 1500 make pdf-annotated UPDATES_EXTRA="--extra W-FIX=conclusions_private/artifacts_20260823_wfix/wfix_map.tsv" > $LOG/annot_build.log 2>&1; echo "make rc=$?"); tail -2 $LOG/annot_build.log; git -C $REPO diff --stat -- UPDATES.md @local/updates-annotations.ltx | tail -3
}
xplat() {
  echo "=== cross-platform: dell as-corrected seed 2 vs m5 as-corrected seed 2"
  D=$T/Baseline_ac_r2_seed2_dell
  # The dell driver writes its seed 2 into Tables/Baseline_ac_r2_seed2 (m5's slot): if that
  # dir now holds a dell sidecar, move it aside and restore m5's copy from the artifact set so
  # the main-checkout S=3 stays one-platform.
  if [ ! -d $D ] && grep -l '"host": "jhu-dell"' $T/Baseline_ac_r2_seed2/RUN_*.prov.json >/dev/null 2>&1; then
    mv $T/Baseline_ac_r2_seed2 $D && mkdir -p $T/Baseline_ac_r2_seed2 && cp -p $A/as-corrected/seed2/* $T/Baseline_ac_r2_seed2/ && echo "  dell seed 2 moved to $(basename $D); m5 seed 2 restored from the artifact set"
  fi
  [ -s $D/welfare6_parallel_summary.json ] || { echo "dell seed 2 not available yet ($D)"; return 1; }
  $PY - $A/as-corrected/seed2/welfare6_parallel_summary.json $D/welfare6_parallel_summary.json <<'EOF'
import json, sys
a = json.load(open(sys.argv[1]))["welfare6"]; b = json.load(open(sys.argv[2]))["welfare6"]
for k, x in a.items():
    y = b.get(k)
    if x is None or y is None or x != x or y != y: continue
    print(f"  {k:16s} m5={x:.6f} dell={y:.6f} diff={y-x:+.2e} ({100*(y-x)/x:+.4f} %)")
EOF
  for f in welfare6_candidate.tex welfare4_candidate.tex; do cmp -s $A/as-corrected/seed2/$f $D/$f && echo "  $f: BYTE-IDENTICAL across platforms" || echo "  $f: differs across platforms"; done
}
case ${1:?mode} in as-corrected|default) world_harvest $1;; stage) stage;; xplat) xplat;; esac
echo "HARVEST[$1] DONE $(date +%H:%M:%S)"
