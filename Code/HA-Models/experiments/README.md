# Experiment registry

One-line-per-experiment JSONL log of HAFiscal bench runs, with enough
structure to cross-compare configurations and trace ramifications.

## Files

- `registry.jsonl` — append-only. One JSON object per line, one
  experiment per object. Schema below.
- `append.py` — parse `launch_bench.sh` artifacts (bench.log /
  timing.log / mem.csv / launch.meta) and append one line.
- `summarize.py` — read the JSONL, emit a markdown table. Supports
  `--tag <tag>` to filter and `--cols ...` to choose columns.
- `cross.py` — diff two experiments by id (config delta + timing delta +
  correctness check).

## Schema (one JSON object per line in registry.jsonl)

```jsonc
{
  "id":           "<UTC timestamp>_<short slug>",  // unique key
  "label":        "1thr_cpu_par2",                 // launch_bench.sh LABEL
  "timestamp":    "2026-06-01T18:08:27-04:00",
  "git_sha":      "35c3cb1f",                      // HAFiscal commit at run time
  "config": {
    "parametrization": "Baseline",
    "num_iter":        2,
    "shock_type":      "recession",
    "backend":         "cpu",   // "cpu" | "gpu"
    "n_threads":       1,       // HAFISCAL_USE_JAX_2B_THREADS
    "n_workers":       2,       // HAFISCAL_PARALLEL_SOLVE
    "use_jax_2b":      true,    // HAFISCAL_USE_JAX_2B
    "use_solution_cache": false, // HAFISCAL_USE_SOLUTION_CACHE
    "host":            "ECON-MW-7MYCC14",
    "vram_total_gb":   16,
    "host_ram_gb":     54,
    "env_overrides":   {}        // any other notable env vars
  },
  "timing": {
    "wall_total_s":     2842.54,    // /usr/bin/time elapsed
    "wall_jax_total_s": 2793.56,    // bench's wall_jax_total
    "wall_ref_sim_s":   1828.2,     // HARK ref sim auto-init
    "wall_iter_s":      [802.3, 162.2]  // per-iter walls
  },
  "correctness": {
    "Cratio_0":         0.9909,
    "Total_Diff_final": 0.05808,
    "match_baseline":   "bit-identical"  // "bit-identical" | "<X% drift" | "drift"
  },
  "memory": {
    "peak_rss_parent_mb":      17801,    // /usr/bin/time -v Maximum RSS
    "peak_rss_system_mb_est":  34000,    // parent + workers (estimated from /proc)
    "peak_vram_mb":            null,     // nvidia-smi peak during run
    "avg_cpu_pct":             814
  },
  "vs_baseline": {                       // optional comparison block
    "baseline_id":      "2026-06-01T15:53_baseline_2iter_cpu_1thr",
    "wall_total_pct":   -15.8,
    "wall_ref_sim_pct": -13.1
  },
  "hypothesis": "Plain-English what we expected this experiment to show.",
  "outcome":    "Plain-English what it actually showed; lesson learned.",
  "tags":       ["option-E.1", "parallel_solve", "spawn_pool", "2B"],
  "log_paths":  ["Code/HA-Models/jax_mc_speedup/threads_bench_logs/1thr_cpu_par2.bench.log", ...],
  "parent_ids": ["2026-06-01T15:53_baseline_2iter_cpu_1thr"]  // DAG: which prior runs this builds on
}
```

## Conventions

- **id** is `<ISO timestamp, minute precision>_<slug>` so a `sort` orders runs chronologically.
- **tags** lets you slice by feature: e.g. `2B`, `parallel_solve`, `option-A`, `option-E.1`, `regression-test`.
- **parent_ids** gives the DAG of "this run builds on these prior runs" — captures ramification.
- **hypothesis** + **outcome** are short prose. The point of writing them is to force you to think about *what you're testing* and *what was learned* — otherwise the registry decays into a numeric stew.
- When a future commit invalidates an experiment (e.g., a bug fix changes the convergence), the old entry stays — append a new one with updated git_sha. Diffing the two captures the impact of the fix.

## Workflow

```bash
# After a bench completes (launch_bench.sh does this automatically):
python Code/HA-Models/experiments/append.py \
    --label 1thr_cpu_par2 \
    --hypothesis "..." \
    --outcome "..." \
    --tags option-E.1,parallel_solve,2B \
    --parent-ids 2026-06-01T15:53_baseline_2iter_cpu_1thr

# View what's in the registry:
python Code/HA-Models/experiments/summarize.py
python Code/HA-Models/experiments/summarize.py --tag option-E.1
python Code/HA-Models/experiments/summarize.py --tag 2B --cols id,timing.wall_total_s,vs_baseline.wall_total_pct,outcome

# Compare two:
python Code/HA-Models/experiments/cross.py \
    2026-06-01T15:53_baseline_2iter_cpu_1thr \
    2026-06-01T18:08_baseline_2iter_cpu_par2
```

## Big-picture lessons (this section is updated by hand)

A scratch pad for cross-experiment generalizations that emerge from
the registry. **Each lesson must reference the specific experiment
ids that support it** so it's auditable.

### L1. GPU is the path for the 2B JAX kernel
Per-iter speedup is 4.6× on iter 1 and 2.47× on iter 2 at Baseline
(GPU 221 s / 81 s vs CPU 1016 s / 200 s). Cratio_0 and Total_Diff are
bit-identical across backends.
- Supports: `2026-06-01T1554_Baseline_1thread_cpu` →
  `2026-06-01T1652_Baseline_1thread_gpu`

### L2. After moving the JAX kernel to GPU, HARK ref-sim auto-init now dominates wall (~79%)
At GPU Baseline 2-iter, 1138 s of 1441 s `wall_jax_total` is the HARK
ref sim. JAX iters are only 302 s combined. Optimization budget should
target ref sim before iter speedups.
- Supports: `2026-06-01T1652_Baseline_1thread_gpu`

### L3. Multi-worker parallel solve has two distinct failure modes
**CPU**: memory-bound. Each 2B worker needs ~17 GB host RSS. On a
54 GB host this caps workers at 2-3. 2-worker pool engages cleanly
(bit-identical) and gives +15.8% wall. Historical 3.88× was 21
workers × HARK (lighter per-worker), not feasible with 2B.
**GPU**: throughput-bound (GPU is the shared resource). 2 workers
each push JAX work to the same 16 GB / 100%-util GPU, contending
for the scheduler. Result is **-16% overall** — the spawn workers
mostly sit idle waiting on GPU (CPU% drops from 100% with 1 worker
to 136% combined with 2 workers). Iter 2 took 2.5× longer.
**Takeaway**: parallel-solve only helps when each worker can claim
a different physical resource. With one GPU, that's never true.
- Supports CPU: `2026-06-01T1808_Baseline_1thr_cpu_par2` (+15.8%
  vs 1-thread CPU)
- Supports GPU: `2026-06-01T1931_Baseline_1thr_gpu_par2` (-15.8%
  vs 1-worker GPU; peak VRAM 16006 MB / 16376 MB)

### L4. Spawn-pool cold start is paid inside the ref sim
The first eco.solve() through the persistent pool is the ref sim, so
JAX-2B JIT compile in each spawn child shows up *inside* the ref-sim
wall — eroding the parallelization win. Persistent pool amortizes
across subsequent AD iters but can't help iter 0.
- Supports: `2026-06-01T1808_Baseline_1thr_cpu_par2` ref sim only
  -13% (1828 vs 2105 s) while iter 1 is -21% — the gap is consistent
  with a one-time per-worker cold-start of ~150-200 s × 2 workers.

### L5. XLA's internal CPU parallelism saturates ~4 cores at THREADS=1
Average CPU% = 430% on 1-thread CPU bench. Outer threading
(`HAFISCAL_USE_JAX_2B_THREADS>1`) competes for the same cores —
unlikely to give linear scaling. Multiprocessing isolates better but
pays per-worker JIT init.
- Supports: `2026-06-01T1554_Baseline_1thread_cpu` (430% at 1 thread);
  `2026-06-01T1808_Baseline_1thr_cpu_par2` (814% at 2 workers ≈ 2× of
  430%, confirming each worker is also an XLA-saturating process).

### L6. All speedup configurations preserve bit-identical correctness
Across 4 measured configs (CPU/GPU × 1/2-worker), Cratio_0 is
0.9909 and Total_Diff_final is 0.05808 at iter 2. No drift introduced.
- Supports: all 2026-06-01 records.
