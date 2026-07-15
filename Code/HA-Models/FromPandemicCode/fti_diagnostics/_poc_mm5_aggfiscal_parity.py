"""MM5/MM6 parity PoC (DIAGNOSTIC, not production): multi-state FTI solvers — global-Newton
(NAMG) and the licence-clean Tier-C ConsumedATI — vs HARK-EGM on a REAL HAFiscal baseline
``AggFiscalType`` per-period Markov solve.

Both candidates were validated on toy calibrations (White smooth income; a standalone 4-state
chain — the ConsumedATI bake-off measured ×4.31 vs EGM at HAFiscal-College's real calibration
on that 4-state proxy). This PoC closes the harness gap (Option 1, plan
fast-time-iteration/plans/20260621-1711h): do they reproduce the EGM policy on the ACTUAL
HS_Only baseline state structure (6 micro states, bug_fix UI encoding) and calibration, and
at what wall-clock — the right *regime* AND the right *harness* (a real per-period problem; no
AD loop / recession state space yet — that is the next cascade tier).

It builds one HS_Only baseline economy via ``welfare6_scenario.build_and_solve`` (the
``shock_type="base"`` stationary Markov solve), pulls the first solved cohort's Markov inputs,
solves a stock HARK ``MarkovConsumerType`` EGM reference on the same inputs, then runs both
``solve_stationary_NAMG_markov`` and ``solve_stationary_ConsumedATI_markov`` and reports, per
solver: cFunc parity vs EGM on the ergodic region, the FULL consumed(a) Euler residual
(``info['fnorm']`` for ConsumedATI — the masking-bug guard), iterations, wall, and ×-EGM
speedup. NO production code is modified and nothing is grafted — this only measures.

Run (from FromPandemicCode/):
  PYTHONPATH=. <python> fti_diagnostics/_poc_mm5_aggfiscal_parity.py
  POC_NAMG_METHOD=newton  (default; 'anderson' = the deprecated contraction)
"""
from __future__ import annotations

import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_FROMPANDEMIC = os.path.normpath(os.path.join(_HERE, ".."))
for _p in (_FROMPANDEMIC, os.path.normpath(os.path.join(_FROMPANDEMIC, ".."))):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _scalar(v, i=0):
    arr = np.asarray(v)
    return float(arr.reshape(-1)[i]) if arr.size > 1 else float(arr.reshape(-1)[0])


def _egm_reference(MrkvArray, IncShkDstn, LivPrb, DiscFac, CRRA, Rfree, PermGroFac,
                   BoroCnstArt, aXtraMin, aXtraMax, aXtraCount, aXtraNestFac):
    """Stock HARK MarkovConsumerType EGM solve on the EXACT extracted HS_Only inputs."""
    from copy import deepcopy
    from HARK.ConsumptionSaving.ConsMarkovModel import (
        MarkovConsumerType, init_indshk_markov,
    )
    from HARK.distributions import DiscreteDistributionLabeled
    S = MrkvArray.shape[0]
    # Stock MarkovConsumerType's EGM solver indexes shocks by name (S["PermShk"]); the
    # HAFiscal unemployment IncShkDstn entries are plain positional DiscreteDistributions.
    # Relabel for the reference (the NAMG solver reads .atoms positionally, so it is
    # unaffected and still consumes the original objects).
    IncShkDstn = [
        DiscreteDistributionLabeled(
            pmv=np.asarray(d.pmv, dtype=float),
            atoms=np.asarray(d.atoms, dtype=float),
            var_names=["PermShk", "TranShk"],
        )
        for d in IncShkDstn
    ]
    p = deepcopy(init_indshk_markov)
    p["MrkvArray"] = [MrkvArray]
    p["constructors"]["MrkvArray"] = None
    p["Rfree"] = [np.array([Rfree] * S)]
    p["LivPrb"] = [np.array([LivPrb] * S)]
    p["PermGroFac"] = [np.array([PermGroFac] * S)]
    p["CRRA"] = CRRA
    p["DiscFac"] = DiscFac
    p["BoroCnstArt"] = BoroCnstArt
    p["aXtraMin"] = aXtraMin
    p["aXtraMax"] = aXtraMax
    p["aXtraCount"] = aXtraCount
    p["aXtraNestFac"] = aXtraNestFac
    p["vFuncBool"] = False
    p["CubicBool"] = False
    p["global_markov"] = False
    agent = MarkovConsumerType(**p)
    agent.cycles = 0
    agent.IncShkDstn = [list(IncShkDstn)]
    agent.IncShkDstn_base = agent.IncShkDstn
    agent.solve()
    return agent


def main():
    import _hark_fti_path  # noqa: F401  -- locate the external fast-time-iteration `hark_fti`
    from hark_fti.global_newton_markov import solve_stationary_NAMG_markov
    from hark_fti.consumed_ati_markov import solve_stationary_ConsumedATI_markov
    import welfare6_scenario as ws

    _param = os.environ.get("POC_PARAMETRIZATION", "HS_Only")  # HS_Only | College_Only | Baseline ...
    print(f"Building {_param} baseline economy (this runs the base Markov SS solve)...",
          flush=True)
    # Small agent count: the SS *solve* cost is N-independent; this just trims the
    # burn-in / TM-init / shock-history overhead build_and_solve does after solving.
    ctx = ws.build_and_solve(_param, agent_count_total=200)
    agents = ctx["AggEco"].agents
    print(f"  built {len(agents)} cohort agent(s).", flush=True)

    # Pick the MOST-PATIENT cohort (highest DiscFac): that is where EGM is slowest
    # (Þ/R -> 1, the O(1/(1-Þ/R)) regime) and the FTI win is largest. For HS_Only this
    # is the single central atom; for College_Only it is the GIC-cap atom (the bake-off's
    # ×4.31 regime). agents[0] is NOT necessarily the most patient.
    a = max(agents, key=lambda ag: float(np.asarray(ag.DiscFac).reshape(-1)[0]))
    print(f"  most-patient cohort: DiscFac={float(np.asarray(a.DiscFac).reshape(-1)[0]):.5f} "
          f"(of {len(agents)} cohorts)", flush=True)
    MrkvArray = np.asarray(a.MrkvArray[0], dtype=float)
    S = MrkvArray.shape[0]
    IncShkDstn = a.IncShkDstn[0]
    BoroCnstArt = _scalar(a.BoroCnstArt)
    CRRA = float(a.CRRA)
    DiscFac = float(a.DiscFac)
    LivPrb = _scalar(a.LivPrb)
    Rfree = _scalar(a.Rfree)
    PermGroFac = _scalar(a.PermGroFac)
    aXtraGrid = np.asarray(a.aXtraGrid, dtype=float)
    aXtraMin = _scalar(a.aXtraMin)
    aXtraMax = _scalar(a.aXtraMax)
    aXtraCount = int(a.aXtraCount)
    aXtraNestFac = int(getattr(a, "aXtraNestFac", 3))

    print(f"\n  S(combined micro states) = {S}", flush=True)
    print(f"  BoroCnstArt = {BoroCnstArt!r}  (NAMG-markov requires 0)", flush=True)
    print(f"  CRRA={CRRA}  DiscFac={DiscFac:.6f}  LivPrb={LivPrb:.6f}  "
          f"Rfree={Rfree:.6f}  PermGroFac={PermGroFac:.6f}", flush=True)
    print(f"  len(IncShkDstn)={len(IncShkDstn)}  aXtraGrid[{aXtraGrid.size}] "
          f"in [{aXtraGrid.min():.3g}, {aXtraGrid.max():.3g}]  "
          f"(min={aXtraMin:g} max={aXtraMax:g} count={aXtraCount} nest={aXtraNestFac})",
          flush=True)

    if abs(BoroCnstArt) > 1e-12:
        print("\n*** BoroCnstArt != 0: NAMG-markov PoC not applicable as-is. "
              "Report this and stop.", flush=True)
        return 2

    import os as _os
    import time

    # ---- EGM reference (timed) ----
    print("\nSolving stock MarkovConsumerType EGM reference on the same inputs...",
          flush=True)
    t_egm = time.time()
    egm = _egm_reference(MrkvArray, IncShkDstn, LivPrb, DiscFac, CRRA, Rfree, PermGroFac,
                         BoroCnstArt, aXtraMin, aXtraMax, aXtraCount, aXtraNestFac)
    egm_wall = time.time() - t_egm
    egm_cFuncs = list(egm.solution[0].cFunc)
    egm_iters = int(getattr(egm, "completed_cycles", -1))
    print(f"  EGM converged in {egm_iters} sweeps ({egm_wall:.2f}s).", flush=True)

    # Ergodic-relevant region above the shared borrowing constraint (mNrmMin=0).
    m = np.linspace(0.5, 12.0, 60)

    def _worst_parity(cFuncs):
        """max over states of max|c_solver - c_egm| on the ergodic m-grid."""
        w = 0.0
        for s in range(S):
            c_e = np.asarray(egm_cFuncs[s](m), dtype=float)
            c_s = np.asarray(cFuncs[s](m), dtype=float)
            w = max(w, float(np.max(np.abs(c_e - c_s))))
        return w

    rows = []  # (label, converged, iters, wall, speedup_vs_egm, parity_vs_egm, extra)

    # ---- NAMG / global-Newton (the just-renamed Step-2 base-solver path) ----
    # env var, NOT argv: HAFiscal's EstimParameters reads sys.argv positionally (argv[1]=Rfree).
    _method = _os.environ.get("POC_NAMG_METHOD", "newton")  # 'newton' (default) | 'anderson'
    print(f"\nRunning solve_stationary_NAMG_markov(method='{_method}')...", flush=True)
    t0 = time.time()
    namg = solve_stationary_NAMG_markov(
        MrkvArray, IncShkDstn, LivPrb, DiscFac, CRRA, Rfree, PermGroFac,
        BoroCnstArt, aXtraGrid, method=_method, verbose=True,
    )
    namg_wall = time.time() - t0
    namg_iters = getattr(namg, "completed_cycles", "?")  # scalar or (warmup, newton) tuple
    namg_conv = bool(getattr(namg, "namg_converged", False))
    w_namg = _worst_parity(namg.cFunc)
    rows.append((f"NAMG/{_method}", namg_conv, namg_iters, namg_wall,
                 (egm_wall / namg_wall) if namg_wall > 0 else float("nan"), w_namg, "-"))
    print(f"  done in {namg_wall:.2f}s; iters={namg_iters} converged={namg_conv} "
          f"parity|dc|={w_namg:.3e}", flush=True)

    # ---- ConsumedATI-Markov (licence-clean Tier-C consumed(a) coordinate) ----
    # Same first-9 positional args as NAMG; returns (sol, info). info['fnorm'] is the FULL
    # consumed(a) Euler residual on the post-decision grid — the masking-bug guard.
    print("\nRunning solve_stationary_ConsumedATI_markov(inner='gmres')...", flush=True)
    t0 = time.time()
    ati_sol, ati_info = solve_stationary_ConsumedATI_markov(
        MrkvArray, IncShkDstn, LivPrb, DiscFac, CRRA, Rfree, PermGroFac,
        BoroCnstArt, aXtraGrid, inner="gmres", maxit=120, verbose=True,
    )
    ati_wall = time.time() - t0
    ati_iters = ati_info.get("iters", "?")
    ati_conv = bool(ati_info.get("converged", False))
    ati_fnorm = float(ati_info.get("fnorm", float("nan")))
    w_ati = _worst_parity(ati_sol.cFunc)
    rows.append(("ConsumedATI", ati_conv, ati_iters, ati_wall,
                 (egm_wall / ati_wall) if ati_wall > 0 else float("nan"), w_ati,
                 f"fnorm={ati_fnorm:.2e}"))
    print(f"  done in {ati_wall:.2f}s; iters={ati_iters} converged={ati_conv} "
          f"parity|dc|={w_ati:.3e} fnorm={ati_fnorm:.2e}", flush=True)

    # ---- comparison table ----
    print("\n" + "=" * 80, flush=True)
    print(f"HS_Only baseline | S={S} micro-states | real calib "
          f"(CRRA={CRRA}, DiscFac={DiscFac:.4f}, Rfree={Rfree:.4f}, PermGroFac={PermGroFac:.5f})",
          flush=True)
    print(f"EGM reference: {egm_iters} sweeps, {egm_wall:.2f}s", flush=True)
    print("-" * 80, flush=True)
    print(f"{'solver':<14}{'conv':<6}{'iters':<7}{'wall(s)':<10}{'x-EGM':<8}"
          f"{'parity|dc|':<13}{'extra'}", flush=True)
    for label, conv, iters, wall, spd, par, extra in rows:
        print(f"{label:<14}{str(conv):<6}{str(iters):<7}{wall:<10.2f}{spd:<8.2f}"
              f"{par:<13.3e}{extra}", flush=True)
    print("=" * 80, flush=True)

    # PASS gate (ConsumedATI): matches EGM cFunc on the ergodic region AND its FULL
    # consumed(a) residual is converged (the masking-bug guard from the bake-off).
    PARITY_TOL, FNORM_TOL = 5e-3, 1e-6
    ok = (w_ati < PARITY_TOL) and ati_conv and (ati_fnorm < FNORM_TOL)
    print(f"\nConsumedATI vs EGM: parity={w_ati:.3e} (tol {PARITY_TOL:.0e}), "
          f"fnorm={ati_fnorm:.2e} (tol {FNORM_TOL:.0e}), converged={ati_conv} -> "
          f"{'PASS' if ok else 'FAIL'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
