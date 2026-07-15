#!/usr/bin/env python3
"""
MC Determinism Test: Confirms that 0.14.1-bugfixed and 0.17.0-native produce
identical Monte Carlo simulation results when running single-threaded with
synchronized RNG.

This test evaluates the Step 2 estimation objective function at fixed parameter
points (the Nelder-Mead optimizer's initial values) with a reduced agent count
(500 instead of 50,000) for speed. Both HARK versions already use
multi_thread_commands_fake (sequential execution) in the estimation code.

The 0.17.0 version includes RNG synchronization in AggFiscalModel.py
(rng_sync_with_014=True) which replicates 0.14.1's RNG consumption pattern.

If both versions produce identical objective function values and per-agent
statistics, this proves that the only reason for discrepancies in the full
estimation is Monte Carlo noise from the optimizer exploring slightly different
paths (since results ARE deterministic at each evaluation point).

Usage:
    python mc_determinism_test.py              # Run both versions and compare
    python mc_determinism_test.py --compare    # Compare existing JSON results only

Can also be activated within EstimAggFiscalMAIN.py via:
    HAFISCAL_MC_DETERMINISM_TEST=1 python EstimAggFiscalMAIN.py
    python EstimAggFiscalMAIN.py --mc-test
"""

import json
import os
import sys
import subprocess
import time
import numpy as np

# Paths to the two codebases
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_014 = '/home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-bugfixed'
DIR_017 = '/home/econ-ark/GitHub/llorracc/HAFiscal-Latest'

# Results files
RESULTS_014 = os.path.join(DIR_014, 'Code/HA-Models/FromPandemicCode/Results/mc_determinism_test_results.json')
RESULTS_017 = os.path.join(DIR_017, 'Code/HA-Models/FromPandemicCode/Results/mc_determinism_test_results.json')

def run_version(version_dir, version_label):
    """Run the MC determinism test for one version."""
    print(f'\n{"="*70}')
    print(f'Running MC Determinism Test: {version_label}')
    print(f'Directory: {version_dir}')
    print(f'{"="*70}\n')
    
    venv_python = os.path.join(version_dir, '.venv', 'bin', 'python')
    if not os.path.exists(venv_python):
        venv_python = 'python3'
    
    script = os.path.join(version_dir, 'Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py')
    
    env = os.environ.copy()
    env['HAFISCAL_MC_DETERMINISM_TEST'] = '1'
    env['PYTHONUNBUFFERED'] = '1'
    env['NONINTERACTIVE'] = 'true'
    
    # Run from the FromPandemicCode directory (the script expects this)
    work_dir = os.path.join(version_dir, 'Code/HA-Models/FromPandemicCode')
    
    t0 = time.time()
    result = subprocess.run(
        [venv_python, script],
        cwd=work_dir,
        env=env,
        capture_output=False,  # Show output in real-time
        text=True,
    )
    elapsed = time.time() - t0
    
    if result.returncode != 0:
        print(f'\n[ERROR] {version_label} exited with code {result.returncode}')
        return False
    
    print(f'\n[OK] {version_label} completed in {elapsed:.1f}s')
    return True

def compare_results():
    """Compare MC determinism test results from both versions."""
    print(f'\n{"="*70}')
    print('COMPARING MC DETERMINISM TEST RESULTS')
    print(f'{"="*70}\n')
    
    if not os.path.exists(RESULTS_014):
        print(f'[ERROR] 0.14.1 results not found: {RESULTS_014}')
        return False
    if not os.path.exists(RESULTS_017):
        print(f'[ERROR] 0.17.0 results not found: {RESULTS_017}')
        return False
    
    with open(RESULTS_014) as f:
        r014 = json.load(f)
    with open(RESULTS_017) as f:
        r017 = json.load(f)
    
    # Check configuration matches
    print('Configuration:')
    for key in ['AgentCountTotal', 'Splurge', 'CRRA', 'Rfree', 'DiscFacCount']:
        v014 = r014.get(key)
        v017 = r017.get(key)
        match = '✓' if v014 == v017 else '✗ MISMATCH'
        print(f'  {key}: 0.14.1={v014}, 0.17.0={v017}  {match}')
    
    all_identical = True
    max_rel_diff = 0.0
    
    # Compare per-education-group evaluations
    print(f'\n{"="*70}')
    print('PER-EDUCATION-GROUP EVALUATIONS')
    print(f'{"="*70}')
    
    for e014, e017 in zip(r014['evaluations'], r017['evaluations']):
        name = e014['name']
        print(f'\n--- {name} (edType={e014["educ_type"]}) ---')
        
        # Compare scalar values
        for key in ['distance', 'beta', 'nabla', 'GICx']:
            v014 = e014[key]
            v017 = e017[key]
            if v014 == 0 and v017 == 0:
                rel_diff = 0.0
            elif v014 == 0:
                rel_diff = abs(v017)
            else:
                rel_diff = abs(v017 - v014) / abs(v014)
            identical = (v014 == v017)
            if not identical:
                all_identical = False
            max_rel_diff = max(max_rel_diff, rel_diff)
            status = '✓ IDENTICAL' if identical else f'✗ DIFFER (rel={rel_diff:.2e})'
            print(f'  {key:20s}: 0.14.1={v014:>15.10f}  0.17.0={v017:>15.10f}  {status}')
        
        # Compare array values
        for key in ['medianLWPI', 'avgLWPI', 'LWoPI', 'LorenzPts', 'WealthSharesByEd']:
            v014 = np.array(e014[key])
            v017 = np.array(e017[key])
            max_abs = np.max(np.abs(v017 - v014))
            denom = np.maximum(np.abs(v014), 1e-10)
            max_rel = np.max(np.abs(v017 - v014) / denom)
            identical = np.array_equal(v014, v017)
            if not identical:
                all_identical = False
            max_rel_diff = max(max_rel_diff, max_rel)
            status = '✓ IDENTICAL' if identical else f'✗ max_rel={max_rel:.2e}'
            print(f'  {key:20s}: {status}')
            if not identical:
                print(f'    0.14.1: {v014}')
                print(f'    0.17.0: {v017}')
        
        # Compare per-agent snapshots
        print(f'\n  Per-agent snapshots ({len(e014["agent_snapshots"])} agents):')
        n_differ = 0
        max_agent_diff = 0.0
        for s014, s017 in zip(e014['agent_snapshots'], e017['agent_snapshots']):
            for metric in ['mean_aNrm', 'mean_cNrm', 'mean_pLvl', 'mean_mNrm', 'std_aNrm']:
                v014 = s014[metric]
                v017 = s017[metric]
                if v014 != v017:
                    n_differ += 1
                    denom = abs(v014) if abs(v014) > 1e-10 else 1e-10
                    rd = abs(v017 - v014) / denom
                    max_agent_diff = max(max_agent_diff, rd)
                    max_rel_diff = max(max_rel_diff, rd)
        if n_differ == 0:
            print(f'    ✓ ALL agent statistics IDENTICAL')
        else:
            all_identical = False
            print(f'    ✗ {n_differ} agent-metric pairs differ (max rel diff = {max_agent_diff:.2e})')
            # Print the first few differences
            count = 0
            for s014, s017 in zip(e014['agent_snapshots'], e017['agent_snapshots']):
                for metric in ['mean_aNrm', 'mean_cNrm', 'mean_pLvl', 'mean_mNrm', 'std_aNrm']:
                    v014 = s014[metric]
                    v017 = s017[metric]
                    if v014 != v017 and count < 10:
                        denom = abs(v014) if abs(v014) > 1e-10 else 1e-10
                        rd = abs(v017 - v014) / denom
                        print(f'      Agent {s014["idx"]}, {metric}: 0.14.1={v014:.10f}, 0.17.0={v017:.10f} (rel={rd:.2e})')
                        count += 1
    
    # Compare population-level results
    print(f'\n{"="*70}')
    print('POPULATION-LEVEL EVALUATION')
    print(f'{"="*70}')
    
    pd014 = r014.get('population_distance', None)
    pd017 = r017.get('population_distance', None)
    if pd014 is not None and pd017 is not None:
        identical = (pd014 == pd017)
        if pd014 == 0:
            rel_diff = abs(pd017)
        else:
            rel_diff = abs(pd017 - pd014) / abs(pd014)
        max_rel_diff = max(max_rel_diff, rel_diff)
        if not identical:
            all_identical = False
        status = '✓ IDENTICAL' if identical else f'✗ DIFFER (rel={rel_diff:.2e})'
        print(f'  pop_distance: 0.14.1={pd014:.10f}  0.17.0={pd017:.10f}  {status}')
    
    # Final verdict
    print(f'\n{"="*70}')
    print('VERDICT')
    print(f'{"="*70}')
    
    if all_identical:
        print('\n  ✓✓✓  ALL RESULTS ARE BIT-FOR-BIT IDENTICAL  ✓✓✓')
        print('\n  This confirms that the ONLY source of discrepancy in the full')
        print('  estimation is Monte Carlo noise from the optimizer exploring')
        print('  different paths. When given identical inputs and deterministic')
        print('  execution, both HARK versions produce identical outputs.')
    else:
        print(f'\n  ✗ Results DIFFER (max relative difference: {max_rel_diff:.2e})')
        if max_rel_diff < 1e-10:
            print('\n  Differences are at machine epsilon level — effectively identical.')
            print('  The tiny discrepancies are likely floating-point rounding.')
        elif max_rel_diff < 1e-6:
            print('\n  Differences are very small but above machine epsilon.')
            print('  This may indicate minor floating-point ordering differences.')
        else:
            print('\n  ✗ SIGNIFICANT DIFFERENCES DETECTED.')
            print('  This indicates incomplete RNG synchronization or a bug.')
            print('  The discrepancies in the full estimation are NOT purely')
            print('  Monte Carlo noise — there is a systematic difference.')
    
    print(f'\n  Max relative difference across all comparisons: {max_rel_diff:.2e}')
    print()
    
    return all_identical

def main():
    compare_only = '--compare' in sys.argv
    
    if not compare_only:
        # Run both versions
        ok_014 = run_version(DIR_014, '0.14.1-bugfixed')
        if not ok_014:
            print('\n[FATAL] 0.14.1 failed. Cannot continue.')
            sys.exit(1)
        
        ok_017 = run_version(DIR_017, '0.17.0-native')
        if not ok_017:
            print('\n[FATAL] 0.17.0 failed. Cannot continue.')
            sys.exit(1)
    
    # Compare results
    identical = compare_results()
    
    sys.exit(0 if identical else 1)

if __name__ == '__main__':
    main()
