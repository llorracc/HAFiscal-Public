# solution_cache

On-disk cache of AD-converged `eco.solve()` outputs. Lets HARK MC, JAX MC,
5D TM, and any other downstream script skip the expensive `eco.solve()`
when an identical run has already been done.

## Quick start

```python
from solution_cache import cached_eco_solve

# Instead of:
#   eco.switch_shock_type('recession'); eco.solve()
# do:
result = cached_eco_solve(
    ctx, shock_type='recession',
    mc_method='hark_mc',     # or 'jax_mc' / 'jax_mc_replay_v2'
    seeds=(0, 1, 2, 3),
    use_shuffle=False,
)
print(f"cache_hit={result['cache_hit']}, wall={result['wall']:.1f}s")
```

Toggle: `HAFISCAL_USE_SOLUTION_CACHE=1` (off by default — `cached_eco_solve`
falls through to plain `eco.solve()` if the env var is unset).

## What's in the cache key

Everything that affects the numerical output of `eco.solve()` after AD
convergence:

- **Per-cohort solve-time params:** CRRA, DiscFac, Rfree, PermGroFac,
  LivPrb, BoroCnstArt, aXtraGrid, Cgrid, IncShkDstn (atoms + probs),
  MrkvArray, CondMrkvArrays, num_base_MrkvStates, Splurge, T_age
- **AD-loop params:** num_max_iterations_solvingAD, convergence_tol_solvingAD,
  Cfunc_iter_stepsize, ADelasticity, num_experiment_periods
- **Forward-sim during AD:** shock_type, mc_method, seeds, use_shuffle,
  init_panel_method, agent_count_per_cohort
- **HAFISCAL_* env flags (whitelisted, numerical-output-affecting):**
  `HAFISCAL_PLVL_GROWS_DURING_UNEMP`, `HAFISCAL_TM_CFUNC_OFFSET`,
  `HAFISCAL_AGGREGATE_BY_EDU_SHARE`, `HAFISCAL_UI_STATE_ENCODING`,
  `HAFISCAL_SHUFFLE_MRKV_TRANSITION`, `HAFISCAL_AGENTCOUNT_{D,H,C}`,
  `HAFISCAL_INTERPRETATION`, `HAFISCAL_WRAPPER_EDTYPES`, `HAFISCAL_GICX_MODE`,
  `HAFISCAL_NM_START_FROM_SAVED`
## What's NOT in the key (numerical-equivalent toggles)

- `HAFISCAL_JAX_MC_USE_2D_LIFT`, `HAFISCAL_JAX_MC_VMAP_SEEDS`,
  `HAFISCAL_JAX_MC_BATCH_TABLES`, `HAFISCAL_JAX_MC_LAZY_PANEL`,
  `HAFISCAL_JAX_MC_VMAP_COHORTS` — speedup-only, parity-validated
- `HAFISCAL_PARALLEL_SOLVE` — cohort-scheduling only
- `HAFISCAL_USE_JAX_SOLVER` — validated equivalent to HARK numpy solver
- JAX backend (CPU vs GPU) — equivalent within FP precision
- **HARK commit SHA + HAFiscal commit SHA + Python major.minor** —
  these go in the `.meta.json` sidecar for forensics (and a load-time
  warning fires if any differs), but are excluded from the hash so
  a mid-session commit doesn't silently invalidate the cache.

## Cache wrappers

Three drop-in wrappers ship with the cache. All key off the same
`HAFISCAL_USE_SOLUTION_CACHE=1` env var, off-by-default.

| Wrapper | Wraps | Result granularity |
|---|---|---|
| `cached_eco_solve(ctx, shock_type, ...)` | one `eco.solve()` | per-`eco.solve()` |
| `cached_solve_ad_recession(ctx, base_AggCons, ...)` | JAX-AD pipeline (`solve_ad_recession_jax_multicohort`) | full AD loop |
| `cached_solve_ad_recession_hark(ctx, num_max_iter, cutoff, shock_type, name)` | HARK-AD methods (`eco.solve_ad_recession` + 3 siblings) | full AD loop + `eco.stored_solutions[name]` |

The AD wrappers cache the entire AD-converged output. On hit, the AD loop
is skipped entirely — Baseline JAX-AD wall goes from ~3000 s to ~0.5 s
(~5500×); HS_Only HARK-AD wall goes from ~20 s to ~0.08 s (~250×).

## Inspecting the cache

```bash
.venv-linux-x86_64/bin/python Code/HA-Models/solution_cache/inspect_cache.py
.venv-linux-x86_64/bin/python Code/HA-Models/solution_cache/inspect_cache.py --detail
.venv-linux-x86_64/bin/python Code/HA-Models/solution_cache/inspect_cache.py --filter Baseline
```

Summary mode shows entry count + total size per `(parametrization, shock_type)`.
Detail mode adds `mc_method`, `result_type`, age, and the human-readable
filename tag.

## On-disk layout

```
Code/HA-Models/solution_cache/
  __init__.py, cache.py, serialize.py, keys.py    # module (committed)
  .gitignore, README.md
  Baseline/                                       # data (gitignored)
    recession/
      AC10000-10000-10000__mc-hark_mc__noshuf__seed0__a1b2c3d4.pkl
      AC10000-10000-10000__mc-hark_mc__noshuf__seed0__a1b2c3d4.meta.json
    recessionCheck/
      ...
  HS_Only/
    ...
```

- **Top dir:** parametrization name (Baseline, HS_Only, Reduced_Run, ...)
- **Sub dir:** `shock_type` (recession, recessionCheck, base, ...)
- **Filename:** `<human-readable-tag>__<short-hash>.pkl`
- **Sidecar:** `<...>.meta.json` with full key inputs (for `grep` / browsing)
- **Short hash:** first 8 hex of SHA256 of canonical inputs (collision-safe
  enough in practice; full hash is in the meta.json for collision detection)

## Concurrent-safety

Writes go to `.pkl.tmp` then `os.replace`. Multiple processes writing the
same key end with last-writer-wins (still consistent — both pickles contain
the same numerical solution). Reads never see partial files.

## Cache invalidation

Easy mode: `rm -rf Code/HA-Models/solution_cache/{Baseline,HS_Only,...}`.

Surgical mode: delete a specific parametrization subdir.

Note: provenance (HARK/HAFiscal SHAs, Python version) does NOT affect the
cache key — only numerical params do. A commit to either repo doesn't
invalidate any entries; the load step emits a one-line warning if the
cached `.meta.json` records a different SHA than the current process.

## Reconstruction, not pickle-passing

The cache pickles only **numerical arrays** (cNrm, mNrm, BoroCnstNat,
Mgrid). On load, `reconstruct_eco_solution` rebuilds the HARK cFunc objects
using HARK's classes — this is robust to HARK adding/removing attributes
on its interpolator classes (the pickle has no HARK class instances).

If HARK *renames* a class (`LowerEnvelope2D` → something else), the load
raises an `ImportError` — a deliberately loud failure rather than silent
corruption.

## Limitations

- Only the HAFiscal recession cFunc layout is supported (
  `LowerEnvelope2D(VariableLowerBoundFunc2D(LinearInterpOnInterp1D(...),
  LinearInterp(...)), BilinearInterp(...))`). Adapting to other layouts
  is straightforward — see `serialize.py`.
- No automatic cleanup of stale entries — disk grows until manual `rm`.
- The "human-readable tag" packs ~5 params; the full key is in `.meta.json`.
  If you need a different tag schema, see `keys.parametrization_tag`.
