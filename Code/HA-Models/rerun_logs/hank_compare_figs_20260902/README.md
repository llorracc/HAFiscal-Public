# These comparison figures are verified — the differences are not bugs

Every figure in this directory carries a small footnote pointing here. This file is the
reassurance behind that footnote: what was checked, how, and where the full expositions live.
(Builder: `python -m ssj_ladder.make_compare_figs` — re-runnable; regenerating rewrites the
figures *and* their footnotes together.)

## The one-paragraph version

Wherever the debugged model is run at the published settings, it REPRODUCES the published
behavior — so the visible differences in these figures are traced, deliberate corrections, not
numerical accidents. Specifically: (i) the frozen original construction was verified against
the published 0.14.1 pickle at 2.0e-8; (ii) the new code run on the published-shaped block
reproduces the original's IRF shapes (including the tax-cut hump, peak q5); (iii) each visible
difference was then bisected to the correction that causes it on the mechanism chain
(Phase B), one step at a time.

## Per-figure notes

**`IRF_compare_QE_vs_new_{taylor,fixed_real}`.** Fixed-real: near-identical — the corrections
mattered for accounting more than for consumption paths. Taylor: the debugged side runs the
ADOPTED inertial rule (ρ_r = 0.70, IMPROVEMENT-003). An earlier version of these figures
showed a period-2 zigzag; that was investigated to closure and found to be a grid-masked
dynamic instability of the published un-smoothed rule (ρ_r = 0) — the mode's modulus reaches 1
under wealth-grid refinement — not a coding bug (every Jacobian is smooth; the flow-budget
identities TIGHTEN with refinement). The tax-cut panel's shape change (published hump peaking
q5-6 → debugged front-load peaking q0-1) appears because the revision includes
permanent-income growth in the household dynamics, which the published HANK block omitted
entirely (its growth factor was set to one); the flip happens exactly at the growth step of
the mechanism chain, with the corrected
calibration raising the impact level ~60% and the splurge + corrected column 0 sharpening q0.
Financing (BUG-074) and the overlay-arm choice are shape-neutral.

**`Multipliers_PE_vs_newHANK`.** The HANK block reproduces the PE model when GE mechanisms are
switched off (the PE-reproduction gate, mean deviation 1.16%); the HANK-vs-PE gaps shown are
general-equilibrium economics.

**`Multipliers_QEHANK_vs_newHANK`.** Despite the IRF-shape differences, the CUMULATIVE
multipliers nearly coincide by quarter 12 in both regimes — the corrections redistribute
spending within the policy window far more than they change its total. The tax cut's early gap
IS the front-loading, closing as the original's hump catches up. Each model runs its own
monetary rule (published ρ_r = 0 vs adopted 0.70); fixed-real is rule-free in both.

## The full expositions

- The zigzag investigation, verdict, mechanism (validated out of sample), and adoption:
  `conclusions_private/2026-09-02_taylor-arm-zigzag-is-a-grid-masked-instability-of-the-unsmoothed-rule.md`
- The figures record with the tax-cut decomposition table:
  `conclusions_private/2026-09-02_hank-comparison-figures-and-the-taylor-sawtooth.md`
- The adopted rule: `IMPROVEMENTS_private/HAFiscal_IMPROVEMENT-003_hank_taylor_rule_interest_smoothing.md`
- The newborn convention: `IMPROVEMENTS_private/HAFiscal_IMPROVEMENT-002_hank_newborns_hold_their_first_income_draw.md`
- Run evidence (per-arm dumps + GE logs): `Code/HA-Models/rerun_logs/taylor_instability_20260902/`
