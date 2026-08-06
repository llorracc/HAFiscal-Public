#!/usr/bin/env python3
"""
Turn-8 numerical validation for HAFiscal-doloplus-draft.yaml (ESC reading).

Two independent solvers of the baseline 6-state Markov buffer-stock that the YAML
describes (the ESC Optimizer sub-household), at test points exercising both the
normal macro state (ADF=1) and a recession macro state (ADF<1):

  (A) From-scratch textbook EGM (independent of the YAML text and of HARK), used to
      evaluate the YAML's STATED Euler residual:
        c_opt(m,z)^(-rho) == beta*LivPrb*Rfree*E_{z',psi',theta'}[ Ghat'^(-rho) c_opt(m',z')^(-rho) ]
      with  Ghat' = PermGroFac[z']*psi',  m' = Rfree*a/Ghat' + theta'*ADF,  a = m - c_opt.
  (B) HARK's own low-level Markov solver (solve_one_period_ConsMarkov), driven directly
      with explicit 6-state inputs (bypassing the 0.17 constructor wrapper, which resets
      MrkvArray/Rfree — the same reason HAFiscal overrides pre_solve). Independent codebase
      cross-check of the consumption VALUE c_opt(5,0).

ADF coupling (Turn 6) is exercised by scaling transitory income by ADF = Cratio^(RecState*kappa):
  - Normal macro (RecState=0): ADF = 1.
  - Recession macro (RecState=1): ADF = Cratio^kappa < 1 for Cratio<1.
A transcription error (wrong G exponent, missing factor, splurge-in-budget, dropped ADF)
would break the Euler residual and/or the EGM-vs-HARK agreement.

PASS: Euler relative residual < 1e-3 at each test point; EGM-vs-HARK c_opt(5,0) agree < 1%.

Run as a script (CLI, same output/exit-code contract as the original one-shot):
  <venv>/bin/python Code/HA-Models/dolo_plus_validation/test_euler_at_point.py

Or via pytest (fast tier = YAML-driven EGM Euler residuals; HARK cross-checks are
@pytest.mark.slow):
  pytest Code/HA-Models/dolo_plus_validation/test_euler_at_point.py -q
"""
import ast
import copy
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[3]
YAML_PATH = REPO / "HAFiscal-doloplus-draft.yaml"

RHO_B, RHO_NB = 0.7, 0.5      # UI-benefits / no-benefits replacement rates
TEST_M, TEST_Z = 5.0, 0       # probe point: m=5, employed state
N_PSI, N_THETA = 9, 9         # shock-node counts
CRATIO_REC = 0.90             # recession-scenario Cratio
EULER_TOL = 1e-3
XCHECK_TOL = 1e-2


# ---- 1. calibration from the YAML --------------------------------------------
@lru_cache(maxsize=1)
def load_calibration():
    import yaml
    cal = yaml.safe_load(YAML_PATH.read_text())["calibration"]
    out = {
        "beta": float(cal["beta"]), "rho": float(cal["rho"]), "Rfree": float(cal["Rfree"]),
        "LivPrb": float(cal["LivPrb"]), "kappa": float(cal["kappa"]),
        "sig_psi": float(cal["sigma_psi"]), "sig_theta": float(cal["sigma_theta"]),
        "N_z": int(cal["N_z"]),
        "PermGroFac_z": [float(x) for x in cal["PermGroFac"]],
        "MrkvArray": np.array(ast.literal_eval(cal["MrkvArray"]), dtype=float),
    }
    assert out["MrkvArray"].shape == (out["N_z"], out["N_z"])
    return out


# ---- 2. equiprobable mean-one lognormal shock nodes -------------------------
def equiprob_lognormal(sigma, n):
    from scipy.stats import norm
    e = norm.ppf(np.linspace(0, 1, n + 1)); pdf = norm.pdf(e)
    z = n * (pdf[:-1] - pdf[1:])
    v = np.exp(sigma * z - 0.5 * sigma ** 2); v *= 1.0 / np.mean(v)
    return v, np.full(n, 1.0 / n)


@lru_cache(maxsize=1)
def shock_nodes():
    """SH[z'] = (psi[], theta[], prob[]) joint nodes per next-period state (pre-ADF theta)."""
    cal = load_calibration()
    N_z = cal["N_z"]
    psi_nodes, psi_p = equiprob_lognormal(cal["sig_psi"], N_PSI)
    theta_emp, theta_p = equiprob_lognormal(cal["sig_theta"], N_THETA)

    def shocks(z):
        th, tp = (theta_emp, theta_p) if z == 0 else \
                 (np.array([RHO_NB]), np.array([1.0])) if z == N_z - 1 else \
                 (np.array([RHO_B]), np.array([1.0]))
        PSI, TH = np.meshgrid(psi_nodes, th, indexing="ij")
        return PSI.ravel(), TH.ravel(), np.outer(psi_p, tp).ravel()

    return [shocks(zp) for zp in range(N_z)], (psi_nodes, psi_p), (theta_emp, theta_p)


# ---- 3a. independent EGM (solves the standard normalized Markov buffer-stock) --
@lru_cache(maxsize=8)
def solve_egm(adf):
    """Returns (c_eval(m, z), iterations, final |dc(5)| change) for the given ADF."""
    cal = load_calibration()
    SH, _, _ = shock_nodes()
    N_z, rho = cal["N_z"], cal["rho"]
    beta, LivPrb, Rfree = cal["beta"], cal["LivPrb"], cal["Rfree"]
    PermGroFac_z, MrkvArray = cal["PermGroFac_z"], cal["MrkvArray"]
    aGrid = np.concatenate([[0.0], np.exp(np.linspace(np.log(0.01), np.log(40.0), 96))])
    m0 = np.concatenate([[0.0], np.exp(np.linspace(np.log(0.01), np.log(45.0), 120))])
    mPol = [m0.copy() for _ in range(N_z)]; cPol = [m0.copy() for _ in range(N_z)]
    def c_eval(m, z): return np.interp(m, mPol[z], cPol[z])
    it, chg = 0, np.inf
    for it in range(3000):
        newm, newc, chg = [], [], 0.0
        for z in range(N_z):
            EmV = np.zeros_like(aGrid)
            for zp in range(N_z):
                pz = MrkvArray[z, zp]
                if pz == 0.0: continue
                psi, theta, pr = SH[zp]; Gp = PermGroFac_z[zp] * psi
                mp = Rfree * np.outer(aGrid, 1.0 / Gp) + (theta * adf)[None, :]
                cp = c_eval(mp, zp)
                EmV += pz * ((Gp[None, :] ** (-rho)) * (cp ** (-rho)) * pr[None, :]).sum(1)
            EmV *= beta * LivPrb * Rfree
            c = EmV ** (-1.0 / rho); m = aGrid + c
            m = np.concatenate([[0.0], m]); c = np.concatenate([[0.0], c])
            newm.append(m); newc.append(c)
            chg = max(chg, abs(np.interp(5.0, m, c) - c_eval(5.0, z)))
        mPol, cPol = newm, newc
        if chg < 1e-12: break
    return (lambda m, z: float(np.interp(m, mPol[z], cPol[z]))), it + 1, chg


def euler_resid(c_of, adf):
    """Evaluate the YAML's stated Euler equation on the EGM solution at (TEST_M, TEST_Z)."""
    cal = load_calibration()
    SH, _, _ = shock_nodes()
    rho = cal["rho"]
    c0 = c_of(TEST_M, TEST_Z); a = TEST_M - c0; lhs = c0 ** (-rho)
    rhs = 0.0
    for zp in range(cal["N_z"]):
        pz = cal["MrkvArray"][TEST_Z, zp]
        if pz == 0.0: continue
        psi, theta, pr = SH[zp]; Ghat = cal["PermGroFac_z"][zp] * psi
        mp = cal["Rfree"] * a / Ghat + theta * adf
        cp = np.array([c_of(x, zp) for x in mp])
        rhs += pz * np.sum(pr * Ghat ** (-rho) * cp ** (-rho))
    rhs *= cal["beta"] * cal["LivPrb"] * cal["Rfree"]
    return c0, lhs, rhs, abs(lhs - rhs) / abs(lhs)


# ---- 3b. HARK low-level cross-check (independent codebase) -------------------
@lru_cache(maxsize=8)
def hark_c50(adf):
    """HARK solve_one_period_ConsMarkov iterated to convergence; returns c_opt(5, z=0)."""
    from HARK.ConsumptionSaving.ConsMarkovModel import MarkovConsumerType, solve_one_period_ConsMarkov
    from HARK.distributions import DiscreteDistributionLabeled
    from HARK.utilities import make_assets_grid
    cal = load_calibration()
    _, (psi_nodes, psi_p), (theta_emp, theta_p) = shock_nodes()
    N_z = cal["N_z"]

    def lab(pv, pp, tv, tp):
        P, T = np.meshgrid(pv, tv, indexing="ij")
        return DiscreteDistributionLabeled(pmv=np.outer(pp, tp).ravel(),
                atoms=np.array([P.ravel(), (T * adf).ravel()]), var_names=["PermShk", "TranShk"])
    Inc = [lab(psi_nodes, psi_p,
               theta_emp if z == 0 else np.array([RHO_NB if z == N_z - 1 else RHO_B]),
               theta_p if z == 0 else np.array([1.0])) for z in range(N_z)]
    st = MarkovConsumerType(cycles=0).solution_terminal
    sol = copy.deepcopy(st)
    sol.cFunc = N_z * [st.cFunc[0]]; sol.vPfunc = N_z * [st.vPfunc[0]]
    sol.vFunc = N_z * [None]; sol.vPPfunc = N_z * [None]
    sol.mNrmMin = np.zeros(N_z); sol.hNrm = np.zeros(N_z)
    sol.MPCmin = np.ones(N_z); sol.MPCmax = np.ones(N_z)
    aXtra = make_assets_grid(0.001, 40.0, 80, None, 3)
    kw = dict(IncShkDstn=Inc, LivPrb=cal["LivPrb"] * np.ones(N_z), DiscFac=cal["beta"],
              CRRA=cal["rho"], Rfree=cal["Rfree"] * np.ones(N_z),
              PermGroFac=np.array(cal["PermGroFac_z"]), MrkvArray=cal["MrkvArray"],
              BoroCnstArt=0.0, aXtraGrid=aXtra, vFuncBool=False, CubicBool=False)
    prev = None
    c5 = np.nan
    for _ in range(800):
        sol = solve_one_period_ConsMarkov(sol, **kw)
        c5 = float(sol.cFunc[0](np.array([5.0]))[0])
        if prev is not None and abs(c5 - prev) < 1e-12: break
        prev = c5
    return c5


# ---- 4. scenarios -------------------------------------------------------------
def scenarios():
    kappa = load_calibration()["kappa"]
    return [
        ("normal   (z=0, Cratio=1.0)", 1.0),
        (f"recession(z=0, Cratio={CRATIO_REC}, kappa={kappa})", CRATIO_REC ** (1.0 * kappa)),
    ]


def _adf(scenario):
    kappa = load_calibration()["kappa"]
    return 1.0 if scenario == "normal" else CRATIO_REC ** (1.0 * kappa)


# ---- pytest tier --------------------------------------------------------------
# Fast tier: YAML-driven EGM Euler residuals only (no HAFiscal/HARK solve; seconds).
@pytest.mark.parametrize("scenario", ["normal", "recession"])
def test_euler_residual(scenario):
    adf = _adf(scenario)
    c_of, it, chg = solve_egm(adf)
    assert chg < 1e-12, f"EGM did not converge (it={it}, |dc(5)|={chg:.1e})"
    c0, lhs, rhs, rel = euler_resid(c_of, adf)
    assert rel < EULER_TOL, (
        f"[{scenario}] Euler residual {rel:.3e} >= {EULER_TOL} "
        f"(c0={c0:.6f}, lhs={lhs:.6e}, rhs={rhs:.6e})")


# Slow tier: independent-codebase HARK value cross-check (iterated full Markov solve).
@pytest.mark.slow
@pytest.mark.parametrize("scenario", ["normal", "recession"])
def test_egm_vs_hark_crosscheck(scenario):
    adf = _adf(scenario)
    c_of, _, _ = solve_egm(adf)
    c0 = c_of(TEST_M, TEST_Z)
    ch = hark_c50(adf)
    xchk = abs(c0 - ch) / abs(ch)
    assert xchk < XCHECK_TOL, (
        f"[{scenario}] EGM c(5,0)={c0:.6f} vs HARK {ch:.6f}: rel diff {xchk:.2e} >= {XCHECK_TOL}")


# ---- CLI ----------------------------------------------------------------------
def main():
    print("=" * 70)
    print("HAFiscal dolo-plus YAML — Turn-8 numerical validation")
    print("=" * 70)
    ok = True
    for label, adf in scenarios():
        c_of, it, chg = solve_egm(adf)
        c0, lhs, rhs, rel = euler_resid(c_of, adf)
        ch = hark_c50(adf)
        xchk = abs(c0 - ch) / abs(ch)
        p_eul = rel < EULER_TOL; p_x = xchk < XCHECK_TOL
        ok = ok and p_eul and p_x
        print(f"\n[{label}]   ADF={adf:.5f}")
        print(f"  EGM converged it={it} (|dc(5)|={chg:.1e})")
        print(f"  c_opt(5,0): EGM={c0:.6f}   HARK={ch:.6f}   |diff|/HARK={xchk:.2e}  {'PASS' if p_x else 'FAIL'}(<1e-2)")
        print(f"  Euler resid (YAML eq on EGM soln): {rel:.3e}  {'PASS' if p_eul else 'FAIL'}(<1e-3)")
    print("\n" + "=" * 70)
    print(f"OVERALL: {'PASS' if ok else 'FAIL'}")
    print("=" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
