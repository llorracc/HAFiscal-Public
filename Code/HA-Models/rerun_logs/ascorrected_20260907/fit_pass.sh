#!/bin/bash
# The fit-table pass + the four generators that read its output.
#   fit_pass.sh [world]     world defaults to the ambient one (i.e. `default`)
#
# BUG-125: HAFISCAL_NM_IN_PLACE=0 is REQUIRED. The flag is not read by any optimizer -- it
# is read inside betas_obj_func_educ (EstimAggFiscalMAIN.py:1140), which this pass calls
# directly at :1820. Without it the objective mutates the economy in place and the second
# education group's solve trips the BUG-062 PF-decay guard; that is how the 2026-09-06
# chain of record left a 118-byte AllResults and took four generators down with it.
set -u
L=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(builtin cd "$L/../../../.." && pwd)
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
WORLD=${1:-}
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg
[ -n "$WORLD" ] && export HAFISCAL_WORLD="$WORLD"
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
builtin cd "$REPO/Code/HA-Models/FromPandemicCode" || exit 9
TAG=${WORLD:-default}
echo "=== fit-table pass [world=$TAG] start $(date '+%F %H:%M:%S')"
env -u HAFISCAL_EDTYPES HAFISCAL_SKIP_ESTIMATION_OPTIMIZE=1 HAFISCAL_NM_IN_PLACE=0 \
    "$PY" EstimAggFiscalMAIN.py || { echo "=== FIT PASS FAILED rc=$?"; exit 9; }
echo "=== fit-table pass done $(date '+%F %H:%M:%S'); now the four generators"
for g in CreateLPfig.py CreateIMPCfig.py estimBetas_tabular_generate.py nonTargetedMoments_tabular_generate.py; do
  echo "--- $g"; "$PY" "$g" || echo "    !! $g rc=$?"
done
echo "=== all done $(date '+%F %H:%M:%S')"
