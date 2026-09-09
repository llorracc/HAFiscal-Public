"""gamma=0 identity check: with u=c, u'=1 the welfare Jacobian must
equal the consumption Jacobian BITWISE (same recursions, same seeds).
One cell (educ=1, beta index 3), param='transfers' (exercises the
income-dx path AND the BUG-072 direct column)."""
import os
import sys
import numpy as np
HA = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models"
sys.path.insert(0, HA)
sys.path.insert(0, os.path.join(HA, "FromPandemicCode"))
os.chdir(os.path.join(HA, "FromPandemicCode"))
from step4 import hh_setup, jacobians

ctx = hh_setup.build()
e, d = 1, 3
beta = float(ctx.DiscFacDstns[e].atoms[0][d])
IncDist = [ctx.IncShkDstn[e]]
IncDist_dx = [ctx.IncShkDstn_transfers_dx[e]]
dict_ = [ctx.init_dropout, ctx.init_highschool, ctx.init_college][e]
base = jacobians.prepare_type_base(ctx.BaseTypeList[e], dict_, beta, IncDist)

# gamma=0 arm: weights become u=c, u'=1 (solve already done at CRRA=2)
base["agent_SS"].CRRA = 0.0
CJ0, AJ0, WJ0, _, _, up0 = jacobians.compute_type_jacobian_for_param(
    base, IncDist, IncDist_dx, "transfers")
print(f"gamma=0: Uprime_mean={float(up0):.12f} (must be 1)")
print(f"gamma=0: J_W == J_C bitwise: {np.array_equal(WJ0, CJ0)}")
print(f"gamma=0: max|J_W-J_C| = {float(np.max(np.abs(WJ0-CJ0))):.3e}")

# real gamma=2 arm on the same base
base["agent_SS"].CRRA = 2.0
CJ2, AJ2, WJ2, _, _, up2 = jacobians.compute_type_jacobian_for_param(
    base, IncDist, IncDist_dx, "transfers")
print(f"gamma=2: Uprime_mean={float(up2):.6f}")
print(f"gamma=2: C/A unchanged vs gamma-0 arm: {np.array_equal(CJ2, CJ0)} {np.array_equal(AJ2, AJ0)}")
print(f"gamma=2: J_W impact J_W[0,0]={WJ2[0,0]:.6f} vs u'-mean*J_C[0,0]={float(up2)*CJ2[0,0]:.6f} (covariance gap is the signal)")
