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

P4a RECESSION-SCALE EXTENSION (2026-07-23, meld execution plan
plans/20260723_powerlaw-tail-meld-execution_plan.md section 4 — the pre-registered
GO/NO-GO bench for Step-5a wiring). ``POC_MODE=recession`` switches this file to the
recession-Markov bench: it constructs the REAL ``AggFiscalType`` recession structures
(via ``welfare6_scenario.build_and_solve``'s exact construction path, aborted before
the base solve, then ``agent.switch_shock_type``) and, per (state-scale x patience
atom) cell, times

  * the stock HARK ``MarkovConsumerType`` EGM solve (the incumbent library EGM path,
    HARK tolerance 1e-6) — the PRIMARY wall denominator,
  * ``solve_stationary_ConsumedATI_markov(tail_form='powerlaw', tail_q_mode='chain')``
    (FTI d474914) — the accelerated arm,
  * an in-formulation power-law Picard-EGM reference (same-fixed-point comparator,
    the P2 parity convention) run DEEP via a measured-contraction stopping rule —
    gives the pre-registered consumed(a) parity anchor AND a same-form EGM wall.

State scales map to real production structures (num_experiment_periods drives the
macro count 2*(P+1)): 132 = ``recession`` at Reduced-scale P=10 (22 macro x 6 micro);
252 = ``recessionTaxCut`` at Baseline-scale P=20 (42 macro x 6 micro, tax-cut income
states live). Atoms: HS central / College central / College GIC-cap
(``gic_capped_beta(2, theGICfactor)``), each on its own education-group structure +
per-group default grid (verify the ``[grid_sizing]`` import print: powerlaw +
measured-Q local2 + K=3*hbar top + count basis 192 -> College 591/241 on a bare env).

Env knobs (env, NOT argv — EstimParameters reads sys.argv positionally):
  POC_MODE=recession        activate this bench (default: the base PoC above)
  POC_SCALES=132,252        which scales to run
  POC_ATOMS=hs_central,college_central,college_gic
  POC_ATI_MAXIT=200         ConsumedATI outer-iteration cap
  POC_PICARD_MOVE_TOL=1e-13 fixed move tolerance for the deep reference (P2 convention)
  POC_PICARD_MAXWALL=7200   per-cell Picard wall cap (s)
  POC_OUT=/path/cells.json  optional JSON dump of the per-cell rows
Thread caps must be set in the SHELL before launch (numpy reads them at import):
  OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
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


# =============================================================================
# P4a (2026-07-23): recession-scale GO/NO-GO bench (meld plan section 4).
# Everything below is additive; POC_MODE=recession selects it. The base PoC
# (main() above) is unchanged.
# =============================================================================

def _git_sha(path):
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "-C", path, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _fti_provenance():
    """Verify the resolved hark_fti is the sibling checkout at the expected commit."""
    import _hark_fti_path  # noqa: F401
    import hark_fti
    fti_dir = os.path.dirname(os.path.abspath(hark_fti.__file__))
    fti_repo = os.path.normpath(os.path.join(fti_dir, ".."))
    info = {
        "hark_fti_file": hark_fti.__file__,
        "fti_sha": _git_sha(fti_repo),
        "hafiscal_sha": _git_sha(os.path.normpath(os.path.join(_FROMPANDEMIC, "..", "..", ".."))),
    }
    print(f"[p4a provenance] hark_fti = {info['hark_fti_file']}")
    print(f"[p4a provenance] fast-time-iteration sha = {info['fti_sha']}  "
          f"HAFiscal sha = {info['hafiscal_sha']}", flush=True)
    return info


class _StopBuildAfterConstruction(Exception):
    """Sentinel: welfare6_scenario.build_and_solve reached the base solve."""


def _build_economy_no_solve(parametrization):
    """Construct the REAL AggFiscalType economy via build_and_solve's EXACT
    construction path, aborting just before the base solve.

    P4a needs only the CONSTRUCTED recession Markov inputs (MrkvArray_*,
    IncShkDstn_recession*, per-state LivPrb/PermGroFac/Rfree, per-group grids);
    the base solve + burn-in + TM-init that follow in build_and_solve are
    irrelevant to that extraction and cost ~21 EGM solves at Baseline. Rather
    than duplicating the ~200-line construction block (drift risk), intercept
    ``solution_cache.cached_eco_solve`` — the FIRST call after construction is
    complete (welfare6_scenario.py:511) — capture the economy, and unwind.
    ``from solution_cache import cached_eco_solve`` inside build_and_solve reads
    the package attribute at call time, so the patch takes effect."""
    import solution_cache
    import welfare6_scenario as ws
    captured = {}
    orig = solution_cache.cached_eco_solve

    def _capture_and_abort(ctx, *a, **kw):
        captured["AggEco"] = ctx["AggEco"]
        raise _StopBuildAfterConstruction()

    solution_cache.cached_eco_solve = _capture_and_abort
    try:
        ws.build_and_solve(parametrization, agent_count_total=100)
    except _StopBuildAfterConstruction:
        pass
    finally:
        solution_cache.cached_eco_solve = orig
    if "AggEco" not in captured:
        raise RuntimeError(
            f"build_and_solve({parametrization!r}) returned without reaching "
            "cached_eco_solve — construction path changed; extend the capture point.")
    return captured["AggEco"]


def _agents_by_edu(eco):
    """One representative agent per education group + the group's sorted beta atoms.

    Structure (MrkvArray/IncShkDstn/grids) is beta-invariant within a group, so any
    atom's agent serves for extraction; DiscFac is passed separately to the solvers.
    Groups are identified by the education-specific PermGroFac_base."""
    from EstimParameters import PermGroFac_base_d, PermGroFac_base_h, PermGroFac_base_c
    targets = {
        "dropout": float(PermGroFac_base_d[0]),
        "highschool": float(PermGroFac_base_h[0]),
        "college": float(PermGroFac_base_c[0]),
    }
    out = {}
    for name, g in targets.items():
        members = [a for a in eco.agents
                   if abs(float(np.asarray(a.PermGroFac_base).ravel()[0]) - g) < 1e-12]
        if members:
            betas = sorted(float(np.asarray(a.DiscFac).reshape(-1)[0]) for a in members)
            out[name] = (members[0], betas)
    return out


def _extract_recession_inputs(agent, shock_type, expected_S):
    """switch_shock_type + pull the per-state Markov solve inputs (FULL fidelity:
    per-state PermGroFac — employed micro states grow at the education G, unemployed
    at PermGroFac_unemp=1 under the default BUG-040-off world)."""
    agent.switch_shock_type(shock_type)
    MrkvArray = np.asarray(agent.MrkvArray[0], dtype=float)
    S = MrkvArray.shape[0]
    if S != expected_S:
        raise RuntimeError(f"{shock_type}: got S={S}, expected {expected_S}")
    if not np.allclose(MrkvArray.sum(axis=1), 1.0):
        raise RuntimeError(f"{shock_type}: MrkvArray rows do not sum to 1")
    IncShkDstn = list(agent.IncShkDstn[0])
    if len(IncShkDstn) != S:
        raise RuntimeError(f"{shock_type}: len(IncShkDstn)={len(IncShkDstn)} != S={S}")
    LivPrb = np.asarray(agent.LivPrb[0], dtype=float)
    Rfree = np.asarray(agent.Rfree, dtype=float).reshape(-1)
    PermGroFac = np.asarray(agent.PermGroFac[0], dtype=float)
    assert LivPrb.size == S and Rfree.size == S and PermGroFac.size == S
    # markov_pf_seed's scalar-MPCmin and DiscFacEff=DiscFac*LivPrb[0] assumptions:
    assert np.allclose(Rfree, Rfree[0]), "per-state Rfree found — MPCmin assumption breaks"
    assert np.allclose(LivPrb, LivPrb[0]), "per-state LivPrb found — DiscFacEff assumption breaks"
    if abs(_scalar(agent.BoroCnstArt)) > 1e-12:
        raise RuntimeError("BoroCnstArt != 0 — ConsumedATI-markov requires 0")
    return dict(
        shock_type=shock_type,
        MrkvArray=MrkvArray, S=S, IncShkDstn=IncShkDstn,
        LivPrb=LivPrb, Rfree=Rfree, PermGroFac=PermGroFac,
        CRRA=float(agent.CRRA),
        aXtraGrid=np.asarray(agent.aXtraGrid, dtype=float).copy(),
        aXtraMin=_scalar(agent.aXtraMin), aXtraMax=_scalar(agent.aXtraMax),
        aXtraCount=int(agent.aXtraCount), aXtraNestFac=int(getattr(agent, "aXtraNestFac", 3)),
    )


def _egm_stock_arm(inp, DiscFac):
    """Stock HARK MarkovConsumerType EGM on the exact extracted inputs (timed).

    The incumbent library-EGM wall: HARK's iterate-to-tolerance loop (default
    tolerance 1e-6, the same stopping class production uses). The agent's
    aXtraGrid is overridden with the EXACT HAFiscal per-group grid so both arms
    solve on identical knots (pre_solve only reconstructs solution_terminal, so
    the override sticks — verified by the post-solve assert)."""
    import time
    from copy import deepcopy
    from HARK.ConsumptionSaving.ConsMarkovModel import (
        MarkovConsumerType, init_indshk_markov,
    )
    from HARK.distributions import DiscreteDistributionLabeled
    S = inp["S"]
    IncShkDstn = [
        DiscreteDistributionLabeled(
            pmv=np.asarray(d.pmv, dtype=float),
            atoms=np.asarray(d.atoms, dtype=float),
            var_names=["PermShk", "TranShk"],
        )
        for d in inp["IncShkDstn"]
    ]
    p = deepcopy(init_indshk_markov)
    p["MrkvArray"] = [inp["MrkvArray"]]
    p["constructors"]["MrkvArray"] = None
    p["Rfree"] = [inp["Rfree"].copy()]
    p["LivPrb"] = [inp["LivPrb"].copy()]
    p["PermGroFac"] = [inp["PermGroFac"].copy()]
    p["CRRA"] = inp["CRRA"]
    p["DiscFac"] = float(DiscFac)
    p["BoroCnstArt"] = 0.0
    p["aXtraMin"] = inp["aXtraMin"]
    p["aXtraMax"] = inp["aXtraMax"]
    p["aXtraCount"] = inp["aXtraCount"]
    p["aXtraNestFac"] = inp["aXtraNestFac"]
    p["vFuncBool"] = False
    p["CubicBool"] = False
    p["global_markov"] = False
    agent = MarkovConsumerType(**p)
    agent.cycles = 0
    agent.assign_parameters(aXtraGrid=inp["aXtraGrid"].copy())
    agent.IncShkDstn = [list(IncShkDstn)]
    agent.IncShkDstn_base = agent.IncShkDstn
    t0 = time.perf_counter()
    agent.solve()
    wall = time.perf_counter() - t0
    assert np.array_equal(np.asarray(agent.aXtraGrid, dtype=float), inp["aXtraGrid"]), \
        "stock EGM rebuilt aXtraGrid — grids no longer identical"
    return dict(
        cFunc=list(agent.solution[0].cFunc),
        iters=int(getattr(agent, "completed_cycles", -1)),
        wall=wall,
        tolerance=float(getattr(agent, "tolerance", float("nan"))),
    )


def _picard_sweep_factory(inp, DiscFac):
    """Build the in-formulation Picard-EGM sweep map X -> sweep(X) with the SAME
    floating slope-Q power-law tail as ConsumedATI 'chain' mode.

    One sweep IS one EGM backward iteration in the consumed(a) coordinate:
    x_i <- (const_i / T_i)^(1/rho), T_i = sum_jp Pi[i,jp] E[(G_jp c_jp(mNext))^-rho],
    with the power-law continuation rebuilt from the current iterate (mNext is
    i-independent given jp, so each target state's continuation is evaluated once
    per sweep and scattered to its predecessor rows). Provenance:
    fast-time-iteration hark_fti/test_powerlaw_tail_jacobian.py::_picard_markov
    (the P2 same-fixed-point parity convention), adapted to per-state
    Rfree/PermGroFac."""
    from hark_fti.consumed_ati_markov import markov_pf_seed, _state_continuation
    from HARK.interpolation import LinearInterp

    Mrkv = inp["MrkvArray"]
    S = inp["S"]
    aN = inp["aXtraGrid"]
    R = inp["Rfree"]
    G = inp["PermGroFac"]
    CRRA = inp["CRRA"]
    L = float(inp["LivPrb"][0])
    DiscFacEff = float(DiscFac) * L
    MPCmin, hNrm = markov_pf_seed(Mrkv, inp["IncShkDstn"], DiscFacEff, R, G, CRRA)
    cFuncCnst = LinearInterp(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    Gk = [np.asarray(d.atoms[0], float) * float(G[jp])
          for jp, d in enumerate(inp["IncShkDstn"])]
    Tran = [np.asarray(d.atoms[1], float) for d in inp["IncShkDstn"]]
    Probs = [np.asarray(d.pmv, float) for d in inp["IncShkDstn"]]
    const = 1.0 / (DiscFacEff * R)                    # (S,)
    rows_of = [np.nonzero(Mrkv[:, jp] > 0.0)[0] for jp in range(S)]
    a_col = aN[:, None]

    def _cont(Xj, j):
        return _state_continuation(Xj, aN, hNrm[j], MPCmin, cFuncCnst,
                                   tail_form="powerlaw", tail_Q=None)

    def sweep(X):
        T = np.zeros((S, aN.size))
        for jp in range(S):
            rows = rows_of[jp]
            if rows.size == 0:
                continue
            cont = _cont(X[jp], jp)
            mNext = float(R[jp]) * a_col / Gk[jp] + Tran[jp]          # (J, K)
            cNext = np.asarray(cont[3](mNext.ravel()), float).reshape(mNext.shape)
            contrib = ((Gk[jp] * cNext) ** (-CRRA)) @ Probs[jp]       # (J,)
            T[rows] += Mrkv[rows, jp][:, None] * contrib[None, :]
        return (const[:, None] / T) ** (1.0 / CRRA)

    X0 = np.array([np.maximum(MPCmin * (aN + hNrm[s]), 1e-10) for s in range(S)])
    return sweep, _cont, X0, MPCmin, hNrm


def _picard_powerlaw_arm(inp, DiscFac, move_tol=1e-13, egm_stop_tol=1e-6,
                         maxit=500_000, wall_cap_s=7200.0, log_every=1000):
    """Deep in-formulation power-law Picard-EGM — the same-fixed-point parity
    reference, run to a FIXED move tolerance (default 1e-13, the P2 reference
    convention: distance-to-limit <= move_tol * rho/(1-rho), <= ~2.5e-11 even at
    the GIC-cap rho ~ 0.996).

    A projection-based stop (move * rho_hat/(1-rho_hat)) was tried first and
    failed a UNITS check: move is RELATIVE (|dX|/(1+|X|)) while the parity gate
    is ABSOLUTE max|dX|, and the top consumed knots are O(30), so a 4.6e-10
    relative projection was ~1.4e-8 absolute — measured on the 132/hs cell,
    where a machine-zero-residual (fnorm 8.9e-16) ATI solution sat 1.238e-8
    (absolute) from the projection-stopped reference and the gap collapsed to
    8.4e-10 once the reference ran to the fixed relative tol below (single
    dominant mode throughout; no hidden slow mode). At 1e-13 relative the
    absolute limit-error is <= ~1e-10 at every bench cell's X-scale and
    contraction. rho_hat is still measured and reported, as a diagnostic only.
    Also records the sweep/wall at the first move < egm_stop_tol — the
    same-form EGM-equivalent-stop wall."""
    import time

    sweep, _cont, X, MPCmin, hNrm = _picard_sweep_factory(inp, DiscFac)
    S = inp["S"]
    moves = []
    egm_stop = None
    converged = False
    rho_hat = float("nan")
    t0 = time.perf_counter()
    for k in range(1, maxit + 1):
        Xn = sweep(X)
        move = float(np.max(np.abs(Xn - X) / (1.0 + np.abs(X))))
        X = Xn
        moves.append(move)
        wall = time.perf_counter() - t0
        if egm_stop is None and move < egm_stop_tol:
            egm_stop = dict(sweeps=k, wall=wall, move=move)
        if k >= 21:
            last = np.asarray(moves[-21:])
            with np.errstate(divide="ignore", invalid="ignore"):
                ratios = last[1:] / last[:-1]
            ratios = ratios[np.isfinite(ratios) & (ratios > 0)]
            if ratios.size >= 10:
                rho_hat = float(np.median(ratios))
        if move < move_tol:
            converged = True
            break
        if log_every and k % log_every == 0:
            print(f"    [picard] sweep {k}  move={move:.3e}  rho_hat={rho_hat:.6f}  "
                  f"wall={wall:.1f}s", flush=True)
        if wall > wall_cap_s:
            print(f"    [picard] WALL CAP hit at sweep {k} (move={move:.3e})",
                  flush=True)
            break
    wall_total = time.perf_counter() - t0
    proj = (move * rho_hat / (1.0 - rho_hat)
            if np.isfinite(rho_hat) and 0.0 < rho_hat < 1.0 else float("nan"))
    conts = [_cont(X[j], j) for j in range(S)]
    return dict(
        X_ref=X, cFunc=[c[3] for c in conts], sweeps=len(moves), wall=wall_total,
        move_final=moves[-1] if moves else float("nan"), rho_hat=rho_hat,
        proj_err=proj, converged=converged, move_tol=move_tol,
        egm_stop=egm_stop or dict(sweeps=-1, wall=float("nan"), move=float("nan")),
        MPCmin=MPCmin, hNrm=hNrm, sweep_fn=sweep,
    )


def _ati_arm(inp, DiscFac, maxit=200, verbose=False, tol_delta=1e-9, tol_EE=1e-9):
    """solve_stationary_ConsumedATI_markov, powerlaw + chain (timed)."""
    import time
    from hark_fti.consumed_ati_markov import solve_stationary_ConsumedATI_markov
    t0 = time.perf_counter()
    sol, info = solve_stationary_ConsumedATI_markov(
        inp["MrkvArray"], inp["IncShkDstn"], inp["LivPrb"], float(DiscFac),
        inp["CRRA"], inp["Rfree"], inp["PermGroFac"], 0.0, inp["aXtraGrid"],
        inner="gmres", maxit=maxit, verbose=verbose,
        tol_delta=tol_delta, tol_EE=tol_EE,
        tail_form="powerlaw", tail_q_mode="chain",
    )
    wall = time.perf_counter() - t0
    return sol, info, wall


def _cfunc_maxdiff(cf_a, cf_b, m):
    return max(float(np.max(np.abs(np.asarray(fa(m), float) - np.asarray(fb(m), float))))
               for fa, fb in zip(cf_a, cf_b))


def _bench_cell(inp, atom_name, DiscFac, ati_maxit, picard_move_tol, picard_maxwall):
    """One (state-scale x atom) cell: stock EGM + ConsumedATI + deep Picard + metrics."""
    S, J = inp["S"], inp["aXtraGrid"].size
    print(f"\n--- cell: S={S} ({inp['shock_type']}) atom={atom_name} "
          f"beta={DiscFac:.6f} J={J} aMax={inp['aXtraGrid'].max():.0f} ---", flush=True)

    print("  stock HARK MarkovConsumerType EGM...", flush=True)
    egm = _egm_stock_arm(inp, DiscFac)
    print(f"    EGM: {egm['iters']} sweeps, {egm['wall']:.2f}s "
          f"(tolerance={egm['tolerance']:g})", flush=True)

    print("  ConsumedATI-markov (powerlaw, chain, gmres)...", flush=True)
    ati_sol, ati_info, ati_wall = _ati_arm(inp, DiscFac, maxit=ati_maxit)
    print(f"    ATI: iters={ati_info['iters']} converged={ati_info['converged']} "
          f"({ati_info['converged_reason']}) fnorm={ati_info['fnorm']:.2e} "
          f"EE={ati_info['ee_max']:.2e} inner_total={ati_info['inner_iters_total']} "
          f"fell_back={ati_info['fell_back_to_direct']} wall={ati_wall:.2f}s", flush=True)

    print("  deep power-law Picard-EGM reference (same-form fixed point)...", flush=True)
    pic = _picard_powerlaw_arm(inp, DiscFac, move_tol=picard_move_tol,
                               wall_cap_s=picard_maxwall)
    print(f"    picard: {pic['sweeps']} sweeps wall={pic['wall']:.1f}s "
          f"rho_hat={pic['rho_hat']:.6f} move_final={pic['move_final']:.2e} "
          f"(tol {pic['move_tol']:g}) converged={pic['converged']}; "
          f"EGM-equivalent stop (move<1e-6): "
          f"sweep {pic['egm_stop']['sweeps']} @ {pic['egm_stop']['wall']:.1f}s", flush=True)

    # Cross-map certificate: one Picard sweep applied AT the ATI solution. If
    # ||sweep(X_ati) - X_ati|| is machine-small, X_ati is a fixed point of the
    # INDEPENDENT Picard-EGM map itself — a same-fixed-point certificate that
    # does not depend on how deep the reference iterate got.
    X_ati = np.asarray(ati_info["consumed_a"], float)
    cross_move_default = float(np.max(np.abs(pic["sweep_fn"](X_ati) - X_ati)
                                      / (1.0 + np.abs(X_ati))))
    print(f"    cross-map certificate: |sweep(X_ati)-X_ati| = {cross_move_default:.3e} "
          f"(default-gate ATI)", flush=True)

    # --- metrics ---
    parity_consumed = float(np.max(np.abs(
        np.asarray(ati_info["consumed_a"], float) - pic["X_ref"])))

    # Stopping-noise decomposition (the P1/P2 convention: tightened, never
    # loosened): the production-gate (1e-9) ATI stop leaves ~1e-8-class distance
    # to the fixed point at moderate contraction. If the default-gate parity
    # lands in that gray zone, re-run ATI at tightened gates (1e-11) as an
    # UNTIMED parity certificate — the wall ratio always uses the production-
    # gate wall above.
    parity_tight = None
    tight_info = None
    cross_move_tight = None
    if 1e-9 < parity_consumed <= 1e-6:
        print("  parity in the stopping-noise gray zone — untimed tightened-gate "
              "(1e-11) ATI certificate pass...", flush=True)
        _, tight_info, tight_wall = _ati_arm(inp, DiscFac, maxit=ati_maxit,
                                             tol_delta=1e-11, tol_EE=1e-11)
        X_t = np.asarray(tight_info["consumed_a"], float)
        parity_tight = float(np.max(np.abs(X_t - pic["X_ref"])))
        cross_move_tight = float(np.max(np.abs(pic["sweep_fn"](X_t) - X_t)
                                        / (1.0 + np.abs(X_t))))
        print(f"    tight ATI: iters={tight_info['iters']} "
              f"converged={tight_info['converged']} ({tight_info['converged_reason']}) "
              f"fnorm={tight_info['fnorm']:.2e} wall={tight_wall:.2f}s "
              f"parity_tight={parity_tight:.3e} "
              f"cross-map={cross_move_tight:.3e}", flush=True)
    m_top = float(min(np.asarray(pic["X_ref"][s], float)[-1] + inp["aXtraGrid"][-1]
                      for s in range(S)))
    m_full = np.concatenate([np.array([1e-4, 1e-3, 1e-2]),
                             np.linspace(0.05, m_top * 0.999, 400)])
    parity_cfunc_ati_vs_egm = _cfunc_maxdiff(list(ati_sol.cFunc), egm["cFunc"], m_full)
    parity_cfunc_ati_vs_ref = _cfunc_maxdiff(list(ati_sol.cFunc), pic["cFunc"], m_full)
    egm_vs_ref = _cfunc_maxdiff(egm["cFunc"], pic["cFunc"], m_full)
    m_erg = np.linspace(0.5, 12.0, 60)
    parity_erg_ati_vs_egm = _cfunc_maxdiff(list(ati_sol.cFunc), egm["cFunc"], m_erg)

    ratio_stock = egm["wall"] / ati_wall if ati_wall > 0 else float("nan")
    ratio_picard = (pic["egm_stop"]["wall"] / ati_wall
                    if ati_wall > 0 and pic["egm_stop"]["sweeps"] > 0 else float("nan"))
    row = dict(
        S=S, shock_type=inp["shock_type"], atom=atom_name, beta=float(DiscFac),
        J=J, aMax=float(inp["aXtraGrid"].max()),
        egm_wall=egm["wall"], egm_iters=egm["iters"], egm_tolerance=egm["tolerance"],
        ati_wall=ati_wall, ati_iters=ati_info["iters"],
        ati_converged=bool(ati_info["converged"]),
        ati_reason=ati_info["converged_reason"],
        ati_fnorm=float(ati_info["fnorm"]), ati_ee_max=float(ati_info["ee_max"]),
        ati_inner_total=int(ati_info["inner_iters_total"]),
        ati_fell_back_to_direct=bool(ati_info["fell_back_to_direct"]),
        picard_sweeps=pic["sweeps"], picard_wall=pic["wall"],
        picard_rho_hat=pic["rho_hat"], picard_proj_err=pic["proj_err"],
        picard_converged=bool(pic["converged"]),
        picard_egm_stop_sweeps=pic["egm_stop"]["sweeps"],
        picard_egm_stop_wall=pic["egm_stop"]["wall"],
        ratio_stock=ratio_stock, ratio_picard=ratio_picard,
        parity_consumed=parity_consumed,
        parity_consumed_tight=parity_tight,
        cross_map_move=cross_move_default,
        cross_map_move_tight=cross_move_tight,
        ati_tight_converged=(bool(tight_info["converged"]) if tight_info else None),
        ati_tight_iters=(int(tight_info["iters"]) if tight_info else None),
        ati_tight_fnorm=(float(tight_info["fnorm"]) if tight_info else None),
        parity_cfunc_ati_vs_ref=parity_cfunc_ati_vs_ref,
        parity_cfunc_ati_vs_egm=parity_cfunc_ati_vs_egm,
        parity_erg_ati_vs_egm=parity_erg_ati_vs_egm,
        egm_vs_ref=egm_vs_ref,
        picard_move_final=pic["move_final"], picard_move_tol=pic["move_tol"],
    )
    print(f"    parity: consumed(ATI vs deep-ref)={parity_consumed:.3e}  "
          f"cFunc(ATI vs ref)={parity_cfunc_ati_vs_ref:.3e}  "
          f"cFunc(ATI vs stockEGM)={parity_cfunc_ati_vs_egm:.3e}  "
          f"cFunc(stockEGM vs ref)={egm_vs_ref:.3e}", flush=True)
    print(f"    walls: EGM {egm['wall']:.2f}s | ATI {ati_wall:.2f}s | "
          f"ratio(stock)={ratio_stock:.2f}x  ratio(same-form-EGM@1e-6)={ratio_picard:.2f}x",
          flush=True)
    return row


def main_recession():
    import json
    prov = _fti_provenance()
    from EstimParameters import gic_capped_beta, theGICfactor
    beta_gic = float(gic_capped_beta(2, theGICfactor))

    scales = [int(s) for s in os.environ.get("POC_SCALES", "132,252").split(",") if s]
    atoms_sel = [a.strip() for a in os.environ.get(
        "POC_ATOMS", "hs_central,college_central,college_gic").split(",") if a.strip()]
    ati_maxit = int(os.environ.get("POC_ATI_MAXIT", "200"))
    picard_move_tol = float(os.environ.get("POC_PICARD_MOVE_TOL", "1e-13"))
    picard_maxwall = float(os.environ.get("POC_PICARD_MAXWALL", "7200"))

    # scale -> (parametrization, shock_type): the state count is driven by
    # num_experiment_periods P via 2*(P+1) macro states x 6 micro:
    #   132 = recession       @ Reduced-scale P=10 (22 macro)
    #   252 = recessionTaxCut @ Baseline-scale P=20 (42 macro, tax-cut income live)
    scale_map = {132: ("Reduced_Run", "recession"), 252: ("Baseline", "recessionTaxCut")}

    rows = []
    for scale in scales:
        param, shock_type = scale_map[scale]
        print(f"\n=== scale S={scale}: constructing {param} economy (no base solve) ===",
              flush=True)
        eco = _build_economy_no_solve(param)
        by_edu = _agents_by_edu(eco)
        for name, (_, betas) in sorted(by_edu.items()):
            print(f"  {name}: {len(betas)} beta atom(s): "
                  f"[{', '.join(f'{b:.5f}' for b in betas)}]", flush=True)
        hs_agent, hs_betas = by_edu["highschool"]
        co_agent, co_betas = by_edu["college"]
        atom_defs = {
            "hs_central": (hs_agent, float(hs_betas[len(hs_betas) // 2])),
            "college_central": (co_agent, float(co_betas[len(co_betas) // 2])),
            "college_gic": (co_agent, beta_gic),
        }
        print(f"  atoms: " + ", ".join(f"{n}(beta={b:.6f})"
                                       for n, (_a, b) in atom_defs.items())
              + f"  [gic cap = gic_capped_beta(2, {theGICfactor}) = {beta_gic:.6f}; "
                f"College top atom in calib = {max(co_betas):.6f}]", flush=True)

        # Extract once per education structure actually used at this scale.
        inputs = {}
        for atom in atoms_sel:
            agent, beta = atom_defs[atom]
            key = id(agent)
            if key not in inputs:
                inputs[key] = _extract_recession_inputs(agent, shock_type, scale)
            rows.append(_bench_cell(inputs[key], atom, beta, ati_maxit,
                                    picard_move_tol, picard_maxwall))

    # ---- summary table + pre-registered criterion ----
    print("\n" + "=" * 110, flush=True)
    print("P4a recession-scale bench — powerlaw+chain ConsumedATI-markov vs stock EGM "
          f"(FTI {prov['fti_sha']}, HAFiscal {prov['hafiscal_sha']})", flush=True)
    print("-" * 110, flush=True)
    hdr = (f"{'S':<5}{'atom':<17}{'beta':<10}{'EGM s':<9}{'ATI s':<9}{'x-stock':<9}"
           f"{'x-sameform':<11}{'consumed-parity':<17}{'fnorm':<11}{'conv'}")
    print(hdr, flush=True)
    for r in rows:
        print(f"{r['S']:<5}{r['atom']:<17}{r['beta']:<10.5f}{r['egm_wall']:<9.2f}"
              f"{r['ati_wall']:<9.2f}{r['ratio_stock']:<9.2f}{r['ratio_picard']:<11.2f}"
              f"{r['parity_consumed']:<17.3e}{r['ati_fnorm']:<11.2e}"
              f"{r['ati_converged']}", flush=True)
    print("=" * 110, flush=True)

    # Pre-registered criterion (meld plan section 4): GO <=> wall win >= 1.5x vs
    # EGM AT THE BINDING ATOMS at parity (consumed(a) <= ~1e-8, fnorm machine-
    # class); else NO-GO for Step-5a wiring. Binding atoms = College central (the
    # Reduced binding case) + College GIC-cap (the Baseline binding case);
    # hs_central is a reported context cell, not a gate. Parity may be certified
    # by the untimed tightened-gate pass (stopping-noise decomposition, the P1/P2
    # tightened-never-loosened convention); the wall ratio is always the
    # production-gate solve's.
    BINDING = {"college_central", "college_gic"}
    PARITY_TOL = 1e-8
    per_cell = {}
    for r in rows:
        parity_ok = r["parity_consumed"] <= PARITY_TOL
        parity_via = "default-gate"
        if not parity_ok and r.get("parity_consumed_tight") is not None:
            parity_ok = (r["parity_consumed_tight"] <= PARITY_TOL
                         and bool(r.get("ati_tight_converged")))
            parity_via = "tightened-gate certificate"
        ok = bool(r["ati_converged"] and parity_ok and r["ratio_stock"] >= 1.5)
        r["cell_go_grade"] = ok
        r["parity_via"] = parity_via
        binding = r["atom"] in BINDING
        per_cell[(r["S"], r["atom"], binding)] = ok
        print(f"  cell (S={r['S']}, {r['atom']}{', BINDING' if binding else ''}): "
              f"{'GO-grade' if ok else 'not GO-grade'} "
              f"(ratio {r['ratio_stock']:.2f}x, parity {r['parity_consumed']:.2e}"
              + (f" -> tight {r['parity_consumed_tight']:.2e}"
                 if r.get("parity_consumed_tight") is not None else "")
              + f" [{parity_via}], converged={r['ati_converged']})", flush=True)
    binding_results = [ok for (S, a, b), ok in per_cell.items() if b]
    if binding_results and all(binding_results):
        verdict = "GO"
    elif binding_results and not any(binding_results):
        verdict = "NO-GO"
    elif binding_results:
        verdict = "MIXED"
    else:
        verdict = "INCOMPLETE (no binding cells ran)"
    print(f"\nP4a VERDICT (pre-registered criterion, binding atoms "
          f"= college_central + college_gic): {verdict}", flush=True)

    out = os.environ.get("POC_OUT", "")
    if out:
        with open(out, "w") as f:
            json.dump(dict(provenance=prov, rows=rows, verdict=verdict), f, indent=2)
        print(f"[p4a] wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    if os.environ.get("POC_MODE", "base").strip().lower() == "recession":
        sys.exit(main_recession())
    sys.exit(main())
