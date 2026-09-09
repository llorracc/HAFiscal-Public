#!/bin/bash
# Bring m5's appendix arms back to dell so every comparison is computed in one tree
# (the 2026-09-03 cold run used the same tar-over-ssh pattern). Copies only what the
# report needs: the arm table dirs, the arm calibrations, and the queue's logs.
# Nothing is overwritten in place -- m5 tables land under Tables/ with their own names
# (the arms m5 ran are disjoint from dell's), and m5's calibrations land beside dell's
# with an _m5 tag so the harvest can never silently replace a dell-estimated file.
set -u
REPO=/home/shared/github/llorracc/HAFiscal-Latest
FPC=$REPO/Code/HA-Models/FromPandemicCode
RES=$REPO/Code/HA-Models/Results
LOG=$REPO/Code/HA-Models/rerun_logs/appendix_20260904
M=hafiscal-coldrun-fixedtree-20260903
ARMS="Rfree_1005 Rfree_1015 LowerUBnoB LowerUBnoB_histB"
# COPYFILE_DISABLE=1: macOS tar otherwise emits an AppleDouble "._name" companion for
# every file, which would litter the Linux tree (harmless to the readers, but noise).
STEMS="DiscFacEstim_CRRA_2.0_R_1.005 DiscFacEstim_CRRA_2.0_R_1.015 DiscFacEstim_CRRA_2.0_R_1.01_altBenefits"

echo "=== harvest from m5 $(date +%F\ %H:%M:%S)"

# 0a. Relocate anything the queues parked IN PLACE. The drivers launched on 2026-09-04 sourced
# the first cut of park(), which left Tables/<NAME>_seedK_pre_lambda_20260904 -- still a match
# for the readers' "<NAME>_seed*" glob, so the appendix C rows would average fresh seeds with
# August ones (Rspell_4 read S=6, AD check 2.345 instead of 3.194).
bash "$LOG/sweep_parked.sh" "$FPC/Tables" || exit 9

# 0b. Park DELL's stale copies of the arms m5 ran. They were never parked here (park runs on
# the machine that runs the arm), so until the harvest overwrites them the readers would pick
# up dell's August directories -- and tar extracting over them could leave stale files behind.
PARK="$FPC/Tables/_parked_20260904"; mkdir -p "$PARK"
for a in $ARMS; do
  for d in "$FPC/Tables/$a" "$FPC/Tables/$a"_seed[012]; do
    [ -d "$d" ] || continue
    b=$(basename "$d")_pre_lambda_20260904
    [ -e "$PARK/$b" ] && continue
    mv "$d" "$PARK/$b" && echo "  parked dell's stale $(basename "$d")"
  done
done

# 0c. Sweep m5 too. Its queue parks in place as well; the tar below copies exact seed names
# so contamination cannot reach the report through it, but a clean tree removes the class of
# risk rather than relying on that argument holding for every future reader.
ssh ccarroll-m5 "bash ~/$M/Code/HA-Models/rerun_logs/appendix_20260904/sweep_parked.sh \
    ~/$M/Code/HA-Models/FromPandemicCode/Tables" || echo "  (m5 sweep failed -- check before trusting the harvest)"

# 1. arm table directories (5a + the three welfare seeds each)
PATHS=""
for a in $ARMS; do PATHS="$PATHS Code/HA-Models/FromPandemicCode/Tables/$a Code/HA-Models/FromPandemicCode/Tables/${a}_seed[012]"; done
ssh ccarroll-m5 "cd ~/$M && COPYFILE_DISABLE=1 tar cf - $PATHS 2>/dev/null" | tar xf - -C "$REPO" || { echo "HARVEST FAILED (tables)"; exit 9; }

# 2. calibrations, tagged _m5 so a dell-estimated file is never silently replaced
for s in $STEMS; do
  for v in _ESC _TM_a_ESC; do
    ssh ccarroll-m5 "cat ~/$M/Code/HA-Models/Results/${s}${v}.txt" > "$RES/${s}${v}_m5.txt" 2>/dev/null \
      && echo "  calibration: ${s}${v}_m5.txt" || echo "  MISSING: ${s}${v}.txt on m5"
  done
done

# 2b. INSTALL m5's estimates at the canonical names -- robustness_appendix_diff.py and
# Parameters.py both read the untagged file, so an arm estimated on m5 is only "the arm's
# calibration" once installed. dell's August file is parked first, never overwritten.
SUF=pre_lambda_20260904
for s in $STEMS; do
  for v in _ESC _TM_a_ESC; do
    src="$RES/${s}${v}_m5.txt"; dst="$RES/${s}${v}.txt"
    [ -s "$src" ] || { echo "  skip install ${s}${v} (no m5 file)"; continue; }
    [ -f "$dst" ] && [ ! -f "$RES/${s}${v}_${SUF}.txt" ] && cp -p "$dst" "$RES/${s}${v}_${SUF}.txt" && echo "  parked $(basename $dst)"
    cp -p "$src" "$dst" && echo "  installed $(basename $dst) <- m5"
  done
done

# 3. m5's own Baseline reference (its within-machine comparison point) + logs, kept apart
mkdir -p "$LOG/m5"
ssh ccarroll-m5 "cd ~/$M && COPYFILE_DISABLE=1 tar cf - Code/HA-Models/FromPandemicCode/Tables/Baseline_seed[012] Code/HA-Models/FromPandemicCode/Tables/Baseline_upgradecheck 2>/dev/null" \
  | tar xf - -C "$LOG/m5" || echo "  (m5 Baseline reference not harvested)"
ssh ccarroll-m5 "cd ~/$M/Code/HA-Models/rerun_logs/appendix_20260904 && COPYFILE_DISABLE=1 tar cf - . 2>/dev/null" | tar xf - -C "$LOG/m5" \
  || echo "  (m5 logs not harvested)"

echo "--- harvested arm tables:"
for a in $ARMS; do
  printf '  %-20s 5a=%s welfare seeds=%s\n' "$a" \
    "$([ -f "$FPC/Tables/$a/Multiplier_candidate.tex" ] && echo yes || echo NO)" \
    "$(ls -d $FPC/Tables/${a}_seed[012] 2>/dev/null | wc -l)"
done
# 4. final sweep: nothing parked may remain in the glob namespace before the report runs
bash "$LOG/sweep_parked.sh" "$FPC/Tables" || exit 9
echo "--- seed dirs each arm glob now sees (must be exactly the fresh 3, or 5 for Baseline):"
for a in $ARMS Rspell_4 ADElas CRRA3 Splurge0 Baseline Baseline_uiB; do
  printf '  %-18s %s\n' "$a" "$(ls -d $FPC/Tables/${a}_seed* 2>/dev/null | xargs -n1 basename 2>/dev/null | tr '\n' ' ')"
done
# 5. contamination gate: every seed battery feeding a report row must be named exactly
# <tag>_seed<n> AND date from the current calibration. Remaining flags must be only the
# rows this run deliberately does not cover (the histB variants of the four C blocks), which
# are parked before the report so they render as (pending) rather than as August numbers.
"$REPO/.venv/bin/python" "$LOG/check_glob_contamination.py" || echo "  ^^ review every flag above BEFORE generating the report"
echo "=== harvest done $(date +%F\ %H:%M:%S)"
