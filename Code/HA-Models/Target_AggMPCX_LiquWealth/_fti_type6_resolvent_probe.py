"""Decisive probe: WHY does plain NAM crawl on the patient GIC-edge type-6, and
would a GMRES-accelerated resolvent fix it?

Mechanism under test
--------------------
NAM's per-call step solves ``(F'_A + F'_B) step = -F`` *exactly* (sparse direct).
Writing ``D = F'_A`` (diagonal) and ``T' = -D^{-1} F'_B`` (the time-iteration
operator), that step is

    step = (D + F'_B)^{-1}(-F) = (I - T')^{-1} D^{-1}(-F) = (I - T')^{-1} ddx,

i.e. NAM ALREADY applies the full resolvent ``(I - T')^{-1}`` each outer step.
So a GMRES solve of the *same* linear system must return the *same* step and
therefore CANNOT change the number of HARK outer iterations. If type-6 still
crawls, the rate-limiter is NOT the inner linear solve. The two real suspects:

  (S1) third-effect MASKING: ``on_segment`` zeros F'_B wherever next-period m
       lands in the limiting-MPC extrapolation tail (mathematically correct:
       the tail does not depend on interior knots). If the patient agent's
       dynamics live in that tail, (D+F'_B) ~ D and the step ~ one plain
       time-iteration step => linear at rate ~ patience.
  (S2) EGM FALLBACK: solve_one_period falls back to ONE EGM step whenever the
       NAM step is infeasible (c<=0 or a<BoroCnstNat) or the continuation is
       invalid. If that fires every outer iter for type-6, "NAM" is silently
       just EGM time-iteration => linear at rate ~ patience.

This script instruments _nam_newton_step (called once per outer iteration),
records per-iteration: spectral radius rho(T') (power iteration), masked
fraction of (j,k) pairs, feasibility of the raw NAM step, and GMRES-vs-spsolve
step agreement. It runs a moderate type (fast) and type-6 (GIC edge) for
contrast, at aXtraMax=1280, autoExtend OFF.
"""
import os
import sys
from copy import deepcopy

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import gmres, LinearOperator

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.normpath(os.path.join(_HERE, "..", "FromPandemicCode"))):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import _hark_fti_path  # noqa: F401,E402  -- resolve external `hark_fti` (fast-time-iteration)

from HARK.distributions import Uniform
import hark_fti.ConsIndShockModelFTI as M
from hark_fti.ConsIndShockModelFTI import (
    _arbitrage_jacobian_parts,
    _build_dF_dC_coo,
    _apply_off_diag,
)

import fti_step1


# ---- Step-1 NOR base_params + tapered betas (mirror test_fti_step1.py) -------
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
    # GPFacMod = (R*DiscFac*LivPrb)^(1/rho) / G  (modified growth-patience factor)
    return (R * DiscFac * LivPrb) ** (1.0 / rho) / G


# ---- instrumented Newton step ------------------------------------------------
_REC = []  # one dict per outer iteration


def _rho_power_iter(matvec, n, iters=200):
    """Estimate spectral radius of a linear operator by power iteration."""
    v = np.random.default_rng(0).standard_normal(n)
    v /= np.linalg.norm(v) + 1e-300
    lam = 0.0
    for _ in range(iters):
        w = matvec(v)
        nw = np.linalg.norm(w)
        if nw == 0.0 or not np.isfinite(nw):
            return nw
        lam = nw  # |lambda| ~ ||T'v|| for unit v at convergence
        v = w / nw
    return lam


def _instrumented_nam_step(mNow, cNow, cFunc_next, cFuncUnc_next, Probs, PermShk,
                           TranShk, Rfree, CRRA, PermGroFac, DiscFacEff):
    parts = _arbitrage_jacobian_parts(
        mNow, cNow, cFunc_next, cFuncUnc_next, Probs, PermShk, TranShk, Rfree, CRRA,
        PermGroFac, DiscFacEff,
    )
    if parts is None:
        _REC.append({"branch": "egm_invalid"})
        return None
    F, dF_dC_diag, L, GammaC_adj, Gamma_adj = parts
    J = mNow.size - 1

    # --- exact NAM step (sparse direct) ---
    rows, cols, data = _build_dF_dC_coo(L, GammaC_adj, Gamma_adj, dF_dC_diag)
    A = sparse.coo_array((data, (rows, cols)), shape=(J, J)).tocsc()
    step = sparse.linalg.spsolve(A, -F, permc_spec="NATURAL")

    # --- T' = -(D^{-1}) F'_B operator (matrix free), spectral radius ---
    Dinv = 1.0 / dF_dC_diag
    def Tp(u):
        return -Dinv * _apply_off_diag(u, L, GammaC_adj, Gamma_adj)
    rho = _rho_power_iter(Tp, J, iters=300)

    # --- masked fraction: on_segment was applied inside parts; reconstruct it ---
    # GammaC_adj/Gamma_adj already carry the on_segment mask. Count (j,k) with BOTH
    # weights ~0 as "masked" (third effect inactive there).
    both_zero = (np.abs(GammaC_adj) < 1e-30) & (np.abs(Gamma_adj) < 1e-30)
    mask_frac = float(both_zero.mean())

    # --- GMRES on the SAME system; compare step ---
    Aop = LinearOperator((J, J), matvec=lambda x: A @ x)
    gx, info = gmres(Aop, -F, rtol=1e-10, maxiter=2 * J)
    gmres_gap = float(np.max(np.abs(gx - step)))

    # --- feasibility of the raw NAM step (c>0 and a=m-c not too negative) ---
    cTrial = cNow[1:] + step
    aTrial = mNow[1:] - cTrial
    feasible = bool(np.all(np.isfinite(cTrial)) and np.all(cTrial > 0.0))
    min_a = float(np.min(aTrial))

    _REC.append({
        "branch": "nam",
        "J": J,
        "rho_Tp": float(rho),
        "mask_frac": mask_frac,
        "gmres_gap": gmres_gap,
        "gmres_info": int(info),
        "feasible_raw": feasible,
        "min_a": min_a,
        "max_step": float(np.max(np.abs(step))),
        "max_F": float(np.max(np.abs(F))),
    })
    return cNow[1:] + step


def run_type(base, betas, j, aXtraMax=1280.0, max_outer=400):
    _REC.clear()
    DiscFac = float(betas[j])
    gpf = _gpf_mod(base, DiscFac)
    fti = fti_step1.make_fti_type(base, DiscFac, method="NAM", autoExtend=False)
    fti.aXtraMax = aXtraMax
    fti.update()           # rebuild aXtraGrid etc. at the new top
    fti.tolerance = 1e-6
    fti.max_iterations = max_outer
    # patch the module-level step used by solve_one_period
    orig = M._nam_newton_step
    M._nam_newton_step = _instrumented_nam_step
    try:
        fti.solve(verbose=False)
    finally:
        M._nam_newton_step = orig
    iters = int(getattr(fti, "completed_cycles", -1))
    recs = list(_REC)
    n_nam = sum(r["branch"] == "nam" for r in recs)
    n_invalid = sum(r["branch"] == "egm_invalid" for r in recs)
    n_infeasible = sum(r["branch"] == "nam" and not r["feasible_raw"] for r in recs)
    nam_recs = [r for r in recs if r["branch"] == "nam"]
    print(f"\n===== type {j}  DiscFac={DiscFac:.10f}  GPF-Mod={gpf:.8f}  aXtraMax={aXtraMax:g} =====")
    print(f"  outer iters (completed_cycles) : {iters}   (cap={max_outer})")
    print(f"  solve_one_period calls         : {len(recs)}")
    print(f"    NAM-step branch              : {n_nam}")
    print(f"    EGM fallback (invalid cont.) : {n_invalid}")
    print(f"    NAM step raw-INFEASIBLE      : {n_infeasible}  (-> damped or EGM fallback)")
    if nam_recs:
        last = nam_recs[-5:]
        print("  last NAM-branch iterations:")
        print("    rho(T')     mask_frac  gmres_gap   feas  min_a       max_step    max_|F|")
        for r in last:
            print("    {rho_Tp:<11.7f} {mask_frac:<9.4f} {gmres_gap:<11.2e} {feas}  "
                  "{min_a:<11.3e} {max_step:<11.3e} {max_F:.2e}".format(
                      feas=("Y" if r["feasible_raw"] else "N"), **r))
        rhos = np.array([r["rho_Tp"] for r in nam_recs])
        masks = np.array([r["mask_frac"] for r in nam_recs])
        gaps = np.array([r["gmres_gap"] for r in nam_recs])
        print(f"  rho(T')   over NAM iters: min={rhos.min():.6f} max={rhos.max():.6f} last={rhos[-1]:.6f}")
        print(f"  mask_frac over NAM iters: min={masks.min():.4f} max={masks.max():.4f} last={masks[-1]:.4f}")
        print(f"  max GMRES-vs-spsolve step gap over all iters: {gaps.max():.2e}")
    return iters, recs


if __name__ == "__main__":
    base = _base_params()
    betas = _tapered_betas(base)
    print("tapered betas:", np.round(betas, 8))
    # moderate (fast) contrast then the GIC-edge type
    run_type(base, betas, 3, aXtraMax=1280.0, max_outer=400)
    run_type(base, betas, 6, aXtraMax=1280.0, max_outer=400)
