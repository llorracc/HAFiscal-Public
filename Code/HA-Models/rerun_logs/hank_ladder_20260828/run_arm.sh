#!/bin/bash
# usage: run_arm.sh ARM ENGINE [VAR=VAL ...]     (env GE_ONLY=1 skips the Jacobian stage and reuses the obj in place)
set -u
ARM=$1; ENGINE=$2; shift 2
ROOT=/Users/ccarroll/GitHub/llorracc/HAFiscal-Latest
LAD=/Users/ccarroll/ui_ext_20260826/hank_ladder_20260828
OUT=$LAD/$ARM; mkdir -p "$OUT"
source "$LAD/env_base.sh"
export HAFISCAL_STEP4_ENGINE=$ENGINE
for kv in "$@"; do export "$kv"; done
export HAFISCAL_HANK_MULT_DUMP=$OUT/mult_dump.pkl HAFISCAL_HANK_SS_DUMP=$OUT/ss_dump.pkl
env | grep -E "^HAFISCAL_|^MPLBACKEND|^PYTHONUNBUFFERED" | sort > "$OUT/env.txt"
cd "$ROOT" || exit 1
git rev-parse HEAD > "$OUT/git_head.txt"
PY=.venv/bin/python
echo "ARM=$ARM ENGINE=$ENGINE deltas: $* ; start $(date '+%F %T')" > "$OUT/wall.txt"
if [ "${GE_ONLY:-0}" != "1" ]; then
  T0=$(date +%s)
  /usr/bin/time -l $PY Code/HA-Models/step4/run_jacobians.py > "$OUT/jacobians.log" 2>&1; RC=$?
  T1=$(date +%s); echo "jacobians rc=$RC wall_s=$((T1-T0)) $(grep 'maximum resident' "$OUT/jacobians.log" | tr -s ' ')" >> "$OUT/wall.txt"
  cp Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj "$OUT/HA_Fiscal_Jacs.obj"
  shasum -a 256 "$OUT/HA_Fiscal_Jacs.obj" >> "$OUT/wall.txt"
else
  echo "GE_ONLY: Jacobians reused in place: $(shasum -a 256 Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj)" >> "$OUT/wall.txt"
fi
T0=$(date +%s)
/usr/bin/time -l $PY Code/HA-Models/step4/run_ge.py > "$OUT/ge.log" 2>&1; RC=$?
T1=$(date +%s); echo "ge rc=$RC wall_s=$((T1-T0))" >> "$OUT/wall.txt"
cp Code/HA-Models/Results_HANK/multipliers_across_horizon_w_splurge.obj "$OUT/multipliers_pickle.obj"
if [ "$ENGINE" = "monolith" ]; then
  $PY "$LAD/ge_monolith_dump.py" "$OUT/mult_dump.pkl" > "$OUT/ge_dump.log" 2>&1
  echo "ge_dump rc=$?" >> "$OUT/wall.txt"
fi
$PY "$LAD/analyze_arm.py" "$OUT" > "$OUT/summary.txt" 2>&1
cp Code/HA-Models/FromPandemicCode/Figures/HANK_*_candidate.pdf "$OUT/" 2>/dev/null
echo "end $(date '+%F %T')" >> "$OUT/wall.txt"
echo DONE >> "$OUT/wall.txt"
