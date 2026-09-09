# Shared solved-policy store: solve each household problem once, everywhere

**Owner charge (2026-08-24 ~15:00):** "implementing the shared solved-policy store proposal
is the most urgent thing on the agenda, since it may result in major timing improvements
that will speed everything else. Make a plan now to implement that. (Did the HAFiscal-QE
version solve everything twice, or is this a defect that we introduced?)"
**Status (2026-08-24 21:15): P0–P4 LANDED on the sub-branch; both byte-identity gates
PASSED (multiplier entry on m5, welfare battery on xubuntark); the store is DEFAULT-ON
(P3 flip) at `~/.cache/hafiscal/policy_store`; the sub-branch fast-forwards into the
working branch with this commit. Execution log at the end of this file.**

**Earlier status (2026-08-24 evening):** P0 + P1 code LANDED on the sub-branch
`0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_policy-store` (commit 3a0a0657): store
module, solver-aware key, one-sweep HIT guard, hooks in the economy solve and both
welfare workers, `[solve-wall]` accounting, tests (10 passed incl. the HS_Only
byte-identity tier). **P1 gate PASSED on ccarroll-m5** (`~/gate_p1_m5.out`, Reduced_Run
multiplier entry): `Multiplier_candidate.tex` byte-identical across store OFF / ON-cold /
ON-warm (the only differing files are the per-run timestamped `RUN_*.prov.json`
sidecars — exclude them in diff gates); ON-warm: 24 HITs, 0 REJECTED, one-sweep moves
3e-5…1e-4; each cold economy solve of 50–55 s (3 agents, S=132: accel 23–26 s + ATI
27–30 s) became ~2 s on hits; the sidecar carries the `policy_store` and `solve_wall`
events with determinism `pure-config`. macOS tests: 10 passed on ccarroll. P2 code
landed (older cold-solution layers no-op under the store; AD key + solver-source hash);
P2 welfare-battery gate RUNNING on xubuntark (`~/gate_p2_xub.out`). Owner's ten
mid-way questions were asked 2026-08-24 ~16:00 with defaults; proceeding on the defaults
until answered. Companion records: BUG-089 (the discrepancy that exposed the double
solve), `conclusions_private/2026-08-24_bug088-knife-edge-verdict_*.md` §7–7b.

## 0. The historical question first

**The published QE code solved once.** `HAFiscal-QE/Code/HA-Models/FromPandemicCode/
AggFiscalMAIN.py` is one program: per scenario it solves the 21 types, runs the Monte-Carlo
simulation, saves the results; `Output_Results.py` then calls `Welfare.Welfare_Results(
saved_results_dir, …)`, which reads those saved simulation results — welfare was a
post-processing of the same simulated paths, never a second solve.

**We introduced the second solve**, in two steps, each for a good reason and neither
noticing the duplication: (a) 2026-04-17 (`26c012f9`, "MC welfare-6 subprocess parallelism:
9.88× speedup") gave welfare its own driver (`run_welfare6_parallel.py` →
`welfare6_scenario.py`) so it could run 5× the agents, several seeds, and cell-parallel
workers — each cell builds and solves its own economy; (b) the multipliers moved to the
TM a-indexed engine in `AggFiscalMAIN_reduced.py` (Step 5a) while welfare stayed Monte
Carlo (Step 5b), so the two entries became separate programs with separate solve paths —
and, since the fast solver (ATI) was wired only into the economy-level dispatcher that 5a
uses, separate *solvers*. Inside the welfare battery the duplication was later mitigated
with its own caches (§1), but nothing crosses the entry-point boundary, and the multiplier
entry caches nothing: every S5a run, every seed of a seed battery, and each of its four
forked shock workers re-solves the base structure cold.

## 1. What exists today (inventory — the store extends this, it does not add a mechanism)

| layer (`Code/HA-Models/solution_cache/`) | what it stores | key | consumers | gate |
|---|---|---|---|---|
| `recession_init` (`cache.py:381–470`) | the cold per-economy AD-off solution per `shock_type` (knot-extraction serializer → **lossy tails**, BUG-067 class) | `compute_solve_key` = SHA256 of `gather_solve_inputs`: per-agent primitives (`_agent_params_dict`: DiscFac, CRRA, Rfree, LivPrb, PermGroFac, aXtraGrid, Cgrid, IncShkDstn, MrkvArray, …) + AD params + an env whitelist (19 vars) — excludes commit SHAs | welfare battery (save in `run_recession`, load at AD init) | `HAFISCAL_USE_SOLUTION_CACHE=1` + `HAFISCAL_AD_INIT_CACHE` |
| `policy_full` (`cache.py:600–692`) | the same, **wholesale pickle** of `agent.solution` (lossless, tails included) | same key | welfare battery | master gate |
| `ad_full` (`cache.py:693+`) | the AD-converged (belief CFunc, policies) pair, wholesale; every HIT re-verified by the owner's one-iteration double-check | solve key + engine | welfare AD loop | master gate + `HAFISCAL_AD_FULL_CACHE` |
| presolve capture (`HAFISCAL_REPLAY_PRESOLVE_CACHE`) | the replay engine's captured presolve panel | sim key | hybrid welfare engine | bundle |
| `base_aggcons` | the base run's AggCons vector (sim artifact) | sim key | welfare children | master gate |

Gaps the store closes:

1. **The multiplier entry (5a) uses none of it.** `AggregateDemandEconomy.solve()` has no
   load/save hook; the ATI router, the NAMG branch and `solve_agent` all solve cold.
2. **Per-economy granularity.** Entries are the 21-agent bundle for one `shock_type`; a
   robustness variant that changes one education group, or the Step-2 estimator's
   `only_agents` re-solve, cannot reuse the other 14–20 agents' solutions.
3. **The key misses the solver's *code*.** CORRECTED 2026-08-24 evening (my first
   reading of the whitelist was truncated): `keys.py::_HAFISCAL_NUMERICAL_ENV_VARS`
   DOES key `STEP5_ATI` (+ `MIN_DISCFAC`), `PF_DECAY_EXTRAP`, `PF_DECAY_Q`, `STEP2_NAMG`,
   `USE_JAX_2B` and the primitives-affecting flags; the grid is safe (aXtraGrid is a
   primitive in the key; `SLICE_INTERP`, `SOLVE_ACCEL`, `NEWTON2D_*`, `DIST_TOP_MODE`,
   `T_AGE` are keyed too — second correction, after reading the tuple to its closing
   bracket). What it lacks: `USE_JAX_SOLVER` (deliberately excluded as "same cFunc to
   <1e-3", the kernel-parity class) and — the real gap — any solver *source* version: a
   solver edit at unchanged flags (today's BUG-089 fix) leaves every key unchanged, so
   old entries would be served. The store keys a content hash of the solver source; P2
   adds the same hash + `USE_JAX_SOLVER` to the AD-cache key (one deliberate
   invalidation of the gitignored dev caches).
4. **Two mechanisms for one artifact** (`recession_init` lossy vs `policy_full` lossless).
5. **No fixed-point guard on cold-solution HITs** (only `ad_full` has the double-check).

## 2. Where the solve time goes (P−1 gate — measure before designing the payoff)

Known today (2026-08-24, dell, fixed solver, K=3 grid):

- Multiplier entry, per shock scenario, S=252: the 10 routed (patient) atoms take 58–107 s
  each in the measured-Q 'lagged' ATI (today's re-run logs); the 11 EGM (impatient) atoms
  at 241 knots are **not timed anywhere** — at K=1 pure EGM they dominated (the P1 probe's
  21-agent recession solve took ~2 h, driven by 735–845-sweep patient atoms; the impatient
  ones converge in ~100–300 sweeps at ~2–3 s/sweep on the K=3 grid, i.e. plausibly
  5–15 min each). Four shock scenarios run in forked workers; each also re-solves the
  S=6 base. Per-phase walls printed today: TM sims ~1–2 min, AD phases 10–16 min.
- Seed batteries: `--seed-offset 0,1,2` = three complete S5a runs → three identical cold
  solves.
- Welfare battery (hybrid, Baseline): 54 min; its cold solves are cached within the
  battery after the first cell; nothing arrives from 5a.
- Step 2 (TM-a estimation): the objective's per-candidate solves are not reusable; the
  final calibration's base-structure solutions are, and are re-solved by 5a/5b.

**P0 action:** add solve-wall accounting to `AggregateDemandEconomy.solve()` (per agent:
engine, iterations, wall; per call: total) printed like the `[step5-ati]` lines and
summed into the provenance sidecar, then read the shares off tonight's two re-runs and
one welfare battery. The payoff estimate in §5 is provisional until this lands.

## 3. Design — what already exists vs what actually changes

**Owner's framing (2026-08-24, correct):** the same household problems are solved twice,
in two programs, with slightly different methods; we want them solved once. Nearly all
the machinery below EXISTS (the welfare pipeline's `solution_cache/`: content-keyed
entries, wholesale pickles, atomic writes, a guarded cache with a one-iteration check).
The work is plumbing, in five small pieces:

1. the multiplier program reads the cache before solving and writes after — it never
   touches it today (one hook in `AggregateDemandEconomy.solve()`);
2. the welfare program's cohort workers go through that same hook — today they call
   HARK's per-agent solve directly and bypass everything;
3. the cache key must say "same problem AND same solver *code*": the existing key already
   carries the solver/tail flags (corrected reading, §1.3); it lacks a solver-source hash
   (and the JAX EGM kernel flag) — without it a solver edit at unchanged flags serves
   stale policies (today's BUG-089 change would have);
4. entries per agent instead of per 21-agent economy, so partial reuse works;
5. the one-sweep fixed-point check on cold-policy hits (today only the AD cache has it).

Everything after this paragraph is the specification of those five pieces.

**Unit of storage = one agent's converged AD-off policy** (`ConsumerSolution`, wholesale
pickle — the `policy_full` pattern; never the knot-extraction serializer).

**Key = SHA256 of** (a) the agent's primitives exactly as `_agent_params_dict` gathers
them (this already pins the shock structure: MrkvArray, IncShkDstn, per-state R/Γ/LivPrb,
grids, Cgrid, BoroCnstArt, DiscFac, CRRA, Splurge, T_age…) + `ADFunc` parameters
(elasticity, Cgrid — the AD-off policy still carries C-slices) + `num_experiment_periods`
/ `num_base_MrkvStates`; (b) the solver environment: the existing whitelist **plus**
`STEP5_ATI`, `STEP5_ATI_MIN_DISCFAC`, `PF_DECAY_EXTRAP`, `PF_DECAY_Q`, `PF_DECAY_DRIFT_TOL`,
`SLICE_INTERP`, `SOLVE_ACCEL`, `USE_JAX_SOLVER`, `STEP2_NAMG` (adding vars invalidates all
existing keys — a documented trap, accepted once, deliberately, at store introduction);
(c) a **solver-code content hash**: SHA256 of the source of `AggFiscalModel.py`'s solver
functions, `local_q_tail.py`, `powerlaw_decay.py`, `grid_sizing.py`, `hark_fti/
consumed_ati_markov.py`, `hark_fti/powerlaw_tail.py`, `hark_fti/consumed_block_core.py`,
and HARK's `interpolation.py`/`core.py` — so a solver change (today's) invalidates entries
without pinning commit SHAs (the existing convention "mid-session commits must not
invalidate" is kept: only solver source changes do). Provenance (SHAs, host, run_id) goes
in the sidecar, not the key.

**HIT guard (the safety net for whatever the key misses):** on load, apply ONE backward
sweep of the agent's own solver (`HARK.core.solve_one_cycle(agent, sol, None)`) and
require `distance(sweep(sol), sol) ≤ max(agent.tolerance, 1e-6)`; a stored policy that
is not a fixed point of *this* agent's operator (wrong calibration vintage, changed
convention, corrupted file) is rejected as a MISS with a loud line and a REUSE-ledger
event. Cost: one sweep (~1–3 s at S=252) per HIT — negligible against the 1–15-min solve
it replaces, and it is the same certificate the BUG-062 guard and the `ad_full`
double-check rest on. (Byte purity is preserved: the check's output is discarded; the
loaded object is installed as-is.)

**Install semantics = what a solve does:** `agent.solution = [sol]`; `agent.post_solve()`;
`agent.get_economy_data(eco)` (the `policy_full` pattern); `MrkvArray_prev` bookkeeping
(the BUG-064 `solve_if_changed` wiring) — one helper used by every entry so the two cannot
drift.

**Scope, phase 1:** cold AD-off solves only (from_solution is None). The AD-phase warm
re-solves depend on the belief `CFunc` and stay as they are; the AD-converged pair stays
in `ad_full` (its own guarded cache). Sharing AD-converged policies across the TM and MC
methods is a separate owner decision (it would couple the two methods' fixed points).

**API:** `solution_cache/policy_store.py` — `key_for(agent)`, `try_load(agent, eco)`,
`save(agent, sol)`, `solve_or_load(agent, eco, from_solution=None, solver=<callable>)`;
storage `solution_cache/policies/<parametrization>/<key>.pkl` + `.meta.json` (atomic
writes and orphan-tmp cleanup reused from `cache.py`); flags `HAFISCAL_POLICY_STORE`
(`1` opt-in in phase 1; default ON after the gates) and `HAFISCAL_POLICY_STORE_VERIFY`
(default `1`; `0` only for diagnostics); every HIT/MISS/SAVE/REJECT lands in the
provenance REUSE ledger (`record_reuse_event`) so a result file's sidecar says which
policies it loaded and from which producer run.

**Wiring (three call sites, one helper):** `AggregateDemandEconomy.solve()` (before the
NAMG/ATI/accel branches — a HIT skips them all), `parallel_solve._solve_worker` (the
welfare battery's cohort workers) and `welfare6_scenario._solve_agent_worker` (its
spawn-context twin). The Step-2 estimator's final solve at the installed calibration
publishes its base-structure policies through the same helper.

## 4. Phases and gates

| phase | work | gate |
|---|---|---|
| **P0 — profile** (½ day) | solve-wall accounting in `eco.solve()` + sidecar; read shares off the two running re-runs and one welfare battery | numbers in this doc's §5 |
| **P1 — the store + 5a** (1 day) | `policy_store.py`; key extension (whitelist + solver-code hash); HIT guard; the install helper; wiring in `eco.solve()`; tests: key sensitivity (each solver flag / a solver-source edit / a calibration digit flips the key), guard rejects a corrupted and a stale-solver entry, HIT install ≡ fresh solve (bitwise policy snapshot) | (a) byte-identity: S5a Reduced tables with store OFF vs ON-cold identical; (b) ON-warm (second run) tables byte-identical to (a); (c) `test_provenance` sees the REUSE events |
| **P2 — unify + cross-entry** (1 day) | wire the welfare workers to the store; retire `recession_init`'s lossy path and `policy_full` onto it (aliases kept one cycle); Step-2 final-solution publication; per-agent partial reuse for robustness variants (`only_agents`) | welfare battery: first cell loads 5a's policies (HIT lines), battery results byte-identical to the uncached battery; robustness variant re-solves only the changed group |
| **P3 — default-on + policy** (½ day + owner rulings) | default `HAFISCAL_POLICY_STORE=1`; ENV_FLAGS/README; cross-machine entries (m5/dell float differences: the guard tolerates them, but a HIT then reproduces the *producer's* bits — owner decides whether keys include the platform); optional: AD-converged sharing across methods | owner rulings on the two policy points; `test_locked_tables` untouched |

**Companion lever (P4, NOT immediate — corrected 2026-08-24 evening):**
`HAFISCAL_STEP5A_PARALLEL_SOLVE=auto` is inert under the multiplier entry's production
default: `step5a_parallel_solve._incompatible_flags_active()` falls back to the stock
`eco.solve()` whenever an ATI/NAMG/accel opt-in is active, because the fork worker runs
plain `solve_agent` only (the patient atoms would lose their 60–160 s ATI solves for
20-minute EGM solves). Making the lever real means giving the worker the SAME engine
ladder as the economy loop (store → NAMG → ATI → accel → EGM; factor the per-agent
ladder out of `AggregateDemandEconomy.solve()` into a function both call) and dropping
STEP5_ATI from the incompatibility list, then a byte-identity gate. Payoff: only the
*first* cold solve of a new calibration/world/scenario (the store makes it the only one),
so it ranks after P3.

## 5. Expected payoff (provisional — P0 replaces these with measurements)

Reuse matrix (rows = who solves; columns = who can load):

| producer → consumer | what is shared | today | with the store |
|---|---|---|---|
| 5a run → its own 4 shock workers | base structure S=6 (and the base-only warm seeds) | 4 solves | 1 |
| 5a seed 0 → seeds 1, 2 (`--seed-offset` battery) | every cold policy (seeds affect only simulation) | 3 solves | 1 |
| 5a → 5b welfare battery | base + recession-family cold policies (same primitives, now same solver) | separate solves | load |
| Step-2 final solve → 5a/5b | base-structure policies at the installed calibration | re-solved | load |
| certified run → robustness variant (one group changed) | the unchanged groups' policies | 21 solves | 7 |
| any run → the same run repeated (annotated build, UPDATES regeneration, cross-machine replication) | everything | full re-solve | load + guard |

Order of magnitude: a cold S=252 solve of the 21 types is tens of minutes per scenario on
the K=3 grid; the store turns every repeat into seconds plus the guard sweep. For the
S=3 multiplier batteries alone that is roughly two of three solve phases per world; for
the two-world program roughly half of all solve time now spent. It does not touch the
TM/MC simulation and AD-iteration walls (those are the other half of S5a and most of
5b) — the companion lever and the existing AD caches own those.

## 6. Risks and traps (each has a mitigation above)

- Stale HIT from an incomplete key → whitelist extension + solver-code hash + the
  one-sweep guard (belt, braces, and a tripwire).
- Lossy serialization (BUG-067: knot extraction dropped tails, 7.2e-3) → wholesale
  pickle only; pickles reference HAFiscal-local classes (`PowerLawDecayLinearInterp`,
  FTI `PowerLawTailLinearInterp`) — store the class module paths in the sidecar and
  reject on import failure (a MISS, never a crash).
- Concurrency (4 forked workers + parallel batteries) → the existing atomic-write +
  orphan-tmp discipline; first writer wins, later writers verify-and-skip.
- Disk: ~3 MB per agent-policy at S=252/241 knots → ~65 MB per scenario, a few hundred
  MB per world program; gitignored; a `prune` subcommand by age/producer.
- Determinism class: a run with HITs is "pure-config" only if the producer was; the
  sidecar records producer run_ids so provenance stays traceable.
- Byte-exactness of ON-cold vs OFF: only saves are added; gate (a) proves it.

## 7. What is deliberately NOT in this plan

- Sharing AD-converged policies between the TM multiplier engine and the MC welfare
  engine (method coupling — owner decision, §3 scope note).
- Cross-machine policy transport by default (P3 ruling).
- Replacing the welfare battery's presolve-capture cache (a sim-side artifact, unrelated).

## Execution log (2026-08-24)

- **P0/P1 (3a0a0657):** store + hooks + `[solve-wall]` accounting; **gate on ccarroll-m5**
  (`~/gate_p1_m5.out`, Reduced_Run multiplier entry): `Multiplier_candidate.tex`
  byte-identical store OFF / ON-cold / ON-warm; 24 HITs, 0 REJECTED, one-sweep moves
  3e-5…1e-4; economy cold solves 50–55 s → 2 s on hits.
- **P2 (248ab59c):** `recession_init` / `policy_full` layers no-op under the store; AD key
  carries the solver-source hash + `USE_JAX_SOLVER`. **Welfare gate on xubuntark**
  (`~/gate_p2_xub.out`, Reduced_Run battery, its own caches cleared per arm): `welfare6_`
  and `welfare4_candidate.tex` byte-identical across OFF / ON-cold / ON-warm; 51 HITs in
  the warm arm (33 at S=132, 18 at S=6), 0 REJECTED, worst one-sweep move 3.2e-4; battery
  wall 25.4 min (off) / 22.2 (cold, saves included) / **8.7 min (warm)**. The only files
  that differed were the timestamped provenance sidecars and the summary JSON's wall-clock
  fields.
- **P4 (0c66523e):** engine ladder in `parallel_solve._solve_worker` (`engine_ladder=True`
  from the Step-5a wrapper; `HAFISCAL_STEP5_ATI` off the wrapper's incompatible list;
  entries record `producer.engine`). ccarroll HS_Only harness: 12/12 outputs identical
  (pre/off/on). m5 Reduced_Run gate: first run was VACUOUS (worktree had not advanced —
  `rm -rf` of tracked figures blocked `pull --rebase`, `-q` hid it; memory trap 17) —
  re-run on f28d0fc8 with a HEAD guard (17:06): **PASS** — 16 pooled solves, 0 fallbacks;
  Reduced_Run tables byte-identical P_off / P_on / P_on+store; 16/16 per-agent cFunc
  probe pickles byte-identical; the pool did 55 worker-seconds in 41 s wall (3 cohorts,
  the 28-s ATI atom sets the floor — the 21-cohort Baseline economies are where the
  divisor-8 budget pays). `HAFISCAL_STEP5A_PARALLEL_SOLVE=auto` is now the multiplier
  entry's setdefault (owner default 8).
- **P3 (this commit):** `enabled()` default ON (`0/off/false/no` opts out); store dir
  default moved from per-checkout `solution_cache/policies/` to the per-user
  `~/.cache/hafiscal/policy_store` (owner default 1: per-machine, never transported);
  ENV_FLAGS / CLAUDE.md / module docstring updated; `test_flags` covers the defaults.
- **Cross-entry sharing (measured next, xubuntark):** the key excludes AgentCount/seeds,
  so a welfare battery loads a multiplier run's entries — including ATI-solved patient
  atoms the welfare path never produced itself. Entries now carry `producer.engine`; the
  planned measurement is a Reduced_Run welfare battery on a multiplier-populated store vs
  the store-off battery (cells vs the seed band).
- **Production numbers on the fixed solver (BUG-088/089) + shared K=3 grid:** default world
  1.258 / 1.258 / 1.027 (unchanged); as-corrected 1.249 / 1.258 / 1.015 (+0.001 on check and
  tax cut vs the 08-23 W-FIX). S=3 seed bands for both worlds: seeds 1,2 running through
  the dell store (`~/coldrun_2026-08/rerun_{default,ac}_fixed_K3_seed{1,2}.log`).
- **Production-scale evidence (dell, the seed batteries, 2026-08-24 16:17–17:51):** per
  21-agent S=252 economy solve, default world 1155–1425 s cold (accel 40–60 s per impatient
  atom, ATI 70–110 s per patient atom); as-corrected 2066–2441 s (its impatient atoms run
  plain EGM — the Newton-2D accelerator is an IMPROVEMENT excluded from the bug-fix-only
  world — at 110–150 s each). A store HIT replaces any of these with ~2 s
  (`store=10(25s)`). The two seeds of each world were launched concurrently and raced each
  other to the same entries, so each solved roughly half its agents cold (default: 27 and
  18 hits over 6 recession economies); a serial second run of the same calibration is
  ~21 × 2 s ≈ 40 s per economy instead of 20–40 min. Dell store after the batteries: 168
  entries, 553 MB (format 1; the format-2 default store at `~/.cache/hafiscal/policy_store`
  starts empty, so the first post-merge production run on each machine is cold once).
- **Multiplier seed bands are degenerate by construction:** the TM engine is distributional;
  `HAFISCAL_SEED_OFFSET` only shifts the HARK RNG seeds the MC simulation consumes. Default
  world: the three per-seed tables are byte-identical
  (`conclusions_private/artifacts_20260824_fixedsolver_bands/`).
- **P2b — format-2 welfare gate on xubuntark (83813a10, 17:06–17:59): PASS, EXACT.**
  `welfare6`/`welfare4` candidate tables byte-identical OFF / ON-cold / ON-warm and all 8
  welfare6 cells identical to 0.000e+00 in both store arms (the format-1 gate had the four
  AD cells 6e-14…3e-12 off on hits; carrying `_newton2d_cInterior` with the entry closed
  it). Walls: off 1495 s, cold 1337 s (12 saves + 37 intra-battery hits), warm 320 s
  (69 hits, 0 rejections) — 4.7× on the second run of the same calibration.
- **Seed batteries complete (18:12):** as-corrected seeds 1/2 = 1.249 / 1.258 / 1.015, byte-
  identical to seed 0 like the default world's (32 and 30 hits, 0 rejections). Both worlds'
  S=3 multiplier bands are degenerate by construction (TM engine); artifacts in
  `conclusions_private/artifacts_20260824_fixedsolver_bands/{default,as-corrected}/`.
- **Cross-entry measurement (xubuntark, 18:00–18:50): NO sharing — and the reason is a
  defect, BUG-090.** The multiplier entry on the welfare-populated store: 0 hits / 16 saves;
  for every (β, Markov structure) the keys differ in `agent/IncShkDstn` (every state but
  employed) + the inert `HAFISCAL_NEWTON2D_WARM_PAYLOAD` flag. The welfare drivers
  hard-coded the unemployed income as a point mass (the `off` / as-corrected process) in
  both worlds while `Simulate.py` and the estimator honor `HAFISCAL_PERM_DURING_UNEMP`
  (`on` in the default world) and the welfare SIMULATION applies ψ during unemployment:
  default-world welfare policies were solved without the risk they face (stored policies
  differ by up to 10 % at low m in unemployed states). Fixed at 895a5cbe (SST in both
  drivers + legacy toggle; store key drops the inert flag); as-corrected byte-identical by
  construction. Materiality + the first real cross-entry sharing test running on m5
  (`~/gate_bug090_m5.out`). Record: `BUGS_private/HAFiscal_BUG-090_*.md`.
- **BUG-090 materiality (m5, Reduced_Run, default world, 895a5cbe):** fixed vs pre-fix
  welfare cells: ui_rec −0.403 %, ui_rec_AD −0.450 %, check_rec_AD −0.177 %,
  taxcut_rec_AD −0.100 %, the rest ≤0.05 % (systematic; ≈ half the Baseline battery's
  cross-seed SE on the UI cells). The escape hatch reproduces xubuntark's genuine pre-fix
  cells to 6 decimals. Record: BUG-090.
- **First TRUE cross-entry sharing (m5, db961ef6, after the third legacy layer —
  `cached_eco_solve`'s knot extractor — was made a plain solve under the store):** the
  welfare battery on the multiplier-populated store: 87 hits (57 S=6 + 30 S=132), 3 saves,
  loading the pool-produced entries incl. the 4 ATI-solved patient atoms. Cells vs the
  store-off welfare battery: welfare6 ≤1.4e-5 abs (taxcut_rec_AD +1.1e-4, +0.009 %),
  `welfare6_candidate.tex` byte-identical, `welfare4_candidate.tex` third decimal moved —
  the ATI-vs-EGM residual, and a RUN-ORDER dependence (whichever entry solves first
  decides the engine of the patient atoms). → **P5:** the welfare spawn worker runs the
  same ladder (ATI router → accel → EGM; `try_solve_ati_markov` module-level; welfare6's
  `HAFISCAL_STEP5_ATI=1` setdefault becomes live). Gate on m5 (`gate_p5_m5.sh`): ATI_off vs
  FIX_off = the residual; ATI_store / ATI_wstore vs ATI_off must be EXACT; the multiplier
  entry on the welfare-populated store must reproduce F_pop2's table.
- **P5 gate, first pass (m5, 45ed0759, 19:09–19:15):** welfare→multiplier direction EXACT
  (the multiplier entry on the welfare-populated store — 15 S=132 + 3 S=6 hits, incl. the
  welfare workers' own ATI atoms — reproduced its fresh-store table byte for byte); the
  store-ON welfare arms ran (12 ROUTED ATI solves in the battery); the store-OFF welfare
  arm crashed in `serialize.extract_eco_solution` ("cFunc layout unexpected … got
  LinearInterpOnInterp1D"): with the store off the battery's legacy knot-extraction
  layers are live again and now meet ATI-solved policies from its own workers. Fix: the
  two lossy layers (`recession_init`, base-economy `cached_eco_solve`) are inactive under
  `HAFISCAL_STEP5_ATI=1` (wholesale layers unaffected). Second pass = `gate_p5b_m5.sh`.
  Note: the mechanical router edit (self→class statics) changed the solver-source hash, so
  every earlier entry missed by design — the hash guards exactly this.
- **P5b gate (m5, ee65a2fe, 19:25–19:33): PASS.** (i) ATI-ladder welfare (store OFF) vs
  EGM welfare: welfare6 cells within 1.4e-5 (ui_rec +0.001 %), the rest ≤3e-6 — the
  ATI-vs-EGM residual is now a fixed property of the pipeline, not of run order. (ii) The
  same battery on a welfare-populated store and on a multiplier-populated store: EXACT —
  every cell 0.000000, `welfare6`/`welfare4` candidate tables byte-identical to the
  store-off run; 87 hits / 3 saves on the multiplier-populated store (incl. the pool's 4
  ATI atoms). (iii) Multiplier entry: fresh store (two commits) and the welfare-populated
  store give byte-identical tables. Solve once, load anywhere, either order — the
  owner's 2026-08-24 charge is met at Reduced_Run scale in the default world.
- **Owner (19:45): "the welfare battery should NOT BE ALLOWED TO SOLVE AT ALL — why did
  it?"** Answer: 3 store MISSES, all in `recessionTaxCut_AD`, no guard rejection anywhere;
  cause = **BUG-091**: the welfare drivers put the payroll tax cut in every experiment
  period (10 quarters, blocks 2–21) while the paper, `TaxCutPeriods=8`, the simulation's
  delivery and the multiplier entry use 8 (blocks 2–17). Both worlds. Fix: one SST
  expression (`income_process_sst.taxcut_block_range` / `build_recession_taxcut_inc_shk_dstn`,
  `[2·nb, (2·TaxCutPeriods+2)·nb)`) used by the welfare drivers, `Simulate.py` and the
  delivery (byte-identical at 8); `HAFISCAL_WELFARE6_LEGACY_TAXCUT_BLOCKS=1` rebuilds the
  old process. **Strict mode:** `HAFISCAL_POLICY_STORE_REQUIRE=1` (welfare entry points'
  setdefault) — a store-eligible cold solve that misses RAISES with the household/key and
  the two possible causes; hooks in all three ladders. Gate `gate_bug091_m5.sh`: multiplier
  populates → welfare strict must finish with ZERO saves (both worlds); strict on an empty
  store must fail loudly; tax-cut cells before/after (materiality) in both worlds.
- **BUG-091 gate, default world (m5, b109c151, 19:51–20:01): PASS.** Welfare in strict mode
  on the multiplier-populated store: 90 hits, ZERO saves (never solved), cells and both
  tables identical to the store-off run; strict on an empty store fails at the first cold
  solve with the MISS RuntimeError; escape hatch reproduces the 10-quarter cells exactly;
  multiplier table unchanged by the SST expression. BUG-091 materiality: taxcut_norec
  +0.101 %, taxcut_rec +0.108 %, taxcut_rec_AD −0.665 %, all other cells exactly 0.
- **As-corrected arm DEADLOCKED (20:01–20:52):** the multiplier entry's fork pool returned
  an ATI-solved policy (hark_fti classes) and the parent — which never resolves the FTI
  path unless the default-world accelerator runs — failed to unpickle it
  (`ModuleNotFoundError: No module named 'hark_fti'`); a dead result channel hangs
  `Pool.map` (trap 12 class). Fix: `policy_store.ensure_fti_importable()` (best-effort
  `_hark_fti_path.ensure_hark_fti()`) at store import, before every store `pickle.load`,
  and in both pool parents before dispatch. As-corrected arms re-run as `gate_bug091b_m5.sh`.
- **BUG-091 materiality, as-corrected (m5, 5622922b, store OFF):** taxcut_norec +0.103 %,
  taxcut_rec +0.125 %, taxcut_rec_AD −0.676 %, all other cells exactly 0 — same pattern as
  the default world; the W-FIX welfare tax-cut column carries it. The as-corrected strict
  arm is on its third run (take 1: FTI-unpickle deadlock; take 2: GNU `timeout` absent on
  macOS — both harness defects, fixed; `gate_bug091c_m5.sh`).
- **BUG-091 gate, as-corrected, take 3 (m5, 5622922b, 21:06–21:11): PASS.** The multiplier
  entry's fork pool completed (each S=132 economy: 2 EGM-cold + 1 ATI worker, 107 worker-s
  in 62 s wall — no unpickle deadlock); the welfare battery in strict mode on that store:
  90 hits, ZERO saves, every cell and both tables byte-identical to the store-off run; the
  store holds only multiplier-produced entries (4 ATI + 8 EGM). **Both worlds: the welfare
  battery never solves; a miss is an error.** Open owner decisions: Baseline S=3 welfare
  re-battery (default world: BUG-090+091; as-corrected W-FIX: BUG-091 tax-cut column).
- **Baseline S=3 welfare re-battery (owner: "run it for both worlds", 21:20).** As-corrected
  world COMPLETE on m5 (793eb539; multiplier 55 min populating 89 entries; welfare seeds
  0/1/2 in 16 / 7.5 / 8 min, 630 / 546 / 546 hits, ZERO solves, zero misses — strict mode;
  seeds 1/2 reuse seed 0's AD fixed point per RECONCILED-004, hence fewer loads). C4
  internal band gate PASS (24/24). Cells: check_norec 0.9631, taxcut_norec 0.9896,
  check_rec 1.0137, ui_rec 1.8188, taxcut_rec 0.9919, check_rec_AD 1.3905, ui_rec_AD
  2.1970, taxcut_rec_AD 1.1513 (SE 0.01–0.71 %). Versus the 08-24 accert battery: every
  non-AD cell and seed 0's AD cells reproduce to 4–5 decimals (the store/ATI/strict
  changes moved nothing there); the tax-cut cells carry BUG-091 at Baseline scale —
  taxcut_norec +0.46 %, taxcut_rec +0.58 %, **taxcut_rec_AD −1.67 %** (1.1709 → 1.1513);
  seeds 1–2's other AD cells shifted 0.2–0.9 % because all three seeds now share m5's
  seed-0 AD fixed point (RECONCILED-004 convention; accert's seeds 1/2 ran on other
  machines with their own AD solves). Artifacts: `conclusions_private/
  artifacts_20260825_rebattery/as-corrected/`. Default world (dell) in progress.
- **dell, as-corrected multiplier pre-populate (21:33–22:38, concurrent with the default
  chain):** table 1.249 / 1.258 / 1.015 (= the wtH_ac re-run and m5) — the as-corrected
  entries are in dell's store, so the driver's later as-corrected step runs as all-hits.
- **Default world Baseline S=3 COMPLETE on dell (22:29–23:32; 651/651/650 hits, 0 solves,
  0 misses; 21 min per seed).** vs the 08-23 rerun, per seed: BUG-090 → ui_rec −0.20 %,
  ui_rec_AD −0.32 %, check_rec_AD −0.22 %; BUG-091 → taxcut_norec +0.47 %, taxcut_rec +0.58 %,
  taxcut_rec_AD −1.81 % (per-seed deltas within ±0.05 %). C4 gate FAIL on check_rec_AD seeds
  0/2 (0.77 %/0.71 % vs 0.5 %) — the identical failure of the 08-23 default rerun: under the
  hybrid engine each seed solves its own AD fixed point (seeds 1–2 hit seed 0's `ad_full` entry
  and the guard correctly rejected it, step 0.13), so default-world AD cells carry AD-path
  variance; the 0.5 % tolerance is miscalibrated for check_rec_AD there (owner call; not moved).
  Staged: CURRENT candidate ← seed 0; W-FIX welfare ← as-corrected seed 0; UPDATES.md rebuilt.
- **Baseline-scale store identity (dell, 00:07):** the as-corrected multiplier program run
  entirely from the store — 158 hits, 0 saves, 0 rejections, 36 min vs 65 min cold — produced
  a `Multiplier_candidate.tex` BYTE-IDENTICAL to the cold pre-populate run's; the
  default-world r2 table is byte-identical to the 16:12 re-run (pool default + store changed
  nothing). The store's production contract holds at Baseline scale in both worlds.
- **Cross-platform replication (as-corrected seed 2, m5 vs dell, 00:35):** every non-AD cell
  identical to 1e-13; AD cells −0.23 % / −0.41 % / −0.06 % (check / UI / tax cut) — dell's seed 2
  had no seed-0 AD entry to reuse (seed 0 ran on m5) and solved its own AD path, the
  RECONCILED-004 convention effect, not a platform effect. dell's copy kept as
  `Tables/Baseline_ac_r2_seed2_dell/`; the main-checkout S=3 set stays one-platform (m5).
  Chain finished 00:34 (dell seed 2: 651 hits, 0 solves). Overnight arc COMPLETE.
- **P6 — AD-equilibrium sharing (owner ruling 2026-08-25 ~01:00, "go ahead, implement it
  tonight"; 6e872ec1):** the welfare battery must not solve the AD fixed point either.
  `solution_cache/equilibrium_store.py`: Step 5a publishes, after its AD-TM block, the pair
  the TM loop leaves on the economy — the trained belief `CFunc` (Phase 1 trains one belief
  over the macro chain; Phase 2 only evaluates durations on it), the AD-on elasticity, and
  every household's policy solved at that belief; `run_recession_AD` installs it
  (`store_ADsolution(shock_type)` snapshot, so the unchanged post-loop `restore_ADsolution`
  works) and SKIPS its MC AD loop; strict mode raises on a missing equilibrium. Key = per-
  agent policy-store primitives for the scenario + AD inputs (demand elasticity, horizon;
  the ACTIVE elasticity is solve state, excluded) + AD/TM env + solver-source hash. Flag
  `HAFISCAL_AD_EQUILIBRIUM_SHARE` (opt-in tonight; default flip = owner). Gate
  `gate_eq_m5.sh` (Reduced_Run, both worlds): 5a publishes 4 equilibria; welfare with
  SHARE=1 must skip all 4 AD loops with 0 policy solves; W_eq vs W_ref cells = the TM-vs-MC
  AD fixed-point gap; SHARE=1 on a store without equilibria must fail loudly. Then Baseline
  S=3 in both worlds on the shared equilibrium (dell default, m5 as-corrected).
- **P6 gate 1 (m5 05:31–05:43) — publish PASS, consume FAIL, strict PASS:** 5a published 4
  equilibria per world (12 policies + 4 equilibria in each store); the welfare battery MISSED
  all 4 in both worlds (strict mode failed loudly, as it must, but on the wrong occasion). The
  bare key could not say why, so `equilibrium_store.explain_miss()` was added (nearest stored
  entry for the scenario, differing leaves grouped by field; consumer inputs dropped under
  `<store>/equilibrium/_misses/`). A one-cell probe (recessionCheck_AD, as-corrected store)
  found the SOLE differing leaf: `env.HAFISCAL_AD_CONVERGENCE_TOL` = `""` (welfare) vs `1e-2`
  (5a: `AggFiscalMAIN_reduced.py:152` setdefault, STANDARD tier). All 3 agents' primitives,
  the scenario, the world and the solver source matched exactly.
  **Design fix (7c6089b9): key = the MODEL; the producer's conventions are provenance.** The
  consumer never iterates, so the AD tolerance / iteration cap / TM discretisation are not
  inputs it could match — it wants THE spending program's equilibrium. They now ride in the
  meta as `conventions` (env + the effective values 5a passes: tolerance, cap, mCount, neutral
  measure), print on every HIT and in the welfare "AD loop SKIPPED" line, and a re-publish
  with different conventions REPLACES the entry (same: kept; the spending program is the
  authority). Key = agents' policy-store primitives (already carrying the solver env) + AD
  inputs + `HAFISCAL_WORLD` + solver source. Fact to carry into the report: under sharing the
  AD cells sit on 5a's equilibrium converged at 5a's tolerance 1e-2 (the welfare loop used
  Parameters' 1e-3 at Baseline); tightening is a Step-5a decision. Gate 2 launched 05:50 on
  7c6089b9 (`~/gate_eq_m5_r2.out`).
- **P6 gate 2 (m5 05:50–06:01, 7c6089b9) — PASS, both worlds.** Per world: 5a published 4
  equilibria (13/12 policy saves, fresh store); W_ref (SHARE=0) 90 policy hits, 4 own AD loops;
  **W_eq (SHARE=1): 4 equilibrium HITs, all 4 AD loops SKIPPED, 78 policy hits, 0 saves, 0
  misses, 4 tables** (37 s vs W_ref 62 s; the 12 fewer hits are the AD cells' scenario policies
  no longer loaded — the equilibrium carries them); W_eq_empty (SHARE=1, store copy without
  `equilibrium/`): every AD cell fails loudly with the explainer ("no stored equilibrium for
  scenario 'recessionCheck' under …_noeq/equilibrium (0 entries for other scenarios)"). HIT
  provenance printed: `AD tol=0.01, max iters=5, engine=tm, saved by ccarroll-m5`. Non-AD
  cells W_eq ≡ W_ref to the last digit (untouched path). **AD cells = the TM-vs-MC AD
  fixed-point gap at Reduced_Run** (5 iters / tol 1e-2 / 5000 agents — loose by design):
  default check_rec_AD 1.4672→1.4177 (−3.37 %), ui_rec_AD 2.3681→2.4054 (+1.57 %),
  taxcut_rec_AD 1.1747→1.1702 (−0.39 %); as-corrected +0.43 % / −0.61 % / −1.02 %. Baseline
  decides. Launched 06:01: `rebattery_eq_dell.sh 7c6089b9` (default, dell main checkout,
  `Tables/Baseline_eq_seed{0,1,2}`) and `rebattery_eq_m5.sh 7c6089b9` (as-corrected, m5
  worktree, `Tables/Baseline_ac_eq_seed{0,1,2}`); harvest via `harvest_rebattery_eq.sh`
  (band gate, SE table, tex band, artifact set `artifacts_20260825_rebattery_eq/`, shift vs
  the r2 own-AD-loop battery). Known nit: the entry meta's `hafiscal_sha` reads `unknown`
  from the m5 worktree (`keys._hafiscal_root` looks for a `.git` DIRECTORY; a worktree's
  `.git` is a file); cosmetic, fix after the batteries.
- **P6 Baseline, as-corrected (m5, 06:01–06:58, 57 min end-to-end):** 5a from the store
  (166 hits, 0 solves, 40 min) published 4 equilibria (`AD tol=0.01, max iters=15, engine=tm`)
  and its table stayed BYTE-IDENTICAL to r2 (1.249/1.258/1.015). Welfare seeds 0/1/2: 5.7 /
  5.5 / 5.5 min each (16 / 7.5 / 8 last night), 630 policy hits, 0 saves, 0 misses, 4
  equilibrium HITs, all 4 AD loops SKIPPED per seed. **C4 PASS 24/24.** Non-AD cells ≡ r2 to
  the last digit (shift +0.000 %, per seed). AD cells = the TM-vs-MC AD fixed-point gap at
  Baseline: check_rec_AD 1.3905 → **1.4038 (+0.96 %)**, ui_rec_AD 2.1970 → **2.1859 (−0.50 %)**,
  taxcut_rec_AD 1.1513 → **1.1461 (−0.45 %)**; SEs unchanged (0.17 / 0.42 / 0.06 %). At two
  decimals the W-FIX welfare6 AD row goes 1.39 / 2.21 / 1.15 → 1.41 / 2.20 / 1.15. The
  welfare4 table's AD-consumption row `C(Rec, AD, policy)` moves more: 2.742 / 4.288 / 2.520 →
  2.834 / 4.301 / 2.526 (+3.4 % / +0.3 % / +0.2 %) — the TM equilibrium's consumption path
  differs from the MC loop's most for the check. Artifacts:
  `conclusions_private/artifacts_20260825_rebattery_eq/as-corrected/`.
- **P6 Baseline, default (dell) — early read, seed 0 (07:00):** non-AD cells ≡ r2; AD cells
  check_rec_AD 1.3860 → 1.3130 (**−5.27 %**), ui_rec_AD 2.1312 → 2.1010 (−1.41 %), taxcut_rec_AD
  1.1408 → 1.1319 (−0.79 %) — five times the as-corrected gap. Not a stale-feed artefact: the
  hybrid bundle's `HAFISCAL_REPLAY_CRATIO_PREV` is read only inside the (skipped) AD loop
  (`jax_mc_replay_ad.py:455`); the measurement stage is the same HARK MC under both engines.
  **Discriminator (m5, Reduced_Run, default world, 07:03):** welfare with the `hark` engine's own
  MC AD loop vs the gate-2 arms — HARK loop vs hybrid loop: check +0.87 % / UI +1.38 % / taxcut
  +0.97 % (the known ~1 % hybrid residual); **HARK loop vs TM equilibrium: check +4.39 % / UI
  −0.19 % / taxcut +1.37 %.** Both MC engines agree with each other; the default-world TM
  equilibrium is the odd one out, while in the as-corrected world TM and the HARK loop agree
  within 0.4 % (Reduced_Run) / 1 % (Baseline). The worlds differ economically only in
  `HAFISCAL_PERM_DURING_UNEMP` (on / off) plus the `HAFISCAL_T_AGE=200` cap (as-corrected).
  Mechanism test launched 07:06 on m5 (`mech_eq_m5.sh`, `~/mech_eq_m5.out`): default world with
  (V1) PERM_DURING_UNEMP=off, (V2) T_AGE=200 — each: 5a publishes, HARK loop vs TM equilibrium.
  Whichever flip collapses the gap names the mechanism; if neither, the gap is elsewhere in the
  default world's TM AD path.
  **V1 (07:14): PERM_DURING_UNEMP is NOT it** — HARK loop vs TM with the income convention
  flipped: check +4.23 % / UI −0.31 % / taxcut +1.41 % (unchanged).
  **V2 (07:19): the AGE CAP is the mechanism** — default world + `HAFISCAL_T_AGE=200`: HARK loop
  vs TM: check **−0.33 %** / UI +0.90 % / taxcut +1.03 %, i.e. the ≤1 % agreement of the
  as-corrected world. In the uncapped (perpetual-youth) world the TM AD equilibrium disagrees
  with both MC engines by ~4–5 % on the check's AD welfare (Reduced_Run +4.4 %, Baseline seed 0
  −5.3 % on the cell); under a cap they agree. The uncapped TM path (Doob π_Q baseline +
  `_effective_LivPrb(·, None)` propagation) is the default world's production path for the
  multiplier table too. Filed as **BUG-092** (OPEN; candidate mechanism: the uncapped pLvl
  cross-section — the known +3 % var(log pLvl) MC-vs-TM-a drift, which the check's lump-sum
  AD welfare is the most sensitive cell to; NOT adjudicated tonight).
- **P6 Baseline, default (dell, 06:01–07:20):** 5a from the store (165 hits, 0 solves, 43 min)
  published 4 equilibria; table BYTE-IDENTICAL to r2 (1.258/1.258/1.027). Seeds 11.8 / 12.0 /
  11.7 min (were 21 / 21 / 20.5), 630 / 629 / 629 policy hits, 0 saves, 0 misses, 4 equilibrium
  HITs + 4 AD loops SKIPPED per seed. C4 FAIL 22/24 on check_rec_AD seeds 0 & 2 (0.66 / 0.74 %
  vs 0.5 %) — the same two cells as the two previous default batteries, now on a COMMON
  equilibrium: that scatter is measurement variance of the uncapped world (SE 0.41 % vs 0.43 %
  own-loop; as-corrected 0.17 %), NOT AD-path variance (the earlier explanation in the morning
  report §2 and the RECONCILED-004 amendment was corrected). UI / tax-cut AD SEs did tighten
  (0.81 → 0.58 %, 0.13 → 0.08 %). AD cells vs r2 (S=3 means): check_rec_AD 1.3754 → **1.3044
  (−5.16 %)**, ui_rec_AD 2.1043 → 2.1156 (+0.54 %), taxcut_rec_AD 1.1386 → 1.1300 (−0.75 %);
  CURRENT welfare6 AD row at two decimals 1.39 / 2.10 / 1.14 → 1.31 / 2.10 / 1.13. NOTHING
  staged from the eq batteries (CURRENT / W-FIX stay on r2 pending the owner's rulings).
  Artifacts: `conclusions_private/artifacts_20260825_rebattery_eq/default/`. After the
  batteries: `keys._hafiscal_root` fixed (`.git` file in worktrees → `os.path.exists`).
  **Owner decisions:** SHARE default flip (as-corrected safe; default = adopt the TM equilibrium
  while BUG-092 is open), 5a's AD tolerance, BUG-092's arbiter (and whether the default world
  should carry an age cap, the setting under which the two engines agree).
- **BUG-092 localization (owner: "localize BUG-092 with the two Reduced_Run TM variants",
  09:30):** knobs 592274cd — `HAFISCAL_TM_Q_METHOD` (force doob/cohort/bst) and
  `HAFISCAL_TM_PROP_CAP_T_AGE` (cap only in `propagate_experiment_tm_a`'s mortality share +
  `_propagate_state_fracs`). Reading the TM's check delivery first: the check goes through
  `_compute_check_buckets` — 50 pLvl-quantile buckets from the ANALYTICAL pLvl model
  (`compute_pLvl_distribution`: lognormal mixture over a T_age-dependent age chain) with one
  TM per bucket — while the MC delivers `CheckStimLvl·phase_out/pLvl` per agent: a check-only,
  cap-dependent seam on its own. Batteries launched 09:42: m5 `bug092_variants_m5.sh` (VA =
  T_AGE=200 + Q_METHOD=doob; VB = uncapped + PROP_CAP_T_AGE=200; each 5a-publish → HARK loop vs
  TM equilibrium on the AD cells); dell `bug092_testC_dell.sh` (Test C: multiplier program under
  BOTH engines, `HAFISCAL_MULTIPLIER_ENGINE=tm|mc`, uncapped and capped — the NO-AD check
  response TM vs MC, plus the MC engine's N-aware pLvl-moment drift diagnostic).
  **VA (09:48): the Doob π_Q baseline is NOT the site** — capped world + `TM_Q_METHOD=doob`: TM
  equilibrium vs HARK loop check −0.17 % / UI +1.01 % / taxcut +1.11 % (V2's cohort baseline:
  −0.33 / +0.90 / +1.03 %); the two constructions also give the same multipliers (1.376/1.427/
  1.122 vs 1.378/1.428/1.123). **Test C's first attempt was INVALID:** `HAFISCAL_MULTIPLIER_ENGINE=mc`
  alone did not switch the engine on a direct `AggFiscalMAIN_reduced.py` invocation (its
  `Run_Dict` reads `HAFISCAL_SIM_METHOD` before EstimParameters' setdefault runs) — the "mc"
  table was byte-identical to the TM one; redone as `bug092_testC2_dell.sh` with
  `HAFISCAL_SIM_METHOD=MC` explicit (chained after the TM arms). Latent-defect note: verify
  whether `reproduce.sh --multiplier-engine mc` suffers the same (it may export SIM_METHOD itself).
  (Checked: `reproduce.sh mc` routes to `reproduce_computed_mc_only.sh`, which exports
  `HAFISCAL_SIM_METHOD=MC` — the gap is only for direct invocation; small fix pending.)
  **VB (09:53): the propagation's mortality share is NOT the site** — uncapped +
  `PROP_CAP_T_AGE=200`: TM vs HARK loop check +4.48 % (unchanged from +4.39 %), UI −0.19 %, taxcut
  +1.37 %; the check multiplier moved only +0.4 %. Both requested variants exonerate their seams.
  **Probe `probe_plvl_grid.py` (09:58): the analytical pLvl grid coarseness is NOT the site** —
  uncapped the 200-point log-p grid spans [−3.5, 21.2] (dp 0.124; 3 points in the phase-out
  band) yet reproduces the 20000-point reference to 0.03 % on E[check level] and 0.01 % on
  E[check/p]; the 50 buckets' aggregates agree to ≤0.03 %.
  **Test C2 (09:55): the MC engine's pLvl DRIFT GATE HARD-FAILS in the uncapped world** —
  `[drift agent_1] var log(p) drift = −0.0251 (rel) outside N-aware band [−0.0007, +0.1467]
  (N=2635)`; agent_0 −0.0368. The MC cross-section is 2.5–3.7 % UNDER-dispersed relative to the
  TM-analytical ergodic. Redone as Test C3 with `HAFISCAL_DRIFT_HARD_FAIL=0` to get the MC
  multipliers + drift lines uncapped AND capped. Working hypothesis now: the MC panels are seeded
  by a finite-N stratified inverse-CDF sample of the analytical mixture, which truncates the fat
  age/pLvl tails that only exist under perpetual youth; the check (lump sum, ∝ 1/p) is the cell
  exposed to that.
  **Probe, sampler arm (10:02) — LOCALIZED to E[p] in the uncapped world.** Uncapped analytical
  ergodic E[p] (p in $1000/quarter): dropout 8.8, HS 43.4, college 74.8 (≈ $300k/yr; capped 25.6);
  mass above the phase-out end ($150k/yr): college 29 % (17 % capped), HS 18 % (7.5 %). The MC init
  sampler at the agents' N reproduces E[check/p] (−0.1 %) and var log p (−0.4 %) but its realized
  E[p] is 11.5 % (HS, N=2635) / 18.5 % (college, N=1900) BELOW the analytical mean — a heavy-tail
  sample mean (N=100 000 still −5 / −9 %; max sampled p 325 758). Capped: all within 0.1 %.
  Mechanism: TM's check AD response = 1 + ΔC_level/C_base_level with C_base ∝ analytical E[p];
  MC's uses its realized panel mean; population-weighted TM C_base ≈ 1.18× MC's → the check's
  Cratio response ~15 % smaller in TM × the check cell's AD share (~28 %) ≈ −4.2 % (observed
  −4.4 %). UI and tax cut are ∝ p → E[p]-free → no gap. Not a coding defect in either engine: the
  uncapped world's ergodic E[p] is dominated by centuries-old households (a consequence of the
  2026-07-27 EPOCH cap removal); the TM computes it faithfully, finite-N MC cannot realize it.
  Prediction for Test C3: uncapped no-AD check multiplier (ΔC/cost, levels) TM ≈ MC; AD check
  multiplier TM < MC; capped both agree.
  **Test C2, capped MC engine (10:04, drift gate passes on all 3 types):** no-AD 0.953 / 1.007 /
  0.947 vs TM 0.958 / 1.009 / 0.947 (check −0.5 %); AD 1.392 / 1.474 / 1.136 vs TM 1.378 / 1.428 /
  1.123 (+1.0 / +3.2 / +1.2 %, the loose 5-iteration Reduced_Run AD loops' residual).
  **Test C3, uncapped MC engine (10:13): the multiplier prediction FAILED** — no-AD check 0.958 vs
  TM 0.971 (−1.3 %); AD check **1.399 vs 1.395 (+0.3 %)**; UI 1.456 vs 1.422; taxcut 1.144 vs 1.121.
  Self-consistent engines agree on the multiplier; only what SHARING hands across engines (the
  belief) disagrees. Direct measurement of the converged objects: uncapped base AggCons TM/MC
  1.160 (income 1.174); peak |Cratio−1| TM/MC recession 0.74 / check 0.74 / UI 0.60; check ΔC in
  levels 0.98. Capped: base 0.95; peaks 0.94 / 1.20 / 0.93. `mill_rule` (AggFiscalModel.py:2585)
  applies the BELIEF to the realized Cratio to set next period's AD factor, so the TM belief
  installed in the welfare MC world understates the AD boost. Check-specific welfare sensitivity
  and the multiplier immunity are recorded as observed-not-derived (open accounting item).
  Owner clarification given: no spending number changed; sharing exposed a pre-existing
  engine disagreement in the uncapped world; the cap was dropped in BOTH engines (MC
  `T_age=None`, Parameters.py:351/644).
  **Test C final (10:23), check column (no-AD / AD):** uncapped TM 0.971 / 1.395, MC 0.958 /
  1.399; capped TM 0.958 / 1.378, MC 0.953 / 1.392. Owner's proposed reading ("TM ignores the
  pLvl distribution ⇒ misestimates the check") answered: the TM carries an analytical pLvl
  distribution for the check (50 buckets; probe: moments to 0.03 %) and the no-AD check
  multipliers agree within 1.3 %; the disagreement is the aggregate LEVEL / Cratio scale (the
  tail), which travels only through the shared belief. **Entry-point fix (direct
  `HAFISCAL_MULTIPLIER_ENGINE=mc`):** `AggFiscalMAIN_reduced.py` now resolves the METHOD axis
  itself when `HAFISCAL_SIM_METHOD` is unset (prints `[method-axis] …`); Smoke_Test of the
  direct mc call ran the MC engine (drift lines present).
  **Owner's large-N test (10:45–):** sampler-limit E[p] shortfall (college) −18.3 % (N=2k) →
  −11.9 % (20k) → −7.6 % (200k) → −4.7 % (2M) → −2.8 % (20M): converges at ~N^(−0.2), so no
  feasible panel realizes the uncapped level (Baseline N ≈ 3.8k college ⇒ ≈ −16 %). Full MC
  engine at 10× / 40× agents launched 10:50 (`bug092_largeN_dell.sh`, `largeN_dell.out`; ~1.5 h /
  ~6 h) — base level + Cratio peaks vs TM. Proposal recorded in BUG-092: install 5a's realized
  per-duration `Cratio_hist` as a PRESCRIBED AD path in `mill_rule` so the welfare panel never
  aggregates (the faithful form of the ruling; not yet built).
  **10× MC engine (11:01, 11 min):** base AggCons TM/MC **1.029** (1×: 1.160) — the LEVEL gap is
  finite-N and closes fast (the warm-up shifts the panel's bulk up ~0.5 % in log p; drift lines
  all within bands); multipliers 0.958 / 1.004 / 0.961 and 1.390 / 1.394 / 1.139. **Cratio
  comparison WITHDRAWN:** the engines' `Cratio_hist` objects are not comparable — TM records
  its belief/state path (exactly 1.0 outside the recession period), MC the realized
  AggCons/base ratio (slow post-recession recovery); the 10× "peaks" were dominated by that
  and by single-realization noise at the 1e-2 loop tolerance. Owner's "can't we just correct
  the mean?": YES — under the p ⊥ aNrm assumption already used at the seed, the missing tail
  is a known level; but the 10× result says the cheapest correction may be N itself. Decisive
  test launched 11:07 on m5 (`bug092_w10x_m5.sh`): welfare arms at 10× agents
  (`--agent-count-total 50000`), own HARK loop vs the TM equilibrium — if the +4.4 % gap on
  check_rec_AD shrinks toward the capped ~0.3 %, finite-N level is confirmed as the cause and
  "more agents / analytical-E[p] aggregation" is the fix. 40× multiplier run continues on dell.
  Artifacts (default):
  `conclusions_private/artifacts_20260825_rebattery_eq/as-corrected/` (per-seed tables,
  summaries, sidecars, band.gate, SE table, `shift_vs_r2.txt`, m5 logs).
  **Session crash 11:12 (recorded 12:10 by the successor session).** The 40× MC arm OOM-killed
  one duration-fork child (13 python processes at 7–12 GB; 60 GB + 8 GB swap gone) and systemd's
  `OOMPolicy=stop` stopped the whole tmux pane scope — the Claude session with it — 30 s after
  the m5 10× welfare arms finished, so their result was never read. Fixes: `~/.config/systemd/
  user.conf` `DefaultOOMPolicy=continue` (live on the pane scope), heavy runs now go through
  `systemd-run --user -p MemoryMax=…` units (memory `feedback_compute_in_own_systemd_unit`).
  **m5 10× welfare result:** sharing gap on `check_rec_AD` 4.39 → 3.54 % (We 1.4286 / Wh 1.4792);
  own-loop cell N-invariant (−0.05 %); the panel's level closed −13.8 → −5.9 %. Reading: the
  level is at most half the gap; the rest is the belief/realization seam → the prescribed-AD-path
  seam (BUG-092 proposal) is the fix to build, not the mean correction alone. 40× replaced by a
  20× rerun (`HAFISCAL_DUR_WORKERS=1`, unit `bug092-mcN20x`, 11:58). Full table: BUG-092 "Results".
  **20× done 12:08 (9 min under the 50 G cap, peak ~32 GB): TM/MC level 1.044** — not monotone vs
  10× (1.029); single-seed level noise ±1–2 %. The large-N arm is closed: the level is finite-N
  and closes to a few %, and that is not where most of the welfare gap is.
  **12:40 CORRECTION of the 12:10 reading:** the "belief/realization seam" does not exist — every
  belief either engine trains has slope 0 (`CRule(Cratio_t, 0.0)`; verified on the 4 stored
  Reduced_Run equilibria, 0/17 424 nonzero), so `mill_rule`'s `CratioNext` is the intercept whatever
  the panel aggregates: **under sharing the installed equilibrium already IS a prescribed AD path**.
  Built the tripwire instead (`equilibrium_store.py`: slopes verified on every HIT — REJECTED /
  error under REQUIRE — prescribed path printed + recorded on SAVE/HIT; test added; smoke = Baseline
  seed 0 SHARE=1 on dell, `w6-tripwire-smoke` unit). Welfare panel level re-measured: 1× −11.1 %,
  10× −5.9 %. The gap = TM fixed point vs MC-loop fixed point measured on the same panel; a faithful
  mean correction = population-weighted tail strata in the SAMPLER (or the age cap). BUG-092 "Reading
  — CORRECTED 12:40".
  **12:45 BUG-093 filed** while extracting the prescribed paths from dell's four Baseline default
  equilibria: they prescribe recession Cratio 1.030–1.044 (ADF > 1 in the recession). Root symptom:
  the Baseline-uncapped TM's no-AD experiment consumption never returns to base (+2.6…3.3 % at
  t=30, income at 0.9997) — TM-internal, Baseline-only (Reduced_Run TM and the Baseline MC loop
  return to 1.000). Plan in the BUG file; owner to prioritize vs the weighted sampler / age cap.
  **13:25 BUG-093 localized by the null-experiment probe** (`bug093_null_experiment_probe.py`): the
  TM's experiments start from the Doob π_Q, base + propagation use the plain Q-kernel; 31 % apart at
  the most patient college atom. With `HAFISCAL_TM_Q_METHOD=bst` the null experiment is exact and the
  Baseline default-world recession path is 0.9893 → 0.9997 (was 1.026 → 1.026). Owner decision on the
  default construction, then 5a + welfare re-runs. BUG-093 "Plan".
  **14:40 BUG-093 FIXED (B + C).** `HAFISCAL_TM_Q_METHOD` selects ONE construction for base/start/kernel;
  `doob` (default) = Fix 4 π_Q + p-weighted survival step; `bst` = plain. Null 1.0000 under both.
  5a + welfare re-runs under both arms launched (units `bug093-rerun-q{doob,bst}`); the equilibria
  the welfare battery installs will now prescribe recession Cratio ≈ 0.99 (ADF < 1). Owner to pick
  the default world's arm from the tables.

  **22:30 OWNER RULING — sharing is the DEFAULT (IMPROVEMENT).** `HAFISCAL_AD_EQUILIBRIUM_SHARE`
  enters `config/catalog.py` as `ad_equilibrium_share` (canonical `1`, paper `0`): on in the `default`
  world, off in `as-corrected` unless explicit. Applied via `EstimParameters._WORLD_APPLY`; the battery
  child (`welfare6_scenario.py`) and parent (`run_welfare6_parallel.py`) resolve the weighted-tail
  default from the same value. Landed after the 22:01 candidate battery was cut (no mid-battery edits);
  see the session record's rulings 9–10 and `docs/ENV_FLAGS.md`.
