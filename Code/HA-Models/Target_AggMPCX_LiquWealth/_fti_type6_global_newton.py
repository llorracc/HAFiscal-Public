"""Positive confirmation of the CORRECTED fix direction for the patient type-6.

The resolvent probe (_fti_type6_resolvent_probe.py) showed:
  * NAM's per-call solve is ALREADY the exact resolvent (I-T')^{-1}; GMRES on the
    same system is bit-identical (gap ~1e-15) => per-call GMRES cannot help.
  * No EGM fallbacks; the outer loop is plain fixed-point iteration whose rate is
    rho(T') ~ GPF-Mod (0.993 for type-6 => ~900+ outer iters).

The rate-limiter is therefore the LAGGED continuation in HARK's outer loop: each
call linearizes around the previous iterate's policy. The fix is to remove the
lag and Newton-solve the *self-consistent* fixed point F(c)=0 (continuation = the
iterate being solved for) directly. We do this Jacobian-free: GMRES forms the
Jacobian-vector products by finite differences of F, so the FULL Jacobian
(including the tail coupling that NAM's analytic F'_B masks) is captured
automatically. If this converges type-6 in O(1) outer Newton steps regardless of
patience, the fix direction (global Newton-Krylov / Winant improved-time-iteration,
GMRES at the GLOBAL level) is confirmed.
"""
import os
import sys
from copy import deepcopy

import numpy as np
import scipy.optimize as sopt

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.normpath(os.path.join(_HERE, "..", "FromPandemicCode"))):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import _hark_fti_path  # noqa: F401,E402  -- resolve external `hark_fti` (fast-time-iteration)

from HARK.distributions import Uniform, expected
from HARK.interpolation import LinearInterp, LowerEnvelope
from HARK.ConsumptionSaving.ConsIndShockModel import (
    calc_boro_const_nat,
    calc_human_wealth,
    calc_m_nrm_min,
    calc_mpc_max,
    calc_mpc_min,
    calc_patience_factor,
    calc_worst_inc_prob,
)
from hark_fti.ConsIndShockModelFTI import (
    _arbitrage_jacobian_parts,
    solve_one_period_ConsIndShockFTI,
)
import fti_step1


def _base_params():
    b = deepcopy(__import__("SetupParamsCSTW").init_infinite)
    b["LivPrb"] = [1 - 1 / 160]
    b["Rfree"] = 1.02 ** 0.25
    b["Rsave"] = 1.02 ** 0.25
    b["Rboro"] = 1.137 ** 0.25
    b["pLogInitMean"] = 0
    b["UnempPrb"] = 0.044
    b["IncUnemp"] = 0.60
    b["PermShkStd"] = [0.001 ** 0.5]
    b["TranShkStd"] = [0.132 ** 0.5]
    b["BoroCnstArt"] = 0
    b["PermGroFacAgg"] = 1.01 ** 0.25
    b["CRRA"] = 2.0
    b["T_age"] = None
    return b


def _tapered_betas(base, center=0.9608076235664129, spread=0.07128652461546793, TypeCount=7):
    beta_set = Uniform(bot=center - spread, top=center + spread).discretize(TypeCount).atoms[0]
    GICmaxBeta = (1 - base["LivPrb"][0]) + (base["PermGroFacAgg"] ** base["CRRA"]) / base["Rfree"]
    tt, minBeta = 0.01, 0.01
    out = np.array(beta_set, dtype=float)
    for j in range(TypeCount):
        if out[j] > GICmaxBeta - tt:
            out[j] = GICmaxBeta - tt + np.arctan((out[j] - GICmaxBeta + tt) / tt) * tt / np.pi * 2
        elif out[j] < minBeta:
            out[j] = minBeta
    return out


def _gpf_mod(base, DiscFac):
    R = float(np.asarray(base.get("Rsave", base["Rfree"])).reshape(-1)[0])
    G = float(base["PermGroFacAgg"])
    rho = float(base["CRRA"])
    LivPrb = float(base["LivPrb"][0])
    return (R * DiscFac * LivPrb) ** (1.0 / rho) / G


def converge_scalar_chain(IncShkDstn, LivPrb, DiscFac, CRRA, Rfree, PermGroFac,
                          BoroCnstArt, n_iter=20000):
    """Iterate the PERFECT-FORESIGHT scalar chain (hNrm, MPCmin, BoroCnstNat, mNrmMin,
    MPCmax) to its fixed point. Pure scalar recursion — converges to machine precision
    regardless of how slow the *rate* is (the GIC-edge type's chain crawls at ~PatFac,
    so the policy warm-start cannot supply a converged chain in a few steps)."""
    DiscFacEff = DiscFac * LivPrb
    Ex_IncNext = expected(lambda x: x["PermShk"] * x["TranShk"], IncShkDstn)
    WorstIncPrb = calc_worst_inc_prob(IncShkDstn)
    PatFac = calc_patience_factor(Rfree, DiscFacEff, CRRA)
    hNrm, MPCmin, MPCmax, mNrmMin = 0.0, 1.0, 1.0, 0.0
    for _ in range(n_iter):
        hNrm_new = calc_human_wealth(hNrm, PermGroFac, Rfree, Ex_IncNext)
        BoroCnstNat = calc_boro_const_nat(mNrmMin, IncShkDstn, Rfree, PermGroFac)
        mNrmMin_new = calc_m_nrm_min(BoroCnstArt, BoroCnstNat)
        MPCmin_new = calc_mpc_min(MPCmin, PatFac)
        MPCmaxUnc = calc_mpc_max(MPCmax, WorstIncPrb, CRRA, PatFac, BoroCnstNat, BoroCnstArt)
        MPCmax_new = 1.0 if BoroCnstNat < mNrmMin_new else MPCmaxUnc
        d = max(abs(hNrm_new - hNrm), abs(MPCmin_new - MPCmin),
                abs(mNrmMin_new - mNrmMin), abs(MPCmax_new - MPCmax))
        hNrm, MPCmin, MPCmax, mNrmMin = hNrm_new, MPCmin_new, MPCmax_new, mNrmMin_new
        if d < 1e-15:
            break
    BoroCnstNat = calc_boro_const_nat(mNrmMin, IncShkDstn, Rfree, PermGroFac)
    return dict(hNrm=hNrm, MPCmin=MPCmin, MPCmax=MPCmax, mNrmMin=mNrmMin,
                BoroCnstNat=BoroCnstNat)


def make_residual(chain, IncShkDstn, LivPrb, DiscFac, CRRA, Rfree, PermGroFac,
                  BoroCnstArt, aXtraGrid):
    """Self-consistent arbitrage residual F(c_interior) on the fixed m-grid.

    Scalar chain (hNrm, MPCmin, BoroCnstNat) is supplied at its EXACT fixed point
    (``converge_scalar_chain``). The continuation cFunc is rebuilt from the SAME c
    being solved for (no lag).
    """
    DiscFacEff = DiscFac * LivPrb
    hNrmNow = chain["hNrm"]
    BoroCnstNat = chain["BoroCnstNat"]
    mNrmMinNow = calc_m_nrm_min(BoroCnstArt, BoroCnstNat)
    MPCminNow = chain["MPCmin"]
    cFuncLimitIntercept = MPCminNow * hNrmNow
    cFuncLimitSlope = MPCminNow
    cFuncNowCnst = LinearInterp(
        np.array([mNrmMinNow, mNrmMinNow + 1.0]), np.array([0.0, 1.0])
    )
    mNow = np.insert(np.asarray(aXtraGrid, dtype=float) + mNrmMinNow, 0, BoroCnstNat)
    Probs = IncShkDstn.pmv
    PermShk = IncShkDstn.atoms[0]
    TranShk = IncShkDstn.atoms[1]

    def residual(c_int):
        c_full = np.insert(np.asarray(c_int, dtype=float), 0, 0.0)
        cFuncUnc = LinearInterp(mNow, c_full, cFuncLimitIntercept, cFuncLimitSlope)
        cFunc = LowerEnvelope(cFuncUnc, cFuncNowCnst, nan_bool=False)
        parts = _arbitrage_jacobian_parts(
            mNow, c_full, cFunc, cFuncUnc, Probs, PermShk, TranShk, Rfree, CRRA,
            PermGroFac, DiscFacEff,
        )
        if parts is None:
            return np.full_like(c_int, 1e3)
        return parts[0]

    # PF+ linear starting guess from the converged chain: c = MPCmin*(m + hNrm),
    # clipped to be feasible (0 < c < m - BoroCnstNat).
    c0 = MPCminNow * (mNow[1:] + hNrmNow)
    c0 = np.minimum(c0, 0.999 * (mNow[1:] - BoroCnstNat))
    c0 = np.maximum(c0, 1e-6)
    return residual, mNow, c0


def run(j, aXtraMax=1280.0, warm_nam_steps=20, aXtraCount=None, aXtraNestFac=None):
    base = _base_params()
    betas = _tapered_betas(base)
    DiscFac = float(betas[j])
    gpf = _gpf_mod(base, DiscFac)

    agent = fti_step1.make_fti_type(base, DiscFac, method="NAM", autoExtend=False)
    agent.aXtraMax = aXtraMax
    if aXtraCount is not None:
        agent.aXtraCount = aXtraCount
    if aXtraNestFac is not None:
        agent.aXtraNestFac = aXtraNestFac
    agent.update()
    IncShkDstn = agent.IncShkDstn[0]
    LivPrb = float(np.asarray(agent.LivPrb).reshape(-1)[0])
    CRRA = float(agent.CRRA)
    Rfree = float(np.asarray(agent.Rfree).reshape(-1)[0])
    PermGroFac = float(np.asarray(agent.PermGroFac).reshape(-1)[0])
    BoroCnstArt = agent.BoroCnstArt
    aXtraGrid = agent.aXtraGrid

    # EXACT perfect-foresight scalar chain (no policy warm-start needed/used).
    chain = converge_scalar_chain(
        IncShkDstn, LivPrb, DiscFac, CRRA, Rfree, PermGroFac, BoroCnstArt
    )

    residual, mNow, c0 = make_residual(
        chain, IncShkDstn, LivPrb, DiscFac, CRRA, Rfree, PermGroFac, BoroCnstArt, aXtraGrid
    )
    f0 = float(np.max(np.abs(residual(c0))))

    # GLOBAL damped Newton with a DENSE finite-difference Jacobian (captures the FULL
    # self-consistent coupling, incl. the tail that NAM's analytic F'_B masks). Robust
    # where scipy's JFNK line search is fragile on this stiff GIC-edge problem.
    def dense_fd_jac(c, F):
        n = c.size
        Jt = np.empty((n, n))
        for i in range(n):
            d = 1e-7 * (1.0 + abs(c[i]))
            cp = c.copy()
            cp[i] += d
            Jt[i] = (residual(cp) - F) / d
        return Jt.T  # column i = dF/dc_i

    c = c0.copy()
    converged = False
    n_outer = 0
    hist = []
    for n_outer in range(1, 31):
        F = residual(c)
        fnorm = float(np.max(np.abs(F)))
        hist.append(fnorm)
        if fnorm < 1e-8:
            converged = True
            break
        J = dense_fd_jac(c, F)
        try:
            step = np.linalg.solve(J, -F)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(J, -F, rcond=None)[0]
        # damped line search: keep c>0 and reduce ||F||
        t = 1.0
        accepted = False
        for _ in range(30):
            ctrial = c + t * step
            if np.all(ctrial > 0.0) and np.all(np.isfinite(ctrial)):
                if float(np.max(np.abs(residual(ctrial)))) < fnorm:
                    c = ctrial
                    accepted = True
                    break
            t *= 0.5
        if not accepted:
            break
    c_star = c
    f_star = float(np.max(np.abs(residual(c_star))))
    print(f"\n===== type {j}  DiscFac={DiscFac:.10f}  GPF-Mod={gpf:.8f}  aXtraMax={aXtraMax:g} =====")
    print(f"  grid J                        : {mNow.size - 1}")
    print(f"  converged chain: hNrm={chain['hNrm']:.4f} MPCmin={chain['MPCmin']:.6f} "
          f"mNrmMin={chain['mNrmMin']:.4f}")
    print(f"  initial ||F||_inf             : {f0:.3e}")
    print(f"  GLOBAL damped-Newton steps    : {n_outer}   (converged={converged})")
    print(f"  final   ||F||_inf             : {f_star:.3e}")
    print(f"  ||F|| history: " + " ".join(f"{h:.2e}" for h in hist))
    return n_outer, converged, f_star


if __name__ == "__main__":
    print("Global Jacobian-free Newton-Krylov (GMRES) on the SELF-CONSISTENT F(c)=0.")
    print("Contrast with HARK outer-loop NAM: type-3 ~91 iters, type-6 ~900+ iters.")
    run(3, aXtraMax=1280.0)
    run(6, aXtraMax=1280.0)
    print("\n--- type 6 grid refinement (does the stall lift with more knots?) ---")
    run(6, aXtraMax=1280.0, aXtraCount=100)
    run(6, aXtraMax=1280.0, aXtraCount=400)
    run(6, aXtraMax=1280.0, aXtraCount=400, aXtraNestFac=4)
