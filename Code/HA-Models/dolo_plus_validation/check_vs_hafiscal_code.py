#!/usr/bin/env python3
"""
YAML <-> HAFiscal-code consistency check (#1), on the _TM-vs-MC branch, ESC mode.

Builds a baseline single-cohort AggFiscalType (interpretation='ESC'), solves with
HAFiscal's actual solver, extracts its EXACT calibration (DiscFac, CRRA, Rfree, LivPrb
vector, PermGroFac vector, joint MrkvArray, per-state IncShkDstn), then runs the
independent textbook EGM (the same equations the dolo-plus YAML encodes) with that
EXACT calibration and compares the employed-state consumption policy cFunc[0](m).

Rationale: under ESC the optimizer-stage cFunc is HARK's standard Markov buffer-stock
(a = m - c); ESC/CDC differ only in the out-of-YAML simulation asset update. So this
check validates that the YAML's optimizer-stage EQUATIONS reproduce HAFiscal's solved
policy, decoupled from calibration-value choices.

Gate (rel < 1e-3) is evaluated on probe points WITHIN both solvers' grid support
(m <= GATE_M_MAX): HAFiscal's production asset grid tops out at aXtraMax=40, so its
cFunc at m >> 40 is linear extrapolation — comparing that against a gridded EGM
measures extrapolation policy, not equation faithfulness. Probes beyond GATE_M_MAX
are still printed (FYI rows) but not gated. See the 2026-06-12 addendum in
FINDING_permgrofac_marginal_value_factor.md.

The 1e-3 gate is evaluated at EQUATION-CHECK grid densities (HAFiscal aXtraCount=192,
EGM aCount=440): the production grid (aXtraCount=48) carries an intrinsic ~3e-3
discretization residual at m~20 that is attributable to grid density, not equations
(bisection evidence in the addendum). Run with --production-grids to see the
production-grid residual (informational; gate not applied).

CLI:
  EGM_FACTOR_MODE={standard|hafiscal_code} python check_vs_hafiscal_code.py
      [--production-grids]
  exit 0 iff the supported-range gate passes.

Importable machinery (used by conftest.py / test_yaml_vs_code_cfunc.py):
  import_fpc_modules(), build_and_solve_agent(), extract_calibration(),
  solve_egm_from_calibration(), compare_cfunc(), run_check().
"""
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import numpy as np

FPC_DIR = Path(__file__).resolve().parents[1] / "FromPandemicCode"
# argv layout EstimParameters parses: [prog, Rfree, CRRA, IncUnemp, IncUnempNoBenefits]
DEFAULT_ARGV = ["check_vs_hafiscal_code", "1.01", "2.0", "0.7", "0.5"]
GATE_REL = 1e-3      # equation-faithfulness gate (tighten-only; see module docstring)
GATE_M_MAX = 40.0    # gate domain cap = production aXtraMax (beyond it cFunc extrapolates)
PROBES = [0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 20.0, 50.0, 100.0, 300.0, 1000.0]

# Equation-check grid densities: dense enough that the discretization residual is
# < the 1e-3 gate (bisection evidence: FINDING addendum 2026-06-12).
CHECK_AXTRA_COUNT = 192
CHECK_EGM_ACOUNT = 440
PROD_EGM_ACOUNT = 220
EGM_AMAX = 2000.0


@contextmanager
def _chdir(path):
    saved = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(saved)


def import_fpc_modules():
    """Import Parameters/AggFiscalModel safely and return (Parameters, AggFiscalModel).

    EstimParameters parses sys.argv and reads calibration files relative to cwd at
    import time (CLAUDE.md rule: patch sys.argv BEFORE importing Parameters), so this
    swaps in a pinned argv and chdirs to FromPandemicCode/ for the import, restoring
    both afterwards. Idempotent: once the modules are in sys.modules it's a no-op.
    """
    os.environ.setdefault("HAFISCAL_INTERPRETATION", "ESC")
    if str(FPC_DIR) not in sys.path:
        sys.path.insert(0, str(FPC_DIR))
    saved_argv = sys.argv
    sys.argv = list(DEFAULT_ARGV)
    try:
        with _chdir(FPC_DIR):
            import Parameters
            import AggFiscalModel
    finally:
        sys.argv = saved_argv
    return Parameters, AggFiscalModel


def build_and_solve_agent(aXtraCount=None, aXtraMax=None):
    """Build + solve a baseline single-cohort HS AggFiscalType in ESC mode.

    Optional aXtraCount/aXtraMax override the production asset grid (48 pts to 40)
    for grid-density diagnosis; None keeps production values. Returns a dict with
    the solved agent and the pieces extract_calibration() needs.
    """
    Parameters, AggFiscalModel = import_fpc_modules()
    from copy import deepcopy

    from HARK.distributions import DiscreteDistribution

    with _chdir(FPC_DIR):
        P = Parameters.return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
        (init_dropout, init_highschool, init_college, init_ADEconomy,
         DiscFacDstns, DiscFacCount, AgentCountTotal, base_dict,
         num_max_iterations_solvingAD, convergence_tol_solvingAD,
         UBspell_normal, num_base_MrkvStates, *_rest) = P

        init_hs = deepcopy(init_highschool)
        if aXtraCount is not None:
            init_hs["aXtraCount"] = int(aXtraCount)
        if aXtraMax is not None:
            init_hs["aXtraMax"] = float(aXtraMax)

        econ = AggFiscalModel.AggregateDemandEconomy(**init_ADEconomy)
        hs = AggFiscalModel.AggFiscalType(**init_hs)
        hs.interpretation = "ESC"
        hs.cycles = 0
        hs.get_economy_data(econ)
        IncShk_u = DiscreteDistribution(
            np.array([1.0]), [np.array([1.0]), np.array([hs.IncUnemp])])
        IncShk_un = DiscreteDistribution(
            np.array([1.0]), [np.array([1.0]), np.array([hs.IncUnempNoBenefits])])
        Emp = deepcopy(hs.IncShkDstn[0])
        hs.IncShkDstn = [[Emp] + [IncShk_u] * (num_base_MrkvStates - 2) + [IncShk_un]]
        hs.IncShkDstn_base = hs.IncShkDstn
        hs.DiscFac = float(DiscFacDstns[1].atoms[0][0])
        econ.agents = [hs]
        hs.update_mrkv_array("base")
        hs.solve()

    return {
        "agent": hs,
        "economy": econ,
        "num_base_MrkvStates": num_base_MrkvStates,
        "aXtraCount": aXtraCount if aXtraCount is not None else init_highschool["aXtraCount"],
        "aXtraMax": aXtraMax if aXtraMax is not None else init_highschool["aXtraMax"],
    }


def extract_calibration(solved):
    """Extract the solved agent's EXACT calibration into a plain dict."""
    hs = solved["agent"]
    cFuncs = hs.solution[0].cFunc
    J = len(cFuncs)
    Rvec = np.asarray(hs.Rfree).ravel()
    Rfree = float(Rvec[0])
    assert np.allclose(Rvec, Rfree), Rvec
    IncShk = hs.IncShkDstn[0]

    def shock_nodes(z):
        d = IncShk[z]
        return np.asarray(d.atoms[0]), np.asarray(d.atoms[1]), np.asarray(d.pmv)

    return {
        "cFuncs": cFuncs,
        "J": J,
        "beta": float(hs.DiscFac),
        "rho": float(hs.CRRA),
        "Rfree": Rfree,
        "LivPrb": np.asarray(hs.LivPrb[0]).ravel()[:J],
        "PermGroFac": np.asarray(hs.PermGroFac[0]).ravel()[:J],
        "Mrkv": np.asarray(hs.MrkvArray[0])[:J, :J],
        "shocks": [shock_nodes(z) for z in range(J)],
        "Splurge": float(hs.Splurge),
    }


def solve_egm_from_calibration(calib, factor_mode="standard",
                               aCount=PROD_EGM_ACOUNT, aMax=EGM_AMAX):
    """Independent textbook EGM with the agent's EXACT calibration.

    factor_mode: 'standard' uses (PermGroFac*psi)^(-rho) in the marginal value
      (spec 7.4, standard HARK, the dolo-plus YAML, the post-BUG-047 HAFiscal solver);
      'hafiscal_code' uses psi^(-rho) only — the legacy pre-BUG-047 solver math
      (AggFiscalModel.py marginal-value factor before the fix).
    Returns (egm_callable(m, z) -> c, iterations).
    """
    J = calib["J"]
    beta, rho, Rfree = calib["beta"], calib["rho"], calib["Rfree"]
    LivPrb, PermGroFac, Mrkv = calib["LivPrb"], calib["PermGroFac"], calib["Mrkv"]
    SH = calib["shocks"]
    aGrid = np.concatenate([[0.0], np.exp(np.linspace(np.log(0.01), np.log(aMax), aCount))])
    m0 = np.concatenate([[0.0], np.exp(np.linspace(np.log(0.01), np.log(aMax * 1.05), aCount + 40))])
    mPol = [m0.copy() for _ in range(J)]
    cPol = [m0.copy() for _ in range(J)]
    ce = lambda m, z: np.interp(m, mPol[z], cPol[z])
    it = 0
    for it in range(4000):
        nm, nc, chg = [], [], 0.0
        for z in range(J):
            E = np.zeros_like(aGrid)
            for zp in range(J):
                pz = Mrkv[z, zp]
                if pz == 0.0:
                    continue
                psi, theta, pr = SH[zp]
                Gp = PermGroFac[zp] * psi
                mp = Rfree * np.outer(aGrid, 1.0 / Gp) + theta[None, :]
                cp = ce(mp, zp)
                fac = (Gp if factor_mode == "standard" else psi)[None, :] ** (-rho)
                E += pz * (fac * (cp ** (-rho)) * pr[None, :]).sum(1)
            E *= beta * LivPrb[z] * Rfree
            c = E ** (-1.0 / rho)
            m = aGrid + c
            m = np.concatenate([[0.0], m])
            c = np.concatenate([[0.0], c])
            nm.append(m)
            nc.append(c)
            chg = max(chg, abs(np.interp(5.0, m, c) - ce(5.0, z)))
        mPol, cPol = nm, nc
        if chg < 1e-12:
            break
    return (lambda m, z: float(np.interp(m, mPol[z], cPol[z]))), it + 1


def compare_cfunc(calib, egm, probes=PROBES, gate_m_max=GATE_M_MAX):
    """Compare HAFiscal cFunc[0] (employed) vs the EGM policy across probe points.

    Returns dict with per-probe rows (m, c_hafiscal, c_egm, rel, gated) plus
    maxrel_gated (over m <= gate_m_max — both solvers on-grid) and maxrel_all.
    """
    cFuncs = calib["cFuncs"]
    rows = []
    maxrel_gated, maxrel_all = 0.0, 0.0
    for m in probes:
        ch = float(cFuncs[0](np.array([m]), np.array([1.0]))[0])  # 2D cFunc(m, Cratio=1)
        ce_ = egm(m, 0)
        rel = abs(ch - ce_) / abs(ch)
        gated = m <= gate_m_max
        rows.append({"m": m, "c_hafiscal": ch, "c_egm": ce_, "rel": rel, "gated": gated})
        maxrel_all = max(maxrel_all, rel)
        if gated:
            maxrel_gated = max(maxrel_gated, rel)
    return {"rows": rows, "maxrel_gated": maxrel_gated, "maxrel_all": maxrel_all,
            "gate_m_max": gate_m_max}


def run_check(factor_mode="standard", solved=None, aXtraCount=CHECK_AXTRA_COUNT,
              egm_aCount=CHECK_EGM_ACOUNT, probes=PROBES, gate_m_max=GATE_M_MAX):
    """Full check: solve HAFiscal agent (unless a solved dict is supplied), run the
    EGM at the same calibration, compare. Returns the compare_cfunc() dict plus
    'pass_gate', 'iterations', 'calib', 'solved'."""
    if solved is None:
        solved = build_and_solve_agent(aXtraCount=aXtraCount)
    calib = extract_calibration(solved)
    egm, it = solve_egm_from_calibration(calib, factor_mode=factor_mode, aCount=egm_aCount)
    res = compare_cfunc(calib, egm, probes=probes, gate_m_max=gate_m_max)
    res.update({"pass_gate": res["maxrel_gated"] < GATE_REL, "iterations": it,
                "factor_mode": factor_mode, "calib": calib, "solved": solved})
    return res


def _print_result(res):
    calib = res["calib"]
    solved = res["solved"]
    print(f"[HAFiscal ESC solve] J={calib['J']}  beta={calib['beta']:.6f}  "
          f"rho={calib['rho']}  Rfree={calib['Rfree']}  aXtraCount={solved['aXtraCount']}")
    print(f"  PermGroFac = {np.round(calib['PermGroFac'], 6)}")
    print(f"  LivPrb[:3] = {np.round(calib['LivPrb'][:3], 6)}   Splurge={calib['Splurge']:.4f}")
    print(f"  MrkvArray row0 = {np.round(calib['Mrkv'][0], 4)}")
    print(f"\n[EGM converged it={res['iterations']}, FACTOR_MODE={res['factor_mode']}]  "
          f"comparison of employed-state cFunc[0](m):")
    print(f"  {'m':>6} {'HAFiscal':>12} {'EGM':>12} {'rel.diff':>10}")
    for r in res["rows"]:
        note = "" if r["gated"] else "   (FYI: extrapolation beyond grids, not gated)"
        print(f"  {r['m']:>6.2f} {r['c_hafiscal']:>12.6f} {r['c_egm']:>12.6f} "
              f"{r['rel']:>10.2e}{note}")
    print(f"\nmax rel diff, gated probes m<={res['gate_m_max']:g} (on-grid) = "
          f"{res['maxrel_gated']:.3e}   RESULT: "
          f"{'PASS (<1e-3)' if res['pass_gate'] else 'FAIL'}")
    print(f"max rel diff, all probes (incl. extrapolation FYI)   = {res['maxrel_all']:.3e}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    factor_mode = os.environ.get("EGM_FACTOR_MODE", "standard")
    production = "--production-grids" in argv
    if production:
        axc, eac = None, PROD_EGM_ACOUNT
        print("[grids] PRODUCTION (aXtraCount=48, EGM aCount=220) — informational; "
              "the 1e-3 gate applies at equation-check densities")
    else:
        axc, eac = CHECK_AXTRA_COUNT, CHECK_EGM_ACOUNT
        print(f"[grids] EQUATION-CHECK (aXtraCount={axc}, EGM aCount={eac})")
    res = run_check(factor_mode=factor_mode, aXtraCount=axc, egm_aCount=eac)
    _print_result(res)
    if production:
        print("\n[--production-grids is informational: exit code not gated; "
              "the residual above includes production-grid discretization]")
        return 0
    return 0 if res["pass_gate"] else 1


if __name__ == "__main__":
    sys.exit(main())
