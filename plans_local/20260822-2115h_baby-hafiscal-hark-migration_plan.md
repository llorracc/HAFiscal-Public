# BabyHAFiscal: the HARK-sufficiency migration plan

**STATUS: DEFERRED (owner ruling 2026-08-23 ~11:00) — a to-do for when HAFiscal
itself is truly finished.** Do not scaffold, do not answer the §6 questions, do not
re-propose; the plan stays as the ready-to-execute design for that day. PRs that
serve HAFiscal directly (#1818, the eventual TM split) proceed on their own merits
under the per-PR rule; the baby consumes them whenever it wakes.

**Charge (owner, 2026-08-22 ~21:05):** plan the migration of HAFiscal's generic tools
into HARK, organized so that HARK contains every element needed to run a "baby"
version of the HAFiscal paper — simplified (no 3 education groups; no HANK-SAM;
further simplifications welcome), carrying the **best-of** tricks only (none of the
dead-ends, no infinite option surface), and prototyped by letting the HARK version
**draw upon the HAFiscal version until the two have converged**.

**Relation to existing docs:** this plan is the FORCING FUNCTION for the endgame in
`Code/HA-Models/docs/HARK_MIGRATION_LEDGER.md` §0 — the ledger inventories what CAN
move; the baby defines what MUST move and certifies sufficiency. The endgame is
demonstrably real when the baby runs on pip-installed HARK alone.

---

## 1. The baby-model spec (proposed; owner trims/extends)

**Keeps (the paper's essence):**
- One-asset HA consumption model, splurge factor, ESC interpretation
  (splurge-out-of-stage — the settled D-06 ruling).
- β-heterogeneity via the Step-1 estimate consumed directly: the 7-atom
  uniform-spread (β, ∇) plus ς from `Result_AllTarget_ESC.txt` — **Step 2 is skipped
  entirely** (no education groups; one population calibrated by Step-1's output).
- Two macro states (normal/recession) with the recession-expected-length Markov
  structure; employed/unemployed micro states with UI benefits, in the MINIMAL
  encoding that supports the three policies (small enough to enumerate by hand in
  the notebook text).
- All three fiscal policies — stimulus check, UI extension, tax cut — in recession,
  with and without the AD effect (the consumption-demand feedback loop).
- Outputs: the multiplier table and the welfare-6 "bang for the buck" table (the
  paper's two headline exhibits), 2–3 figures (IRFs of C by policy).

**Drops:** education heterogeneity (S2), robustness arms (S3), HANK-SAM (S4),
Splurge=0 counterfactual, sticky-expectations machinery, agent-count scaling,
caches/provenance/parallel harnesses, the QE freeze apparatus, and the entire
`HAFISCAL_*` configuration surface.

**Optional appendix tier (not core):** a mini Step-1 estimation notebook — the
two-stage continuation (cold ς=0 multistart → joint descent) with the structural
GIC-cap parametrization — as the `HARK.estimation` showcase. Core baby CONSUMES
numbers; the appendix shows how they were produced.

**Form factor:** a REMARK-style repo (working name `HAFiscal-baby`) of 2–4
notebooks + a thin `baby/` package, whose imports at convergence are 100%
`from HARK ...`. Candidate graduation: one notebook becomes a HARK `examples/`
page (the merged #1785 docs page is the natural neighbor).

## 2. Sufficiency inventory: element → where it stands → what must move

| # | element the baby needs | HARK today | gap / vehicle |
|---|---|---|---|
| E1 | Markov consumer w/ aggregate-state-dependent income | **HAVE** (MarkovConsumerType; #1797/#1798 structural AggIndMrkv rewrite MERGED) | — |
| E2 | state-dependent income construction (unemployment, UI benefits, extensions) | HAVE the primitives (#1789/#1792 merged) | example-level construction code (baby-side) |
| E3 | normalization under Markov/vector growth | **HAVE** (#1784 merged) | consume it (also the N1 demolition test) |
| E4 | solve: EGM + cubic-Hermite representation | **HAVE** (native) | — (baby uses plain EGM; **no FTI/ATI** — private-repo dep is inadmissible in the baby) |
| E5 | far-tail closure: measured-Q power-law attach | **PR #1818 OPEN** | + the measure-Q helper (mods-memo headline) → #1818 amendment |
| E6 | grid sizing: patience-based aXtraMax (K·h̄ rule), simple form | vendored (`grid_sizing.py`) | small PR (ledger fast-track #6), or inline 30 lines in the baby if HARK declines |
| E7 | **transition-matrix machinery for Markov/agg types**: dist-grid, jump-to-grid, TM assembly, ergodic solve, NPV accounting | HARK has IndShock-only TM methods; the Markov/agg generalization is vendored (`tm_methods.py`, 7.6k lines) | **THE critical-path PR: J6 `HARK.transition_matrix`** — scoped BY the baby (see §4) |
| E8 | AD feedback loop (Cratio → income scaling → re-solve fixed point) | Market pattern exists | example-level (~50 lines in the baby) |
| E9 | policy experiments + multiplier accounting | — | example-level + tiny NPV utilities riding E7 |
| E10 | welfare-6 measure | — | example-level (one formula, one code cell) |
| E11 | (appendix tier) estimation scaffolding: multistart, structural-cap parametrization, continuation | vendored | **J25** `HARK.estimation` utilities PR |
| E12 | splurge wrapper (ESC) | — | example-level (~20 lines) — deliberately NOT a library feature |

**Sharp consequence:** the library-side critical path is just **E5 (#1818, in
flight) + E7 (the J6 TM split)**, with E6/E11 as small side PRs. Everything else is
authorship inside the baby. The scary-looking 86k-LOC FromPandemicCode does NOT
migrate — the baby re-expresses its essence in a few hundred lines against HARK.

## 3. The anti-dead-end discipline (the "tricky part," codified)

1. **No option surface.** The baby has zero env flags. Every contested axis gets ONE
   choice, made in code, with a one-line provenance comment citing the HAFiscal
   evidence doc (e.g. `# power-law tail attach, measured Q — chosen over farfield/
   chart alternatives: HAFiscal conclusions 2026-08-22`). The dead-ends appear only
   in a short "roads not taken" note, as prose.
2. **The best-of registry (the settled choices the baby embraces):** ESC
   interpretation; EGM solve; measured-Q power-law attach (NO knots — an
   exploration-speed trick, not model substance; NO farfield; NO chart); patience-
   based grid rule; TM-ergodic steady state; **deterministic TM for policy dynamics
   as primary** (seedless — pedagogically clean; MC as the single cross-check cell;
   validate this choice in prototyping, cf. the joint-5D/bucketing lesson at full
   scale); 7-atom β spread; #1784 normalization. Nothing else ships.
3. **One engine per task.** No dual paths, no fallbacks, no engine switches.
4. **Numbers get fresh dials:** the baby's goldens are its OWN converged results
   under the scaffolded phase — the baby is simplified, so it never claims the
   paper's numbers; it claims its own, reproducibly.

## 4. The convergence protocol ("draw upon until converged")

Generalizes the proven `TAIL_IMPL=pr` co-debug pattern to whole-model scale:

- **Phase A — scaffolded.** `HAFiscal-baby` imports HARK for everything HARK has,
  and imports the gaps from HAFiscal-Latest through ONE module: `baby/bridge.py`
  (path-resolved like `_hark_fti_path.py`). Every borrow is registered in the
  bridge's MANIFEST: `{symbol, borrowed-from, target PR, status}`. **The manifest IS
  the remaining-migration list** — self-documenting, shrink-to-zero.
- **Phase B — parity flips.** As each gap lands upstream, the bridge flips that
  symbol to the HARK import behind a parity gate: baby end-to-end results identical
  (1e-12 where exact; documented tolerance where representation changes). One flip
  per commit; the flip commit deletes nothing yet.
- **Phase C — converged.** Manifest empty → delete `bridge.py` → CI runs the baby
  end-to-end against pip HARK (`pip install econ-ark`) with the golden gate.
  Convergence criterion is mechanical: `grep -ri hafiscal baby/` matches only prose.
- **The umbilical (owner refinement, 2026-08-22 ~22:05): bridge updates are never
  silent.** The manifest pins each borrowed symbol's SOURCE CONTENT HASH as of its
  last baby-side review. A guard test (`test_bridge_sync.py`, same pattern as
  HAFiscal's registry guards) recomputes the hashes every run: any change to a
  borrowed symbol — a HAFiscal-side fix flowing into the bridge, a flip, a new
  borrow — FAILS the baby's own test suite until an entry is appended to
  `BRIDGE_LOG.md` dispositioning it as exactly one of:
  **INCORPORATED** (baby updated; goldens re-run and re-frozen if moved) or
  **SPURIOUS** (the change doesn't bear on the baby; one-line reason recorded).
  No third state, no silent pass-through — the baby literally cannot go green while
  an undispositioned bridge-side change exists.
  The umbilical is TWO-WAY: complaints discovered while building the baby (API
  awkwardness, numerical surprises, doc gaps) are registered in the same log and
  dispositioned on the parent side — fixed-in-HAFiscal / fixed-in-PR / spurious —
  so the baby also functions as HAFiscal's and the PRs' most honest reviewer.
- **Scope-cutting dividend:** E7 (the J6 TM split) is developed AGAINST the baby's
  bridge manifest — the baby defines the minimal public API `HARK.transition_matrix`
  must export, instead of wholesale-porting 7.6k lines. What the baby never borrows,
  the PR never carries.

## 5. Sequencing (each PR gated on owner release, per standing rule)

| step | what | depends on | effort class |
|---|---|---|---|
| 0 | owner trims/approves the baby spec (§1) + this plan | — | ruling |
| 1 | scaffold `HAFiscal-baby` (repo, bridge, notebook skeletons); baby runs end-to-end in Phase A borrowing E5/E6/E7 pieces | nothing upstream — **can start immediately** | 2–4 sessions |
| 2 | freeze baby goldens (multipliers, welfare cells, ergodic moments) | 1 | small |
| 3 | #1818 lands + measure-Q amendment → first parity flip (E5) | Alan/CI | small |
| 4 | J6 `HARK.transition_matrix` PR, scoped by the bridge manifest (E7) → flip | 1, owner release | the big one (2–5 sessions) |
| 5 | E6 grid-rule PR (or inline) → flip; E11 J25 estimation PR (appendix tier) → flip | 4 | small / medium |
| 6 | Phase C: delete bridge, pip-HARK CI, REMARK polish; propose one notebook to HARK examples | 3–5 | small |
| 7 | demolition dividend: every flipped family's HAFiscal-Latest vendored copy becomes deletable per the ledger's state machine (CONSUMED → DELETED) | rolling | rolling |

**Interaction with the paused consumption plan:** the baby does not replace it — the
consumption plan swaps HAFiscal-Latest itself onto upstreamed pieces (N1…); the baby
proves library sufficiency for OUTSIDERS. They share PRs (E5/E6/E7) and can proceed
in either order; the baby is the better forcing function for API design because it
has no legacy call sites.

## 6. Open questions for the owner (none block step 1)

1. Baby spec trims/adds (§1) — in particular: TM-primary for policy dynamics OK?
2. Name: `HAFiscal-baby` (working) vs alternatives; REMARK vs HARK-examples-first.
3. Appendix estimation tier: in or out of the initial scaffold?
4. Where the baby repo lives (llorracc/ private until presentable, then econ-ark?).
