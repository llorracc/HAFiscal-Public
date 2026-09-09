"""BUG-071 step 0, decisive: under HARK 0.14.1, does a solve on the QE construction (deepcopy + positional atoms[1]*=0.7)
equal a solve on a distribution REBUILT with TranShk*0.7 (post-scaling), or the UNSCALED solve (pre-scaling)?"""
import numpy as np, copy, HARK
from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType, init_idiosyncratic_shocks
from HARK.distribution import DiscreteDistributionLabeled
p = dict(init_idiosyncratic_shocks); p.update(cycles=0, T_cycle=1)
def solved_c(dstn):
    a = IndShockConsumerType(**p); a.update_income_process(); a.IncShkDstn = [dstn]; a.solve()
    m = np.linspace(0.5, 10, 25); return a.solution[0].cFunc(m)
base = IndShockConsumerType(**p); base.update_income_process(); d0 = base.IncShkDstn[0]
c_unscaled = solved_c(copy.deepcopy(d0))
qe = copy.deepcopy(d0); qe.atoms[1] = qe.atoms[1] * 0.7                      # the QE HANK construction
c_qe = solved_c(qe)
atoms = np.asarray(d0.atoms).copy(); atoms[1] = atoms[1] * 0.7
rebuilt = DiscreteDistributionLabeled(pmv=np.asarray(d0.pmv), atoms=atoms, var_names=["PermShk", "TranShk"], seed=0)
c_rebuilt = solved_c(rebuilt)
print("HARK", HARK.__version__)
print("max|c_qe - c_rebuilt(post-scaling)| =", float(np.max(np.abs(c_qe - c_rebuilt))))
print("max|c_qe - c_unscaled(pre-scaling)| =", float(np.max(np.abs(c_qe - c_unscaled))))
print("max|c_rebuilt - c_unscaled|         =", float(np.max(np.abs(c_rebuilt - c_unscaled))))
