"""PoC: can FTI (NAM) speed up HAFiscal's Step-1 most-patient agent?

HAFiscal's Step-1 beta/splurge estimation (Target_AggMPCX_LiquWealth/
Estimation_BetaNablaSplurge.py) solves an infinite-horizon (cycles=0), single-state,
KinkedR-with-BoroCnstArt=0 problem -- which its own docstring calls "mathematically
equivalent to IndShockConsumerType". Discount factors are tapered toward the growth-
impatience bound GICmaxBeta, so the most patient type sits at GPF-Mod ~ 0.999: exactly the
regime where EGM time-iteration crawls and NAM wins big.

This script, using HAFiscal's *own* calibration constants, pins that most-patient type and:
  (A) "as configured" -- times HAFiscal's KinkedR-EGM (aXtraMax=20) vs FTI-NAM (auto grid).
  (B) "apples-to-apples" -- discovers a properly sized grid, then times EGM vs NAM on the
      identical grid and checks policy + Euler-error parity.
  (C) "clean pattern" -- transplants the NAM cFunc into a KinkedRconsumerType and confirms
      the policy is identical (so HAFiscal can keep its existing simulate()/RNG path).

Run (from FromPandemicCode/):
  HAFiscal-Latest/.venv/bin/python fti_diagnostics/poc_hafiscal_step1_fti.py
"""
from __future__ import annotations

import os
import sys
import time
from copy import deepcopy

import numpy as np

# The FTI solver (`hark_fti.ConsIndShockModelFTI`) now lives in the sibling
# fast-time-iteration repo (its canonical home); `_hark_fti_path` (in FromPandemicCode)
# locates that checkout. hark_fti's internal imports are all `HARK.`-qualified, so they
# bind to HAFiscal's installed HARK (the venv this runs under). SetupParamsCSTW (Step-1
# calibration constants) comes from HAFiscal's Target_AggMPCX_LiquWealth.
_HERE = os.path.dirname(os.path.abspath(__file__))
_FROMPANDEMIC = os.path.normpath(os.path.join(_HERE, ".."))
_HAF_STEP1 = os.path.normpath(os.path.join(_FROMPANDEMIC, "..", "Target_AggMPCX_LiquWealth"))
for _p in (_FROMPANDEMIC, _HAF_STEP1):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import _hark_fti_path  # noqa: F401,E402  -- resolve external `hark_fti` (fast-time-iteration)

from HARK.distributions import Uniform
from HARK.ConsumptionSaving.ConsIndShockModel import (
    IndShockConsumerType,
    KinkedRconsumerType,
)
from hark_fti.ConsIndShockModelFTI import IndShockConsumerTypeFTI
from SetupParamsCSTW import init_infinite


# --------------------------------------------------------------------------------------- #
# 1. Reproduce HAFiscal Step-1 NOR base_params + the tapered discount-factor ladder.
#    (mirrors Estimation_BetaNablaSplurge.py lines 167-202 and 345-355)
# --------------------------------------------------------------------------------------- #
def hafiscal_base_params():
    b = deepcopy(init_infinite)
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


def tapered_betas(base, center, spread, TypeCount=7):
    beta_set = Uniform(bot=center - spread, top=center + spread).discretize(TypeCount).atoms[0]
    GICmaxBeta = (1 - base["LivPrb"][0]) + (base["PermGroFacAgg"] ** base["CRRA"]) / base["Rfree"]
    tt, minBeta = 0.01, 0.01
    out = np.array(beta_set, dtype=float)
    for j in range(TypeCount):
        if out[j] > GICmaxBeta - tt:
            out[j] = GICmaxBeta - tt + np.arctan((out[j] - GICmaxBeta + tt) / tt) * tt / np.pi * 2
        elif out[j] < minBeta:
            out[j] = minBeta
    return out, GICmaxBeta


def gpf_mod(base, DiscFac):
    R, rho, G = base["Rfree"], base["CRRA"], base["PermGroFac"][0]
    LivPrb = base["LivPrb"][0]
    E_inv_psi = np.exp(base["PermShkStd"][0] ** 2)  # E[psi^-1], mean-one lognormal
    abs_pat = (R * DiscFac) ** (1.0 / rho)
    return abs_pat * LivPrb * E_inv_psi / G


# --------------------------------------------------------------------------------------- #
# 2. Solver params + builders (clean minimal dict; only keys the types use).
# --------------------------------------------------------------------------------------- #
SOLVE_KEYS = (
    "CRRA Rfree PermGroFac BoroCnstArt PermShkStd PermShkCount TranShkStd TranShkCount "
    "UnempPrb IncUnemp aXtraMin aXtraMax aXtraCount aXtraNestFac LivPrb"
).split()


def solve_params(base, DiscFac, aXtraMax=None, aXtraCount=None):
    p = {k: deepcopy(base[k]) for k in SOLVE_KEYS}
    # FTI/IndShock expect the time-varying (list) form for Rfree.
    p["Rfree"] = [float(np.asarray(base["Rfree"]).reshape(-1)[0])]
    p.update(DiscFac=DiscFac, cycles=0, T_cycle=1, vFuncBool=False, CubicBool=False,
             aXtraExtra=None)
    if aXtraMax is not None:
        p["aXtraMax"] = float(aXtraMax)
    if aXtraCount is not None:
        p["aXtraCount"] = int(aXtraCount)
    return p


def make_egm(base, DiscFac, **grid):
    a = IndShockConsumerType(**solve_params(base, DiscFac, **grid))
    a.cycles = 0
    return a


def make_kinkedR(base, DiscFac, **grid):
    p = solve_params(base, DiscFac, **grid)
    p.pop("Rfree", None)  # KinkedR derives the saving/borrowing kink from Rboro/Rsave
    p.update(Rboro=base["Rboro"], Rsave=base["Rsave"])
    a = KinkedRconsumerType(**p)
    a.cycles = 0
    return a


def make_nam(base, DiscFac, *, autoExtend, **grid):
    a = IndShockConsumerTypeFTI(method="NAM", autoExtendGridTop=autoExtend,
                                **solve_params(base, DiscFac, **grid))
    a.cycles = 0
    return a


# --------------------------------------------------------------------------------------- #
# 3. Timing + accuracy helpers.
# --------------------------------------------------------------------------------------- #
def timed_solve(make, *, repeats=2, warmup=True):
    if warmup:
        make().solve()
    best, iters, agent = np.inf, -1, None
    for _ in range(repeats):
        agent = make()
        t0 = time.perf_counter()
        agent.solve()
        best = min(best, time.perf_counter() - t0)
        iters = int(getattr(agent, "completed_cycles", -1))
    return agent, iters, best


def euler_errors(agent, m_vals):
    sol = agent.solution[0]
    cFunc = sol.cFunc
    R = float(np.asarray(agent.Rfree).reshape(-1)[0])
    G = float(np.asarray(agent.PermGroFac).reshape(-1)[0])
    rho = float(agent.CRRA)
    DiscFacEff = float(agent.DiscFac) * float(np.asarray(agent.LivPrb).reshape(-1)[0])
    dstn = agent.IncShkDstn[0]
    probs = np.asarray(dstn.pmv, dtype=float)
    perm = np.asarray(dstn.atoms[0], dtype=float)
    tran = np.asarray(dstn.atoms[1], dtype=float)
    m = np.asarray(m_vals, dtype=float)
    c = np.asarray(cFunc(m), dtype=float)
    a = m - c
    mNext = (R / (G * perm))[None, :] * a[:, None] + tran[None, :]
    cNext = np.asarray(cFunc(mNext.ravel()), dtype=float).reshape(mNext.shape)
    EndOfPrdvP = DiscFacEff * R * G ** (-rho) * (
        probs[None, :] * perm[None, :] ** (-rho) * cNext ** (-rho)
    ).sum(axis=1)
    c_opt = EndOfPrdvP ** (-1.0 / rho)
    return (c - c_opt) / c_opt


# --------------------------------------------------------------------------------------- #
# 4. Run.
# --------------------------------------------------------------------------------------- #
_GRIDTOP_CAP = 64.0 * 20.0  # FTI gridTopMaxFac (64) x HAFiscal initial top (20)


def same_grid_compare(base, DiscFac, label):
    """Discover an accuracy-appropriate grid via NAM autoExtend, then time EGM vs NAM on it.

    Returns a dict; if the type is at the GIC edge (autoExtend hits the grid-top cap or NAM
    fails to converge), reports that instead of running a slow big-grid EGM.
    """
    nam_disc, nam_it, nam_t = timed_solve(
        lambda: make_nam(base, DiscFac, autoExtend=True), repeats=1, warmup=False)
    aMax = float(nam_disc.aXtraMax)
    J = int(np.asarray(nam_disc.aXtraGrid).size)
    hit_cap = aMax >= _GRIDTOP_CAP - 1.0
    diverged = nam_it >= 2000
    if hit_cap or diverged:
        return dict(label=label, DiscFac=DiscFac, gpf=gpf_mod(base, DiscFac),
                    pathological=True, aMax=aMax, J=J, nam_it=nam_it, nam_t=nam_t)

    grid = dict(aXtraMax=aMax, aXtraCount=J)
    egm, egm_it, egm_t = timed_solve(lambda: make_egm(base, DiscFac, **grid),
                                     repeats=1, warmup=False)
    nam, nit, nt = timed_solve(lambda: make_nam(base, DiscFac, autoExtend=False, **grid),
                               warmup=False)
    m_test = np.linspace(0.5, max(5.0, aMax * 0.5), 60)
    dC = float(np.max(np.abs(np.asarray(egm.solution[0].cFunc(m_test))
                             - np.asarray(nam.solution[0].cFunc(m_test)))))
    return dict(label=label, DiscFac=DiscFac, gpf=gpf_mod(base, DiscFac),
                pathological=False, aMax=aMax, J=J,
                egm_it=egm_it, egm_t=egm_t, nam_it=nit, nam_t=nt, dC=dC,
                ee_egm=float(np.max(np.abs(euler_errors(egm, m_test)))),
                ee_nam=float(np.max(np.abs(euler_errors(nam, m_test)))),
                nam_agent=nam)


def main():
    base = hafiscal_base_params()
    center, spread = 0.9608076235664129, 0.07128652461546793  # Result_AllTarget.txt
    betas, GICmaxBeta = tapered_betas(base, center, spread, TypeCount=7)

    print("=" * 80)
    print("HAFiscal Step-1 (NOR) discount-factor ladder")
    print("=" * 80)
    print(f"GICmaxBeta = {GICmaxBeta:.6f}   config grid: aXtraMax={base['aXtraMax']}, "
          f"aXtraCount={base['aXtraCount']}")
    for j, bb in enumerate(betas):
        print(f"  type {j}: DiscFac={bb:.6f}  GPF-Mod={gpf_mod(base, bb):.5f}"
              f"{'   <- most patient (GIC edge)' if j == len(betas) - 1 else ''}")

    make_nam(base, float(betas[0]), autoExtend=False).solve()  # one-time numba warmup

    # ---- Part 1: per-type EGM cost on HAFiscal's actual grid (what it pays today) ----- #
    print("\n" + "=" * 80)
    print("Part 1 - EGM cost per type on HAFiscal's grid (KinkedR, aXtraMax=20, J=20)")
    print("=" * 80)
    print(f"{'type':>5} {'GPF-Mod':>8} {'iters':>7} {'ms':>9}")
    for j, bb in enumerate(betas):
        _, it, t = timed_solve(lambda b=bb: make_kinkedR(base, b), repeats=2)
        print(f"{j:>5} {gpf_mod(base, bb):>8.5f} {it:>7} {t*1e3:>9.1f}", flush=True)

    # ---- Part 2: same-grid EGM vs NAM for moderately-patient types ------------------- #
    print("\n" + "=" * 80)
    print("Part 2 - Accuracy-appropriate grid: EGM vs FTI-NAM (same grid), per type")
    print("=" * 80)
    print(f"{'type':>5} {'GPF-Mod':>8} {'J':>5} {'EGM it':>7} {'EGM ms':>8} "
          f"{'NAM it':>7} {'NAM ms':>8} {'iters x':>8} {'speed x':>8} "
          f"{'max|dC|':>9} {'EE EGM':>8} {'EE NAM':>8}")
    results = {}
    for j in (1, 2, 3, 4, 5, 6):
        r = same_grid_compare(base, float(betas[j]), f"type{j}")
        results[j] = r
        if r["pathological"]:
            print(f"{j:>5} {r['gpf']:>8.5f} {r['J']:>5}  PATHOLOGICAL: autoExtend hit "
                  f"top={r['aMax']:.0f} / NAM iters={r['nam_it']} (GIC edge)", flush=True)
        else:
            print(f"{j:>5} {r['gpf']:>8.5f} {r['J']:>5} {r['egm_it']:>7} "
                  f"{r['egm_t']*1e3:>8.1f} {r['nam_it']:>7} {r['nam_t']*1e3:>8.1f} "
                  f"{r['egm_it']/max(r['nam_it'],1):>8.1f} {r['egm_t']/r['nam_t']:>8.2f} "
                  f"{r['dC']:>9.1e} {r['ee_egm']:>8.1e} {r['ee_nam']:>8.1e}", flush=True)

    # ---- Part 3: clean pattern transplant on a type where NAM wins ------------------- #
    print("\n" + "=" * 80)
    print("Part 3 - Clean pattern: transplant NAM cFunc into a KinkedRconsumerType")
    print("=" * 80)
    win = next((results[j] for j in (4, 3, 2) if not results[j]["pathological"]), None)
    if win is None:
        print("  (no non-pathological winner among types 2-4; skipping transplant demo)")
    else:
        nam = win["nam_agent"]
        host = make_kinkedR(base, win["DiscFac"], aXtraMax=win["aMax"], aXtraCount=win["J"])
        host.solve()
        c_before = float(host.solution[0].cFunc(10.0))
        host.solution[0].cFunc = nam.solution[0].cFunc  # the transplant
        m_chk = np.linspace(0.5, 30.0, 40)
        ok = np.allclose(np.asarray(host.solution[0].cFunc(m_chk)),
                         np.asarray(nam.solution[0].cFunc(m_chk)), rtol=0, atol=0)
        sim_ok = True
        try:
            host.track_vars = ["cNrm"]
            host.T_sim, host.AgentCount = 5, 200
            host.initialize_sim()
            host.simulate()
        except Exception as e:  # noqa: BLE001
            sim_ok = f"sim failed: {type(e).__name__}: {e}"
        print(f"  using {win['label']} (GPF-Mod={win['gpf']:.5f})")
        print(f"  c(10): host-EGM before={c_before:.6f}  after-transplant="
              f"{float(host.solution[0].cFunc(10.0)):.6f}  NAM={float(nam.solution[0].cFunc(10.0)):.6f}")
        print(f"  cFunc identical to NAM after transplant: {bool(ok)}")
        print(f"  initialize_sim()+simulate() with transplanted policy: {sim_ok}")

    print("\nDONE.")


if __name__ == "__main__":
    main()
