# Morning report — 2026-08-25 (overnight run of the 2026-08-24 arc)

*(final, 07:25 EDT — §§1–6 are the 21:22 arc (both batteries, BUG-090/091, store contract);
§7 is the AD-equilibrium sharing you asked for at 01:00, finished at 07:20, including the new
BUG-092 it exposed. Decisions for you: §4 items 1–4 and §7's (5)–(7).)*

## 1. What you asked for last night, and what happened

**"Run the Baseline S=3 welfare re-battery for both worlds."** Launched 21:22 on code
793eb539 (all of yesterday's fixes). Strict store mode is now the welfare battery's default,
so each machine first ran the multiplier program to populate its own store and the welfare
batteries then loaded every policy and solved nothing.

| world | machine | multiplier (populate) | welfare seeds 0 / 1 / 2 | store use | C4 band gate |
|---|---|---|---|---|---|
| as-corrected | m5 | 55 min, 89 entries; table 1.249 / 1.258 / 1.015 (= dell's) | 16 / 7.5 / 8 min | 630 / 546 / 546 hits, **0 solves, 0 misses** | **PASS** (24/24) |
| default | dell | 67 min, 84 entries; table 1.258 / 1.258 / 1.027 (unchanged) | 21 / 21 / 20.5 min | 651 / 651 / 650 hits, **0 solves, 0 misses** | **FAIL on `check_rec_AD` seeds 0 & 2 (0.77 % / 0.71 % vs the 0.5 % tolerance) — the identical two failures the 08-23 default rerun had (+0.78 % / −0.68 %)**; 22/24 pass |

For scale: the same as-corrected battery took 1 h 45 min per seed on m5 on 08-24 (cold).
Seeds 1–2 reuse seed 0's AD fixed point by convention (RECONCILED-004), hence the shorter
walls and fewer loads.

## 2. Welfare tables of record — what moved and why

### As-corrected (W-FIX column) — S=3 means, SE in brackets

| cell | accert (08-24, pre-fix) | now | Δ | cause |
|---|---|---|---|---|
| check_norec | 0.9631 | 0.9631 [0.01 %] | 0 | — |
| taxcut_norec | 0.9850 | **0.9896** [0.00 %] | +0.46 % | BUG-091 |
| check_rec | 1.0137 | 1.0137 [0.08 %] | 0 | — |
| ui_rec | 1.8187 | 1.8188 [0.71 %] | 0 | — |
| taxcut_rec | 0.9862 | **0.9919** [0.03 %] | +0.58 % | BUG-091 |
| check_rec_AD | 1.3881 | 1.3905 [0.16 %] | +0.17 % | seeds 1–2 now share seed 0's AD path (RECONCILED-004); seed 0 identical |
| ui_rec_AD | 2.1875 | 2.1970 [0.41 %] | +0.43 % | same |
| taxcut_rec_AD | 1.1709 | **1.1513** [0.06 %] | **−1.67 %** | BUG-091 |

Every non-tax cell reproduces the accert values *per seed* to 4–5 decimals wherever the
seed's AD path is the same — the store, the ATI ladder and strict mode changed nothing
there. BUG-090 does not touch this world (verified at Baseline scale).

### Default (CURRENT column) — S=3 means; per-seed deltas vs the 08-23 rerun (same seeds, same machine, same engine)

| cell | 08-23 rerun (pre-fix) | now | Δ (mean) | per-seed Δ (s0, s1, s2) | cause |
|---|---|---|---|---|---|
| check_norec | 0.9629 | 0.9624 | −0.05 % | −0.04, −0.05, −0.06 | BUG-090 (small) |
| taxcut_norec | 0.9852 | **0.9898** | **+0.47 %** | +0.48, +0.46, +0.48 | BUG-091 |
| check_rec | 1.0133 | 1.0127 | −0.05 % | −0.04, −0.05, −0.08 | BUG-090 (small) |
| ui_rec | 1.7686 | **1.7650** | **−0.20 %** | −0.14, −0.18, −0.29 | BUG-090 |
| taxcut_rec | 0.9859 | **0.9916** | **+0.58 %** | +0.61, +0.57, +0.57 | BUG-091 |
| check_rec_AD | 1.3785 | **1.3754** | **−0.22 %** | −0.23, −0.19, −0.26 | BUG-090 |
| ui_rec_AD | 2.1111 | **2.1043** | **−0.32 %** | −0.26, −0.30, −0.40 | BUG-090 |
| taxcut_rec_AD | 1.1596 | **1.1386** | **−1.81 %** | −1.80, −1.81, −1.84 | BUG-091 |

The per-seed deltas are tight (each bug moves every seed by nearly the same amount), which is
the signature of a deterministic construction change rather than noise. Cross-seed SEs (this
battery): UI cells 1.0 % / 0.8 %, check_rec_AD 0.43 %, the rest ≤0.17 %.

**Why the default-world band is wider than the as-corrected one and why C4 "fails" — CORRECTED
at 07:20.** My first explanation (each default-world seed solved its own AD fixed point under
the hybrid engine, so its AD cells carry AD-path variance) turned out to be wrong for the cell
that fails: the shared-equilibrium battery (§7) puts all three seeds on ONE equilibrium and
`check_rec_AD` still scatters exactly as much (SE 0.41 % vs 0.43 %; C4 fails on the same two
seeds, 0.66 % / 0.74 % vs 0.5 %). That scatter is welfare-simulation variance of the uncapped
(perpetual-youth) default world — the as-corrected world (T_age=200) has 0.17 % on the same
cell. (UI and tax-cut AD cells did tighten on the common equilibrium: 0.81 → 0.58 % and 0.13 →
0.08 %, so a part of THEIR band was AD-path variance.) The 0.5 % C4 tolerance was dispositioned
for the UI cells on 08-23 (3 %); `check_rec_AD` in the default world needs the same treatment
(measured 0.7–0.8 % on three independent S=3 batteries). I did not move the gate — your call.

## 3. What changed in the code base yesterday (all on the working branch, pushed)

- **Shared solved-policy store** (P0–P5): default ON, per-machine at `~/.cache/hafiscal/policy_store`;
  one-sweep hit guard; entries carry the Newton-2D warm payload; solver-source hash in the key;
  `HAFISCAL_STEP5A_PARALLEL_SOLVE=auto` in the multiplier entry; the welfare workers run the same
  solver ladder (ATI for patient atoms) so entries are identical whichever program produced them.
- **Strict mode:** `HAFISCAL_POLICY_STORE_REQUIRE=1` (welfare entry points) — a store miss raises.
- **BUG-088/089** (ATI spurious fixed point; biased tail exponent) — fixed; multiplier tables
  re-run (default unchanged; as-corrected +0.001 on check/tax cut); S=3 multiplier seeds byte-identical.
- **BUG-090** (welfare ignored `PERM_DURING_UNEMP`) and **BUG-091** (welfare tax cut 10 quarters vs 8)
  — fixed; escape hatches `HAFISCAL_WELFARE6_LEGACY_UNEMP_INCSHK`, `HAFISCAL_WELFARE6_LEGACY_TAXCUT_BLOCKS`.
- Welfare SE table generator: `--summaries` mode (the archived accert band was all-nan; regenerated).

## 4. Decisions that are yours

1. **Promotion** of the new welfare candidates (QE freeze intact; CURRENT candidate staged at
   `Tables/CRRA2/welfare6_candidate.tex`, W-FIX welfare table refreshed in the artifact set).
2. Whether welfare should keep solving its patient atoms with ATI (welfare6 ≤1e-4, welfare4
   third decimal vs all-EGM) — reversible with `HAFISCAL_STEP5_ATI=0` in both entry points.
3. The dead parameters `TaxCutContinuationProb_Rec/_Bas` (stored, never read) — delete or wire.
4. The C4 band tolerance for `check_rec_AD` under the hybrid engine (0.5 % vs a measured
   0.7–0.8 % on two independent S=3 batteries): widen as was done for the UI cells on 08-23,
   or keep the gate red as a reminder that default-world AD cells carry AD-path variance.

## 5. Staged and regenerated (23:35)
- CURRENT welfare candidate ← default seed 0 (`Tables/CRRA2/welfare6_candidate.tex`, gitignored
  staging; previous 08-20 spine candidate archived in the artifact set).
- W-FIX welfare table ← as-corrected seed 0 (`artifacts_20260823_wfix/welfare6_wfix.tex`; the
  pre-fix file kept beside it), its S=3 SE band regenerated; UPDATES.md rebuilt (welfare rows in
  both columns changed; badge map unchanged, so the annotated PDF stands).
- Artifact sets: `conclusions_private/artifacts_20260825_rebattery/{default,as-corrected}/`
  (per-seed tables, summaries, sidecars, band gates, SE tables).

## 6. Store contract at Baseline scale
- dell ran the as-corrected multiplier program entirely from the store (158 hits, 0 saves,
  0 guard rejections; 36 min vs 65 min cold): `Multiplier_candidate.tex` **byte-identical** to
  the cold run's. The default-world multiplier table is byte-identical to the afternoon's re-run.
  Both multiplier tables are unchanged by anything done yesterday (1.258/1.258/1.027 and
  1.249/1.258/1.015).
- Cross-platform replication of one welfare seed (as-corrected seed 2, m5 vs dell, 00:35):
  every non-AD cell identical to **1e-13**; the AD cells differ by 0.06–0.41 % only because
  dell's seed 2 had no seed-0 AD entry to reuse (seed 0 ran on m5) and solved its own AD path —
  the RECONCILED-004 convention again, not a platform effect. (dell's copy kept as
  `Tables/Baseline_ac_r2_seed2_dell/`; the reported S=3 set is all-m5.)

All chains of the 21:22 arc finished at 00:34.

## 7. P6 — the welfare battery no longer solves the AD equilibrium either (your 01:00 ruling, implemented overnight)

**What you said.** "The welfare calculations should NOT SOLVE ANYTHING — everything has already
been solved in the spending engine; the point of the welfare analysis is to CALCULATE the
welfare consequences of the solution already obtained, which requires MC rather than TM."
Until tonight the four `_AD` welfare cells still re-solved the aggregate-demand fixed point
with their own MC iteration (warm re-solve ↔ simulate ↔ belief update) — the residual second
solve after the policy store, and the source of the default world's 0.7–0.8 % per-seed AD
scatter (each seed converged its own fixed point; §2).

**What was built (`HAFISCAL_AD_EQUILIBRIUM_SHARE=1`, opt-in tonight; the default flip is yours).**
- Step 5a (TM), right after its AD-TM block, publishes each recession scenario's equilibrium
  into the shared store: the trained belief `CFunc`, the AD-on elasticity, and every
  household's policy solved at that belief (`solution_cache/equilibrium_store.py`; entries
  under `~/.cache/hafiscal/policy_store/equilibrium/`).
- Step 5b's `run_recession_AD` installs that pair and SKIPS its AD loop; the unchanged
  post-loop restore + MC simulation follows. Under strict mode a missing equilibrium is an
  error, like a missing policy. The AD cells are now pure MC measurement on the spending
  engine's equilibrium — in both worlds, for every seed, so seed bands carry simulation
  variance only.
- **Key = the model** (every agent's policy-store primitives for the scenario, the AD inputs,
  the world, the solver source). The producer's conventions — its AD tolerance / iteration
  cap / TM discretisation — are deliberately NOT in the key: the consumer never iterates, so
  it has nothing to match; it wants *the* spending program's equilibrium. They ride in the
  entry's meta, print on every HIT and in the welfare log ("AD loop SKIPPED … AD tol=0.01,
  max iters=…; this battery's own cutoff NOT used"), and a re-publish with different
  conventions replaces the entry.

**How the gates went (m5, Reduced_Run, both worlds).**
- Gate 1 (05:31): 5a published 4 equilibria per world; the welfare battery MISSED all four.
  I added a miss explainer (the error now names the nearest entry's differing fields) and it
  found a single leaf: `HAFISCAL_AD_CONVERGENCE_TOL` — the multiplier entry point setdefaults
  `1e-2` (STANDARD tier), the welfare battery leaves it unset. Everything else matched exactly.
  That is what led to the key principle above.
- Gate 2 (05:50, 7c6089b9): PASS. Per world: welfare with sharing took 4 equilibrium HITs,
  skipped all 4 AD loops, 0 policy saves, 0 misses, 4 tables (37 s vs 62 s for the
  own-loop reference); a store without equilibria fails loudly on every AD cell; non-AD cells
  identical to the last digit. **AD cells move by the TM-vs-MC fixed-point gap** — at
  Reduced_Run (5 iterations, tol 1e-2, 5000 agents; loose by design): default −3.4 % / +1.6 %
  / −0.4 % (check / UI / tax cut), as-corrected +0.4 % / −0.6 % / −1.0 %.

**Baseline S=3 on the shared equilibrium (launched 06:01; dell default, m5 as-corrected).**
Each machine re-ran the multiplier program with sharing on (all policies from the store, 0
solves; 40 / 43 min) — its multiplier table stayed **byte-identical** to last night's in both
worlds (publishing has no side effect on 5a) — then the three welfare seeds, each taking 4
equilibrium HITs and skipping all 4 AD loops (630 policy hits, 0 solves, 0 misses per seed).
Non-AD cells reproduce last night's battery to the last digit (untouched path); only the AD
cells move, by the TM-vs-MC fixed-point gap:

| world | seed wall (was) | C4 band gate | check_rec_AD | ui_rec_AD | taxcut_rec_AD |
|---|---|---|---|---|---|
| as-corrected (W-FIX) | 5.7 / 5.5 / 5.5 min (16 / 7.5 / 8) | **PASS 24/24** | 1.3905 → **1.4038** (+0.96 %) [SE 0.17 %] | 2.1970 → **2.1859** (−0.50 %) [0.42 %] | 1.1513 → **1.1461** (−0.45 %) [0.06 %] |
| default (CURRENT) | 11.8 / 12.0 / 11.7 min (21 / 21 / 20.5) | FAIL 22/24 — `check_rec_AD` seeds 0 & 2 (0.66 % / 0.74 %), the same two as before | 1.3754 → **1.3044 (−5.16 %)** [SE 0.41 %] | 2.1043 → **2.1156** (+0.54 %) [0.58 %] | 1.1386 → **1.1300** (−0.75 %) [0.08 %] |

At two decimals the W-FIX welfare6 AD row goes 1.39 / 2.21 / 1.15 → **1.41 / 2.20 / 1.15**;
the CURRENT row goes 1.39 / 2.10 / 1.14 → **1.31 / 2.10 / 1.13**.

**The default world's −5 % on the check is a bug, not "the gap" (BUG-092, OPEN).** A 5 %
disagreement between two fixed-point methods on the same household problem — five times what
the as-corrected world shows — needed an explanation before 8am, so I ran three Reduced_Run
discriminators on m5 while dell finished (all default world; each compares the welfare battery's
own HARK-MC AD loop with the TM equilibrium):
- plain default world: check **+4.4 %** apart (the hybrid loop agrees with the HARK loop to ~1 %
  — the two MC engines are not the issue);
- V1, `PERM_DURING_UNEMP=off` (the only other economic difference between the worlds): still
  **4.2 %** apart — not the income convention;
- V2, `T_AGE=200` (the as-corrected age cap): **0.3 %** apart — collapses.
So: **in the uncapped (perpetual-youth) world, the TM AD equilibrium disagrees with both MC
engines by 4–5 % on the check's AD welfare; under an age cap the methods agree within 1 %.** The
uncapped TM path (Doob π_Q baseline instead of the cohort-age one; raw `LivPrb` in the AD
propagation) is the default world's production path. **Localized the same morning (your
request):** neither the Doob baseline nor the propagation mortality is the site; the root is
the uncapped world's ergodic permanent-income distribution — with 2 %/yr growth and no kill
date, `E[p]` is 4.7× the entry level and carried by households ~186 years old (college: E[p]
≈ $300k/yr uncapped vs $102k/yr capped; 29 % above the check's phase-out vs 17 %). The TM
computes that analytically; a finite-N MC realizes it 11–18 % low; the two engines' baseline
consumption levels differ by 16 % and their Cratio responses by 25–40 %. **The multiplier
table is NOT exposed** — the `mc` engine reproduces the TM's AD check multiplier to +0.3 %
(each engine is self-consistent); what disagrees is the belief `CFunc` that sharing hands
from 5a to welfare, which `mill_rule` turns into the realized AD factor. Not a code defect:
a property of the uncapped world (the 2026-07-27 cap removal, applied to both engines — the
cap was not forgotten in MC). Record: `BUGS_private/HAFiscal_BUG-092_*.md`. Decision:
restore the paper's T_age=200 in the default world (all engines agree ≤1 %), or keep
perpetual youth and pin the level objects to realized income. The as-corrected world is
unaffected.
The welfare4 table's AD-consumption row `C(Rec, AD, policy)` moves more — 2.742 / 4.288 /
2.520 → 2.834 / 4.301 / 2.526 (+3.4 % / +0.3 % / +0.2 %), the same shift on every seed —
i.e. the TM equilibrium's consumption path differs from the MC loop's most for the check.
Artifact set: `conclusions_private/artifacts_20260825_rebattery_eq/{as-corrected,default}/`
(per-seed tables, summaries, sidecars, band gates, SE tables, `shift_vs_r2.txt`, logs).

**Two facts you should know before reading those numbers.**
1. The shared equilibrium is converged to **5a's tolerance, 1e-2** (`AggFiscalMAIN_reduced.py`
   setdefault, every tier), whereas the welfare loop it replaces used Parameters' 1e-3 at
   Baseline. Under your ruling that is correct (5a's solution is the solution), but if you
   want the AD cells on a tighter fixed point, the place to tighten is Step 5a.
2. RECONCILED-004 ("seed 0's AD point shared across offsets") described the `hark` engine's
   convention; the hybrid engine never shared (each seed re-solved). With sharing on, BOTH
   worlds and all seeds sit on the one TM equilibrium — the convention RECONCILED-004 wanted,
   now by construction. I will amend that record once the Baseline numbers are in.

**Decisions added to §4:** (5) flip `HAFISCAL_AD_EQUILIBRIUM_SHARE` to default-on — safe for
the as-corrected world now (AD cells move ≤1 %, bands unchanged, 3× faster seeds); for the
default world it means adopting 5a's TM equilibrium while BUG-092 is open (check_rec_AD 1.375 →
1.304); (6) Step 5a's AD tolerance (1e-2 → 1e-3 costs 5a wall; it is the tolerance the welfare
AD cells now inherit); (7) BUG-092's arbiter while open: TM (your ruling's letter) or the MC
loop (the historical CURRENT column) for the default world's `_AD` cells — and whether the
default world should carry an age cap at all, since the cap is what makes the two engines agree.

Nothing was staged or promoted from the shared-equilibrium batteries: CURRENT and W-FIX stay on
last night's own-loop battery (§5) until you rule on (5)/(7). Both worlds' sharing artifacts
are complete and committed, so adopting is a copy, not a re-run.

All batteries finished 07:20; machines idle. Code: 7c6089b9 (store key principle + miss
explainer); records: BUG-092, RECONCILED-004 amended, ENV_FLAGS, plan log, memory.
