# BUG-084 onset ∧ support: test on battery-landing, implement if green

**Authorization (owner, 2026-08-21 ~15:25):** "make a plan to test BUG-084's onset ∧
support rule when the batteries land, and then if the tests are successful to implement
it." Supersedes deferred-log #20's "re-surface, don't implement": on the trigger this plan
EXECUTES. Ruling of record: `conclusions_private/2026-08-21_dist-top-onset-rule-ruling.md`.

**Trigger:** monitor b6tuv8820 reports dellb (ADElas multipliers) AND crra3 (G5 welfare)
done. Phase 0 (pure dev, no compute contention) starts immediately.

## D1 — the rule, formalized (design step, Phase 0 output)

For each estimated atom i (per education group, per ρ):
  a*_i = min( kernel_onset_i(τ),  support_i(ε) )
- kernel_onset_i(τ): the mortality-inclusive one-EGM-step asymmetry-flattening onset
  (the ruling doc's diagnostic; cull L_eff, discount β·L_raw).
- support_i(ε): the atom's wealth-weighted (1−ε) ergodic quantile on the covering grid —
  REUSE `adaptive_grid_tm.per_atom_dist_aGrid_max` machinery.
- Rationale for the min: an atom whose support ends below its kernel-onset never visits
  the region where its kernel misbehaves (ρ=3 dropout/HS tops); an atom whose support
  extends beyond its onset is carried by the tail state, whose validity needs the top
  ≥ the onset (cap-class atoms).
Required top (estimation surface, tail state ON) = max_i a*_i, plus margin; defaults
τ = 0.01, ε = 1e-4 (report sensitivity at τ ∈ {0.005, 0.02}). Production 1300 stands
unless the tests themselves demand otherwise (they should ratify it with margin —
predicted max_i a*_i ≈ 700-class at ρ=2).

## Phases, arms, gates (cascade: cheapest first; HALT on any gate failure → report, no implementation)

**Phase 0 — dev, now (dell, no battery contention).** Build the staging module
`Code/HA-Models/onset_dist_top.py` (promotion of the ruling doc's embedded script + the
support intersection + `required_top()` API) + unit tests: L_eff closed form == 0.991254;
caps == `gic_capped_beta` at ρ ∈ {2,3}; α via `per_atom_alpha.kesten_alpha` (T_age-split
call); onset values reproduce the ruling doc's table (tolerance: scan-grid resolution).
Also dev (NOT yet installed): the `production_dist_aGrid_max` fix — β=2.0 probe +
REFUSE-at-covering-ceiling — behind a branch that Phase 4 lands. Nothing on the run path
changes in Phase 0. Cost: ~1 h dev, minutes of compute.

**Phase 1 — the ladder (dell, on trigger; ~1 h).** ρ=2 College (binding group), 4 cold
COBYQA starts per arm, tail state ON (estimation default), everything else = certified
stack; arms differ in ONE thing (dist top):
- A1 top=2900 (deep reference)
- A2 top=800 (rule-permitted: above predicted max_i a*_i)
- A3 top=300 (falsification arm: BELOW the worst real-atom onset — the rule predicts
  degradation here; if A3 also agrees, the rule is vacuous-conservative at ρ=2 — record,
  not a failure)
- Reference = the canonical 1300 battery (exists, 4/4).
GATE G1: A1 and A2 agree with the 1300 reference in (β,∇) within the reference battery's
cross-start scatter; recorded moments within the standing bands. G1 failure ⟹ HALT.

**Phase 2 — cross-ρ spot (dell, after Phase 1; ~25 min).** ρ=3 College at top=2900, 4
cold starts vs today's G3 result at 1300 (β 0.9869/∇ 0.0266). GATE G2: agreement within
cross-start scatter (the freshest validation: ρ=3's top atom has 2.96e-3 mass above 1300,
all carried by the tail state).

**Phase 3 — rule computation + verdict (~15 min).** `required_top()` for all atoms, both
ρ, with τ/ε sensitivity; verify predictions vs Phase-1/2 outcomes (A3 degradation
direction; A1/A2 flatness). Compose the verdict table.

**Phase 4 — implementation (only if G1 ∧ G2 green).** The ruling doc's 4-step spec:
(1) install `onset_dist_top.py` + tests; (2) land the `production_dist_aGrid_max`
refuse-at-ceiling + β=2.0 probe fix; (3) doctrine text: CLAUDE.md dist_aGrid_max
instruction + ENV_FLAGS `HAFISCAL_TM_AMAX` entry → onset ∧ support (+ the connectivity
addendum conditions: append-never-redistribute, Δlog < log(ψmax/ψmin),
`min_aCount_for_mixing`, mixing diagnostic at any new (top,count)); (4) BUG-084 dossier +
index → FIXED-CLOSED citing this plan's verdict. No numeric change: 1300 stays in every
configuration.

**Phase 5 — report** (verdict table, gates, sensitivity, what changed where) + memory +
deferred-log #20 resolution.

## Bookkeeping
- Arms run in the dell main checkout is FORBIDDEN (canonical Results/) — use a fresh
  worktree `~/coldrun_2026-08/wtT` at branch tip (venv via uv, ~5-10 min) with per-arm
  `HAFISCAL_TM_AMAX` env; outputs namespaced per arm; nothing overwrites canonical files.
- Runner: setsid, +x, per-stage logs, flag files (.done/.failed/.pid), PYTHONUNBUFFERED,
  `HAFISCAL_FTI_REPO` + ATI env (the certified stack), monitor on flags.
- Est. wall after trigger: ~1 h 45 m (Phases 1–3) + ~45 m implementation ⟹ BUG-084
  closed ~2.5 h after the batteries land.

---

## EXECUTION LOG

- **15:00** trigger fired (dellb 14:58:51, crra3 14:55:28; monitor b6tuv8820 retired).
- **15:04** Phase 1+2 arms launched concurrently (wtT/wtA2/wtA3/wtP2, shared venv):
  A1 ρ=2@2900, A2 ρ=2@800, A3 ρ=2@300, P2 ρ=3@2900 (College, 4 cold COBYQA starts each).
  P2 log carries the CRRA=3.0 override; per-arm dist-top verification at TM-build time.
  Monitor b2nyrzsdp on flags. ALSO observed in every arm log: the live solve grids are
  PF-decay-ruled (467/237, 551/240, 591/241) — triggered the remedy-F verdict CORRECTION
  (see the remedies plan, f4521ce6).
- **15:06** support leg DONE (both ρ, ~90 s — single-atom solves are cheap). **Rule output:**
  ρ=2: dropout a*=611 (onset binds), HS 575, College 70 ⟹ **required = 611** — 1300
  ratified with 2.1× margin, as predicted. ρ=3: dropout a*=1060 (SUPPORT binds — the
  intersection working), College 148, **HS a*=1701 (onset 1701, support 1939) ⟹
  required = 1701 > 1300.** The binding ρ=3 atom is HS, not College — the plan's P2 arm
  does not test it.
- **15:0x** **Arm P2b added** (wtP2b): ρ=3 HS (EDTYPES=1) at top 2900, 4 cold starts, vs
  today's G3 HS 1300 reference (0.8969/0.1205, 4-start cold — a valid paired reference).
  This is the rule's sharpest falsifiable prediction: if 2900-vs-1300 differences exceed
  cross-start scatter, ρ=3 production estimates need top ≥ 1701 (a REAL finding, and the
  fresh γ=3 row would need re-running); if within scatter, 1300 stands and required_top is
  recorded as a conservative guardrail (the tail state absorbing the 1.7% kernel
  deviation). GATE G2 now = P2 (College) ∧ P2b (HS) both judged.
- **15:3x–15:50 — dropout arms (the true ρ=2 gate) + College graded-objective proof.**
  Sidecars turned out stale (no emission from estim_phase2 bare runs) — TM_AMAX consumption
  proven instead by code path (tm_methods: `dist_aGrid_max=None → env`) AND by the graded
  objective values (College distance 1.0408/1.0354/1.0153 at 2900/800/300: the grids
  differed; the argmin didn't). College runs 2 starts by structure (startpoint grid).
  D800: Δβ +0.032%, Δ∇ −0.093%; D300 (falsification arm): Δβ +0.002%, Δ∇ −0.007% — BOTH
  4/4 one basin; non-monotone in the top ⟹ node-placement jitter, not truncation. Per the
  pre-registered language: the rule is CONSERVATIVE at ρ=2 (top-insensitive to ≥300) — a
  pass. **G1 GREEN. G2-College GREEN.** Owner scope ruling (15:4x): ρ=3 legs are a separate
  agenda — closure gates on ρ=2 only; P2b files separately on landing.
- **~16:00 — Phase 4 EXECUTED** (commit below): onset_dist_top PROMOTED; β=2.0 probe +
  refuse-at-ceiling in `production_dist_aGrid_max` (+3 guard tests, 9/9 fast suite green;
  env-flag registry guard 7/7); parity-cap bench refusal-fallback to the recorded 1300;
  CLAUDE.md + ENV_FLAGS doctrine replaced (onset ∧ support + connectivity conditions).
  BUG-084 dossier + index → FIXED-CLOSED. No numeric change anywhere; 1300 stands.
- **16:0x–16:3x — refusal criterion HARDENED to v2 after owner review** ("too easy a test —
  what is needed is a case where we know the config should fail, but NOT by a colossal
  margin"). The review was right twice over: (i) the ceiling check only caught colossal
  failures; (ii) a pile-mass margin is unfixable — the truncated dynamics undercount their
  own tail ~3× (10× margin wrongly refused a certifiable config; 2× missed a known-bad one).
  v2 = MEASURED convergence: quantile computed on the covering grid AND a 1.5× taller one,
  refuse on >5% disagreement (pile check kept as the colossal fast-path). Real-config
  boundary test (env-gated, GREEN): installed College top atom — covering 8,000 refuses
  (18.9% disagreement; the 8k build's plausible 6,679 would have passed every old check);
  12,000 refuses (8,231 vs 8,976 — quantile INSIDE the grid yet 8% low: invisible to any
  pile/ceiling heuristic); 20,000 passes with q=8,976 (dossier 8,968: 0.1%). Unit fakes
  rewritten as fixed-distribution vs top-dependent-corruption cases. 10/10 fast + slow green.
- **16:2x — P2b (ρ=3 HS @2900, separate filing per owner scope ruling): AGREES** with the
  1300 reference (Δβ +0.0012%, Δ∇ −0.011%; 3+/4 starts one basin) ⟹ the rule's ρ=3
  required=1701 is CONSERVATIVE (tail state absorbs the 1.7% kernel deviation); the γ=3
  row stands; NO robustness-agenda finding.
