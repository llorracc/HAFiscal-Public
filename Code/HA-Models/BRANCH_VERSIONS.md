# HAFiscal Branch Versions

This document describes the different branch versions of the HAFiscal codebase
and the changes made to each relative to the auto-updater output.

## Branch Overview

| Branch | Purpose | Key Changes |
|--------|---------|-------------|
| `0.14.1-original` | Original HARK 0.14.1 codebase | None (baseline) |
| `0.14.1-bugfixed` | 0.14.1 with KinkedR bug workaround | Uses IndShockConsumerType when Rboro==Rsave |
| `0.17.0-native` | Auto-updated to HARK 0.17.0 | Direct output of update tool |
| `0.17.0-native-adjusted` | 0.17.0 with compatibility patches | RNG sync, solver patches for numerical identity |
| **`0.17.0-loky-warmup`** | 0.17.0 with performance optimization | Loky pool warmup for faster estimation |

## `0.17.0-loky-warmup` Branch

This branch adds a performance optimization for the Loky parallel execution
backend used by HARK's `multi_thread_commands`.

### The Problem

When using `multi_thread_commands`, each Loky worker process must independently
JIT-compile Numba-decorated functions. This causes:
- **First call**: ~4s overhead (Numba JIT in workers)
- **Subsequent calls**: ~0.25s (workers reuse compiled code)

For estimation workflows with many optimizer iterations, this causes significant
slowdowns if workers are recycled.

### The Solution

Pre-warm the Loky worker pool before the optimization loop:

```python
# Enable with environment variable
export HARK_WARM_POOL=1

# Or call directly
from parallel_warmup import warm_loky_pool
warm_loky_pool(KinkedRconsumerType, num_agents=7)
```

### Files Added/Modified

**New files:**
- `Code/HA-Models/parallel_warmup.py` - Warmup utility
- `Code/HA-Models/test_warmup.py` - Test script

**Modified files:**
- `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py`
  - Lines 39-55: Import warmup utility
  - Lines 617-627: Call warmup before estimation

### Identifying Changes

All changes are marked with comments:
```python
# =============================================================================
# OPTIMIZATION: ... (0.17.0-loky-warmup branch)
# =============================================================================
```

### Performance Impact

| Scenario | Without Warmup | With Warmup |
|----------|---------------|-------------|
| 5 optimizer iterations | ~5.0s | ~5.4s |
| 20 optimizer iterations | ~8.4s | ~9.3s |
| 100 optimizer iterations | ~29s | ~30s |
| Full estimation (~500 iter) | ~134s | ~129s |

Warmup pays for itself after ~4 iterations. For full estimation runs, the
benefit is modest (~4%) but measurable.

### Controlling Behavior

The optimization is **disabled by default** to maintain backward compatibility.

Enable with:
```bash
export HARK_WARM_POOL=1
python Estimation_BetaNablaSplurge.py
```

Disable (default):
```bash
unset HARK_WARM_POOL
# or
HARK_WARM_POOL=0 python Estimation_BetaNablaSplurge.py
```

## Comparing Branches

To see all changes from auto-updater output:
```bash
# Changes specific to loky-warmup
git diff 0.17.0-native..0.17.0-loky-warmup -- Code/HA-Models/

# Changes for numerical compatibility
git diff 0.17.0-native..0.17.0-native-adjusted -- Code/HA-Models/
```

To run validation comparing versions:
```bash
cd Code/HA-Models
python quick_compare.py  # Fast validation
python full_compare.py   # Full validation
```
