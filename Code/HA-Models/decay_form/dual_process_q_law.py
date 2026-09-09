"""Dual process: the law by which the local power-law exponent Q converges.

Owner design 2026-07-23: slide the two-secant window one knot at a time over the
TOP of the solved grid — Q from knots (k-2,k-1,k) vs (k-1,k,k+1) — giving the
local exponent Q at adjacent abscissas; the per-e-fold difference is the local
drift dQ/dln(x+h). If Q(x) -> Q_inf like C*(x+h)^(-p) then the drift series is
itself a pure power law with the SAME exponent p:
    drift(x) = dQ/dln(x+h) = p*C*(x+h)^(-p)
so ln(drift) vs ln(x+h) is linear with slope -p — no Q_inf needed — and
    Q_inf_hat = Q_top + drift_top / p_hat        (integrating the drift tail).
Alternative law check: exponential relaxation drift ~ exp(-r*(x+h)) would be
linear in ln(drift) vs (x+h) instead; report both R^2.

College GIC-cap atom (beta = gic_capped_beta(2)), real 4-state base economy —
the k_sweep_real_agent construction. Config from env (grid top/count).
"""
import os
import sys

import numpy as np

REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
HAM = os.path.join(REPO, "Code", "HA-Models")
FPC = os.path.join(HAM, "FromPandemicCode")
for p in (HAM, FPC):
    sys.path.insert(0, p)
os.chdir(FPC)
os.environ.setdefault("HAFISCAL_INTERPRETATION", "ESC")

label = sys.argv[1]

_saved = sys.argv
sys.argv = [sys.argv[0]]
try:
    import EstimParameters as ep
    from EstimParameters import (init_college, init_ADEconomy,
                                 gic_capped_beta, theGICfactor)
    from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
    from HARK.distributions import DiscreteDistribution
    from powerlaw_decay import PowerLawDecayLinearInterp
finally:
    sys.argv = _saved

ag = AggFiscalType(**init_college)
ag.cycles = 0
eco = AggregateDemandEconomy(**init_ADEconomy)
ag.get_economy_data(eco)
Du = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnemp])])
Dn = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnempNoBenefits])])
ag.IncShkDstn = [[ag.IncShkDstn[0]] + [Du] * ep.UBspell_normal + [Dn]]
ag.IncShkDstn_base = ag.IncShkDstn
ag.DiscFac = gic_capped_beta(2, theGICfactor)
ag.AgentCount = 1
ag.tm_a_indexed = True
eco.agents = [ag]
eco.solve()

# collect the decay-active slices
seen, slices = set(), []


def walk(o, depth=0):
    if id(o) in seen or depth > 8:
        return
    seen.add(id(o))
    if isinstance(o, PowerLawDecayLinearInterp):
        slices.append(o)
        return
    for attr in ("functions", "xInterpolators", "func", "function", "dfunc"):
        v = getattr(o, attr, None)
        if v is None:
            continue
        for it in (v if isinstance(v, (list, tuple)) else [v]):
            walk(it, depth + 1)


for f in ag.solution[0].cFunc:
    walk(f)
slices = [s for s in slices if getattr(s, "decay_extrap", False)]
print(f"[{label}] grid {init_college['aXtraMax']:.0f}/{init_college['aXtraCount']}"
      f"  decay-active slices: {len(slices)}")


def analyze(s):
    x = np.asarray(s.x_list, float)
    y = np.asarray(s.y_list, float)
    mpc = float(s.slope_limit)
    h = float(s.intercept_limit) / mpc
    pivot = x + h
    gap = mpc * pivot - y
    ok = (gap > 1e-10 * np.maximum(y, 1e-300)) & (x > 5.0)
    x, pivot, gap = x[ok], pivot[ok], gap[ok]
    if x.size < 8:
        return None
    lp, lg = np.log(pivot), np.log(gap)
    # adjacent-knot secants: Qs_j between knots j and j+1, at midpoint abscissa
    Qs = -(np.diff(lg)) / np.diff(lp)
    mid = 0.5 * (lp[:-1] + lp[1:])
    # the owner's two top windows: (N-3,N-2,N-1) vs (N-2,N-1,N)
    N = x.size
    win_prev = dict(Q1=Qs[-3], Q2=Qs[-2],
                    drift=(Qs[-2] - Qs[-3]) / (0.5 * (lp[-1 - 0] - lp[-4] )) if N >= 4 else np.nan)
    # per-window drift as defined in production: (Q2-Q1)/half-span of the triple
    def window(kend):  # triple (kend-2, kend-1, kend), 0-indexed into x
        q1 = -(lg[kend - 1] - lg[kend - 2]) / (lp[kend - 1] - lp[kend - 2])
        q2 = -(lg[kend] - lg[kend - 1]) / (lp[kend] - lp[kend - 1])
        half = 0.5 * (lp[kend] - lp[kend - 2])
        return q1, q2, (q2 - q1) / half
    qA1, qA2, dA = window(N - 2)   # (N-3, N-2, N-1)
    qB1, qB2, dB = window(N - 1)   # (N-2, N-1, N)
    # drift series: centered differences of Qs on the mid-abscissa
    d = np.diff(Qs) / np.diff(mid)
    dm = 0.5 * (mid[:-1] + mid[1:])
    pos = d > 0
    res = dict(h=h, mpc=mpc, N=N, x_top=x[-1],
               QA=(qA1, qA2, dA), QB=(qB1, qB2, dB))
    if pos.sum() >= 6:
        # power-law fit: ln d = ln(pC) - p * lnpivot
        A = np.vstack([np.ones(pos.sum()), dm[pos]]).T
        coef, *_ = np.linalg.lstsq(A, np.log(d[pos]), rcond=None)
        pred = A @ coef
        ss = 1 - np.sum((np.log(d[pos]) - pred) ** 2) / max(np.sum((np.log(d[pos]) - np.log(d[pos]).mean()) ** 2), 1e-300)
        p_hat = -coef[1]
        # exponential-law alternative: ln d vs pivot
        Ae = np.vstack([np.ones(pos.sum()), np.exp(dm[pos])]).T
        coefe, *_ = np.linalg.lstsq(Ae, np.log(d[pos]), rcond=None)
        prede = Ae @ coefe
        sse = 1 - np.sum((np.log(d[pos]) - prede) ** 2) / max(np.sum((np.log(d[pos]) - np.log(d[pos]).mean()) ** 2), 1e-300)
        # Q_inf via the drift-tail integral, using the top-window drift dB
        drift_top = dB if dB > 0 else (d[pos][-1] if pos.any() else np.nan)
        Q_inf = qB2 + (drift_top / p_hat if p_hat > 0 else np.nan)
        res.update(p_hat=p_hat, r2_pow=ss, r2_exp=sse, n_fit=int(pos.sum()),
                   efolds=float(dm[pos][-1] - dm[pos][0]), Q_inf=Q_inf,
                   drift_top=drift_top)
    return res


rows = [r for r in (analyze(s) for s in slices) if r]
print(f"[{label}] per-slice dual-process fits ({len(rows)} usable slices):")
print(f"{'h':>7s} {'x_top':>7s} {'Q(A):N-1 win':>13s} {'Q(B):N win':>11s} "
      f"{'driftB':>8s} {'p_hat':>7s} {'R2pow':>6s} {'R2exp':>6s} {'efolds':>6s} {'Q_inf':>7s}")
for r in rows:
    qa, qb = r["QA"], r["QB"]
    if "p_hat" in r:
        print(f"{r['h']:7.1f} {r['x_top']:7.1f} {qa[1]:13.4f} {qb[1]:11.4f} "
              f"{qb[2]:8.4f} {r['p_hat']:7.3f} {r['r2_pow']:6.3f} {r['r2_exp']:6.3f} "
              f"{r['efolds']:6.2f} {r['Q_inf']:7.3f}")
    else:
        print(f"{r['h']:7.1f} {r['x_top']:7.1f} {qa[1]:13.4f} {qb[1]:11.4f} {qb[2]:8.4f}   (insufficient positive-drift points)")
ps = [r["p_hat"] for r in rows if "p_hat" in r]
qinfs = [r["Q_inf"] for r in rows if "p_hat" in r and np.isfinite(r.get("Q_inf", np.nan))]
if ps:
    print(f"[{label}] median p_hat = {np.median(ps):.3f}  (range {min(ps):.3f}..{max(ps):.3f});"
          f"  median Q_inf_hat = {np.median(qinfs):.3f}" if qinfs else "")
