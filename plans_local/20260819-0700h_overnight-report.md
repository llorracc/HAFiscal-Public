# Overnight report — 2026-08-19 07:00 (for the owner waking ~07:20)

Everything below ran autonomously per your 23:00 instruction. Facts first; my
recommendations are confined to §7. Nothing was promoted, no default flipped, no
S1 estimate of record chosen — those are yours (§7).

## 1. Headline

Three complete 8-seed S1 batteries now exist on the same startpoint grid, machines and
shards, differing ONLY in search parameterization (plus ftol per the evening ruling):

| battery | config | in basin | total evals | consensus (ς / β / ∇) |
|---|---|---|---|---|
| run 7 (native) | bounded, taper, ftol 1e-8 | **8/8** | 10,511 | 0.2998440±2.9e-5 / 0.9795203±6.3e-6 / 0.0293929±7.2e-6 |
| V4 (θ unbounded) | log/logit, no bounds, ftol 1e-5 | 4/8 | — | 0.2998042±1.6e-4 / 0.9795256±3.6e-6 / 0.0293865±3.9e-6 |
| **V4b (θ + box)** | log/logit, finite θ box, ftol 1e-5 | **6/8** | **5,827** | **0.2998670±1.0e-4 / 0.9795228±2.4e-5 / 0.0293900±2.7e-5** |

All three consensuses are the same optimum within the joint scatter. V4b's gate:
consensus MET on both denominators; stragglers [7,8] documented; the era-1 HALT is the
designed one (memo logic identical to run 7's).

## 2. The night's discovery: the θ trap, its fix, and the residual corner

- **23:40** — V4 lost every k=0.90 seed to the **ς=0 saturated asymptote**: with no
  bounds, scipy's Brent line search brackets outward from an impatient β toward ς=0,
  lands at θ_s≈−78 (ς≈1e-34) where f is exactly flat in θ_s, and can never leave. The
  four endpoints are the *Splurge-0 arm's own optimum* (β 0.9264, ∇ 0.0900) — confirmed
  by S3 (§4), which estimates exactly that point on purpose.
- **Fix, same night** — `HAFISCAL_STEP1_THETA_BOX=1` (commit `44b442fc`): finite θ
  bounds restore scipy's bounded, globally-sampling line search while keeping the maps.
  Floors at ς/∇/cap-margin = 1e-4, where the maps are still responsive.
- **V4b result** — the box **rescued the (k=0.90, ∇₀=0.05) corner on both machines**
  (seeds 3: 1178 evals, 4: 1310 — the exact seeds V4 lost) and cost the good seeds
  nothing (599–869). The residual failures are one corner, **(k=0.90, ∇₀=0.01)** (seeds
  7/8): a **premature ftol stop on the box floor** (ς=1e-4, β 0.9414, ∇ 0.0713,
  f 0.081, ~245 evals), bit-reproducible across architectures. Mechanism: the logit
  stretches ς∈[1e-4, 0.01] across ~40% of the θ_s box, so crossing the valley is many
  tiny-relative-improvement iterations and ftol=1e-5 quits. (Native crossed it only
  with ftol=1e-8-class patience and 1863–2007 evals.)

## 3. S2 — Step 2 candidate on the run-7 winner: RUNNING

Both arms launched 00:30 (dell) / 00:40 (m5), consumed the run-7 winner with proof
lines (`CONSUMED_SPLURGE_BYTES = {'splurge': 0.2998729669935777, …}`), still solving at
07:00 (6.5 h in — the cold 4-start NM grid per education group is the long pole; the
"~15 min" figure is the warm single-start). Healthy, no errors; FTI-fallback lines are
the benign default-EGM path. **Label stands: CANDIDATE on the run-7 winner** — if you
rule V4b's winner (or anything else) as the S1 SoR, S2 is a rerun of the same
runner with a different input file.

## 4. S3 — Splurge-0 arm, native vs θ, on the new universal grid (xubuntark)

θ swept the board; native is still finishing its hard corners at 07:00:

| arm | native evals | θ evals | endpoint (β, ∇) |
|---|---|---|---|
| sp1 | ≥1010, RUNNING | 227 | 0.9263755, 0.0900112 |
| sp2 | 269 | 190 | 0.9263607–0.9263752, 0.0900113–0.0900283 |
| sp3 | ≥988, RUNNING | 199 | 0.9263788, 0.0900073 |
| sp4 | 438 | 206 | 0.9263607–0.9264839, 0.0898846–0.0900283 |

All 6 finished arms agree on (β≈0.92637, ∇≈0.09001) to ~4 decimals across
parameterizations. In the 2-D arm (no ς dimension, hence no valley) **θ is 1.4–5×
cheaper and had zero failures** — the clean θ win the 3-D battery's trap obscured.

## 5. θ xtol A/B (ccarroll) — DELAYED by machine sleep, 3/4 done

ccarroll slept from ~00:00 (banner-exchange timeouts), waking only for Power-Nap
windows; the arms are suspended-not-dead and 3 of 4 have finished inside wake windows.
Endpoints are on the machine, retrievable when it wakes. **Lesson recorded: launch Mac
compute under `caffeinate -i`** (m5 doesn't sleep; ccarroll does).

## 6. Also from the night

- The **ftol replay tool cannot yet replay box runs** (it re-runs scipy unbounded;
  V4b traces overflow) — small follow-up to add a `--box` mode.
- A **split-brain incident**, resolved cleanly: a pre-compaction incarnation of this
  session was still alive and executed the 00:30 V4 wrap-up (correctly). I verified
  its launches, adopted them, and it confirmed stand-down with a full inventory; its
  archives are the record (`run8_archive/`, `run9_archive/` on both machines). One
  self-inflicted hazard was caught and reversed within minutes (I briefly archived
  V4b's live log files; moved back, no data lost).
- All artifacts committed and pushed: V4 record `fadbc2de`, V4b record `2b7651a4`
  (`Code/HA-Models/Results/cold_rerun_2026-08/s1_run8_theta/` and `s1_run9_thetabox/`).

## 7. Open decisions (yours), with my recommendations

Facts above; opinions here.

- **D3 default flip (native → θ)?** *Recommend: not yet.* θ+box is 6/8 vs native's
  8/8. Cheaper per good seed and cleanly better in the 2-D arm, but I would not make
  a default of a search that loses a known corner. Two candidate completions, either
  of which could justify the flip after one battery: (a) per-seed ftol tightening
  (k=0.90∧∇₀=0.01 seeds run at 1e-8), or (b) a narrower ς floor (e.g. 5e-3) so the
  valley crossing is shorter in θ.
- **S1 estimate of record?** *Recommend: run 7's consensus* (8/8, tightest scatter).
  V4b independently confirms it; nothing in θ moved the answer.
- **S2 acceptance:** wait for the arms to finish, then gate; the candidate input
  matches my recommended SoR winner already, so no rerun is expected.
- **θ xtol:** A/B incomplete (ccarroll's sleep). No evidence yet that 1e-6 is wrong
  in θ; defer until the arms land.

## 8. State at 07:00

dell: S2 running (6.5 h) · m5: S2 running (6.3 h) · xubuntark: 2 native S3 arms
still walking · ccarroll: 1 xtol arm left, machine asleep · V4/V4b fully archived,
merged, gated, committed, pushed.

## Addendum 07:57 — θ xtol A/B completed (ccarroll woke; 4/4 arms)

θ-space, unbounded (V4-era config), ftol=1e-5, k_top seeds 1 and 2; the matching V4
arms (xtol=1e-6, dell/m5) are the middle rows. All six endpoints are in the basin.

| seed | xtol | evals | ς | β | ∇ |
|---|---|---|---|---|---|
| 1 | 1e-5 | **426** | 0.2999193 | 0.9795290 | 0.0293831 |
| 1 | 1e-6 (V4) | 689 | 0.2998282 | 0.9795253 | 0.0293869 |
| 1 | 1e-7 | 797 | 0.2998466 | 0.9795237 | 0.0293888 |
| 2 | 1e-5 | **497** | 0.2998399 | 0.9795250 | 0.0293873 |
| 2 | 1e-6 (V4) | 680 | 0.2998365 | 0.9795245 | 0.0293879 |
| 2 | 1e-7 | 699 | 0.2998681 | 0.9795241 | 0.0293887 |

Measured: **xtol=1e-5 saves ~30–38 % of evals** on good seeds with endpoint shifts
inside the battery scatter; 1e-7 costs ~10–15 % more than 1e-6 and buys nothing beyond
scatter. Caveat (machine differs across rows — arm64 ccarroll vs the V4 rows' own
machines — but the run-7/V1 record shows machine effects are inside scatter).
*Recommendation update (§7): θ xtol=1e-5 is attractive for k_top-class seeds, but do
NOT adopt while the hard corner is open — coarser line searches would make the ς-valley
crossing worse. Revisit together with the corner fix (per-seed ftol or ς floor).*

## Addendum 08:35 — S2 candidate COMPLETE, both arms, bitwise identical

Both S2 arms finished (m5 07:09, dell 08:29; exit 0 both). **The two machines'
estimates are BITWISE IDENTICAL** — every β and ∇ digit-for-digit across
x86-64/arm64 (the TM-ergodic Step-2 engine is deterministic enough to be
architecture-stable, unlike Step-1's Powell trajectories):

| group | β (candidate) | ∇ (candidate) | β anchor (Jul-27) | Δβ |
|---|---|---|---|---|
| Dropout | 0.7476558 | 0.2921471 | 0.7377979 | **+1.34 %** |
| HS | 0.9377309 | 0.0729327 | 0.9351696 | **+0.27 %** |
| College | 0.9929803 | 0.0146678 | 0.9923833 | +0.06 % |

GICx = 7.6004023 (unchanged). Consumed ς = 0.2998729669935777 (run-7 winner; proof
lines in both banners). Fit: medianLWPI 112.80 = data exactly; Lorenz
[0.39, 1.62, 3.83, 9.83] vs data [0.15, 0.92, 3.27, 10.30]; distance 1.0397; best
basin = start #1 of the 4-start cold grid.

**Gate view:** Dropout and HS breach the per-group |Δβ| ≤ 0.1 %-class gate. Per the
chain plan's pre-authorized propagation note, this inherits S1's passed Δς (+10.9 %):
more splurge consumption ⇒ patience must rise to hold the same wealth targets, most
for the lowest-wealth group — the sign and ordering match. The consequence-bearing
gate (fit quality) PASSES (medianLWPI exact, Lorenz within its historical class).
**Owner decisions: accept the S2 candidate (or order the pre-authorized control arm —
S2 rerun on the INSTALLED ς — to separate the stage's own move from the inherited
one), and rule on the S1 SoR it presumes.** Artifacts:
`Code/HA-Models/Results/cold_rerun_2026-08/s2_candidate_run7winner/`.


## Rulings received 2026-08-19 morning
- **S1 estimate of record = run 7** (owner: "yes - implement"): winner seed 5 committed as
  `Code/HA-Models/Results/cold_rerun_2026-08/s1/Result_AllTarget_ESC.txt`; ruling doc
  `conclusions_private/2026-08-19_s1-estimate-of-record-run7.md`. The S2 candidate already
  consumed exactly this file — no rerun.
- **θ xtol: deferral accepted** (owner: "OK") — xtol stays 1e-6 in θ; the measured 1e-5
  savings (~⅓ of evals) revisited together with the corner fix.
- D3 and S2 acceptance: explanations requested; pending.

## Addendum 09:40 — watershed probe (owner-ordered): k=0.95 REFUTED as the corner fix

140 evaluations, 10 min on dell (`Results/cold_rerun_2026-08/s1_watershed_probe/`):
conditional optimum ς*(β, ∇) along a β ladder covering every startpoint class.

| β | ς* (∇=0.01) | ς* (∇=0.05) | note |
|---|---|---|---|
| 0.8983 (k=0.90, ∇₀=.01) | floor (1e-4) | floor | |
| 0.9143 (k=0.95, ∇₀=.05) | floor | floor | |
| 0.9264 (S3 anchor) | floor | floor | |
| 0.9350 | floor | floor | |
| 0.9420 | floor | floor | |
| **0.9487 (k=0.95, ∇₀=.01)** | **floor** | **floor** | k=0.95 does NOT clear it |
| 0.9608 (k_top, ∇₀=.05) | **0.03** | **0.10** | lift-off |

**The watershed sits in (0.9487, 0.9608)** — far above my 0.92–0.94 interpolation from the
S3 anchor. Any k that clears it is k_top-class (≥0.96), i.e. abandoning the far bracket
altogether. k=0.95 buys nothing.

The probe also explains WHY (∇₀=0.05) escapes and (∇₀=0.01) stalls, and it re-ranks the
fixes: at the ς floor, f falls steeply in β at ∇=0.05 (1.108→1.026 over β 0.898→0.949 —
strong per-iteration progress, ftol never triggers) but is nearly FLAT at ∇=0.01
(1.121→1.101, 5× shallower; and even at β=0.9608 the ∇=0.01 slice sits at f≈1.098 —
with ∇ pinned that low, NO β fits the wealth targets, so the whole slice is a
high-f plateau). The (k=0.90, ∇₀=0.01) seed must therefore climb in β AND grow ∇ across
a plateau that is flat in every direction — which is exactly what a loose ftol reads as
convergence. Consequence: **fix (b) (higher ς floor) only shortens the ς leg and does
NOT remove the plateau — it may not rescue seeds 7/8. Fix (a), per-seed ftol=1e-8 on the
(k-low, ∇₀=0.01) seeds, attacks the actual failure (patience where the landscape is
flat) and is now the recommended candidate.** Native's 8/8 at ftol=1e-8 is the proof
that patience suffices.

---

## Addendum 5 (13:50) — run 10 (V4c, global ftol=1e-6) COMPLETE: 6/8, REJECTED

Full record: `Code/HA-Models/Results/cold_rerun_2026-08/s1_run10_thetabox_ftol1e-6/`.
Modal 6/8, winner = SoR optimum to sub-gate precision (Δβ=−1e-5%, Δf=−2e-5%); all 8
self-terminated (no F7 kills — the box contains the asymptote). The two corner seeds
still failed, in DIFFERENT modes than run 9: seed 7 (m5) converged AT the ς box floor
(f=49×f\*, a genuine local min — no ftol rescues it); seed 8 (dell) ftol-stopped
mid-plateau (f=9.6×f\*), whereas the same start at 1e-5 had reached the floor — plateau
trajectories are ULP-unstable to launch context. Cost of 1e-6: +9.2% evals on modal
seeds, ~2.4× on failed ones, zero rescue → **global 1e-6 rejected**. Fix (a) (per-seed
1e-8) is *weakened but standing*: it can only rescue stall-mode failures (1 of 4
observed corner failures across runs 9+10); floor captures are ftol-invariant. The
corner-fix ruling is therefore no longer urgent: best-of-8 delivers the SoR optimum in
every θ+box battery, native remains the 8/8 robustness reference, θ+box stays opt-in.
NOTE (correcting the 13:35 in-chat status): the m5 seed that crossed the plateau late
was **seed 3 — a modal seed that was merely slow at 1e-6 (1,320 evals)** — not corner
seed 7; seed 7 ended at the floor. No corner seed was rescued.

---

## Addendum 7 (14:30) — fix (c) IMPLEMENTED (owner ruling); run 11 validation LAUNCHED

Owner ruled: implement fix (c) and validate on the corner seeds, split dell/m5.
**Implemented** in `powell_minimize` (commit 7b5be4d4): on a regression stop — terminal f
worse than the best evaluated f by more than the stop test's own resolution — restart
from the best point with a fresh direction set, ≤ `HAFISCAL_STEP1_RESTART_MAX`=2; wired
`restart_at_best=(box is not None)` at both θ call sites (ON exactly under θ+box; native /
unbounded-θ / LEGACY / post-MAXFEV legs never restart; pure no-op on clean stops). New
flags documented in ENV_FLAGS.md; 10 unit tests (AST-extracted `powell_minimize`, scripted
scipy — the estimator is never imported), green on dell and m5.

**Run 11 (S1run11-fixc)** launched 14:30 EDT on both machines, wt at 7b5be4d4,
θ+box, ftol=1e-6 (the setting whose trajectories reach the fix's territory — at 1e-5 the
corner seeds ftol-stop at the iter-2 floor point before the escape leg exists):
- dell, seed 8 — the RESCUE candidate: expect the run-10 327-eval prefix bitwise, then
  `RESTART_AT_BEST 1/2` from (ς=0.0435, β=0.9390, ∇=0.0752) f=0.0158 and an escape leg
  toward the global basin. Success = modal endpoint; informative failure = another
  capture, recorded.
- m5, seed 7 — the WRONG-BASIN check (expectation REVISED ~15:00 after the owner's
  ς=0-reachability question exposed an imprecision): the floor point f=0.0807 is NOT the
  wrong basin's bottom — run 8's saturated seeds put that at f=0.0165, (0.9264, 0.0900) —
  so the restart(s) will likely DESCEND WITHIN the wrong basin toward ≈0.0165 rather than
  cheaply re-confirm 0.0807. Still non-modal, still excluded by best-of-8; the ≤2 cap and
  the endpoint are what this seed validates. (Terminology: nothing reaches ς=0 under θ —
  unbounded runs park on the θ_s≲−37 double-precision SATURATION flat at θ_s≈−78; boxed
  runs pin at the ς=1e-4 floor face, which is placed where the map is still responsive
  precisely so saturation is unreachable.)
- m5, seed 6 — the NO-OP control: expect zero restarts and a bitwise-identical result to
  run-10 m5 seed 6 (same machine, same ftol; the only code change is post-termination).

ETA: seed 6 ~17:15, seed 7 ~18:30–19:00, seed 8 between ~16:45 and ~19:30 (escape-leg
length unknown; each leg capped at MAXFEV=3000). Verdict written to a run-11 record on
completion.

---

## Addendum 8 (17:20) — BOTTOM PROBE: the "ς=0 basin" is NOT a basin. Artifact verdict.

Owner design (~17:00): interrogate the ς=0 conditional optimum itself — (β,∇) =
(0.9263755, 0.0900111), f=0.016504 by citation from run 8's four saturated seeds.
Record: `Code/HA-Models/Results/cold_rerun_2026-08/s1_bottom_probe/` (script + log + json;
19 objective evals, 2 minutes on dell).

- **Part A — first-order (decisive):** at the bottom, ∂f/∂ς(0⁺) ≈ **−0.062 < 0**; the
  ς-slice min is at ς≈0.03 (f=0.015936 < 0.016504). The ς=0 face fails the KKT test in
  the UNILATERAL ς direction — no joint move needed. Since ∇f in (β,∇) vanishes there by
  construction, first-order feasibility is settled: the point is NOT a local minimum of
  the underlying problem. Run 8 converged there only because the saturated logit had
  dς/dθ_s ≈ 0 — the level-slope was invisible through the map.
- **Part B — finite displacement:** f along the STRAIGHT chord bottom→SoR is monotone
  decreasing (0.01650 → 0.00165, no interior hump). Not even a curved path is needed.
- **Reconciliation with the watershed probe:** the ς-preference flips with ∇ as well as
  β — at (0.926, 0.090) the flip has happened even though (0.926, 0.01/0.05) is
  floor-side. The conditional-ς* watershed is a CURVE in (β,∇); seed 8's escape door at
  (0.941, 0.073) and the bottom's own liftoff are the same phenomenon.

**Verdict: the corner-seed failures are entirely SEARCH-PROCEDURE artifacts** — the
saturated logit (run 8/V4), the box floor + Powell's regression stops (runs 9–11), and
ftol-on-a-shallow-shelf (run 9 at 1e-5) — on a landscape that is, as far as these probes
can see, ONE connected basin. "The ς=0 basin" should hereafter be called **the ς≈0
SHELF**. Consequences: (i) run-11 seed 7's expected floor endpoint indicts Powell's
mechanics, not the landscape; (ii) COBYQA runs should reach the global optimum from
BOTH the original seed-7 start (run 12, live) and the bottom start (stage 2,
`s1_bottomstart.log`, live — launched 17:14 with `HAFISCAL_STEP1_STARTPOINT`, result
slot C); (iii) the D3 question (θ default flip) is reframed — the barrier maps are fine,
but the OPTIMIZER pairing decides robustness.

---

## Addendum 9 (18:00) — ALL FOUR probes confirmed; run 11 = 8/8 (seed 7 RESCUED, beating its prediction)

- **Run 12** (COBYQA, seed 7's original start): global basin in **130 evals**
  (0.29845, 0.97927, 0.02967), f=0.0016479.
- **Slot C** (COBYQA, bottom start): lifted off ς=0 immediately, global basin in
  **119 evals** (0.30154, 0.97980, 0.02908), f=0.0016484. Both endpoints +0.06–0.09%
  above f\* on scipy defaults (final-TR-radius derivation needed for production polish);
  they straddle the SoR in ς. Record: `s1_run12_mixed_cobyqa/`.
- **Run 11 complete — 8/8**: seed 6 bitwise no-op ✓; seed 8 rescued (1 restart,
  1,137 evals) ✓; **seed 7 RESCUED (2 restarts, 1,798 evals)** — correcting addendum 8's
  prediction (i): restart 1's FRESH DIRECTION SET alone walked f=0.0807→0.00165 off the
  shelf; the blocker was Powell's poisoned conjugate directions, never a local minimum.
  Fenced log-space + fix (c) now matches direct search's 8/8 at comparable-or-cheaper
  corner cost (1,798/1,137 vs native 2,007/1,863). Record: `s1_run11_fixc/`.
- Open owner questions reshaped by today: the corner-fix arc is CLOSED (fix (c)
  validated; no ftol change needed); D3-class question is now "which optimizer pairing" —
  direct Powell (8/8, proven, expensive corners) vs fenced Powell + fix (c) (8/8,
  validated today) vs level-ς COBYQA (10× cheaper on hard starts, needs a tolerance
  derivation + full-battery benchmark before any default talk). No action until ruled.

---

## Addendum 10 (19:00) — RUN 13: full 8-seed COBYQA battery @1e-8 — 8/8 basin, 7/8 SoR-class, 1,380 evals, 26 min

Owner-ruled battery, split dell {1,4,5,8} / m5 {2,3,6} / ccarroll {7} by slot capacity.
**Winner = seed 7 (the historically hardest corner): f 2.2e-10 BELOW the SoR trace value
in 163 evals on the slowest machine.** Corners cost 163/163 (native: 2,007/1,863).
Total battery 1,380 evals ≈ **7.6× cheaper than native**; consensus mean over the 7
SoR-class seeds matches the SoR ς to 6 decimals. One wart, now characterized: seed 2
stopped at the recurring (0.3014, 0.9798, 0.0291) model-stationarity trap (+0.09%;
same point as slot-C default — a ridge/kink where the interpolation model's gradient
vanishes; radius-independent; ~1/8 frequency; absorbed by best-of-N). Full record +
the standing three-way engine comparison table: `s1_run13_cobyqa_battery/`. The
optimizer-pairing ruling is OWNER-OPEN with the evidence base now complete.

---

## Addendum 6 (14:15) — owner Q "would seed 8 have continued at 1e-7?" → NO (exact); fix (a) REFUTED; fix (c) proposed

Exact ftol replay of both run-10 failures (all probed stops land inside the recorded
traces, so this is replay, not extrapolation): **seed 8 stops at the same 327 evals for
every ftol from 3e-6 to 1e-8; seed 7 at the same 850 from 1e-6 to 1e-8.** Mechanism:
scipy Powell's stop test is SIGNED (`2(fx−fval) ≤ ftol(...)`); bounded line searches
(fminbound) can return a point WORSE than the incumbent, so an iteration can end
net-worse — negative LHS — and the test then fires at ANY ftol. Seed 8 was actually
ESCAPING the ς=0 basin (ς 0.0001→0.0435, f→0.0158 < the wrong basin's min 0.0807) when
one regressing line search (→ ς=0.53, f=0.117) ended its iteration net-worse and scipy
declared success. Corrections to addendum 5 and the 13:5x report: (i) fix (a) per-seed
tighter ftol is REFUTED for these failures, not merely weakened; (ii) the run-9/run-10
seed-8 "mode difference" was a pure ftol-prefix effect on one deterministic trajectory,
NOT ULP instability (and seed 7's m5 trace replays on dell with 0 mismatches — θ+box is
architecture-reproducible here). New cheap candidate **fix (c) restart-at-best**: detect
a regression stop (returned f ≫ best-so-far f), restart Powell from best-so-far with
fresh directions (≤2 restarts) — likely rescues seed 8 (expected 7/8); seed 7 is
genuinely lost to the ς=0 local min under θ geometry. NOT implemented — owner decision.
Full detail: run-10 gate report § "Post-hoc exact replay".

---

## Addendum 11 (19:15) — OWNER RULING: COBYQA ADOPTED as the Step-1 default engine

(NOTE on this file's structure: addenda 7–10 were inserted at their anchor points, so
physical order ≠ chronological order; this is the final entry of 2026-08-19.)

`HAFISCAL_STEP1_PARAM` default → `mixed`; `HAFISCAL_STEP1_COBYQA_FINAL_TR` default →
`1e-8` (commit 4439c070; decision record
`conclusions_private/2026-08-19_step1-default-cobyqa-adoption.md`). The S1 estimate of
record is UNCHANGED (SoR = run-7 winner, produced under `native`; run-13's winner agrees
to sub-gate precision) — an ENGINE adoption, not new numbers. One-knob rollback:
`HAFISCAL_STEP1_PARAM=native`. `theta`+box+fix (c) stay opt-in; the Powell tolerance
flags are dormant under the default. 89 step-1 tests green. The corner-fix arc and the
optimizer-pairing question are both CLOSED; D3 is formally superseded by this adoption.
Remaining owner item from today: S2 acceptance (decomposition delivered 15:41).
