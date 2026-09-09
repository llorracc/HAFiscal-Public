"""p11: localize the PE-grid Jacobian corruption. One cell (e=1,d=3),
param=UI_extend, PE grids: kernel arm vs certified-python arm.
Under LEGACY grids the dist top (1e5) < solve top (1e6) so the
beyond-solve-top region was never exercised; PE grids invert that."""
import os
import sys
import numpy as np

os.environ["HAFISCAL_HANK_GRIDS"] = "pe"
HA = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models"
sys.path.insert(0, HA)
sys.path.insert(0, os.path.join(HA, "FromPandemicCode"))
os.chdir(os.path.join(HA, "FromPandemicCode"))

from step4 import hh_setup, jacobians

ctx = hh_setup.build()
e, d = 1, 3
beta = float(ctx.DiscFacDstns[e].atoms[0][d])
IncDist = [ctx.IncShkDstn[e]]
IncDist_dx = [ctx.IncShkDstn_ui_extend_dx[e]]
dict_ = [ctx.init_dropout, ctx.init_highschool, ctx.init_college][e]
print(f"solve grid: aXtraMax={dict_['aXtraMax']} aXtraCount={dict_['aXtraCount']}; "
      f"dist mCount={dict_['mCount']} mMax={dict_['mMax']}")

def run_arm(fb):
    os.environ["HAFISCAL_STEP4_FAST_BACKWARD"] = fb
    import step4.common as C
    C._FASTBACK_MODS = None  # reset loader cache between arms
    base = jacobians.prepare_type_base(ctx.BaseTypeList[e], dict_, beta, IncDist)
    grid = np.asarray(base["agent_SS"].dist_mGrid)
    top = dict_['aXtraMax']
    print(f"  dist grid top points: {grid[-4:]}; points > solve-top({top}): {(grid > top).sum()}")
    D = np.asarray(base["agent_SS"].vec_erg_dstn).flatten()
    nm = len(grid)
    Dm = D.reshape(-1, nm) if D.size % nm == 0 else None
    if Dm is not None:
        print(f"  ergodic mass on dist points > solve-top: {Dm[:, grid > top].sum():.3e}; on top point: {Dm[:, -1].sum():.3e}")
    CJ, AJ, WJ, C_ss, A_ss, up = jacobians.compute_type_jacobian_for_param(
        base, IncDist, IncDist_dx, "UI_extend")
    print(f"  C_ss={C_ss:.5f} A_ss={A_ss:.4f}  max|J_C|={np.abs(CJ).max():.4e}  "
          f"J_C[0,0]={CJ[0,0]:.4e}  J_C[10,10]={CJ[10,10]:.4e}  frac|J|>1: {(np.abs(CJ)>1).mean():.3f}")
    return CJ

print("=== ARM A: kernel (FAST_BACKWARD=1) ===")
CJ_k = run_arm("1")
print("=== ARM B: certified python (FAST_BACKWARD=0) ===")
CJ_p = run_arm("0")
print(f"\nkernel-vs-python: max|diff|={np.abs(CJ_k-CJ_p).max():.4e}  "
      f"python max|J|={np.abs(CJ_p).max():.4e}  kernel max|J|={np.abs(CJ_k).max():.4e}")
