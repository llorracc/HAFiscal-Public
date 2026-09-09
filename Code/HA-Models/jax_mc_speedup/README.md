# jax_mc_speedup

New HAFiscal benchmarking + scaffolding for JAX MC speedups (2026-05-20).
Moved here from `Code/HA-Models/FromPandemicCode/` because FromPandemicCode/
is reserved for code that originated with the Pandemic paper; new code
goes here.

## Files

- **jax_mc_speedup_bench.py** — benchmark harness. Runs
  `solve_ad_recession_jax_multicohort` and records wall + outputs for
  parity comparison across speedup variants.

  ```
  python jax_mc_speedup_bench.py --label v0_baseline
  HAFISCAL_JAX_MC_USE_2D_LIFT=1 python jax_mc_speedup_bench.py --label v1
  python jax_mc_speedup_bench.py --compare v0_baseline v1
  ```

- **jax_solver_iterated.py** — Speedup 2B. Two entry points:
  - `iterate_cfunc_jax(...)` — fixed-N iter via `lax.scan` (original
    scaffold)
  - `iterate_cfunc_jax_until_convergence(...)` — convergence variant
    via `lax.while_loop` with cFunc-table-diff stop criterion (all
    inside JIT, no Python dispatch per iter)
  - `extract_solve_inputs(agent, solution_initial)` — gathers all kernel
    arrays from a HAFiscal agent
  - `solve_to_convergence_from_agent(agent, max_iters, tol)` — end-to-end
    convenience wrapper

- **test_2B_while_loop_parity.py** — Parity + timing at HS_Only:
  HARK native vs JAX scan-fixed vs JAX while_loop. Confirms B↔C
  bit-comparable (~1e-7). At HS_Only scale, (C) is ~1.08× faster than
  (B) but still ~0.75× of HARK native — the speedup is gated on larger
  scale + GPU.

- **test_2B_scaled.py** — Same parity test parameterized on
  `--parametrization {HS_Only,Reduced_Run,Baseline}` and `--cohort N`.

- **overnight_1a2a_sweep.sh / overnight_phase2.sh** — Overnight runners
  for the 1A-2A characterization matrix and the 2B-at-scale parity.

- **combined_parallel_jax_test.py** — Validates `HAFISCAL_USE_JAX_SOLVER`
  + cohort-parallel solve compose correctly. From 2026-05-19.

- **load_balance_bench.py** — Measures cohort-parallel-solve speedup at
  Baseline 5x with the largest-β-first load balancing. From 2026-05-19.

- **speedup_bench_results/** — `.npz` outputs from
  `jax_mc_speedup_bench.py` runs. Gitignored.

## Related (still in FromPandemicCode/, since they were modified there)

- `FromPandemicCode/jax_mc_ad.py` — kernel + 1A/1B/1D variants
- `FromPandemicCode/jax_mc_ad_multicohort.py` — driver + 2A vmap-cohorts

## Env flags (1A–2A from the speedup brainstorm)

| Flag | What it does |
|---|---|
| `HAFISCAL_JAX_MC_USE_2D_LIFT=1` | (m,C) bilinear cFunc lift |
| `HAFISCAL_JAX_MC_VMAP_SEEDS=1` | One JIT call across seeds |
| `HAFISCAL_JAX_MC_BATCH_TABLES=1` | Single host→device transfer |
| `HAFISCAL_JAX_MC_LAZY_PANEL=1` | Skip cLvl panel on non-final iters |
| `HAFISCAL_JAX_MC_VMAP_COHORTS=1` | One JIT call across cohorts |

All optimization flags; do NOT affect numerical output. Validated to
parity 1e-7 at HS_Only and Reduced_Run.

Full registry of all `HAFISCAL_*` env flags (defaults, gating, caveats):
`Code/HA-Models/docs/ENV_FLAGS.md` (section "JAX & Speedups").
