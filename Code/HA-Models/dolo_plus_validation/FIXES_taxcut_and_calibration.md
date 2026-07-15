# Fixes: recessionTaxCut 6-state crash + ESC calibration silent-fallback hazard
Branch: `…_TM-vs-MC_taxcut-calib-fixes` (off parent). 2026-06-04. Investigated via workflow
(2 parallel agents); fixes applied + validated by hand.

## FIX 1 — recessionTaxCut income mapping crashed in bug_fix (6-state) mode
Root cause (Simulate.py): TWO latent length-4-vs-6 bugs masked by one IndexError:
- `:241` base/recession micro list built with only `UBspell_normal` (=2) → 4 elements, but
  bug_fix needs 6 ([E,U1,U2,U3,U4,X]). Latent: would corrupt base/recession/Check at TM time.
- `:257` TaxCut list same 4-vs-6 defect.
- `:261` `np.mod(i,4)` hardcoded the legacy micro count.
The TaxCut loop runs at setup (before any solve), so its IndexError fired first and hid the
line-241 bug.

Fix (Simulate.py:241/257/261): build lists as
`[E] + [unemp]*UBspell_normal + [nobenefits]*(num_base_MrkvStates-2-UBspell_normal) + [nobenefits]`
and index `np.mod(i, num_base_MrkvStates)`. The factor `(num_base-2-UBspell_normal)` ==
Policy_ExtraBenefitQuarters (=2 bug_fix, **0 legacy → byte-identical legacy**). Matches the
validated welfare6_scenario.py:446-467 construction; loop upper bound `18*num_base` KEPT (matches
the MC ground truth; do NOT widen to welfare6's all-macro bound).

VALIDATED: bug_fix Reduced_Run now completes (was IndexError). Check 1.32, TaxCut 1.11 — matching
legacy and the expected ~1.11-1.14. Legacy regression: Check 1.32, TaxCut 1.11, unchanged.

NOT fixed (flagged): `convergence_experiment.py:116/122/125` has the SAME three bugs AND a
separate BUG-023-style `atoms[0][1]` TranShk typo (line 120). It's a diagnostic script; fixing
only the crash would mask the income typo, so left for a validated combined fix.

SEPARATE NEW BUG (ticket): UI recession multiplier is `nan` in bug_fix but `1.34` in legacy —
`Simulate.py:246` sets `IncShkDstn_recessionUI = IncShkDstn_recession` without the bug_fix U3/U4
extension-benefit income, so recessionUI == recession → 0/0. (UI is the deprecated/unreliable
metric; out of scope here, but real.)

## FIX 2 — ESC silently loads CDC calibration on fallback (the 1.37-vs-1.32 puzzle)
Root cause: `Results/DiscFacEstim_CRRA_2.0_R_1.01.txt` (the un-suffixed default) holds **CDC**
betas (0.6556/0.8968/0.9788, uniform GICx). `_interpretation.resolve_path` returns the `_ESC`
file if it exists, **else silently falls back** to that CDC default. So an ESC run done before the
aggregate `_ESC.txt` was synced (commit c6935969, May 4) — or with it missing/stale — silently
loaded CDC discount factors, inflating the recession+AD Check multiplier 1.32 → ~1.37 (~+4%, outside
paper precision). The earlier "1.37" in this session was exactly that artifact. CURRENT tree is
correct: a default ESC run loads β 0.7237/0.9278/0.9826 → **1.32** (verified).

Fix (`_interpretation.resolve_path`): loud `warnings.warn("[ESC calibration HAZARD] …")` when ESC
falls back to the non-ESC file. Safe (warning, not raise; CDC backward-compat preserved). Verified:
ESC+existing→no warn; ESC+missing→warn; CDC+missing→no warn.

IMPACT / RECOMMENDED AUDIT: any ESC figure/table generated via the DEFAULT calibration path BEFORE
commit c6935969 may have silently used CDC/stale betas (~4% on Check). Audit which ESC outputs
predate c6935969 and used the default path; re-run any that did. Consider upgrading the warning to
a hard raise for ESC, and making the aggregate `_ESC.txt` a derived single-source-of-truth from the
per-group `_edType*_ESC.txt` files so it can't go stale.
