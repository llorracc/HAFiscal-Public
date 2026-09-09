# Robustness appendix on the current stack — plan (2026-08-20 21:00)

**Charge** (owner ruling 2026-08-20 ~20:00): the robustness appendix is in scope for the
current version — "run after the no-splurge chain". Machines: dell + m5 (+ xubuntark when it
resolves; `xubuntark` does not resolve from dell tonight). Promotion of anything stays the
owner's action, deferred until the chains land.

## What the appendix contains and what each piece needs

`Subfiles/Appendix-Robustness.tex` (all tables HAND-TYPED; no generated inputs):

| exercise | configs (Parameters.py) | estimates shown | welfare shown | multipliers quoted | figures |
|---|---|---|---|---|---|
| interest rate | `Rfree_1005`, `Rfree_1015` | (β,∇) per education; splurge NOT re-estimated (same 0.30 across R) | 𝒞 in basis points, no-AD and AD | — | `LorenzPoints_robustness_R.pdf` |
| risk aversion | `CRRA1`, `CRRA3` | splurge AND (β,∇) re-estimated per γ | 𝒞 bp | — | `LorenzPoints_robustness_CRRA.pdf`; Step-1 CRRA comparison figs |
| benefits | `LowerUBnoB` (ρ_b 0.3, ρ_nb 0.15) | (β,∇) per education | 𝒞 bp | — | — |
| recession properties | `Rspell_4`, `ADElas` (κ 0.5) | none (main calibration) | 𝒞 bp | yes (1.224/1.180/0.967; 1.636/1.492/1.152) | — |

## Producibility on the certified stack (scoped tonight)

- **Step 2 per config** — YES, unchanged machinery: `estim_phase2_tm_a.py R CRRA IncUnemp
  IncUnempNoB splurge` names its outputs `DiscFacEstim_CRRA_{CRRA}_R_{R}[_altBenefits]…`,
  exactly what `Parameters.py` resolves for each parametrization. 3 groups × 4 cold COBYQA
  starts, ATI; ~40 min (dell) / ~60 min (m5) per config.
- **Fit-table pass per config** (`AllResults_*`; the Lorenz robustness figures' inputs) —
  YES with the BUG-080 workaround (`HAFISCAL_NM_IN_PLACE=0`). `CreateLPfig.py`'s robustness
  reads (argv 1 = R figure, 2 = CRRA figure) are NOT interpretation-resolved → extend the
  BUG-081 fix to those four reads before regenerating.
- **Step-1 re-estimation for CRRA 1 / 3** — NEEDS CODE: the arm is a literal
  `Run_other_CRRA_values = False`, runs the 27-point grid sequentially, has no START_SUBSET
  sharding, no winner-writer, and saves `Result_AllTarget_CRRA_{c}_startpoint{i}.txt` while
  `Parameters.py` reads `Result_CRRA_{c}.0.txt`. Refactor (~1 h): env gate
  `HAFISCAL_STEP1_OTHER_CRRA=1`, START_SUBSET sharding, min-f winner → `Result_CRRA_{c}.0(.txt|_ESC.txt)`.
  Then ~25 min sharded per γ.
- **Multipliers for Rspell_4 / ADElas** — NEEDS a generic `--parametrization NAME` flag in
  `AggFiscalMAIN_reduced.py` (only `--baseline/--splurge0/--hs-only` exist); ~30 min each.
- **Welfare in basis points (𝒞)** — NOT producible by the certified welfare engine: the
  tables come from the legacy `Welfare.py::Welfare_Results` (welfare4/5), which needs
  individual-level MC consumption (`cLvl_all_splurge`); the TM reduced Step-5 skips it
  ("TM mode produces aggregates only") and the welfare6 battery emits only the 𝒲 ratio.
  Options for the owner: (a) run Step 5 in MC mode per config (`HAFISCAL_SIM_METHOD=MC`,
  the reliable-MC engine; hours per config, 7 configs); (b) extend the welfare6 battery to
  emit 𝒞 from the same welfare impacts (engineering + a Baseline cross-check against (a));
  (c) keep the bp tables at their QE values and re-run only estimates/figures/multipliers.
  **Ruling needed before any welfare compute.**

## Tonight (no ruling needed)

- **m5 (idle):** `robust_m5.sh` — Step 2 + fit-table pass for `Rfree_1015`, then
  `LowerUBnoB`. Launched 2026-08-20 ~21:00. ETA ~2.5 h.
- **dell (after the no-splurge chain, ~23:30):** Step 2 + fit-table pass for `Rfree_1005`
  (driver `robust_dell.sh`, chained on the chain's completion marker). ETA ~1 h.
- Tomorrow morning: the CRRA Step-1 arm refactor → CRRA1/CRRA3 Step 1 (sharded) → Step 2 → fit
  passes; the `--parametrization` flag → Rspell_4/ADElas multipliers; the Lorenz robustness
  figures; the appendix-table diff script (candidate (β,∇) per config vs the hand-typed
  rows). Welfare per the ruling above.

## ETA

Estimates + fit passes + figures + multipliers: done by ~noon 2026-08-21 on dell + m5.
Welfare bp tables: +1 day if (a); +½ day engineering + validation if (b); 0 if (c).

## Records

Per-config logs `~/coldrun_2026-08/robust_<config>_*.log` (m5, dell); outputs in each
worktree's `Results/` (`DiscFacEstim_*`, `AllResults_*_candidate`); record dir
`Results/cold_rerun_2026-08/s9_robustness/` when assembled.

## Execution log

- 20:54 m5 part A: `Rfree_1015` (19 min) and `LowerUBnoB` (28 min) Step 2 + fit passes DONE 21:48;
  calibrations installed `8533c492`. LowerUBnoB Dropout ∇ = 0.4000 = search-box bound (4/4 starts).
- 21:3x **BUG-082** found and fixed (`7d66c5ad`): the appendix 𝒞 tables divided utils by a
  log-utility normalizer; the battery now writes `welfare4.tex`; `HAFISCAL_WELFARE_CE_HORIZON`
  (lifetime|panel) is the remaining owner ruling — both renderings come from the same pickles.
  → the welfare-bp question above is RESOLVED in favour of option (b) with the corrected formula.
- 21:50 m5 part B: `Rfree_1005` Step 2 + fit pass → welfare batteries (offset 0) for
  Rfree_1005, Rfree_1015, LowerUBnoB (`robust_m5_b.sh`).
- 21:5x dell part B armed behind the no-splurge chain: welfare for ADElas, Rspell_4 + their
  multipliers via the new `--parametrization` flag (`robust_dell_b.sh`).
- Tomorrow: Step-1 CRRA arm refactor → CRRA1/CRRA3 chain; `CreateLPfig` robustness reads
  (ESC); Lorenz robustness figures; 𝒞 tables rendered per the horizon ruling; the
  hand-typed-table diff.
- 22:05 OWNER RULING: `HAFISCAL_WELFARE_CE_HORIZON=lifetime` (the default) — 𝒞 = permanent
  proportional consumption change; decision record
  conclusions_private/2026-08-20_bug082-welfare-ce-lifetime-horizon-ruling.md. No re-runs.
- 22:15 pre-overnight decision review → three OWNER RULINGS (~22:30):
  1. **BUG-083** — the LowerUBnoB dropout Step-2 estimate (8533c492) was PINNED at the Step-1
     search box's ∇ end (all 4 starts at ∇ = 0.4000 exactly; objective 2.20 vs 0.11 for dropouts
     elsewhere; published 0.445* / γ = 3: 0.459*). Ruling: widen the Step-2 end to 0.55 (= widest
     end keeping every atom positive at the cap) — `HAFISCAL_STEP2_NABLA_MAX`, `NABLA_AT_BOX`
     tripwire, commit `ed80c247`. Re-estimate of the LowerUBnoB dropout group + interior re-check
     of the main-spec dropout group: dell, wt2 (`robust_dell_c.sh`, 22:34) → staged to m5 →
     `robust_m5_c.sh` redoes the LowerUBnoB fit pass + welfare after part B (part B's LowerUBnoB
     welfare on the pinned calibration is SUPERSEDED; its outputs renamed `_SUPERSEDED_nabla04`).
  2. Seeds for the appendix welfare tables: KEEP single seed (offset 0). Measured from the m5
     `s5b_spine.log` Baseline tables: UI 𝒲 1.80 / 1.74 / 1.77 across seeds 0/1/2, check 1.02 /
     1.01 / 1.01, tax cut 0.99 ×3 → ≤ 1.7% seed noise, far below the cross-configuration
     differences the appendix reports (e.g. the published UI column moves ±30% across R).
  3. γ rows: re-estimate the splurge per γ as the published appendix did → the Step-1 arm
     refactored (`HAFISCAL_STEP1_OTHER_CRRA`, sharded, winner to `Result_CRRA_<g>.0_ESC.txt`;
     commit `5e82651f`, smoke-tested at γ = 3) and `crra_chain.sh` armed on dell behind the
     BUG-083 runs: per γ ∈ {1, 3}: 8 Step-1 shards → merge → `dist_aGrid_max` re-derived at that
     γ (`production_dist_aGrid_max` under the γ's EstimParameters → `HAFISCAL_TM_AMAX`) → Step 2
     (3 groups × 4 starts, ∇ end 0.55) → fit pass → welfare (offset 0).
- 22:50 FINDING (process): `run_welfare6_parallel.py` names pickles/tables WITHOUT the seed and
  the spine drivers ran `--seed-offset 0,1,2` into the SAME directories → each seed overwrote the
  previous; the spine4 packet's `welfare6_candidate.tex` is seed 2 alone (the "S=3" row of the
  report was an overstatement; the three tables survive only in `s5b_spine.log`). Fixes armed:
  `seedsnap_Splurge0.sh` snapshots the N5 seeds as each table lands; `robust_m5_d.sh` re-runs the
  Baseline seeds 0/1/2 into `--out-dir/--table-dir` per seed after part C (so the S=3 band and
  the per-seed 𝒞 exist for real). Morning: a small aggregation step (mean ± band) for the packet,
  and `--seed-offset` should refuse to run without a per-seed `--out-dir` (or derive one).
- Overnight schedule (dell): N5 → N6 → `robust_dell_b.sh` (ADElas, Rspell_4 welfare + multipliers)
  ∥ `crra_chain.sh` (γ = 1 then 3). (m5): part B → part C (LowerUBnoB corrected) → part D
  (Baseline per-seed). Monitors on all.
- 22:58 BUG-083 runs landed: LowerUBnoB dropouts **β 0.6236 / ∇ 0.4370 / f 0.076** (4/4 starts;
  pinned run 0.6557 / 0.4000 / 2.20; published 0.609 / 0.445*); main-spec dropout re-check 4/4 =
  installed 0.7481 / 0.2916. Installed in main (`6b6003f8`); staged to m5 (part C). R = 1.005
  cal installed (`9ccb9f25`): D 0.7517/0.2922, HS 0.9438/0.0703, C 0.9980/0.0117.
- 23:15 **γ = 1 PARKED — OWNER DECISION NEEDED.** All 8 cold Step-1 starts converge to the SAME
  point: splurge = 0 (on the face), β 0.98031, ∇ 0.02440 — top atom AT the γ = 1 cap (1.00132) —
  with objective **0.441** (γ = 2 optimum: 0.0017; start points: 1.0–1.4). Under the ergodic TM
  engine the log-utility model cannot reach the wealth targets without patience beyond the GIC,
  which the cap forbids by construction. The published γ = 1 row (splurge 0.312, D 0.692/0.333,
  HS 0.966/0.154*, **C 1.05†** = "all atoms violate the GIC, replaced") only existed because the
  MC engine's finite burn-in tolerated non-stationary patience. Options: (a) drop the γ = 1 row
  and say why (recommended: the row was an artefact of a non-ergodic simulation); (b) report
  γ = 1 as the constrained optimum with its fit (splurge 0, cap binding) and the explanation;
  (c) reproduce the published row under the legacy MC Step-1 engine — reproduces an artefact
  (Step 2/5 still need the GIC). Artefacts: `Results/cold_rerun_2026-08/crra1_parked/`.
- 23:20 **BUG-084** (OPEN): `production_dist_aGrid_max` returns 19,900 at EVERY γ (incl. 2): its
  "β = 1.01 clips to the cap" premise is stale under the aggregate-cusp cap (College cap 1.0114);
  the cap atom's 1e-4 quantile is ~20,000 (mortality-only tail) and the installed College top
  atom keeps 3.0e-3 of its mass above 1,300 (q(1−1e-4) = 8,968). Not on the run path; the
  sizing RULE needs an owner re-ruling. Chain: G2 re-derivation RETIRED, every row runs on the
  production 1,300, a `[tail-diag]` line logs the estimated College top atom's tail per γ.
- 23:21 `crra_chain.sh` relaunched with `GAMMAS=3` (γ = 3 only; published row feasible under the
  cap 1.01395: C 0.973, D ∇ 0.459 < 0.55). Commit `ac3602c6`.
- 23:52 γ = 3 Step 1: **8/8 in one basin** — winner splurge 0.3009 / β 0.9656 / ∇ 0.0472,
  f 0.00168 (published splurge 0.304); installed `d7bb94f3`. Step 2 at γ = 3 started.
- 00:07 **INCIDENT:** the harness reaped three idle launcher shells; the no-splurge driver
  (nohup'd, not setsid'd) died with its launcher 8 min into the Splurge0 seed-2 battery (seeds 0
  and 1 complete + snapshotted: UI 𝒲 1.77 / 1.68, check 1.02 / 1.02, tax cut 0.98 / 0.98 at
  Rec, AD=0). `robust_dell_b` then started and HALTed at its worktree fast-forward (untracked
  copies of the six Splurge0 calibration files I had just committed to main `152f5e9c`; plus a
  dirty tracked `Result_AllTarget_Splurge0.txt`). Fixed 00:09 (cmp-verified removal + checkout),
  ff to `152f5e9c`, `robust_dell_b` relaunched (setsid) — ADElas welfare from 00:09. Seed-2
  re-run launched in the same wt with explicit `_seed2` dirs (`nosplurge_seed2_rerun.sh`);
  N6 (the SplurgeComp table) moves to the morning, composed from the seed-aggregated tables.
  Step-3 calibration installed in main (`152f5e9c`).
- **2026-08-21 12:25 — N6 COMPOSED (S=3).** Seed-2 Splurge0 rerun completed 12:16 (flag
  `nosplurge_seed2_rerun.done`; explicit `_seed2` dirs). Seed aggregation via
  `welfare6_seedband.py` (inputs counted, 3 distinct tables each): Splurge0 welfare6
  largest relative half-range 2.61% (UI rec cell 1.73 ± 0.045); Baseline (m5 part D)
  welfare6 1.69% (UI 1.77 ± 0.030); Baseline welfare4 abs half-ranges ≤ 0.30 but the
  near-zero 𝒞(Rec, taxcut) cell (−0.13 ± 0.075) makes the relative figure (58%) misleading
  — small-denominator artifact, quote absolute. Aggregates in `~/coldrun_2026-08/seedagg/`.
  N6 = `welfare6_splurgecomp.py` on the two seedmeans →
  `Tables/Splurge0/welfare6-SplurgeComp_candidate.tex` (frozen file untouched;
  run_id fe56eaf7_baab8a_20260821-122518). vs QE frozen: ς=0 cells within 0.01–0.04,
  baseline parens shift more (e.g. check AD 1.27(1.38) vs 1.27(1.35)); ui_norec blank by
  design. Remaining on dell: robust_dell_b (ADElas→Rspell_4), γ=3 resume (G3 live).
- **2026-08-21 ~13:00 — owner rulings on the §4 docket** (morning report): **(3) QE freeze
  STANDS — no promotions.** All cold-rerun tables remain `_candidate` siblings (branch-installed
  calibrations stay; the rendered paper keeps the QE-published numbers; preview via
  `make pdf-candidate`). Item closed. **(4) `--seed-offset` guard ADOPTED** — the `878b0475`
  per-seed-default-dirs implementation is the standing behavior (verified at function level:
  seed 0 → production paths byte-for-byte; K>0 → `_seed<K>` dirs + `[seed-dirs]` note; explicit
  dirs win); stale `--seed-offset` help text synced in this commit. **(1) γ=1**: clarified as
  the robustness-appendix CRRA row (the chain already run; parked at the ς=0/cap face) — the
  a/b/c ruling remains open, no urgency under the freeze. **(2) BUG-084**: plain-language
  explanation delivered; the sizing-rule re-ruling remains open (tool refuse-at-ceiling fix is
  unblocked either way).
- **2026-08-21 ~14:05 — BUG-084 RULED (implementation deferred).** Owner adopted the
  onset ∧ support criterion (one EGM step from the PF anchor → mortality-inclusive kernel
  asymmetry → per-atom onset, intersected with per-atom mass support; tail state above) as
  the principled dist-grid-top rule; it ratifies 1300 at τ≈1.3% and updates cap-atom
  α to 1.42 (ρ=2) / 1.26 (ρ=3) under the aggregate-cusp cap. Implementation waits on the
  owner completing the 08-20/21 speedup testing. SoT:
  `conclusions_private/2026-08-21_dist-top-onset-rule-ruling.md`; deferred-log entry added.
- **2026-08-21 ~15:00 — the γ=1 finding is now BUG-086** (owner: "if not documented, it
  should be a BUG"): the published row's defect documented as two layers — finite-burn-in
  MC objective well-defined only through the horizon in the GIC-violating region (the
  paper's own † footnote acknowledges all atoms violated the GIC), plus the post-hoc
  "replaced with a value below the upper bound" whose replacement is unreported. The a/b/c
  presentational decision (still open) should cite BUG-086; recommendation (a) unchanged.
- **2026-08-21 ~15:15 — γ=1 RULED (a) AND EXECUTED**: owner ruled "drop the γ=1 row,
  citing BUG-086". `Subfiles/Appendix-Robustness.tex` edited (7 surgical edits): row out of
  `tab:robustness_gamma` (+ † footnote retired), γ=1 row out of the mlwpi table, the three
  γ=1 paragraphs → the omission explanation (BUG-086 cited in a tex comment; public prose
  carries the substance: no GIC-satisfying configuration matches the wealth targets at log
  utility; earlier estimates were finite-simulation artifacts), results-section sentence
  sharpened, and a new sentence ties the mlwpi table + Lorenz figure to the γ=3 discussion
  (figure regeneration without γ=1 panels → TODO). **The owner docket is now EMPTY.**
