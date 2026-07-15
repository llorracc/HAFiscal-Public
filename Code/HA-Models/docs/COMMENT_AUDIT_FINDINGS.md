# COMMENT_AUDIT_FINDINGS — Mandate-1 findings & owner-triage log

Findings doc for the documentation-rationalization effort
(`plans/20260611_doc-rationalization-overview.md`). Per the shared execution
contract, any discovered *behavior question* (e.g. a comment contradicting a
decided default) is logged here for owner triage — never silently fixed.
Audit/classification tables from the doc-sweep phases also land here.

## How to use this file

Treat this file as a triage ledger, not a blanket permission slip to edit code.
Rows under **OWNER-TRIAGE** and **CONTRADICTED** identify places where comments,
help text, or behavior disagree with current owner docs. If the row says owner
ruling or code change is required, preserve that as an open prerequisite unless
the requested task explicitly includes the ruling or the code evidence is
locally decisive and low-risk.

For documentation-sufficiency work, the highest-value rows are the ones that
can mislead a new agent into proposing superseded methodology or stale entry
points: `qe_fidelity` profile semantics, `AggFiscalMAIN.py` references,
hybrid/TM welfare claims, shuffle-default polarity, and broken test/run
instructions. Do not silently "fix" behavior-implicated rows while doing a
comment-only cleanup.

---

## Phase B audit — root live working documents (2026-06-11)

Per the Phase B owner ruling (`plans/20260611_docs-dedup-and-navigation.md`):
`agenda_2026_06_03.md` and `TODO_HARK_0171_UPDATE.md` are **live working
documents** — audited item-by-item below, files left untouched. An updated
draft agenda was produced at `agenda_2026_06_11_DRAFT.md` for owner review.

### `agenda_2026_06_03.md` (speedup-track forward agenda)

**Headline:** none of the five Tier-1 items was started — the track pivoted
after 2026-06-03 to BUG-047/051/052/053, the welfare-method unification
(2026-06-10), and the dolo-plus + doc-rationalization mandates (evidence:
`conclusions_private/2026-06-*` series; `history/20260609-*` session docs; no
matching commits since 2026-06-03 in `git log`).

#### Context & constraints framing

| item | status | evidence |
|---|---|---|
| Framing: "UI deprecated from headlines; UI multiplier and welfare both unreliable" | **superseded** | `conclusions_private/2026-06-10_welfare_method_unified_MC.md` — ui_rec/ui_rec_AD ARE reportable via MC+CRN+stratified-shuffle; only ui_norec stays excluded |
| Framing: "MC + CRN unified welfare (2026-05-10)" is the methodology | **superseded** (extended) | same doc — 2026-06-10 unified-MC decision is now canonical; defaults wired into `FromPandemicCode/EstimParameters.py` canonical block (`HAFISCAL_QE_FIDELITY` escape hatch) |
| Constraint: NEVER report ui_norec | **open** (standing, still binding) | same doc (ui_norec exclusion reaffirmed; 0/0 by construction) |
| All other constraints (no T_sim mods; no new code in FromPandemicCode/; ≤0.5% drift; cascade-gate; PYTHONUNBUFFERED; no default re-estimation; MC↔TM-a companion) | **open** (standing, still binding) | `CLAUDE.md` canonical-approach block; note the 2026-06-09 BUG-053 re-estimation was explicit-owner-requested, consistent with the rule (`history/20260609-1650h_bug053-reestimation-gicfactor-0p9995.md`) |

#### Tier 1

| item | status | evidence |
|---|---|---|
| T1.1 welfare6 pickle-diff CLI | **open** (not started) | `Code/HA-Models/welfare6_diff.py` absent; no matching commits since 2026-06-03 |
| T1.2 `make smoke` Reduced_Run gate | **open** (not started) | `Code/HA-Models/smoke_welfare6.py`, `Code/HA-Models/golden/`, and a Makefile `smoke` target all absent |
| T1.3 JAX persistent compilation cache | **open** (not started) | `git grep JAX_COMPILATION_CACHE` hits only this agenda + the (now-archived) speedup session-starter |
| T1.4 diagnose "GPU slot at 0% util" routing | **open** (not started) | `run_welfare6_parallel.py` has no commits since 2026-06-03; no routing conclusions doc (`conclusions_private/2026-06-05_jax_gpu_solver_spike.md` is the solver kernel — different topic) |
| T1.5 auto-registry on bench completion | **open** (not started) | no `finalize_registry` in tracked code; `Code/HA-Models/experiments/append.py` unchanged |

#### Tier 2

| item | status | evidence |
|---|---|---|
| T2.1 RAM upgrade (+64 GB) | **open** (awaiting capex decision) | host still 54 GiB total (`free -h`, 2026-06-11) |
| T2.2 seed-parallel unified job board | **open** (prereq RSS measurements still missing) | no YAML job-board artifact in repo |
| T2.3 shell wrapper polish | **open** | no `--mode cold\|warm\|reuse-cache` alias in `run_welfare6_parallel.py` |
| T2.4 2A vmap-cohorts GPU revisit | **open** (still gated on T1.4) | T1.4 row above |

#### Tier 3 (deferred items, 17)

| item | status | evidence |
|---|---|---|
| AD-first / LPT scheduling | **done** (was already shipped at agenda time) | commit `afa7d7e9` (the agenda row itself says so) |
| Joint-distribution UI welfare TM-a | **superseded** | `conclusions_private/2026-06-10_welfare_method_unified_MC.md` — UI welfare reinstated via MC+CRN+stratified-shuffle; TM 5-D exact ui_rec exists as validation, joint-TM route moot |
| Defensive `JAX_2B_THREADS`/`duration_workers` cap | **open — deferral trigger FIRED** | `conclusions_private/2026-06-03_duration_workers_resource_constraint.md` — 2 OOM kills verified 2026-06-03; root cause = ~16 GB duration-worker forks; workaround `--duration-workers 1`; auto-budgeter still defaults dw=2 (no hard fix) |
| Remaining 14 rows (cross-param cache reuse; cache base eco-state; MoM warm-start; JAX-native AD loop; vm.swappiness/cgroup; GPU upgrade; cache LRU pruning; pre-build eco_ref; ref-sim init_panels disk cache; GPU async/multi-stream; empirical slot tuning; share eco_ref.solve; …) | **open** (deferred-by-design; triggers not fired) | agenda's own trigger column; no contrary evidence found in `conclusions_private/2026-06-*` |

#### Open questions for user judgment

| item | status | evidence |
|---|---|---|
| Q1 RAM capex approval | **open** | host unchanged at 54 GiB |
| Q2 GPU-slot-at-0%-util: bug or AD-HIT quirk? | **open** | T1.4 never executed |
| Q3 make `HAFISCAL_USE_SOLUTION_CACHE=1` default-on? | **open** | `EstimParameters.py` canonical block sets shuffle/aMax defaults only — no solution-cache default |
| Q4 "are we done optimizing single-cell wall?" | **open** (de facto: track parked since 06-03; destination moved to Plan H QE-matching) | no speedup commits since 2026-06-03; `plans/20260610_post_merge_canonicalize_default_solution.md` priority ladder |
| Q5 smoke-golden refresh ownership | **open** (moot until T1.2 exists) | T1.2 row above |

**Summary `agenda_2026_06_03.md`: 33 rows audited — 1 done, 3 superseded
(1 item + 2 context framings), 29 open.** The validation cascade / success
metric / failure-handling sections are standing procedure, not items (not
classified).

### `TODO_HARK_0171_UPDATE.md`

**Headline:** the wait-trigger **fired** — HARK `0.17.1` was released
2026-02-02 (tag in the HARK repo). But the prescribed action path is
superseded: the repo no longer pins `v0.17.0.post1-broadcasting-fix`, and the
current branch needs post-0.17.1 HARK features (normalization + dual_measure,
interpolation_jax), so plain `econ-ark>=0.17.1` is no longer sufficient.

| item | status | evidence |
|---|---|---|
| Premise: "WAITING FOR HARK 0.17.1 RELEASE" (weekly check) | **done** (released) | HARK repo tag `0.17.1`, tagged 2026-02-02 (`git -C ../../econ-ark/HARK log -1 0.17.1`) |
| Step 1: pyproject → `econ-ark>=0.17.1` from PyPI | **superseded** | `pyproject.toml` no longer carries the broadcasting-fix pin; deps line 34 is bare `econ-ark` with a `[tool.uv.sources]` override to the local editable dev HARK (line 162); the v0.17.0-reproduction release work pinned public SHA `d15660d5` because the branch needs features absent from the 0.17.x tags |
| Step 2: test on `master-with-borocnstnat-fix-using-0p17p0` | **superseded** | canonical integration target is now `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` (`plans/20260610_integration-target-TM-vs-MC.md`); the old branch survives on origin but is not the line |
| Step 3: merge to master | **open** | the 0.17-upgrade line is still unmerged to master; the merge path runs through the TM-vs-MC integration branch (same plan) |
| Step 4: delete this file + `INTERIM_REPRODUCTION_INSTRUCTIONS.md`, update refs | **open** (gated on Step 3) | both files still at root; kept per Phase B owner ruling (live doc / external-facing); INTERIM got a one-line currency pointer 2026-06-11 |
| Release-check procedure (pip index / GitHub API) | **done** (obsolete — release confirmed) | same tag evidence |

**Summary `TODO_HARK_0171_UPDATE.md`: 6 rows audited — 2 done, 2 superseded,
2 open.** Recommended owner action (carried into the draft agenda): rewrite or
retire the file at merge time — its end-state goal (public, reproducible HARK
dependency) survives, but the concrete path is now the pinned-public-SHA route
(`d15660d5` → bump to `ce0cb5d6`+ at next re-pin) rather than PyPI 0.17.1.

---

## Code-comment hygiene (`plans/20260611_code-comment-hygiene.md`) — consolidated Phase A findings (2026-06-11)

Consolidation of the four Phase-A inventory reports (grep battery per plan §Phase A;
session inputs `/tmp/m3_inventory_{core,livefpc,hamodels,orchestration}.md`):

| partition | scope | CONTRADICTED | STALE-FWD-REF | ORPHAN-REF | UNVERSIONED | HISTORICAL-OK |
|---|---|---|---|---|---|---|
| 1 core | 15 production files in `FromPandemicCode/` | 9 table rows | 6 | 5 | 2 | 26 rows (~190 hits) |
| 2 livefpc | remaining live `FromPandemicCode/*.py` | 9 | 6 (1 moot) | 3 | 9 | ~150 hits |
| 3 hamodels | `Code/HA-Models/` top + jax_mc_speedup/ + solution_cache/ + dolo_plus_validation/ | 8 | 6 | 4 | 3 | ~45 files clean |
| 4 orchestration | `reproduce/**`, root scripts, Makefile, Empirical, Target_AggMPCX | 13 | 2 | 10 | 6 | ~30+ sites |
| **total** | | **39** | **20** | **22** | **20** | bulk |

Accounting for the 39 CONTRADICTED rows: **19** hoisted into the owner-triage
section below (behavior-implicated, grouped into items a–s with three
new spec-verified finds c/l/m), **18** in the LOGGED table, **2** pre-approved
by standing rulings (`Simulate.py:249-258` ruling 1 — its BUG-050 fix/defer
status still needs a separate owner confirm; `Parameters.py:102-115` comment
part, ruling 3 — its VALUE question is item (b) below). Classes 2/4/5 are
non-blocking and go straight to Phase C; their disposition lands in the
FIXED-BY-PHASE-C table.

**Liveness caveat (from partition 2):** Mandate-1 archive batches landed in
this worktree DURING the inventory (`run_reduced_tm_a_indexed.py` and
`welfare6_tm_joint.py` left the live set mid-scan). Phase B/C must re-check
per-file liveness before applying any fix.

### RESOLUTIONS (owner rulings 2026-06-12) — ALL items below are CLOSED

> **⚠ SUPERSESSION BANNER (added 2026-06-13; owner-RESOLVED same day).** Two of the
> 2026-06-12 dispositions below were re-opened by the econ-mw merge and then ruled on by
> the owner 2026-06-13 (`plans/20260613-1830h_config-taxonomy-reconciliation-post-econ-mw-merge.md`):
> - **(d) "QE_FIDELITY implies legacy UI encoding — FULL QE world" (`bd907196`):**
>   **OVERRULED.** The owner ruled to REMOVE the `QE_FIDELITY⟹legacy-UI` coupling and to
>   **RETIRE `HAFISCAL_QE_FIDELITY`** entirely (redundant with `as-corrected` + the old
>   branch). UI encoding is the BUG-043 toggle handled by the world scheme. Execution
>   (full retirement) is scheduled; the duplicate setdefault was already removed 2026-06-13.
> - **"USE_JAX_2B dev-only" (`857f66a0`):** **SUPERSEDED** — owner confirmed 2B is
>   SANCTIONED for production; econ-mw's stale "dev-only" comment is a cleanup TODO.
>
> Otherwise the dispositions below stand. The historical triage tables further down
> are the original audit record (some "fix pending" cells were since fixed — e.g.
> (i) cache-key was landed as `9233a017`/BUG-059, (c)/(d) etc.); do not read them as
> current status.

Every finding (a)–(s) and every LOGGED row was ruled on by the owner on
2026-06-12 and executed the same day. Dispositions and commits:

| finding(s) | disposition | commit |
|---|---|---|
| (c) AD_MAX_ITER re-parenting | code FIX: AgentCountTotal block re-parented; verified both sides | `45f0ab05` |
| (i) cache-key gap | code FIX: GIC_SHAVE_ON_GPF added to `_HAFISCAL_NUMERICAL_ENV_VARS` | `9233a017` |
| (m) NM_IN_PLACE log default, (j) `make test`, (s) stale runtime strings, row 20 echo path | code-string/recipe fixes | `7e5efdd0` |
| (d) qe_fidelity profile + UI_STATE_ENCODING gap | profile exports QE_FIDELITY=1; QE_FIDELITY now implies legacy UI encoding — FULL QE world | `bd907196` |
| (a)+(h) hybrid welfare path | RETIRED: legacy banners, ui_norec cell never emitted to .tex, runner docstrings corrected | `858fe9ed` |
| 7 flag deprecations (SPLURGE_OLD, IS_FORCE_LOW_ANRM, VERSION, AGENTCOUNT_TOTAL, RUN_ONLY_SHOCK, STEP5_SCOPE, TM_INIT_MEASURE 'Q') | registry + dead-code removal; guard test PASS | `b38621fc` |
| (b) GICx fallback 4.0→4.5, (e) production_current relabel, (f) BUG-054 filed, (g) BUG-044/045 assigned, (k) do_all_reduced env wiring, (l) Clean_Folders retirement, (o) upgrade-validation banner, TM_MCOUNT ruled intentional, USE_JAX_2B dev-only | judgment batch | `857f66a0` |
| 18 LOGGED rows + (p)(q)(r) | comment rewrites applied (5 rows verified already fixed in the original Phase C) | `50e02251` |
| (n) SECURITY email credential | handled out-of-band pre-ruling: file stripped + purge plan at `1f677e08`; revocation = owner action | `1f677e08` |

The tables below are retained UNCHANGED as the audit record; read them together
with the resolutions above.

### OWNER-TRIAGE: behavior-implicated findings (HISTORICAL — closed 2026-06-12, see RESOLUTIONS above)

One row per finding. None of these was fixable under the comment-only AST gate
without an owner ruling (most needed a small CODE change or a behavior decision).

| # | finding | where | why it matters | suggested vehicle |
|---|---|---|---|---|
| a | Production hybrid-welfare path computes `w6_ui_norec` and writes it into the paper `welfare6.tex` (Rec=0 row, TM value substituted for the MC 0/0); module headers declare the 2026-05-10 hybrid (TM for Check/TaxCut, MC for UI) — the INVERSE of the decided method | `FromPandemicCode/run_hybrid_welfare6.py:3,446,475-477,500`; `FromPandemicCode/welfare6_hybrid_table.py:1-2,47-63` | Violates the standing **NEVER-report-ui_norec** rule (0/0 by construction, "NO EXCEPTIONS" — TM substitution included); emits a paper artifact under the superseded method (2026-06-10: MC+CRN+stratified-shuffle canonical for ALL cells) | Owner ruling: retire or re-head the hybrid path as legacy; drop the ui_norec cell from the `.tex` emit (code edit, outside the comment gate). Decide jointly with (h) |
| b | GICx FALLBACK value `GICx=4.0` now clips the central College β under BUG-053 defaults | `FromPandemicCode/Parameters.py:102-115` (GICxDefaults + derivation comment) | Derivation assumed the pre-BUG-053 linear β-shave. Under the default GPF-shave (cap=GICmax·factor^CRRA, CRRA=2): GICx=4.0 ⇒ factor≈0.982 ⇒ cap≈0.9705 < 0.98 ⇒ central College β clipped — violating the comment's own stated invariant. Fires whenever the DiscFacEstim file load fails (silent mis-calibration on the fallback path) | Comment rewrite pre-approved (ruling 3); the **VALUE** needs re-derivation (invariant needs factor²>0.9737 ⇒ GICx>4.31; e.g. 4.5) — code fix, owner decision |
| c | `HAFISCAL_AD_MAX_ITER` re-parenting bug: commit `e1fa6368` (2026-05-04) inserted the `if _ad_iter_env:` block at the wrong indentation, capturing the pre-existing AgentCountTotal if/elif/else (formerly under `if Parametrization in ('Reduced_Run','Smoke_Test','HS_Only')`) | `FromPandemicCode/Parameters.py:731-752` (AgentCountTotal branches at :738-752 under `if _ad_iter_env:` at :732); verified vs `git show e1fa6368^` | Two-sided silent N corruption: (i) env unset (the normal case) ⇒ Smoke_Test/HS_Only/Reduced_Run keep AgentCountTotal=10000 (:314) instead of 100/1500/5000; (ii) env set on **Baseline** ⇒ the `else:` clobbers AgentCountTotal→5000 (half population) | Code fix: re-parent the block under the parametrization guard. BUG-report candidate (Type-A error per error-fix governance: default-fix + paper trail). Audit which historical runs set the env var |
| d | `reproduce.sh --profile qe_fidelity` does NOT set `HAFISCAL_QE_FIDELITY=1` (0 hits of the var in the script) | `reproduce.sh:1030-1032, 2534-2545` | Since the Plan-A canonical defaults (2026-06-10, EstimParameters setdefault block), a "QE fidelity" run silently inherits shuffle-ON + stratified + aMax=1300 — the canonical world, not the QE world the profile claims to reproduce. The escape hatch exists for exactly this profile | Owner: add `export HAFISCAL_QE_FIDELITY=1` to the profile (1-line code edit) or reword the profile's claim |
| e | `production_current` profile pins legacy behavior while claiming "snapshot of current default behavior" | `reproduce.sh:2576-2587` | Forces `HAFISCAL_GICX_MODE` legacy + `NM_START_FROM_SAVED=0`; actual code defaults are `'hardcoded'` (EstimAggFiscalMAIN.py:1281) and `'1'` (:1312) — the profile's output is NOT current-default behavior | Owner: relabel (e.g. "production_2026-05 legacy-GICx snapshot") or update the env lines to the true defaults |
| f | `Estimation_BetaNablaSplurge.py` calls `_wealth_under_cdc` UNCONDITIONALLY under `HAFISCAL_INTERPRETATION=ESC`; the promised `_wealth_under_esc` ((1−ς)·aLvl) never landed (plan closed without it) | `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py:343,350` (calls); `:243-246,270-274,341,466` (forward-promise comments) | ESC-mode Step-1 runs ESC dynamics with the CDC wealth-correction formula — interpretation mismatch inside one estimation (matched-triple discipline: {PermGroFac, calibration, interpretation}). Default CDC path unaffected | Owner ruling: intended approximation or a new BUG report; then rewrite the 4 forward-promise comments to match the ruling |
| g | BUG-044/045 three-way numbering collision | `BUGS_private/HARK+HAFiscal_TM_vs_MC_bug_index.md:80` ("BUG-044/045 do not exist") vs `FromPandemicCode/AggFiscalModel.py:914,986` (BUG-044 = HARK stratified-shuffle fix, PR #1776 — also project memory) vs `FromPandemicCode/welfare6_tm_joint5d.py:262,359` (+411,630) (BUG-044/045 = unrelated joint-5D kernel fixes #10/#11) | The registry disowns both numbers while two unrelated fix families use them — BUG refs are unresolvable for any future reader; provenance chain broken | Owner: assign the numbers (register dossiers / index rows) and renumber or de-number the losing uses; then mechanical comment fixes |
| h | Runner docstrings "standard MC (no shuffle, CRN-paired)" now FALSE at runtime | `FromPandemicCode/run_hybrid_welfare6.py:3`; `FromPandemicCode/run_all.py:14` | EstimParameters canonical block (2026-06-10) setdefaults `HAFISCAL_MC_SHUFFLE=1` + stratified; both runners import it and set no override ⇒ they now run shuffled while documenting no-shuffle | Owner ruling FIRST (behavior): should these runners inherit the canonical defaults or pin legacy no-shuffle? Then rewrite docstrings. Triage with (a) |
| i | Solution-cache key whitelist missing `HAFISCAL_GIC_SHAVE_ON_GPF` while its docstring claims "all HAFISCAL_* env flags that affect numerical output" are keyed | `Code/HA-Models/solution_cache/keys.py:13-15,35-36` (`_HAFISCAL_NUMERICAL_ENV_VARS`) | The flag changes clipped β atoms (BUG-053) ⇒ numerical output differs across flag flips but the cache key doesn't ⇒ stale-cache hazard. Same failure class as the PERMGROFAC_FIX omission fixed 2026-06-04. `docs/ENV_FLAGS.md` already records "known gap, fix pending" | Land the 1-line whitelist addition (code, outside the comment gate); soften the keys.py docstring to name the gap until then |
| j | `make test` runs a nonexistent test dir | `Makefile:42-43` (`test: pytest tests/`), help text `:15` | `tests/` does not exist ⇒ the target fails when invoked; CLAUDE.md prescribes `pytest Code/ reproduce/` | 1-line recipe fix (code edit) |
| k | `do_all_reduced.py` ignores `HAFISCAL_RUN_STEP_{1,2,4,5}` + wrong scale claim | `Code/HA-Models/do_all_reduced.py:44-49` (hardcodes `run_step_{1,2,4,5}=True`; only step 3 env-gated) and `:9-10` ("Reduced_Run (3 types × 7 β atoms)") | Claims "same flags as do_all.py" but a user's `HAFISCAL_RUN_STEP_5=false` is silently ignored (do_all.py honors it via `_env_run`) — usability footgun. And Reduced_Run is 3 types × **1** β atom, N=5000 (Parameters.py:344-348); "3×7=21" describes Baseline | Owner: wire `_env_run` like do_all.py (code) or document the divergence; the 3×7 row becomes a comment rewrite post-ruling |
| l | `Clean_Folders.py` parses the RETIRED `AggFiscalMAIN.py` as its single source of truth | `FromPandemicCode/Clean_Folders.py:68` (default `'./AggFiscalMAIN.py'`), `:236-249` (hard error if absent) | `AggFiscalMAIN.py` no longer exists on this branch (only `AggFiscalMAIN_reduced.py`) ⇒ the tool unconditionally errors out; its robustness-flag-source premise is dead | Owner: repoint the SST (AggFiscalMAIN_reduced.py / do_all flags) or archive the tool |
| m | `NM_IN_PLACE` behavior default ≠ trajectory-log default | `FromPandemicCode/EstimAggFiscalMAIN.py:1062` (dispatch default `'1'`) vs `:1162` (trajectory-metadata default `'0'`) | With the env var unset, the run actually executes in-place NM but the trajectory log records `in_place: False` — provenance artifacts misstate the regime that produced them | 1-char code fix (align the `:1162` default to `'1'`) — outside the comment gate |
| n | **SECURITY: git-tracked plaintext Gmail app password** | `reproduce/upgrade-validation/email_config.py` (tracked since `72d96cca`, 2026-02-04; file mode 664 despite its own "chmod 600" comment). Secret deliberately NOT reproduced here — file+commit reference only | A live credential is committed to repo history. Repo is currently private; owner has been notified for revocation | **OUT-OF-BAND, ahead of all comment work:** revoke the app password; replace with env-var loading + .gitignore; purge history before any publication. The comment fix is moot until then |
| o | Upgrade-validation harness is partly fictional | `reproduce/upgrade-validation/step_runner.py:11-16,52-69` (expects `EstimResults.txt` / `AggFiscalResults.txt` / `SimulationResults.txt` / `AllResults.txt` — NONE ever existed; step labels diverge from do_all's canonical steps); `interactive_validation.py:92-101` (would build Python 3.9 + PyPI `econ-ark==0.17.0` envs — branch needs 3.10/3.11 + the pinned git HARK) | Running it builds wrong environments and checks for files that never existed ⇒ guaranteed false failures; the migration it validated is complete | Archive-in-place banner for the whole `upgrade-validation/` directory, or correct the pins if it must stay runnable — owner disposition |
| p | JAX-AD support comment contradicts the adjacent code line | `FromPandemicCode/welfare6_scenario.py:697-702` vs `:703` | Comment claims only `recession` + `recessionUI` are wired; the next line declares `JAX_AD_SUPPORTED_SCENARIOS` = all 4 (Check/TaxCut included; validated 2026-05-19, CLAUDE.md) | Trivially provable from adjacent code — fast-track approval for a past-tense rewrite |
| q | Newborn-`'transition'` mode documented as "welfare CRN broken (bias INCREASES on UI cells)" | `FromPandemicCode/AggFiscalModel.py:986-992` | Pre-stratified-era claim. `'transition'` is the canonical production default (`HAFISCAL_SHUFFLE_NEWBORN_FIX=transition`, EstimParameters setdefault, 2026-06-10) with <0.31% bias post-stratified fix — the doc steers readers away from the production default | **RESOLVED 2026-06-13** (owner-approved): comment rewritten to flag `'transition'` as the canonical default and the "CRN broken" claim as STALE/plain-shuffle-era, with config-category pointer. `py_compile` OK |
| r | "Shuffle flags default off / opt-in" comments at two production sites | `FromPandemicCode/EstimAggFiscalMAIN.py:764-769`; `FromPandemicCode/Simulate.py:343-351` | Canonical block setdefaults `HAFISCAL_MC_SHUFFLE=1` + stratified + transition since Plan A (2026-06-10) — polarity inverted (opt-OUT via `HAFISCAL_QE_FIDELITY=1`). Note: the 2026-06-09 re-estimation ran under shuffle-ON, so the calibration/regime matched pair holds — the comments are what's wrong | **RESOLVED 2026-06-13** (owner-approved): both headers rewritten — polarity corrected (MC_SHUFFLE defaults ON; OFF only under QE_FIDELITY) and stratified shuffle reclassified as a BUG-FIX (reliable UI welfare), with config-worlds pointer. `py_compile` OK |
| s | Stale claims living in STRING LITERALS (AST-gate-blocked) | `FromPandemicCode/welfare6_scenario.py:824-828` (argparse help: "currently 1E-2"; Parameters.py default is 1E-3, 1E-2 only for reduced parametrizations); `welfare6_scenario.py:758-760` (print: "replay only supports 'recession' currently"); `FromPandemicCode/Output_Results.py:224` (`warnings.warn` cites Simulate.py:246; assignment now at :258); `FromPandemicCode/run_welfare6_parallel.py:553-555` (`--skip-ui` help over-claims the ui_norec rule as covering ui_rec/ui_rec_AD) | Strings are code under the AST gate — Phase C cannot fix them; users see the stale text at runtime in help/warnings | Explicit owner-approved code-string edit batch (trivial; `py_compile` + per-file diff review in lieu of the strict gate) — or remain logged |

### LOGGED (CONTRADICTED, log-only per owner default) — HISTORICAL: all rows closed 2026-06-12 (commit `50e02251`; 5 rows were already fixed in the original Phase C)

The remaining CONTRADICTED rows from the four inventories — no edits were made
during the audit; each awaited a (fast) owner ruling before any Phase-C
rewrite. Excluded here: the 2 rows pre-approved by rulings 1/3 (tracked via
FIXED-BY-PHASE-C) and the 19 behavior-implicated rows hoisted into the triage
table above.

| partition | file:line | stale claim | contradicting source | proposed post-ruling action |
|---|---|---|---|---|
| core | `EstimAggFiscalMAIN.py:1272` | GICX_MODE "cap pinned at module-load theGICfactor=**0.999** (DEFAULT post-Phase G)" | `theGICfactor = 0.9995` since 2026-06-09 (EstimParameters.py:418, BUG-053); `'hardcoded'` IS still the default mode | Replace the literal with "theGICfactor (see EstimParameters.py)" — candidate for extending ruling 3 (same GICx family) |
| core | `EstimAggFiscalMAIN.py:1276` | "For factor = theGICfactor (0.999), GICx ≈ 6.9068" | Runtime computes logit(0.9995) ≈ 7.6009 from the imported value; var name `_GICx_for_factor_0999` is CODE (rename out of scope) | Same ruling-3 extension; var rename deferred |
| core | `welfare6_tm.py:1-31` (module docstring) | "Bias vs CRN-MC limit… ~5-15% UI (worst case where MC itself is unreliable)" | 2026-06-10: MC+CRN+stratified-shuffle canonical for ALL cells (ui_rec +0.05%); TM-a welfare = TaxCut-only backup | Status banner ("TaxCut-only backup per 2026-06-10 decision") after ruling |
| livefpc | `extract_h0_diagnostic.py:26` | `SHOCKS = ["Check","TaxCut"] # UI deprecated per memory` | UI reportable since 2026-06-10; only ui_norec stays excluded. (Multiplier-side caveat real at the time; quota-exact urates still GATED) | Rewrite to date-scoped: "UI excluded in the 2026-05-04 Phase H-0 runs (pre-variance-reduction guidance)" |
| livefpc | `estim_phase2_tm_a.py:284` | "cap pinned at module-load theGICfactor=**0.999** (DEFAULT post-Phase G)" | Same 0.9995 evidence as the EstimAggFiscalMAIN twin; behavior unaffected (line 289 imports the live value) | Same ruling-3-extension rewrite as its twin |
| livefpc | `welfare6_tm_bucket.py:4-5` | bucket-by-bucket "captures Check progressivity **correctly**" | Bucket-mean φ(pLvl) is a structural Jensen loss: +0.86-0.95% check_rec gap that does NOT converge away (2026-06-09/10 diagnosis) | Qualify: "to first order (vs rep-agent); structural ~+0.9% check_rec bias remains" |
| livefpc | `welfare6_tm_make_tex.py:5-7` | emits "welfare6_tm_only.tex … for paper if MC is dropped" | 2026-06-10: MC is the canonical paper method for all cells; the contingency resolved the OPPOSITE way | Mark TM-only output diagnostic/backup, never paper |
| hamodels | `adaptive_grid_tm.py:6-22` | module docstring presents the trim/grow `iterate()` loop as the module's method | `iterate()` is "DEPRECATED / BROKEN" (:217, fail-fasts at :264); `production_aMax()` replaced it (BUG-053 audit: non-convergent 2-cycle) | Rewrite docstring around `production_aMax()`; demote the SCHEME block to a "retired original scheme" note |
| hamodels | `reestimate_bug053_orchestrate.py:5-6` | "the cap moves the most-patient atom (college: GPF 0.9995 -> 0.999)" | Executed run used `theGICfactor=0.9995` (its own :10,:53-55,:119); user kept cap β=1.005369 (calibration-neutral) | Stamp: "initial 0.999 plan; executed 2026-06-09 run used 0.9995 — mechanism corrected, cap unchanged" |
| hamodels | `reestimate_bug053_orchestrate.py:14-15` | "GATE halt unless 867 <= aMax <= 1300 … reject the over-conservative 1300" | Code `:56` gate is `[867, 1600]`; run returned aMax=1300 and PASSED; 1300 is now production (`HAFISCAL_TM_AMAX=1300`) | Rewrite to the actual gate; drop "over-conservative" |
| hamodels | `welfare6_check_rec_bucketed5d.py:2` | "check_rec via BUCKETED-5D — **the Plan A closure**" | 2026-06-10: check_* = MC; bucketed-5D has the structural φ(pLvl) limit; 6-D is the deferred provable TM-check fix | Re-head as diagnostic with outcome stamp |
| hamodels | `welfare6_reconcile_sweep.py:4-8` | "bucket Riemann error decays ~1/n² … TM→MC as n_buckets→dense" | Empirically refuted by its own follow-up: the residual check_rec gap does not vanish with refinement (structural limit) | Append outcome stamp; keep the math as the tested hypothesis |
| orchestration | `reproduce.sh:2592` | production_fast log: "~1-2 hours (~50% of production_current)" | Its own help says production_fast "Wall ~3-6 hr" (:1041); 50% of 6-12 h = 3-6 h | Harmonize to one number (likely ~3-6 hr) |
| orchestration | `reproduce.sh:2570` | qe_fidelity_fast warning: "use --profile qe_fidelity (~10 hr including welfare)" | qe_fidelity's own estimate is "~12-24 hours" (:1034, :2544, :2571) | Harmonize to ~12-24 hr |
| orchestration | `reproduce.sh:2636` | production_cdc_tm: "Welfare numbers stay in qe_fidelity (MC) until TM welfare-6 implemented" | TM welfare-6 exists (welfare6_tm.py etc.) AND the 2026-06-10 decision made MC canonical anyway | Rewrite: "welfare-6 remains MC per the 2026-06-10 unified-MC decision (TM welfare exists, non-canonical)" |
| orchestration | `reproduce.py:6` | "Mirrors reproduce.sh with **identical CLI interface**" | reproduce.py has 7 flags; reproduce.sh ~30 (profiles/modifiers added May 2026) | Docstring rewrite: "subset mirror (core scopes only)" |
| orchestration | `reproduce/reproduce_computed_tm_only.sh:36` | echo points users at `Tables/CRRA2/Multiplier.ltx` | `AggFiscalMAIN_reduced.py --baseline` writes `Tables/Baseline/`; Tables/CRRA2 comes from a different pipeline | Fix the echo target to Tables/Baseline/ (code-string; trivial) |
| orchestration | `reproduce/reproduce_computed_TM_and_MC.sh:158` | "(Welfare_Results is obsolete on this tree; see Phase 3)" | Welfare_Results is wired and gated live (Output_Results.py:610-612); sibling script advertises its outputs; MC welfare canonical | Reword: "per-percentile Welfare_Results runs in MC mode; canonical welfare-6 comes from Phase 3" |

Borderline (class-5, escalation candidate — not counted above): the
"`--comp full` ≈ 4-5 days" wall-time family (`reproduce.sh:1020,1110,1798`;
`reproduce.py:735,1026,1062`; +3 sibling scripts; CLAUDE.md "~5 days") predates
the a-indexed TM Step-5a default (measured 9.45 h forked / ~22.5 h serial,
2026-06-11) — stamp as QE-era MC benchmark or re-benchmark once and update the
family together.

### FIXED-BY-PHASE-C

Populated at commit time by the Phase-C fix agents (one row per file batch;
AST comment-only gate result recorded per file).

| file | rows fixed (class) | commit | gate |
|---|---|---|---|
| _populated at commit time_ | | | |

### Addressed 2026-06-11 (B-items) — doc-fixes applied vs logic-fixes QUEUED

Batch from `plans/20260611_B-items-cleanup-execution.md` (Q3 = document-only for
B3/B7/B9; B5/B10/B11 = stated defaults). Worktree `HAFiscal-Latest-B-fixes`,
NOT committed by this agent (file list reported to the orchestrator). Every `.py`
edit was COMMENT/DOCSTRING-ONLY and passed the AST gate (docstring-stripped
`ast.dump` of working tree == `git show HEAD:` ).

**Doc-fixed here (comments / registry / READMEs / BUG-status; NO logic change):**

| item | row(s) | what was done |
|---|---|---|
| B7 | (c)-adjacent flags | `docs/ENV_FLAGS.md` Status → `deprecated` (+ one-line reason) for `HAFISCAL_AGENTCOUNT_TOTAL` (echo-only), `HAFISCAL_RUN_ONLY_SHOCK` (print-if-set), `HAFISCAL_STEP5_SCOPE` (write-only), `HAFISCAL_IS_FORCE_LOW_ANRM` + `HAFISCAL_WELFARE6_TM_INIT_MEASURE` (IS pathway superseded 2026-06-10). Deprecation `# NOTE` comment added at each read site (jax_mc_baseline_5x_bench.py:24, run_step5a_only.py:72, AggFiscalMAIN_reduced.py:159, welfare6_scenario_IS.py:155, welfare6_scenario.py:525, run_hybrid_welfare6.py:178). No code removal/wiring. |
| B10 | `TM_MCOUNT`, `USE_JAX_2B` | `docs/ENV_FLAGS.md` notes: `HAFISCAL_TM_MCOUNT` 50/100/200 per-call-site defaults documented as INTENTIONAL per-context (not a unify); `HAFISCAL_USE_JAX_2B` classified DEV-ONLY pending an explicit production sanction. |
| B9 | (k) | `do_all_reduced.py` control-panel comment: hardcodes steps 1/2/4/5 ON, IGNORES `HAFISCAL_RUN_STEP_{1,2,4,5}` (only RUN_STEP_3 honored). Note only — `_env_run` wiring NOT done. |
| B9 | (j)/17 | `Makefile` `test:` target comment: points at nonexistent `tests/` (real: `pytest Code/ reproduce/`). Target NOT changed. |
| B9 | (l) | `Clean_Folders.py` comment at the `./AggFiscalMAIN.py` guard: SST file is RETIRED on this branch so the tool always errors. Not fixed. |
| B9 | (o)/22/23 | `ARCHIVED-IN-PLACE / fictional` banner added atop the `reproduce/upgrade-validation/` entry scripts (step_runner.py, interactive_validation.py, parallel_validation.py + the 4 run_*.sh launchers). Directory left in place. |
| B5 | (g) | Created `BUGS_private/HAFiscal_BUG-044_stratified_shuffle_mrkv_transition.md` (HARK PR #1776 stratified-shuffle assignment-step fix; Status: Fixed). De-numbered `welfare6_tm_joint5d.py`'s internal "BUG-044/045" labels → local `FIX-A`/`FIX-B` (joint-5D kernel fixes #10/#11; never registry bugs). |
| C3 | — | `HAFiscal_BUG-053*.md` Status → "RE-ESTIMATED 2026-06-09 (theGICfactor=0.9995, committed d1a06a9c); calibration-neutral cap"; `HAFiscal_BUG-043*.md` "default still legacy" → "default = bug_fix since 2026-05-16 (EstimParameters.py:217); QE via QE_FIDELITY / explicit legacy". |
| B11 | — | Archive READMEs: corrected `diagnostics_archive/README.md:36-37` (the "compute_welfare6_se_table.py imports diag_welfare6_se" premise is FALSE — string-ref only) and `welfare6_diagnostics_archive/README.md:13,15` (`welfare6_tm_aggregate` + `welfare6_tm_make_tex` are NOT canonical core — zero consumers; keep-for-now). No files moved. |

**Logic fixes QUEUED (pending owner greenlight — NOT done in this round):**

| item | row | queued logic change |
|---|---|---|
| B3 | (b) | `Parameters.py` GICx FALLBACK value (GICx=4.0 clips central College β under BUG-053 GPF-shave; invariant needs factor²>0.9737 ⇒ GICx>4.31, e.g. 4.5). Re-derivation + code fix owner-gated. **(Parameters.py is owned by the orchestrator — deferred.)** |
| B7 | (wiring) | Either wire `HAFISCAL_AGENTCOUNT_TOTAL` / `HAFISCAL_STEP5_SCOPE` into their intended consumers, or remove the dead `setdefault` / print lines (code removal). Doc-deprecation only this round. |
| B9 | (k) | `do_all_reduced.py`: wire do_all.py's `_env_run` for `HAFISCAL_RUN_STEP_{1,2,4,5}`; fix the "3 types × 7 β atoms" scale claim (Reduced_Run is 3 types × 1 β atom). |
| B9 | (j)/17 | `Makefile` `test:` recipe → `pytest Code/ reproduce/`. |
| B9 | (l) | `Clean_Folders.py`: repoint the SST off the retired `AggFiscalMAIN.py` (or archive the tool). |

**Deferred to orchestrator (owned files this agent must not touch):** B3 lives in
`Parameters.py`; C1/C2 (already filed as BUG-058 / BUG-059) live in `Parameters.py`
and `solution_cache/keys.py`. Those code edits are out of this agent's scope.

### Docstring-coverage census (counted for a future sized pass — NOT filled now)

Per ruling 4, backfill in this pass is restricted to the owner-named entry
points; everything else is counted only.

- **Core (partition 1)** — named-list status, AST-verified: CONFIRMED missing → `Welfare.Welfare_Results`, `Parameters.return_parameters`, `Parameters` module docstring, `welfare6_scenario.main`. ALREADY documented (lighter touch) → `welfare6_scenario.build_and_solve` (has a docstring; de-line-number its "run_hybrid_welfare6.py lines 47-144" pointer when touched), `EstimAggFiscalMAIN` module docstring (exists; entry-point internals light). Counted-but-not-filled → `FiscalTools.run_experiment` ("Returns: TBD" placeholder), assorted `tm_methods.py` private helpers, `Output_Results.py` plotting helpers.
- **Live FromPandemicCode (partition 2)** — 27 priority files: **76 of 175 functions missing docstrings (57% coverage** — matches the plan's ~55% estimate). Worst files: `harmenberg_doob_tier1.py` 5/5 missing, `verify_welfare_replay.py` 2/2, `welfare6_tm_bucket.py` 6/8, `welfare6_tm_repagent_from_csvs.py` 5/7, `welfare6_tm_stratified.py` 5/8, `run_welfare6_parallel.py` 8/16.
- **HA-Models top-level (partition 3)** — no per-function census reported in the inventory (partition surveyed for claim-staleness only); fold into the future sized pass.
- **Orchestration (partition 4)** — **129/162 functions documented (80%)**. Gap files: `Estimation_BetaNablaSplurge.py` **3/14** (the only production-pipeline file in the gap list), `build_manifest.py` 20/23, `profile_do_all.py` 1/3, version-comparison `test_step*.py` 0-1 each, `reproduce.py` 19/20, upgrade-validation modules ~1 missing each. None of the owner-named backfill entry points lives in this partition.
- **Sizing for the future pass:** ≈110+ undocumented functions outside the named list (76 livefpc + 33 orchestration + core/hamodels counted items), concentrated in diagnostics and the welfare6_tm_* family.

---

## Phase A/C — comment-hygiene, orchestration + shell partition (2026-06-11)

Partition inventory: group 4 of `plans/20260611_code-comment-hygiene.md`
(scope: root `reproduce.sh`/`reproduce.py`/`monitor.sh` + `reproduce/**` +
`Code/Empirical/` + `Target_AggMPCX_LiquWealth/`). Row numbers below are the
partition inventory's. Classes 2/4/5 were APPLIED in Phase C (comment/help-text
only; AST-gated for `.py`); CONTRADICTED rows are logged here for owner triage
— **no code/env/behavior line was changed**.

### CONTRADICTED — owner triage required (log-only) — HISTORICAL: closed 2026-06-12 (see RESOLUTIONS section above)

| row | file:line | claim vs reality | behavior-implicated? |
|---|---|---|---|
| 11 | `reproduce.sh` `--profile qe_fidelity` (help ~1031; case arm ~2540) | Help says "Reproduce HAFiscal-QE methodology with current code", but the profile does NOT set `HAFISCAL_QE_FIDELITY=1` — since the 2026-06-10 canonical Plan-A defaults (EstimParameters.py setdefault block: shuffle ON, stratified Mrkv transition, TM_AMAX=1300), a run inherits the NEW canonical welfare/grid defaults, not the QE world. Owner: add `export HAFISCAL_QE_FIDELITY=1` (behavior change) or reword the claim. A NOTE comment was added above the env block; env lines untouched. | YES |
| 12 | `reproduce.sh` `production_current` arm (~2580) | Labeled "Snapshot of current default behavior" but PINS legacy GICx + `HAFISCAL_NM_START_FROM_SAVED=0`, while code defaults are `hardcoded` + `1` (EstimAggFiscalMAIN.py:1281/:1312). Owner: relabel (e.g. "2026-05 legacy-GICx pin") or update env to true defaults. NOTE comment added; env lines untouched. | YES |
| 16 | `reproduce.sh` ~2645 (`production_cdc_tm`) | "Welfare numbers stay in qe_fidelity (MC) until TM welfare-6 implemented" — TM welfare-6 exists (welfare6_tm.py) AND the 2026-06-10 unified-MC decision made MC canonical for all welfare cells. Suggested rewrite: "Welfare-6 remains MC per the 2026-06-10 unified-MC decision (TM welfare exists but is non-canonical)." | comment-only, but owner asked to confirm wording |
| 17 | `Makefile:15,42-43` | `test:` recipe runs `pytest tests/`; no `tests/` dir exists (CLAUDE.md prescribes `pytest Code/ reproduce/`). Broken make target = code fix, outside the comment-only gate. | YES (broken target) |
| 19 | `Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py:243-246, 270-274, 341, 466` | Docstrings promise ESC sibling helpers (`_wealth_under_esc`, `_lottery_consumption_under_esc`) "planned in plans/20260425-2137h_cdc-esc-configurable-refactor.md Phase B" — plan DONE/closed, helpers never built; `_wealth_under_cdc` is called UNCONDITIONALLY (lines ~343/350) even under `HAFISCAL_INTERPRETATION=ESC` (only the agent TYPE dispatches). Owner must rule: (a) is unconditional CDC wealth-correction under ESC intended, or a new BUG report? (b) then the 4 in-docstring promises get rewritten accordingly. The section header above the helpers (line ~228) was rewritten in Phase C to state this reality and point here. | YES (ESC-mode Step-1 semantics) |
| 20 | `reproduce/reproduce_computed_tm_only.sh:~40` | Final echo points users at `Tables/CRRA2/Multiplier.ltx`; the `--baseline` run writes `Tables/Baseline/`. Fix is an output-message edit (functional echo of a result path) — owner confirm. | message only |
| 21 | `reproduce/reproduce_computed_TM_and_MC.sh:~158` | "(Welfare_Results is obsolete on this tree; see Phase 3)" — Welfare_Results is live and gated (Output_Results.py `has_individual_data`); 2026-06-10 decision keeps MC welfare canonical. | comment-only; wording to owner |
| 22 | `reproduce/upgrade-validation/interactive_validation.py:92-101` | Pins Python 3.9 for HARK 0.14.1 (CLAUDE.md: use 3.10) and pypi `econ-ark==0.17.0` (branch needs the pinned git ref with normalization/dual_measure). Disposition: archive-in-place banner vs correct pins — owner. | YES if harness rerun |
| 23 | `reproduce/upgrade-validation/step_runner.py:11-16,52-69` | Step labels diverge from do_all's canonical steps; none of the 4 expected result files has ever existed. Same archive-banner disposition as row 22. | YES if harness rerun |
| 32 | `reproduce/upgrade-validation/email_config.py` | Security escalation — handled separately out-of-band by the owner (per Phase C task instruction); not part of this comment pass. | YES (out-of-band) |

### Applied in Phase C (this partition)

- Class 2 (STALE-FORWARD-REF): `reproduce.sh` BUG-039 "requires … to be landed" ×4
  (help :1041/:1044 + production_fast/tm_throughout_fast WARNINGs) → past tense
  (Phases A/E/G landed; `hardcoded` GICx + warm-start are code defaults,
  EstimAggFiscalMAIN.py:1281/:1312); `Estimation_BetaNablaSplurge.py:228` section
  header → current reality + pointer to row 19. `reproduce.py` module docstring
  "identical CLI mirror" → subset-CLI statement (row 18, pre-authorized).
- Class 4 (ORPHAN-REF): 3× `bug034_*.sh` plan path → `plans/20260425-2137h_cdc-esc-configurable-refactor.md`;
  3× `docs/SCF_DATA_VINTAGE.md` → `reproduce/reproduce_data_moments/SCF-data-appendix.md`
  (reproduce.sh, reproduce_data_moments.sh, adjust_scf_inflation.py); `Splurge.txt`
  → `Result_AllTarget*.txt` (reproduce.sh qe_fidelity_fast comment); monitor usage
  self-name (NOTE: root `monitor.sh` is a committed SYMLINK to
  `Code/HA-Models/hafiscal_monitor.sh` — row 8's "two different files" premise was
  wrong; fixed via an alias note in the real file, not a rename);
  `reproduce_scf-data-downloads-comparisons.sh` usage self-name; stale
  `Output_Results.py:593-597` pointer → line-number-free `has_individual_data` gate.
- Class 5 (UNVERSIONED-CLAIM): "4-5 days"/"~6 days"/"~65h Step 5" family stamped
  "(migration-era figure; Step-5a measured 9.45h forked-AD at Baseline, 2026-06-11;
  see Code/HA-Models/README.md)" across reproduce.sh, reproduce_computed_min.sh,
  reproduce_documents.sh, reproduce_figures_from_results.sh,
  run_full_comp_validation.sh, and as AST-safe `#` NOTEs in reproduce.py (the
  in-string print/help occurrences cannot be edited under the comment-only gate);
  "~26 min TM" + "Phase 1 (TM, ~1h)" stamped m-indexed-era (canonical a-indexed
  Step-5a slower); profile wall-time table stamped "2026-05 profile-plan estimates";
  version-comparison fixture dicts labeled (0.14.1-era pins ≠ post-BUG-053
  2026-06-09 calibration; Splurge0 pins verified == live Results file).
- Internal runtime contradictions harmonized (rows 14, 15): production_fast
  "~1-2 hours" → "~3-6 hr (2026-05 est; varies by hardware)"; qe_fidelity_fast's
  "~10 hr" → "~12-24 hr" (matches qe_fidelity's own estimate).

Open owner question carried from row 28: `--comp TM-and-MC` / `--tm-only` produce
m-indexed TM multipliers while do_all's canonical Step-5a is a-indexed (BUG-033)
— should these paths set `HAFISCAL_TM_A_INDEXED=1`?
