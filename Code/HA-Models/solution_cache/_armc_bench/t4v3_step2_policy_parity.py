"""T4 v3 (C3.5): Step-2 base-estimation-economy POLICY parity, flag-off
vs newton2d+numba — the NAMG-precedent form (test_step2_namg_base_solver
pattern). The full objective-readback form is blocked by a PRE-EXISTING
branch defect (PF-decay guard trip in calcAllResults, reproduced at
c545d2aa before all of today's changes — logged for owner adjudication).
Expected parity: ~1e-5 class (both converge to 1e-9-class fixed points on
the same grids; the NAMG-era bar was 5e-3 across a fixed-grid gap)."""
import os
import sys
import time

import numpy as np

# Path-agnostic (m5 portability, 2026-08-08): derive the repo root from
# this script's location (…/Code/HA-Models/solution_cache/_armc_bench/).
_REPO = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
FP = os.path.join(_REPO, "Code", "HA-Models", "FromPandemicCode")
sys.path.insert(0, FP)
sys.path.insert(0, os.path.join(_REPO, "Code", "HA-Models"))
os.chdir(FP)
os.environ["HAFISCAL_SKIP_ESTIMATION"] = "1"
sys.argv = sys.argv[:1]

import EstimAggFiscalMAIN as E  # noqa: E402

eco = E.AggDemandEconomy


def solve_arm(accel):
    if accel:
        os.environ["HAFISCAL_SOLVE_ACCEL"] = "newton2d"
        os.environ["HAFISCAL_NEWTON2D_KERNEL"] = "numba"
    else:
        for k in ("HAFISCAL_SOLVE_ACCEL", "HAFISCAL_NEWTON2D_KERNEL"):
            os.environ.pop(k, None)
    for ag in eco.agents:
        ag.MrkvArray_prev = None  # defeat solve_if_changed: force real solves
    from AggFiscalModel import AggregateDemandEconomy as _ADE
    print(f"[t4v3]   arm accel={accel}: router sees "
          f"method={_ADE._solve_accel_method()!r} "
          f"eco_class={type(eco).__name__} "
          f"solve_from={type(eco).solve.__module__}", flush=True)
    t0 = time.time()
    eco.solve()
    wall = time.time() - t0
    cf = [[ag.solution[0].cFunc[j]
           for j in range(np.asarray(ag.MrkvArray[0]).shape[0])]
          for ag in eco.agents]
    eng = sum(hasattr(ag, "_newton2d_cInterior") for ag in eco.agents)
    return wall, cf, eng


w_off, cf_off, _ = solve_arm(False)
w_on, cf_on, eng = solve_arm(True)
m = np.linspace(0.5, 12.0, 60)
ones = np.ones_like(m)
worst = 0.0
for ce, cn in zip(cf_off, cf_on):
    for j in range(len(ce)):
        c_e = np.asarray(ce[j](m, ones), dtype=float)
        c_n = np.asarray(cn[j](m, ones), dtype=float)
        worst = max(worst, float(np.max(np.abs(c_e - c_n))))
print(f"[t4v3] agents={len(eco.agents)} newton2d-engaged={eng} "
      f"wall off={w_off:.1f}s on={w_on:.1f}s "
      f"policy parity max|dc|={worst:.3e} (NAMG-era bar 5e-3)", flush=True)
print("[t4v3] DONE", flush=True)
