set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest; FPC=$REPO/Code/HA-Models/FromPandemicCode; HA=$REPO/Code/HA-Models
PY=$REPO/.venv/bin/python; T=$FPC/Tables; LOG=$HA/rerun_logs/candidate_20260825; A=$REPO/conclusions_private/artifacts_20260825_candidate
WF=$REPO/conclusions_private/artifacts_20260823_wfix
EXPECT=${1:?expected short HEAD}; HEAD=$(git -C $REPO rev-parse --short HEAD)
echo "main checkout at $HEAD (expected $EXPECT) $(date +%H:%M:%S)"; [ "$HEAD" = "$EXPECT" ] || { echo "ABORTED: HEAD mismatch"; exit 9; }
cd $FPC
export HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration PYTHONUNBUFFERED=1 HAFISCAL_TM_A_INDEXED=1 HAFISCAL_AD_EQUILIBRIUM_SHARE=1 JAX_PLATFORMS=cpu
echo "config: default store $HOME/.cache/hafiscal/policy_store; SHARE=1; TM_Q_METHOD default (doob); weighted-tail battery default (K=200, q=0.01); S=3"
stamp() { echo "=== $1 $(date +%H:%M:%S)"; }
mult() { world=$1; sfx=$2; stamp "multiplier[$world] start"; env HAFISCAL_WORLD=$world HAFISCAL_FIGS_SUFFIX=$sfx $PY AggFiscalMAIN_reduced.py --baseline > $LOG/mult_$world.log 2>&1; rc=$?; stamp "multiplier[$world] end rc=$rc"; grep -h "10y-horizon Multiplier" $T/Baseline$sfx/Multiplier.tex | head -2; echo "   equilibria: $(grep -c 'ad-equilibrium\] REPLACING' $LOG/mult_$world.log) REPLACING, $(grep -c 'ad-equilibrium\] SAVED' $LOG/mult_$world.log) SAVED, $(grep -c 'ad-equilibrium\] KEEP' $LOG/mult_$world.log) KEEP; policy hits=$(grep -c 'policy-store\] HIT' $LOG/mult_$world.log) miss=$(grep -c 'MISS at' $LOG/mult_$world.log)"; }
w6() { world=$1; K=$2; tag=$3; stamp "welfare[$world] seed $K start"; env HAFISCAL_WORLD=$world $PY run_welfare6_parallel.py --baseline --seed-offset $K --out-dir welfare6_scenario_results_Baseline_${tag}_seed$K --table-dir Tables/Baseline_${tag}_seed$K > $LOG/w6_${tag}_seed$K.log 2>&1; rc=$?; stamp "welfare[$world] seed $K end rc=$rc tables=$(ls $T/Baseline_${tag}_seed$K 2>/dev/null | wc -l)"; d=$FPC/welfare6_parallel_logs/Baseline$([ $K = 0 ] || echo _seed$K); echo "   policy hits=$(grep -rh 'policy-store\] HIT' $d | wc -l) miss=$(grep -rl 'MISS at' $d | wc -l) | equilibrium HIT=$(grep -rh 'ad-equilibrium\] HIT' $d | wc -l) | weighted-tail lines=$(grep -rh '^\[weighted-tail\]' $d | wc -l)"; grep -h "FAIL\|Traceback" $LOG/w6_${tag}_seed$K.log | head -2; }
post() { W=$1; tag=$2; mkdir -p $A/$W; S="$T/Baseline_${tag}_seed0/welfare6_parallel_summary.json $T/Baseline_${tag}_seed1/welfare6_parallel_summary.json $T/Baseline_${tag}_seed2/welfare6_parallel_summary.json"
  for K in 0 1 2; do [ -s $T/Baseline_${tag}_seed$K/welfare6_parallel_summary.json ] || { echo "MISSING Baseline_${tag}_seed$K summary"; return 1; }; done
  stamp "$W: C4 3-seed band gate"; $PY $HA/full_profile_rerun_gates.py s5b --fresh $S > $A/$W/band.gate 2>&1; grep -E "GATE|FAIL" $A/$W/band.gate | head -3
  stamp "$W: across-seed SE table"; (cd $FPC && $PY compute_welfare6_se_table.py --summaries $S --out $A/$W/welfare6_seed_band.tex) | tail -n 4
  stamp "$W: tex-level band"; (cd $HA && $PY welfare6_seedband.py --label "$W world, Baseline S=3, sharing ON (TM doob equilibrium), weighted-tail panel K=200 q=0.01, 2026-08-25" --out $A/$W/welfare6 $T/Baseline_${tag}_seed0/welfare6_candidate.tex $T/Baseline_${tag}_seed1/welfare6_candidate.tex $T/Baseline_${tag}_seed2/welfare6_candidate.tex) | tail -n 3
  for K in 0 1 2; do mkdir -p $A/$W/seed$K; cp -p $T/Baseline_${tag}_seed$K/*.tex $T/Baseline_${tag}_seed$K/*.json $A/$W/seed$K/ 2>/dev/null; done
  cp -p $T/Baseline_$([ $W = default ] && echo cand || echo ac_cand)/Multiplier*.tex $A/$W/ 2>/dev/null; cp -p $LOG/mult_$W.log $A/$W/ 2>/dev/null
  echo "=== $W cells per seed:"; $PY - $S <<'PYEOF'
import json, sys, math
rows = [json.load(open(p))["welfare6"] for p in sys.argv[1:]]
keys = [k for k in rows[0] if k != "ui_norec"]
print(f"{'cell':16s}" + "".join(f"{'seed'+str(i):>12s}" for i in range(len(rows))) + f"{'mean':>12s}{'SE%':>8s}")
for k in keys:
    v = [r[k] for r in rows]; m = sum(v)/len(v); sd = math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1)); se = sd/math.sqrt(len(v))
    print(f"{k:16s}" + "".join(f"{x:12.6f}" for x in v) + f"{m:12.6f}{100*se/m:8.3f}")
PYEOF
}
stage() { stamp "stage candidates"; mkdir -p $A/default $A/as-corrected
  for f in welfare6_candidate.tex Multiplier_candidate.tex; do [ -f $T/CRRA2/$f ] && cp -p $T/CRRA2/$f $A/default/${f%.tex}_previous_$(date +%Y%m%d-%H%M).tex; done
  cp -p $T/Baseline_cand_seed0/welfare6_candidate.tex $T/CRRA2/welfare6_candidate.tex && echo "CURRENT welfare6 candidate <- default seed 0 (Tables/CRRA2/welfare6_candidate.tex, gitignored staging)"
  cp -p $T/Baseline_cand/Multiplier.tex $T/CRRA2/Multiplier_candidate.tex && echo "CURRENT Multiplier candidate <- default 5a (Tables/CRRA2/Multiplier_candidate.tex)"
  if [ -d $WF ]; then for f in welfare6_wfix.tex welfare6_seed_band.tex; do [ -f $WF/$f ] && cp -p $WF/$f $WF/${f%.tex}_previous_$(date +%Y%m%d-%H%M).tex; done
    cp -p $T/Baseline_ac_cand_seed0/welfare6_candidate.tex $WF/welfare6_wfix.tex && echo "W-FIX welfare6 <- as-corrected seed 0"; cp -p $A/as-corrected/welfare6_seed_band.tex $WF/welfare6_seed_band.tex
    for K in 0 1 2; do cp -p $T/Baseline_ac_cand_seed$K/welfare6_parallel_summary.json $WF/welfare6_parallel_summary_ac_cand_seed$K.json; done; fi
}
mult default _cand
for K in 0 1 2; do w6 default $K cand; done
post default cand
mult as-corrected _ac_cand
for K in 0 1 2; do w6 as-corrected $K ac_cand; done
post as-corrected ac_cand
stage
echo "CANDIDATE DELL DONE $(date +%H:%M:%S)"
