"""Test parallel_eco_solve at Baseline 5x scale (21 cohorts).

1. Solve sequentially (HARK reference) — measure wall + capture solutions
2. Solve in parallel — measure wall + capture solutions
3. Compare cFunc evaluations bit-by-bit (should be identical)
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

# Set BLAS threads BEFORE importing numpy (avoid oversubscription with multiprocessing)
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')

import numpy as np
from copy import deepcopy
import welfare6_scenario as ws


def main():
    parametrization = os.environ.get('TEST_PARAM', 'HS_Only')
    n_workers_str = os.environ.get('TEST_N_WORKERS', 'auto')
    n_workers = (min(21, os.cpu_count() or 4) if n_workers_str == 'auto'
                  else int(n_workers_str))
    print(f"=== Parallel solve test: {parametrization}, n_workers={n_workers} ===")

    print(f"\nBuilding {parametrization}...")
    t0 = time.time()
    # Build with single worker first so sequential reference is clean
    ws._SOLVE_WORKERS = 1
    ctx = ws.build_and_solve(parametrization)
    AggEco = ctx['AggEco']
    print(f"  built+solved in {time.time()-t0:.2f}s, {len(AggEco.agents)} cohorts")

    # Switch to recession for a realistic solve target
    eco_s = deepcopy(AggEco)
    eco_s.switch_shock_type('recession')

    eco_p = deepcopy(AggEco)
    eco_p.switch_shock_type('recession')

    # Sequential: clear solutions, set workers=1
    ws._SOLVE_WORKERS = 1
    for a in eco_s.agents:
        a.solution = []  # empty list, not None (HARK len() check)
    print(f"\n[Sequential] solving {len(eco_s.agents)} cohorts ...")
    t0 = time.time()
    eco_s.solve()
    t_seq = time.time() - t0
    print(f"  seq: {t_seq:.2f}s")

    # Parallel: clear solutions, set workers=N
    ws._SOLVE_WORKERS = n_workers
    for a in eco_p.agents:
        a.solution = []
    print(f"\n[Parallel] solving {len(eco_p.agents)} cohorts (n_workers={n_workers}) ...")
    t0 = time.time()
    eco_p.solve()
    t_par = time.time() - t0
    print(f"  par: {t_par:.2f}s")
    ws._SOLVE_WORKERS = 1  # reset

    # Validate: per-cohort cFunc[j] should match bit-by-bit
    m_query = np.linspace(1.0, 10.0, 30)
    C_query = np.full(30, 1.0)
    print(f"\n=== Per-cohort cFunc comparison ===")
    n_pass = 0
    max_rel_overall = 0.0
    for c_idx, (a_s, a_p) in enumerate(zip(eco_s.agents, eco_p.agents)):
        sol_s = a_s.solution[0]
        sol_p = a_p.solution[0]
        if len(sol_s.cFunc) != len(sol_p.cFunc):
            print(f"  cohort {c_idx}: state count mismatch ({len(sol_s.cFunc)} vs {len(sol_p.cFunc)})")
            continue
        max_rel = 0.0
        for j in range(len(sol_s.cFunc)):
            c_s = sol_s.cFunc[j](m_query, C_query)
            c_p = sol_p.cFunc[j](m_query, C_query)
            denom = np.maximum(np.abs(c_s), 1e-12)
            rd = np.abs((c_p - c_s) / denom).max()
            max_rel = max(max_rel, rd)
        max_rel_overall = max(max_rel_overall, max_rel)
        passed = max_rel < 1e-10  # parallel should give IDENTICAL results
        n_pass += int(passed)
        mark = '✓' if passed else '✗'
        if c_idx < 5 or not passed:
            print(f"  cohort {c_idx:>2}: max rel diff = {max_rel:.4e} {mark}")
    print(f"\n=== Summary ===")
    print(f"  Sequential: {t_seq:.2f}s")
    print(f"  Parallel:   {t_par:.2f}s")
    print(f"  Speedup:    {t_seq/t_par:.2f}x")
    print(f"  Bit-identical: {n_pass}/{len(eco_s.agents)} cohorts")
    print(f"  Global max rel diff: {max_rel_overall:.4e}")
    if n_pass == len(eco_s.agents) and t_par < t_seq:
        print("\n✓ Parallel solve validated")
    elif n_pass != len(eco_s.agents):
        print(f"\n✗ {len(eco_s.agents)-n_pass} cohorts differ — parallel gave non-identical result")
    else:
        print(f"\n⚠ Parallel was not faster ({t_par:.1f}s vs {t_seq:.1f}s)")


if __name__ == '__main__':
    main()
