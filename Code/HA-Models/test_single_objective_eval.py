#!/usr/bin/env python
"""
Test script to evaluate the objective function at a SINGLE point
and capture detailed intermediate values.
"""

import sys
import os
import numpy as np
import random
import json

# Determine which version
VERSION = os.environ.get('HAFISCAL_VERSION', 'unknown')
OUTPUT_DIR = '/tmp/hafiscal_debug_step1'
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"=" * 70)
print(f"SINGLE OBJECTIVE EVALUATION - Version: {VERSION}")
print(f"=" * 70)

# Setup paths
if VERSION == '0.14.1-bugfixed':
    BASE = '/home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-bugfixed'
elif VERSION == '0.17.0-native':
    BASE = '/home/econ-ark/GitHub/llorracc/HAFiscal-Latest'
else:
    print(f"ERROR: Unknown version {VERSION}")
    sys.exit(1)

sys.path.insert(0, f'{BASE}/Code/HA-Models')
sys.path.insert(0, f'{BASE}/Code/HA-Models/Target_AggMPCX_LiquWealth')
os.chdir(f'{BASE}/Code/HA-Models/Target_AggMPCX_LiquWealth')

# Set seeds
np.random.seed(12345)
random.seed(55)

# Test parameters - use the STARTING POINT from the optimization
TEST_SPLURGE = 0.24906992981618237
TEST_BETA = 0.9675474591463475
TEST_NABLA = 0.05782806961924406

print(f"\nTest Point:")
print(f"  splurge = {TEST_SPLURGE}")
print(f"  beta    = {TEST_BETA}")
print(f"  nabla   = {TEST_NABLA}")

# Import base parameters (but NOT the full estimation code)
from copy import deepcopy

try:
    from HARK.distribution import Uniform
except ImportError:
    from HARK.distributions import Uniform

# Check what consumer type to use
if VERSION == '0.14.1-bugfixed':
    from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
    AgentType = KinkedRconsumerType
else:
    # For 0.17.0, we need to check if RNGSyncKinkedRconsumerType exists
    try:
        from rng_synchronized_consumer import RNGSyncKinkedRconsumerType
        AgentType = RNGSyncKinkedRconsumerType
        print("Using RNGSyncKinkedRconsumerType for 0.17.0")
    except:
        from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
        AgentType = KinkedRconsumerType
        print("Using standard KinkedRconsumerType for 0.17.0")

TypeCount = 7

# Base params - NOR parametrization
_LivPrb = 1 - 1/160
_Rfree = 1.02**0.25

base_params = {
    'CRRA': 2.0,
    'Rfree': _Rfree,
    'Rsave': _Rfree,  # NOR: Rsave = Rfree
    'Rboro': 1.137**0.25,  # NOR: Rboro > Rsave
    'PermGroFac': [1.0],
    'PermGroFacAgg': 1.01**0.25,
    'BoroCnstArt': 0,  # No borrowing
    'CubicBool': False,
    'vFuncBool': False,
    'PermShkStd': [0.001**0.5],
    'PermShkCount': 5,
    'TranShkStd': [0.132**0.5],
    'TranShkCount': 5,
    'UnempPrb': 0.044,
    'IncUnemp': 0.60,
    'UnempPrbRet': None,
    'IncUnempRet': None,
    'aXtraMin': 0.00001,
    'aXtraMax': 20,
    'aXtraCount': 20,
    'aXtraExtra': [None],
    'aXtraNestFac': 3,
    'LivPrb': [_LivPrb],
    'DiscFac': 0.97,
    'cycles': 0,
    'T_cycle': 1,
    'T_retire': 0,
    'T_sim': 800,
    'T_age': None,
    'IndL': 10.0/9.0,
    'aNrmInitMean': np.log(0.00001),
    'aNrmInitStd': 0.0,
    'pLvlInitMean': 0.0,
    'pLvlInitStd': 0.0,
    'AgentCount': 5000,
}

print(f"\nBase parameters:")
print(f"  Rfree = {base_params['Rfree']}")
print(f"  Rsave = {base_params['Rsave']}")
print(f"  Rboro = {base_params['Rboro']}")
print(f"  BoroCnstArt = {base_params['BoroCnstArt']}")

# Build discount factor distribution
DiscFacDstn = Uniform(TEST_BETA - TEST_NABLA, TEST_BETA + TEST_NABLA).discretize(TypeCount)
beta_set = DiscFacDstn.atoms.flatten().copy()

# Apply GIC tapering
GICmaxBeta = (1-_LivPrb) + (base_params['PermGroFacAgg']**base_params['CRRA'])/_Rfree
minBeta = 0.01

print(f"\nGICmaxBeta: {GICmaxBeta}")
print(f"Raw beta_set: {beta_set}")

for j in range(TypeCount):
    taper_threshold = 0.01
    if beta_set[j] > GICmaxBeta - taper_threshold:
        beta_set[j] = GICmaxBeta - taper_threshold + (np.arctan((beta_set[j] - GICmaxBeta + taper_threshold)/taper_threshold))*taper_threshold/np.pi*2
    elif beta_set[j] < minBeta:
        beta_set[j] = minBeta

print(f"Tapered beta_set: {beta_set}")

# Create agents
print("\n" + "="*70)
print("Creating and solving agents...")
print("="*70)

agents = []
for j in range(TypeCount):
    params = deepcopy(base_params)
    params['DiscFac'] = beta_set[j]
    params['seed'] = 12345 + j
    
    agent = AgentType(**params)
    agent.solve()
    agents.append(agent)
    
    # Print solution info
    print(f"Agent {j}: DiscFac={beta_set[j]:.6f}, mNrmMin={agent.solution[0].mNrmMin:.6f}")

# Simulate
print("\n" + "="*70)
print("Simulating agents...")
print("="*70)

for j, agent in enumerate(agents):
    agent.initialize_sim()
    agent.simulate()

# Collect wealth
WealthNow = np.concatenate([agent.state_now["aLvl"] for agent in agents])
print(f"\nTotal agents: {len(WealthNow)}")
print(f"Mean wealth: {np.mean(WealthNow):.4f}")
print(f"Wealth percentiles (25,50,75): {np.percentile(WealthNow, [25,50,75])}")

# Compute K/Y ratio (simplified)
from HARK.utilities import get_percentiles, get_lorenz_shares

lorenz_target = np.array([0.029, 0.354, 1.84, 7.42])/100
lorenz_points = np.array([0.25, 0.50, 0.75, 0.99])  # Avoid 1.0 which may cause issues
try:
    lorenz_model = get_lorenz_shares(WealthNow, percentiles=lorenz_points)
except (ValueError, TypeError):
    # Different API versions
    try:
        lorenz_model = get_lorenz_shares(WealthNow, percentiles=lorenz_points*100)
    except:
        lorenz_model = np.array([0.0, 0.0, 0.0, 0.0])
        print("WARNING: Could not compute Lorenz shares")

print(f"\nLorenz shares (model): {lorenz_model}")
print(f"Lorenz shares (target): {lorenz_target}")

# Lorenz error
lorenz_err = np.sqrt(np.sum((lorenz_model - lorenz_target)**2))
print(f"Lorenz error: {lorenz_err}")

# K/Y ratio
KY_target = 6.60
# Simplified K/Y calculation (actual is more complex)
KY_model = np.mean(WealthNow)  # Placeholder
print(f"\nK/Y ratio (model, simplified): {KY_model:.4f}")
print(f"K/Y ratio (target): {KY_target}")

# Save detailed results
results = {
    'version': VERSION,
    'test_point': {
        'splurge': TEST_SPLURGE,
        'beta': TEST_BETA,
        'nabla': TEST_NABLA,
    },
    'base_params': {
        'Rfree': float(base_params['Rfree']),
        'Rsave': float(base_params['Rsave']),
        'Rboro': float(base_params['Rboro']),
        'BoroCnstArt': float(base_params['BoroCnstArt']),
    },
    'beta_set': beta_set.tolist(),
    'wealth_stats': {
        'mean': float(np.mean(WealthNow)),
        'std': float(np.std(WealthNow)),
        'percentiles': np.percentile(WealthNow, [10,25,50,75,90]).tolist(),
    },
    'lorenz_model': lorenz_model.tolist(),
    'lorenz_target': lorenz_target.tolist(),
    'lorenz_error': float(lorenz_err),
}

output_file = f"{OUTPUT_DIR}/single_eval_{VERSION}.json"
with open(output_file, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to: {output_file}")

print(f"\n{'='*70}")
print("TEST COMPLETE")
print(f"{'='*70}")
