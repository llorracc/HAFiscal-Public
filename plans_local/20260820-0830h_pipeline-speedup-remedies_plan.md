# Pipeline speedup remedies — implementation plan (owner-ordered 2026-08-20 morning)

**Charge** (owner, 08:2x): implement all the diagnosed speedup remedies; distribute
compute across **jhu-dell, ccarroll-m5, xubuntark** (EXCLUDE ccarroll — intermittent
internet today). Execution starts after today's spine report per the standing order;
this plan is written and shown now.

**The measured cost model being attacked** (from last night's batteries): one S2
evaluation = 21 infinite-horizon EGM solves (14 redundant) + a 1e-12 ergodic POWER
iteration whose cost blows up ~1/(1−GPF) + targets. College evals ~65–90 s (vs Dropout
~15–20 s) because near-cusp patience inflates BOTH the solve sweeps and the ergodic
spectral gap — and the aggregate-cusp cap ruling means the patient region is now priced
honestly (the old clip made above-cap trials cheap-and-fake). S2 battery ≈ 9–10 h
sequential; ~5.5 h with last night's 3-group concurrency surgery.

## The remedies

| id | remedy | attacks | expected | validation gate |
|---|---|---|---|---|
| **B** | **Ergodic distribution by direct eigensolver** — replace `find_ergodic_distribution`'s power iteration with sparse ARPACK leading-eigenvector (fallback: direct sparse solve of (P′−I)π=0, normalized); env `HAFISCAL_TM_ERGODIC_SOLVER=eig\|power` (default `eig` after gate) | the spectral-gap wall (College's dominant cost; gap-independent runtime) | College ergodic ~30–60 s/eval → **<1 s** | π parity vs power iteration ≤1e-10 sup-norm on all 3 groups × 3 trial (β,∇) points incl. near-cusp; plus S1's TM targets bitwise-class check |
| **C** | **Dirty-solve** — `betas_obj_func_educ_tm_a` re-solves ONLY the changed group's 7 types (other 14 keep solutions); env `HAFISCAL_STEP2_DIRTY_SOLVE=1\|0` (default 1 after gate) | the 21-type redundancy (owner: "fix this waste") | ~1.1–1.2× (CORRECTED 08-20 ~10:00: economy.solve already warm-starts untouched types to ~1 sweep, so the measured waste is 10–20%/eval, not the 2× first claimed) | objective value bitwise vs full re-solve at 3 trial points per group (the untouched types' solutions are by construction identical objects) |
| **A** | **Within-eval parallel solves** — wire the validated `parallel_solve` machinery (bit-identical, 3.88× at 21 cohorts) into the S1 and S2 objective solve steps (7-way per group / 21-way for S1) | serial solve time inside each eval | ~2.5–4× on the solve share | bit-identity vs serial (the machinery's existing standard) at 2 trial points per stage |
| **D** | **FTI/Newton re-enablement** — DIAGNOSIS (08-20 ~09:00): nothing moved; dell/m5 MAIN repos resolve `hark_fti` fine via their siblings, but the resolver's sibling rule is relative to the RUNNING CHECKOUT and the whole chain/spine era ran in worktrees (`~/coldrun_2026-08/wt` has no sibling) — every FTI site fail-softed to EGM silently all week. FIX: set `HAFISCAL_FTI_REPO=<machine's canonical checkout>` in every stage runner (env survives worktrees AND `uv sync`, unlike editable installs, which sync prunes); clone/ship the sibling to xubuntark; add a loud-mode tripwire `HAFISCAL_REQUIRE_FTI=1` in performance-critical runners so absence HALTS instead of whispering (guarded-fallback + isolation = silent perf loss, the week's lesson) | EGM sweep count for PATIENT types — the ones College is made of | ~2.5× on patient-type solves (84→33 s lineage, bitwise-validated historically) | the tier scheme's existing parity gates re-run on one College solve; the no-FTI fallback path must remain byte-identical stock EGM |
| **F** | **Grid reduction** — the proven Hermite/gridpoint result (1.68e-3 accuracy at 60 pts) wired into the estimation solve grids behind `HAFISCAL_SOLVE_GRID_PROFILE=hermite60\|full` (default full until the composed gate) | per-sweep cost of every solve | 2–4× per solve | estimate-level: re-run S1 battery winner + one S2 group under `hermite60`; accept if Δ(β,∇,ς) within the batteries' own cross-start scatter |

Composition (College eval): ~80 s → ergodic <1 s + solve/(A×D×F) ⇒ **~4–8 s** class.

## Sequencing & compute distribution (no ccarroll)

Phase 0 (post-report, ~16:30): create `speedup` worktrees on the three machines
(the spine worktrees stay untouched until it completes; all validation runs in
separate worktrees against the frozen post-spine commit).

| phase | dell (32c) | m5 (arm64) | xubuntark (slow, big-RAM) |
|---|---|---|---|
| P1 (impl., ~16:30–19:30) | implement B + C (code + unit gates) | install D (fast-time-iteration, arm64) + run its parity gate | pull repo; stage F profile wiring |
| P2 (validation, ~19:30–22:00) | B+C parity gates on all groups; then A wiring + bit-identity | D College-solve parity + A bit-identity cross-check (arm64) | B π-parity independent replication (cross-arch) |
| P3 (composed benchmark, ~22:00–23:00) | one full College S2 group, all remedies ON vs OFF (the headline number) | one full S1 battery, all-ON (est. <10 min) | F estimate-level gate (S1 winner under hermite60) |
| P4 (overnight cert battery) | full S2 3-group battery, all-ON | S5b spot-cell w/ new cal | full S1+S3 batteries under all-ON |

Gates are cascade-ordered (cheapest first, HALT on failure — standing rule). Every
remedy lands behind its own env flag with the OFF path byte-identical, so the certified
configuration is a set of default flips only after P4 reads green.

## ETAs

- **Plan execution**: P1–P3 complete ~23:00 tonight; P4 certifies overnight; **remedies
  certified and defaults flipped by tomorrow (08-21) morning.**
- **Projected full-suite (main spine) runtime after remedies**: S1 ~10 min · S2 ~30–45 min
  (3-group concurrent, College eval ~5–8 s) · S4 ~1.5 h (own L3b thread later) ·
  S5a ~2 h · S5b ~2.5 h (m5, parallel to S4/S5a) ⇒ **≈ 4–4.5 h wall** on the two fast
  machines (vs ~9 h today, ~16 h un-surgeried) — estimation stages become negligible;
  S4/S5a/S5b become the new critical path (their own speedup threads exist and are
  out of scope here).
- Risk buffer: if ARPACK convergence is temperamental on the near-unit-root matrices
  (known failure mode), the direct sparse solve fallback is the same afternoon's work;
  if D's arm64 build fights, D ships dell/xubuntark-only first (m5 keeps EGM fallback —
  correctness unaffected by construction).


---

## P2 VERDICTS (09:40–09:55, executed early per owner re-sequencing; spine stopped 09:20 by owner order)

- **B — flipped to `direct` (0c904948), reframed as a CORRECTNESS fix**: the ergodic was
  never the wall (N=804, ~0.03 s); on all 7 College TMs the two solvers agree ≤1.3e-10
  with direct 4 decades cleaner. The B-gate's 2× objective gap exposed a pre-existing
  KNIFE-EDGE in the College target (weighted-median grid-step; owner brief:
  conclusions_private/2026-08-20_college-objective-median-knife-edge.md).
- **C — flipped to `1` (254a8fa7), resized honestly**: bitwise-identical objectives,
  ~0–5% wall (hygiene, not speed).
- **D — the headline**: ATI routing (FTI via env; the worktree blind-spot fix) makes
  College evals **3.5–35× faster** (20/2/9/2 s vs 70/48/42/77 s) at ~3e-5 relative
  objective deltas (its validated tier class; eval-1 delta is the knife-edge). Enabled
  at RUNNER level for spine3; estimate-level gate = battery agreement within
  cross-start scatter.
- **A — wired (4a77d8a4) but moot** at warm per-eval solve costs; stays opt-in.
- **F — deferred**; never blocked the restart.

**SPINE3 launched 09:57** on the certified stack (monitor btwxu09t1); projected complete
~14:45–15:00. On completion: gates vs candidates → the outcomes report (posted) →
memory updates, per the owner's away-mode instructions.

---

## COMPLETE (12:0x) — spine3 done in 2h00m, all gates green, report POSTED

Full spine 09:57–11:57 (dell 1h46m; m5 S5b 55m). S2 10h→40min (ATI ROUTED, patient atoms
0.14–0.16s at 1e-16 residuals); S5a multipliers exact match (1.26/1.26/1.03); S5b
welfare table BYTE-IDENTICAL to the 08-19 candidate; S1 deterministic reproduction.
Record: Results/cold_rerun_2026-08/s7cand_spine3/ (8f1dac1d).
**Outcomes report (posted): https://claude.ai/code/artifact/0cadc595-7cfa-43a0-ab1a-cdc10809ab9c**
Owner-parked: promotion (the freeze door), the knife-edge ruling, remedy F, S4/5 threads.

---

## Remedy F verdict (2026-08-21 ~14:5x): VOID PREMISE — closed without a battery

Owner ordered F's acceptance battery launched (m5). Pre-launch scrutiny (the P−1 profile F
never got) voids it: the knob was never wired, and the premise fails — the certified
estimation stack runs **c48/top-40 linear (S2, `EstimParameters` defaults; no runner sets
`HAFISCAL_AXTRA_COUNT`)** and **c20/top-20 linear (S1, `SetupParamsCSTW`)**. The proven
"1.68e-3 at 60 pts = c192-class at 1/4 the points (6.2×)" is a reduction only against the
frontier thread's c192 reference; against the ACTUAL estimation grids hermite60 is a grid
INCREASE, so the projected "2–4× per solve" does not exist. Per BUG-061 the estimation
solve grid errs SHORT (17.6% of HS wealth beyond the 40-top → extrapolation bias), so
grid reduction was never available there; Hermite+60 survives as an ACCURACY-epoch
candidate coupled to the BUG-061/062 cluster (β ~0.3% ⟹ matched re-estimation,
owner-gated), not a speedup. **F closed VOID; the speedup-testing program's remaining
open item is the remedy-D soak (the live robustness/ρ-chain batteries).** Nothing was
launched on m5.

## CORRECTION to the F verdict (2026-08-21 15:0x) — the "void premise" was itself based on a stale layer

The 14:5x verdict claimed the certified estimation stack runs c48/top-40 linear. That was
EstimParameters' STATIC DEFAULTS; the live stack routes the solve grids through
`grid_sizing` under `HAFISCAL_PF_DECAY_Q=local2` (the PF-decay world's solve-top rule
aXtraMax=K·h̄, K=3), producing per-group grids **Dropout 467/237, HS 551/240, College
591/241** — observed directly in the BUG-084 arm logs (first line of every
`b084_*.log`, 15:04). Against c240-class grids, hermite60 IS a ~4× point reduction and
F's original acceptance test is meaningful after all. **Corrected status: F returns to
OWNER-PARKED (viable, untested)** — the knob is still unwired; the acceptance test
(S1 winner + one S2 group under a hermite60-profile, accept within cross-start scatter)
stands as written. Lesson recorded: verify the RESOLVED runtime config, not the file
defaults (the same layer-mistake class as BUG-085's "Done ≠ right model").

## Remedy F — WIRED, TESTED, PASSED (2026-08-21 ~17:30; stays OPT-IN)

Owner order 15:5x ("wire-and-test F on the idle machine"). Wiring: `HAFISCAL_SOLVE_GRID_PROFILE`
(grid_sizing SST, default `full` = byte-identical no-op; `hermite60` setdefaults count-basis 60 +
`HAFISCAL_SLICE_INTERP=hermite`; f855ccd5; registry+parity guards green; import smoke: per-group
grids resolve 467/60, 551/60, 591/61 — tops kept, counts at the proven T2a 60-75 window).
Acceptance battery (m5 wtF, cold, per the plan's pre-registered gate = Δ within cross-start scatter):

| arm | treatment | result (β/∇ or ς/β/∇) | reference | Δ | verdict |
|---|---|---|---|---|---|
| F_S2 College (2 cold starts, one basin) | full hermite60 | 0.9928799 / 0.0146282 | canonical full-grid 0.9929747 / 0.0146778 | −0.0095% / −0.34% | **PASS** (β ≪ the 0.06% class; ∇ inside the day's 0.7% grid-jitter class) |
| F_S1 seed 7 | count-only (S1's patched ConsIndShock has no slice option — labeled) | 0.2996938 / 0.9790004 / 0.0298611 | paired same-engine full-grid seed-7 0.2984542 / 0.9792742 / 0.0296733 | +0.42% / −0.028% / +0.63% | **PASS** (inside the seed7-vs-SoR same-basin scatter: ς 0.47%, ∇ 0.97%) |

Speed: F_S2 starts 1.7–2.1 min on m5 (≈2×-class vs a same-machine full-grid estimate; exact
ratio unmeasured same-machine — not headlined); F_S1 full COBYQA converge in 2.5 min wall.
End-to-end gains are muted because ATI already crushed the solve share — F's value is cold
re-estimation campaigns, as scoped. **STATUS: OPT-IN (default `full`).** A default flip would
be an owner ruling under calibration-epoch discipline (∇ moves 0.3–0.6% — inside scatter,
above byte-identity). Launch post-mortem: the first two m5 launches died silently on
macOS-has-no-setsid (harness trap 14); nohup+disown pattern fixed it.

**With F tested, every remedy in this program is now tested: A moot-by-benchmark (opt-in),
B/C/D adopted (bitwise/certified), F passed (opt-in). Program CLOSED.**

### F addendum (2026-08-21 ~18:05): same-machine A/B ratios + an S1 verdict amendment

Control arms (m5 wtF, identical seeds, profile=full, warm caches):

| stage | full | hermite60 | ratio | why |
|---|---|---|---|---|
| S2 College, good-basin per start (ATI ROUTED) | 2.5 min | 1.7–2.1 min | **1.2–1.5×** | ATI already ate the solve share; grid reduction buys the residual |
| S2 wall (2 starts) | 12.2 min | 6.0 min | 2.0× | inflated: the full arm's start #2 went off-basin (7.7 min, dist 7.95) while BOTH hermite60 starts found the good basin — a landscape observation (n=1), not a speed claim |
| S1 seed 7 (NO ATI — plain EGM, 0 routed lines) | **19.05 min** | **2.53 min** | **7.5×** | the undiluted grid effect: count basis 192→60 (~3.2× points) × fewer/cheaper sweeps; cubic-eval cost is invisible |

**S1 accuracy verdict AMENDED (PASS → MARGINAL/instructive):** the m5 full control reproduces
the SoR to ~1e-5 (0.2998698/0.9795228/0.0293901), making the clean comparison: hermite60
count-only S1 = ς −0.06%, β −0.05%, **∇ +1.6%** — the ∇ delta sits ~1.6× the same-basin
scatter class (~1%), OUTSIDE strictly. Economically consistent with the frontier's own
finding (in-solver LINEAR error ~10× the knots' capacity): at 60 points the Hermite slices
are LOAD-BEARING, and S1's patched solver lacks them. Where hermite was active (S2), accuracy
held (∇ −0.34%, inside class). CONSEQUENCE: hermite60 is certified for the S2/AggFiscalModel
path only; S1 use requires wiring the slice option into the Step-1 solver first (or S1 stays
at full grids — at 2.5 vs 19 min the motive exists). Overall F status unchanged: OPT-IN,
passed for its actual (S2) treatment.

### F addendum 2 (2026-08-21 ~18:30): S1 FULL-treatment verdict = FAIL; no S1 default flip

Owner conditional ("if it passes, flip hermite60 to the default for S1") — the acceptance
rerun (seed 7, 60-basis + CubicBool-Hermite via the 5d6baf7b wiring, m5, 2.9 min) FAILED the
pre-registered gate vs the full-grid control (0.2998698/0.9795228/0.0293901, f 0.0016469):

  ς +0.29% (inside) · β +0.056% (at the class boundary) · **∇ −2.29% (OUTSIDE ~1%)** · f +4.9%

Notably WORSE on ∇ than count-only linear (+1.6%), with the sign flipped (over→under-dispersion):
HARK's plain CubicInterp does not rescue S1 accuracy at 60-basis the way the T2a slices did on
the S2 path. Suspected mechanism (unproven): the ABOVE-TOP EXTRAPOLATION form, not the interior
interp — S1's wealth-target moments lean on the extrapolated region (HAFISCAL_STEP1_DIST_TOP_MULT
=10 evaluates to 10× the solve top), where HARK CubicInterp decays to the limiting line while the
certified T2a object is the POWERLAW-decay Hermite. **Disposition: no default flip (per the
conditional); the S1 CubicBool wiring stays as harmless opt-in; hermite60 remains certified for
the S2/AggFiscalModel path only. The S1 7.5× is claimable today only at reduced accuracy.**
Future options (owner-gated, not executed): (a) wire the PowerLawDecay-Hermite ctor into the
KinkedR path (real solver surgery); (b) a small basis ladder (96/120) to find S1's
accuracy-preserving floor.

### F addendum 3 (2026-08-21 ~19:35): S1 FULL-STACK PASS → S1 DEFAULT FLIPPED (owner conditional)

The three earlier S1 arms are RECLASSIFIED INVALID (two wiring bugs, 0ef0b2f8: the profile's
count value never reached S1's count base — arms ran 25-pt grids vs a 238-pt control — and
PF_DECAY_Q=farfield silently reverted the grid world to legacy). H4, the first VALID arm
(401/73 + Hermite slices + farfield tail): ς +0.072% / β +0.0093% / ∇ −0.37% vs control,
ALL inside the gate (∇ 3× margin), wall 19.05 → 4.4 min (4.3×). Farfield machinery: V0
truth gate 5e-5; v1 scalar-Richardson falsified in-session (μ≈1 far-field spectrum) → v2
Anderson mini-solve per the owner's "FTI leap" hint. **Owner conditional executed: the
Step-1 estimator family now DEFAULTS to the full stack** (setdefaults at the entry;
explicit env wins; QE-fidelity/as-corrected conservative; rollback = profile `full` +
PF_DECAY_Q `measured`). S2 defaults untouched; the S1 SoR untouched (future estimations
inherit the stack). Remaining S2-side option (unwired, owner-gated): farfield for the
AggFiscalModel slice attach.

### F addendum 4 (2026-08-21 ~20:20): tail-knot experiment EXECUTED — the amplification hypothesis is RETIRED

Lit-synthesis §5 experiment (owner: "pursue the experiment"). Wired HAFISCAL_STEP1_TAIL_KNOTS
(J log-spaced SOLVED knots over the reach set via HARK aXtraExtra; default 0 byte-identical;
+ TAIL_REACH companion). Physics A/B on one S1 type (β=0.9793, 401/73 Hermite+farfield) vs a
50k/3000 deep truth:

| metric | A (attach only) | B (+8 solved tail knots) |
|---|---|---|
| reach-set [1.05,1.6]× rel-c err | 6.5e-5 | 1.3e-5 |
| capacity of the same knots | 2.0e-4 | ~1e-8 (knots on the set) |
| **amplification ratio** | **0.3×** | (denominator ~0) |
| beyond [2.4,20]× | 4.4e-5 | 2.2e-5 |
| interior | 2.4e-5 | 1.7e-5 |
| wall/solve | 0.6 s | 0.7 s (+15%) |

**Verdict per the pre-registered branches: the ~10× in-solver amplification DOES NOT EXIST in
the current stack** — arm A's ratio is 0.3× (the farfield power-law attach ABOVE the top is
already more accurate than a same-knots Hermite representation, because it carries the true
functional form). The 10× belonged to the pre-powerlaw (naive/linear extrapolation) era; the
farfield attach had already closed the feedback channel. CONSEQUENCES: (i) the attach-refinement
program (lit shortlist #3 Padé / #4 ξ-Hermite) is DEPRIORITIZED — the stack sits at the
interior-representation floor (2-6e-5 class, balanced), not an attach floor; (ii) tail knots
survive as an OPT-IN 2-5× reach-set accuracy knob at +15% wall (default 0) — immaterial to
estimation (1e-5-class ≪ parameter sensitivity), so NO default change and no estimation-level
arm needed; (iii) the experiment retired a live hypothesis exactly as designed.

### G addendum (2026-08-22 ~01:10): GRID-ONLY comprehensive battery → S1 DEFAULT FLIPPED (owner word + "comprehensive tests, implement if robust" charge)

Supersedes addendum 4's "no default change" for the knots — the simplicity arc re-purposed
them from "accuracy knob on top of farfield" to "the coordinates fix that REPLACES farfield"
(lit-synthesis §6; MoM + Lentini–Keller anchors). Chronology: m5 G arm (knots J8@12×,
measured) PASSED +0.27%/+0.019%/−0.76%; G6 (REACH=6) REJECTED (∇ −1.06%); then the owner's
comprehensive-tests charge. The battery caught TWO wiring gaps — (1) the hermite host kept
the stock exp attach (rewrap refused CHS; fixed by in-place retrofit, `ecce3e7f`); (2) the
wealth-moments grid extension anchored at the knot-extended top, coarsening the mass-bearing
range ~7× (battery-1 scatter FAIL; fixed by basis-top anchoring, `e3df0bae`) — plus an H4
8-start attribution battery. Verdict (battery-2): G/H4 scatter 1.80–1.90× (≤2× rule ⇒
basis-inherent); modes: G ≡ H4 to 0.01pp (+0.080%/+0.010%/−0.396% vs SoR); γ=3 and splurge0
arms PASS; solve-level suite 10/10 (attach form/shape/continuity, depth+count convergence,
farfield certification 1–3%, fidelity pin m5↔dell to 10 digits). **DEFAULT FLIPPED to
hermite60 + knots 8@12× + measured attach; farfield DEMOTED to the certification
instrument.** ~3.3× vs control (~30% slower than H4 — the price of no mini-solve in the
flight path). Full evidence: conclusions_private/2026-08-21_step1-grid-only-default-flip.md
(incl. the winner-lottery property surfaced for the owner + the install-battery=full-profile
convention option).
