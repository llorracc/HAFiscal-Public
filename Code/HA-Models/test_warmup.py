#!/usr/bin/env python
"""
Test script for the Loky pool warmup feature.

This script demonstrates the performance difference between:
1. Running WITHOUT pool warmup (slow first call)
2. Running WITH pool warmup (all calls fast)

Usage:
    # Without warmup (see ~4s first-call overhead)
    python test_warmup.py
    
    # With warmup (all calls ~0.3s after ~4s warmup)
    HARK_WARM_POOL=1 python test_warmup.py
"""

import os
import sys
import time

# Ensure clean environment
os.environ.setdefault('HARK_WARM_POOL', '0')

print("=" * 70)
print("Testing Loky Pool Warmup Feature")
print("=" * 70)
print(f"HARK_WARM_POOL = {os.environ.get('HARK_WARM_POOL', 'not set')}")
print()

# Force cold pool
try:
    from joblib.externals.loky import get_reusable_executor
    get_reusable_executor().shutdown(wait=True, kill_workers=True)
    print("Reset Loky pool to cold state")
except:
    pass
print()

# Import and run warmup if enabled
from parallel_warmup import maybe_warm_pool, is_warmup_enabled
from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType
from HARK.core import multi_thread_commands

if is_warmup_enabled():
    print("Pool warmup ENABLED")
    # num_agents must match number of agent types used in iterations (7)
    warmup_time = maybe_warm_pool(IndShockConsumerType, num_agents=7)
else:
    print("Pool warmup DISABLED")
    warmup_time = 0

print()
print("-" * 70)
print("Running 3 estimation iterations to show timing pattern")
print("-" * 70)

# Setup params
params = {
    'CRRA': 2.0,
    'Rfree': [1.01],
    'DiscFac': 0.96,
    'LivPrb': [0.99],
    'PermGroFac': [1.01],
    'PermShkStd': [0.1],
    'PermShkCount': 7,
    'TranShkStd': [0.1],
    'TranShkCount': 7,
    'UnempPrb': 0.05,
    'UnempPrbRet': 0.0,
    'IncUnemp': 0.3,
    'IncUnempRet': 0.0,
    'BoroCnstArt': 0.0,
    'tax_rate': 0.0,
    'T_retire': 0,
    'T_age': None,
    'T_cycle': 1,
    'cycles': 0,
    'AgentCount': 5000,
    'aXtraMin': 0.001,
    'aXtraMax': 40,
    'aXtraCount': 48,
    'aXtraNestFac': 3,
    'aXtraExtra': None,
    'vFuncBool': False,
    'CubicBool': False,
}

times = []
for i in range(3):
    # Create 7 agents (typical for estimation)
    agents = []
    for j in range(7):
        p = params.copy()
        p['DiscFac'] = 0.90 + 0.01 * j
        p['seed'] = 12345 + j
        agents.append(IndShockConsumerType(**p))
    
    t0 = time.time()
    multi_thread_commands(agents, ['solve()'])
    elapsed = time.time() - t0
    times.append(elapsed)
    print(f"  Iteration {i+1}: {elapsed:.3f}s")

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
total = warmup_time + sum(times)
print(f"Warmup time:      {warmup_time:.2f}s")
print(f"Iteration 1:      {times[0]:.2f}s {'(cold start)' if not is_warmup_enabled() else '(warmed)'}")
print(f"Iteration 2:      {times[1]:.2f}s")
print(f"Iteration 3:      {times[2]:.2f}s")
print(f"Total:            {total:.2f}s")
print()

if not is_warmup_enabled():
    print("TIP: Run with HARK_WARM_POOL=1 to see improved performance")
    print("     The warmup cost is paid once, then all iterations are fast.")
