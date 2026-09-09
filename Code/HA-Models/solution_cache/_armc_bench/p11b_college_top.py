"""p11b: the College GIC-cap top atom (e=2,d=6) under PE grids —
distribution + J diagnostics (the suspect cell class)."""
import os
import sys
import numpy as np

os.environ["HAFISCAL_HANK_GRIDS"] = os.environ.get("P11_GRIDS", "pe")
HA = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models"
sys.path.insert(0, HA)
sys.path.insert(0, os.path.join(HA, "FromPandemicCode"))
os.chdir(os.path.join(HA, "FromPandemicCode"))
from step4 import hh_setup, jacobians

ctx = hh_setup.build()
e, d = 2, 6
beta = float(ctx.DiscFacDstns[e].atoms[0][d])
print(f"cell e={e} d={d} beta={beta:.6f}  grids={os.environ['HAFISCAL_HANK_GRIDS']}")
IncDist = [ctx.IncShkDstn[e]]
IncDist_dx = [ctx.IncShkDstn_ui_extend_dx[e]]
dict_ = [ctx.init_dropout, ctx.init_highschool, ctx.init_college][e]
print(f"solve aXtraMax={dict_['aXtraMax']:.1f}/{dict_['aXtraCount']}  dist {dict_['mCount']}/{dict_['mMax']}")

base = jacobians.prepare_type_base(ctx.BaseTypeList[e], dict_, beta, IncDist)
ss = base["agent_SS"]
grid = np.asarray(ss.dist_mGrid)
D = np.asarray(ss.vec_erg_dstn).flatten()
nm = len(grid)
Dm = D.reshape(-1, nm)
top = float(dict_['aXtraMax'])
print(f"D: min={D.min():.3e} max={D.max():.3e} sum={D.sum():.6f} neg-mass={D[D<0].sum():.3e}")
print(f"mass beyond solve-top: {Dm[:, grid > top].sum():.4e}; at top point: {Dm[:, -1].sum():.4e}")
print(f"C_ss={float(ss.C_ss):.5f}  A_ss={float(ss.A_ss):.4f}")
cpol = np.asarray(ss.cPol_Grid)
print(f"cPol at top 4 grid pts (state 0): {cpol[0][-4:]}")
CJ, AJ, WJ, C_ss, A_ss, up = jacobians.compute_type_jacobian_for_param(
    base, IncDist, IncDist_dx, "UI_extend")
print(f"max|J_C|={np.abs(CJ).max():.4e}  J_C[0,0]={CJ[0,0]:.4e}  frac|J|>1: {(np.abs(CJ)>1).mean():.4f}")

# column decomposition + python arm
print(f"[decomp] |J_C[:,0]|max={np.abs(CJ[:,0]).max():.4e}  |J_C[:,1:]|max={np.abs(CJ[:,1:]).max():.4e}  |J_C diag 1:|={np.abs(np.diag(CJ)[1:]).max():.4e}")
import step4.common as CM
os.environ["HAFISCAL_STEP4_FAST_BACKWARD"] = "0"
CM._FASTBACK_MODS = None
base2 = jacobians.prepare_type_base(ctx.BaseTypeList[e], dict_, beta, IncDist)
CJp, AJp, WJp, _, _, _ = jacobians.compute_type_jacobian_for_param(
    base2, IncDist, IncDist_dx, "UI_extend")
print(f"[python arm] max|J_C|={np.abs(CJp).max():.4e}  J_C[0,0]={CJp[0,0]:.4e}  "
      f"|col0|max={np.abs(CJp[:,0]).max():.4e}  |body|max={np.abs(CJp[:,1:]).max():.4e}")
print(f"kernel-vs-python max|diff|={np.abs(CJ-CJp).max():.4e}")

# hypothesis probes: builder mismatch vs mass non-conservation
ssM = np.asarray(base2["agent_SS"].tran_matrix)
print(f"[H-b] SS tranmat rowsum dev: max|colsum-1|={np.abs(ssM.sum(axis=0)-1).max():.3e}")
fhM = np.asarray(base2["FinHorizonAgent"].tran_matrix)
mid = 5  # far from the shock slot
d5 = np.abs(fhM[mid] - ssM)
print(f"[H-a] FH[t={mid}] vs SS tranmat: max|diff|={d5.max():.3e}  at flat-idx={d5.argmax()}")
c_ss_v = np.asarray(base2["agent_SS"].cPol_Grid).flatten()
Dv = np.asarray(base2["agent_SS"].vec_erg_dstn)
dcur = Dv.copy()
for t in range(10):
    dcur = ssM @ dcur
    if t in (0, 4, 9):
        print(f"[H-c] t={t+1}: C-drift={float(c_ss_v @ dcur) - float(base2['agent_SS'].C_ss):+.3e}  mass-drift={float(dcur.sum())-1:+.3e}")

# MECHANISM PROBE: dated-vs-SS policy mismatch BY GRID REGION at an
# un-shocked distance (FH period 5 solved back from the SS terminal —
# should equal SS up to anticipation ~O(dx) everywhere; if the mismatch
# is ~0 in-grid but large at the extrapolated top points, the
# extrapolation instability is the mechanism.
fh = base2["FinHorizonAgent"]
c_fh5 = np.asarray(fh.cPol_Grid[5]).flatten()
c_ssv = np.asarray(base2["agent_SS"].cPol_Grid).flatten()
gridv = np.asarray(base2["agent_SS"].dist_mGrid)
nmv = len(gridv)
dpol = np.abs(c_fh5 - c_ssv).reshape(-1, nmv)
in_grid = gridv <= float(dict_['aXtraMax'])
print(f"[MECH] |c_FH[t=5] - c_SS|: max IN-grid={dpol[:, in_grid].max():.3e}  "
      f"max at EXTRAP points={dpol[:, ~in_grid].max():.3e}")
print(f"[MECH] extrap-point values c_SS={c_ssv.reshape(-1,nmv)[0,~in_grid]}  "
      f"c_FH5={c_fh5.reshape(-1,nmv)[0,~in_grid]}")
