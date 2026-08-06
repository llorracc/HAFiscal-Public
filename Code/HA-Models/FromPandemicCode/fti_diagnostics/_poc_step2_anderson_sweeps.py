"""Step-2 solver A/B (DIAGNOSTIC): EGM sweeps vs multi-state Anderson sweeps on the ACTUAL
Step-2 cohort calibrations — cold AND warm-started (the Step-2 NM reuse case).

The Step-2 profiler (_poc_step2_profile.py) showed the warm solve is ~27% of each objective
evaluation at production N, and is dominated by slow high-patience atoms (EGM sweeps 38-545).
This closes the loop: for each education cohort's SLOWEST (highest-beta) atom, how many sweeps
does the reliable multi-state Anderson contraction (solve_stationary_NAMG_markov, method=
'anderson') need vs stock HARK EGM, and does it reach the same policy?

  - COLD: c_init=None (first solve / cold start).
  - WARM: c_init = EGM-converged policy perturbed for a small beta step (the Step-2 NM reuse
    pattern: beta barely moves between Nelder-Mead evaluations).

Run (from FromPandemicCode/):
  PYTHONPATH=. HAFISCAL_SKIP_ESTIMATION=1 <python> fti_diagnostics/_poc_step2_namg_sweeps.py
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np

os.environ.setdefault("HAFISCAL_SKIP_ESTIMATION", "1")

_HERE = os.path.dirname(os.path.abspath(__file__))
_FROMPANDEMIC = os.path.normpath(os.path.join(_HERE, ".."))
for _p in (_HERE, _FROMPANDEMIC, os.path.normpath(os.path.join(_FROMPANDEMIC, ".."))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _poc_mm5_aggfiscal_parity import _egm_reference, _scalar  # noqa: E402


def _measure_cohort(name, agent, solve_stationary_NAMG_markov):
    MrkvArray = np.asarray(agent.MrkvArray[0], dtype=float)
    S = MrkvArray.shape[0]
    IncShkDstn = agent.IncShkDstn[0]
    BoroCnstArt = _scalar(agent.BoroCnstArt)
    CRRA = float(agent.CRRA)
    DiscFac = float(agent.DiscFac)
    LivPrb = _scalar(agent.LivPrb)
    Rfree = _scalar(agent.Rfree)
    PermGroFac = _scalar(agent.PermGroFac)
    aXtraGrid = np.asarray(agent.aXtraGrid, dtype=float)
    aXtraMin = _scalar(agent.aXtraMin)
    aXtraMax = _scalar(agent.aXtraMax)
    aXtraCount = int(agent.aXtraCount)
    aXtraNestFac = int(getattr(agent, "aXtraNestFac", 3))

    print(f"\n=== {name}: DiscFac={DiscFac:.5f}  S={S}  BoroCnstArt={BoroCnstArt!r}  "
          f"aXtra[{aXtraGrid.size}] max={aXtraMax:g} ===", flush=True)
    if abs(BoroCnstArt) > 1e-12:
        print("  BoroCnstArt != 0 -> NAMG-markov n/a; skipping.", flush=True)
        return None

    # --- EGM reference (stock HARK MarkovConsumerType), count sweeps + wall ---
    t0 = time.time()
    egm = _egm_reference(MrkvArray, IncShkDstn, LivPrb, DiscFac, CRRA, Rfree, PermGroFac,
                         BoroCnstArt, aXtraMin, aXtraMax, aXtraCount, aXtraNestFac)
    egm_wall = time.time() - t0
    egm_sweeps = int(getattr(egm, "completed_cycles", -1))
    egm_cFuncs = list(egm.solution[0].cFunc)
    print(f"  EGM (HARK): {egm_sweeps} sweeps, {egm_wall:.2f}s", flush=True)

    # --- Anderson COLD ---
    t0 = time.time()
    a_cold = solve_stationary_NAMG_markov(
        MrkvArray, IncShkDstn, LivPrb, DiscFac, CRRA, Rfree, PermGroFac,
        BoroCnstArt, aXtraGrid, method="anderson", verbose=False,
    )
    cold_wall = time.time() - t0
    cold_iters = a_cold.completed_cycles  # (warm, iters)
    cold_conv = bool(a_cold.namg_converged)

    # parity EGM vs Anderson-cold on the ergodic region
    m = np.linspace(0.5, 12.0, 60)
    worst = 0.0
    for s in range(S):
        dc = float(np.max(np.abs(np.asarray(egm_cFuncs[s](m)) - np.asarray(a_cold.cFunc[s](m)))))
        worst = max(worst, dc)

    # --- Anderson WARM (Step-2 reuse): c_init = EGM policy on the NAMG grid ---
    c_init = np.array([np.asarray(egm_cFuncs[s](aXtraGrid), dtype=float) for s in range(S)])
    t0 = time.time()
    a_warm = solve_stationary_NAMG_markov(
        MrkvArray, IncShkDstn, LivPrb, DiscFac, CRRA, Rfree, PermGroFac,
        BoroCnstArt, aXtraGrid, method="anderson", verbose=False, c_init=c_init,
    )
    warm_wall = time.time() - t0
    warm_iters = a_warm.completed_cycles

    print(f"  Anderson COLD: iters={cold_iters} converged={cold_conv} {cold_wall:.2f}s | "
          f"parity max|dc|={worst:.2e}", flush=True)
    print(f"  Anderson WARM (c_init=EGM policy): iters={warm_iters} {warm_wall:.2f}s", flush=True)
    if egm_sweeps > 0 and isinstance(cold_iters, tuple):
        print(f"  >>> COLD sweep ratio EGM/Anderson = {egm_sweeps}/{sum(cold_iters)} "
              f"= x{egm_sweeps/max(sum(cold_iters),1):.1f}", flush=True)
    return dict(name=name, DiscFac=DiscFac, egm_sweeps=egm_sweeps,
                cold_iters=cold_iters, warm_iters=warm_iters, parity=worst)


def main():
    import _hark_fti_path  # noqa: F401  -- locate the external fast-time-iteration `hark_fti`
    from hark_fti.global_newton_markov import solve_stationary_NAMG_markov
    print("Importing EstimAggFiscalMAIN (builds Step-2 economy; one-time)...", flush=True)
    import EstimAggFiscalMAIN as E

    DFC = int(E.DiscFacCount)
    agents = E.AggDemandEconomy.agents
    cohorts = {0: "Dropout", 1: "Highschool", 2: "College"}
    rows = []
    for e, nm in cohorts.items():
        # slowest atom = highest DiscFac = last index in the cohort block
        slow = agents[e * DFC + (DFC - 1)]
        r = _measure_cohort(f"{nm} (slowest atom)", slow, solve_stationary_NAMG_markov)
        if r:
            rows.append(r)

    print("\n" + "=" * 78, flush=True)
    print("STEP-2 SOLVER A/B SUMMARY (slowest atom per cohort)", flush=True)
    print(f"{'cohort':>14} {'beta':>8} {'EGM sweeps':>11} {'Anderson cold':>14} "
          f"{'Anderson warm':>14} {'parity':>10}", flush=True)
    for r in rows:
        cold = sum(r["cold_iters"]) if isinstance(r["cold_iters"], tuple) else r["cold_iters"]
        warm = sum(r["warm_iters"]) if isinstance(r["warm_iters"], tuple) else r["warm_iters"]
        print(f"{r['name'].split()[0]:>14} {r['DiscFac']:>8.4f} {r['egm_sweeps']:>11} "
              f"{cold:>14} {warm:>14} {r['parity']:>10.1e}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
