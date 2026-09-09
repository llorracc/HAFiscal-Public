# S2/production solve path — test-then-implement plan

**Charge (owner, 2026-08-22 ~10:20):** "execute R1 and adopt R2, then make a plan to
test then implement the S2/production solve path." R1 (S1 REACH 12→6) executed
`47f43b33` (bitwise vs the K8R6 battery); R2 (install-at-full) adopted `db20753b`.
This plan brings the S1 program's modernized solve treatment to the
FromPandemicCode world — Step 2 (per-group discount-factor estimation,
`estim_phase2_tm_a.py`/`EstimParameters.py`) and the Step-5 production solves
(`AggFiscalModel`, `Parameters.py`) — under the same discipline that governed the S1
flip: solve-level certification → estimation batteries → production parity →
implement on pass. Cascade-gated; any gate failure HALTs and reports.

## 0. What is being tested (and what already exists)

Candidate: `HAFISCAL_SOLVE_GRID_PROFILE=hermite60` on the S2/production path — count
basis 60 (per-group grids Dropout 467/60, HS 551/60, College 591/61 vs the current
default's 237–241) + `HAFISCAL_SLICE_INTERP=hermite` (the T2a EGM-exact-MPC cubic
slices in the AggFiscalModel PF-decay solver — solve-level certified 2026-08-03) +
the certified measured-Q per-slice attach (unchanged). NOT initially in the
candidate: tail knots (S2 has no aXtraExtra wiring; decision node D1 below decides
whether it needs any) and farfield (stays the certification oracle, here too).

Already-measured evidence (Phase-0 recon, 2026-08-22):
- m5 F-program S2 College arm (4 cold starts, 2026-08-21): hermite60 β 0.9929 /
  ∇ 0.0146 vs full β 0.9930 / ∇ 0.0147, wall 6.0 vs ~24 min (4×); ATI-routed
  per-solve 0.05–0.10 s vs 0.16–0.30 s. Caveats: College only, 4-digit precision
  from the log (full precision in the wtF DiscFacEstim files), predates this week's
  fixes (which are S1-scoped: CHS rewrap, moments anchor — S2 code paths unaffected,
  verify in Phase 1 anyway).
- T2a certification (plans/20260803-2030h): hermite slices on the AggFiscalModel
  solver, 60–75-pt operating window, solve-level.
- The S1 program's transferable results: scatter is the discriminating axis;
  stragglers are generic and min-f-filtered; certification catches what estimation
  smoke misses; verify-in-log per arm (invalid-arms discipline).

Structural difference from S1 (drives D1): S2's TM dist grid runs to
`dist_aGrid_max=1300` > the per-group solve tops (467/551/591), so the measured-Q
attach serves [top, 1300] — a window with REAL ergodic mass (the College GIC-cap
atom's tail; the BUG-084 onset∧support ruling ratified 1300 at ρ=2, unaffected by a
count change — note, no re-run needed). S1's moments barely weighted its window; S2's
K/Y-and-Lorenz targets weight this one more. The College arm's ≈0.01% β pass suggests
the weight is still small; Phase 1 measures instead of assumes.

## 1. Phase 1 — solve-level certification (dell; build ~1h, run minutes)

Build `step2_attach_probe.py` (Code/HA-Models/; mirrors `step1_attach_probe.py`):
solve the three education groups' type lists at a given config via the REAL
EstimParameters/AggFiscalModel path (import-safe entry or the estim script's eval
mode — recon the cheapest honest hook first; NO replica), dump per-group-per-atom
cFuncs on a dense vector + grids + (κ̲, h̄, installed Q) + shock primitives.

Metrics and pre-registered gates (constants frozen from the first measurement pass,
×3–5 headroom, the S1 pattern):
- shape: gap>0, MPC ↓→κ̲, c↑ on [0, 2600] — required, every group × atom;
- window error: candidate vs the full-profile control AND vs a deep reference
  (count-basis 400) on **[top, 1300]** (the attach-served, mass-bearing window) and
  on the interior [1, top]; gate set after measurement;
- exponent certification: installed per-slice measured Q vs the farfield oracle
  (per-atom primitives) on farfield-healthy atoms — band 10% (the certified S1
  standard); report drift;
- fidelity guard: QE-fidelity/as-corrected must keep today's full-grid path
  bit-consistent (echo + objective pin, the S1 pattern).

**Decision node D1:** if the candidate's [top,1300] window error is ≤ the control's
own error class (both ride the same attach mechanics — likely), proceed WITHOUT
knots (simplicity). If the coarse basis materially degrades the window (attach
mis-identification at 60-count secants), wire per-group `aXtraExtra` knots in
EstimParameters covering [1.06×top, ≥1300] (College REACH≈2.2, Dropout≈2.8 — the
historical 2.2 default's origin) and re-certify. The S1 lesson says solved-values-
over-the-window beats attach-fidelity arguments; the S1 lesson ALSO says don't add
machinery the instruments don't demand.

## 2. Phase 2 — Step-2 estimation batteries (dell; ~2h)

All three groups × 4-start cold COBYQA (the BUG-083 ∇-box), candidate vs
fresh-control, sharded per the established pattern (per-start files; per-arm
worktrees wt2/wt3):
- gates: winner AND mode |Δβ| ≤ 0.06% (the TM≡MC precedent), |Δ∇| ≤ 1% vs the
  fresh-control battery; scatter ladder candidate-vs-control reported (pre-register:
  candidate scatter ≤ 4× control per param — S2's 4-start basins have less
  statistics than S1's 8; report-first discipline);
- cross-machine: College winner vs the m5 arm's values;
- adjudicator: extend the v4 pattern (`s2_adjudicate.py`).

## 3. Phase 3 — production (Step-5) parity (the long pole; overnight)

Cascade, cheapest first, HALT on fail:
- **3a smoke:** one recession policy multiplier at HS_Only-class config, candidate
  vs full (~tens of minutes) — gate |ΔM| ≤ 0.005;
- **3b welfare smoke:** one welfare-6 cell (HS_Only check_rec) through the hybrid
  engine at candidate grids — gate: within the seed-band class (≤0.5%);
- **3c the full pair:** Baseline Step-5a multiplier run, candidate vs full — the
  same-code A/B (NOT vs the belief-consistent epoch anchors — cross-epoch
  comparisons forbidden by the A/B-one-axis rule). Cost ~9.45h (full) + ~3–4h
  (candidate est.) → overnight, phase-boundary alerts per the standing convention.
  Gates: |ΔM| ≤ 0.005 per policy; Cratio paths within 1e-3-class.
- Provenance sidecars on all runs; no locked/frozen artifact is touched (outputs are
  `_candidate`-class or scratch worktrees; QE freeze standing).

## 4. Phase 4 — implement (on full pass; ~1h)

- Default flip at the S2/production sites: fidelity-guarded `setdefault` of
  `HAFISCAL_SOLVE_GRID_PROFILE=hermite60` at the EstimParameters entry (mirroring
  the S1 stack block; explicit env wins; QE-fidelity/as-corrected keep `full`), so
  Step 2, Step 5 and the welfare pipeline inherit it; Parameters.py needs no
  separate edit (same env, mirrored resolver).
- T5-style checks: env-clean per-group Step-2 seed runs bitwise vs the Phase-2
  battery shards; a Step-5 smoke re-run bitwise vs 3a.
- Records: ENV_FLAGS (profile entry gains the S2/production default note),
  README runtimes, decision doc (`conclusions_private/2026-08-22_s2-production-
  solve-path.md`), memory. R2 note: Step-2 SoR files are NOT re-installed by the
  flip — any future DiscFacEstim install runs `full` per the doctrine; the flip
  governs exploration estimation + the production SOLVES (where the wall win lives:
  Step-5a ≈9.45h → est. 3–4h; Step 2 ≈4×).

## 5. Kill criteria / non-goals

- Any pre-registered gate failure HALTs the cascade at that phase; report + no
  implement (the S1 program's precedent: two of its candidates died at exactly
  these gates).
- Non-goals: no knots unless D1 demands them; no farfield flight-path use; no
  welfare-engine changes; no SoR installs; no locked-table promotion; γ-row
  and Splurge0 S2 variants inherit whatever passes (spot-check only).

Walls: Phase 1 today (~1.5h incl. build), Phase 2 today (~2h), Phase 3 overnight,
Phase 4 tomorrow (~1h). Every battery/probe pattern reuses this week's committed
apparatus.

## 6. PHASE-1 VERDICT (2026-08-22 ~11:40): CASCADE HALT — no S2/production flip

The solve-level certification (step2_attach_probe.py over full/h60/h96/h120/deep-500,
3 groups × 7 atoms × 4 states, composed surface at Cratio=1 vs the deep reference)
kills the basis-reduction candidate at D1:

| worst interior rel-c err | full(240) | h60 | h96 | h120 |
|---|---|---|---|---|
| Dropout | 1.0e-3 | 1.3e-3 | 4.9e-4 | 4.6e-4 |
| Highschool | 1.2e-3 | 1.33e-2 | 5.7e-3 | 3.8e-3 |
| College | 1.5e-3 | **1.59e-2** | 6.8e-3 | 4.5e-3 |

The binding cells are the GIC-cap atoms (e2a6/e1a6), error BROAD across the whole
mass-bearing range (not localized), objective level at the SoR +40% (College h60),
still +1.1% at h120. Convergence rate ⇒ reaching the accepted 1.5e-3 class needs
~170–200 count-basis — the savings vs the 240 default evaporate. T2a hermite slices
were verified ACTIVE in every candidate probe (holder=PowerLawDecayCubicHermiteInterp)
— no wiring gap; the degradation is genuine basis under-resolution of the cap-regime
policies. NOTE: the m5 h60 ESTIMATION arm "passed" (β 0.01%) — an estimation-level
acceptance that would have shipped a 1.6% policy error into Step-5; certification
caught what the estimation could not. Phases 2–4 are MOOT per the cascade.

**Disposition:** the S2/production default stays full-count + certified measured
attach (unchanged — now evidence-backed rather than assumed). Knots for the
[top,1300] window buy nothing at full count (window error 6e-4–1.3e-3 = the interior
class already). Step-5 wall relief continues to come from the deployed ATI routing /
solution cache / parallel-solve machinery, not grid reduction. Deliverables kept:
the `HAFISCAL_STEP2_RUN_ESTIMATION=0` eval mode + `step2_attach_probe.py` = the
standing S2 certification instrument (the S1 suite's analog); per-group h96 is
certified for Dropout-only exploration if ever useful.
