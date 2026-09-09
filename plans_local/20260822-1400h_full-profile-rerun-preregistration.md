# Full-profile rerun — pre-registration (gates frozen BEFORE the seam test runs)

**Owner rulings (2026-08-22 ~14:00):** (1) test the continuation-at-full seam
STANDALONE first; (2) Step-2 smoke; (3) pre-register now — this document; (4) caches
WARM for these tests and everything up to the full-profile run; the full-profile
install rerun itself parks caches (cold). Scope of the eventual rerun: Steps 1, 2,
5a, 5b (+S=3); Steps 3 and 4 excluded as robustness. All outputs `_candidate`;
installation = a separate reviewed promote (QE freeze standing).

## Pre-registered acceptance gates (comparators all on disk today)

**G-A. Seam test: env-clean `HAFISCAL_SOLVE_GRID_PROFILE=full` continuation
(standalone, wt3, warm, sequential — exactly the execution shape the install
rerun's Step 1 will use; its FIRST run at the fine grid).**
- A1 stage-1 unanimity: ≤1e-4 relative (expected ~1e-8 class, as at the fast grid).
- A2 stage-1 (β̂₀, ∇̂₀) vs the installed Splurge-0 SoR (0.9263754327132292 /
  0.09001127614153807): |Δβ| ≤ 0.01%, |Δ∇| ≤ 0.2% (the fast-grid basis effect was
  −0.0061%/+0.073%; at full it should collapse toward zero).
- A3 stage-2 endpoint vs the installed main SoR (0.299869842312644 /
  0.9795228226132132 / 0.029390125527173155): |Δς| ≤ 0.1%, |Δβ| ≤ 0.006%,
  |Δ∇| ≤ 0.2% — i.e., INSIDE the fresh CTRLF battery's own cluster spread
  (0.086%/0.005%/0.18%); CTRLF's winner is the certification comparator
  (its winner ≡ SoR at −0.009%/+0.000%/−0.002%).
- A4 wall recorded (expected ~100–110 min sequential; informs the rerun ETA).

**G-B. Step-2 smoke (College, single start, HEAD, warm): the only stage not
re-measured this week.**
- B1 completes cleanly at the default engine/config with the expected grid echoes.
- B2 (β, ∇) vs the installed DiscFacEstim College row (0.9929746941368701 /
  0.014677786363168077): |Δβ| ≤ 0.06% (the TM≡MC precedent), |Δ∇| ≤ 1%.
- B3 wall recorded (README vintage says ~15 min for all three groups).

**G-C. The eventual full-profile rerun (launch gated on G-A and G-B passing):**
- C1 Step 1 (continuation at full): gates A1–A3 applied in-flight; Step 2 must not
  start on a Step-1 failure (phase-gated driver, not bare do_all).
- C2 Step 2 (all three groups) vs installed DiscFacEstim: |Δβ| ≤ 0.06%, |Δ∇| ≤ 1%
  per group.
- C3 Step 5a Baseline multipliers vs the belief-consistent epoch anchors
  (Check 1.236 / TaxCut 1.015 / UI 1.247): |ΔM| ≤ 0.005 per policy (nothing this
  week touched the FromPandemicCode solve paths — S1-side and opt-in changes only).
- C4 Step 5b welfare-6 cells vs the spine-4/part-D tables: within the measured
  seed band (≤0.5% class per cell), S=3 via per-seed out-dirs (the 878b0475
  pattern; the seed-overwrite trap is the named risk). NOTE (2026-08-22 ~16:05):
  C4 now ALSO certifies the welfare path's new ATI-on default (owner ruling
  "otherwise ATI is the default"; parity class ~2e-4 policy sup-norm ≪ the band;
  solution-cache keys include STEP5_ATI, so the flip cold-misses old caches by
  design).
- C5 cache policy: COLD (park) for this run only; warm everywhere else.
- C6 provenance sidecars on; run from a tagged commit; all writes `_candidate`.

Failure handling: any gate failure HALTs the phase (cascade), report, no promote.

## Verdicts

**G-B (Step-2 smoke): PASS (2026-08-22 15:34).** B1 clean (correct grid echoes 237–241;
ATI ROUTED ×409 after the FTI-env fix — the first launch fail-softed to EGM because the
worktree lacked `HAFISCAL_FTI_REPO`; the killed-wrapper/orphan-python interlude is in the
process-hygiene memory). B2: College β=0.9930 / ∇=0.0147 / GICx=7.6004 ≡ the installed
DiscFacEstim row at print precision. B3 wall: **5.5 min** College single-start (ATI) ⇒
all-three-groups do_all shape ≈ 12–16 min, confirming the README ~15 min figure.
**Driver requirement absorbed:** the rerun exports
`HAFISCAL_FTI_REPO=/home/shared/github/llorracc/fast-time-iteration` for Steps 2/5
(production convention); Step 1 needs no FTI (EGM default, matching every certified S1
result).

**G-A (seam: continuation at PROFILE=full, knots8 inherited): A1 FAIL / A2 FAIL /
A3 PASS / A4 recorded (2026-08-22 16:55, wt3).**
- A1 FAIL (marginal): stage-1 unanimity spread 1.268e-4 vs ≤1e-4, ∇-driven (β
  spread 1.05e-5; ∇ endpoints 0.0898632–0.0898746). The loud-fallback fired as
  designed (first live trigger) → dispersed 8-start battery ran; `Splurge0.txt`
  correctly withheld.
- A2 FAIL (marginal, from the 4 stage-1 files): β +0.0119…+0.0129% vs ≤0.01%;
  ∇ −0.153…−0.166% vs ≤0.2% (passes). At the fast grid the same protocol gave
  −0.0061%/+0.073% — the shift appears at full+knots specifically.
- A3 PASS: min-f winner sp3 (f=0.001645704487) vs SoR: ς +0.0400% / β +0.00245%
  / ∇ −0.145%, all inside gates. CTRLF phenomenology reproduced: 5-start tight
  cluster + the 0.3011 attractor (sp1/sp5: +0.41%/+0.023%/−0.93%, f≈0.0016467,
  0.06% f-margin below winner) + one straggler (sp7). sp8 re-found the SoR to
  +0.0001% ς and f-ties sp3 at 1.1e-5 relative — winner-wander inside the flat
  valley, both inside gates.
- A4: ~2h27m (stage-1 ~22 min + fallback battery ~2h05m); the unanimity-holding
  continuation shape would have been ~40 min.
- Disposition: per the pre-registered contingency, the one-axis A/B
  (KNOTS=0 at PROFILE=full, same protocol/worktree/env) launched 16:58 —
  attribution test for the unanimity/A2 shift and certification of the
  KNOTS=0 install pin. Artifacts of this arm preserved at
  ~/coldrun_2026-08/seam_knots8_results/; log seam_full_continuation.log.

**Contingency arm (KNOTS=0 @ PROFILE=full, one-axis A/B): branch-2 CONFIRMED;
launch config `--knots 0 --allow-s1-fallback` (2026-08-22 19:35, wt3).**
- Stage 1: unanimity ALSO failed — spread 1.588e-3 (12.5× the knots8 arm's) →
  the full PROFILE, not the knots, breaks stage-1 agreement. Two earlier
  hypotheses REFUTED: knots neither roughen stage 1 (they tightened it) nor
  shift the optimum (knots0 sp1–3 land in the same 0.92649/0.08988 stop-family
  as all four knots8 starts). Root phenomenon: the full-grid ς=0 valley is
  flat at ~1e-5-relative f — COBYQA stop-points scatter ~1.5e-3 in ∇ below the
  objective's resolution; the ≤1e-4 unanimity spec is fast-grid-calibrated.
- Lineage continuity, three ways: k0-sp4 stage-1 endpoint ≡ the installed
  Splurge0 SoR BITWISE (0.9263754327132292/0.09001127614153807) and is the
  stage-1 min-f stop (f=0.016503842 vs cluster 0.016503949+); the attach
  probe's f at the main SoR = 0.001646862911722531 ≡ the frozen fidelity pin
  to all printed digits; battery min-f winner (sp1, f=0.001646864916)
  reproduces the SoR at ς −0.0085% / β +0.000027% / ∇ −0.0019% — CTRLF
  certification class (CTRLF winner: −0.009%/+0.000%/−0.002%).
- Battery A3 gate: formal PASS under branch-2 semantics (--allow-fallback:
  A1/A2 informational, A3 binding); 7-start cluster + 1 straggler (sp7,
  −0.47%/+0.96%, min-f-filtered — same straggler startpoint family as CTRLF
  s7 and the knots8 arm's sp7).
- Follow-up (NOT tonight; owner review with both arms' data): stage-1
  acceptance recalibration for full grids — f-tie criterion (starts f-tie
  within ~1e-4 rel → min-f selects) instead of parameter-space unanimity;
  tonight's data would then select the installed SoR bitwise and restore the
  ~40-min continuation shape at full.

## Overnight run verdicts (2026-08-23, 01:17–02:2x; autonomous per approved protocol)

**S1: PASS** (157 min, fallback battery per branch 2). Reproduction is BITWISE vs the
afternoon contingency: A3 endpoint ≡ wt3 knots0 winner to every digit; stage-1 spread
1.588e-3 (≡). A2 note for honesty: the gate's delta-0.000 read the pre-existing
INSTALLED `Splurge0.txt` (the protocol correctly withheld a fallback-tainted write);
informational under the waiver either way.

**S2: PASS after driver fix** (17 min). Two driver bugs (both mine, both mechanical,
fixed + pushed 01:2x): the ATI tripwire grepped my paraphrase "ATI ROUTED" instead of
the literal `[step5-ati] ROUTED:`; the C2 gate read per-edType single-group artifacts
(stale mtimes) instead of the full-run combined `DiscFacEstim_CRRA_2.0_R_1.01_TM_a_ESC.txt`.
Reality: FTI routing healthy (1113 lines; qualified atoms ROUTED, low-β
patience-skips per design); fresh combined estimates written FROM tonight's S1 winner
(footer ς=0.29984); C2 deltas 4.6e-7…4.3e-5 rel — 100–1000× inside gates. Third
driver lesson: a `--from` resume always sees the run's own staged outputs as dirt →
`--allow-dirty` is required on resume (design fix queued: skip the clean-check when
FROM > s1).

**S5a: gate C3 FAILED — attributed to STALE ANCHORS, not regression.** Fresh
multipliers 1.258 / 1.258 / 1.027 (check/UI/taxcut) vs anchors 1.236/1.247/1.015;
whole table shifted up ~+0.5–1.5%, shares unchanged. Refuted: parser (table is
genuine; twin 1.258s a rounding coincidence); ATI flip (the 08-07 anchor-producing
run itself had STEP5_ATI=1, same c96 tier, same aMax). CONFIRMED two-way epoch
mismatch, from the runs' own calibration echoes:
- anchor run (f6c7e615, 08-07) loaded the EPOCH-PRE calibration (Dropout atoms center
  0.7378, ∇≈0.3035) — the current run-13 SoR (0.7481/0.2916) was installed 08-19
  (f581985b), AFTER the anchor table was generated;
- GIC caps differ ~+0.006 per group (tonight 1.00872/1.01068/1.01142 vs anchor
  1.00268/1.00464/1.00537) — the 08-14 FVAC-drop ruling; anchor College ran 1/7
  atoms AT the cap, tonight 0/7.
The pre-registration's claim "nothing this week touched the FromPandemicCode solve
paths" missed that the 08-14 cap ruling and the 08-19 calibration install BIND Step-5
agents. Tonight's values are presumptively the CORRECT first multipliers of the
current epoch. End-to-end proof arm in flight: 5a re-run AT f6c7e615 in wt3
(expect ≈1.239/1.249/1.017; verdict appended below).

**C4 comparator audit (before S5b ever ran):** the gate's wired reference
(`Tables/Baseline/welfare6_parallel_summary.json`) is dated MAY 16 — three months
stale. The spine-4 packet's welfare candidate is seed 2 ALONE (the seed-overwrite
trap). There exists NO clean current-epoch S=3 welfare comparator; tonight's S5b
(per-seed dirs) would create the first. C4's honest reformulation: (i) internal
3-seed band ≤0.5%/cell; (ii) vs the spine4 seed-2 table, informational.

**Morning decisions for the owner:** (1) accept the C3 attribution → tonight's run
becomes the epoch-defining anchor set (gate comparators re-anchored to it for future
reruns); (2) release S5b under the reformulated C4 (~1h); (3) the S7 adopt/certify
sitting then has the complete picture.

**C3 attribution PROVEN (03:02):** the f6c7e615 anchor arm (wt3, same tier/env shape)
reproduces the installed candidate at print precision — 1.239/1.248/1.016 vs installed
1.239/1.249/1.017 (Δ ≤ 0.001 = print/input-drift class) — against tonight's
1.258/1.258/1.027. Same code+inputs ⇒ same table; the C3 delta is entirely the
08-14 cap ruling + 08-19 run-13 calibration install. VERDICT: tonight's multipliers
are the correct first values of the current epoch; the C3 anchors were stale.

## Protocol amendment (owner-ruled 2026-08-23 morning): proven-benign gate failures
do not idle the machine

When a gate failure is dispositioned DURING the run by hard evidence as either
(a) **mechanical** — driver/gate wiring, not the pipeline (e.g., wrong grep literal,
wrong artifact filename), or (b) **stale-comparator** — an A/B at the comparator's
own producing commit (or equivalent provenance proof) shows the anchors predate
owner-ruled model changes and the pipeline reproduces the old world at print
precision — then later phases that are **computationally independent** of the failed
phase MAY be run **informationally** without waiting for morning:
- their results are labeled INFORMATIONAL (no gate-pass claimed, nothing promoted);
- the failure's disposition (re-anchor / fix) remains an owner decision at the
  morning sitting — the informational run merely ensures the evidence base is
  complete when that sitting happens;
- the evidence and disposition MUST be appended to this pre-registration BEFORE the
  informational phase launches (the record precedes the run);
- mechanism: `--from <phase> --allow-dirty` (the resume path), with the
  informational labeling recorded here.
A failure with NO proven-benign disposition keeps the original hard-cascade rule:
halt, preserve, report, wait.

**D1 + D2 RULED (owner, 2026-08-23 morning: "one word to launch them now").**
D1: the C3 attribution is ACCEPTED — tonight's tagged run (rerun-full-20260822-2222 +
-0123) is the epoch-defining anchor set; S5A_ANCHORS re-anchored to 1.258/1.258/1.027
(old 1.236/1.247/1.015 retired as stale, kept in comments). D2: S5b RELEASED under
the reformulated C4 = internal 3-seed band (each seed's cell within 0.5% of the
cross-seed mean; ui_norec excluded) + spine4-seed2 comparison informational in the
report (its wired May-16 predecessor is retired). Launch: --from s5b, cold caches,
per-seed dirs; ~2.5–3 h.

**S5b first launch (07:42) died mechanical:** the C5 park moved the whole
`solution_cache/` — which is also the CODE PACKAGE welfare6_scenario imports
unconditionally → ModuleNotFoundError in every scenario child. Fix: park only the
no-`.py` data subdirs (package stays importable; fresh-entry collision on restore
handled absent-only). Pre-authorized mechanical lane; relaunched --from s5b.

**S5b ran to completion (07:43–09:27; seeds 105/103/97 min→ wait — see logs; 3/3 rc=0).
C4 tripped on ui_rec + ui_rec_AD only — dispositioned MISWIRED GATE (proven benign):**
my 0.5% band was calibrated on the quiet cells; the preserved 08-10 S=3 artifacts at
this exact config (solution_cache/_armc_bench/seedband_S3_0810) show the UI-recession
cells' cross-seed scatter has ALWAYS been ~±2% (seed1 ui_rec 1.7333 vs seed2 1.8096 =
4.3% range; ui_rec_AD 4.5%) — small effective N (benefit-exhausted subpopulation).
Tonight's seeds (ui_rec 1.7365/1.7699/1.7993; ui_rec_AD 2.0789/2.1175/2.1368) sit
INSIDE the historical range. Every other cell passed at ≤0.3%. Gate fix: per-cell
bands — ui_rec/ui_rec_AD 3.0% (covers the measured ±2.2% half-range with margin),
all other cells keep 0.5%. Phase completed from the existing seed artifacts (gate
re-run + band table); no recompute.

**D4 IMPLEMENTED AS DEFAULT (owner: "implement this as default", 2026-08-23 ~10:00):**
stage-1 acceptance = parameter unanimity OR f-tie ≤1e-4 relative (log-midpoint of the
measured classes: widest one-basin tie 8.1e-6, smallest distinct-attractor gap 6.1e-4).
Module `step1_stage1_acceptance.py` + guard `test_step1_ftie_acceptance.py` (5/5,
pinned to the 08-22/23 records; knots0-full record → accept via f-tie, min-f = the
installed Splurge-0 SoR bitwise). Wired into the estimator's continuation block;
banner now reports both spreads and the accepting arm.
