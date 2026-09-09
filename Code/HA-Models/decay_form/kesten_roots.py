import os, sys
import numpy as np
from scipy.optimize import brentq
REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
for p in (os.path.join(REPO, "Code", "HA-Models"), os.path.join(REPO, "Code", "HA-Models", "FromPandemicCode")):
    sys.path.insert(0, p)
os.chdir(os.path.join(REPO, "Code", "HA-Models", "FromPandemicCode"))
os.environ.setdefault("HAFISCAL_INTERPRETATION", "ESC")
_s = sys.argv; sys.argv = [sys.argv[0]]
try:
    import EstimParameters as ep
    from EstimParameters import init_college, gic_capped_beta, theGICfactor
    from AggFiscalModel import AggFiscalType
finally:
    sys.argv = _s
ag = AggFiscalType(**init_college)          # no solve needed
inc = ag.IncShkDstn[0]                   # employed-state joint (psi, xi)
psi, pmv = np.asarray(inc.atoms[0], float), np.asarray(inc.pmv, float)
R = float(np.asarray(ag.Rfree, float).flat[0]); G = float(ep.PermGroFac_base_c[0])
rho = float(ag.CRRA); L = float(np.asarray(ag.LivPrb, float).flat[0])

def root(beta, lo=1e-6, hi=64.0):
    PG = (R * beta * L) ** (1.0 / rho) / G
    def f(q):
        return np.log(np.dot(pmv, psi ** (1.0 + q))) - np.log(R / G) - q * np.log(PG)
    # continued root: ignore the PG>=1 guard; scan for a sign change
    grid = np.linspace(lo, hi, 20000)
    v = np.array([f(q) for q in grid])
    s = np.where(np.sign(v[:-1]) != np.sign(v[1:]))[0]
    return PG, [brentq(f, grid[i], grid[i + 1], xtol=1e-10) for i in s]

for name, b in (("cap 1.005369", gic_capped_beta(2, theGICfactor)),
                ("Ctop 0.9986", 0.99859), ("central 0.991926", 0.9919255740493225)):
    PG, roots = root(float(b))
    print(f"{name}: PG={PG:.6f}  continued Kesten root(s) = {[f'{r:.4f}' for r in roots]}")
