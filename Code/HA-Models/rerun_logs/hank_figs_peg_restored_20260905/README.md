# HANK candidate figures with the constant-nominal-rate (peg) arm restored — 2026-09-05

**What these are.** Today's production HANK figures (the 2026-09-03 production Jacobians `HA_Fiscal_Jacs.obj` at
commit 19fdf30e, the default-world GE: inertial Taylor rule ρ_r = 0.70, newborns holding their first income draw,
household financing, the calibrated splurge overlay) rendered with **all three monetary arms**, i.e. with the peg line
that the revision's candidate figures omit (owner ruling 2026-09-05, `HAFISCAL_HANK_FIGURE_ARMS` default
`taylor,fixed_real`). Regenerated on the owner's request the same day to look again at the peg's impact quarter.
Every panel now carries a legend naming the colours (owner rule 2026-09-05, `step4/figures.py`).

**How.** In a worktree at 19fdf30e (the main tree's Jacobian pickle was occupied by the ladder run
`hank_ladder_20260905`): `HAFISCAL_HANK_FIGURE_ARMS=all python Code/HA-Models/step4/run_ge.py` (18 s). Numbers are
those of the production GE; only what is drawn differs.

| file | shows |
|---|---|
| `HANK_transfer_IRF_candidate.{pdf,png}` | stimulus check, consumption IRF, three arms |
| `HANK_UI_IRF_candidate.{pdf,png}` | UI extension, consumption IRF |
| `HANK_tax_IRF_candidate.{pdf,png}` | payroll tax cut, consumption IRF — the peg line's quarter 1 is the puzzle (1.51 % vs the published 4.91 %; quarters 2–5 agree) |
| `HANK_*_multiplier_candidate.{pdf,png}` | the cumulative consumption multipliers |
| `HANK_IRFs_w_splurge_candidate.{pdf,png}` | the three IRFs on one row |

**Colours:** blue solid = active Taylor rule (ρ_r = 0.70 here; the published rule had no smoothing); orange dashed =
fixed nominal rate (the peg); red dotted = fixed real rate.

**Published counterparts (frozen, QE):** `Code/HA-Models/FromPandemicCode/Figures/HANK_{transfer,UI,tax}_{IRF,multiplier}.pdf`
on this branch, and the paper's Figure 5.

**Why the peg's quarter 1 differs — status.** The published construction and the corrected column 0 both give a smooth
peg line on the QE calibration (arms 0 and 1 of `hank_ladder_20260905`: 4.91, 4.97, 4.59, 4.31, 4.02 % of C_ss); the
collapse of quarter 1 enters at a later rung of the ladder (growth restoration, per-education chains, financing,
conventions or the calibration). The by-rung figure is added here when the ladder lands.

## Addendum 16:15 — the rung is growth restoration (arm 2)

`tax_irf_by_rung.{png,pdf}` (script `tax_irf_by_rung.py`; regenerated as arms land) draws the tax-cut consumption IRF
per ladder rung under each regime. Rungs 0, 1 and 1h coincide (smooth peg line 4.91, 4.97, 4.59 …; Taylor rising
2.10, 2.07, 2.31 …). **Rung 2 — education-specific permanent-income growth restored in the household block
([BUG-073](../../../../BUGS_private/HAFiscal_BUG-073_hank_permgrofac_ones_discards_growth.md) with
[BUG-097](../../../../BUGS_private/HAFiscal_BUG-097_step4_tranmat_ignores_permgrofac_after_bug073_fix.md)) — introduces
the impact-quarter seesaw in BOTH nominal arms and leaves the fixed real rate smooth:**

| tax cut, % of C_ss, q1..q4 | peg | Taylor (ρ_r = 0) | fixed real |
|---|---|---|---|
| rung 1 (published block, corrected column 0) | 4.91 4.97 4.59 4.31 | 2.10 2.07 2.31 2.43 | 3.14 3.15 3.23 3.26 |
| rung 2 (+ growth) | 6.50 4.79 4.62 4.24 | 0.11 1.42 1.96 2.43 | 3.59 3.62 3.72 3.76 |
| tightness q1..q4, rung 1 | +0.47 +0.93 +0.57 +0.47 | +0.69 +0.08 +0.25 +0.22 | +0.62 +0.39 +0.36 +0.33 |
| tightness q1..q4, rung 2 | +2.43 −0.14 +0.30 +0.23 | −1.38 +0.73 +0.55 +0.48 | +0.72 +0.45 +0.43 +0.39 |

The mode is an alternating tightness swing at the impact dates; with growth restored its amplitude jumps from ~0.6 to
~2 under the peg and from ~0.6 to ~2 (opposite phase) under the un-smoothed Taylor rule, while the fixed-real arm,
which has no Fisher equation, is untouched. Under the peg the phase differs between this calibration (q1 high) and
today's production model (q1 low): the peg's terminal-wealth selection sets the phase and amplitude (the α sweep).
Under the Taylor rule interest smoothing (ρ_r = 0.70) damps the mode from quarter 2 on (today's production line).
Growth also lifts the 20-quarter multipliers: check +27 % (Taylor) / +20 % (fixed real), UI +28 % / +20 %, tax cut
+36 % / +18 % — the re-based growth rung of the ladder.
