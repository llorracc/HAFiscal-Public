"""Prototype the owner's two-secant local-Q scheme (2026-07-22).

For each candidate solve-grid top T: place two augmented points below T
(geometric in the power law's own abscissa x+h, ratio r), form two log-log
secant estimates Q1 (lower pair) and Q2 (upper pair) from the DEEP-solved
truth, then attach gap(x) = gap(T)*((x+h)/(T+h))**(-Q2) and measure the
extrapolation error against the deep truth over the TM evaluation range
[T, 2500] (production TM_AMAX ~1300, with margin).

Diagnostic: drift = (Q2 - Q1) / (per e-fold of ln(x+h)).
Feasibility: geometric-in-(x+h) placement needs T > h*(1/r^2 - 1).
"""
import numpy as np
from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType

R, GAMMA, RHO, LIV = 1.01, 1.0 + 0.01958 / 4, 2.0, 1.0 - 1.0 / 160.0
PSI_STD, XI_STD, UNEMP, INC_UN = np.sqrt(0.003), np.sqrt(0.12), 0.027, 0.7


def deep_solve(beta):
    ag = IndShockConsumerType(
        cycles=0, Rfree=[R], PermGroFac=[GAMMA], DiscFac=beta, CRRA=RHO,
        LivPrb=[LIV], PermShkStd=[PSI_STD], TranShkStd=[XI_STD],
        UnempPrb=UNEMP, IncUnemp=INC_UN, T_cycle=1,
        aXtraMax=1.0e6, aXtraCount=320, aXtraNestFac=3,
        vFuncBool=False, CubicBool=False)
    ag.solve()
    return ag.solution[0]


def gap_of(sol, m):
    return sol.MPCmin * (m + sol.hNrm) - sol.cFunc(m)


def two_secant(sol, T, r):
    """Q1, Q2 from three points geometric in (x+h): T, then r, r^2 below."""
    h = sol.hNrm
    xs = np.array([(T + h) * r ** 2, (T + h) * r, T + h])
    ms = xs - h
    if ms[0] <= 0.05:
        return None
    g = gap_of(sol, ms)
    if np.any(g <= 0):
        return None
    lg, lx = np.log(g), np.log(xs)
    Q1 = -(lg[1] - lg[0]) / (lx[1] - lx[0])
    Q2 = -(lg[2] - lg[1]) / (lx[2] - lx[1])
    drift_per_efold = (Q2 - Q1) / ((lx[2] - lx[0]) / 2.0)
    return ms, Q1, Q2, drift_per_efold


def attach_error(sol, T, Q, eval_top=2500.0):
    """Relative errors of the constant-Q attach from T over [T, eval_top]."""
    h = sol.hNrm
    gT = float(gap_of(sol, T))
    lad = np.geomspace(T * 1.02, eval_top, 25)
    g_true = gap_of(sol, lad)
    c_true = sol.cFunc(lad)
    g_att = gT * ((lad + h) / (T + h)) ** (-Q)
    c_att = sol.MPCmin * (lad + h) - g_att
    return np.max(np.abs(c_att - c_true) / c_true), np.max(np.abs(g_att - g_true) / g_true)


for name, beta in (("cap atom (strip)", 1.0053691243346485), ("atom #4 (subcritical)", 0.9919)):
    sol = deep_solve(beta)
    h = sol.hNrm
    print(f"\n=== {name}: h={h:.1f}  feasibility floor T > h*(1/r^2-1):"
          f" r=0.80 -> {h*(1/0.8**2-1):.0f},  r=0.90 -> {h*(1/0.9**2-1):.0f}")
    print(f"{'T':>6} {'r':>5} {'aug pts (m)':>18} {'Q1':>7} {'Q2':>7} {'drift/efold':>11} "
          f"{'max|dc|/c':>10} {'max|dg|/g':>10}")
    for T in (40.0, 100.0, 200.0, 400.0, 600.0, 800.0, 1300.0):
        for r in (0.8, 0.9):
            out = two_secant(sol, T, r)
            if out is None:
                print(f"{T:>6.0f} {r:>5.2f} {'infeasible (m<=0)':>18}")
                continue
            ms, Q1, Q2, drift = out
            ce, ge = attach_error(sol, T, Q2)
            print(f"{T:>6.0f} {r:>5.2f} {f'{ms[0]:.0f},{ms[1]:.0f}':>18} {Q1:>7.3f} {Q2:>7.3f} "
                  f"{drift:>+11.3f} {ce:>10.2e} {ge:>10.2e}")
