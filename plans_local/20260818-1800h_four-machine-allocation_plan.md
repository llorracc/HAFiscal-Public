# Four-machine allocation: V4 and what runs beside it (2026-08-18 evening)

**Owner rulings this applies:** ftol=1e-5 (derived); xtol=1e-6 unchanged; V4 on dell+m5
(recommendation accepted). **Status (2026-08-19 07:00): EXECUTED overnight** — V4/V4b done (see 20260819-0700h_overnight-report.md), S2 arms running, S3 6/8 (θ arms all done), xtol A/B 3/4 (ccarroll slept). **Original:** STAGED — awaiting go.

## 0. The machines, as measured today

| | jhu-dell | ccarroll-m5 | ccarroll | xubuntark |
|---|---|---|---|---|
| arch / cores | x86-64 / 32 | arm64 / 18 | arm64 / 16 (owner's workstation) | x86-64 Sandy Bridge / 24, 125 GiB |
| Step-1 eval | 6.2 s | 7.1 s | 7.7 s | **28 s** |
| anchor bits | `…5354` | `…53353` | `…53353` (= m5) | `…53535` (≠ dell) |
| env | dell's set (SoT) | = dell (synced 17:40) | = dell (+platform pkgs) | = dell |
| reachability | — | direct | direct | via ccarroll bastion hop |
| status | idle | idle | idle | idle |

Rule of thumb that falls out: anything on the **critical path** or needing a **matched
control** goes to dell+m5; ccarroll takes **light, independent** jobs (≤3 procs — it is the
owner's desk); xubuntark takes **off-critical-path, wall-insensitive** jobs (4.5× slower per
core, but 24 idle cores and no one waiting on it).

## 1. Critical path — dell + m5

**V4 — the 8-seed θ battery, run 7 as matched control.** Same 8 startpoints, same
checkerboard shard (dell 1,4,5,8 / m5 2,3,6,7), same tolerances except the just-ruled
`ftol=1e-5`, `HAFISCAL_STEP1_PARAM=theta`. Compare against run 7: modal basin, spread,
straggler count, evals. Pre-registered prediction: seeds 7/8 stop straggling if the shelf
was the mechanism (V3 says it is).
- Expected evals: run 7 at ftol=1e-5 would have been 9,497 total; V1 suggests θ needs
  fewer still. Wall = slowest seed ≈ 1,900 × 6.5 s ≈ **2.5–3.5 h**.
- Then: merge shards, gate (expect one basin; the era-1 HALT is by design), write V4 vs
  run 7 comparison → **owner ruling on the D3 default flip** → S1 estimate of record.
- Runner: `s1_run.sh` relabelled `S1run8` with the PARAM mode in its banner; run-7 logs
  archived to `run7_archive/` on both machines first.

**Then S2 (Step 2, cold multistart, TM-ergodic) on dell + m5** consuming the S1 estimate of
record via `HAFISCAL_SPLURGE_FILE` — `s2_run.sh` is already staged. ~15 min per group per
start on dell; the 4/3/2 dispersed grid ⇒ ~1–2 h. Gated on the S1 SoR ruling above, so it
starts after V4 is judged, not before.

## 2. ccarroll — light, independent, informs the θ default

**θ-space `xtol` A/B on seed 1** (the one job xtol *can* be studied by, since it changes
the trajectory): `xtol ∈ {1e-5, 1e-7}` at `ftol=1e-5`, θ mode; V4's dell seed 1 (xtol=1e-6)
is the middle arm. Reports evals and endpoint shift in run-7 sd units. Two processes,
~1.5–2 h, ~2 of 16 cores. Independent of V4 (V4 does not need it), and it answers the
question the owner asked about xtol *where it will matter going forward* rather than on
the legacy path.

## 3. xubuntark — off critical path, wall-insensitive

**S3, the Splurge=0 robustness arm, NATIVE (chain stage S3, "informational, off critical
path")** — `HAFISCAL_STEP1_SPLURGE0=1` with the cold 9-point grid, 9 concurrent processes
(2-D problem, cheaper per solve; ~4–6 h at 28 s/eval, nobody waits). Independent of V4 and
S2. Its logs also feed the same ftol replay.

**Deferred: S3 under θ.** Found while staging: the S3 cold grid is `β₀ ∈ {0.85, 0.925, 1.0}
× ∇₀ ∈ {0, 0.025, 0.05}` — three startpoints have ∇₀ = 0 (log ∇ = −∞) and the β₀ = 1
column puts the top atom above the cap for ∇₀ > 0. The native taper absorbs both; θ cannot
represent them (`to_theta_bn` raises, correctly). D1=(c) therefore needs a small follow-up:
a cap-relative, ∇₀>0 grid for S3, mirroring the S1 grid fix of 2026-08-17. Code change,
then the θ arm can run (xubuntark again). Not blocking anything.

**Optional, second priority: the S2 control arm on the INSTALLED ς** (pre-authorized by the
chain plan's rule 3c for breach analysis). Independent of V4, could start now; caveat: it
would then differ from the new-ς S2 in machine as well as ς (arithmetic ~1e-14 vs a 0.1 %
gate — negligible, but not the one-thing-differs ideal). Cheap to redo on dell if S2
breaches, so this is a nice-to-have, not a need.

## 4. What is NOT worth a machine

- Native `xtol` A/B — legacy path once θ flips; skip.
- V5 (θ on arm64) — V4's m5 shard IS V5.
- A cross-CPU x86 mirror on xubuntark — its bits differ from dell anyway (`…53535`), and
  run 7 already showed no machine effect above the seed scatter.

## 5. Sequencing and dependencies

```
now      dell+m5: V4 ─────────────────┐    ccarroll: θ xtol A/B    xubuntark: S3 native
                                      │
+3h      merge, gate, V4-vs-run7 ─────┤
         OWNER: D3 flip? S1 SoR? ─────┤    (S3-θ grid fix: small code change, any time)
+3.5h    dell+m5: S2 (cold, TM-erg) ──┘    xubuntark: S3 θ (after grid fix), S2 control arm
```

Nothing on ccarroll or xubuntark is on the critical path; if either is inconvenient today
it can simply be skipped without delaying S2.
