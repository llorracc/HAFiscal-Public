"""Two-anchor bridge test: can an ANALYTICALLY-anchored varying-Q tail beat the
constant measured-Q tail deep above aMax?

From a production-top solve (K=3 -> 591), anchor the tail at the top knot with
the PRODUCTION estimator's measured Q, then extrapolate two ways:
  T1 constant-Q:  gap(u) = gap_top * exp(-Q_hat * u),          u = ln(pivot/pivot_top)
  T2 bridge:      Q(u) = q_inf - (q_inf - Q_hat) * exp(-nu*u)  (ChiTailNu family:
                  measured near anchor, ANALYTICAL far anchor q_inf = Kesten root,
                  ANALYTICAL rate nu = min(q_inf, 1-q_inf))
                  gap(u) = gap_top * exp(-[q_inf*u - (q_inf-Q_hat)*(1-e^(-nu u))/nu])
Truth: a SOLVE_AMAX=50000 solve of the same atom (in-sample there).
Reports relative c-error of each tail vs truth at test points above 591.
Atom via argv: cap | central. Second bridge arm for cap: the empirical
plateau anchor 0.69 (its own root 1.374 is the in-range-invisible supercritical
object; that mismatch is the point of the cap arm).
"""
import os
import sys
import numpy as np

REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
for p in (os.path.join(REPO, "Code", "HA-Models"),
          os.path.join(REPO, "Code", "HA-Models", "FromPandemicCode")):
    sys.path.insert(0, p)
os.chdir(os.path.join(REPO, "Code", "HA-Models", "FromPandemicCode"))
os.environ.setdefault("HAFISCAL_INTERPRETATION", "ESC")

atom = sys.argv[1]
_saved = list(sys.argv)
sys.argv = [sys.argv[0]]
try:
    import EstimParameters as ep
    from EstimParameters import (init_college, init_ADEconomy,
                                 gic_capped_beta, theGICfactor)
    from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
    from HARK.distributions import DiscreteDistribution
    from powerlaw_decay import PowerLawDecayLinearInterp
    from local_q_tail import local_q_from_knots
finally:
    sys.argv = _saved

BETA = {"cap": float(gic_capped_beta(2, theGICfactor)), "central": 0.9919255740493225}[atom]
ROOT = {"cap": 1.3739, "central": 0.5470}[atom]          # continued Kesten roots (from primitives)
EMP = {"cap": 0.690, "central": None}[atom]              # cap: measured reachable plateau


def solve(amax_env):
    if amax_env:
        os.environ["HAFISCAL_SOLVE_AMAX"] = amax_env
    else:
        os.environ.pop("HAFISCAL_SOLVE_AMAX", None)
    import importlib
    _argv = list(sys.argv)
    sys.argv = [sys.argv[0]]      # EstimParameters parses argv at module exec
    try:
        importlib.reload(ep)      # re-run the grid block under the new env
    finally:
        sys.argv = _argv
    from EstimParameters import init_college as ic, init_ADEconomy as ia
    ag = AggFiscalType(**ic)
    ag.cycles = 0
    eco = AggregateDemandEconomy(**ia)
    ag.get_economy_data(eco)
    Du = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnemp])])
    Dn = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnempNoBenefits])])
    ag.IncShkDstn = [[ag.IncShkDstn[0]] + [Du] * ep.UBspell_normal + [Dn]]
    ag.IncShkDstn_base = ag.IncShkDstn
    ag.DiscFac = BETA
    ag.AgentCount = 1
    ag.tm_a_indexed = True
    eco.agents = [ag]
    eco.solve()
    seen, out = set(), []

    def walk(o, d=0):
        if id(o) in seen or d > 8:
            return
        seen.add(id(o))
        if isinstance(o, PowerLawDecayLinearInterp):
            out.append(o)
            return
        for a in ("functions", "xInterpolators", "func", "function", "dfunc"):
            v = getattr(o, a, None)
            if v is None:
                continue
            for it in (v if isinstance(v, (list, tuple)) else [v]):
                walk(it, d + 1)
    for f in ag.solution[0].cFunc:
        walk(f)
    s = next(x for x in out if getattr(x, "decay_extrap", False))
    return s


s591 = solve(None)                      # production top (K*hbar = 591)
x = np.asarray(s591.x_list, float); y = np.asarray(s591.y_list, float)
mpc = float(s591.slope_limit); h = float(s591.intercept_limit) / mpc
lq = local_q_from_knots(x, y, h, mpc)   # the production estimator at the top
Q_hat = float(lq["Q"])
p_top = x[-1] + h
gap_top = mpc * p_top - y[-1]

s50k = solve("50000")                   # truth grid
xt = np.asarray(s50k.x_list, float); yt = np.asarray(s50k.y_list, float)

tests = [1300.0, 3000.0, 8000.0, 20000.0, 45000.0]
print(f"[{atom}] beta={BETA:.6f}  Q_hat(top-591, production estimator)={Q_hat:.4f}  "
      f"root={ROOT}  gap_top/c_top={gap_top / y[-1]:.4f}")
print(f"{'m':>7s} {'truth c':>10s} {'T1 const-Q err':>14s} {'T2 bridge(root) err':>19s}"
      + ("  T2b bridge(0.69) err" if EMP else ""))
for m in tests:
    u = np.log((m + h) / p_top)
    c_true = float(np.interp(m, xt, yt))
    line = mpc * (m + h)
    gap1 = gap_top * np.exp(-Q_hat * u)
    c1 = line - gap1
    def bridge(qi):
        nu = min(qi, abs(1.0 - qi)) if 0 < qi < 1 else 0.31
        integ = qi * u - (qi - Q_hat) * (1.0 - np.exp(-nu * u)) / nu
        return line - gap_top * np.exp(-integ)
    c2 = bridge(ROOT)
    row = (f"{m:7.0f} {c_true:10.4f} {abs(c1 - c_true) / c_true:14.2e} "
           f"{abs(c2 - c_true) / c_true:19.2e}")
    if EMP:
        row += f" {abs(bridge(EMP) - c_true) / c_true:19.2e}"
    print(row)
