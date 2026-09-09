#!/bin/bash
# One robustness-appendix arm under the 2026-09-06 defaults: Step 5a, then S=3 welfare seeds.
#   arm.sh <PARAMETRIZATION> [TAG] [FIGS_SUFFIX]
# TAG defaults to the parametrization; FIGS_SUFFIX is for the history-policy variants (_histB).
#
# The environment is BARE on purpose: the catalog is what is being exercised. Previous artefacts
# are parked into a SUBDIRECTORY (glob does not recurse) and anything tracked is restored from
# HEAD, because an arm directory holds committed files -- both lessons of 2026-09-04.
# Every stage is idempotent via a .done marker, so a killed queue resumes where it stopped.
set -u
L=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(builtin cd "$L/../../../.." && pwd)
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
FPC="$REPO/Code/HA-Models/FromPandemicCode"
PARK="Tables/_parked_20260906"
NAME=$1; TAG=${2:-$1}; SFX=${3:-}
# NAME must be a parametrization Parameters.py knows. A tag is NOT a parametrization: the history
# arms are the Baseline / LowerUBnoB parametrizations under another policy, so they are spelled
# `Baseline:Baseline_uiB:_uiB`, not `Baseline_uiB`.

export PYTHONUNBUFFERED=1 MPLBACKEND=Agg HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration" \
         "$HOME/github/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
for v in $(env | grep -o '^HAFISCAL_[A-Z0-9_]*' | grep -vE 'QUIET_BETADISTR|POLICY_STORE_REQUIRE|FTI_REPO'); do
  unset "$v"
done
# ...but "bare" does NOT mean "unset everything". HAFISCAL_TM_A_INDEXED and HAFISCAL_STEP5_ATI are
# owned PER ENTRY POINT, not by the world catalog (CLAUDE.md: "set per-entry-point (do_all
# Step-5a)"), so stripping them does not fall back to a default -- it falls back to OFF, which is
# the m-indexed TM that BUG-033 documents as biasing multipliers by 15-25 %. do_all sets
# HAFISCAL_TM_A_INDEXED=1 for Step 5a and passes the same value to Step 5b (BUG-119 option 1);
# a driver that runs those stages must do the same. Omitting them is what invalidated the first
# cut of the 2026-09-06 appendix arms, and it presented as a fake model bug (BUG-123, withdrawn):
# the `historical` arm's stimulus-check and tax-cut multipliers moved, which no UI policy can do.
export HAFISCAL_TM_A_INDEXED=1 HAFISCAL_STEP5_ATI=1
# The history-policy arms are the one place a policy IS pinned: they ARE that policy's arm, and
# the fifth block of the appendix exists to compare it against the default. Both naming
# conventions are in use -- `_histB` for the C blocks' variants and `_uiB` for the Baseline row
# of the fifth block -- and both must pin it, or the arm silently runs the default policy and the
# block compares the default against itself.
case "$TAG" in *_histB|*_uiB) export HAFISCAL_UI_EXTENSION_POLICY=historical
                              echo "  [arm] $TAG pins HAFISCAL_UI_EXTENSION_POLICY=historical";; esac

stamp() { echo "=== $1 $(date '+%F %H:%M:%S')"; }
builtin cd "$FPC" || exit 9

if [ ! -f "$L/${TAG}_parked.done" ]; then
  mkdir -p "$PARK"
  for d in "Tables/$TAG" Tables/${TAG}_seed*; do
    [ -d "$d" ] || continue
    case "$d" in Tables/_parked_*) continue;; esac
    [ -e "$PARK/$(basename "$d")" ] && continue
    mv "$d" "$PARK/$(basename "$d")" && echo "  parked $d -> $PARK/"
  done
  # Restore ONLY the tracked files this park just displaced -- never a blanket checkout of
  # Tables/. An arm directory holds committed artefacts as well as run outputs, so moving it
  # deletes tracked files from the working tree and the guards notice; but `git checkout -- Tables`
  # also REVERTS every other tracked file under it, and most of those are live results. On
  # 2026-09-06 at 19:26:04 the CRRA3 arm's park did exactly that and silently reverted the S=5
  # Baseline welfare band produced ten minutes earlier -- the same trap this repo recorded on
  # 2026-09-04. Restore path by path, from the list of what moved.
  git -C "$REPO" status --porcelain -- Code/HA-Models/FromPandemicCode/Tables 2>/dev/null \
    | awk '$1 == "D" || $1 == "AD" {print $2}' \
    | while read -r _gone; do
        case "$_gone" in
          */"$TAG"/*|*/"$TAG"_seed*) git -C "$REPO" checkout -- "$_gone" 2>/dev/null && echo "  restored tracked $_gone" ;;
        esac
      done
  touch "$L/${TAG}_parked.done"
fi

if [ ! -f "$L/${TAG}_s5a.done" ]; then
  T0=$(date +%s); stamp "5a[$TAG] start"
  env ${SFX:+HAFISCAL_FIGS_SUFFIX=$SFX} "$PY" AggFiscalMAIN_reduced.py --parametrization "$NAME" \
      > "$L/mult_$TAG.log" 2>&1 || { stamp "HALT 5a[$TAG]"; exit 9; }
  stamp "5a[$TAG] end wall=$(( ($(date +%s)-T0)/60 ))min"
  grep "AD effect)\|expenditure during" "Tables/$TAG/Multiplier_candidate.tex" 2>/dev/null
  touch "$L/${TAG}_s5a.done"
fi

for K in 0 1 2; do
  [ -f "$L/${TAG}_s5b_seed$K.done" ] && continue
  T1=$(date +%s); stamp "w6[$TAG] seed $K start"
  "$PY" run_welfare6_parallel.py --parametrization "$NAME" --seed-offset $K \
      --out-dir "welfare6_scenario_results_${TAG}_seed$K" --table-dir "Tables/${TAG}_seed$K" \
      > "$L/w6_${TAG}_seed$K.log" 2>&1 || { stamp "HALT w6[$TAG] seed $K"; exit 9; }
  stamp "w6[$TAG] seed $K end wall=$(( ($(date +%s)-T1)/60 ))min tables=$(ls Tables/${TAG}_seed$K/*.tex 2>/dev/null | wc -l)"
  touch "$L/${TAG}_s5b_seed$K.done"
done
touch "$L/${TAG}.done"
stamp "arm[$TAG] DONE"
