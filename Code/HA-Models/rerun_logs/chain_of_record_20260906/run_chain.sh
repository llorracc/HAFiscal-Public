#!/bin/bash
# The chain of record, re-run under the defaults installed 2026-09-06 (owner: "rerun the whole
# chain of record under the new defaults") -- the onset-spike timing fix and the four-quarter UI
# cap, both now BUG_FIX rows carried by both worlds.
#
# The environment is deliberately BARE. Nothing here pins an economic setting: the catalog is the
# thing being exercised, so anything exported would defeat the purpose. HAFISCAL_TM_A_INDEXED is
# set by do_all per entry point, not here.
set -u
L=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(builtin cd "$L/../../../.." && pwd)
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg
export HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration" \
         "$HOME/github/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
for v in $(env | grep -o '^HAFISCAL_[A-Z0-9_]*' | grep -vE 'QUIET_BETADISTR|POLICY_STORE_REQUIRE|FTI_REPO'); do
  unset "$v"
done
echo "===== chain of record on $(hostname), HEAD $(git -C "$REPO" log --oneline -1)"
echo "===== bare HAFISCAL env: $(env | grep -c '^HAFISCAL_') vars: $(env | grep -o '^HAFISCAL_[A-Z0-9_]*' | tr '\n' ' ')"
echo "===== start $(date '+%F %H:%M:%S')"
"$PY" "$REPO/Code/HA-Models/do_all.py"
echo "===== do_all rc=$? end $(date '+%F %H:%M:%S')"
