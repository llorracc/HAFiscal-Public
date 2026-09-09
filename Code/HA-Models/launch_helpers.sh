# launch_helpers.sh — source from launchers (bash). Wraps the three compute classes in runq so arms queue instead of contend
# (infrastructure plan B4, 2026-08-28). Requires: $PY (python), $HA (Code/HA-Models dir).
#   run5a  <args to AggFiscalMAIN_reduced.py>      e.g. run5a --baseline
#   runw6  <args to run_welfare6_parallel.py>      e.g. runw6 --baseline --seed-offset 0 --out-dir ... --table-dir ...
#   runs2  <args to estim_phase2_tm_a.py>          the three groups are launched INSIDE one step2 slot by the caller:
#                                                  runs2_group  runs `HAFISCAL_EDTYPES=$G ...` for G in 0 1 2 concurrently
# Set HAFISCAL_RUNQ=0 to bypass. `$PY $HA/runq.py status` shows the queue.
HA=${HA:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Thread pins (2026-08-28): the multiplier program forks shock workers with process pools, and the battery forks dw x sw
# children; BLAS/OpenMP threads inside each of them oversubscribe the box and can DEADLOCK a forked worker (Rfree_1015 and
# Rspell_4 hung for 7 h on 2026-08-28 without these pins, co-running). The August launchers had them; keep them.
export OPENBLAS_NUM_THREADS=${OPENBLAS_NUM_THREADS:-1} OMP_NUM_THREADS=${OMP_NUM_THREADS:-1} NUMEXPR_NUM_THREADS=${NUMEXPR_NUM_THREADS:-1} MKL_NUM_THREADS=${MKL_NUM_THREADS:-1}
run5a()  { "$PY" "$HA/runq.py" --class 5a      -- "$PY" AggFiscalMAIN_reduced.py "$@"; }
runw6()  { "$PY" "$HA/runq.py" --class battery -- "$PY" run_welfare6_parallel.py "$@"; }
runs2_groups() { # runs Step 2 for groups 0 1 2 concurrently inside ONE step2 slot; args = estim_phase2_tm_a.py args; logs to $1 prefix
  local LOGP=$1; shift
  "$PY" "$HA/runq.py" --class step2 -- bash -c 'for G in 0 1 2; do HAFISCAL_EDTYPES=$G "$0" estim_phase2_tm_a.py "${@:2}" > "$1_g$G.log" 2>&1 & done; wait' "$PY" "$LOGP" "$@"
}
