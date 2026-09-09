#!/bin/bash
# Bring m5's four appendix arms into dell's tree, so every comparison is computed in one place.
#
# m5 ran its arms in $HOME/GitHub/llorracc/HAFiscal-Latest. Two things this must get right, both
# learned the hard way on 2026-09-04 and again on 2026-09-06:
#
#   * dell holds its OWN stale copies of these arm directories -- park() runs on the machine that
#     runs the arm, so dell never parked them. Park them into the dated SUBDIRECTORY (glob does not
#     recurse) before extracting, or the readers average two vintages under `<NAME>_seed*`.
#   * never `git checkout -- Tables` to tidy up afterwards. It reverts every tracked result under
#     it; that is what destroyed the S=5 welfare band at 19:26 on 2026-09-06.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest
FPC=$REPO/Code/HA-Models/FromPandemicCode
M5=ccarroll-m5
M5REPO='$HOME/GitHub/llorracc/HAFiscal-Latest'
ARMS="Rfree_1005 Rfree_1015 LowerUBnoB LowerUBnoB_histB"
PARK="$FPC/Tables/_parked_20260906_dellcopies"
mkdir -p "$PARK"

echo "=== harvest from m5 $(date '+%F %H:%M:%S')"
echo "--- 0. park dell's own stale copies of the arms m5 ran"
for a in $ARMS; do
  for d in "$FPC/Tables/$a" "$FPC"/Tables/${a}_seed*; do
    [ -d "$d" ] || continue
    b=$(basename "$d")
    [ -e "$PARK/$b" ] && continue
    mv "$d" "$PARK/$b" && echo "    parked dell's $b"
  done
done

echo "--- 1. pull the arm directories (COPYFILE_DISABLE=1: macOS tar would emit ._ companions)"
TARGETS=""
for a in $ARMS; do TARGETS="$TARGETS Tables/$a Tables/${a}_seed*"; done
# shellcheck disable=SC2029
ssh "$M5" "cd $M5REPO/Code/HA-Models/FromPandemicCode && COPYFILE_DISABLE=1 tar czf - $TARGETS 2>/dev/null" \
  | tar xzf - -C "$FPC" && echo "    extracted"

echo "--- 2. what landed"
for a in $ARMS; do
  n=$(ls -d "$FPC"/Tables/${a}_seed* 2>/dev/null | wc -l)
  m=$(sed -n 5p "$FPC/Tables/$a/Multiplier_candidate.tex" 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | tr '\n' ' ')
  printf "    %-18s S=%s  %s\n" "$a" "$n" "${m:-MISSING}"
done
echo "=== harvest done $(date '+%F %H:%M:%S')"
