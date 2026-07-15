# Solve / Simulate Tool Map (Phase A)

**Date:** 2026-06-21 · **Branch:** `…_TM-vs-MC_toolmap-phase-a` · **Status:** Phase-A v1 complete (4 CPU tools mapped; FTI/JAX deferred)
**Engine:** `Code/HA-Models/toolmap/bench_toolmap.py` · **Data:** `toolmap/results/<host>.json` · **Diff:** `toolmap/compare_results.py` · **Ledger:** `conclusions_private/2026-06-21_toolchain-ledger.md`

A *measured* map of HAFiscal's solve and simulate tools, benchmarked on a common small problem (**HS_Only** single-cohort: build + solve + sim) on two machines — **econ-mw** (`dell-8960-ext`, x86_64) and **ccarroll-m5** (arm64 Mac). For each tool: what it computes, measured wall-time, accuracy vs the baseline, and platform support. The bottom ranks a **win-list** that picks the next productionization target.

## Cross-platform reproduction guarantee
- **Same machine:** bit-identical (deterministic seeds; verified by back-to-back reruns).
- **x86_64 ↔ arm64:** agree to **~14 significant digits** (worst relative delta **`3.3e-15`**). The two machines produce numerically-identical-to-FP-noise results.
- **Parity-gate convention:** same-machine = bit-identical; cross-machine = `rel ≤ 1e-12` (safe margin over the measured 3.3e-15).

## SOLVE tools
| tool | what it is | econ-mw | ccarroll-m5 | accuracy vs EGM | platform |
|---|---|---|---|---|---|
| **EGM** (default) | HARK infinite-horizon EGM/markov solve (`AggregateDemandEconomy.solve`) | **0.25 s** | **0.23 s** | baseline | both (CPU) |
| **Anderson-EGM** (opt-in) | accelerated multi-state base solver (`HAFISCAL_STEP2_ANDERSON`) | **0.047 s (≈5.3× vs EGM)**, engaged | _fell back to EGM_ | matches EGM ~**1e-3** (kernel parity, accelerated) | **econ-mw only** — Mac can't import `hark_fti` (sibling-repo gap) |
| FTI (NAM / ATI / ConsumedATI) | fast-time-iteration solvers (sibling `fast-time-iteration` repo, `HAFISCAL_FTI_METHOD`) | not yet benched — needs sibling repo import | — | — | opt-in; sibling repo |
| JAX solver | GPU EGM kernel (`HAFISCAL_USE_JAX_SOLVER`) | not benched — GPU + `jax` group | **N/A** (no CUDA on arm Mac) | — | **econ-mw GPU only** |

## SIMULATE tools
| tool | what it is | econ-mw | ccarroll-m5 | accuracy vs MC | platform |
|---|---|---|---|---|---|
| **MC** (default) | HARK MC forward sim, aggregate moments | **0.63 s** | **0.53 s** | baseline | both (CPU) |
| **TM-ergodic** | a-indexed TM stationary-distribution moments (`tm_methods.compute_baseline_tm_data`) | **0.030 s (≈21× vs MC)** | **0.050 s (≈10.5× vs MC)** | matches MC within **~2 %** (aNrm mean +0.67 %, var +2.34 % — MC sampling noise); cross-platform 1e-16 | both (CPU), **deterministic** |
| stratified-shuffle MC | variance-reduced MC for welfare cells | not benched (it's the *reliable welfare* estimator; v1 used plain MC) | — | (BUG-057: plain MC unreliable for small-subpop cells) | both (CPU) |
| JAX-MC | GPU MC kernel | not benched — GPU | **N/A** | — | **econ-mw GPU only** |

## Decision map — which tool when
- **SOLVE:** EGM default everywhere; Anderson opt-in _(does it win at scale? — TBD)_; FTI/JAX specialized/GPU.
- **SIM — ergodic/aggregate moments (Step-2):** **TM-ergodic** — ~10–21× faster than MC, deterministic, matches MC within sampling noise → the efficient choice for the moment computation.
- **SIM — welfare (per-agent, CRN):** **MC + stratified-shuffle** — only MC provides the per-agent matching welfare-6 needs (TM can't).
- **SIM — multipliers:** TM (a-indexed) default; reliable-MC cross-check (the `--default`/`--legacy` axis, IMPROVEMENT-001).

## Ranked win-list (→ picks Phase B)
1. **TM-ergodic for the Step-2 moment computation** — >10× deterministic, CPU-portable (runs on both machines), matches MC within sampling noise. Highest (value × portability × parity-confidence). **→ Phase B target.** Parity gate = TM-vs-MC moment agreement (~2 %, within MC noise), NOT bit-identical.
2. **Anderson-EGM** — genuine **~5.3× solve speedup** (econ-mw), matches EGM to ~1e-3. But **not portable as-is**: falls back to EGM on ccarroll-m5 (sibling `fast-time-iteration` not importable as `hark_fti` there) → behind TM-ergodic on the portability axis. Productionizable for econ-mw, or once the Mac's sibling import is fixed.
3. GPU JAX kernels (solver, MC) — large speedups but **econ-mw-only** (not portable); stay specialized.

Phase B built **#1** as a parity-gated tool; **its default was FLIPPED on 2026-06-23 — TM-ergodic is now the Step-2 default engine (`mc` opt-in)** — after the owner-gated matched re-validation showed TM and MC estimate the SAME β to ≤0.06% across all three cohorts (the apparent Dropout gap was BUG-036 multimodality, not engine), at ~28× the speed (a full cross-machine estimation in ~15 min vs ~7 h/cohort). Rationale + validation table: `conclusions_private/2026-06-23_step2-default-flip-to-tm-ergodic.md`.
