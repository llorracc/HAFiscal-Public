"""
Solution cache smoke test.

Builds HS_Only, runs cached_eco_solve twice with the same params.
- First run: cache miss, solves + saves.
- Second run: cache hit, loads.
- Verifies cFunc values agree between the two on a query grid.

Run with:
    HAFISCAL_USE_SOLUTION_CACHE=1 python smoke_test.py
"""
import sys, os, time, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "FromPandemicCode"))
sys.path.insert(0, os.path.dirname(HERE))  # so `import solution_cache` works
sys.argv = [sys.argv[0]]

import numpy as np
from copy import deepcopy

# Force cache on
os.environ["HAFISCAL_USE_SOLUTION_CACHE"] = "1"

from welfare6_scenario import build_and_solve
from solution_cache import cached_eco_solve


def _eval_cfuncs(eco, m_query, M_query):
    """Evaluate cFunc[0] across all cohorts on (m_query, M_query). Returns
    list of np.ndarray, one per cohort."""
    out = []
    for agent in eco.agents:
        cf0 = agent.solution[0].cFunc[0]
        out.append(np.asarray(cf0(m_query, M_query)))
    return out


def main():
    print("=== Solution cache smoke test ===\n", flush=True)
    print("(1/3) Building HS_Only + first cached_eco_solve (expect MISS)...",
          flush=True)
    ctx = build_and_solve("HS_Only")
    t0 = time.time()
    r1 = cached_eco_solve(
        ctx, shock_type="recession",
        mc_method="hark_mc", seeds=(0,), use_shuffle=False,
        init_panel_method="newborn_pool", verbose=True,
    )
    print(f"  result: cache_hit={r1['cache_hit']}, "
          f"wall_total={time.time()-t0:.2f}s, "
          f"wall_inner={r1['wall']:.2f}s", flush=True)
    assert not r1["cache_hit"], "expected cache miss on first run"
    assert os.path.exists(r1["pkl_path"]), \
        f"cache pkl not written: {r1['pkl_path']}"
    pkl_path_first = r1["pkl_path"]
    print(f"  cache written to: {pkl_path_first}", flush=True)

    # Capture cFunc values
    m_q = np.linspace(0.5, 10.0, 30)
    M_q = np.full_like(m_q, 5.0)  # arbitrary aggregate M
    cf_first = _eval_cfuncs(ctx["AggEco"], m_q, M_q)

    print("\n(2/3) Rebuilding HS_Only + second cached_eco_solve (expect HIT)...",
          flush=True)
    ctx2 = build_and_solve("HS_Only")
    t0 = time.time()
    r2 = cached_eco_solve(
        ctx2, shock_type="recession",
        mc_method="hark_mc", seeds=(0,), use_shuffle=False,
        init_panel_method="newborn_pool", verbose=True,
    )
    print(f"  result: cache_hit={r2['cache_hit']}, "
          f"wall_total={time.time()-t0:.2f}s, "
          f"wall_inner={r2['wall']:.2f}s", flush=True)
    assert r2["cache_hit"], "expected cache hit on second run"

    cf_second = _eval_cfuncs(ctx2["AggEco"], m_q, M_q)

    print("\n(3/3) Comparing reconstructed cFunc vs original solve...", flush=True)
    all_ok = True
    for c_idx, (a, b) in enumerate(zip(cf_first, cf_second)):
        max_abs = np.max(np.abs(a - b))
        max_rel = np.max(np.abs((a - b) / np.maximum(np.abs(a), 1e-12)))
        ok = max_rel < 1e-6
        flag = "OK" if ok else "FAIL"
        print(f"  cohort {c_idx}: max_abs={max_abs:.2e}, max_rel={max_rel:.2e} [{flag}]",
              flush=True)
        if not ok:
            all_ok = False

    if all_ok:
        print("\n=== PASS ===")
        print(f"Cache file persists at: {pkl_path_first}", flush=True)
    else:
        print("\n=== FAIL ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
