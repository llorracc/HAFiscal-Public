"""p12: quantify the backward-chain convergence drift on the College
GIC-cap cell under LEGACY grids (why BUG-075 stayed invisible there)."""
import os
import sys
import numpy as np
os.environ["HAFISCAL_HANK_GRIDS"] = "legacy"
HA = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models"
sys.path.insert(0, HA)
sys.path.insert(0, os.path.join(HA, "FromPandemicCode"))
os.chdir(os.path.join(HA, "FromPandemicCode"))
from step4 import hh_setup, jacobians
ctx = hh_setup.build()
e, d = 2, 6
beta = float(ctx.DiscFacDstns[e].atoms[0][d])
IncDist = [ctx.IncShkDstn[e]]
dict_ = [ctx.init_dropout, ctx.init_highschool, ctx.init_college][e]
base = jacobians.prepare_type_base(ctx.BaseTypeList[e], dict_, beta, IncDist)
zp = base["zeroth_policies"]
c_ss = np.asarray(base["agent_SS"].cPol_Grid).flatten()
if zp is not None:
    zc = zp[0].reshape(300, -1)
    for t in (295, 150, 0):
        print(f"legacy College-cap: |c_ghost[t={t}] - c_SS| max = {np.abs(zc[t]-c_ss).max():.3e}")
