"""
AD-converged cache smoke test.

Builds HS_Only, runs cached_solve_ad_recession twice.
- First run: cache miss, runs full AD loop, saves.
- Second run: cache hit, loads in seconds.
- Verifies Cratio_hist and per-cohort cFunc agree between the two.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "FromPandemicCode"))
sys.path.insert(0, os.path.dirname(HERE))
sys.argv = [sys.argv[0]]

import numpy as np

os.environ["HAFISCAL_USE_SOLUTION_CACHE"] = "1"

from welfare6_scenario import build_and_solve, run_base
from solution_cache import cached_solve_ad_recession


def _eval_cfunc_per_cohort(eco, m_q, M_q):
    return [np.asarray(ag.solution[0].cFunc[0](m_q, M_q))
            for ag in eco.agents]


def main():
    print("=== AD-converged cache smoke test ===\n", flush=True)

    print("(1/3) Build HS_Only + first cached_solve_ad_recession (expect MISS)...",
          flush=True)
    ctx = build_and_solve("HS_Only")
    _ = run_base(ctx)
    base_AggCons = ctx["AggEco"].base_AggCons

    t0 = time.time()
    r1 = cached_solve_ad_recession(
        ctx, base_AggCons,
        num_max_iterations=3,
        convergence_cutoff=1e-9,
        shock_type="recession",
        mc_method="jax_mc_2d_vmap",
        seeds=(0, 1), use_shuffle=False,
        verbose=True,
    )
    wall1 = time.time() - t0
    print(f"  wall_total={wall1:.2f}s, converged={r1.get('converged')}, "
          f"Cratio[0]={float(r1['final_Cratio_hist'][0]):.6f}", flush=True)

    m_q = np.linspace(0.5, 10.0, 30)
    M_q = np.full_like(m_q, 5.0)
    cf_first = _eval_cfunc_per_cohort(ctx["AggEco"], m_q, M_q)
    Cratio_first = np.asarray(r1["final_Cratio_hist"])

    print("\n(2/3) Rebuild HS_Only + second cached_solve_ad_recession (expect HIT)...",
          flush=True)
    ctx2 = build_and_solve("HS_Only")
    _ = run_base(ctx2)
    base_AggCons2 = ctx2["AggEco"].base_AggCons

    t0 = time.time()
    r2 = cached_solve_ad_recession(
        ctx2, base_AggCons2,
        num_max_iterations=3,
        convergence_cutoff=1e-9,
        shock_type="recession",
        mc_method="jax_mc_2d_vmap",
        seeds=(0, 1), use_shuffle=False,
        verbose=True,
    )
    wall2 = time.time() - t0
    print(f"  wall_total={wall2:.2f}s", flush=True)

    cf_second = _eval_cfunc_per_cohort(ctx2["AggEco"], m_q, M_q)
    Cratio_second = np.asarray(r2["final_Cratio_hist"])

    print("\n(3/3) Comparing cached load vs original AD run...", flush=True)
    cratio_max_rel = np.max(np.abs(
        (Cratio_first - Cratio_second) / np.maximum(np.abs(Cratio_first), 1e-12)))
    print(f"  Cratio_hist: max rel diff = {cratio_max_rel:.2e}",
          flush=True)
    all_ok = cratio_max_rel < 1e-6
    for c_idx, (a, b) in enumerate(zip(cf_first, cf_second)):
        max_abs = np.max(np.abs(a - b))
        max_rel = np.max(np.abs((a - b) / np.maximum(np.abs(a), 1e-12)))
        ok = max_rel < 1e-6
        flag = "OK" if ok else "FAIL"
        print(f"  cohort {c_idx} cFunc[0]: max_abs={max_abs:.2e}, "
              f"max_rel={max_rel:.2e} [{flag}]", flush=True)
        if not ok:
            all_ok = False

    print(f"\nWall MISS->HIT: {wall1:.2f}s -> {wall2:.2f}s "
          f"({wall1/max(wall2, 1e-6):.1f}x speedup)")
    if all_ok:
        print("=== PASS ===")
    else:
        print("=== FAIL ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
