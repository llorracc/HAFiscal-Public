# HAFiscal Comparison Results (2026-02-03)

## Comparison: 0.14.1-bugfixed vs 0.17.0-loky-warmup

### Runtime (Step 1: Splurge Estimation)

| Version | Duration | Ratio |
|---------|----------|-------|
| 0.14.1-bugfixed | 15.2 min | 1.0x |
| 0.17.0-loky-warmup | 27.1 min | 1.78x |

**Note:** HARK_WARM_POOL=1 was enabled for 0.17.0, but did not help.

### Estimated Parameters

| Parameter | 0.14.1-bugfixed | 0.17.0-loky-warmup | Difference |
|-----------|-----------------|-------------------|------------|
| splurge | 0.2461 | 0.2471 | 0.40% |
| beta | 0.9676 | 0.9677 | 0.01% |
| nabla | 0.0578 | 0.0578 | 0.03% |

**Conclusion:** Parameters are essentially identical (< 0.5% difference).

### Why Warmup Did Not Help

The Loky pool warmup optimization was designed to pre-compile Numba JIT code
in worker processes before the optimization loop. However, it did not help
because:

1. **Worker Pool Recycling**: During `scipy.optimize.minimize`, Loky may
   recycle workers between iterations due to memory pressure or timeouts.
   
2. **Different Worker Counts**: The optimizer calls `multi_thread_commands`
   with varying numbers of agents across different objective function
   evaluations, which can trigger new worker spawning.
   
3. **Memory Pressure**: The 0.17.0 version uses significantly more memory
   (~2.4GB vs ~260MB), which may trigger worker recycling.

4. **Loky's Default Behavior**: Loky's `get_reusable_executor` doesn't
   guarantee worker persistence across separate `Parallel()` calls,
   especially when memory usage is high.

### Root Cause of 1.78x Slowdown

The slowdown is due to Numba JIT recompilation in Loky worker processes:
- HARK 0.17.0 has more Numba-decorated code than 0.14.1
- Each worker process must independently JIT compile this code
- Worker recycling during optimization causes repeated recompilation

## Additional Investigation (Sequential Execution)

### Sequential Execution Test

Tested using `multi_thread_commands_fake` (sequential) instead of parallel:
- **0.17.0 Sequential: 74 minutes** (vs 27 min parallel)
- Sequential is 2.7x slower than parallel for 0.17.0

This confirms that parallel execution IS helping despite JIT overhead.

### Single-Agent Solve() Performance

Profiled individual solve() calls (after JIT warmup):
- **0.14.1: 571ms per solve**
- **0.17.0: 204ms per solve** (2.8x FASTER!)

**Key Finding:** The core solver is actually FASTER in 0.17.0!

### Where Is the Slowdown?

Since solve() is faster but overall estimation is slower, the overhead must be in:
1. **Loky worker management** - spawning, serialization, recycling
2. **Memory pressure** - 0.17.0 uses ~2.4GB vs 0.14.1's ~260MB (9x more!)
3. **Object serialization** - larger objects take longer to serialize for workers
4. **Agent construction/simulation** - may have additional overhead

### Memory Usage Analysis

The 9x memory increase in 0.17.0 is likely causing:
1. More frequent garbage collection
2. Loky worker recycling (workers killed when memory is tight)
3. Slower serialization of larger agent objects
4. Cache pressure

### Potential Solutions

1. **Investigate memory bloat** - Find what's using 9x more memory in 0.17.0
2. **Reduce agent state** - Disable unnecessary tracking/history
3. **Use threading backend** - Avoids serialization (but has GIL issues)
4. **Optimize Loky settings** - Increase worker lifetime, reduce recycling
5. **Profile serialization** - Identify what's slow to serialize

### Conclusion

The 0.17.0 slowdown is NOT due to slower computation - it's due to:
- Parallelization overhead (Loky worker management)
- Memory pressure causing worker recycling
- Larger object serialization

The solver itself is 2.8x faster in 0.17.0, but this is negated by infrastructure overhead.

## Solution: Disable History Tracking

### The Fix

Added to `Estimation_BetaNablaSplurge.py`:
```python
BaseType.track_vars = []  # Disable history tracking
```

### Results After Optimization

| Version | Runtime | vs 0.14.1 |
|---------|---------|-----------|
| 0.14.1-bugfixed | 15.2 min | 1.0x |
| 0.17.0 (before) | 27.1 min | 1.78x slower |
| **0.17.0 (optimized)** | **21.5 min** | **1.41x slower** |

### Memory Impact

| Stage | Before | After | Reduction |
|-------|--------|-------|-----------|
| After simulate (7 agents) | 355 MB | 141 MB | 60% |

### Remaining Gap

The remaining 1.41x slowdown is due to:
1. **Construction overhead**: 136 MB vs 72 MB (1.9x more)
2. **Loky parallelization costs**: Worker spawning, serialization
3. **Additional validation/checking** in 0.17.0

### Recommendation

For HAFiscal and similar estimation workflows:
1. Set `track_vars = []` on all agents before simulation
2. Only enable tracking when history data is actually needed
3. Consider proposing this as a HARK default for estimation use cases
