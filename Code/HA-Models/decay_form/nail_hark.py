"""Nail the two-channel decomposition: g(m) = A*m^(-q*) + B*m^(-1).
HARK IndShockConsumerType, transitory-only, deep grid. Tests:
 (1) case A (q*>1): two-term fit (q* fixed) vs single-term; A,B; m_cross; local slope.
 (2) impatient q*<1 case: leading exponent = q* (Kesten).
 (3) sigma sweep: B proportional to sigma^2.
"""
import numpy as np
np.seterr(all='ignore')
from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType


def Pthorn_G(R, G, beta, rho):
    return (R * beta) ** (1.0 / rho) / G


def qstar(R, G, beta, rho):
    PG = Pthorn_G(R, G, beta, rho)
    return np.log(R / G) / np.log(1.0 / PG)


def solve(R, G, beta, rho, sigma_theta, aMax=1e7, aCount=800):
    a = IndShockConsumerType(
        CRRA=rho, Rfree=[R], DiscFac=beta, PermGroFac=[G], LivPrb=[1.0],
        cycles=0, PermShkStd=[1e-9], PermShkCount=1, TranShkCount=11,
        TranShkStd=[sigma_theta], UnempPrb=0.0, BoroCnstArt=0.0,
        aXtraMin=1e-4, aXtraMax=aMax, aXtraCount=aCount, aXtraNestFac=4,
    )
    a.solve()
    s = a.solution[0]
    return s.cFunc, float(s.MPCmin), float(s.hNrm)


def gap_on_ladder(cFunc, kmin, h, m_lo=20.0, m_hi=1e6, n=200):
    m = np.geomspace(m_lo, m_hi, n)
    c = cFunc(m)
    line = kmin * (m + h)
    g = line - c
    rel = g / np.maximum(c, 1e-300)
    # clean window: g positive, monotone-ish, above ~1e-11 relative (float64 floor guard)
    ok = (g > 0) & (rel > 1e-11) & np.isfinite(g)
    return m[ok], g[ok], rel[ok]


def local_loglog_slope(m, g):
    lm, lg = np.log(m), np.log(g)
    # central-difference local slope d log g / d log m
    sl = np.gradient(lg, lm)
    return sl


def two_term_fit(m, g, qs):
    # g = A*m^-qs + B*m^-1   (linear in A,B)
    X = np.column_stack([m ** (-qs), m ** (-1.0)])
    coef, res, *_ = np.linalg.lstsq(X, g, rcond=None)
    A, B = coef
    pred = X @ coef
    ss_res = np.sum((g - pred) ** 2)
    ss_tot = np.sum((g - g.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot
    return A, B, r2


def one_term_fit(m, g, p):
    X = (m ** (-p)).reshape(-1, 1)
    coef, *_ = np.linalg.lstsq(X, g, rcond=None)
    pred = X @ coef
    r2 = 1 - np.sum((g - pred) ** 2) / np.sum((g - g.mean()) ** 2)
    return float(coef[0]), r2


def report(tag, R, G, beta, rho, sigma):
    qs = qstar(R, G, beta, rho)
    cF, kmin, h = solve(R, G, beta, rho, sigma)
    m, g, rel = gap_on_ladder(cF, kmin, h)
    if len(m) < 10:
        print(f"[{tag}] too few clean points ({len(m)})"); return None
    A, B, r2_two = two_term_fit(m, g, qs)
    A1, r2_qs = one_term_fit(m, g, qs)
    B1, r2_one = one_term_fit(m, g, 1.0)
    sl = local_loglog_slope(m, g)
    mcross = (abs(A) / abs(B)) ** (1.0 / (qs - 1.0)) if qs != 1 and B != 0 else np.nan
    print(f"\n[{tag}] R={R} G={G} beta={beta} rho={rho} sigma_theta={sigma}")
    print(f"  kappa_min={kmin:.6f}  h={h:.4f}  q*={qs:.4f}  Pthorn_G={Pthorn_G(R,G,beta,rho):.6f}")
    print(f"  clean window m in [{m[0]:.0f}, {m[-1]:.0f}]  ({len(m)} pts)")
    print(f"  local log-log slope: at m={m[0]:.0f} -> {sl[2]:.3f};  at m={m[-1]:.0f} -> {sl[-3]:.3f}")
    print(f"  TWO-term fit g=A*m^-q* + B*m^-1 : A={A:.4g}  B={B:.4g}  R2={r2_two:.6f}")
    print(f"  one-term m^-q* only : A={A1:.4g}  R2={r2_qs:.6f}")
    print(f"  one-term m^-1   only : B={B1:.4g}  R2={r2_one:.6f}")
    print(f"  implied m_cross=(A/B)^(1/(q*-1)) = {mcross:.4g}")
    return dict(tag=tag, R=R, G=G, beta=beta, sigma=sigma, qstar=qs, A=A, B=B,
               r2_two=r2_two, r2_qs=r2_qs, r2_one=r2_one, mcross=mcross,
               slope_lo=float(sl[2]), slope_hi=float(sl[-3]))


print("=" * 70)
print("(1) case A: Gamma=1.01, R=1.04, beta=0.96  -> q* > 1")
rA = report("caseA", 1.04, 1.01, 0.96, 2.0, 0.10)

print("\n" + "=" * 70)
print("(2) impatient low-growth: Gamma=1.0, R=1.01, beta=0.90 -> q* < 1")
r2 = report("impatient", 1.01, 1.0, 0.90, 2.0, 0.10)

print("\n" + "=" * 70)
print("(3) Gamma=1 near-knife-edge: Gamma=1.0, R=1.04, beta=0.96 -> q* huge")
r3 = report("gamma1", 1.04, 1.0, 0.96, 2.0, 0.10)

print("\n" + "=" * 70)
print("(4) sigma sweep on case A: is B proportional to sigma^2 ?")
rows = []
for sig in [0.05, 0.10, 0.15]:
    r = report(f"caseA_sig{sig}", 1.04, 1.01, 0.96, 2.0, sig)
    if r: rows.append((sig, r['A'], r['B']))
print("\n  sigma   A        B        B/sigma^2")
for sig, A, B in rows:
    print(f"  {sig:.2f}   {A:.4g}   {B:.4g}   {B/sig**2:.4g}")
print("\n(B/sigma^2 ~ constant  => Jensen channel amplitude proportional to variance, confirming p=1 forcing)")
