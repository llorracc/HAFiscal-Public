# Overnight report — night of 2026-08-20→21 (robustness appendix + no-splurge chain)

**Provenance:** the scheduled author (the `--continue` fork session that drove Aug 19–20)
died at 00:20 with this report undelivered; written 2026-08-21 ~12:00 by the original
session, reconstructed from the fork's own execution log
(`plans_local/20260820-2100h_robustness-appendix-batteries_plan.md`), the coldrun flags,
commits `c96aa3ac..c9a5ecb9`, and both machines' filesystems — then extended with what
today's pickup of the orphans found. Successor to `20260819-0700h_overnight-report.md`.

## 1. Program and outcomes

| battery | machine | window | outcome |
|---|---|---|---|
| part A: `Rfree_1015`, `LowerUBnoB` Step 2 + fit | m5 | 20:54–21:48 | ✅ installed `8533c492` (LowerUBnoB dropout ∇ pinned at 0.40 → became BUG-083) |
| no-splurge chain N1–N4 (splurge=0 Step 1 COBYQA, Step-3 calibration) | dell | 20:5x–22:00 | ✅ installed `aff30532`/`152f5e9c` (D 0.7198/0.3242, HS 0.9091/0.1055, C 0.9867/0.0205) |
| BUG-083 re-estimation (`robust_dell_c`) | dell | 22:34–22:58 | ✅ LowerUBnoB dropout **β 0.6236 / ∇ 0.4370 / f 0.076** (pinned run: 2.20; published 0.609/0.445\*); main-spec dropout re-check 4/4 = installed. `6b6003f8` |
| part B: `Rfree_1005` Step 2 + fit; welfare for R-configs | m5 | 21:50–**05:35** | ✅ COMPLETE (setsid survivor). R=1.005 installed `9ccb9f25`: D 0.7517/0.2922, HS 0.9438/0.0703, C 0.9980/0.0117 |
| part C: corrected-LowerUBnoB fit + welfare | m5 | –**06:34** | ✅ COMPLETE (supersedes part B's pinned-calibration welfare, renamed `_SUPERSEDED_nabla04`) |
| part D: Baseline welfare seeds 0/1/2 → per-seed dirs | m5 | –**07:22** | ✅ COMPLETE — the real S=3 band now exists (fixes the 22:50 seed-overwrite finding) |
| N5: Splurge0 welfare seeds 0/1/2 | dell | 21:5x–00:07 | seeds 0,1 ✅ + snapshotted (𝒲 UI 1.77/1.68, check 1.02/1.02, taxcut 0.98/0.98; Rec, AD=0); **seed 2 killed** → rerun RUNNING since 11:28 |
| N6: SplurgeComp table | dell | deferred | ⏳ queued on seed 2 (`welfare6_splurgecomp.py --baseline … --splurge0 … --out …`) |
| `robust_dell_b`: ADElas + Rspell_4, welfare + multipliers | dell | 00:09–00:19 ✝ | **killed** → RUNNING since 11:29 (wt ff'd clean to `c9a5ecb9`; ETA ~16:00–18:00) |
| γ chain, γ=1 | dell | 23:15 | ⛔ **PARKED — owner decision** (see §4) |
| γ chain, γ=3: G1 Step 1 | dell | 23:21–23:52 | ✅ 8/8 one basin: **splurge 0.3009 / β 0.9656 / ∇ 0.0472, f 0.00168** (published splurge 0.304); installed `d7bb94f3` |
| γ=3: G2 grid top | dell | 23:52 | ✅ stays at production 1300; `[tail-diag]` armed |
| γ=3: G3 Step 2 (+G4/G5) | dell | 23:52–00:19 ✝ | ❌ killed **and MISWIRED — see §2** |
| spine4 (S8 candidate) | dell/m5 | afternoon | ✅ complete; `spine4_post2.failed` is residue of a HALT "recovered outside the driver (BUG-080) 18:12–18:29"; packet PDF verified 19:14 (`a3b3c1e9`) |

✝ 00:19:28–00:19:30: both dell batteries and the γ=3 Step-2 trio died within seconds of each
other — an external kill sweep during the shutdown around the driver's exit, not crashes.

## 2. NEW finding (today, from the pickup): the γ=3 G3+ stages ran at the WRONG γ

`crra3_s2g2.log` ends `Done.` — but wrote `DiscFacEstim_CRRA_2.0_…` with β 0.9930 / GICx
7.6004 (main-spec values). Root cause: **`EstimParameters.py` never reads CRRA from argv —
the `elif len(sys.argv) >= 3: CRRA = float(sys.argv[2])` block is commented out** (it died
together with the old per-CRRA splurge-file autoload). Rfree (argv[1]-path), IncUnemp/NoB
(argv[3,4]) and Splurge (argv[5]) all flow; CRRA silently stays 2.0. Every prior use of
`estim_phase2_tm_a.py` had CRRA=2, so the latency was invisible; the γ arm is the first
caller that needed it. Consequences: (i) even absent the sweep, G3–G5 would have produced
wrong-model results under γ-less names; (ii) the γ=2-named per-edType outputs **clobbered 5
main-spec intermediates in wt2** — restored today via cmp-verified `git checkout` (wt2 now
0 dirty tracked). The γ=3 chain's G1/G2 results are unaffected (the Step-1 arm passes γ by
its own env gate). **Fix + surgical G3–G5 resume are the next actions** (§5); candidate
BUG-085.

## 3. Bugs and rulings of the night

- **BUG-082** (𝒞 tables divided by a log-utility normalizer) — fixed `7d66c5ad`; owner
  ruling 22:05: `HAFISCAL_WELFARE_CE_HORIZON=lifetime`; decision record in
  `conclusions_private/2026-08-20_bug082-…`. Resolves the welfare-bp producibility question
  in favor of option (b) with the corrected formula.
- **BUG-083** (Step-2 ∇ search end 0.4 pinned the low-benefits dropout) — end widened to
  0.55 (`ed80c247`) + `NABLA_AT_BOX` tripwire; re-estimated same night (§1).
- **BUG-084** — OPEN, owner re-ruling needed: `production_dist_aGrid_max` returns 19,900 at
  every γ (its "β=1.01 clips to the cap" premise is stale under the aggregate-cusp cap);
  installed College top atom keeps 3.0e-3 mass above 1300 (q(1−1e-4)=8,968). Not on the run
  path; chain runs on the production 1300 with a per-γ `[tail-diag]` line.
- **Seed-overwrite finding (22:50)** — `run_welfare6_parallel.py` named outputs without the
  seed; the spine drivers' seeds 0/1/2 overwrote each other (the spine4 packet's welfare
  table was seed 2 alone; "S=3" in that report was an overstatement). Fixed by per-seed
  dirs (`878b0475`) + part D re-run; **remaining**: aggregate the part-D tables
  (`welfare6_seedband.py`) into the packet, and make bare `--seed-offset K>0` refuse
  without a per-seed out-dir.
- **BUG-085 (candidate, today)** — the dead CRRA argv read (§2).
- Owner rulings 22:15–22:30 recorded in the plan log: BUG-083 box; **appendix welfare
  tables stay single-seed** (measured seed noise ≤1.7% ≪ cross-config differences); γ rows
  re-estimate splurge per γ (arm built `5e82651f`, smoke-tested).

## 4. Owner decisions outstanding

1. **γ=1 row** (parked 23:15; artifacts `Results/cold_rerun_2026-08/crra1_parked/`): all 8
   cold starts → splurge=0 face, top atom AT the γ=1 cap, f 0.441 (vs 0.0017 at γ=2). The
   ergodic TM engine cannot reach the wealth targets at log utility within the GIC; the
   published row existed only because MC's finite burn-in tolerated non-stationary patience.
   Options: (a) drop the row and say why — the fork's recommendation; (b) report the
   constrained optimum with the explanation; (c) reproduce the artefact under the legacy MC
   engine.
2. **BUG-084** grid-top sizing rule re-ruling.
3. **Promotions** — every calibration above is installed on the branch but promotion
   remains yours (the 20:00 charge).
4. (Small) adopt the `--seed-offset` refusal guard.

## 5. State at writing (12:00) and next actions

Running: Splurge0 seed-2 rerun (since 11:28), robust_dell_b (since 11:29, stage ADElas
welfare) — both monitored (flags + failure/vanish detection). m5: everything complete.
xubuntark: idle. Next, in order: (1) reinstate the CRRA argv read (BUG-085 fix) on the
branch and in wt2; (2) surgical γ=3 G3→G5 resume (Step 1/G2 stand; G5 gated on a free
welfare-battery slot); (3) N6 when seed 2 lands; (4) `welfare6_seedband` aggregation of
part D into the spine4 packet correction; (5) the deferred appendix tail: CRRA fit passes,
Lorenz robustness figures, `robustness_appendix_diff.py` run against the hand-typed rows.

## 6. Where things live

Fork's execution log: `plans_local/20260820-2100h_robustness-appendix-batteries_plan.md` ·
flags/logs `~/coldrun_2026-08/` (dell), same on m5 · installs: commits listed in §1 ·
γ=1 parking + spine records under `Code/HA-Models/Results/cold_rerun_2026-08/` · the
session split-brain that delayed this report: `memory/feedback_tmux_continue_split_brain.md`
and the claude-session guard now deployed fleet-wide (llorracc/claude `e463bc1`+).

---

## Addendum (14:2x) — §4 docket correction after re-reading the 08-19/20 records

Two items listed as outstanding were ALREADY RESOLVED before this report was written and
should not have been carried forward: **D3** (θ default flip) was formally SUPERSEDED by
the COBYQA Step-1 default adoption (owner ruling, 08-19 Addendum 11, `4439c070` — θ+box
stays opt-in, no flip pending); **S2 acceptance** was RULED (owner: S2 machinery = S1
machinery `eb0d18f0`; S2 COBYQA battery installed as the canonical calibration
`f3a9ff71`). The live docket is: γ=1 row (a/b/c), BUG-084 (now RULED 08-21, impl
deferred — `conclusions_private/2026-08-21_dist-top-onset-rule-ruling.md`), promotions
(RULED 08-21: QE stays frozen, no promotions), --seed-offset guard (RULED 08-21:
adopted, `878b0475` flavor). Net: **only the γ=1 row remains undecided.**
