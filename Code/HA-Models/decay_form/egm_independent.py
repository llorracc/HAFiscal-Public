"""Independent from-scratch EGM (NO HARK) cross-check of the two-channel decomposition
g(m) = A*m^(-q*) + B*m^(-1).  Transitory-only (psi=1), lognormal theta.

HISTORICAL FILE -- two corrections of record (2026-07-05, theorem review R4):
(a) the original docstring claimed a "float128 gap"; in fact LD = np.longdouble was defined but
    never applied -- all arrays are float64 (immaterial: the measured window sits well above the
    fp64 cancellation floor);
(b) the fitted "B" this script reports is a crossover-WINDOW artifact, not the m->infinity
    amplitude, and its sigma-independence is an artifact of the same fit: see
    BufferStockTheory-Latest @ 716cfd82 :: theory/powerlaw-decay/  (public:
    https://llorracc.github.io/BufferStockTheory-Latest/powerlaw-decay-theory/)
    (Theorem A3: x*g -> kappa*(rho+1)*Var(theta)/(2*(R/G*P_G-1)),
    confirmed to 0.2%; numerics_appendix.md SS3 reproduces this script's ~0.2 fitted B on the
    same solution whose true tail amplitude is ~0.03).

Original purpose: (1) the m^-1 channel is REAL (independent of HARK); (2) min(1,q*) leading
exponent; (3) B(sigma) scaling of the FITTED coefficient.
"""
import numpy as np
from scipy.stats import norm

LD = np.longdouble


def lognormal_nodes(sigma, N=21):
    if sigma < 1e-9:
        return np.array([1.0]), np.array([1.0])
    s = np.sqrt(np.log(1.0 + sigma**2)); mu = -0.5 * s**2
    u = (np.arange(N) + 0.5) / N
    th = np.exp(mu + s * norm.ppf(u))
    th = th / th.mean()                 # renormalize E[theta]=1 exactly
    return th, np.full(N, 1.0 / N)


def kappa_min(R, beta, rho):
    return 1.0 - (R * beta) ** (1.0 / rho) / R


def qstar(R, G, beta, rho):
    PG = (R * beta) ** (1.0 / rho) / G
    return np.log(R / G) / np.log(1.0 / PG)


def eval_c(mq, m_grid, c_grid, km, h):
    """Consumption at query m: constrained (c=m) below the grid, PF asymptote above it."""
    c = np.interp(mq, m_grid, c_grid)
    c = np.where(mq < m_grid[0], mq, c)             # natural borrowing constraint: consume all
    c = np.where(mq > m_grid[-1], km * (mq + h), c)  # PF asymptote above the solved grid
    return c


def solve_egm(R, G, beta, rho, sigma, aMax=1e6, Na=4000, tol=1e-12, maxit=4000):
    th, p = lognormal_nodes(sigma)
    Reff = R / G                         # psi=1 -> m' = Reff*a + theta
    km = kappa_min(R, beta, rho)
    h = G / (R - G)                      # human wealth, transitory-only, E[theta]=1
    a = np.geomspace(1e-4, aMax, Na)     # fixed end-of-period asset grid
    disc = beta * R * G ** (-rho)
    m_grid = a + km * (a + h)            # init endogenous m
    c_grid = km * (a + h)                # init c = PF line
    mp = Reff * a[:, None] + th[None, :]  # (Na, N) next-period m
    err = np.inf
    for it in range(maxit):
        cp = eval_c(mp.ravel(), m_grid, c_grid, km, h).reshape(mp.shape)
        EvP = np.sum(p[None, :] * cp ** (-rho), axis=1)
        consumed = (disc * EvP) ** (-1.0 / rho)
        m_new = a + consumed
        err = np.max(np.abs(consumed - eval_c(m_new, m_grid, c_grid, km, h)))
        m_grid, c_grid = m_new, consumed
        if err < tol:
            break
    return m_grid, c_grid, km, h, it, err


def diagnose(tag, R, G, beta, rho, sigma):
    m_grid, c_grid, km, h, it, err = solve_egm(R, G, beta, rho, sigma)
    qs = qstar(R, G, beta, rho)
    # gap on a clean ladder (float64; reliable where g/c is above the solve/interp floor)
    mm = np.geomspace(50.0, 1e6, 220)
    cc = np.interp(mm, m_grid, c_grid)
    g = km * (mm + h) - cc
    rel = g / cc
    ok = (g > 0) & (rel > 1e-10) & np.isfinite(g)
    mm, g = mm[ok], g[ok]
    if len(mm) < 8:
        print(f"[{tag}] too few clean pts ({len(mm)}) it={it} err={err:.1e}"); return None
    lm, lg = np.log(mm), np.log(g)
    sl = np.gradient(lg, lm)
    # two-term fit g = A m^-q* + B m^-1
    X = np.column_stack([mm ** (-qs), mm ** (-1.0)])
    (A, B), *_ = np.linalg.lstsq(X, g, rcond=None)
    pred = X @ np.array([A, B])
    r2 = 1 - np.sum((g - pred) ** 2) / np.sum((g - g.mean()) ** 2)
    mcross = (abs(A) / abs(B)) ** (1.0 / (qs - 1.0)) if qs != 1 and B != 0 else np.nan
    print(f"[{tag}] R={R} G={G} beta={beta} sigma={sigma}  (EGM it={it}, err={err:.1e})")
    print(f"   km={km:.6f} h={h:.4f} q*={qs:.4f}  window m[{mm[0]:.0f},{mm[-1]:.0f}] ({len(mm)} pts)")
    print(f"   local slope: lo={sl[2]:.3f}  hi={sl[-3]:.3f}   two-term A={A:.4g} B={B:.4g} R2={r2:.5f}  m_cross={mcross:.3g}")
    return dict(tag=tag, sigma=sigma, A=float(A), B=float(B), q=float(-sl[-3]), qstar=qs)


print("=== INDEPENDENT EGM (float128 gap) ===")
print("\n-- case A (Gamma=1.01, R=1.04, beta=0.96): q*=2.72>1, expect leading m^-1 --")
diagnose("caseA", 1.04, 1.01, 0.96, 2.0, 0.10)
print("\n-- impatient (Gamma=1.0, R=1.01, beta=0.90): q*~0.21<1, expect leading m^-q* --")
diagnose("impatient", 1.01, 1.0, 0.90, 2.0, 0.10)
print("\n-- sigma sweep on case A: B(sigma)? --")
rows = []
for sig in [0.02, 0.05, 0.10, 0.15, 0.20]:
    r = diagnose(f"sig{sig}", 1.04, 1.01, 0.96, 2.0, sig)
    if r: rows.append(r)
print("\n  sigma     B         B/sigma^2     B/sigma")
for r in rows:
    s = r['sigma']
    print(f"  {s:.2f}    {r['B']:.4g}    {r['B']/s**2:.4g}      {r['B']/s:.4g}")
