"""AD-loop Anderson PoC (DIAGNOSTIC, not production): does Anderson-accelerating the
Aggregate-Demand outer fixed-point loop reach the SAME fixed point as the stock damped
Picard loop, in fewer outer iterations?

The AD loop in ``AggregateDemandEconomy.solve_ad_recession`` is a damped-Picard fixed point
in the aggregate ``CFunc`` (driven by ``Cratio_hist``). The opt-in ``HAFISCAL_AD_ANDERSON``
branch (default OFF) mixes the recent CFunc-parameter residual history via least-squares.
``solve_ad_recession`` resets ``CFunc`` to the flat guess at the top of every call, so two
sequential calls on one economy are a clean, deterministic A/B (same map G, same seeds).

This builds ONE HS_Only economy, runs the stock loop then the Anderson loop on the SAME
``shock_type``, and reports: outer-iteration count, converged flag, and per-period max|dCratio|
between the two converged ``Cratio_hist`` paths. NO production behavior changes (the branch is
opt-in and toggled from here).

Run (from FromPandemicCode/):
  PYTHONPATH=. HAFISCAL_SIM_METHOD=MC <python> fti_diagnostics/_poc_ad_anderson.py [shock_type]
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_FROMPANDEMIC = os.path.normpath(os.path.join(_HERE, ".."))
for _p in (_FROMPANDEMIC, os.path.normpath(os.path.join(_FROMPANDEMIC, ".."))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Take the shock type from argv but DO NOT leave it in sys.argv: EstimParameters reads
# sys.argv[1:] as numeric Rfree/CRRA/IncUnemp on import, so a non-float there crashes it.
SHOCK = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("POC_AD_SHOCK", "recession")
sys.argv = sys.argv[:1]


def _run(eco, anderson, maxit, cutoff):
    eco.ad_anderson = bool(anderson)
    t0 = time.time()
    eco.solve_ad_recession(maxit, convergence_cutoff=cutoff, name=None, shock_type=SHOCK)
    dt = time.time() - t0
    return dict(
        iters=int(eco._ad_last_iters),
        converged=bool(eco._ad_last_converged),
        cratio=np.array(eco._ad_last_cratio_hist, dtype=float),
        total_diff=float(eco._ad_last_total_diff),
        secs=dt,
    )


def main():
    from copy import deepcopy

    import welfare6_scenario as ws

    print(f"Building HS_Only economy for AD-loop PoC (shock_type={SHOCK!r})...", flush=True)
    ctx = ws.build_and_solve("HS_Only")
    ws.run_base(ctx)  # base results / base_AggCons, matching production ordering
    maxit = int(os.environ.get("POC_AD_MAXIT", str(ctx["num_max_iterations_solvingAD"])))
    cutoff = float(os.environ.get("POC_AD_CUTOFF", str(ctx["convergence_tol_solvingAD"])))
    print(f"  built; {len(ctx['AggEco'].agents)} cohort agent(s). "
          f"maxit={maxit} cutoff={cutoff:g}", flush=True)

    # Mirror run_recession_AD's setup: deepcopy + switch_shock_type sets the recession
    # Markov dimensions (CFunc grows to the multi-macro-state size). A fresh eco per arm
    # guarantees identical starting state for the A/B (solve_ad_recession also resets
    # CFunc to the flat guess at the top of every call).
    print("\n=== STOCK damped-Picard AD loop ===", flush=True)
    eco_s = deepcopy(ctx["AggEco"])
    eco_s.switch_shock_type(SHOCK)
    stock = _run(eco_s, anderson=False, maxit=maxit, cutoff=cutoff)

    print("\n=== Anderson-accelerated AD loop ===", flush=True)
    eco_a = deepcopy(ctx["AggEco"])
    eco_a.switch_shock_type(SHOCK)
    andr = _run(eco_a, anderson=True, maxit=maxit, cutoff=cutoff)

    n = min(stock["cratio"].size, andr["cratio"].size)
    dcr = float(np.max(np.abs(stock["cratio"][:n] - andr["cratio"][:n])))

    print("\n" + "=" * 64, flush=True)
    print(f"shock_type = {SHOCK}", flush=True)
    print(f"  STOCK    : {stock['iters']:3d} iters  converged={stock['converged']}  "
          f"final_diff={stock['total_diff']:.2e}  {stock['secs']/60:.1f} min", flush=True)
    print(f"  ANDERSON : {andr['iters']:3d} iters  converged={andr['converged']}  "
          f"final_diff={andr['total_diff']:.2e}  {andr['secs']/60:.1f} min", flush=True)
    if andr["iters"] > 0:
        print(f"  outer-iteration speedup : x{stock['iters']/max(andr['iters'],1):.2f}", flush=True)
    print(f"  max|dCratio| (converged paths) = {dcr:.3e}", flush=True)
    ok = stock["converged"] and andr["converged"] and dcr < 5e-3 and andr["iters"] <= stock["iters"]
    print(("PASS" if ok else "FAIL")
          + "  (same fixed point < 5e-3 AND Anderson not slower in iters)", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
