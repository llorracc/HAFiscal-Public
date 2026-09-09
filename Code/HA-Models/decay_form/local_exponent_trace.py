"""Which power law rules the REACHABLE range? Deep-solve single-state proxies of
HAFiscal College atoms and trace the local exponent Q(x) = -d ln gap / d ln(x+h)
against three anchors: q_det (psi==1 root), q* (Kesten root, discrete psi),
and min(1, q*) (the asymptotic income channel).

Owner conjecture (2026-07-21): over the mortality-reachable range the gap follows
a simpler (psi=1-regime) power law and the supercritical asymptotic apparatus is
practically irrelevant. Gap floor guard: gap/c > 1e-10 (decay_form convention).
"""
import numpy as np
from scipy.optimize import brentq
from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType

R, GAMMA, RHO, LIV = 1.01, 1.0 + 0.01958 / 4, 2.0, 1.0 - 1.0 / 160.0
PSI_STD, XI_STD, UNEMP, INC_UN = np.sqrt(0.003), np.sqrt(0.12), 0.027, 0.7


def qstar_discrete(beta, psi, pmv):
    PG = (R * beta * LIV) ** (1.0 / RHO) / GAMMA
    if PG >= 1.0:
        return np.nan
    def f(q):
        return np.log(np.dot(pmv, psi ** (1.0 + q))) - np.log(R / GAMMA) - q * np.log(PG)
    if f(0.0) >= 0.0:
        return np.nan
    hi = 1.0
    while f(hi) < 0.0 and hi < 512.0:
        hi *= 2.0
    return brentq(f, 0.0, hi, xtol=1e-10)


def q_det(beta):
    PG = (R * beta * LIV) ** (1.0 / RHO) / GAMMA
    return np.log(R / GAMMA) / (-np.log(PG)) if PG < 1.0 else np.nan


def trace(name, beta):
    ag = IndShockConsumerType(
        cycles=0, Rfree=[R], PermGroFac=[GAMMA], DiscFac=beta, CRRA=RHO,
        LivPrb=[LIV], PermShkStd=[PSI_STD], TranShkStd=[XI_STD],
        UnempPrb=UNEMP, IncUnemp=INC_UN, T_cycle=1,
        aXtraMax=1.0e6, aXtraCount=320, aXtraNestFac=3,
        vFuncBool=False, CubicBool=False)
    ag.solve()
    sol = ag.solution[0]
    dstn = ag.IncShkDstn[0]
    psi = np.asarray(dstn.atoms[0], float)
    pmv = np.asarray(dstn.pmv, float)
    qs, qd = qstar_discrete(beta, psi, pmv), q_det(beta)
    PG = (R * beta * LIV) ** (1.0 / RHO) / GAMMA
    drift = np.log(PG) - np.dot(pmv, np.log(psi))  # E[dln aNrm] in the accumulation regime
    print(f"\n=== {name}: beta={beta:.6f}  P_Gamma={PG:.6f}  Rcal*P_Gamma={PG*R/GAMMA:.6f}")
    print(f"    anchors: q_det(psi=1)={qd:.3f}   q*(Kesten)={qs:.4f}   min(1,q*)={min(1.0, qs):.4f}")
    print(f"    MPCmin={sol.MPCmin:.6f}  hNrm={sol.hNrm:.2f}  top-drift E[dln a]={drift:+.6f}/qtr "
          f"(={drift*4*100:+.2f}%/yr; e-folds per 40y life: {drift*160:+.3f})")
    lad = np.geomspace(5.0, 3.0e5, 40)
    c = sol.cFunc(lad)
    gap = sol.MPCmin * (lad + sol.hNrm) - c
    ok = gap / c > 1e-10
    x = lad + sol.hNrm
    lg, lx = np.log(gap[ok]), np.log(x[ok])
    Q = -(lg[2:] - lg[:-2]) / (lx[2:] - lx[:-2])   # centered local exponent
    mid = lad[ok][1:-1]
    print(f"    {'m':>10} {'gap/c':>10} {'Q_local':>8}")
    for m_, g_, c_, q_ in zip(mid, gap[ok][1:-1], c[ok][1:-1], Q):
        print(f"    {m_:>10.0f} {g_/c_:>10.2e} {q_:>8.3f}")


trace("College GIC-cap atom (strip: GPF_in>1, production)", 1.0053691243346485)
trace("College atom #4 (subcritical bulk)", 0.9919)
