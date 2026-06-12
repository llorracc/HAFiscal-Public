# Numba JIT Recompilation Overhead in `multi_thread_commands`

## Issue Summary

When using HARK's `multi_thread_commands` with the default Loky backend, each worker process must independently JIT-compile Numba-decorated functions. This causes significant performance overhead, especially for the first call in a session.

## Observed Behavior

| Backend | First Call | Subsequent Calls | Notes |
|---------|-----------|-----------------|-------|
| Loky (cold start) | **~4.0s** | ~0.27s | Each worker JITs independently |
| Loky (warm pool) | ~0.28s | ~0.27s | **Fastest when pool persists** |
| Threading | ~1.4s | ~1.4s | GIL contention, slower than sequential |
| Sequential | ~1.0s | ~1.0s | Baseline, no parallelism |

**Key insight**: Loky with a warm pool is **3-4x faster** than sequential! The problem is the ~4s cold-start overhead when workers must JIT-compile Numba code.

## Root Cause

The Loky backend spawns separate Python processes that don't share the Numba JIT cache from the main process. Each worker must independently compile Numba functions when they are first called. HARK uses Numba in several performance-critical functions, causing this overhead to accumulate.

### Evidence

When running with Loky backend, the Numba deprecation warnings appear **multiple times** (once per worker):

```
/path/to/numba/core/decorators.py:262: NumbaDeprecationWarning: numba.generated_jit is deprecated...
  warnings.warn(msg, NumbaDeprecationWarning)
/path/to/numba/core/decorators.py:262: NumbaDeprecationWarning: numba.generated_jit is deprecated...
  warnings.warn(msg, NumbaDeprecationWarning)
[... repeated for each worker ...]
```

This confirms that Numba's JIT compilation is occurring in each worker process independently.

## Impact

For estimation workflows that call `multi_thread_commands` many times (e.g., during parameter optimization with scipy.optimize), this can result in **2x or greater slowdown** compared to:
1. Sequential execution
2. Threading backend
3. Pre-warmed Loky workers

### Real-World Example

In HAFiscal's splurge estimation workflow:
- HARK 0.14.1: ~13 minutes
- HARK 0.17.0: ~28 minutes (2.1x slower)

The slowdown is due to Loky worker pool recycling during optimization iterations.

## Reproduction

### Prerequisites

```bash
pip install econ-ark>=0.17.0
```

### Run the MWE

```bash
python mwe_numba_jit_overhead.py
```

### Expected Output

The script will benchmark different parallelization backends and display:
1. Per-trial timing for each backend
2. Summary comparison table
3. Analysis of the root cause

## Proposed Solutions

### Option A: Use Threading Backend

**Change:**
```python
# In HARK/core.py, modify multi_thread_commands:
agent_list_out = Parallel(n_jobs=num_jobs, backend='threading')(
    delayed(run_commands)(*args)
    for args in zip(agent_list, len(agent_list) * [command_list])
)
```

**Pros:**
- No JIT recompilation overhead
- Consistent performance across calls
- Simpler debugging (shared memory)

**Cons:**
- **GIL contention makes it SLOWER than sequential!** (1.4s vs 1.0s per call)
- Not recommended for CPU-bound work despite Numba releasing GIL
- Memory sharing issues if agents are modified

**Benchmark Results:**
- First call: 1.4s
- Subsequent: 1.4s
- **Total for 5 iterations: 7.2s (vs 4.9s sequential, vs 1.4s warm Loky)**

**NOT RECOMMENDED** - threading is actually slower than sequential for this workload.

### Option B: Add Backend Parameter to `multi_thread_commands`

**Change:**
```python
def multi_thread_commands(
    agent_list: List, 
    command_list: List, 
    num_jobs=None,
    backend='loky'  # NEW: Allow user to choose backend
) -> None:
    ...
    agent_list_out = Parallel(n_jobs=num_jobs, backend=backend)(...)
```

**Pros:**
- Backward compatible
- Users can choose based on their workflow
- Easy to test different backends

**Cons:**
- Requires users to understand the tradeoff
- Doesn't fix the default behavior

### Option C: Configure Loky for Persistent Workers

**Change:**
```python
from joblib import parallel_backend, Parallel, delayed

# Set Loky to reuse workers more aggressively
with parallel_backend('loky', inner_max_num_threads=1):
    agent_list_out = Parallel(
        n_jobs=num_jobs,
        prefer='processes',
        batch_size='auto',  # Group work to reduce overhead
    )(...)
```

**Pros:**
- Maintains process isolation
- Can still benefit from cached JIT in reused workers

**Cons:**
- Complex configuration
- May still have first-call overhead
- Loky worker lifecycle not fully controllable

### splurge-in-budget: Enable Numba Disk Cache

**Change:**
Add to HARK startup or documentation:
```python
import os
os.environ['NUMBA_CACHE_DIR'] = '/tmp/numba_cache'
# or in .numbarc: cache = True
```

**Pros:**
- Numba automatically caches compiled code to disk
- Workers can load cached code instead of recompiling
- Persists across sessions

**Cons:**
- First-ever run still slow
- Disk I/O overhead
- Cache invalidation complexity
- Requires user configuration

### Option E: Pre-Warm Worker Pool

**Change:**
```python
def warm_numba_cache(agent_list):
    """Pre-compile Numba functions in workers before optimization."""
    # Run a minimal solve to trigger JIT compilation
    dummy_agent = agent_list[0].__class__(**minimal_params)
    multi_thread_commands([dummy_agent], ['solve()'])
```

**Pros:**
- One-time warmup cost
- Subsequent calls fast

**Cons:**
- Requires explicit call by user
- Workers may still be recycled during long optimizations
- Doesn't solve root cause

## Recommendation

Based on benchmarks, **Loky with a warm worker pool is 3-4x faster** than all other approaches. The problem is only the cold-start JIT overhead.

**Short-term (Recommended):**
1. **Implement Option B** - Add `backend` parameter to `multi_thread_commands` 
2. **Implement Option E** - Provide a `warm_parallel_pool()` utility function
3. **Document** that users should call `warm_parallel_pool()` before optimization loops

**Medium-term:**
- Enable Numba disk caching by default (`NUMBA_CACHE_DIR`)
- This persists JIT compilation across sessions

**Long-term:**
- Consider using `joblib.Memory` or similar caching for worker persistence
- Investigate Loky timeout/keepalive settings

**NOT Recommended:**
- Threading backend (slower than sequential due to GIL contention)
- Always using sequential (loses 3-4x performance benefit of warm Loky)

## Files

- `mwe_numba_jit_overhead.py` - Main benchmark script
- `mwe_loky_isolation.py` - Demonstrates worker pool isolation
- `mwe_proposed_fixes.py` - Compares proposed solutions
- `README.md` - This documentation

## Related Issues

- [Joblib Loky Backend Documentation](https://joblib.readthedocs.io/en/latest/parallel.html)
- [Numba Caching](https://numba.readthedocs.io/en/stable/developer/caching.html)
