# MoM log-gap chart on the S1 slice — the "does it retire the knots?" A/B

**Charge (owner, 2026-08-22 ~02:20):** "scope and make the plan in plans_local/ then
execute it" — for the proposal from the dimensional-robustness exchange: represent the
solved consumption function in Method-of-Moderation-style transformed coordinates (a
re-charting of the interpolant, NOT a re-coordinatization of the solver), and test
whether the chart retires the tail-knot machinery the S1 default flipped to tonight
(`4122ddba`). Anchors: Wu–Tokuoka–Carroll (MoM); the log-abscissa chart is the 1-D
shadow of the multi-D-robust representation (see the flip decision doc §follow-on and
the 2026-08-22 chat exchange).

**Registered question:** does the chart, alone on the hermite60 basis grid (no knots),
pass the same comprehensive gates the grid-only default passed? Secondary: if not
alone, does it *shrink* the knots (fewer, shorter)?

**Pre-registered prediction (stated before any run):** CH0 (chart alone) is at risk of
an H2-class ∇ miss, because the chart's linear (ξ,y)-extrapolation above 604 is a
constant-Q power law with a top-LOCAL exponent, and the moments window 604→6,040 needs
the WINDOW exponent (local ≈ low-0.8s at the 604 top vs window ≈ 0.96 for the cap atom;
same mechanism that retired `slope` mode). CH6 (chart + 4 short knots) is predicted to
pass: the knots put the chart's end slope on a knot-span lever arm and move the
extrapolated stretch to 3,627→6,040 where little mass lives. If CH0 passes anyway, the
interior-representation gain of the chart beat the exponent risk — that IS the
registered question, so run it honestly.

## 1. Design (one-sided log-gap Hermite chart)

Chart of the UNCONSTRAINED branch only (the `LowerEnvelope` keeps the constrained
branch `c=m` outside the transform — same surgical boundary as tonight's CHS retrofit):

- knots: xᵢ = host CHS x_list (natural m units, unchanged); ξᵢ = log(xᵢ + h̄)
- values: gᵢ = κ̲·(xᵢ+h̄) − c(xᵢ) (the PF gap; κ̲ = sol.MPCmin, h̄ = sol.hNrm — the
  iteration's OWN bounds, internally consistent per backward step); yᵢ = log gᵢ
- slopes: y′ᵢ = (xᵢ+h̄)·(κ̲ − c′(xᵢ))/gᵢ, with c′ from the host's exact Hermite knot
  derivatives (evaluate host.derivative at knots)
- interpolant: cubic Hermite in (ξ, y); END-SLOPE linear extrapolation both ends
  (above the top this IS a power law with the locally-measured exponent — the attach
  falls out with no separate machinery, no measured-Q estimator, no farfield call)
- evaluation: c(m) = κ̲·(m+h̄) − exp(y(log(m+h̄))); MPC = κ̲ − (g/X)·y′(ξ) (chain rule)
- class `MoMLogGapChart(HARKinterpolator1D)` in `Code/HA-Models/mom_chart.py`
  (`_evaluate`, `_der`, `distance_criteria` on the chart arrays); introspection attrs
  `decay_extrap_form='mom_chart'`, `decay_extrap_Q = −(top end slope)` so the probe and
  the certification read it uniformly
- guards (transparent-fallback convention: refuse → stock tail kept, one-shot warn):
  any gap ≤ 0, non-finite h̄/κ̲, non-monotone ξ

## 2. Wiring (mirrors the proven farfield pattern exactly)

1. `rng_synchronized_consumer`: alongside the `farfield` gate, `HAFISCAL_PF_DECAY_Q=
   chart` installs `_install_mom_chart()` — the same 12-name-signature per-iteration
   wrapper (the within-solve iterations must see the chart, or the arm re-imports the
   H2 within-solve channel), swapping `sol.cFunc.functions[0]` per iteration.
2. `grid_sizing.powerlaw_measured_active`: add `'chart'` to the measured family —
   WITHOUT this the whole grid world silently reverts to legacy 20/20 (the H3
   invalid-arm bug, re-registered here deliberately).
3. `step1_powerlaw_tail.rewrap_type_cfunc_powerlaw`: the already-power-law guard also
   refuses `decay_extrap_form == 'mom_chart'` (never clobber the chart post-solve).
4. `docs/ENV_FLAGS.md`: `chart` value documented under HAFISCAL_PF_DECAY_Q
   (diagnostic/opt-in; NO default change — there is no standing owner authorization
   for a chart flip; this program ends at verdicts + recommendation).
5. Tests: extend the family fast test with `'chart'`; keep every default-config
   assertion untouched.

## 3. Arms, gates, decision rule (pre-registered)

Arms (8-start shard batteries, wt2, dell; candidate env per arm + the per-arm
config-echo verification IN THE LOG before results count — the invalid-arms lesson):

| arm | env | question |
|---|---|---|
| CH0 | PROFILE=hermite60 PF_DECAY_Q=chart KNOTS=0 | chart retires knots? |
| CH6 | PROFILE=hermite60 PF_DECAY_Q=chart KNOTS=4 REACH=6 | chart shrinks knots? |

Comparators already in evidence: control/SoR, H4, grid-only battery-2 (the flipped
default), all in `conclusions_private/2026-08-21_step1-grid-only-default-flip.md`.

Solve-level (probe per arm, before batteries): chart installed on all 7 atoms
(holder class), shape (gap>0 to 3e4, MPC ↓ → κ̲, c ↑), c vs the deep 238-pt+J24/R48
reference on [1.5,10]× (report; grid-only's number is ≤3.8e-5 vs same-basis deep /
1-2e-3 vs fine-basis), window-fit exponent over [1.5,10]× vs farfield q̂ on the
farfield-healthy atoms (report; band 10% is the certified standard).

Estimation-level gates (same as the flip): mode |Δς| ≤ 0.5%, |Δβ| ≤ 0.06%,
|Δ∇| ≤ 1% vs the installed SoR; scatter ≤ 2× H4's (0.168%/0.0087%/0.332%);
winner reported alongside.

Decision rule: CH0 passes all → answer YES (recommend to owner; no flip without
word). CH0 fails, CH6 passes → answer "not alone; it shrinks the machinery to
J=4@6×" — report CH6 vs the flipped default on accuracy/scatter/wall/simplicity.
Both fail → chart lane closed for S1 (the multi-D robustness argument stands
independently; record why 1-D didn't bind).

## 4. Execution checklist

- [ ] mom_chart.py (class + builder + guards)
- [ ] installer gate + `_install_mom_chart` in rng_synchronized_consumer
- [ ] family predicate + rewrap guard + ENV_FLAGS + fast-test extension
- [ ] CH0 probe smoke: chart reaches all atoms; metrics; deep-ref + exponent report
- [ ] fast+slow suite green (10/10, default-config assertions untouched)
- [ ] commit (opt-in machinery only) → wt2 → CH0+CH6 batteries (16 shards)
- [ ] adjudicate (v2 extended), verdicts vs pre-registered rule
- [ ] records: this plan's addendum + flip-doc cross-pointer + memory line; report
      with recommendation; NO default change

Wall estimate: ~45 min build+probes, ~30–40 min batteries.

## 5. VERDICTS (2026-08-22 08:25; battery wall ~30 min for both arms — chart costs no wall)

Both arms' MODES are essentially unbiased — CH6 ≡ knots-default ≡ H4 to 0.01pp
(+0.078%/+0.010%/−0.391%), CH0 +0.223%/+0.018%/−0.699%, all inside the delta gates —
but BOTH FAIL the pre-registered scatter rule catastrophically:

| arm | scatter (ς/β/∇, rel range) | vs H4 | mode cluster | f-spread |
|---|---|---|---|---|
| control 604/238 | 0.034%/0.0016%/0.063% | 0.2× | 7/8 | — |
| H4 (farfield, no knots) | 0.168%/0.0087%/0.332% | 1× | 5/8 | 0.01% |
| knots default (G b2) | 0.303%/0.016%/0.629% | 1.8–1.9× | 4/8 | 0.02% |
| **CH6 (chart + 4 knots @6×)** | 1.06%/0.062%/2.38% | **6.3–7.2×** | 3/8 | 0.33% |
| **CH0 (chart, no knots)** | 2.00%/0.120%/4.61% | **11.9–13.9×** | 2/8 | 0.82% |

**Answer to the registered question: NO — the chart neither retires nor shrinks the
knots. The chart lane is CLOSED for S1.** Decision rule applied as pre-registered
(both arms fail ≤2× scatter).

**The prediction was wrong in an instructive way (recorded per the honest-verdict
convention):** the pre-registered CH0 risk was exponent BIAS (local q 1.162 vs window
0.950 on the cap atom → predicted ∇ mode miss). The mode ∇ came in at −0.699%,
IN-gate — the bias channel was absorbed. What failed instead was OBJECTIVE-SURFACE
ROUGHNESS: a clean dose-response ladder in how much of the evaluation path runs
through the (exp ∘ spline ∘ log) round-trip — control 1× → H4 5× → knots 9× → CH6 31×
→ CH0 59× (in control units). The chart re-builds a nonlinear transform of the solved
values every solver iteration; log-space Hermite micro-wiggles where the gap is small
come back through exp() as micro-basins that COBYQA's trust region genuinely lands in
(stops at 0.33–0.82% f-spread = real distinct stops, not tolerance noise; the same
natural-termination signature as the battery-1 diagnosis).

**The transferable lesson (feeds the dimensional-robustness thread):** representation
smoothness FOR THE OPTIMIZER is a separate axis from asymptotic correctness of the
extrapolation. Solved knots win because they stay LINEAR in c — no transform noise on
the estimation surface. Transforms/compactification belong at SOLVE TIME (grid
placement, boundary conditions — the option-2 lane, real surgery) rather than as
post-hoc re-charting inside an estimation loop. The multi-D robustness argument is
unchanged — the chart failed here for optimizer-surface reasons at the 60-basis, not
for asymptotic-correctness reasons.

Machinery disposition: `HAFISCAL_PF_DECAY_Q=chart` + `mom_chart.py` stay as the
documented opt-in (the A/B is reproducible; ENV_FLAGS entry marked no-default). S1
default remains the grid-only knots stack (`4122ddba`). Evidence: this file §5,
adjudicator `~/coldrun_2026-08/g_adjudicate_v3.py`, snapshots `ch0_results/`
`ch6_results/`, probes `probe_ch0/ch6.npz` (scratchpad).

## 6. Assessment-arm addendum (2026-08-22 09:45; owner charge: comprehensive default assessment)

Four more 8-start arms (driver `~/coldrun_2026-08/assess_battery.sh`, wt2+wt3 concurrent):
**CHP0** (pchip chart) — ∇-scatter 4.61%→0.83%: the chart's roughness mechanism is
CONFIRMED as slope-noise Hermite oscillation (pre-registered ≤1% band); residual ~2.5×
H4 = the transform floor; lane stays closed. **K8R6** (knots 8@6×, post-moments-fix) —
VIABLE: mode ≡ the 12× default to 0.004pp, scatter 1.76–1.90× H4, cert depth ≤7.9e-5,
farfield 1.4–5.9% ⇒ the original REACH=6 rejection was entirely the moments-bug
artifact. **K4R12** — DEAD on both instruments (cert 2.95e-4; estimation mode ∇
−1.008%); J=4@6× certifies thinly (1.39e-4) with no battery — J stays 8. **CTRLF**
(fresh full-profile control) — winner ≡ SoR to ≤0.01% (f to 7 digits); 7/8 at 0.18%
∇-class + one min-f-filtered straggler ⇒ the install-at-full convention's measured
basis. Full synthesis + recommendations (R1: shrink REACH 12→6 on owner word; R2:
install-at-full doctrine): conclusions_private/2026-08-22_s1-default-setup-assessment.md.
