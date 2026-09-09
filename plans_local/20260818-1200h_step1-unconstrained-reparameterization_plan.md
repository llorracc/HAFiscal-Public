# Step-1: replace bounds + taper with an unconstrained (log / logit) parameterization

**Status (2026-08-19 07:00):** V4 + V4b COMPLETE — see plans_local/20260819-0700h_overnight-report.md. θ-unbounded 4/8 (ς=0 asymptote); θ+box 6/8, consensus MET, run-7 optimum confirmed; residual corner (k=0.90, ∇₀=0.01) = premature ftol stop on the box floor. D3 flip NOT recommended yet.
**Status (superseded):** IN PROGRESS 2026-08-18 — P0 done (`add0d823`), P1 done (`ed3ab519`), V2 PASSED on
x86-64 (dell) and arm64 (ccarroll): native and theta both return each machine's own anchor
bitwise at the optimum. V1 RUNNING on ccarroll since 13:32 (three arms: native seed 1, theta
seed 1, theta from the optimum; logs `~/s1theta/v1_*.log`, results `result_*.json`). V3
RUNNING on xubuntark (`~/s1theta/v3_{native,theta}.log`). P4/V4 not started (V4 = xubuntark,
after run 7 completes and V1 reports).
**Environments (owner ask 2026-08-18):** `uv.lock` is GITIGNORED (since bcbbd7d4), so every
machine had its OWN lock and "sync from the lock" diverged per machine — that is the whole
mechanism of the dell/m5 skew. Dell's lock (md5 8f7d6435…, = the E5 "dell's set") was copied
out-of-band and frozen-synced: xubuntark now IDENTICAL to dell (156 pkgs; it had been on
Python 3.10 with econ-ark 0.17.1 from a LOCAL file path); ccarroll identical up to the two
platform-conditional packages (appnope/greenlet). m5 deliberately NOT touched — run 7 live;
sync it in the first no-arm window (owner E5 window rule). Durable fix = re-track uv.lock
(HARK is a portable git ref now); that is the E-plan's call, not this one's.
**Owner rulings (2026-08-18):** D1 = **(c)** full θ ∈ ℝ³ incl. `find_Opt_splurge0`;
D2 = **logit(ς), log(cap − a_hi), log ∇**, `minBeta` a tripwire only; D3 = **opt-in**
`HAFISCAL_STEP1_PARAM=native|theta`, default `native`.
**Run 7 is live** (relaunched 10:31, ETA ~13:50) from a SEPARATE worktree; with D3 = opt-in
the main-repo default path stays byte-identical, so P0/P1/V2 can be built now without
touching it. Heavy compute (V1 solves, P4, V4) is scheduled below.

---

## 1. What this replaces, and why it came up

Step-1 currently enforces four parameter restrictions by three different mechanisms,
none of which is a reparameterization:

| restriction | how it is enforced today | where |
|---|---|---|
| ς ∈ [0, 0.9] | scipy `bounds` on the search | `find_Opt` bounds list |
| β ∈ [0.7, 1.1] | scipy `bounds` on the search | same |
| ∇ ∈ [0, 0.4] | scipy `bounds` on the search | same |
| every atom < `GICmaxBeta` | **arctan squash applied to the atoms after discretization** | `FagerengObjFunc`, the `TAPER_THRESHOLD` loop |
| every atom > `minBeta`=0.01 | hard clip on the atoms | same loop |

Two failures this year trace directly to that arrangement.

**The taper's saturation shelf (run 4, 2026-08-17).** The arctan maps
`[cap−τ, ∞) → [cap−τ, cap)`, so it is many-to-one: once atoms sit deep in the band, large
moves in nominal β produce almost no move in the effective atoms. Slope is
`d(eff)/d(nom) = (2/π)/(1+z²)` — already only ~0.64 at the band edge (a kink), and <13% at
z>2. Seeds born above the cap landed on that shelf with no gradient to leave it: 4 of 4
above-cap seeds died against 2 of 21 below-cap. The fix at the time was to move the
*startpoints* (cap-relative grid) rather than remove the shelf.

**The boundary-dust crash (run 7, 2026-08-18).** scipy's bounded Powell probes a bound and
its line-search arithmetic undershoots by float dust — measured at
`ς = −5.293955920339377e-23`. A domain guard that rejected it killed two seeds. Fixed with
a `_DOMAIN_DUST = 1e-9` tolerance, but the underlying fact remains: **bounds are a place
where the optimizer and the model disagree about what is representable.**

An unconstrained parameterization removes both classes at once: there is no bound to probe
and no squash to saturate, because out-of-domain points are *not representable*.

---

## 2. The proposed parameterization

Work in the **atom endpoints**, not in (β, ∇). With `TypeCount = 7` and
`Uniform(bot=β−∇, top=β+∇).discretize(7)`, the atoms are `β ± κ∇`, `β ± (4/7)∇`,
`β ± (2/7)∇`, `β`, where **κ = (TypeCount−1)/TypeCount = 6/7** (`top_atom_offset()`).
Every restriction is a statement about the two endpoints:

```
minBeta  <  a_lo  ≤  a_hi  <  GICmaxBeta        a_hi = β + κ∇ ,  a_lo = β − κ∇
```

Three unconstrained reals, `θ = (θ_ς, θ_hi, θ_w) ∈ ℝ³`:

```
ς    = σ(θ_ς)                                  ∈ (0, 1)          logit
a_hi = minBeta + (cap − minBeta)·σ(θ_hi)       ∈ (minBeta, cap)  logit
a_lo = minBeta + (a_hi − minBeta)·σ(θ_w)       ∈ (minBeta, a_hi)  logit   [nested]
β    = (a_hi + a_lo)/2 ,   ∇ = (a_hi − a_lo)/(2κ)
```

with `σ(x) = 1/(1+e^{−x})`.

**Why logit and not log everywhere.** The owner's suggestion was `log ς` and
`log(cap − β)`. Log fixes the *lower* barrier only; ς additionally needs ς ≤ 1 (it is a
convex-combination weight: `c = (1−ς)·cFunc + ς·y`, `wealth = (1−ς)·aLvl`, and ς>1 inverts
the sign of the whole wealth cross-section), and `a_hi` needs both ends. The nested logit
on `a_lo` is what makes `∇ ≥ 0` and `a_lo > minBeta` *simultaneously* structural — a plain
`log ∇` gives ∇>0 but says nothing about the bottom atom clearing `minBeta`.

`log(cap − a_hi)` is the pure-log variant and is **kept as an option** (§7 D2): it is what
the owner asked for, is one parameter simpler, and differs only in whether `a_hi` is also
bounded below by `minBeta` structurally. Under the current calibration `a_hi ≈ 1.0047`
against `minBeta = 0.01`, so that lower bound is nowhere near binding and the pure log is
defensible.

### What this buys

- **The taper disappears entirely.** `a_hi < cap` is structural, so no atom can exceed the
  cap and there is nothing to squash. `TAPER_THRESHOLD` / `HAFISCAL_STEP1_TAPER_THRESHOLD`
  become dead, and with them the τ-sensitivity thread (τ=0.010 → 0.005 → 0.002) that has
  consumed several runs.
- **The objective becomes a true function of the atoms.** Today the map
  (β,∇) → atoms is many-to-one near the cap; after, it is a diffeomorphism. No shelf, no
  kink, no region where the optimizer is blind.
- **No bounds, so no dust.** `_DOMAIN_DUST`, both domain guards, and the `minBeta` clip all
  become unreachable-by-construction rather than defended.
- **The cap constraint is imposed on the object it is about** — the top atom — rather than
  on each atom after the fact.

### What it costs — stated plainly

- **The estimate will move.** Powell's direction set, step sizes and `xtol` all live in the
  search coordinates; a line search in θ is not a line search in (ς,β,∇). This is an
  experimental change requiring re-validation, not a refactor. Every Step-1 anchor
  (`f = 0.001646865550005354` on dell, `…53353` on m5) is invalidated as a *byte* anchor,
  though §5 shows they remain usable as *value* anchors.
- **The boundaries become unreachable** — ς=0, ς=1, ∇=0, a_hi=cap are all asymptotes.
  See §4 for why this is acceptable here, and where it is not.
- **Tolerances change meaning.** `xtol=1e-6` in θ is `dβ = (cap−a_hi)·(…)·dθ` in β: near the
  cap that is *tighter* than today, far from it *looser*. §6 covers re-tuning.

---

## 3. Sites to change

Enumerated so the work is bounded. All in
`Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py` unless noted.

| # | site | change |
|---|---|---|
| S1 | `FagerengObjFunc` signature | accept `(ς, β, ∇)` as today; the transform lives in the *caller* so the objective stays interpretable and every existing direct call (Run_3D_Plot, CRRA blocks, `find_Opt_splurge0`'s literal 0) is untouched |
| S2 | the arctan taper loop (~L878–883) | DELETE, behind the flag; atoms pass through nominal |
| S3 | `minBeta` clip | DELETE (structural) |
| S4 | `_verify_gic_satisfied` | KEEP as a tripwire — it should now be unreachable; if it ever fires, the transform is wrong. Change its message accordingly |
| S5 | `LAST_TAPER_CENSUS` / BUG-078 diagnostic | KEEP but re-purpose: `z` is meaningless without a band. Report `cap − a_hi` and the atom margins instead |
| S6 | `find_Opt` bounds + `powell_minimize` call | search θ ∈ ℝ³, no `bounds=` at all |
| S7 | the cap-relative multistart grid builder | re-express the 8 startpoints in θ. The *intent* (bracket each axis at 2 levels, top clear of the cap) survives; the arithmetic changes |
| S8 | `find_Opt_splurge0` | 2-D analogue: ς fixed at 0 (a literal, NOT searched — so the ς=0 reachability objection does not apply here), θ = (θ_hi, θ_w) |
| S9 | the two domain guards + `_DOMAIN_DUST` | KEEP as tripwires; they must never fire. Their tests become "the transform never emits out-of-domain values" |
| S10 | `Code/HA-Models/coldrun/s1_gate.py` | grid legend + startpoint labels read from the log already; verify the θ-space legend parses |
| S11 | `test_fti_step1.py` `_tapered_betas` | consumes the taper directly — update or gate |
| S12 | `test_single_objective_eval.py`, `fti_diagnostics/poc_hafiscal_step1_fti.py`, `_fti_type6_*.py` | reference the cap/taper; audit for breakage |

**Not touched:** `gic_taper_cap()` stays exactly as-is — it is the SST for the cap and the
transform consumes it. The name becomes slightly wrong (no taper); rename deferred to
avoid churn in the FTI files that import it.

---

## 4. The reachability objection, resolved case by case

A transform makes its endpoints asymptotes. Each must be checked against actual use:

- **ς = 0** — used as a *fixed* value by four call sites (`find_Opt_splurge0`, its
  `check_maximum` probe, two `Run_3D_Plot` calls). All pass a **literal 0** into
  `FagerengObjFunc`; none of them *search* ς. Since the transform lives in the caller (S1),
  those paths are unaffected. **Not a blocker.**
- **ς = 1** — pure hand-to-mouth. Never used; wealth ≡ 0 there. **Not a blocker.**
- **∇ = 0** — homogeneous β. Not currently an estimated or restricted arm. Reachable to
  1e-300 under the transform. **Not a blocker, but flag it** if a "∇=0 robustness" arm is
  ever wanted, since it would have to fix ∇ outside the search exactly as ς=0 does.
- **a_hi = cap** — *should* be unreachable; that is the GIC boundary and the whole point.
- **The multistart grid endpoints** (ς₀=0.01, ∇₀=0.01) are interior, so they map to finite
  θ (log(0.01/0.99) ≈ −4.6). **Not a blocker.**

I raised the ς=0 objection earlier and overstated it: the relevant question is whether ς=0
is *searched*, not whether it is *used*, and it is not searched.

---

## 5. Validation — the part that decides whether this ships

The reparameterization is admissible only if it finds the same optimum where the two
formulations are mathematically equivalent, and differs only where the taper was actually
distorting the answer.

**V1 — inert-taper equivalence (the decisive test, cheap).** At τ=0.002 the optimum of
record is *outside* the band: `TAPER_CENSUS` reports `n_in_taper: 0`, `n_pinned: 0`,
`nominal_atoms == effective_atoms` exactly. **Where the taper is inert, the two
formulations describe the identical objective**, so a θ-space solve started from the
transformed optimum must return to the same point. Target: agreement to ≲1e-8 in f and
≲1e-6 relative in (ς,β,∇). Anything worse means the transform or its Jacobian is wrong,
not that the estimator changed. Cost: 2 solves ≈ 2×1052 evals ≈ 4 h wall (or ~2 h with
today's speedups, concurrent).

**V2 — objective-value identity at fixed parameters.** For a grid of (ς,β,∇) with all atoms
below cap−τ, `FagerengObjFunc` must return **bitwise identical** f whether reached directly
or through the transform, since the taper is a no-op there and the atoms are the same
floats. This is a unit test, seconds, no solve. It isolates "did the transform change the
model" from "did it change the search".

**V3 — the shelf, measured.** Pick a (β,∇) whose top atom sits at z≈3 (deep in the band).
Under the taper, sweep nominal β and show `d(f)/d(β)` collapses; under the transform, show
it does not. This is the *positive* case for the change and belongs in the record.

**V4 — full 8-seed battery in θ-space**, same protocol as run 7. Compare: modal basin,
inter-seed spread, straggler count, and whether seeds 7/8 (the ∇₀=0.01, k=0.90 corner that
straggles in both runs 6 and 7) now converge. **Prediction to record in advance:** if the
shelf was the mechanism, the straggler rate falls.

**V5 — cross-machine.** Repeat V1 on m5. Architecture differences are ~1e-14 relative; the
transform must not amplify them.

---

## 6. Tolerances

`xtol`/`ftol` were re-ruled on 2026-08-18 (1e-6 / 1e-8, replacing scipy's 1e-4/1e-4) after
a controlled A/B showed the loose values were terminating far from the optimum. **Those
values were tuned in (ς,β,∇) space and do not transfer.** Under the transform:

```
dβ/dθ_hi = (cap − minBeta)·σ'(θ_hi) = (a_hi − minBeta)·(cap − a_hi)/(cap − minBeta)
```

At the optimum (`a_hi = 1.004714`, `cap = 1.0076174`, `minBeta = 0.01`) this evaluates to
**2.895e-3** (verified numerically), so `xtol = 1e-6` in θ is an `a_hi` step of **2.9e-9**
(a β step of 1.4e-9) — **345× tighter** than today's 1e-6 applied directly to β. Left alone
this would inflate eval counts, possibly past the `maxfev = 3000` guard. **Plan: re-run the same A/B design that produced the current
values** (same seed, tight vs loose, compare endpoint and eval count) in θ-space, and set
`xtol` so the *implied β resolution* matches today's. Do not carry the numbers over.

---

## 7. Owner decisions needed before coding

**D1 — scope.** (a) taper only (replace the arctan with the `a_hi` transform, keep scipy
bounds on ς and ∇); (b) full unconstrained θ ∈ ℝ³ as in §2; (c) full, plus the same
treatment in `find_Opt_splurge0`. *Recommendation: (b), with (c) following once (b)
validates.* (a) leaves the dust class alive for no saving.

**D2 — logit or pure log, per parameter.** §2 uses nested logits throughout; the owner's
literal suggestion is `log ς` and `log(cap − a_hi)`. They are not interchangeable
parameter-by-parameter:
- **ς: logit.** ς≤1 is a real modelling constraint with a sign-flip failure mode
  (`wealth = (1−ς)·aLvl`), so a one-sided log leaves it to "won't be reached" — the
  reasoning that failed with the guards. Logit costs nothing extra.
- **a_hi: the owner's `log(cap − a_hi)`.** Near the cap the two forms are the SAME map up
  to an additive constant: `1−σ(θ) ≈ e^{−θ}`, so `θ_hi ≈ log(cap−minBeta) − log(cap−a_hi)`
  — at the optimum `θ_hi = 5.8366` vs `log(cap−a_hi) = −5.8419`, differing by
  `log(0.9976) ≈ −0.0024`. They part company only near `minBeta`, which is 343× further
  from `a_hi` than the cap is. Take the simpler one that was asked for.
- **∇ / a_lo: `log ∇` recommended over the nested logit.** `log ∇` is directly the log
  of the reported dispersion (its SE is a relative SE), and it leaves `a_lo > minBeta` as
  a TRIPWIRE rather than a structural bound — acceptable because today's box already
  implies `a_lo ≥ 0.7 − (6/7)·0.4 = 0.357`, so nothing practical is lost. The nested
  logit is the "fully structural" alternative at the price of one more constant.
*Recommendation: logit(ς), log(cap − a_hi), log ∇; minBeta kept as a tripwire only.*
Note the transform lives in the CALLER (S1), so D2 is cheap to revisit later; D1 and D3
are the structural decisions.

**D3 — default or opt-in.** *Recommendation: `HAFISCAL_STEP1_PARAM=native|theta`, default
`native`, until V1/V2/V4 pass; then flip and retire the taper.* This keeps the default path
byte-identical while the work proceeds, which is what let today's two speedups land safely.

---

## 7a. Findings from the readiness check (2026-08-18, post-ruling)

**F1 — Removing `bounds=` changes scipy's line-search ROUTINE, not just the coordinates.**
Verified in the installed scipy 1.17.1 (`_optimize.py`, `_linesearch_powell`): with bounds
Powell minimises each line with `_minimize_scalar_bounded(..., xatol=xtol)` — an ABSOLUTE
tolerance in the line parameter; with no bounds it uses `_minimize_scalar_brent(...,
tol=xtol*100)` — a RELATIVE tolerance, `tol1 = tol·|α| + 1e-11`. So the θ-space search
differs from native in two ways at once: the coordinates AND the scalar minimiser under
each Powell step. Consequences: (i) V1's "same optimum" claim stands (a well-defined local
minimum is routine-independent) but its EVAL-COUNT comparison is confounded and must not
be read as the cost of the transform alone; (ii) P4 (tolerance re-derivation) is not
optional — `xtol` does not even mean the same thing on the two paths; (iii) the boundary
dust that killed run-7 seeds is a property of the BOUNDED routine, so it disappears for a
second, independent reason.

**F2 — Where the transform lives: a new module `Code/HA-Models/step1_param.py`,** beside
`step1_tm_targets.py` / `step1_tm_init.py` (NOT in `FromPandemicCode/`, per standing
rule). Forward map θ → (ς, β, ∇), inverse map, and the cap read via
`gic_taper_cap()` at call time. This keeps `FagerengObjFunc` in native coordinates (S1)
and makes the map unit-testable WITHOUT importing the estimator (which has no `__main__`
guard). V2 lives there.

**F3 — `check_maximum` sub-problems stay on `native` for now.** `find_Opt(check_maximum=
True)` searches (ς, ∇) at a FIXED β ± deviation, and `find_Opt_splurge0`'s L-BFGS-B probe
searches ∇ at fixed β. With β fixed, `a_hi = β + κ∇` is not the free coordinate, so the
cap is not structural in that sub-problem under this parameterization; making it so needs
a different map (logit of `a_hi` between β and cap). `check_maximum` defaults to False and
is not on the multistart path, so it is left native and flagged, not silently converted.

**F4 — Startpoints map to finite θ.** Every grid point has `a_hi,0 = k·cap < cap`
(k ∈ {1−2τ/cap, 0.90}), ς₀ ∈ {0.01, 0.5}, ∇₀ ∈ {0.01, 0.05}: all interior, all finite in θ.

**F5 — Provenance.** The flag value prints in the run banner next to `POWELL_TOL` and
`[step1-engine]`; the gate reads it. `HAFISCAL_STEP1_PARAM` goes into
`Code/HA-Models/docs/ENV_FLAGS.md` (the guard test requires it).

## 7b. Results so far (2026-08-18 evening)

**V1 (ccarroll, arm64, three arms concurrent, ~4 h):**

| arm | evals | ς̂ | β̂ | ∇̂ | f |
|---|---|---|---|---|---|
| native, seed 1 | 1452 | 0.2997816 | 0.9795097 | 0.0294049 | 0.0016468702 |
| **theta, seed 1** | **936** | 0.2998432 | 0.9795229 | 0.0293898 | **0.0016468649** |
| theta, from the optimum | 220 | 0.2998402 | 0.9795225 | 0.0293903 | 0.0016468649 |

Same basin; theta's endpoint sits INSIDE run 7's eight-seed native spread (ς 0.29977–0.29987)
with an f 3.2e-6 (relative) BELOW the native arm's; and it got there in 64 % of the evals
(936 vs 1452 — recall F1: eval counts are not a clean measure of the map, the line-search
routine differs too; but the direction is favourable, not adverse). Starting from the
optimum, theta moves 3e-7 in ς and reports f = 0.00164686492 vs the anchor's
0.00164686555 — i.e. it REFINED the tolerance-probe optimum by 4e-7 relative: the ridge
bottom is flat at that level and every endpoint here lives on it. The plan's original V1
target of "≲1e-6 relative in parameters" was therefore unrealistic — the native seeds
themselves scatter 3e-4 in ς — and the honest statement is: same optimum to within the
native inter-seed spread, f at least as good, no MAXFEV, no pathology near the cap.
**V1 PASSES.** No tolerance retune was needed to get there (P4 becomes a refinement, not
a prerequisite).

**V3 (xubuntark, x86-64 Sandy Bridge, ~28 s/eval):** the shelf, measured. At the optimum's
(ς, ∇), sweeping the top atom's effective margin m = cap − a_hi:

| m | native: (df/dβ_nominal)/(df/da_eff) | theta: (df/dθ_hi)/(df/da_eff) |
|---|---|---|
| 0.006→0.005 (outside band) | 1.000 | −5.5e-3 (= −m) |
| 0.0029→0.0025 (optimum) | 1.000 | −2.7e-3 |
| 0.002→0.0017 (band edge) | **0.625** (the kink; 2/π = 0.637 predicted) | −1.8e-3 |
| 0.0011→0.0008 | 0.287 | −9.3e-4 |
| 0.0006→0.0004 | 0.090 | −4.8e-4 |
| 0.0002→0.0001 | 0.0078 | −1.3e-4 |
| 0.0001→0.00005 | **0.0020** | −6.2e-5 |

Native's responsiveness drops by a factor 500 across the band, with a kink at the edge —
to move the effective top atom from cap−1e-4 to cap−5e-5, nominal β must move 0.0255.
Theta's responsiveness is exactly −(cap_eff − a_hi): smooth, no kink, proportional to the
margin, zero only AT the cap. Both agree bitwise on f at every matched effective atom
(same atoms), and f rises steeply toward the cap (113 at m=5e-5 vs 0.0016 at the optimum),
which is why an unbounded line search does not run to the cap. **V3 confirms the mechanism.**

**Cross-machine bits, for the record:** dell `…5354`, xubuntark `…53535` (both x86-64;
different BLAS kernels — Sandy Bridge has no FMA), ccarroll = m5 `…53353` (arm64, and
identical across numba 0.65.1/0.66.0). native == theta bitwise on every machine at the
optimum (V2 ×4).

**Run 7 (native, the matched control for V4) COMPLETED 14:03/14:20:** 8/8 seeds, one basin,
ς 0.2998440 (sd 2.9e-5), β 0.9795203 (sd 6.3e-6), ∇ 0.0293929 (sd 7.2e-6); gate HALT vs the
era-1 anchor by design, memo in `Code/HA-Models/Results/cold_rerun_2026-08/s1_run7/`.

## 8. Sequencing

```
P0  step1_param.py forward/inverse + V2 (unit-level identity test) FIRST — it defines
    "the transform is correct" independently of any search behaviour  [now; no compute]
P1  wire the flag into find_Opt / find_Opt_splurge0 / grid builder / banner; V2 must
    pass bitwise; native path must reproduce today's anchors byte-for-byte  [now]
P2  V1 inert-taper equivalence on dell — 27 idle cores while run 7 runs; cannot perturb
    run 7 (byte-identity under concurrency proven) and is not a wall benchmark. If a
    V1 pilot hits MAXFEV under Brent's relative tol (F1), reorder: P4 before P2.
    Then V5 on m5 after run 7's m5 shard finishes.
P3  V3 shelf measurement — the affirmative case, for the record
P4  re-tune tolerances (§6) via the same A/B design as 2026-08-18
P5  re-express the multistart grid in θ (S7); gate legend check (S10)
P6  V4 full battery, compare against run 7 as the matched control
P7  owner ruling: flip the default, delete the taper (S2/S3), retire
    HAFISCAL_STEP1_TAPER_THRESHOLD, update ENV_FLAGS.md and the docs map
```

P0–P2 are ~1 day including wall time and answer the question that matters (is the
transform right, and does it reproduce the answer where it should). P4/P6 are the
expensive parts and should not start until P2 is green.

---

## 9. Risks

- **Silent Jacobian error.** A wrong transform can still produce a plausible optimum. V2
  (bitwise identity at fixed parameters) is the defence — it cannot be satisfied by a
  transform that is merely close.
- **Re-tuned tolerances become a second change.** V4 would then confound
  reparameterization with tolerance. *Mitigation: P4 before P6, and V4 run at the θ-space
  tolerance whose implied β resolution matches run 7's.*
- **The straggler prediction fails.** If seeds 7/8 still straggle in θ-space, the shelf was
  not the mechanism and the τ-thread's premise needs revisiting. That is a useful negative
  result, not a wasted run — record it either way.
- **FTI/diagnostic breakage** (S11/S12). Those files import the cap and the taper. They are
  opt-in paths, so breakage is not on the default route, but it must not be discovered by a
  future user.

---

## 10. Transform arithmetic, checked

Round-tripping the optimum's measured atoms through §2 (independent of any code):

```
a_hi = 1.004714, a_lo = 0.954331   ->   beta = 0.9795225000, nabla = 0.0293900833
of record:                              beta = 0.9795223672, nabla = 0.0293902812
```

Agreement to ~1.3e-7 in β and 2e-7 in ∇, which is the rounding in the 6-dp census atoms the
endpoints were read from — not a defect in the mapping. V2 must be run on full-precision
atoms, not the census.

```
sigma(theta_hi) = 0.9970896305     theta_hi =  5.8366     (logit form)
log(cap - a_hi) = -5.8419                                 (pure-log form)
d a_hi / d theta = 2.8950e-03
```

## 11. Anchors of record (pre-change)

Preserve for comparison; all at ς=0.29984030318959165, β=0.9795223672003747,
∇=0.029390281157148056, τ=0.002, xtol=1e-6, ftol=1e-8:

```
jhu-dell     f = 0.001646865550005354     (x86-64)
ccarroll-m5  f = 0.0016468655500053353    (arm64)
TAPER_CENSUS at the optimum: n_in_taper=0, n_pinned=0, nominal==effective
top atom 1.004714  vs  band floor 1.005617  ->  clears by 9.0e-4
```

The census line is what makes V1 valid: **the taper is provably inert at the optimum**, so
any difference V1 finds is attributable to the search, not the model.
