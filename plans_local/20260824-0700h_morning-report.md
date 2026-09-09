# Morning report — overnight of 2026-08-23 → 24

Branch: `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` (all work committed + pushed
through the night; nothing awaits a local push).

## Headline

1. **BUG-088 RESOLVED — the guard was right.** Arm D (full as-corrected on the
   CERTIFIED calibration) ran the entire Step-5 multiplier pipeline clean: 0 guard
   trips, 0 ATI fallbacks. The failing run's guard line inverts to the GIC-capped
   β = 1.01141947 to 7 significant figures (probe archived): the superseded warm
   calibration's above-cap College top atom (0.993035+0.020971 = 1.014006) was
   capped to the knife edge, where the S=252 ATI line-search failed and the EGM
   fallback produced a cFunc violating the PF bound by 34%. The BUG-062 guard
   caught a genuinely bad solve. Residual recorded in the BUG file: any future
   calibration whose top atom caps will fail-fast there; investigate the fallback
   before ever weakening the guard.

2. **W-FIX multiplier column landed** (Arm D IS the W-FIX S5a; provenance-verified
   `world=as-corrected`):

   | 10y multiplier (AD) | Check | UI | TaxCut |
   |---|---|---|---|
   | W-PUB (published) | 1.228 | 1.209 | 0.975 |
   | FROZEN | 1.239 | 1.248 | 1.016 |
   | CURRENT | 1.258 | 1.258 | 1.027 |
   | **W-FIX** | **1.248** | **1.258** | **1.014** |

3. **W-FIX welfare recomputed on the certified calibration — band gate PASS, warm
   caveat CLOSED.** S=3 cross-machine (dell seed0 / m5 seed1 / ccarroll seed2, tag
   `accert`): every cell of every seed inside its C4 band (UI cells ≤1.41e-2 vs
   the 3e-2 measured-class tolerance; quiet cells ≤4.9e-3 vs 5e-3). The
   warm-vs-certified delta is immaterial in every reported cell — the College ∇
   revision (0.0210 → 0.0174) does not move welfare:

   | cell | warm mean | cert mean | Δ% | Δ/SE_warm |
   |---|---|---|---|---|
   | check_norec | 0.9629 | 0.9631 | +0.02% | 1.4σ |
   | taxcut_norec | 0.9850 | 0.9850 | 0.00% | 0.4σ |
   | check_rec | 1.0135 | 1.0137 | +0.02% | 0.2σ |
   | ui_rec | 1.8195 | 1.8187 | −0.04% | −0.1σ |
   | taxcut_rec | 0.9860 | 0.9862 | +0.01% | 0.4σ |
   | check_rec_AD | 1.3890 | 1.3881 | −0.06% | −0.3σ |
   | ui_rec_AD | 2.1836 | 2.1875 | +0.18% | 0.3σ |
   | taxcut_rec_AD | 1.1704 | 1.1709 | +0.05% | 0.7σ |

   Cross-seed SEs on the certified cells: ui_rec 0.71%, ui_rec_AD 0.61%, all
   others ≤0.25% (SE table archived:
   `conclusions_private/artifacts_20260823_wfix/welfare6_seed_band.tex` —
   *erratum 2026-08-24 17:00:* the archived .tex was all-`nan` until then (the
   generator ran in raw-pickle mode with only seed 0's pickles on this box);
   regenerated from the three seeds' summaries, same numbers as quoted here; delta
   table `warm_vs_cert_delta.txt`). `welfare6_wfix.tex` refreshed to the
   certified seed-0 candidate; UPDATES.md + annotated PDF regenerated (11 badges
   hold). ui_norec excluded per standing rule.
   *Provenance footnote:* long-running children stamp HEAD at write time, so the
   seed-0 sidecar names a later docs-only commit than the bba60f41 code that ran;
   no compute file changed mid-run.

4. **Splurge0 step-4 multiplier run landed** (54 min, clean; the last "awaiting
   candidates" exhibit): Multiplier_SplurgeComp candidate — Splurge0 AD
   multipliers **1.142 / 1.249 / 0.989** vs baseline 1.258/1.258/1.027
   (published comparison was 1.143/1.221/0.947). Cumulative_multipliers_SplurgeComp
   figure candidate harvested too.

5. **W-FIX column is now COMPLETE over the exhibits where it is defined** (added
   after the main assembly, ~02:10): a fresh as-corrected fit pass at the
   certified calibration (L2 = 0.6165pp vs QE-Jan 0.5859pp — comparable fit)
   produced W-FIX `estimBetas` — (β,∇) = (0.749, 0.291) / (0.940, 0.071) /
   (0.993, 0.017) — and `nonTargetedMoments`. With Multiplier and welfare6 that
   is all four Step-2/Step-5-derived exhibits; Step-1-derived exhibits are
   world-invariant (S1 reads no world-varying flag — proven), and Splurge0
   exhibits are default-world robustness by construction, so no further W-FIX
   cells exist. En route, two findings filed to `plans_local/TODO.md` for a
   daytime decision: generic `resolve_path` is NOT world-aware for AllResults
   (only `resolve_calib_path` is), and a June-14 stale ac AllResults candidate
   was silently feeding generators until replaced tonight — candidates for a
   resolver extension + an AllResults vintage guard.

## UPDATES / annotated-build state

- **Awaiting candidates: 11 → 0.** Ten entries reclassified honestly as
  hand-maintained wrappers / no-generator static exhibits (own UPDATES section,
  stem-matched cross-refs to generator-side twins); the eleventh
  (Multiplier_SplurgeComp) got its candidate from tonight's run.
- **Annotated PDF badges 6 → 11**: wrapper-rendered exhibits now badge too
  (`\subfile` hook at `\AtBeginDocument`; unknown args no-op). Verified one badge
  per rendered table, correct positions.
- `make pdf-annotated` now takes `UPDATES_EXTRA='--extra W-FIX=…/wfix_map.tsv'`
  so the W-FIX column survives regeneration.
- Figures: 22/26 have candidates ("candidate differs" tracked by SHA in
  UPDATES.md). The other 4: two Lorenz robustness figures (final-final-only by
  ruling), `UIextension_CompSplurge0` + `UnempSpell_Dynamics` (same generator,
  needs MC `Full_Output=True` baselines both arms — deferred to plans_local/TODO.md).
- Step-1 `_splurge0` comparison figures (AggMPC / LiquWealth): refreshed to
  current-epoch candidates via a plot-only Step-1 pass rerun under the production
  config (`SOLVE_GRID_PROFILE=full`, 604/238 grid verified in-log; first bare-env
  attempt was caught by a 3% wealth-stat mismatch and discarded). Residual
  1-display-ulp difference vs the production table candidate (7.08 vs 7.07 in the
  last MPC_WealthQuartiles column) is the flat-valley class: the production table
  was written mid-install-run before the f-tie selection; the existing production
  table candidates were left untouched.

## Full test suite: from "8 failed" to a fully-triaged story (late-night arc)

Running the repo's canonical `pytest Code/ reproduce/` (which had not been run
in full for a while) surfaced a shape-shifting failure set (8, then 7, then 6
across runs). All of it is now explained, fixed, or filed:

- **Root cause of the shape-shifting: reproduce.sh deleted the live `.venv`
  symlink on every invocation** ("obsolete symlink" cleanup, contradicting the
  `make sync` convention that creates it). Any suite run that exercised
  reproduce.sh's parse surface (`test_verify_level`) destroyed the symlink
  mid-run, and every later subprocess-spawning test failed unpredictably.
  Caught red-handed with a filesystem watcher + instrumented `-v` run
  (deletion at `test_verify_level[args3]`, 06:02:38). **Fixed**: reproduce.sh
  now removes only a DANGLING symlink; verified the live one survives a direct
  invocation and the whole test file.
- **4 stale-vs-epoch tests fixed** (each pinned pre-epoch behavior):
  1. `test_multibeta_population_mass_unity` — asserted β<1; above-1 atoms are
     by design under the GIC-cap regime (bound = the GPF cap).
  2. `test_step1 anchor` — bitwise objective anchor probed 08-18, before the
     owner-ruled 08-22 grid-only/KNOTS=0 install; re-pinned under the test's
     own controlled-subprocess conditions.
  3. `test_step5_ati forced-error` — asserted the pre-ruling EGM soft-fallback;
     the router now (a61a1dc4, owner ruling 08-22) wraps any routed-path
     failure in a FATAL RuntimeError; test now asserts the raise + cause chain.
  4. `test_hank_ge_stage goldens` — pinned ς=0.27035 and its GE peaks; the
     R-c single-sourcing correctly carries the installed ς=0.29987 and peaks
     move +3–5% (direction consistent); re-pinned with lineage.
- **4 order-sensitive failures filed** (`plans_local/TODO.md`): the
  pf_asymptote pair + step1 anchor pair fail in-suite before the deletion point
  yet pass standalone — pre-existing test-env-hygiene class, not tonight's work.
- **Confirming full-suite run (landed 07:07): 899 passed, 4 failed — exactly
  the prediction.** The welfare6_ergodic pair went green (symlink casualties,
  now fixed in-suite), the `.venv` symlink survived the whole run, and the four
  remaining failures are precisely the filed pre-existing order-sensitive
  quartet (each passes standalone). The suite verdict is stable and fully
  triaged: every failure is either fixed tonight or filed with evidence.

## Hygiene

- Guard pytest sweep: **80 passed** (vintage guard, step1 f-tie, runtime parity,
  locked tables, provenance).
- Provenance reverse-lookup verified on both new artifacts (W-FIX multiplier →
  as-corrected/perm=off; Splurge0 → default/perm=on).
- Memory + plan doc updated (BUG-088 resolution memorialized).

## Open decisions for the owner (none blocking)

- The W-FIX welfare numbers in UPDATES.md are replaced by the certified-calibration
  ones at harvest; the warm-vintage evening numbers survive only in git history.
  Shout if you want both vintages shown side-by-side instead.
- S4 (HANK/SAM) exhibits remain unpromoted per prior ruling; untouched.
