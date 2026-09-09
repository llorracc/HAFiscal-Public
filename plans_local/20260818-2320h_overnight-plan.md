# Overnight plan, 2026-08-18 23:20 → 2026-08-19 ~07:20 (owner asleep; autonomous)

**Authorization:** owner 23:00 — "you can use all four of jhu-dell, ccarroll-m5, ccarroll,
and xubuntark in whatever manner is most efficient"; earlier: continue runs to completion.
**Everything below is LAUNCHED and monitored** (persistent monitor `baswrfla0`, state-change
events; crons at 03:53 = V4 wrap-up + S2 launch, 06:57 = morning report).

## Running now (all launched 23:15–23:19)

| machine | job | procs | expected end |
|---|---|---|---|
| dell + m5 | **V4** — `S1run8-theta`: 8-seed θ battery, ftol=1e-5, xtol=1e-6, worktrees `aaf7faad`, checkerboard shard as run 7 | 4 + 4 | ~02:00–02:45 |
| ccarroll | **θ xtol A/B** — seeds 1 & 2 × xtol {1e-5, 1e-7} at ftol=1e-5 (V4's seed 1/2 at 1e-6 are the middle arms) | 4 | ~01:30–02:00 |
| xubuntark | **S3** — Splurge=0 arm on the new universal 4-point grid, native AND θ (θ in a second worktree so result files cannot collide) | 8 | ~03:00–05:00 |

## When V4 finishes (cron 03:53, or the monitor event if earlier)
1. `s1_merge_shards.sh ~/coldrun_2026-08/s1_merged_v4` (explicit dir — run 7's merge stays)
2. gate it (expect one basin; era-1 HALT is by design); write V4-vs-run-7 comparison
   (basins, consensus ± sd, straggler count, evals, per machine; the pre-registered
   prediction was "seeds 7/8 stop straggling")
3. exact ftol replay on the V4 traces (sanity: does 1e-5 stop where it should in θ?)
4. **launch S2 on dell + m5** (`s2_run.sh`, chain two-arm design) on the **run-7 WINNER**
   (seed 5: ς 0.2998730 / β 0.9795245 / ∇ 0.0293882 — the gate's min-f seed, staged at
   `$WT/Code/HA-Models/Results/cold_rerun_2026-08/s1/Result_AllTarget_ESC.txt` on both).
   Labelled a CANDIDATE: the S1 estimate-of-record ruling (native run 7 vs θ V4) is the
   owner's; the two consensuses are expected to differ by ~1e-4 in ς, so if the ruling
   goes the other way S2 is a ~1–2 h rerun. Nothing is promoted.

## Morning report (cron 06:57) — `plans_local/20260819-*_overnight-report.md`
V4 results + comparison; S2 candidate gate; S3 native vs θ; xtol A/B; open owner decisions
(D3 flip, S1 SoR, S2 acceptance, θ xtol). Facts and recommendations kept separate.

## What is deliberately NOT done overnight
Promotions, default flips, merges to other branches, memory rewrites of rulings, and
anything the owner said to ask about first. Failures are recorded, not papered over.

## 23:40 finding — V4 has a failure mode (recorded as it happened)
25 min in, all four **k = 0.90** seeds (4, 8 on dell; 3, 7 on m5 — both ς₀ levels, both ∇₀
levels) had "converged" at ~240 evals to the **splurge=0 conditional optimum**
(β 0.9264, ∇ 0.0900, f 0.01650 = 10× the true minimum) with θ_s ≈ −78 (ς 1e-34), Powell
reporting success. The four k_top seeds are converging normally. Mechanism: from an
impatient β the objective first FALLS toward ς=0; unbounded Brent brackets outward into the
saturated region where f is exactly flat in θ_s; nothing can bring it back. Native never did
this because its BOUNDED line search samples the whole [0, 0.9] segment every cycle (run 7:
8/8 from the same startpoints). So V4's pre-registered prediction is FALSIFIED as
implemented: θ removed the taper shelf and introduced a worse trap.

**Response (no ruling touched):** `HAFISCAL_STEP1_THETA_BOX=1` (`44b442fc`, opt-in, default
off) gives Powell a finite θ box — floors at ς/∇/margin = 1e-4 where the maps are still
responsive, native's ends elsewhere — restoring the bounded, globally sampling line search
while keeping the log/logit maps and the structural cap. **V4b** (`S1run9-thetabox`) runs on
dell+m5 as soon as V4 finishes, concurrently with the S2 candidate. V4 runs to completion
untouched (its 4 good seeds are still informative, and its failure is the finding).
