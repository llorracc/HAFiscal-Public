#!/bin/bash
# Step 5a for the as-corrected world under the CURRENT defaults (2026-09-07).
#
# WHY. UPDATES.md's BUGFIXED column and the co-author briefing's "bug fixes only" row both
# read a STATIC artifact from 2026-08-23 (conclusions_private/artifacts_20260823_wfix/
# Multiplier_wfix.tex, 1.309 / 1.217 / 1.059). That predates the lambda bundle of 08-29 --
# which had already moved as-corrected to 1.320 / 1.253 / 1.087 -- and the BUG-122 timing fix
# and four-quarter cap of 09-06, both BUG_FIXes and so both ON in this world too. No
# re-estimation is needed: the as-corrected calibration is already the lambda-matched one
# (Results/DiscFacEstim_*_ascorrected.txt, 08-29, agreeing with the default world to seven
# significant figures), so the matched triple holds.
#
# OUTPUT SUFFIX IS LOAD-BEARING. AggFiscalMAIN_reduced writes Tables/<param><FIGS_SUFFIX>/;
# without a suffix this would overwrite Tables/Baseline/ -- the DEFAULT world's chain of
# record. Suffixed, it lands in Tables/Baseline_ac_20260907/ and touches nothing.
set -u
L=$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(builtin cd "$L/../../../.." && pwd)
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg
export HAFISCAL_WORLD=as-corrected
# Entry-point-owned: do_all's Step 5a exports these and the catalog does NOT supply them, so a
# driver must SET them -- stripping falls back to OFF (the m-indexed TM, 15-25 % bias, BUG-033).
export HAFISCAL_TM_A_INDEXED=1 HAFISCAL_STEP5_ATI=1
export HAFISCAL_QUIET_BETADISTR=1 HAFISCAL_POLICY_STORE_REQUIRE=0
export HAFISCAL_FIGS_SUFFIX=_ac_20260907
# ui_extension_policy and onset_spike_t0_exempt are deliberately NOT pinned: both are BUG_FIX
# rows, so the catalog applies them in this world too, and the point is to exercise that
# wiring. Verified afterwards from the run's provenance sidecar, never assumed.
for d in "$REPO/../fast-time-iteration" "$HOME/GitHub/llorracc/fast-time-iteration"; do
  [ -d "$d/.git" ] && { export HAFISCAL_FTI_REPO=$(builtin cd "$d" && pwd); break; }
done
builtin cd "$REPO/Code/HA-Models/FromPandemicCode" || exit 9
echo "=== as-corrected 5a on $(hostname) start $(date '+%F %H:%M:%S')"
"$PY" AggFiscalMAIN_reduced.py --baseline
rc=$?
echo "=== as-corrected 5a rc=$rc end $(date '+%F %H:%M:%S')"
exit $rc
