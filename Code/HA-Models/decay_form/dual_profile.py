"""Q(x) profile + interior windowed drift for the College GIC-cap atom.

Solves once (env-config grid), then reports, at chosen abscissas x*, the local
exponent from a 5-knot regression window CENTERED at x* (endpoint-free), plus
the endpoint windows for comparison — separating location-drift from the
top-of-grid artifact."""
import os
import sys
import numpy as np

REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
for p in (os.path.join(REPO, "Code", "HA-Models"),
          os.path.join(REPO, "Code", "HA-Models", "FromPandemicCode")):
    sys.path.insert(0, p)
os.chdir(os.path.join(REPO, "Code", "HA-Models", "FromPandemicCode"))
os.environ.setdefault("HAFISCAL_INTERPRETATION", "ESC")

label = sys.argv[1]
_saved_argv_full = list(sys.argv)
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
    sys.argv = _saved_argv_full

ag = AggFiscalType(**init_college)
ag.cycles = 0
eco = AggregateDemandEconomy(**init_ADEconomy)
ag.get_economy_data(eco)
Du = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnemp])])
Dn = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnempNoBenefits])])
ag.IncShkDstn = [[ag.IncShkDstn[0]] + [Du] * ep.UBspell_normal + [Dn]]
ag.IncShkDstn_base = ag.IncShkDstn
ag.DiscFac = (0.9919255740493225 if (len(sys.argv) > 2 and sys.argv[2] == "central") else gic_capped_beta(2, theGICfactor))
ag.AgentCount = 1
ag.tm_a_indexed = True
eco.agents = [ag]
eco.solve()

seen, slices = set(), []
def walk(o, d=0):
    if id(o) in seen or d > 8:
        return
    seen.add(id(o))
    if isinstance(o, PowerLawDecayLinearInterp):
        slices.append(o); return
    for a in ("functions", "xInterpolators", "func", "function", "dfunc"):
        v = getattr(o, a, None)
        if v is None: continue
        for it in (v if isinstance(v, (list, tuple)) else [v]):
            walk(it, d + 1)
for f in ag.solution[0].cFunc:
    walk(f)
s = next(s for s in slices if getattr(s, "decay_extrap", False))
x = np.asarray(s.x_list, float); y = np.asarray(s.y_list, float)
mpc = float(s.slope_limit); h = float(s.intercept_limit) / mpc
pivot = x + h; gap = mpc * pivot - y
ok = (gap > 1e-10 * np.maximum(y, 1e-300)) & (x > 5.0)
x, pivot, gap = x[ok], pivot[ok], gap[ok]
lp, lg = np.log(pivot), np.log(gap)

def local_fit(i, w=2):
    j0, j1 = max(0, i - w), min(len(x), i + w + 1)
    A = np.vstack([np.ones(j1 - j0), lp[j0:j1]]).T
    c, *_ = np.linalg.lstsq(A, lg[j0:j1], rcond=None)
    return -c[1]

print(f"[{label}] grid top {x[-1]:.0f}, {len(x)} usable knots, h={h:.1f}")
print(f"{'x*':>9s} {'Q (5-knot centered)':>20s}")
targets = [300, 600, 1000, 2000, 4000, 8000, 16000, 30000, 45000]
prevQ, prevlp = None, None
for t in targets:
    if t > x[-2]:
        continue
    i = int(np.argmin(np.abs(x - t)))
    if i >= len(x) - 2:
        i = len(x) - 3
    Q = local_fit(i)
    dr = "" if prevQ is None else f"   drift vs prev: {(Q - prevQ) / (lp[i] - prevlp):+.4f}/e-fold"
    print(f"{x[i]:9.0f} {Q:20.4f}{dr}")
    prevQ, prevlp = Q, lp[i]
# endpoint windows for the artifact comparison
for tag, i in (("N-4 (interior-ish)", len(x) - 5), ("N-1 endpoint", len(x) - 2)):
    print(f"  window at {tag}: Q = {local_fit(i):.4f}")
