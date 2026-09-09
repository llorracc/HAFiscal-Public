# Fix BUG-122: cap the UI extension at four quarters of benefits per spell

**Status:** COMPLETE — Steps 0-4 DONE (2026-09-06), **Step 5 DONE (2026-09-07)**: the bug record carries the measured materiality and the ruling; the revision memo's §2 ledger and the co-author briefing's §7 ledger both gain BUG-122 (`dfc28587`, which also removed the withdrawn BUG-043 from the briefing's published-code list); the documentation note is `RECESSION_MECHANICS.md`. One item raised for a ruling rather than decided: the briefing still quotes the pre-cap headline numbers in seven places (`plans_local/TODO.md`). Original status line follows. Steps 0-4 DONE (2026-09-06). Step 0 (the onset-spike timing fix) and Step 1-2 (the cap, `paper_capped`) are BOTH the DEFAULT in BOTH worlds, on the owner's rulings of that day ("when you have vetted and cleared it, this change will want to become the default"; "wire it into both worlds"). Step 3's G1-G8 are green. Step 4 measured at HS_Only and at Baseline, on two machines each. **Step 5 (records) is the remainder**, together with re-running the chain of record under the new defaults and deciding what co-authors are told. Owner ruling 2026-09-06: "if the paper as implemented gave anyone 5 quarters of
UI benefits, that was a BUG... the --as-corrected and default new machinery should properly give at
most four quarters of benefits to anyone"). Bug record:
`BUGS_private/HAFiscal_BUG-122_ui_extension_overpays_the_pre_onset_unemployed.md`.

## The ruling, restated as a specification

* **Reproduction arm** (`HAFISCAL_UI_STATE_ENCODING=legacy`, and `paper` under `calendar` when
  explicitly requested as the reproduction reference): keeps the defect. Seven micro states. This is
  what the published code does and it must stay reproducible.
* **`as-corrected` and `default`**: at most FOUR quarters of benefits to any household in a spell,
  counting quarters drawn before the recession, exactly as the paper's paragraph says. Bug fixes are
  mandatory in both worlds, so this is not a discretionary axis.
* **Consequence for the chain:** with the cap, the pre-onset cohorts need two extra quarters, not
  three, so the corrected chain carries TWO extension states — **six micro states, not seven**.

## Step 0 — make the state label honest: fix the onset-spike timing (blocking, and separable)

**The ambiguity, and why it dissolves rather than needing new machinery.** Under `calendar` a
household's micro state IS its position in the benefit spell (u1Q, u2Q, ext1..ext3, noBen), so
"quarters already drawn" reads straight off the state label and the cap needs nothing more. The label
is honest for everyone EXCEPT the spike cohort: the spike writes laid-off households into the FIRST
benefit state before any period is recorded, and the t=0 transition then advances them to the second,
so at the first recorded quarter they are labelled as having drawn one quarter when they have drawn
none. A cap applied to that label would cut them to three, breaking a row that is currently correct.

**The fix (owner-endorsed 2026-09-06): make the label honest, do not add a discriminator.** Apply the
spike so the affected households are in their FIRST benefit state at the FIRST RECORDED period rather
than being advanced out of it beforehand:

* MC (`AggFiscalModel.hit_with_recession_shock`): exempt spiked households from the t=0 transition,
  exactly as newborns already are.
* TM (`tm_methods`, the experiment-start half-step): the sequence is
  `ergodic -> consume (base policy) -> save -> SPIKE -> transition -> income`; move the spike to
  AFTER the transition so the spiked mass is not advanced before its first recorded income.

Both are orderings, not new state. Keep the two engines' timing aligned — that alignment is already
load-bearing and tested (the 2026-04-10 finding: spiking before the consumption half-step made
newly-unemployed households save under the wrong policy and overstated their saving by ~85 %).

**What it buys in one stroke.** The spike cohort becomes what it economically is — someone who
becomes unemployed at the start of the recession, indistinguishable from an ordinary t=0 entrant —
so its label correctly says zero quarters drawn and it receives the paper's four. The genuinely
pre-onset households keep labels that do reflect what they drew, so the cap applies to them
correctly. No flag, no extra state dimension, nothing the TM cannot represent.

**SCOPE WARNING — this is not confined to the extension, and must be measured separately.** Today the
spike cohort draws ONE recorded quarter of ordinary benefits where a chain entrant draws two, in the
plain `recession`, `recessionCheck` and `recessionTaxCut` scenarios as well. Fixing the timing gives
them the second quarter EVERYWHERE, so it moves the baseline recession scenarios, not only the UI
one. It is therefore a bigger change than the cap, and the two effects must not be confounded:

  **Measure the timing fix ON ITS OWN, adopt it, and only then layer the cap on top.**
  Order: (i) timing fix alone vs today, all four recession scenarios, TM outlays then Step 5a;
  (ii) cap on top of the timing fix, UI only. Two separable deltas, each attributable.

**Provenance.** The published ordering is presumably deliberate — someone chose to move people first
and transition after — and nothing in the paper describes it either way. So this is a THIRD
undocumented mechanism and belongs in the same documentation note (Step 5). Whether it is itself a
BUG or a convention is an owner ruling; the plan treats it as a fix because the ruling that benefits
be capped at four is unimplementable while the label lies.

**This also closes the standing onset-spike to-do** (`plans_local/TODO.md`), which proposed exactly
this toggle as its measurement and has been parked since 2026-08-28. It is now on the critical path.

**Deliverable:** the timing fix behind a flag (default OFF until measured), its own gate rows in
`test_ui_extension_schedule.py`, the measured deltas of (i), and an owner ruling recorded in
BUG-122 before Step 1 begins.

### Step 0 as executed (2026-09-06) — two corrections the measurement forced

**(a) Holding them is only half the fix; the spike must also be RESIZED.** The published ordering
is not arbitrary. Because the spiked transition immediately, a share `T[1,0] = 25 %` of them find
work again in the same quarter, so the spike over-lays-off to land on the target unemployment rate
— and lands on it exactly. Holding them without resizing puts the first recession quarter 12.5 %
above the doubled-unemployment target in every education group. The resizing is closed-form,
`f_exempt = f (T[0,0] − T[1,0]) / T[0,0]`, and with it the two orderings give the same unemployment
path to machine precision. Rule SST: `Code/HA-Models/onset_spike_rule.py`, which both engines go
through so their timing cannot drift apart.

**(b) The fix corrects the PLAIN RECESSION, not the extension.** The onset cohort's UI-extension
total is four quarters either way — the pre-period the spike writes into is never simulated, so the
relabelling costs no benefits. What was wrong is that this cohort drew ONE recorded quarter of
ordinary benefits where every other unemployed household draws two. The measured 19 % fall in the
UI extension's incremental outlay is the counterfactual becoming correctly more generous, not the
extension paying less. **So Step 0 does not by itself take anyone from five quarters to four** —
the cap of Steps 1–5 remains this bug's fix; Step 0 is its precondition.

Measured (HS_Only, TM, all four scenarios; dell, reproduced on xubuntark to 4e-16): unemployment
path identical to 1e-16; plain-recession income +0.46 % at q = 1 and identical everywhere else;
UI outlay 601.34 → 485.90; UI multiplier (AD) 1.437 → 1.443; check 1.501 → 1.500; tax cut
1.222 → 1.222 with its outlay identical to 3e-14. MC (ccarroll): same signs, UI outlay −12.9 %.
Refactor neutrality: flag OFF reproduces the pre-refactor code at 0.000e+00.

Also landed with it: the AD-equilibrium store now KEYS on the flag (unkeyed, a welfare battery run
under the fix would have consumed the equilibrium of a run without it), the 28 existing entries
were re-keyed to the flag's OFF value, and the env-flag registry guard now runs in `make test-fast`.

## Step 1 — the corrected rule (SST)

`Code/HA-Models/ui_extension_rule.py` is the single source of truth and gains a third canonical
policy, alongside `paper` and `historical`:

  `paper_capped` — the paper's own window, with total benefits per spell capped at
  `UBspell_normal + ExtraUBperiods_capped` where the cap is the paper's four quarters counted
  INCLUSIVE of quarters drawn before the onset.

Implementation notes:
* `n_extension` becomes 2 (hence six micro states); `t_enact`, `t_end`, `entry` unchanged from
  `paper` — the fix is the cap, not the window or the eligibility rule.
* `paid()` must consult how much of the spell precedes the extension, which the extension-state
  index already encodes under `calendar`: an entrant at extension state j has drawn
  `UBspell_normal + (j - 1)`. The cap is then a comparison, not new machinery.
* Keep `paper` exactly as it is. Do NOT re-point the name: the reproduction arm and every record
  since 2026-08-26 refer to it.

## Step 2 — world wiring

`config/catalog.py` row `ui_extension_policy`: reclassify from DISCRETIONARY to **BUG_FIX**, with
`canonical = paper_capped` (default world), `as_corrected = paper_capped` (mandatory in both, as bug
fixes are), and `paper = paper` (the reproduction value). Record the reclassification and its reason
in the row's `evidence`, and note that it SUPERSEDES the 2026-08-28 "window everywhere" ruling in
the narrow respect that the ruling assumed `paper` == the paper's paragraph.

## Step 3 — gates, before any number is quoted

Extend `Code/HA-Models/test_ui_extension_schedule.py`, whose traced-schedule harness already does
exactly this job:

| # | assertion |
|---|---|
| G1 | Under `paper_capped`, EVERY case totals ≤ 4 benefit quarters counting pre-onset ones. |
| G2 | The paper's own rows are UNCHANGED from `paper`: onset cohort 4, t=1 entrant 3, t≥2 entrant 2, unchanged whether or not the recession ends early. Only the two pre-onset rows move (5 → 4). |
| G3 | `paper` still reproduces `legacy` row for row — the reproduction arm is untouched. |
| G4 | The corrected chain has SIX micro states; `paper` still has seven. |
| G5 | `historical` is unchanged (it is a different policy, not this fix). |
| G6 | Both deprecated spellings (`window`, `history`) still resolve (the 2026-09-06 rename). |
| G7 | With the Step-0 timing fix, the spike cohort's traced row is IDENTICAL to an ordinary t=0 entrant's, in every scenario -- the label is honest. |
| G8 | Without the cap but WITH the timing fix, the spike cohort still gets the paper's four (the timing fix alone must not change that row). |

## Step 4 — measure the materiality, then re-run what moves

Nothing is quoted until measured. Order, cheapest first:

0. **The timing fix alone** (Step 0), all four recession scenarios: TM outlays, then Step 5a. This
   delta is NOT about the extension and must be reported separately -- it moves the plain recession,
   check and tax-cut arms too, because the spike cohort gains its second ordinary benefit quarter.
1. **Outlay only** (minutes): the UI extension's cost under `paper` vs `paper_capped`, ON TOP OF the
   timing fix, at Baseline, TM. This alone tells us the multiplier's denominator change.
2. **Step 5a multipliers** (~45 min): the UI column moves; check and tax cut must not.
3. **Step 5b welfare, S = 3** (~30 min): the UI welfare cells.
4. If and only if the estimation is affected: it is NOT — the base chain's extension states are
   lumpable no-benefit states, so a Step-2 estimate is invariant to the policy (catalog `coupling`).
   Verify that claim holds for `paper_capped` rather than assuming it.

**Expected direction:** capping REMOVES an over-payment, so the extension's cost falls and both the
UI multiplier and the UI welfare-per-dollar rise. Magnitude unknown; the affected cohorts are small
(households already unemployed at the onset), so a small effect would not be surprising, and a small
effect is still a fix.

## Step 5 — records and the co-author story

* Bug record updated with the measured materiality and the Step-0 ruling.
* The revision memo's and the co-author briefing's ledgers gain BUG-122 as an ORIGINAL-CODE
  correction — the first new one since the briefing was sent. Owner decides whether it warrants
  telling co-authors before the next natural contact; it is a defect in the published code, so the
  presumption is different from BUG-082's "let sleeping dogs lie".
* The documentation note this whole thread wants (the onset spike, the unanticipated recession, the
  per-regime stationary chains, entry-instant/exit-gradual, and the treatment of the already
  unemployed) — NONE of which is in the paper — with the traced schedule as its centrepiece.

## Cost

Steps 0–3: half a day, dominated by Step 0. Step 4: ~1.5 h of compute, no re-estimation and no new
solves (the policy store serves the same household problem). Step 5: an hour.
